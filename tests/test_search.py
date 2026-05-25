import threading

from hydra import engine as engine_module
from hydra.board import Board
from hydra.engine import INFINITY, MATE_SCORE, SearchParams
from hydra.evaluation import ClassicalEvaluator
from hydra.movegen import generate_legal_moves
from hydra.moves import (
    FLAG_EN_PASSANT,
    FLAG_PROMOTION,
    move_flag,
    move_from_sq,
    move_to_sq,
    move_to_uci,
)
from hydra.syzygy import TB_LOSS, TB_PROMOTES_NONE, TB_WIN, RootProbeResult
from hydra.transposition import TranspositionTable


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


def test_quiescence_stores_transposition_result() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1")
    params = SearchParams()
    tt = TranspositionTable(1)
    ss = engine_module._SS(
        board,
        params,
        ClassicalEvaluator(),
        tt,
        threading.Event(),
        None,
    )

    engine_module._quiescence(ss, -INFINITY, INFINITY)

    entry = tt.probe(board.hash)
    assert entry is not None
    assert entry.depth == 0


def test_quiescence_searches_initial_quiet_checks() -> None:
    board = Board.from_fen("7k/8/6K1/8/8/2Q5/8/8 w - - 0 1")
    params = SearchParams()
    tt = TranspositionTable(1)
    ss = engine_module._SS(
        board,
        params,
        ClassicalEvaluator(),
        tt,
        threading.Event(),
        None,
    )

    score = engine_module._quiescence(ss, -INFINITY, INFINITY)

    assert score >= MATE_SCORE - 1


def _brute_force_quiet_checks(board: Board) -> set[int]:
    checks: set[int] = set()
    for move in generate_legal_moves(board):
        flag = move_flag(move)
        if board.mailbox[move_to_sq(move)] != engine_module._NPT:
            continue
        if flag in {FLAG_EN_PASSANT, FLAG_PROMOTION}:
            continue
        if engine_module._gives_check(board, move):
            checks.add(move)
    return checks


def _assert_quiet_checks_match(board: Board, label: str) -> None:
    expected = _brute_force_quiet_checks(board)
    actual = set(engine_module._quiet_check_moves(board))
    assert actual == expected, (
        label,
        sorted(move_to_uci(move) for move in expected - actual),
        sorted(move_to_uci(move) for move in actual - expected),
    )


def test_targeted_quiet_checks_match_full_legal_scan() -> None:
    fens = [
        "7k/8/6K1/8/8/8/2Q5/8 w - - 0 1",
        "8/4k3/8/3P4/8/8/8/4K3 w - - 0 1",
        "8/8/8/4k3/8/8/3P4/4K3 w - - 0 1",
        "4k3/8/8/8/8/8/4N3/4R2K w - - 0 1",
        "4r2k/4n3/8/8/8/8/8/4K3 b - - 0 1",
        "3k4/8/8/8/8/8/8/R3K3 w Q - 0 1",
        "r3k2r/p1ppqpb1/bn2pnp1/2pP4/1p2P3/2N2N2/PPPBQPPP/R3K2R w KQkq - 0 1",
    ]

    for fen in fens:
        board = Board.from_fen(fen)
        _assert_quiet_checks_match(board, fen)
        for move in generate_legal_moves(board)[:8]:
            board.make_move(move)
            _assert_quiet_checks_match(board, f"{fen} after {move_to_uci(move)}")
            board.unmake_move(move)


class _FakeRootSyzygy:
    enabled = True
    largest = 7

    def __init__(self, move: int) -> None:
        self.move = move
        self.root_calls = 0

    def can_probe(self, board, limit: int) -> bool:
        return board.all_occ.bit_count() <= limit

    def probe_root(self, board) -> RootProbeResult:
        self.root_calls += 1
        return RootProbeResult(
            TB_WIN,
            move_from_sq(self.move),
            move_to_sq(self.move),
            TB_PROMOTES_NONE,
            False,
            1,
        )

    def probe_wdl(self, board) -> int | None:
        return None


def test_root_syzygy_result_short_circuits_search() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")
    expected = generate_legal_moves(board)[0]
    fake = _FakeRootSyzygy(expected)
    params = SearchParams()
    params.depth = 8

    result = engine_module.search(board, params=params, syzygy=fake, syzygy_probe_limit=7)

    assert result.bestmove == expected
    assert result.depth == 0
    assert result.nodes == 1
    assert result.score > 20_000
    assert fake.root_calls == 1


class _FakeWdlSyzygy:
    enabled = True
    largest = 7

    def __init__(self) -> None:
        self.wdl_calls = 0

    def can_probe(self, board, limit: int) -> bool:
        return board.all_occ.bit_count() <= limit

    def probe_root(self, board) -> None:
        return None

    def probe_wdl(self, board) -> int:
        self.wdl_calls += 1
        return TB_LOSS


def test_search_uses_syzygy_wdl_after_irreversible_move() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/6rR w - - 0 1")
    fake = _FakeWdlSyzygy()
    params = SearchParams()
    params.depth = 1

    result = engine_module.search(
        board,
        params=params,
        syzygy=fake,
        syzygy_probe_depth=0,
        syzygy_probe_limit=7,
    )

    assert fake.wdl_calls > 0
    assert result.score > 20_000
