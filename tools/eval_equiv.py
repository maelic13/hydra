#!/usr/bin/env python3
r"""Eval-equivalence checker: prove two engine versions compute identical evalp().

Use for pure-speed eval refactors (e.g. step A4 passed-pawn rewrite): the new
code must return the *exact same* evalp() value as the reference on every
position of a long seeded random playout. Any mismatch = the refactor changed
behavior, not just speed -> fix before running any SPRT.

NOT for eval *changes* (PeSTO, new terms) - those are supposed to differ.

Usage:
    # Before editing, snapshot the current engine as the reference:
    #   Copy-Item hydra_lite\hydra_lite.py tmp_eval_ref.py
    # After editing:
    python tools/eval_equiv.py --ref tmp_eval_ref.py --new hydra_lite/hydra_lite.py

Exit code 0 = PASS (identical), 1 = FAIL (first mismatch printed).
"""

import argparse
import importlib.util
import random
import sys
from pathlib import Path

FENS = [
    ("start",     "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("midgame",   "r1bq1rk1/ppp2pbp/2np1np1/4p3/2PPP3/2N2N2/PP2BPPP/R1BQ1RK1 w - - 0 8"),
    ("tactical",  "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    ("endgame",   "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"),
    ("promotion", "8/2P3k1/8/8/8/8/4Kp2/8 w - - 0 1"),
]


def load(path: str, name: str):
    p = Path(path)
    if not p.exists():
        print(f"ERROR: not found: {p}", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", required=True, help="Reference engine .py (pre-edit snapshot)")
    ap.add_argument("--new", required=True, help="Edited engine .py")
    ap.add_argument("--moves", type=int, default=150, help="Half-moves per playout (default 150)")
    ap.add_argument("--seeds", type=int, default=3, help="Playouts per position (default 3)")
    args = ap.parse_args()

    ref = load(args.ref, "eval_ref_mod")
    new = load(args.new, "eval_new_mod")

    checked = 0
    for label, fen in FENS:
        for seed in range(args.seeds):
            pr, _, _ = ref.build(fen)
            pn, _, _ = new.build(fen)
            rng = random.Random(seed)
            for step in range(args.moves):
                vr = ref.evalp(pr)
                vn = new.evalp(pn)
                checked += 1
                if vr != vn:
                    print(f"FAIL: evalp mismatch at {label} seed={seed} step={step}: "
                          f"ref={vr} new={vn}")
                    print(f"  board: {''.join(pr.b)}  w={pr.w} c={pr.c!r} e={pr.e}")
                    sys.exit(1)
                moves = ref.legal(pr)
                if not moves:
                    break
                m = rng.choice(moves)
                ms = ref.uci(m)
                mn = new.parseuci(pn, ms)
                if mn is None:
                    print(f"FAIL: move {ms} legal in ref but not parsed by new "
                          f"({label} seed={seed} step={step}) - movegen divergence!")
                    sys.exit(1)
                ref.make(pr, m)
                new.make(pn, mn)

    print(f"PASS: {checked} positions compared, evalp identical.")
    sys.exit(0)


if __name__ == "__main__":
    main()
