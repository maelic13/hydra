"""Core type definitions and constants for the Hydra chess engine."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
WHITE: int = 0
BLACK: int = 1
COLOR_NB: int = 2

# ---------------------------------------------------------------------------
# Piece types
# ---------------------------------------------------------------------------
PAWN: int = 0
KNIGHT: int = 1
BISHOP: int = 2
ROOK: int = 3
QUEEN: int = 4
KING: int = 5
PIECE_TYPE_NB: int = 6
NO_PIECE_TYPE: int = 6

PIECE_CHARS = "PNBRQKpnbrqk"
PIECE_NAMES = ("pawn", "knight", "bishop", "rook", "queen", "king")

# ---------------------------------------------------------------------------
# Squares  (LERF: a1 = 0, b1 = 1, … h8 = 63)
# ---------------------------------------------------------------------------
(
    A1,
    B1,
    C1,
    D1,
    E1,
    F1,
    G1,
    H1,
    A2,
    B2,
    C2,
    D2,
    E2,
    F2,
    G2,
    H2,
    A3,
    B3,
    C3,
    D3,
    E3,
    F3,
    G3,
    H3,
    A4,
    B4,
    C4,
    D4,
    E4,
    F4,
    G4,
    H4,
    A5,
    B5,
    C5,
    D5,
    E5,
    F5,
    G5,
    H5,
    A6,
    B6,
    C6,
    D6,
    E6,
    F6,
    G6,
    H6,
    A7,
    B7,
    C7,
    D7,
    E7,
    F7,
    G7,
    H7,
    A8,
    B8,
    C8,
    D8,
    E8,
    F8,
    G8,
    H8,
) = range(64)

SQUARE_NB: int = 64
NO_SQUARE: int = 64

SQUARE_NAMES: tuple[str, ...] = tuple(f + r for r in "12345678" for f in "abcdefgh")

FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"


def square_file(sq: int) -> int:
    return sq & 7


def square_rank(sq: int) -> int:
    return sq >> 3


def make_square(file: int, rank: int) -> int:
    return (rank << 3) | file


# ---------------------------------------------------------------------------
# Castling rights  (4-bit mask)
# ---------------------------------------------------------------------------
CASTLING_NONE: int = 0
WK_CASTLE: int = 1  # White O-O
WQ_CASTLE: int = 2  # White O-O-O
BK_CASTLE: int = 4  # Black O-O
BQ_CASTLE: int = 8  # Black O-O-O
WHITE_CASTLING: int = WK_CASTLE | WQ_CASTLE
BLACK_CASTLING: int = BK_CASTLE | BQ_CASTLE
ALL_CASTLING: int = WHITE_CASTLING | BLACK_CASTLING

# Per-square mask: after any move *from* or *to* this square, AND castling
# rights with this mask to revoke the relevant rights.
CASTLING_MASKS: list[int] = [ALL_CASTLING] * 64
CASTLING_MASKS[A1] = ALL_CASTLING & ~WQ_CASTLE
CASTLING_MASKS[E1] = ALL_CASTLING & ~WHITE_CASTLING
CASTLING_MASKS[H1] = ALL_CASTLING & ~WK_CASTLE
CASTLING_MASKS[A8] = ALL_CASTLING & ~BQ_CASTLE
CASTLING_MASKS[E8] = ALL_CASTLING & ~BLACK_CASTLING
CASTLING_MASKS[H8] = ALL_CASTLING & ~BK_CASTLE

# ---------------------------------------------------------------------------
# Directions
# ---------------------------------------------------------------------------
NORTH: int = 8
SOUTH: int = -8
EAST: int = 1
WEST: int = -1
NORTH_EAST: int = 9
NORTH_WEST: int = 7
SOUTH_EAST: int = -7
SOUTH_WEST: int = -9

# ---------------------------------------------------------------------------
# FEN
# ---------------------------------------------------------------------------
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
