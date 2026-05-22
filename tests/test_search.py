from hydra import engine as engine_module
from hydra.board import Board
from hydra.engine import INFINITY, MATE_SCORE, SearchParams
from hydra.movegen import generate_legal_moves


def test_iterative_deepening_continues_after_forced_mate(monkeypatch) -> None:
    board = Board.from_fen("4K3/2Q5/6k1/8/8/8/8/8 w - - 0 1")
    root_move = generate_legal_moves(board)[0]
    calls: list[tuple[int, int, int]] = []

    def fake_negamax(ss, depth: int, alpha: int, beta: int, *, do_null: bool = True) -> int:
        calls.append((depth, alpha, beta))
        return MATE_SCORE - 9

    monkeypatch.setattr(engine_module, "_negamax", fake_negamax)
    monkeypatch.setattr(engine_module, "_extract_pv", lambda board, tt, depth: [root_move])

    params = SearchParams()
    params.depth = 6

    result = engine_module.search(board, params=params)

    assert result.depth == 6
    assert [depth for depth, _alpha, _beta in calls] == [1, 2, 3, 4, 5, 6]
    assert calls[3][1:] == (-INFINITY, INFINITY)
