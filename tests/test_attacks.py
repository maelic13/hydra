"""Attack table tests."""

from hydra.attacks import (
    KING_ATTACKS,
    KNIGHT_ATTACKS,
    PAWN_ATTACKS,
    bishop_attacks,
    queen_attacks,
    rook_attacks,
)
from hydra.bitboard import BB_SQUARES, popcount
from hydra.types import A1, BLACK, D4, E4, WHITE


def test_knight_center() -> None:
    # Knight on e4 should attack 8 squares
    assert popcount(KNIGHT_ATTACKS[E4]) == 8


def test_knight_corner() -> None:
    # Knight on a1 should attack 2 squares
    assert popcount(KNIGHT_ATTACKS[A1]) == 2


def test_king_center() -> None:
    assert popcount(KING_ATTACKS[E4]) == 8


def test_king_corner() -> None:
    assert popcount(KING_ATTACKS[A1]) == 3


def test_pawn_attacks_white() -> None:
    # White pawn on e4 attacks d5 and f5
    atk = PAWN_ATTACKS[WHITE][E4]
    assert atk & BB_SQUARES[E4 + 7]  # d5
    assert atk & BB_SQUARES[E4 + 9]  # f5
    assert popcount(atk) == 2


def test_pawn_attacks_black() -> None:
    atk = PAWN_ATTACKS[BLACK][E4]
    assert popcount(atk) == 2


def test_rook_empty_board() -> None:
    # Rook on a1, empty board
    atk = rook_attacks(A1, 0)
    assert popcount(atk) == 14  # 7 on file + 7 on rank


def test_bishop_empty_board() -> None:
    # Bishop on d4, empty board
    atk = bishop_attacks(D4, 0)
    assert popcount(atk) == 13


def test_queen_empty_board() -> None:
    atk = queen_attacks(D4, 0)
    assert popcount(atk) == 27  # 14 rook + 13 bishop


def test_rook_with_blockers() -> None:
    # Rook on a1, piece on a4 — should see a2, a3, a4 (stopped) + b1..h1
    occ = BB_SQUARES[A1] | BB_SQUARES[24]  # a4 = 24
    atk = rook_attacks(A1, occ)
    assert atk & BB_SQUARES[8]  # a2
    assert atk & BB_SQUARES[16]  # a3
    assert atk & BB_SQUARES[24]  # a4 (blocker, included)
    assert not (atk & BB_SQUARES[32])  # a5 (blocked)
