"""Move generation tests with perft validation.

Perft (performance test) counts the number of leaf nodes at a given depth.
These are well-known values and serve as the gold standard for correctness
of move generation, make/unmake, and all special moves.
"""

from hydra.board import Board
from hydra.movegen import generate_legal_moves, perft
from hydra.types import STARTING_FEN

# ---- Starting position perft values (https://www.chessprogramming.org/Perft_Results) ----


def test_startpos_depth0() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert perft(board, 0) == 1


def test_startpos_depth1() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert perft(board, 1) == 20


def test_startpos_depth2() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert perft(board, 2) == 400


def test_startpos_depth3() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert perft(board, 3) == 8902


def test_startpos_depth4() -> None:
    board = Board.from_fen(STARTING_FEN)
    assert perft(board, 4) == 197281


# ---- "Kiwipete" position — exercises many special moves ----

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"


def test_kiwipete_depth1() -> None:
    board = Board.from_fen(KIWIPETE)
    assert perft(board, 1) == 48


def test_kiwipete_depth2() -> None:
    board = Board.from_fen(KIWIPETE)
    assert perft(board, 2) == 2039


def test_kiwipete_depth3() -> None:
    board = Board.from_fen(KIWIPETE)
    assert perft(board, 3) == 97862


# ---- Position 3: en-passant + check edge cases ----

POS3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"


def test_pos3_depth1() -> None:
    board = Board.from_fen(POS3)
    assert perft(board, 1) == 14


def test_pos3_depth2() -> None:
    board = Board.from_fen(POS3)
    assert perft(board, 2) == 191


def test_pos3_depth3() -> None:
    board = Board.from_fen(POS3)
    assert perft(board, 3) == 2812


def test_pos3_depth4() -> None:
    board = Board.from_fen(POS3)
    assert perft(board, 4) == 43238


# ---- Position 4: promotions and castling ----

POS4 = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"


def test_pos4_depth1() -> None:
    board = Board.from_fen(POS4)
    assert perft(board, 1) == 6


def test_pos4_depth2() -> None:
    board = Board.from_fen(POS4)
    assert perft(board, 2) == 264


def test_pos4_depth3() -> None:
    board = Board.from_fen(POS4)
    assert perft(board, 3) == 9467


# ---- Position 5: more complex ----

POS5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"


def test_pos5_depth1() -> None:
    board = Board.from_fen(POS5)
    assert perft(board, 1) == 44


def test_pos5_depth2() -> None:
    board = Board.from_fen(POS5)
    assert perft(board, 2) == 1486


def test_pos5_depth3() -> None:
    board = Board.from_fen(POS5)
    assert perft(board, 3) == 62379


# ---- Basic counts check ----


def test_starting_move_count() -> None:
    board = Board.from_fen(STARTING_FEN)
    moves = generate_legal_moves(board)
    assert len(moves) == 20


def test_fen_preserved_after_movegen() -> None:
    """Move generation should not alter the board."""
    board = Board.from_fen(STARTING_FEN)
    fen_before = board.to_fen()
    _ = generate_legal_moves(board)
    assert board.to_fen() == fen_before
