"""Tests for board representation."""

from hydra.bitboard import popcount
from hydra.board import Board
from hydra.types import (
    BLACK,
    D2,
    D4,
    E1,
    E8,
    KING,
    NO_PIECE_TYPE,
    PAWN,
    STARTING_FEN,
    WHITE,
)


def test_starting_fen_roundtrip() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert board.to_fen() == STARTING_FEN


def test_side_to_move() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert board.side == WHITE


def test_custom_fen_roundtrip() -> None:
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    board = Board.from_fen(fen)
    assert board.to_fen() == fen


def test_from_fen_accepts_legacy_fullmove_zero() -> None:
    board = Board.from_fen("8/8/8/8/8/8/4k3/4K3 w - - 0 0")

    assert board.fullmove == 1


def test_mailbox_starting_position() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert board.mailbox[E1] == KING
    assert board.mailbox_color[E1] == WHITE
    assert board.mailbox[E8] == KING
    assert board.mailbox_color[E8] == BLACK
    assert board.mailbox[D2] == PAWN
    assert board.mailbox[D4] == NO_PIECE_TYPE


def test_occupancy() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert popcount(board.occupancy[WHITE]) == 16
    assert popcount(board.occupancy[BLACK]) == 16
    assert popcount(board.all_occ) == 32


def test_king_sq() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert board.king_sq(WHITE) == E1
    assert board.king_sq(BLACK) == E8


def test_zobrist_hash_changes_with_move() -> None:
    board = Board.from_fen(STARTING_FEN)
    h0 = board.hash
    from hydra.moves import make_move
    from hydra.types import E2, E4

    board.make_move(make_move(E2, E4))
    assert board.hash != h0


def test_zobrist_hash_restored_after_unmake() -> None:
    board = Board.from_fen(STARTING_FEN)
    h0 = board.hash
    from hydra.moves import make_move
    from hydra.types import E2, E4

    m = make_move(E2, E4)
    board.make_move(m)
    board.unmake_move(m)
    assert board.hash == h0


def test_copy_independence() -> None:
    board = Board.from_fen(STARTING_FEN)
    copy = board.copy()
    from hydra.moves import make_move
    from hydra.types import E2, E4

    copy.make_move(make_move(E2, E4))
    assert board.to_fen() == STARTING_FEN
    assert copy.to_fen() != STARTING_FEN


def test_various_fen_roundtrips() -> None:
    fens = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
    ]
    for fen in fens:
        board = Board.from_fen(fen)
        assert board.to_fen() == fen, f"Failed roundtrip for: {fen}"
