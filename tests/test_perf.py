"""Performance benchmarks for engine-critical operations.

Run with:  pytest tests/test_perf.py -v -s
The ``-s`` flag lets print output through so you see the numbers.

Each test measures wall-clock time and reports nodes/second or ops/second.
Assertions enforce a generous floor so regressions are caught, but the
printed numbers are the real value — they show absolute throughput.
"""

import time

import pytest

from hydra.attacks import bishop_attacks, queen_attacks, rook_attacks
from hydra.board import Board
from hydra.movegen import generate_captures, generate_legal_moves, perft
from hydra.types import STARTING_FEN

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
MIDGAME = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 3 9"
POS3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"


def _fmt(value: float, unit: str) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M {unit}"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K {unit}"
    return f"{value:.0f} {unit}"


# ---------------------------------------------------------------------------
# 1. Perft throughput  (the gold-standard engine benchmark)
# ---------------------------------------------------------------------------


class TestPerftPerformance:
    """Perft exercises the full pipeline: movegen → make → unmake."""

    def test_perft_startpos_depth4(self) -> None:
        board = Board.from_fen(STARTING_FEN)
        t0 = time.perf_counter()
        nodes = perft(board, 4)
        elapsed = time.perf_counter() - t0
        nps = nodes / elapsed
        print(f"\n  startpos perft(4): {nodes:,} nodes in {elapsed:.3f}s → {_fmt(nps, 'nps')}")
        assert nodes == 197_281
        assert nps > 10_000, f"Too slow: {nps:.0f} nps"

    def test_perft_kiwipete_depth3(self) -> None:
        board = Board.from_fen(KIWIPETE)
        t0 = time.perf_counter()
        nodes = perft(board, 3)
        elapsed = time.perf_counter() - t0
        nps = nodes / elapsed
        print(f"\n  kiwipete perft(3): {nodes:,} nodes in {elapsed:.3f}s → {_fmt(nps, 'nps')}")
        assert nodes == 97_862
        assert nps > 10_000

    def test_perft_startpos_depth5(self) -> None:
        """Depth 5 is the real stress test (~4.9M nodes)."""
        board = Board.from_fen(STARTING_FEN)
        t0 = time.perf_counter()
        nodes = perft(board, 5)
        elapsed = time.perf_counter() - t0
        nps = nodes / elapsed
        print(f"\n  startpos perft(5): {nodes:,} nodes in {elapsed:.3f}s → {_fmt(nps, 'nps')}")
        assert nodes == 4_865_609
        assert nps > 10_000


# ---------------------------------------------------------------------------
# 2. Move generation speed
# ---------------------------------------------------------------------------


class TestMoveGenPerformance:
    """Measure raw move generation (no recursion, no make/unmake)."""

    @pytest.mark.parametrize(
        ("fen", "label"),
        [
            (STARTING_FEN, "startpos"),
            (KIWIPETE, "kiwipete"),
            (MIDGAME, "midgame"),
        ],
    )
    def test_legal_movegen_throughput(self, fen, label) -> None:
        board = Board.from_fen(fen)
        iterations = 5_000
        t0 = time.perf_counter()
        for _ in range(iterations):
            generate_legal_moves(board)
        elapsed = time.perf_counter() - t0
        ops = iterations / elapsed
        moves = len(generate_legal_moves(board))
        print(
            f"\n  legal_movegen [{label}]: {moves} moves, {_fmt(ops, 'gen/s')}"
            f" ({elapsed:.3f}s for {iterations} iters)"
        )
        assert ops > 500, f"Too slow: {ops:.0f} gen/s"

    def test_capture_gen_throughput(self) -> None:
        board = Board.from_fen(KIWIPETE)
        iterations = 10_000
        t0 = time.perf_counter()
        for _ in range(iterations):
            generate_captures(board)
        elapsed = time.perf_counter() - t0
        ops = iterations / elapsed
        caps = len(generate_captures(board))
        print(f"\n  capture_gen [kiwipete]: {caps} captures, {_fmt(ops, 'gen/s')} ({elapsed:.3f}s)")
        assert ops > 1_000


# ---------------------------------------------------------------------------
# 3. Make / Unmake speed
# ---------------------------------------------------------------------------


class TestMakeUnmakePerformance:
    def test_make_unmake_throughput(self) -> None:
        board = Board.from_fen(KIWIPETE)
        moves = generate_legal_moves(board)
        iterations = 50_000
        t0 = time.perf_counter()
        for i in range(iterations):
            m = moves[i % len(moves)]
            board.make_move(m)
            board.unmake_move(m)
        elapsed = time.perf_counter() - t0
        ops = iterations / elapsed
        print(
            f"\n  make+unmake [kiwipete]: {_fmt(ops, 'pairs/s')}"
            f" ({elapsed:.3f}s for {iterations} iters)"
        )
        assert ops > 50_000

    def test_hash_consistency_after_bulk_make_unmake(self) -> None:
        """Verify Zobrist stays consistent after many make/unmake cycles."""
        board = Board.from_fen(KIWIPETE)
        h0 = board.hash
        moves = generate_legal_moves(board)
        for _ in range(1_000):
            for m in moves:
                board.make_move(m)
                board.unmake_move(m)
        assert board.hash == h0, "Zobrist hash drifted after bulk make/unmake"


# ---------------------------------------------------------------------------
# 4. Attack lookup speed
# ---------------------------------------------------------------------------


class TestAttackLookupPerformance:
    def test_sliding_attack_throughput(self) -> None:
        """Measure magic-bitboard sliding attack lookups."""
        occ = Board.from_fen(STARTING_FEN).all_occ
        iterations = 200_000
        t0 = time.perf_counter()
        for i in range(iterations):
            sq = i & 63
            rook_attacks(sq, occ)
            bishop_attacks(sq, occ)
        elapsed = time.perf_counter() - t0
        ops = iterations * 2 / elapsed  # 2 lookups per iteration
        print(f"\n  sliding attack lookups: {_fmt(ops, 'lookups/s')} ({elapsed:.3f}s)")
        assert ops > 500_000

    def test_queen_attack_throughput(self) -> None:
        occ = Board.from_fen(KIWIPETE).all_occ
        iterations = 200_000
        t0 = time.perf_counter()
        for i in range(iterations):
            queen_attacks(i & 63, occ)
        elapsed = time.perf_counter() - t0
        ops = iterations / elapsed
        print(f"\n  queen attack lookups: {_fmt(ops, 'lookups/s')} ({elapsed:.3f}s)")
        assert ops > 200_000


# ---------------------------------------------------------------------------
# 5. Full game simulation
# ---------------------------------------------------------------------------


class TestGameSimulation:
    def test_play_random_game(self) -> None:
        """Play a random-ish game (always pick first legal move) and measure."""

        board = Board.from_fen(STARTING_FEN)
        max_plies = 400
        ply = 0
        t0 = time.perf_counter()
        while ply < max_plies:
            moves = generate_legal_moves(board)
            if not moves:
                break
            # Deterministic "random" pick based on hash
            idx = board.hash % len(moves)
            board.make_move(moves[idx])
            ply += 1
        elapsed = time.perf_counter() - t0
        plies_per_sec = ply / elapsed if elapsed > 0 else float("inf")
        print(f"\n  game sim: {ply} plies in {elapsed:.3f}s → {_fmt(plies_per_sec, 'plies/s')}")
        assert ply > 0
