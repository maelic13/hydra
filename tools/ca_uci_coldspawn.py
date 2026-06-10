#!/usr/bin/env python3
"""Cold-spawn-per-move UCI adapter for ChessAgents engines.

Reproduces the deployment path exactly: a fresh Python process is spawned for
each move, feeding it the FEN + history line on stdin and reading back one UCI
move.  Use this for:
  - Final acceptance SPRT (realistic cold-start included)
  - Cold-start and timeout validation
  - Measuring true wall-time per move

Not suitable for high-concurrency SPSA (slow); use ca_uci_persistent.py for that.

Usage:
    python tools/ca_uci_coldspawn.py --script hydra_lite/hydra_lite.py

Note: subprocess usage here is ONLY in the local test harness; the submitted
engine script itself never spawns processes.
"""

import argparse
import subprocess
import sys

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Hard timeout per move (seconds).  Must be > platform limit so we can catch
# engines that would time out on the real platform.
_HARD_TIMEOUT_S = 6.5


def _run_engine(script: str, fen: str, history: list[str], timeout: float) -> str:
    """Spawn one engine process, return the UCI move (or '0000' on error/timeout)."""
    line = fen
    if history:
        line += " moves " + " ".join(history)
    line += "\n"
    try:
        result = subprocess.run(
            [sys.executable, script],
            input=line,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        move = result.stdout.strip()
        if move:
            return move
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return "0000"


def _out(s: str) -> None:
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def uci_loop(script: str, engine_name: str) -> None:
    fen = START_FEN
    history: list[str] = []

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]

        if cmd == "uci":
            _out(f"id name {engine_name}")
            _out("id author Hydra")
            _out("uciok")

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
            movetime_ms = None
            for i, p in enumerate(parts):
                if p == "movetime" and i + 1 < len(parts):
                    try:
                        movetime_ms = int(parts[i + 1])
                    except ValueError:
                        pass
                    break
            # Give a bit of headroom above the movetime for cold-start cost.
            timeout = (movetime_ms / 1000.0 + 2.5) if movetime_ms is not None else _HARD_TIMEOUT_S

            move = _run_engine(script, fen, history, timeout)
            _out(f"info depth 1 score cp 0 pv {move}")
            _out(f"bestmove {move}")

        elif cmd == "ucinewgame":
            fen = START_FEN
            history = []

        elif cmd == "quit":
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cold-spawn-per-move UCI adapter for ChessAgents Python engines"
    )
    parser.add_argument("--script", required=True, help="Path to the engine .py file")
    parser.add_argument(
        "--name", default="", help="Engine name for UCI header (default: script stem)"
    )
    args = parser.parse_args()

    from pathlib import Path
    name = args.name or Path(args.script).stem
    uci_loop(args.script, name)


if __name__ == "__main__":
    main()
