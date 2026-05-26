import io
import threading
import time

from hydra import uci as uci_module
from hydra.board import Board
from hydra.engine import MAX_DEPTH, SearchParams, SearchResult
from hydra.movegen import generate_legal_moves
from hydra.moves import MOVE_NONE, make_move, move_to_uci
from hydra.uci import UCIProtocol

_ILLEGAL_MOVE_GAME_FEN = "8/6K1/8/8/8/p7/P7/1k6 b - - 4 71"


def _wait_for_output(out: io.StringIO, text: str, timeout: float = 1.0) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if text in out.getvalue():
            return True
        time.sleep(0.01)
    return False


def test_ponder_search_does_not_emit_bestmove_before_stop() -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    params = SearchParams()
    params.depth = 1
    params.ponder = True

    worker = threading.Thread(
        target=protocol._search_worker,
        args=(Board.from_fen(_ILLEGAL_MOVE_GAME_FEN), params),
        daemon=True,
    )
    worker.start()

    assert _wait_for_output(out, "info depth 1")
    assert "bestmove" not in out.getvalue()
    assert worker.is_alive()

    protocol._cmd_stop()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert "bestmove" in out.getvalue()


def test_infinite_search_does_not_emit_bestmove_before_stop() -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    params = SearchParams()
    params.depth = 1
    params.infinite = True

    worker = threading.Thread(
        target=protocol._search_worker,
        args=(Board.from_fen(_ILLEGAL_MOVE_GAME_FEN), params),
        daemon=True,
    )
    worker.start()

    assert _wait_for_output(out, "info depth 1")
    assert "bestmove" not in out.getvalue()
    assert worker.is_alive()

    protocol._cmd_stop()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert "bestmove" in out.getvalue()


def test_uci_advertises_stockfish_style_syzygy_options() -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)

    protocol._cmd_uci()

    text = out.getvalue()
    assert "option name Move Overhead type spin default 20 min 0 max 5000" in text
    assert "option name SyzygyPath type string default <empty>" in text
    assert "option name SyzygyProbeDepth type spin default 1 min 1 max 100" in text
    assert "option name Syzygy50MoveRule type check default true" in text
    assert "option name SyzygyProbeLimit type spin default 7 min 0 max 7" in text


def test_go_without_limits_defaults_to_depth_7() -> None:
    protocol = UCIProtocol(inp=io.StringIO(), out=io.StringIO())

    params = protocol._parse_go(["go"])

    assert params.depth == 7


def test_go_movetime_keeps_full_depth_budget() -> None:
    protocol = UCIProtocol(inp=io.StringIO(), out=io.StringIO())

    params = protocol._parse_go(["go", "movetime", "500"])

    assert params.movetime == 500
    assert params.depth == MAX_DEPTH


def test_go_uses_configured_move_overhead() -> None:
    protocol = UCIProtocol(inp=io.StringIO(), out=io.StringIO())
    protocol._cmd_setoption(["setoption", "name", "Move", "Overhead", "value", "75"])

    params = protocol._parse_go(["go", "movetime", "500"])

    assert params.move_overhead == 75


def test_uci_worker_passes_syzygy_options_to_search(monkeypatch) -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    protocol._options["SyzygyProbeDepth"] = 4
    protocol._options["SyzygyProbeLimit"] = 5
    protocol._options["Syzygy50MoveRule"] = False
    protocol._syzygy._enabled = True
    protocol._syzygy.largest = 5
    captured: dict[str, object] = {}

    def fake_search(board, **kwargs):
        captured["syzygy"] = kwargs["syzygy"]
        captured["syzygy_probe_depth"] = kwargs["syzygy_probe_depth"]
        captured["syzygy_probe_limit"] = kwargs["syzygy_probe_limit"]
        captured["syzygy_50_move_rule"] = kwargs["syzygy_50_move_rule"]
        return SearchResult(bestmove=MOVE_NONE)

    monkeypatch.setattr(uci_module, "search", fake_search)

    protocol._search_worker(Board.from_fen(_ILLEGAL_MOVE_GAME_FEN), SearchParams())

    assert captured["syzygy"] is protocol._syzygy
    assert captured["syzygy_probe_depth"] == 4
    assert captured["syzygy_probe_limit"] == 5
    assert captured["syzygy_50_move_rule"] is False


def test_uci_worker_omits_disabled_syzygy_from_search(monkeypatch) -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    captured: dict[str, object] = {}

    def fake_search(board, **kwargs):
        captured["syzygy"] = kwargs["syzygy"]
        return SearchResult(bestmove=MOVE_NONE)

    monkeypatch.setattr(uci_module, "search", fake_search)

    protocol._search_worker(Board.from_fen(_ILLEGAL_MOVE_GAME_FEN), SearchParams())

    assert captured["syzygy"] is None


def test_uci_worker_replaces_illegal_bestmove(monkeypatch) -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)

    def fake_search(board, **kwargs):
        return SearchResult(bestmove=make_move(0, 1))

    monkeypatch.setattr(uci_module, "search", fake_search)

    protocol._search_worker(Board.from_fen(_ILLEGAL_MOVE_GAME_FEN), SearchParams())

    assert "bestmove 0000" not in out.getvalue()


def test_uci_worker_omits_illegal_ponder_move(monkeypatch) -> None:
    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    protocol._options["Ponder"] = True
    board = Board.from_fen(_ILLEGAL_MOVE_GAME_FEN)
    legal = generate_legal_moves(board)
    bestmove = legal[0]

    def fake_search(board, **kwargs):
        return SearchResult(bestmove=bestmove, pv=[bestmove, make_move(0, 1)])

    monkeypatch.setattr(uci_module, "search", fake_search)

    protocol._search_worker(board, SearchParams())

    assert out.getvalue().strip() == f"bestmove {move_to_uci(bestmove)}"


def test_setoption_syzygy_path_initializes_tablebases_with_debug_output() -> None:
    class FakeSyzygy:
        enabled = False
        largest = 0

        def __init__(self) -> None:
            self.paths: list[str] = []

        def set_path(self, path: str) -> int:
            self.paths.append(path)
            return 5

    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    fake = FakeSyzygy()
    protocol._syzygy = fake
    protocol._cmd_debug(["debug", "on"])

    protocol._cmd_setoption(["setoption", "name", "SyzygyPath", "value", "D:/tb"])

    assert fake.paths == ["D:/tb"]
    assert "info string Set SyzygyPath = D:/tb" in out.getvalue()
    assert "info string Syzygy initialized with 5-piece tables" in out.getvalue()


def test_setoption_syzygy_path_reports_native_extension_error() -> None:
    class FailingSyzygy:
        enabled = False
        largest = 0

        def set_path(self, path: str) -> int:
            msg = "Syzygy support is unavailable"
            raise RuntimeError(msg)

    out = io.StringIO()
    protocol = UCIProtocol(inp=io.StringIO(), out=out)
    protocol._syzygy = FailingSyzygy()

    protocol._cmd_setoption(["setoption", "name", "SyzygyPath", "value", "D:/tb"])

    assert "info string Syzygy support is unavailable" in out.getvalue()
