import threading
from math import isclose

from hydra import engine as engine_module
from hydra.board import Board
from hydra.engine import INFINITY, MATE_SCORE, SearchParams
from hydra.movegen import generate_legal_moves
from hydra.moves import MOVE_NONE, move_from_sq, move_to_sq, move_to_uci
from hydra.syzygy import TB_LOSS, TB_PROMOTES_NONE, TB_PROMOTES_QUEEN, TB_WIN, RootProbeResult


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


def test_search_without_params_keeps_depth_6_baseline(monkeypatch) -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")
    root_move = generate_legal_moves(board)[0]
    calls: list[int] = []

    def fake_negamax(ss, depth: int, alpha: int, beta: int, *, do_null: bool = True) -> int:
        calls.append(depth)
        return 0

    monkeypatch.setattr(engine_module, "_negamax", fake_negamax)
    monkeypatch.setattr(engine_module, "_extract_pv", lambda board, tt, depth: [root_move])

    result = engine_module.search(board)

    assert result.depth == 6
    assert calls == [1, 2, 3, 4, 5, 6]


def test_info_with_pv_never_truncates_a_move_token() -> None:
    board = Board.from_fen("8/6R1/3k4/5K2/5P2/8/4r3/8 w - - 7 1")
    pv = generate_legal_moves(board)[:8]
    info = "info depth 9 seldepth 11 score cp 166 nodes 4148 nps 20135 hashfull 36 time 206"

    line = engine_module._info_with_pv(info, pv)

    assert len(line) <= 96
    tokens = line.split()
    if "pv" in tokens:
        for token in tokens[tokens.index("pv") + 1 :]:
            assert len(token) in {4, 5}


class _FakeRootSyzygy:
    enabled = True
    largest = 7

    def __init__(self, move: int) -> None:
        self.move = move
        self.root_calls = 0

    def can_probe(self, board, limit: int) -> bool:
        return board.all_occ.bit_count() <= limit

    def probe_root(self, board, *, use_50_move_rule: bool = True) -> RootProbeResult:
        self.root_calls += 1
        return RootProbeResult(
            TB_WIN,
            move_from_sq(self.move),
            move_to_sq(self.move),
            TB_PROMOTES_NONE,
            False,
            1,
        )

    def probe_wdl(self, board, *, use_50_move_rule: bool = True) -> int | None:
        return None


def test_root_syzygy_uses_fathom_move_without_searching() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")
    expected = generate_legal_moves(board)[0]
    fake = _FakeRootSyzygy(expected)
    params = SearchParams()
    params.depth = 8
    infos: list[str] = []

    result = engine_module.search(
        board,
        params=params,
        syzygy=fake,
        syzygy_probe_limit=7,
        info_cb=infos.append,
    )

    assert result.bestmove == expected
    assert result.depth == 0
    assert result.nodes == 1
    assert result.score == 20_000
    assert fake.root_calls == 1
    assert "tbhits 1" in infos[-1]
    assert move_to_uci(expected) in infos[-1]


def test_root_syzygy_skips_positions_with_castling_rights() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    expected = generate_legal_moves(board)[0]
    fake = _FakeRootSyzygy(expected)

    result = engine_module._root_syzygy_result(
        board,
        generate_legal_moves(board),
        fake,
        probe_limit=7,
        use_50_move_rule=True,
    )

    assert result is None
    assert fake.root_calls == 0


def test_root_syzygy_maps_promotion_result_to_legal_move() -> None:
    board = Board.from_fen("4k3/P7/8/8/8/8/4K3/8 w - - 0 1")
    legal_moves = generate_legal_moves(board)
    expected = next(move for move in legal_moves if move_to_uci(move) == "a7a8q")

    class PromotionSyzygy:
        def can_probe(self, board, limit: int) -> bool:
            return True

        def probe_root(self, board, *, use_50_move_rule: bool = True) -> RootProbeResult:
            return RootProbeResult(
                TB_WIN,
                move_from_sq(expected),
                move_to_sq(expected),
                TB_PROMOTES_QUEEN,
                False,
                1,
            )

    result = engine_module._root_syzygy_result(
        board,
        legal_moves,
        PromotionSyzygy(),
        probe_limit=7,
        use_50_move_rule=True,
    )

    assert result is not None
    assert result.bestmove == expected
    assert result.pv == [expected]


def test_root_syzygy_ignores_native_move_that_is_not_legal() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")

    class InvalidMoveSyzygy:
        def can_probe(self, board, limit: int) -> bool:
            return True

        def probe_root(self, board, *, use_50_move_rule: bool = True) -> RootProbeResult:
            return RootProbeResult(TB_WIN, 0, 1, TB_PROMOTES_NONE, False, 1)

    assert (
        engine_module._root_syzygy_result(
            board,
            generate_legal_moves(board),
            InvalidMoveSyzygy(),
            probe_limit=7,
            use_50_move_rule=True,
        )
        is None
    )


def test_search_without_syzygy_does_not_call_probe_helper(monkeypatch) -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")
    params = SearchParams()
    params.depth = 2

    def fail_if_called(ss, depth: int) -> int | None:
        raise AssertionError

    monkeypatch.setattr(engine_module, "_probe_syzygy_wdl", fail_if_called)

    result = engine_module.search(board, params=params, syzygy=None)

    assert result.bestmove != MOVE_NONE


def test_movetime_reserves_configured_move_overhead() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")
    params = SearchParams()
    params.movetime = 500
    params.move_overhead = 75

    soft, hard = engine_module._compute_time_limits(params, board.side)

    assert soft == hard
    assert isclose(hard, 0.425)


def test_movetime_keeps_one_millisecond_when_overhead_exceeds_budget() -> None:
    params = SearchParams()
    params.movetime = 5
    params.move_overhead = 10

    soft, hard = engine_module._compute_time_limits(params, 0)

    assert soft == hard
    assert isclose(hard, 0.001)


def test_clock_time_reserves_configured_move_overhead() -> None:
    params = SearchParams()
    params.wtime = 2520
    params.winc = 200
    params.move_overhead = 20

    soft, hard = engine_module._compute_time_limits(params, 0)

    assert isclose(soft, 0.25)
    assert isclose(hard, 0.75)


def test_clock_time_never_goes_negative_when_overhead_exceeds_remaining_time() -> None:
    params = SearchParams()
    params.wtime = 5
    params.move_overhead = 10

    soft, hard = engine_module._compute_time_limits(params, 0)

    assert soft > 0
    assert hard >= soft
    assert isclose(soft, 0.0001)
    assert isclose(hard, 0.0002)


def test_negative_move_overhead_is_treated_as_zero() -> None:
    params = SearchParams()
    params.movetime = 500
    params.move_overhead = -25

    soft, hard = engine_module._compute_time_limits(params, 0)

    assert soft == hard
    assert isclose(hard, 0.5)


class _FakeWdlSyzygy:
    enabled = True
    largest = 7

    def __init__(self) -> None:
        self.wdl_calls = 0
        self.use_50_flags: list[bool] = []

    def can_probe(self, board, limit: int) -> bool:
        return board.all_occ.bit_count() <= limit

    def probe_root(self, board, *, use_50_move_rule: bool = True) -> None:
        return None

    def probe_wdl(self, board, *, use_50_move_rule: bool = True) -> int:
        self.wdl_calls += 1
        self.use_50_flags.append(use_50_move_rule)
        return TB_LOSS


def test_syzygy_50_move_rule_false_allows_nonzero_halfmove_wdl_probe() -> None:
    board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 37 1")
    params = SearchParams()

    respecting_50 = _FakeWdlSyzygy()
    ss_respecting = engine_module._SS(
        board,
        params,
        engine_module.create_evaluator(),
        engine_module.TranspositionTable(1),
        threading.Event(),
        None,
        syzygy=respecting_50,
        syzygy_probe_depth=1,
        syzygy_probe_limit=7,
        syzygy_50_move_rule=True,
    )

    assert engine_module._probe_syzygy_wdl(ss_respecting, 1) is None
    assert respecting_50.wdl_calls == 0

    ignoring_50 = _FakeWdlSyzygy()
    ss_ignoring = engine_module._SS(
        board,
        params,
        engine_module.create_evaluator(),
        engine_module.TranspositionTable(1),
        threading.Event(),
        None,
        syzygy=ignoring_50,
        syzygy_probe_depth=1,
        syzygy_probe_limit=7,
        syzygy_50_move_rule=False,
    )

    assert engine_module._probe_syzygy_wdl(ss_ignoring, 1) < -19_000
    assert ignoring_50.use_50_flags == [False]
    assert ss_ignoring.tb_hits == 1


def test_syzygy_wdl_probe_respects_depth_and_castling_guards() -> None:
    params = SearchParams()
    fake = _FakeWdlSyzygy()
    shallow_board = Board.from_fen("4k3/8/8/8/8/8/4K3/7R w - - 0 1")
    shallow_ss = engine_module._SS(
        shallow_board,
        params,
        engine_module.create_evaluator(),
        engine_module.TranspositionTable(1),
        threading.Event(),
        None,
        syzygy=fake,
        syzygy_probe_depth=4,
        syzygy_probe_limit=7,
        syzygy_50_move_rule=True,
    )

    assert engine_module._probe_syzygy_wdl(shallow_ss, 3) is None
    assert fake.wdl_calls == 0

    castling_board = Board.from_fen("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    castling_ss = engine_module._SS(
        castling_board,
        params,
        engine_module.create_evaluator(),
        engine_module.TranspositionTable(1),
        threading.Event(),
        None,
        syzygy=fake,
        syzygy_probe_depth=1,
        syzygy_probe_limit=7,
        syzygy_50_move_rule=True,
    )

    assert engine_module._probe_syzygy_wdl(castling_ss, 1) is None
    assert fake.wdl_calls == 0
