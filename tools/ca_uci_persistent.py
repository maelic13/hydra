#!/usr/bin/env python3
"""Persistent in-process UCI adapter for ChessAgents engines.

Loads the engine script once as a module, then serves multiple positions via
UCI without spawning a fresh process per move.  Cold-start cost is excluded,
so this adapter is valid for fast relative comparisons (eval, ordering, search
margin tuning) but NOT for tuning the time manager.

Usage:
    python tools/ca_uci_persistent.py --script hydra_lite/hydra_lite.py

UCI options:
    All module-level tunable constants defined in _SPIN_OPTIONS below are
    exposed as UCI spin options so weather-factory can setoption them.
    Option name == Python attribute name on the loaded engine module.

SPSA / fastchess setup:
    - Use this adapter in the fastchess -engine cmd= lines.
    - fastchess sends: uci -> setoption (for each param) -> isready -> position -> go -> ...
    - The adapter monkey-patches the engine module between games; it is NOT
      re-imported between setoption calls.
"""

import argparse
import importlib.util
import sys
import time

# ---------------------------------------------------------------------------
# Tunable constants exposed as UCI spin options.
# Format: name -> (default, min, max)
# Match these to the module-level constant names in the engine script.
# ---------------------------------------------------------------------------
_SPIN_OPTIONS: dict[str, tuple[int, int, int]] = {
    "TT_MAX_ENTRIES":    (300000,  1000, 1000000),
    "ASPIRATION_WINDOW": (45,      5,     300),
    "RFP_MARGIN":        (90,      20,    300),
    "FP_MARGIN":         (160,     40,    400),
    "NULL_MIN_DEPTH":    (3,       2,     6),
    "NULL_REDUCTION":    (3,       2,     5),
    "LMR_MIN_DEPTH":     (3,       2,     5),
    "LMR_DEPTH":         (2,       1,     4),
    "QDELTA_MARGIN":     (220,     50,    500),
    "BOOK_PLY":          (8,       0,     24),
}

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def load_engine(script_path: str):
    spec = importlib.util.spec_from_file_location("chessagents_engine", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # runs module-level code, NOT main()
    return module


def _out(s: str) -> None:
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def uci_loop(engine, engine_name: str) -> None:
    fen = START_FEN
    history: list[str] = []
    cached_root: str | None = None
    cached_history: list[str] = []
    cached_pos = None
    cached_rep: dict[int, int] | None = None

    def build_cached(root_fen: str, moves: list[str]):
        """Build a position for UCI search, reusing prior replay when possible."""
        nonlocal cached_root, cached_history, cached_pos, cached_rep

        can_extend = (
            cached_pos is not None
            and cached_rep is not None
            and cached_root == root_fen
            and len(moves) >= len(cached_history)
            and moves[: len(cached_history)] == cached_history
        )
        if not can_extend:
            cached_root = root_fen
            cached_history = []
            cached_pos = engine.fen(root_fen)
            cached_rep = {engine.key(cached_pos): 1}

        assert cached_pos is not None and cached_rep is not None
        for move_text in moves[len(cached_history) :]:
            move = engine.parseuci(cached_pos, move_text)
            if move is None:
                raise ValueError(f"Illegal UCI move in position history: {move_text}")
            engine.make(cached_pos, move)
            h = engine.key(cached_pos)
            cached_rep[h] = cached_rep.get(h, 0) + 1
            cached_history.append(move_text)

        return cached_pos, cached_rep, cached_history

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]

        if cmd == "uci":
            _out(f"id name {engine_name}")
            _out("id author Hydra")
            for name, (default, lo, hi) in _SPIN_OPTIONS.items():
                _out(f"option name {name} type spin default {default} min {lo} max {hi}")
            _out("uciok")

        elif cmd == "setoption":
            # setoption name X value Y  (names may be multi-word but ours are not)
            if "name" in parts and "value" in parts:
                ni = parts.index("name")
                vi = parts.index("value")
                opt_name = " ".join(parts[ni + 1 : vi])
                opt_val_str = parts[vi + 1] if vi + 1 < len(parts) else ""
                if opt_name in _SPIN_OPTIONS:
                    try:
                        setattr(engine, opt_name, int(opt_val_str))
                    except (ValueError, AttributeError):
                        pass

        elif cmd == "isready":
            _out("readyok")

        elif cmd == "position":
            if len(parts) < 2:
                continue
            if parts[1] == "startpos":
                fen = START_FEN
                mi = parts.index("moves") if "moves" in parts else -1
                history = parts[mi + 1 :] if mi >= 0 else []
            elif parts[1] == "fen" and len(parts) >= 8:
                fen = " ".join(parts[2:8])
                mi = next(
                    (i for i, p in enumerate(parts[8:], 8) if p == "moves"), -1
                )
                history = parts[mi + 1 :] if mi >= 0 else []

        elif cmd == "go":
            # Wall-clock budget starts the instant fastchess asked us to move —
            # everything we do (build/replay + search) counts against it from
            # fastchess's point of view, so our internal timer must too.
            t_start = time.perf_counter()

            # Parse time-control parameters from the go command.
            kv: dict[str, int] = {}
            i = 1
            while i < len(parts):
                key = parts[i]
                if key in ("movetime", "wtime", "btime", "winc", "binc") and i + 1 < len(parts):
                    try:
                        kv[key] = int(parts[i + 1])
                    except ValueError:
                        pass
                    i += 2
                else:
                    i += 1

            try:
                p_obj, rep, hist = build_cached(fen, history)

                # Resolve the per-move budget now that we know whose turn it is.
                # NEVER fall back to engine.SEARCH_TIME here — that is the
                # deployment budget (~4.3s) and is wildly larger than the short
                # st=X controls this adapter is meant to run under; using it
                # guarantees "loses on time" the instant movetime parsing
                # comes back empty.
                if "movetime" in kv:
                    sec = kv["movetime"] / 1000.0
                elif "wtime" in kv and "btime" in kv:
                    we_are_white = p_obj.w
                    my_time = kv["wtime"] if we_are_white else kv["btime"]
                    my_inc = kv.get("winc" if we_are_white else "binc", 0)
                    sec = max(0.05, my_time / 30000.0 + my_inc / 2000.0)
                else:
                    sec = 0.4
                sec = min(sec, 2.0)  # hard cap: never let a single move run away

                book_ply = getattr(engine, "BOOK_PLY", 8)
                m = engine.book(p_obj, hist) if len(hist) < book_ply else None
                if not m:
                    # Subtract time already spent on replay/build AND a safety
                    # margin so the TOTAL response time fastchess measures
                    # (build + search + uci-format + stdout write/flush) lands
                    # safely under the st=X deadline, not just search()'s slice
                    # of it. fastchess enforces st=X with ~zero tolerance —
                    # measured total_dt of 500-550ms (i.e. AT or barely over
                    # the 500ms budget) was enough to lose on time on move 1
                    # of nearly every game. Short fixed-time tests need a large
                    # margin because qsearch and root iteration can overshoot
                    # the internal deadline, and fastchess's st=X boundary has
                    # effectively no tolerance.
                    _SAFETY_MARGIN_S = 0.25 if sec <= 1.0 else 0.18
                    elapsed = time.perf_counter() - t_start
                    remaining = max(0.02, sec - elapsed - _SAFETY_MARGIN_S)
                    m = engine.search(p_obj, rep, remaining)
                move = engine.uci(m) if m else "0000"
            except Exception:
                move = "0000"

            _out(f"info depth 1 score cp 0 pv {move}")
            _out(f"bestmove {move}")

        elif cmd == "stop":
            pass  # search() will have already timed out; no async stop needed

        elif cmd == "quit":
            break

        elif cmd == "ucinewgame":
            fen = START_FEN
            history = []
            cached_root = None
            cached_history = []
            cached_pos = None
            cached_rep = None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persistent UCI adapter for ChessAgents Python engines"
    )
    parser.add_argument("--script", required=True, help="Path to the engine .py file")
    parser.add_argument(
        "--name", default="", help="Engine name reported in UCI header (default: script stem)"
    )
    args = parser.parse_args()

    engine = load_engine(args.script)
    from pathlib import Path
    name = args.name or Path(args.script).stem
    uci_loop(engine, name)


if __name__ == "__main__":
    main()
