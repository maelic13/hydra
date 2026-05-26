"""Tests for move encoding."""

from hydra.board import Board
from hydra.movegen import generate_legal_moves
from hydra.moves import (
    FLAG_CASTLING,
    FLAG_EN_PASSANT,
    FLAG_NORMAL,
    FLAG_PROMOTION,
    MOVE_NONE,
    PROMO_KNIGHT,
    PROMO_QUEEN,
    make_castling,
    make_en_passant,
    make_move,
    make_promotion,
    move_flag,
    move_from_sq,
    move_promo,
    move_promo_piece_type,
    move_to_sq,
    move_to_uci,
    uci_to_move,
)
from hydra.types import E1, E2, E4, E7, E8, G1, QUEEN, STARTING_FEN


def test_normal_move() -> None:
    m = make_move(E2, E4)
    assert move_from_sq(m) == E2
    assert move_to_sq(m) == E4
    assert move_flag(m) == FLAG_NORMAL


def test_promotion() -> None:
    m = make_promotion(E7, E8, PROMO_QUEEN)
    assert move_from_sq(m) == E7
    assert move_to_sq(m) == E8
    assert move_flag(m) == FLAG_PROMOTION
    assert move_promo(m) == PROMO_QUEEN
    assert move_promo_piece_type(m) == QUEEN


def test_en_passant_flag() -> None:
    m = make_en_passant(E4, 37)  # D5 = 35+2 -> dummy
    assert move_flag(m) == FLAG_EN_PASSANT


def test_castling_flag() -> None:
    m = make_castling(E1, G1)
    assert move_flag(m) == FLAG_CASTLING


def test_uci_roundtrip() -> None:
    m = make_move(E2, E4)
    assert move_to_uci(m) == "e2e4"


def test_uci_promotion() -> None:
    m = make_promotion(E7, E8, PROMO_QUEEN)
    assert move_to_uci(m) == "e7e8q"

    m2 = make_promotion(E7, E8, PROMO_KNIGHT)
    assert move_to_uci(m2) == "e7e8n"


def test_uci_to_move() -> None:
    board = Board.from_fen(STARTING_FEN)
    legal = generate_legal_moves(board)
    m = uci_to_move("e2e4", legal)
    assert m != MOVE_NONE
    assert move_to_uci(m) == "e2e4"


def test_uci_to_move_rejects_malformed_tokens() -> None:
    board = Board.from_fen(STARTING_FEN)
    legal = generate_legal_moves(board)

    assert uci_to_move("d", legal) == MOVE_NONE
    assert uci_to_move("b4", legal) == MOVE_NONE
    assert uci_to_move("i2i4", legal) == MOVE_NONE
