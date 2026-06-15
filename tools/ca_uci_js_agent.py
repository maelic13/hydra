#!/usr/bin/env python3
"""Persistent UCI adapter for ChessAgents JS engines (FEN-line / agent-mode protocol).

The JS engine reads one line per move from stdin in ChessAgents format:
  <fen> [moves <uci1> <uci2> ...]
and writes one UCI move per line to stdout.

This wrapper bridges UCI (fastchess) <-> FEN-line (JS engine) so fastchess
can use any ChessAgents JS engine as a UCI opponent.

Usage:
    python tools/ca_uci_js_agent.py --script D:/chess/engines/lozza11.js --name lozza11
"""

import argparse
import subprocess
import sys

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _out(s: str) -> None:
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def uci_loop(node_proc: subprocess.Popen, engine_name: str) -> None:
    root_fen = START_FEN
    moves: list[str] = []

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]

        if cmd == "uci":
            _out(f"id name {engine_name}")
            _out("id author JS agent")
            _out("uciok")

        elif cmd == "isready":
            _out("readyok")

        elif cmd == "ucinewgame":
            root_fen = START_FEN
            moves = []

        elif cmd == "position":
            if len(parts) < 2:
                continue
            if parts[1] == "startpos":
                root_fen = START_FEN
                mi = line.find(" moves ")
                moves = line[mi + 7:].split() if mi >= 0 else []
            elif parts[1] == "fen" and len(parts) >= 8:
                root_fen = " ".join(parts[2:8])
                mi = line.find(" moves ")
                moves = line[mi + 7:].split() if mi >= 0 else []

        elif cmd == "go":
            # Build the ChessAgents input line: current FEN + full move history.
            # lozza11 internally calls `position fen <fen> moves <moves>` so
            # it handles repetition and correct position from this single line.
            agent_line = root_fen
            if moves:
                agent_line += " moves " + " ".join(moves)

            try:
                node_proc.stdin.write(agent_line + "\n")
                node_proc.stdin.flush()
                move = (node_proc.stdout.readline() or "0000\n").strip()
                if not move:
                    move = "0000"
            except Exception:
                move = "0000"

            _out(f"info depth 1 score cp 0 pv {move}")
            _out(f"bestmove {move}")

        elif cmd == "quit":
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="UCI adapter for ChessAgents JS engines (agent/FEN-line mode)"
    )
    parser.add_argument("--script", required=True, help="Path to the JS engine file")
    parser.add_argument("--name", default="", help="Engine name for UCI header")
    args = parser.parse_args()

    from pathlib import Path
    name = args.name or Path(args.script).stem

    proc = subprocess.Popen(
        ["node", args.script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        uci_loop(proc, name)
    finally:
        try:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    main()
