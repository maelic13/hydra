"""Phase 2.1 gate: incremental material+PST+phase accumulators stay consistent.

make_move/unmake_move maintain board.mg_acc/eg_acc/phase_acc incrementally; this
verifies they always equal a from-scratch recompute (the oracle is a fresh
Board.from_fen(board.to_fen()), which rebuilds the accumulators via _init_psqt),
and that unmake restores them exactly — across captures, en passant, castling,
and promotions.
"""

from __future__ import annotations

from hydra.board import Board
from hydra.movegen import generate_legal_moves

# Positions exercising castling, en-passant, and promotions.
_FENS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",  # Kiwipete
    "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3",  # en-passant
    "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1",  # promotions both sides
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
]


def _oracle(board: Board) -> tuple[int, int, int]:
    fresh = Board.from_fen(board.to_fen())
    return fresh.mg_acc, fresh.eg_acc, fresh.phase_acc


def _check(board: Board, depth: int) -> None:
    assert (board.mg_acc, board.eg_acc, board.phase_acc) == _oracle(board), board.to_fen()
    if depth == 0:
        return
    for move in generate_legal_moves(board):
        before = (board.mg_acc, board.eg_acc, board.phase_acc)
        board.make_move(move)
        _check(board, depth - 1)
        board.unmake_move(move)
        assert (board.mg_acc, board.eg_acc, board.phase_acc) == before, board.to_fen()


def test_accumulators_match_scratch_to_depth_3() -> None:
    for fen in _FENS:
        _check(Board.from_fen(fen), 3)


def test_null_move_preserves_accumulators() -> None:
    board = Board.from_fen(_FENS[1])
    before = (board.mg_acc, board.eg_acc, board.phase_acc)
    board.make_null_move()
    assert (board.mg_acc, board.eg_acc, board.phase_acc) == before
    board.unmake_null_move()
    assert (board.mg_acc, board.eg_acc, board.phase_acc) == before
