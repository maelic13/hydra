"""UCI (Universal Chess Interface) protocol implementation.

Implements the full UCI protocol as specified at:
https://backscattering.de/chess/uci/

Commands: uci, debug, isready, setoption, register, ucinewgame,
position, go, stop, ponderhit, quit.

Search runs on a background thread so the UCI input loop is always
responsive — ``stop`` and ``quit`` take effect immediately.
"""

from __future__ import annotations

import sys
import threading
from typing import TextIO

from hydra import __version__
from hydra.bench import run_bench
from hydra.board import Board
from hydra.engine import HistoryTables, SearchParams, SearchResult, search
from hydra.evaluation import available_evaluators, create_evaluator
from hydra.movegen import generate_legal_moves
from hydra.moves import MOVE_NONE, move_to_uci, uci_to_move
from hydra.transposition import TranspositionTable
from hydra.types import STARTING_FEN

ENGINE_NAME = "Hydra"
ENGINE_AUTHOR = "Miloslav Macurek"

# UCI options with (default, min, max) or string default
OPTIONS: dict[str, dict] = {
    "Hash": {"type": "spin", "default": 64, "min": 1, "max": 33554432},
    "Threads": {"type": "spin", "default": 1, "min": 1, "max": 1},
    "Ponder": {"type": "check", "default": False},
    "EvalType": {
        "type": "combo",
        "default": "classical",
        "vars": available_evaluators(),
    },
}


class UCIProtocol:
    """Manages UCI state and dispatches commands."""

    def __init__(
        self,
        inp: TextIO = sys.stdin,
        out: TextIO = sys.stdout,
    ) -> None:
        self._inp = inp
        self._out = out
        self._board = Board.from_fen(STARTING_FEN)
        self._debug = False
        self._options: dict[str, int | str] = {
            name: opt["default"] for name, opt in OPTIONS.items()
        }
        # Search infrastructure
        self._tt = TranspositionTable(self._options["Hash"])
        self._evaluator = create_evaluator(self._options["EvalType"])
        # Threading for non-blocking search
        self._stop_event = threading.Event()
        self._search_thread: threading.Thread | None = None
        self._out_lock = threading.Lock()
        # Ponder support: holds the _SS object so ponderhit can flip the flag
        self._ponder_ss: list = []
        # Persistent history tables — aged each search, reset on ucinewgame
        self._history_tables: HistoryTables = HistoryTables()

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _send(self, msg: str) -> None:
        with self._out_lock:
            self._out.write(msg + "\n")
            self._out.flush()

    def _debug_msg(self, msg: str) -> None:
        if self._debug:
            self._send(f"info string {msg}")

    # ------------------------------------------------------------------
    # Search thread
    # ------------------------------------------------------------------

    def _wait_for_search(self) -> None:
        """Block until any running search finishes."""
        if self._search_thread is not None and self._search_thread.is_alive():
            self._search_thread.join()
        self._search_thread = None

    def _search_worker(self, board: Board, params: SearchParams) -> None:
        """Run search on a background thread and send bestmove when done."""
        try:
            self._ponder_ss.clear()
            result: SearchResult = search(
                board,
                params=params,
                evaluator=self._evaluator,
                tt=self._tt,
                stop_event=self._stop_event,
                info_cb=self._send,
                ponder_switch=self._ponder_ss,
                history_tables=self._history_tables,
            )

            if result.bestmove != MOVE_NONE:
                bm = move_to_uci(result.bestmove)
                # Suggest ponder move if Ponder is enabled and PV has ≥ 2 moves
                if self._options.get("Ponder") and len(result.pv) >= 2:
                    pm = move_to_uci(result.pv[1])
                    self._send(f"bestmove {bm} ponder {pm}")
                else:
                    self._send(f"bestmove {bm}")
            else:
                self._send("bestmove 0000")
        except Exception as exc:
            self._debug_msg(f"Search error: {exc}")
            self._send("bestmove 0000")

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_uci(self) -> None:
        self._send(f"id name {ENGINE_NAME} {__version__}")
        self._send(f"id author {ENGINE_AUTHOR}")
        for name, opt in OPTIONS.items():
            if opt["type"] == "spin":
                self._send(
                    f"option name {name} type spin "
                    f"default {opt['default']} min {opt['min']} max {opt['max']}"
                )
            elif opt["type"] == "string":
                self._send(f"option name {name} type string default {opt['default']}")
            elif opt["type"] == "check":
                self._send(
                    f"option name {name} type check default {'true' if opt['default'] else 'false'}"
                )
            elif opt["type"] == "button":
                self._send(f"option name {name} type button")
            elif opt["type"] == "combo":
                vars_str = " ".join(f"var {v}" for v in opt["vars"])
                self._send(f"option name {name} type combo default {opt['default']} {vars_str}")
        self._send("uciok")

    def _cmd_debug(self, tokens: list[str]) -> None:
        if len(tokens) < 2:
            self._send("info string Invalid UCI command")
            return
        if tokens[1] == "on":
            self._debug = True
        elif tokens[1] == "off":
            self._debug = False
        else:
            self._send("info string Invalid UCI command")

    def _cmd_isready(self) -> None:
        self._wait_for_search()
        self._send("readyok")

    def _cmd_setoption(self, tokens: list[str]) -> None:
        # Format: setoption name <name> [value <value>]
        try:
            name_idx = tokens.index("name") + 1
        except ValueError:
            self._send("info string Invalid UCI command")
            return

        try:
            value_idx = tokens.index("value")
            name_str = " ".join(tokens[name_idx:value_idx])
            value_str = " ".join(tokens[value_idx + 1 :])
        except ValueError:
            name_str = " ".join(tokens[name_idx:])
            value_str = None

        # Case-insensitive option lookup
        matched_name = None
        for opt_name in OPTIONS:
            if opt_name.lower() == name_str.lower():
                matched_name = opt_name
                break

        if matched_name is None:
            self._debug_msg(f"Unknown option: {name_str}")
            return

        opt = OPTIONS[matched_name]
        if opt["type"] == "button":
            return

        if value_str is None:
            self._send("info string Invalid UCI command")
            return

        if opt["type"] == "spin":
            try:
                val = int(value_str)
            except ValueError:
                self._send("info string Invalid UCI command")
                return
            val = max(opt["min"], min(opt["max"], val))
            self._options[matched_name] = val
        elif opt["type"] == "check":
            self._options[matched_name] = value_str.lower() == "true"
        elif opt["type"] == "string":
            self._options[matched_name] = value_str
        elif opt["type"] == "combo":
            if value_str.lower() in (v.lower() for v in opt["vars"]):
                self._options[matched_name] = value_str
            else:
                self._debug_msg(f"Invalid value for {matched_name}: {value_str}")
                return

        self._debug_msg(f"Set {matched_name} = {self._options[matched_name]}")

        # Apply side-effects for specific options
        if matched_name == "Hash":
            self._tt.resize(self._options["Hash"])
        elif matched_name == "EvalType":
            self._evaluator = create_evaluator(self._options["EvalType"])

    def _cmd_register(self, tokens: list[str]) -> None:
        # Registration not required
        self._send("registration ok")

    def _cmd_ucinewgame(self) -> None:
        self._wait_for_search()
        self._board = Board.from_fen(STARTING_FEN)
        self._tt.clear()
        self._history_tables = HistoryTables()

    def _cmd_position(self, tokens: list[str]) -> None:
        if len(tokens) < 2:
            self._send("info string Invalid UCI command")
            return

        idx = 1
        if tokens[idx] == "startpos":
            self._board = Board.from_fen(STARTING_FEN)
            idx = 2
        elif tokens[idx] == "fen":
            # FEN has 6 fields
            if len(tokens) < 8:
                self._send("info string Invalid UCI command")
                return
            fen_str = " ".join(tokens[2:8])
            try:
                self._board = Board.from_fen(fen_str)
            except Exception:
                self._send("info string Invalid UCI command")
                return
            idx = 8
        else:
            self._send("info string Invalid UCI command")
            return

        # Apply moves if present
        if idx < len(tokens) and tokens[idx] == "moves":
            for uci_str in tokens[idx + 1 :]:
                legal = generate_legal_moves(self._board)
                move = uci_to_move(uci_str, legal)
                if move == MOVE_NONE:
                    self._send(f"info string Illegal move: {uci_str}")
                    return
                self._board.make_move(move)

    def _parse_go(self, tokens: list[str]) -> SearchParams:
        """Parse ``go`` sub-commands into :class:`SearchParams`."""
        params = SearchParams()
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok == "infinite":
                params.infinite = True
                i += 1
            elif tok == "ponder":
                params.ponder = True
                i += 1
            elif tok == "depth" and i + 1 < len(tokens):
                params.depth = int(tokens[i + 1])
                i += 2
            elif tok == "movetime" and i + 1 < len(tokens):
                params.movetime = int(tokens[i + 1])
                i += 2
            elif tok == "wtime" and i + 1 < len(tokens):
                params.wtime = int(tokens[i + 1])
                i += 2
            elif tok == "btime" and i + 1 < len(tokens):
                params.btime = int(tokens[i + 1])
                i += 2
            elif tok == "winc" and i + 1 < len(tokens):
                params.winc = int(tokens[i + 1])
                i += 2
            elif tok == "binc" and i + 1 < len(tokens):
                params.binc = int(tokens[i + 1])
                i += 2
            elif tok == "movestogo" and i + 1 < len(tokens):
                params.movestogo = int(tokens[i + 1])
                i += 2
            elif tok == "nodes" and i + 1 < len(tokens):
                params.nodes = int(tokens[i + 1])
                i += 2
            else:
                i += 1
        return params

    def _cmd_go(self, tokens: list[str]) -> None:
        # Stop any ongoing search before starting a new one
        self._cmd_stop()

        self._stop_event.clear()

        # Copy the board so the search thread has its own state
        board_copy = self._board.copy()
        params = self._parse_go(tokens)

        self._search_thread = threading.Thread(
            target=self._search_worker,
            args=(board_copy, params),
            daemon=True,
        )
        self._search_thread.start()

    def _cmd_stop(self) -> None:
        self._stop_event.set()
        self._wait_for_search()

    def _cmd_bench(self, tokens: list[str]) -> None:
        import contextlib

        depth = 9
        if len(tokens) >= 2:
            with contextlib.suppress(ValueError):
                depth = int(tokens[1])
        self._cmd_stop()
        run_bench(depth, out=self._out)

    def _cmd_ponderhit(self) -> None:
        # Switch the running search from ponder mode to normal time-managed mode
        if self._ponder_ss:
            self._ponder_ss[0].switch_from_ponder()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the UCI main loop.

        The input loop runs on the main thread and is always responsive.
        Search runs on a background daemon thread.
        """
        self._send(f"{ENGINE_NAME} {__version__} by {ENGINE_AUTHOR}")

        for raw_line in self._inp:
            line = raw_line.strip()
            if not line:
                continue

            tokens = line.split()
            cmd = tokens[0]

            try:
                if cmd == "uci":
                    self._cmd_uci()
                elif cmd == "debug":
                    self._cmd_debug(tokens)
                elif cmd == "isready":
                    self._cmd_isready()
                elif cmd == "setoption":
                    self._cmd_setoption(tokens)
                elif cmd == "register":
                    self._cmd_register(tokens)
                elif cmd == "ucinewgame":
                    self._cmd_ucinewgame()
                elif cmd == "position":
                    self._cmd_position(tokens)
                elif cmd == "go":
                    self._cmd_go(tokens)
                elif cmd == "stop":
                    self._cmd_stop()
                elif cmd == "ponderhit":
                    self._cmd_ponderhit()
                elif cmd == "bench":
                    self._cmd_bench(tokens)
                elif cmd == "quit":
                    self._cmd_stop()
                    break
                else:
                    self._send("info string Invalid UCI command")
            except Exception:
                self._send("info string Invalid UCI command")


def main() -> None:
    protocol = UCIProtocol()
    protocol.run()


if __name__ == "__main__":
    main()
