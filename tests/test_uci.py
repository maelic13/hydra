import io
import threading
import time

from hydra.board import Board
from hydra.engine import SearchParams
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
