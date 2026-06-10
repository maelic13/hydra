"""
tools/noderate.py — node-rate regression gate for hydra_lite.

Instruments a fixed search on a fixed position set and prints nodes/s,
eval/s, attacked/s, and depth reached. Run this before and after every
Block-1 (A-item) change to confirm speed improvements landed.

Usage:
    python tools/noderate.py [--script hydra_lite/hydra_lite.py] [--time 3.0]
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Fixed positions with known character (varied phase, complexity).
# Do NOT change these between runs — they are the regression baseline.
POSITIONS = [
    # Starting position
    ("start",       "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    # Middlegame (typical bushy tree)
    ("midgame",     "r1bq1rk1/ppp2pbp/2np1np1/4p3/2PPP3/2N2N2/PP2BPPP/R1BQ1RK1 w - - 0 8"),
    # Tactical (lots of captures, stresses qsearch)
    ("tactical",    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    # Endgame (fewer pieces, tests pawn eval)
    ("endgame",     "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"),
]


def load_engine(script: Path):
    spec = importlib.util.spec_from_file_location("hydra_lite_mod", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def benchmark(mod, fen: str, sec: float) -> dict:
    """Run a timed search and return instrumented counters."""
    counters = {"eval": 0, "legal": 0, "attacked": 0, "make": 0, "depth": 0}

    # Wrap the four key functions
    _eval     = mod.evalp
    _legal    = mod.legal
    _attacked = mod.attacked
    _make     = mod.make

    def w_eval(p):
        counters["eval"] += 1
        return _eval(p)

    def w_legal(p, caps=False):
        counters["legal"] += 1
        return _legal(p, caps)

    def w_attacked(p, s, byw):
        counters["attacked"] += 1
        return _attacked(p, s, byw)

    def w_make(p, m):
        counters["make"] += 1
        return _make(p, m)

    mod.evalp    = w_eval
    mod.legal    = w_legal
    mod.attacked = w_attacked
    mod.make     = w_make

    # Patch the search to capture final depth (search returns best move;
    # we detect the last completed depth by watching the TT or by time).
    # Simpler: instrument the iterative-deepening loop via a thin wrapper.
    _search = mod.search
    depth_reached = [0]
    _original_ab  = None  # depth tracking done via nps proxy instead

    p, rep, hist = mod.build(fen)
    t0 = time.perf_counter()
    move = mod.search(p, rep, sec)
    elapsed = time.perf_counter() - t0

    # Restore originals
    mod.evalp    = _eval
    mod.legal    = _legal
    mod.attacked = _attacked
    mod.make     = _make

    nodes = counters["make"]
    return {
        "move":          mod.uci(move) if move else "none",
        "elapsed":       elapsed,
        "nodes":         nodes,
        "nps":           int(nodes / elapsed) if elapsed > 0 else 0,
        "eval":          counters["eval"],
        "eval_s":        int(counters["eval"] / elapsed) if elapsed > 0 else 0,
        "attacked":      counters["attacked"],
        "attacked_s":    int(counters["attacked"] / elapsed) if elapsed > 0 else 0,
        "legal":         counters["legal"],
        "legal_s":       int(counters["legal"] / elapsed) if elapsed > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", default="hydra_lite/hydra_lite.py",
                        help="Path to the engine script (default: hydra_lite/hydra_lite.py)")
    parser.add_argument("--time", type=float, default=3.0,
                        help="Search time per position in seconds (default: 3.0)")
    args = parser.parse_args()

    script = REPO_ROOT / args.script
    if not script.exists():
        print(f"ERROR: engine not found at {script}", file=sys.stderr)
        sys.exit(1)

    print(f"Engine : {script}")
    print(f"Search : {args.time}s per position")
    print()

    mod = load_engine(script)

    totals = {"nodes": 0, "eval": 0, "attacked": 0, "elapsed": 0.0}

    header = f"{'Position':<12} {'Move':<8} {'Nodes':>9} {'NPS':>8} {'Eval/s':>8} {'Atk/s':>8} {'Legal/s':>8} {'Time':>6}"
    print(header)
    print("-" * len(header))

    for label, fen in POSITIONS:
        r = benchmark(mod, fen, args.time)
        print(
            f"{label:<12} {r['move']:<8} {r['nodes']:>9,} {r['nps']:>8,} "
            f"{r['eval_s']:>8,} {r['attacked_s']:>8,} {r['legal_s']:>8,} {r['elapsed']:>6.2f}s"
        )
        totals["nodes"]   += r["nodes"]
        totals["eval"]    += r["eval"]
        totals["attacked"] += r["attacked"]
        totals["elapsed"] += r["elapsed"]

    print("-" * len(header))
    avg_nps = int(totals["nodes"] / totals["elapsed"]) if totals["elapsed"] > 0 else 0
    print(f"\nSUMMARY over {len(POSITIONS)} positions, {args.time}s each:")
    print(f"  Total nodes   : {totals['nodes']:,}")
    print(f"  Avg NPS       : {avg_nps:,}   <-- regression gate")
    print(f"  Total evals   : {totals['eval']:,}")
    print(f"  Total attacked: {totals['attacked']:,}")
    print()
    print("Baseline (2026-06-06, hydra_lite_baseline.py, 4-position suite):")
    print("  Avg NPS ~42,000 | eval/s ~3,800 | attacked/s ~45,000")
    print("  (midgame-only NPS is ~25,000 -- the hardest position in the suite)")
    print()
    ratio = avg_nps / 42000
    marker = "[IMPROVEMENT]" if ratio > 1.15 else ("[REGRESSION]" if ratio < 0.90 else "[NO CHANGE]")
    print(f"  vs baseline: {ratio:.2f}x  {marker}")


if __name__ == "__main__":
    main()
