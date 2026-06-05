#!/usr/bin/env python3
"""Hydra ChessAgents single-file adapter.

Generated from Hydra for https://chessagents.ai/ Python Only submissions.
Reads one FEN line, optionally followed by "moves" and UCI history, prints one legal UCI move.
"""

from __future__ import annotations

import math
import random as _random
import sys
import threading
import time
from typing import TYPE_CHECKING, Callable, NamedTuple, Protocol, TextIO

__version__ = "1.4.1-chessagents"


# ===== hydra/types.py =====
"""Core type definitions and constants for the Hydra chess engine."""


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


# ===== hydra/bitboard.py =====
"""Bitboard manipulation utilities and precomputed masks.

All bitboards are plain Python ``int`` values, masked to 64 bits where
necessary with ``& BB_ALL``.  This avoids numpy overhead for scalar ops
and still gives fast bitwise operations.
"""


# ---------------------------------------------------------------------------
# Fundamental constants
# ---------------------------------------------------------------------------
BB_ZERO: int = 0
BB_ALL: int = 0xFFFF_FFFF_FFFF_FFFF

# ---------------------------------------------------------------------------
# File masks
# ---------------------------------------------------------------------------
BB_FILE_A: int = 0x0101_0101_0101_0101
BB_FILE_B: int = BB_FILE_A << 1
BB_FILE_C: int = BB_FILE_A << 2
BB_FILE_D: int = BB_FILE_A << 3
BB_FILE_E: int = BB_FILE_A << 4
BB_FILE_F: int = BB_FILE_A << 5
BB_FILE_G: int = BB_FILE_A << 6
BB_FILE_H: int = BB_FILE_A << 7

BB_FILES: tuple[int, ...] = tuple(BB_FILE_A << i for i in range(8))

BB_NOT_FILE_A: int = BB_ALL ^ BB_FILE_A
BB_NOT_FILE_H: int = BB_ALL ^ BB_FILE_H
BB_NOT_FILE_AB: int = BB_ALL ^ BB_FILE_A ^ BB_FILE_B
BB_NOT_FILE_GH: int = BB_ALL ^ BB_FILE_G ^ BB_FILE_H

# ---------------------------------------------------------------------------
# Rank masks
# ---------------------------------------------------------------------------
BB_RANK_1: int = 0xFF
BB_RANK_2: int = BB_RANK_1 << 8
BB_RANK_3: int = BB_RANK_1 << 16
BB_RANK_4: int = BB_RANK_1 << 24
BB_RANK_5: int = BB_RANK_1 << 32
BB_RANK_6: int = BB_RANK_1 << 40
BB_RANK_7: int = BB_RANK_1 << 48
BB_RANK_8: int = BB_RANK_1 << 56

BB_RANKS: tuple[int, ...] = tuple(BB_RANK_1 << (8 * i) for i in range(8))

# ---------------------------------------------------------------------------
# Square bitboards
# ---------------------------------------------------------------------------
BB_SQUARES: tuple[int, ...] = tuple(1 << sq for sq in range(64))

# ---------------------------------------------------------------------------
# De Bruijn constant and lookup table for 64-bit LSB
# ---------------------------------------------------------------------------
_DEBRUIJN64: int = 0x03F79D71B4CB0A89
_DEBRUIJN_TABLE: tuple[int, ...] = tuple(((_DEBRUIJN64 << sq) & BB_ALL) >> 58 for sq in range(64))
# Inverse: given index, what square?
_lsb_list = [0] * 64
for _sq in range(64):
    _lsb_list[((_DEBRUIJN64 << _sq) & BB_ALL) >> 58] = _sq
_LSB_TABLE: tuple[int, ...] = tuple(_lsb_list)
del _lsb_list, _sq

# ---------------------------------------------------------------------------
# Bit-manipulation helpers
# ---------------------------------------------------------------------------


def popcount(bb: int) -> int:
    """Number of set bits."""
    return bb.bit_count()


def lsb(bb: int) -> int:
    """Index of the least-significant set bit.  Undefined when *bb* == 0."""
    return _LSB_TABLE[(((bb & -bb) * _DEBRUIJN64) & BB_ALL) >> 58]


def msb(bb: int) -> int:
    """Index of the most-significant set bit.  Undefined when *bb* == 0."""
    return bb.bit_length() - 1


def iter_bits(bb: int):
    """Yield square indices of every set bit, lowest first."""
    lsbt = _LSB_TABLE
    db = _DEBRUIJN64
    all_ = BB_ALL
    while bb:
        yield lsbt[(((bb & -bb) * db) & all_) >> 58]
        bb &= bb - 1


# ---------------------------------------------------------------------------
# Shift helpers (with edge-wrapping protection)
# ---------------------------------------------------------------------------


def shift_north(bb: int) -> int:
    return (bb << 8) & BB_ALL


def shift_south(bb: int) -> int:
    return bb >> 8


def shift_east(bb: int) -> int:
    return (bb << 1) & BB_NOT_FILE_A & BB_ALL


def shift_west(bb: int) -> int:
    return (bb >> 1) & BB_NOT_FILE_H


def shift_north_east(bb: int) -> int:
    return (bb << 9) & BB_NOT_FILE_A & BB_ALL


def shift_north_west(bb: int) -> int:
    return (bb << 7) & BB_NOT_FILE_H & BB_ALL


def shift_south_east(bb: int) -> int:
    return (bb >> 7) & BB_NOT_FILE_A


def shift_south_west(bb: int) -> int:
    return (bb >> 9) & BB_NOT_FILE_H


# ===== hydra/attacks.py =====
"""Precomputed attack tables for all piece types.

* **Leapers** (knight, king, pawn): simple 64-entry lookup tables.
* **Sliders** (rook, bishop, queen): magic-bitboard indexed tables.

All tables are initialised at module import time.
"""



# =====================================================================
# Leaper attack tables
# =====================================================================

KNIGHT_ATTACKS: list[int] = [0] * 64
KING_ATTACKS: list[int] = [0] * 64
PAWN_ATTACKS: list[list[int]] = [[0] * 64, [0] * 64]  # [colour][square]


def _init_knight_attacks() -> None:
    for sq in range(64):
        bb = BB_SQUARES[sq]
        a = 0
        a |= (bb << 17) & BB_NOT_FILE_A
        a |= (bb << 15) & BB_NOT_FILE_H
        a |= (bb << 10) & BB_NOT_FILE_AB
        a |= (bb << 6) & BB_NOT_FILE_GH
        a |= (bb >> 6) & BB_NOT_FILE_AB
        a |= (bb >> 10) & BB_NOT_FILE_GH
        a |= (bb >> 15) & BB_NOT_FILE_A
        a |= (bb >> 17) & BB_NOT_FILE_H
        KNIGHT_ATTACKS[sq] = a & BB_ALL


def _init_king_attacks() -> None:
    for sq in range(64):
        bb = BB_SQUARES[sq]
        a = (
            shift_north(bb)
            | shift_south(bb)
            | shift_east(bb)
            | shift_west(bb)
            | shift_north_east(bb)
            | shift_north_west(bb)
            | shift_south_east(bb)
            | shift_south_west(bb)
        )
        KING_ATTACKS[sq] = a


def _init_pawn_attacks() -> None:
    for sq in range(64):
        bb = BB_SQUARES[sq]
        PAWN_ATTACKS[WHITE][sq] = shift_north_east(bb) | shift_north_west(bb)
        PAWN_ATTACKS[BLACK][sq] = shift_south_east(bb) | shift_south_west(bb)


# =====================================================================
# Sliding attacks — ray-based computation (used during init only)
# =====================================================================


def _sliding_attacks(sq: int, occupied: int, is_rook: bool) -> int:
    """Compute sliding attacks for *sq* with the given *occupied* set."""
    attacks = 0
    f, r = sq & 7, sq >> 3
    if is_rook:
        directions = ((0, 1), (0, -1), (1, 0), (-1, 0))
    else:
        directions = ((1, 1), (1, -1), (-1, 1), (-1, -1))
    for dr, df in directions:
        cr, cf = r + dr, f + df
        while 0 <= cr <= 7 and 0 <= cf <= 7:
            s = (cr << 3) | cf
            attacks |= 1 << s
            if occupied & (1 << s):
                break
            cr += dr
            cf += df
    return attacks


# =====================================================================
# Magic bitboard infrastructure
# =====================================================================


def _rook_relevant_mask(sq: int) -> int:
    """Mask of relevant occupancy bits for a rook on *sq* (edges excluded)."""
    mask = 0
    f, r = sq & 7, sq >> 3
    for cr in range(r + 1, 7):
        mask |= 1 << ((cr << 3) | f)
    for cr in range(r - 1, 0, -1):
        mask |= 1 << ((cr << 3) | f)
    for cf in range(f + 1, 7):
        mask |= 1 << ((r << 3) | cf)
    for cf in range(f - 1, 0, -1):
        mask |= 1 << ((r << 3) | cf)
    return mask


def _bishop_relevant_mask(sq: int) -> int:
    """Mask of relevant occupancy bits for a bishop on *sq*."""
    mask = 0
    f, r = sq & 7, sq >> 3
    for dr, df in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        cr, cf = r + dr, f + df
        while 1 <= cr <= 6 and 1 <= cf <= 6:
            mask |= 1 << ((cr << 3) | cf)
            cr += dr
            cf += df
    return mask


def _subsets(mask: int):
    """Carry-Rippler enumeration of all subsets of *mask*."""
    subset = 0
    while True:
        yield subset
        subset = (subset - mask) & mask
        if subset == 0:
            break


# ---- Hardcoded magic numbers (found via randomised search, seed 42) ------

ROOK_MAGICS: tuple[int, ...] = (
    0xA180008021400010,
    0x0240001000200040,
    0xC900102000400B00,
    0x02001020400A0004,
    0x0200200810020004,
    0x0280020004000180,
    0x4200280504820014,
    0x40800CC080002B00,
    0x0006002902004080,
    0x0605004001008022,
    0x0002001080402208,
    0x0002801000480080,
    0x1800800800040080,
    0x8450800400020080,
    0x4221008401000200,
    0x0002000100540082,
    0x0030208000804000,
    0x1000810040002104,
    0x2060008010008020,
    0x8446020020100AC0,
    0x0000828004000800,
    0x0080808004000200,
    0x0401040008020110,
    0x8038620004004081,
    0x0440400080208000,
    0x0800400100210080,
    0x4400200080801000,
    0x0061002300100208,
    0x080A008600082010,
    0x0000020080040080,
    0x2005050C00102208,
    0x2040411200008044,
    0x0080004000402000,
    0x4890042004404002,
    0x0600801000802000,
    0x0201001001002008,
    0x0020080080800400,
    0x0002000400800280,
    0x0C00418804004210,
    0x0000008842000C01,
    0x0080008040008028,
    0x022000303010400C,
    0x0090008020008010,
    0x0070100008008080,
    0x0121000801110004,
    0x0002000804020010,
    0x0040020108040010,
    0x7040084481020024,
    0x040C8700A6084200,
    0x100226410E008200,
    0x4000200080100080,
    0x0010008008001080,
    0xA002908801000500,
    0x1A22001008040200,
    0x0000080250218400,
    0x0860344401008200,
    0x808020401A008102,
    0x0021004000201081,
    0x800200720A2080C2,
    0x1010100120090005,
    0x0002002005081002,
    0x0012008108045002,
    0x000008101A090084,
    0x2004102110428406,
)

BISHOP_MAGICS: tuple[int, ...] = (
    0x0484200081010100,
    0x0802820204150102,
    0x8408009400900000,
    0x2004042080200000,
    0x1032121008010200,
    0xC140822020008020,
    0x2004841160100040,
    0x0041008800A25004,
    0x41506002020A1420,
    0x0110040828084082,
    0x0000A18801004200,
    0x60000F4103308260,
    0x1403845040010400,
    0x1004008220204128,
    0x0318040C04240412,
    0x3200010308422600,
    0x0040001033281110,
    0x0020411001012100,
    0x090800444800A082,
    0x2820200202004400,
    0x0204000584A00504,
    0x80C0408200500410,
    0x0204000041243006,
    0x4002404080445000,
    0x4008600804A41004,
    0x0A04442C02080808,
    0x8008010808084B00,
    0x0008104038004100,
    0x0410030044200800,
    0x300481000A005201,
    0x0020812080841000,
    0x0004002800820101,
    0x4119114000100400,
    0x0104012400081040,
    0x1044219000A80028,
    0xA216A08020880200,
    0x8540020200802080,
    0x0014011600014802,
    0x0C10420200404100,
    0x0200A20040021100,
    0x2001280840004400,
    0x0002080208000200,
    0xA106020211000200,
    0x101001C20880C800,
    0x000002200D000200,
    0x0950200800880A40,
    0x0011020084088100,
    0x800410808A000100,
    0x0801880823104400,
    0x8C0211010110C202,
    0x00440A9400880010,
    0x1000080242120044,
    0x0100090843040020,
    0x8240840408420000,
    0x0104200481020072,
    0x2090140904002100,
    0x80A0202802082040,
    0x0421010088010822,
    0xE1020001C2029060,
    0x5048800080460808,
    0x8400001021420480,
    0x0800084028018108,
    0x010C422208090101,
    0x0810200140408100,
)

# Relevant-bits counts per square (determines table size)
ROOK_BITS: tuple[int, ...] = (
    12,
    11,
    11,
    11,
    11,
    11,
    11,
    12,
    11,
    10,
    10,
    10,
    10,
    10,
    10,
    11,
    11,
    10,
    10,
    10,
    10,
    10,
    10,
    11,
    11,
    10,
    10,
    10,
    10,
    10,
    10,
    11,
    11,
    10,
    10,
    10,
    10,
    10,
    10,
    11,
    11,
    10,
    10,
    10,
    10,
    10,
    10,
    11,
    11,
    10,
    10,
    10,
    10,
    10,
    10,
    11,
    12,
    11,
    11,
    11,
    11,
    11,
    11,
    12,
)

BISHOP_BITS: tuple[int, ...] = (
    6,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    7,
    7,
    7,
    7,
    5,
    5,
    5,
    5,
    7,
    9,
    9,
    7,
    5,
    5,
    5,
    5,
    7,
    9,
    9,
    7,
    5,
    5,
    5,
    5,
    7,
    7,
    7,
    7,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
    5,
    5,
    5,
    5,
    5,
    5,
    6,
)

# Internal tables filled by _init_magic_tables()
_rook_masks: list[int] = [0] * 64
_bishop_masks: list[int] = [0] * 64
_rook_table: list[list[int]] = [[] for _ in range(64)]
_bishop_table: list[list[int]] = [[] for _ in range(64)]

# Precomputed shifts: 64 - BITS[sq]  (avoids subtraction in hot loop)
ROOK_SHIFTS: tuple[int, ...] = tuple(64 - b for b in ROOK_BITS)
BISHOP_SHIFTS: tuple[int, ...] = tuple(64 - b for b in BISHOP_BITS)


def _init_magic_tables() -> None:
    for sq in range(64):
        # ---- Rook ----
        mask = _rook_relevant_mask(sq)
        _rook_masks[sq] = mask
        bits = ROOK_BITS[sq]
        table = [0] * (1 << bits)
        for subset in _subsets(mask):
            idx = ((subset * ROOK_MAGICS[sq]) & BB_ALL) >> (64 - bits)
            table[idx] = _sliding_attacks(sq, subset, True)
        _rook_table[sq] = table

        # ---- Bishop ----
        mask = _bishop_relevant_mask(sq)
        _bishop_masks[sq] = mask
        bits = BISHOP_BITS[sq]
        table = [0] * (1 << bits)
        for subset in _subsets(mask):
            idx = ((subset * BISHOP_MAGICS[sq]) & BB_ALL) >> (64 - bits)
            table[idx] = _sliding_attacks(sq, subset, False)
        _bishop_table[sq] = table


# =====================================================================
# Public query API
# =====================================================================


def rook_attacks(sq: int, occupied: int) -> int:
    occ = occupied & _rook_masks[sq]
    idx = ((occ * ROOK_MAGICS[sq]) & BB_ALL) >> (64 - ROOK_BITS[sq])
    return _rook_table[sq][idx]


def bishop_attacks(sq: int, occupied: int) -> int:
    occ = occupied & _bishop_masks[sq]
    idx = ((occ * BISHOP_MAGICS[sq]) & BB_ALL) >> (64 - BISHOP_BITS[sq])
    return _bishop_table[sq][idx]


def queen_attacks(sq: int, occupied: int) -> int:
    return rook_attacks(sq, occupied) | bishop_attacks(sq, occupied)


def is_square_attacked(sq: int, by_colour: int, board_pieces, occ: int) -> bool:
    """Return True if *sq* is attacked by *by_colour*.

    *board_pieces* is ``board.pieces`` — a ``[colour][piece_type]`` list of
    bitboards.  Passing it explicitly avoids a circular import.
    """
    them = board_pieces[by_colour]
    if KNIGHT_ATTACKS[sq] & them[1]:  # KNIGHT = 1
        return True
    if PAWN_ATTACKS[1 - by_colour][sq] & them[0]:  # PAWN = 0
        return True
    if KING_ATTACKS[sq] & them[5]:  # KING = 5
        return True
    bq = them[2] | them[4]  # BISHOP | QUEEN
    if bq and bishop_attacks(sq, occ) & bq:
        return True
    rq = them[3] | them[4]  # ROOK | QUEEN
    return bool(rq and rook_attacks(sq, occ) & rq)


def attackers_to(sq: int, occ: int, pieces) -> int:
    """Return a bitboard of all pieces (both colours) that attack *sq*."""

    atk = 0
    for colour in (0, 1):
        them = pieces[colour]
        atk |= KNIGHT_ATTACKS[sq] & them[KNIGHT]
        atk |= PAWN_ATTACKS[1 - colour][sq] & them[PAWN]
        atk |= KING_ATTACKS[sq] & them[KING]
        atk |= bishop_attacks(sq, occ) & (them[BISHOP] | them[QUEEN])
        atk |= rook_attacks(sq, occ) & (them[ROOK] | them[QUEEN])
    return atk


# =====================================================================
# Module initialisation
# =====================================================================

_init_knight_attacks()
_init_king_attacks()
_init_pawn_attacks()
_init_magic_tables()


# ===== hydra/zobrist.py =====
"""Zobrist hashing tables.

A random 64-bit key is assigned to every (colour, piece-type, square) triple,
plus keys for castling rights, en-passant file and side-to-move.  The board
hash is the XOR of the keys for all features present in the position.

Keys are generated deterministically from a fixed seed so that hashes are
reproducible across runs.
"""




_SEED = 0xBEA572  # reproducible

_rng = _random.Random(_SEED)
_rand64 = lambda: _rng.getrandbits(64)  # noqa: E731

# piece_keys[colour][piece_type][square]
PIECE_KEYS: tuple[tuple[tuple[int, ...], ...], ...] = tuple(
    tuple(tuple(_rand64() for _ in range(SQUARE_NB)) for _ in range(PIECE_TYPE_NB))
    for _ in range(COLOR_NB)
)

# en-passant file keys (indexed 0..7)
EP_KEYS: tuple[int, ...] = tuple(_rand64() for _ in range(8))

# castling-rights keys (indexed 0..15, one per 4-bit combination)
CASTLING_KEYS: tuple[int, ...] = tuple(_rand64() for _ in range(16))

# side-to-move key (XOR-ed in when it is Black's turn)
SIDE_KEY: int = _rand64()


# ===== hydra/moves.py =====
"""Compact 16-bit integer move encoding.

Layout (LSB → MSB)::

    bits  0– 5 : from-square   (0–63)
    bits  6–11 : to-square     (0–63)
    bits 12–13 : promotion piece offset (0 = knight … 3 = queen)
    bits 14–15 : special flag
                   0 = normal / capture
                   1 = promotion
                   2 = en-passant capture
                   3 = castling

Using a plain ``int`` instead of a dataclass avoids allocation overhead in
the inner move-generation loop.
"""



# ---------------------------------------------------------------------------
# Flag constants
# ---------------------------------------------------------------------------
FLAG_NORMAL: int = 0
FLAG_PROMOTION: int = 1
FLAG_EN_PASSANT: int = 2
FLAG_CASTLING: int = 3

# Promotion piece offsets (stored in bits 12-13)
PROMO_KNIGHT: int = 0
PROMO_BISHOP: int = 1
PROMO_ROOK: int = 2
PROMO_QUEEN: int = 3

# Null / invalid move sentinel
MOVE_NONE: int = 0

# ---------------------------------------------------------------------------
# Move construction
# ---------------------------------------------------------------------------


def make_move(from_sq: int, to_sq: int) -> int:
    """Encode a normal (quiet or capture) move."""
    return from_sq | (to_sq << 6)


def make_promotion(from_sq: int, to_sq: int, promo: int) -> int:
    """Encode a promotion.  *promo* is PROMO_KNIGHT … PROMO_QUEEN."""
    return from_sq | (to_sq << 6) | (promo << 12) | (FLAG_PROMOTION << 14)


def make_en_passant(from_sq: int, to_sq: int) -> int:
    return from_sq | (to_sq << 6) | (FLAG_EN_PASSANT << 14)


def make_castling(king_from: int, king_to: int) -> int:
    return king_from | (king_to << 6) | (FLAG_CASTLING << 14)


# ---------------------------------------------------------------------------
# Move field extraction
# ---------------------------------------------------------------------------


def move_from_sq(move: int) -> int:
    return move & 0x3F


def move_to_sq(move: int) -> int:
    return (move >> 6) & 0x3F


def move_promo(move: int) -> int:
    """Promotion piece offset (only meaningful when flag == FLAG_PROMOTION)."""
    return (move >> 12) & 0x3


def move_flag(move: int) -> int:
    return (move >> 14) & 0x3


def move_promo_piece_type(move: int) -> int:
    """Return the piece-type constant (KNIGHT..QUEEN) for a promotion move."""
    return KNIGHT + move_promo(move)


# ---------------------------------------------------------------------------
# UCI string conversion
# ---------------------------------------------------------------------------


def move_to_uci(move: int) -> str:
    if move == MOVE_NONE:
        return "0000"
    fsq = move_from_sq(move)
    tsq = move_to_sq(move)
    uci = SQUARE_NAMES[fsq] + SQUARE_NAMES[tsq]
    if move_flag(move) == FLAG_PROMOTION:
        uci += "nbrq"[move_promo(move)]
    return uci


def uci_to_move(uci: str, legal_moves: list[int]) -> int:
    """Find the legal move matching a UCI string.

    We need the list of legal moves because the UCI string alone is
    ambiguous (e.g. it doesn't distinguish en-passant from a normal
    pawn capture).  Returns *MOVE_NONE* if no match.
    """
    if len(uci) not in {4, 5}:
        return MOVE_NONE
    if (
        uci[0] not in FILE_NAMES
        or uci[1] not in RANK_NAMES
        or uci[2] not in FILE_NAMES
        or uci[3] not in RANK_NAMES
    ):
        return MOVE_NONE
    from_sq = make_square(FILE_NAMES.index(uci[0]), RANK_NAMES.index(uci[1]))
    to_sq = make_square(FILE_NAMES.index(uci[2]), RANK_NAMES.index(uci[3]))
    for m in legal_moves:
        if move_from_sq(m) == from_sq and move_to_sq(m) == to_sq:
            if len(uci) == 5:
                if move_flag(m) == FLAG_PROMOTION and "nbrq"[move_promo(m)] == uci[4]:
                    return m
            elif move_flag(m) != FLAG_PROMOTION:
                return m
    return MOVE_NONE


# ===== hydra/board.py =====
"""Board state — the central data structure of the engine.

Maintains **bitboards** (fast set operations), a **mailbox** array (fast
piece-on-square lookup), incrementally updated **Zobrist hash**, and a
**history stack** for unmake.
"""



# Local aliases to avoid attribute lookups in tight loops
_BB = BB_SQUARES
_PK = PIECE_KEYS
_EPK = EP_KEYS
_CK = CASTLING_KEYS
_SK = SIDE_KEY
_CM = CASTLING_MASKS
_NPT = NO_PIECE_TYPE
_BALL = BB_ALL
_KNIGHT_ATK = KNIGHT_ATTACKS
_KING_ATK = KING_ATTACKS
_PAWN_ATK = PAWN_ATTACKS
_RM = _rook_masks
_BM = _bishop_masks
_RT = _rook_table
_BT = _bishop_table
_RMAG = ROOK_MAGICS
_BMAG = BISHOP_MAGICS
_RSHIFT = ROOK_SHIFTS
_BSHIFT = BISHOP_SHIFTS
_NS = NO_SQUARE


class Board:
    """Full board state with make / unmake and incremental Zobrist hash."""

    __slots__ = (
        "_check_cache_key",
        "_check_cache_value",
        "_king_sqs",
        "all_occ",
        "castling",
        "ep_square",
        "fullmove",
        "halfmove",
        "hash",
        "history",
        "mailbox",
        "mailbox_color",
        "occupancy",
        "pieces",
        "side",
    )

    def __init__(self) -> None:
        # pieces[colour][piece_type] — plain-int bitboards
        self.pieces: list[list[int]] = [[0] * PIECE_TYPE_NB for _ in range(COLOR_NB)]
        self.occupancy: list[int] = [0, 0]  # [colour]
        self.all_occ: int = 0

        self.mailbox: list[int] = [_NPT] * SQUARE_NB
        self.mailbox_color: list[int] = [-1] * SQUARE_NB

        self.side: int = WHITE
        self.castling: int = ALL_CASTLING
        self.ep_square: int = _NS
        self.halfmove: int = 0
        self.fullmove: int = 1

        self.hash: int = 0
        # history entries are tuples: (captured, castling, ep_square, halfmove, hash)
        self.history: list[tuple[int, int, int, int, int]] = []
        self._king_sqs: list[int] = [_NS, _NS]  # [WHITE, BLACK]
        self._check_cache_key: int = -1
        self._check_cache_value: bool = False

    # ------------------------------------------------------------------
    # Internal helpers (kept for FEN loading and unmake edge cases)
    # ------------------------------------------------------------------

    def _put_piece(self, colour: int, piece: int, sq: int) -> None:
        bb = _BB[sq]
        self.pieces[colour][piece] |= bb
        self.occupancy[colour] |= bb
        self.all_occ |= bb
        self.mailbox[sq] = piece
        self.mailbox_color[sq] = colour
        self.hash ^= _PK[colour][piece][sq]
        if piece == KING:
            self._king_sqs[colour] = sq

    def _remove_piece(self, colour: int, piece: int, sq: int) -> None:
        bb = _BB[sq]
        self.pieces[colour][piece] ^= bb
        self.occupancy[colour] ^= bb
        self.all_occ ^= bb
        self.mailbox[sq] = _NPT
        self.mailbox_color[sq] = -1
        self.hash ^= _PK[colour][piece][sq]

    def _recompute_occupancy(self) -> None:
        for c in (WHITE, BLACK):
            occ = 0
            for pt in range(PIECE_TYPE_NB):
                occ |= self.pieces[c][pt]
            self.occupancy[c] = occ
        self.all_occ = self.occupancy[WHITE] | self.occupancy[BLACK]

    # ------------------------------------------------------------------
    # King square (cached — O(1))
    # ------------------------------------------------------------------

    def king_sq(self, colour: int) -> int:
        return self._king_sqs[colour]

    # ------------------------------------------------------------------
    # Check detection
    # ------------------------------------------------------------------

    def is_in_check(self) -> bool:
        key = self.hash
        if self._check_cache_key == key:
            return self._check_cache_value
        sq = self._king_sqs[self.side]
        them = self.pieces[1 - self.side]
        occ = self.all_occ
        bq = them[2] | them[4]
        rq = them[3] | them[4]
        result = bool(
            (_KNIGHT_ATK[sq] & them[1])
            or (_PAWN_ATK[self.side][sq] & them[0])
            or (_KING_ATK[sq] & them[5])
            or (bq and _BT[sq][((occ & _BM[sq]) * _BMAG[sq] & _BALL) >> _BSHIFT[sq]] & bq)
            or (rq and _RT[sq][((occ & _RM[sq]) * _RMAG[sq] & _BALL) >> _RSHIFT[sq]] & rq)
        )
        self._check_cache_key = key
        self._check_cache_value = result
        return result

    def is_square_attacked_by(self, sq: int, by_colour: int) -> bool:
        them = self.pieces[by_colour]
        occ = self.all_occ
        if _KNIGHT_ATK[sq] & them[1]:
            return True
        if _PAWN_ATK[1 - by_colour][sq] & them[0]:
            return True
        if _KING_ATK[sq] & them[5]:
            return True
        bq = them[2] | them[4]
        if bq:
            o = occ & _BM[sq]
            if _BT[sq][((o * _BMAG[sq]) & _BALL) >> _BSHIFT[sq]] & bq:
                return True
        rq = them[3] | them[4]
        if rq:
            o = occ & _RM[sq]
            if _RT[sq][((o * _RMAG[sq]) & _BALL) >> _RSHIFT[sq]] & rq:
                return True
        return False

    # ------------------------------------------------------------------
    # Make / Unmake  (fully inlined for performance)
    # ------------------------------------------------------------------

    def make_move(self, move: int) -> None:
        """Apply *move* to the board.  Pushes state onto the history stack."""
        # Inline move field extraction
        fsq = move & 0x3F
        tsq = (move >> 6) & 0x3F
        flag = (move >> 14) & 0x3

        us = self.side
        them = 1 - us

        pieces = self.pieces
        occ = self.occupancy
        mailbox = self.mailbox
        mailbox_color = self.mailbox_color

        piece = mailbox[fsq]
        captured = mailbox[tsq]  # may be _NPT

        # Save state for unmake (plain tuple — no dataclass allocation)
        self.history.append((captured, self.castling, self.ep_square, self.halfmove, self.hash))

        h = self.hash

        # Remove en-passant hash contribution
        ep = self.ep_square
        if ep != _NS:
            h ^= _EPK[ep & 7]

        # Remove castling hash (will re-add after update)
        h ^= _CK[self.castling]

        # ---- Handle captures ----
        if flag == FLAG_EN_PASSANT:
            cap_sq = tsq + (-8 if us == WHITE else 8)
            captured = PAWN
            # Inline _remove_piece for captured pawn
            cap_bb = _BB[cap_sq]
            pieces[them][PAWN] ^= cap_bb
            occ[them] ^= cap_bb
            self.all_occ ^= cap_bb
            mailbox[cap_sq] = _NPT
            mailbox_color[cap_sq] = -1
            h ^= _PK[them][PAWN][cap_sq]
        elif captured != _NPT:
            # Inline _remove_piece for captured piece
            cap_bb = _BB[tsq]
            pieces[them][captured] ^= cap_bb
            occ[them] ^= cap_bb
            self.all_occ ^= cap_bb
            mailbox[tsq] = _NPT
            mailbox_color[tsq] = -1
            h ^= _PK[them][captured][tsq]

        # ---- Move the piece ----
        if flag == FLAG_CASTLING:
            # Inline _move_piece for king
            kbb = _BB[fsq] | _BB[tsq]
            pieces[us][KING] ^= kbb
            occ[us] ^= kbb
            self.all_occ ^= kbb
            mailbox[fsq] = _NPT
            mailbox_color[fsq] = -1
            mailbox[tsq] = KING
            mailbox_color[tsq] = us
            h ^= _PK[us][KING][fsq] ^ _PK[us][KING][tsq]
            self._king_sqs[us] = tsq

            # Determine rook squares
            if tsq > fsq:  # kingside
                rook_from = H1 if us == WHITE else H8
                rook_to = F1 if us == WHITE else F8
            else:  # queenside
                rook_from = A1 if us == WHITE else A8
                rook_to = D1 if us == WHITE else D8

            # Inline _move_piece for rook
            rbb = _BB[rook_from] | _BB[rook_to]
            pieces[us][ROOK] ^= rbb
            occ[us] ^= rbb
            self.all_occ ^= rbb
            mailbox[rook_from] = _NPT
            mailbox_color[rook_from] = -1
            mailbox[rook_to] = ROOK
            mailbox_color[rook_to] = us
            h ^= _PK[us][ROOK][rook_from] ^ _PK[us][ROOK][rook_to]

        elif flag == FLAG_PROMOTION:
            promo_pt = KNIGHT + ((move >> 12) & 0x3)
            # Inline _remove_piece for pawn at fsq
            fbb = _BB[fsq]
            pieces[us][PAWN] ^= fbb
            occ[us] ^= fbb
            self.all_occ ^= fbb
            mailbox[fsq] = _NPT
            mailbox_color[fsq] = -1
            h ^= _PK[us][PAWN][fsq]
            # Inline _put_piece for promoted piece at tsq
            tbb = _BB[tsq]
            pieces[us][promo_pt] |= tbb
            occ[us] |= tbb
            self.all_occ |= tbb
            mailbox[tsq] = promo_pt
            mailbox_color[tsq] = us
            h ^= _PK[us][promo_pt][tsq]

        else:
            # Inline _move_piece for normal move
            mbb = _BB[fsq] | _BB[tsq]
            pieces[us][piece] ^= mbb
            occ[us] ^= mbb
            self.all_occ ^= mbb
            mailbox[fsq] = _NPT
            mailbox_color[fsq] = -1
            mailbox[tsq] = piece
            mailbox_color[tsq] = us
            h ^= _PK[us][piece][fsq] ^ _PK[us][piece][tsq]
            if piece == KING:
                self._king_sqs[us] = tsq

        # ---- Update castling rights ----
        self.castling &= _CM[fsq] & _CM[tsq]
        h ^= _CK[self.castling]

        # ---- Update en-passant square ----
        if piece == PAWN and (tsq ^ fsq) == 16:
            ep_candidate = (fsq + tsq) >> 1
            self.ep_square = ep_candidate
            h ^= _EPK[ep_candidate & 7]
        else:
            self.ep_square = _NS

        # ---- Halfmove clock ----
        if piece == PAWN or captured != _NPT:
            self.halfmove = 0
        else:
            self.halfmove += 1

        # ---- Fullmove counter ----
        if us == BLACK:
            self.fullmove += 1

        # ---- Flip side ----
        self.side = them
        self.hash = h ^ _SK

    def unmake_move(self, move: int) -> None:
        """Undo the last move, restoring from the history stack."""
        # Unpack state tuple
        captured, prev_castling, prev_ep, prev_halfmove, prev_hash = self.history.pop()

        # Flip side back
        self.side = 1 - self.side
        us = self.side
        them = 1 - us

        # Inline move field extraction
        fsq = move & 0x3F
        tsq = (move >> 6) & 0x3F
        flag = (move >> 14) & 0x3

        pieces = self.pieces
        occ = self.occupancy
        mailbox = self.mailbox
        mailbox_color = self.mailbox_color

        if flag == FLAG_CASTLING:
            # Inline undo king move
            kbb = _BB[tsq] | _BB[fsq]
            pieces[us][KING] ^= kbb
            occ[us] ^= kbb
            self.all_occ ^= kbb
            mailbox[tsq] = _NPT
            mailbox_color[tsq] = -1
            mailbox[fsq] = KING
            mailbox_color[fsq] = us
            self._king_sqs[us] = fsq

            # Determine rook squares
            if tsq > fsq:  # kingside
                rook_from = H1 if us == WHITE else H8
                rook_to = F1 if us == WHITE else F8
            else:  # queenside
                rook_from = A1 if us == WHITE else A8
                rook_to = D1 if us == WHITE else D8

            # Inline undo rook move
            rbb = _BB[rook_to] | _BB[rook_from]
            pieces[us][ROOK] ^= rbb
            occ[us] ^= rbb
            self.all_occ ^= rbb
            mailbox[rook_to] = _NPT
            mailbox_color[rook_to] = -1
            mailbox[rook_from] = ROOK
            mailbox_color[rook_from] = us

        elif flag == FLAG_PROMOTION:
            promo_pt = KNIGHT + ((move >> 12) & 0x3)
            # Inline _remove_piece for promoted piece at tsq
            tbb = _BB[tsq]
            pieces[us][promo_pt] ^= tbb
            occ[us] ^= tbb
            self.all_occ ^= tbb
            mailbox[tsq] = _NPT
            mailbox_color[tsq] = -1
            # Inline _put_piece for pawn at fsq
            fbb = _BB[fsq]
            pieces[us][PAWN] |= fbb
            occ[us] |= fbb
            self.all_occ |= fbb
            mailbox[fsq] = PAWN
            mailbox_color[fsq] = us

        else:
            piece = mailbox[tsq]
            # Inline _move_piece: tsq -> fsq
            mbb = _BB[tsq] | _BB[fsq]
            pieces[us][piece] ^= mbb
            occ[us] ^= mbb
            self.all_occ ^= mbb
            mailbox[tsq] = _NPT
            mailbox_color[tsq] = -1
            mailbox[fsq] = piece
            mailbox_color[fsq] = us
            if piece == KING:
                self._king_sqs[us] = fsq

        # Restore captured piece
        if flag == FLAG_EN_PASSANT:
            cap_sq = tsq + (-8 if us == WHITE else 8)
            # Inline _put_piece for captured pawn
            cap_bb = _BB[cap_sq]
            pieces[them][PAWN] |= cap_bb
            occ[them] |= cap_bb
            self.all_occ |= cap_bb
            mailbox[cap_sq] = PAWN
            mailbox_color[cap_sq] = them
        elif captured != _NPT:
            # Inline _put_piece for captured piece
            cap_bb = _BB[tsq]
            pieces[them][captured] |= cap_bb
            occ[them] |= cap_bb
            self.all_occ |= cap_bb
            mailbox[tsq] = captured
            mailbox_color[tsq] = them

        # Restore state from tuple
        self.castling = prev_castling
        self.ep_square = prev_ep
        self.halfmove = prev_halfmove
        if us == BLACK:
            self.fullmove -= 1
        self.hash = prev_hash

    # ------------------------------------------------------------------
    # Null move (pass turn — used by null-move pruning in search)
    # ------------------------------------------------------------------

    def make_null_move(self) -> None:
        """Pass the turn without moving.  Updates hash, clears EP, flips side."""
        self.history.append((_NPT, self.castling, self.ep_square, self.halfmove, self.hash))
        h = self.hash
        if self.ep_square != _NS:
            h ^= _EPK[self.ep_square & 7]
        self.ep_square = _NS
        self.side = 1 - self.side
        self.hash = h ^ _SK

    def unmake_null_move(self) -> None:
        """Undo a null move, restoring the previous state."""
        _, _, prev_ep, prev_halfmove, prev_hash = self.history.pop()
        self.side = 1 - self.side
        self.ep_square = prev_ep
        self.halfmove = prev_halfmove
        self.hash = prev_hash

    # ------------------------------------------------------------------
    # FEN I/O
    # ------------------------------------------------------------------

    @classmethod
    def from_fen(cls, fen: str) -> Board:
        board = cls()
        parts = fen.split()
        if len(parts) != 6:
            msg = f"FEN must have 6 fields, got {len(parts)}"
            raise ValueError(msg)

        rows = parts[0].split("/")
        if len(rows) != 8:
            msg = f"FEN board must have 8 ranks, got {len(rows)}"
            raise ValueError(msg)

        for rank_idx, row in enumerate(reversed(rows)):
            file_idx = 0
            for ch in row:
                if ch.isdigit():
                    skip = int(ch)
                    if skip < 1 or skip > 8:
                        msg = f"Invalid skip digit '{ch}' in rank {8 - rank_idx}"
                        raise ValueError(msg)
                    file_idx += skip
                elif ch in PIECE_CHARS:
                    colour = WHITE if ch.isupper() else BLACK
                    piece = PIECE_CHARS.index(ch) % 6
                    sq = make_square(file_idx, rank_idx)
                    bb = _BB[sq]
                    board.pieces[colour][piece] |= bb
                    board.mailbox[sq] = piece
                    board.mailbox_color[sq] = colour
                    if piece == KING:
                        board._king_sqs[colour] = sq
                    file_idx += 1
                else:
                    msg = f"Invalid character '{ch}' in FEN board"
                    raise ValueError(msg)
            if file_idx != 8:
                msg = f"Rank {8 - rank_idx} has {file_idx} squares instead of 8"
                raise ValueError(msg)

        # Side to move
        if parts[1] not in {"w", "b"}:
            msg = f"Invalid side to move: '{parts[1]}'"
            raise ValueError(msg)
        board.side = WHITE if parts[1] == "w" else BLACK

        # Castling
        board.castling = CASTLING_NONE
        if parts[2] != "-":
            for ch in parts[2]:
                if ch == "K":
                    board.castling |= WK_CASTLE
                elif ch == "Q":
                    board.castling |= WQ_CASTLE
                elif ch == "k":
                    board.castling |= BK_CASTLE
                elif ch == "q":
                    board.castling |= BQ_CASTLE
                else:
                    msg = f"Invalid castling character: '{ch}'"
                    raise ValueError(msg)

        # En passant
        if parts[3] != "-":
            if len(parts[3]) != 2 or parts[3][0] not in FILE_NAMES or parts[3][1] not in RANK_NAMES:
                msg = f"Invalid en passant square: '{parts[3]}'"
                raise ValueError(msg)
            board.ep_square = make_square(
                FILE_NAMES.index(parts[3][0]), RANK_NAMES.index(parts[3][1])
            )

        # Halfmove and fullmove clocks
        try:
            board.halfmove = int(parts[4])
        except ValueError:
            msg = f"Invalid halfmove clock: '{parts[4]}'"
            raise ValueError(msg) from None
        try:
            board.fullmove = int(parts[5])
        except ValueError:
            msg = f"Invalid fullmove number: '{parts[5]}'"
            raise ValueError(msg) from None
        if board.halfmove < 0:
            msg = f"Halfmove clock must be non-negative, got {board.halfmove}"
            raise ValueError(msg)
        if board.fullmove == 0:
            board.fullmove = 1
        elif board.fullmove < 0:
            msg = f"Fullmove number must be >= 1, got {board.fullmove}"
            raise ValueError(msg)

        # Validate exactly one king per side
        for c, name in ((WHITE, "White"), (BLACK, "Black")):
            k = board.pieces[c][KING]
            cnt = k.bit_count()
            if cnt != 1:
                msg = f"{name} must have exactly 1 king, found {cnt}"
                raise ValueError(msg)

        board._recompute_occupancy()
        board._init_hash()
        return board

    def _init_hash(self) -> None:
        """Compute the full Zobrist hash from scratch."""
        h = 0
        for colour in (WHITE, BLACK):
            for pt in range(PIECE_TYPE_NB):
                bb = self.pieces[colour][pt]
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    h ^= _PK[colour][pt][sq]
                    bb &= bb - 1
        h ^= _CK[self.castling]
        if self.ep_square != _NS:
            h ^= _EPK[self.ep_square & 7]
        if self.side == BLACK:
            h ^= _SK
        self.hash = h

    def to_fen(self) -> str:
        rows: list[str] = []
        for rank_idx in range(7, -1, -1):
            row = ""
            empty = 0
            for file_idx in range(8):
                sq = (rank_idx << 3) | file_idx
                pt = self.mailbox[sq]
                if pt == _NPT:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    colour = self.mailbox_color[sq]
                    idx = pt + (6 if colour == BLACK else 0)
                    row += PIECE_CHARS[idx]
            if empty:
                row += str(empty)
            rows.append(row)

        fen = "/".join(rows)
        fen += " w " if self.side == WHITE else " b "

        castling = ""
        if self.castling & WK_CASTLE:
            castling += "K"
        if self.castling & WQ_CASTLE:
            castling += "Q"
        if self.castling & BK_CASTLE:
            castling += "k"
        if self.castling & BQ_CASTLE:
            castling += "q"
        fen += castling or "-"

        if self.ep_square != _NS:
            fen += " " + SQUARE_NAMES[self.ep_square]
        else:
            fen += " -"
        fen += f" {self.halfmove} {self.fullmove}"
        return fen

    def copy(self) -> Board:
        """Return a deep copy (no shared mutable state)."""
        b = Board()
        b.pieces = [row[:] for row in self.pieces]
        b.occupancy = self.occupancy[:]
        b.all_occ = self.all_occ
        b.mailbox = self.mailbox[:]
        b.mailbox_color = self.mailbox_color[:]
        b.side = self.side
        b.castling = self.castling
        b.ep_square = self.ep_square
        b.halfmove = self.halfmove
        b.fullmove = self.fullmove
        b.hash = self.hash
        b.history = self.history[:]
        b._king_sqs = self._king_sqs[:]
        b._check_cache_key = self._check_cache_key
        b._check_cache_value = self._check_cache_value
        return b

    def __repr__(self) -> str:
        return f"Board(fen='{self.to_fen()}')"


# ===== hydra/movegen.py =====
"""Legal move generation and perft.

Strategy: generate *pseudo-legal* moves, then filter out those that leave the
own king in check via a lightweight inline legality check.

When in check, a specialised evasion generator restricts candidate moves to
king moves, captures of the checker, and blocks — avoiding full movegen.
"""




# Local aliases for hot-path
_BB = BB_SQUARES
_PAWN_ATK = PAWN_ATTACKS
_KNIGHT_ATK = KNIGHT_ATTACKS
_KING_ATK = KING_ATTACKS
_RM = _rook_masks
_BM = _bishop_masks
_RT = _rook_table
_BT = _bishop_table
_RMAG = ROOK_MAGICS
_BMAG = BISHOP_MAGICS
_RSHIFT = ROOK_SHIFTS
_BSHIFT = BISHOP_SHIFTS
_BALL = BB_ALL

# Promotion encoding constants (inlined from moves.py)
_FLAG_PROMO = 1 << 14
_FLAG_EP = 2 << 14
_FLAG_CASTLE = 3 << 14
_PROMO_Q = PROMO_QUEEN << 12
_PROMO_R = PROMO_ROOK << 12
_PROMO_B = PROMO_BISHOP << 12
_PROMO_N = PROMO_KNIGHT << 12


# ---------------------------------------------------------------------------
# Inline sliding attack helpers (avoid function call overhead)
# ---------------------------------------------------------------------------


def _rook_atk(sq: int, occ: int) -> int:
    o = occ & _RM[sq]
    return _RT[sq][((o * _RMAG[sq]) & _BALL) >> _RSHIFT[sq]]


def _bishop_atk(sq: int, occ: int) -> int:
    o = occ & _BM[sq]
    return _BT[sq][((o * _BMAG[sq]) & _BALL) >> _BSHIFT[sq]]


# Precomputed empty-board sliding rays — used as ray-existence guards in
# generate_captures to skip the magic lookup when a piece can't reach any enemy.
_BRAY: list[int] = [_bishop_atk(sq, 0) for sq in range(64)]
_RRAY: list[int] = [_rook_atk(sq, 0) for sq in range(64)]


def _sq_attacked(
    sq: int, tp0: int, tp1: int, tp2: int, tp3: int, tp4: int, tp5: int, pawn_atk_us: list, occ: int
) -> bool:
    """Is sq attacked by enemy (tp0..tp5)?  pawn_atk_us = PAWN_ATTACKS[our_side]."""
    if pawn_atk_us[sq] & tp0:
        return True
    if _KNIGHT_ATK[sq] & tp1:
        return True
    if _KING_ATK[sq] & tp5:
        return True
    bq = tp2 | tp4
    if bq:
        o = occ & _BM[sq]
        if _BT[sq][((o * _BMAG[sq]) & _BALL) >> _BSHIFT[sq]] & bq:
            return True
    rq = tp3 | tp4
    if rq:
        o = occ & _RM[sq]
        if _RT[sq][((o * _RMAG[sq]) & _BALL) >> _RSHIFT[sq]] & rq:
            return True
    return False


# ---------------------------------------------------------------------------
# Check detection helpers
# ---------------------------------------------------------------------------


def _checkers(board: Board) -> int:
    """Return bitboard of pieces giving check to the side to move."""
    us = board.side
    them = 1 - us
    ksq = board._king_sqs[us]
    occ = board.all_occ
    tp = board.pieces[them]
    attackers = 0
    attackers |= _PAWN_ATK[us][ksq] & tp[PAWN]
    attackers |= _KNIGHT_ATK[ksq] & tp[KNIGHT]
    attackers |= _bishop_atk(ksq, occ) & (tp[BISHOP] | tp[QUEEN])
    attackers |= _rook_atk(ksq, occ) & (tp[ROOK] | tp[QUEEN])
    return attackers


def _between(sq1: int, sq2: int) -> int:
    """Return bitboard of squares strictly between sq1 and sq2 (on same ray).

    Uses a quick ray computation.  Returns 0 when squares are not aligned
    or adjacent.
    """
    # Determine direction
    r1, f1 = divmod(sq1, 8)
    r2, f2 = divmod(sq2, 8)
    dr = 0 if r2 == r1 else (1 if r2 > r1 else -1)
    df = 0 if f2 == f1 else (1 if f2 > f1 else -1)
    if dr == 0 and df == 0:
        return 0
    # Must be on same rank, file, or diagonal
    if dr != 0 and df != 0 and abs(r2 - r1) != abs(f2 - f1):
        return 0
    if dr == 0 and f1 == f2:
        return 0
    bb = 0
    r, f = r1 + dr, f1 + df
    while 0 <= r < 8 and 0 <= f < 8:
        sq = r * 8 + f
        if sq == sq2:
            break
        bb |= _BB[sq]
        r += dr
        f += df
    return bb


# Precompute between table for all 64×64 square pairs
_BETWEEN: list[list[int]] = [[0] * 64 for _ in range(64)]
for _s1 in range(64):
    for _s2 in range(64):
        _BETWEEN[_s1][_s2] = _between(_s1, _s2)


# ---------------------------------------------------------------------------
# Pseudo-legal move generation
# ---------------------------------------------------------------------------


def _gen_pawn_moves(board: Board, moves: list[int]) -> None:
    us = board.side
    them = 1 - us
    our_pawns = board.pieces[us][PAWN]
    enemy = board.occupancy[them]
    occ = board.all_occ
    empty = ~occ & _BALL

    if us == WHITE:
        ((our_pawns << 8) & _BALL) & empty
        push2 = ((((our_pawns & BB_RANK_2) << 8) & _BALL & empty) << 8) & _BALL & empty
        promo_rank = BB_RANK_7
        pawn_dir = 8
    else:
        (our_pawns >> 8) & empty
        push2 = ((((our_pawns & BB_RANK_7) >> 8) & empty) >> 8) & empty
        promo_rank = BB_RANK_2
        pawn_dir = -8

    promo_pawns = our_pawns & promo_rank
    non_promo_pawns = our_pawns & ~promo_rank

    append = moves.append
    patk = _PAWN_ATK[us]

    # ---- Single pushes (non-promoting) ----
    targets = non_promo_pawns << 8 & _BALL & empty if us == WHITE else non_promo_pawns >> 8 & empty
    bb = targets
    while bb:
        tsq = (bb & -bb).bit_length() - 1
        append((tsq - pawn_dir) | (tsq << 6))
        bb &= bb - 1

    # ---- Double pushes ----
    bb = push2
    while bb:
        tsq = (bb & -bb).bit_length() - 1
        append((tsq - 2 * pawn_dir) | (tsq << 6))
        bb &= bb - 1

    # ---- Single pushes (promoting) ----
    targets = promo_pawns << 8 & _BALL & empty if us == WHITE else promo_pawns >> 8 & empty
    bb = targets
    while bb:
        tsq = (bb & -bb).bit_length() - 1
        fsq = tsq - pawn_dir
        base = fsq | (tsq << 6) | _FLAG_PROMO
        append(base | _PROMO_Q)
        append(base | _PROMO_R)
        append(base | _PROMO_B)
        append(base | _PROMO_N)
        bb &= bb - 1

    # ---- Captures (non-promoting) ----
    bb = non_promo_pawns
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        atk = patk[fsq] & enemy
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            append(fsq | (tsq << 6))
            atk &= atk - 1
        bb &= bb - 1

    # ---- Captures (promoting) ----
    bb = promo_pawns
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        atk = patk[fsq] & enemy
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            base = fsq | (tsq << 6) | _FLAG_PROMO
            append(base | _PROMO_Q)
            append(base | _PROMO_R)
            append(base | _PROMO_B)
            append(base | _PROMO_N)
            atk &= atk - 1
        bb &= bb - 1

    # ---- En-passant ----
    if board.ep_square != NO_SQUARE:
        ep_sq = board.ep_square
        capturers = _PAWN_ATK[them][ep_sq] & our_pawns
        while capturers:
            fsq = (capturers & -capturers).bit_length() - 1
            append(fsq | (ep_sq << 6) | _FLAG_EP)
            capturers &= capturers - 1


def _gen_piece_moves(board: Board, moves: list[int]) -> None:
    us = board.side
    friendly = board.occupancy[us]
    occ = board.all_occ
    append = moves.append
    pieces = board.pieces[us]
    nf = ~friendly

    # Knights
    bb = pieces[KNIGHT]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        targets = _KNIGHT_ATK[fsq] & nf
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # Bishops
    bb = pieces[BISHOP]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        o = occ & _BM[fsq]
        targets = _BT[fsq][((o * _BMAG[fsq]) & _BALL) >> _BSHIFT[fsq]] & nf
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # Rooks
    bb = pieces[ROOK]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        o = occ & _RM[fsq]
        targets = _RT[fsq][((o * _RMAG[fsq]) & _BALL) >> _RSHIFT[fsq]] & nf
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # Queens
    bb = pieces[QUEEN]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        o_r = occ & _RM[fsq]
        o_b = occ & _BM[fsq]
        targets = (
            _RT[fsq][((o_r * _RMAG[fsq]) & _BALL) >> _RSHIFT[fsq]]
            | _BT[fsq][((o_b * _BMAG[fsq]) & _BALL) >> _BSHIFT[fsq]]
        ) & nf
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # King (non-castling)
    ksq = board._king_sqs[us]
    targets = _KING_ATK[ksq] & nf
    while targets:
        tsq = (targets & -targets).bit_length() - 1
        append(ksq | (tsq << 6))
        targets &= targets - 1


def _gen_castling_moves(board: Board, moves: list[int]) -> None:
    us = board.side
    them = 1 - us
    occ = board.all_occ
    tp = board.pieces[them]
    tp0, tp1, tp2, tp3, tp4, tp5 = tp[0], tp[1], tp[2], tp[3], tp[4], tp[5]
    pawn_atk_us = _PAWN_ATK[us]

    if us == WHITE:
        if (
            board.castling & WK_CASTLE
            and not (occ & (_BB[F1] | _BB[G1]))
            and (
                not _sq_attacked(E1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(F1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(G1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
            )
        ):
            moves.append(E1 | (G1 << 6) | _FLAG_CASTLE)
        if (
            board.castling & WQ_CASTLE
            and not (occ & (_BB[D1] | _BB[C1] | _BB[B1]))
            and (
                not _sq_attacked(E1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(D1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(C1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
            )
        ):
            moves.append(E1 | (C1 << 6) | _FLAG_CASTLE)
    else:
        if (
            board.castling & BK_CASTLE
            and not (occ & (_BB[F8] | _BB[G8]))
            and (
                not _sq_attacked(E8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(F8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(G8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
            )
        ):
            moves.append(E8 | (G8 << 6) | _FLAG_CASTLE)
        if (
            board.castling & BQ_CASTLE
            and not (occ & (_BB[D8] | _BB[C8] | _BB[B8]))
            and (
                not _sq_attacked(E8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(D8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
                and not _sq_attacked(C8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, occ)
            )
        ):
            moves.append(E8 | (C8 << 6) | _FLAG_CASTLE)


# ---------------------------------------------------------------------------
# Capture-only pseudo-legal generation (for quiescence search)
# ---------------------------------------------------------------------------


def _gen_pawn_captures(board: Board, moves: list[int]) -> None:
    """Generate pawn captures and promotions (captures + push-promotions)."""
    us = board.side
    them = 1 - us
    our_pawns = board.pieces[us][PAWN]
    enemy = board.occupancy[them]
    empty = ~board.all_occ & _BALL

    if us == WHITE:
        promo_rank = BB_RANK_7
        pawn_dir = 8
    else:
        promo_rank = BB_RANK_2
        pawn_dir = -8

    promo_pawns = our_pawns & promo_rank
    non_promo_pawns = our_pawns & ~promo_rank

    append = moves.append
    patk = _PAWN_ATK[us]

    # Captures (non-promoting)
    bb = non_promo_pawns
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        atk = patk[fsq] & enemy
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            append(fsq | (tsq << 6))
            atk &= atk - 1
        bb &= bb - 1

    # Captures (promoting)
    bb = promo_pawns
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        atk = patk[fsq] & enemy
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            base = fsq | (tsq << 6) | _FLAG_PROMO
            append(base | _PROMO_Q)
            append(base | _PROMO_R)
            append(base | _PROMO_B)
            append(base | _PROMO_N)
            atk &= atk - 1
        bb &= bb - 1

    # Push-promotions (non-capture but critical for quiescence)
    if promo_pawns:
        targets = promo_pawns << 8 & _BALL & empty if us == WHITE else promo_pawns >> 8 & empty
        bb = targets
        while bb:
            tsq = (bb & -bb).bit_length() - 1
            fsq = tsq - pawn_dir
            base = fsq | (tsq << 6) | _FLAG_PROMO
            append(base | _PROMO_Q)
            append(base | _PROMO_R)
            append(base | _PROMO_B)
            append(base | _PROMO_N)
            bb &= bb - 1

    # En-passant
    if board.ep_square != NO_SQUARE:
        ep_sq = board.ep_square
        capturers = _PAWN_ATK[them][ep_sq] & our_pawns
        while capturers:
            fsq = (capturers & -capturers).bit_length() - 1
            append(fsq | (ep_sq << 6) | _FLAG_EP)
            capturers &= capturers - 1


def _gen_piece_captures(board: Board, moves: list[int]) -> None:
    """Generate piece captures only (no quiet moves)."""
    us = board.side
    enemy = board.occupancy[1 - us]
    occ = board.all_occ
    append = moves.append
    pieces = board.pieces[us]

    # Knights
    bb = pieces[KNIGHT]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        targets = _KNIGHT_ATK[fsq] & enemy
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # Bishops
    bb = pieces[BISHOP]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        o = occ & _BM[fsq]
        targets = _BT[fsq][((o * _BMAG[fsq]) & _BALL) >> _BSHIFT[fsq]] & enemy
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # Rooks
    bb = pieces[ROOK]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        o = occ & _RM[fsq]
        targets = _RT[fsq][((o * _RMAG[fsq]) & _BALL) >> _RSHIFT[fsq]] & enemy
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # Queens
    bb = pieces[QUEEN]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        o_r = occ & _RM[fsq]
        o_b = occ & _BM[fsq]
        targets = (
            _RT[fsq][((o_r * _RMAG[fsq]) & _BALL) >> _RSHIFT[fsq]]
            | _BT[fsq][((o_b * _BMAG[fsq]) & _BALL) >> _BSHIFT[fsq]]
        ) & enemy
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            append(fsq | (tsq << 6))
            targets &= targets - 1
        bb &= bb - 1

    # King captures
    ksq = board._king_sqs[us]
    targets = _KING_ATK[ksq] & enemy
    while targets:
        tsq = (targets & -targets).bit_length() - 1
        append(ksq | (tsq << 6))
        targets &= targets - 1


def generate_pseudo_legal_moves(board: Board) -> list[int]:
    moves: list[int] = []
    _gen_pawn_moves(board, moves)
    _gen_piece_moves(board, moves)
    _gen_castling_moves(board, moves)
    return moves


# ---------------------------------------------------------------------------
# Inline legality check (no make/unmake)
# ---------------------------------------------------------------------------


def _is_legal_move(
    move: int,
    us: int,
    them: int,
    all_occ: int,
    king_sq: int,
    mailbox: list[int],
    them_pieces: list[int],
    _BB: list[int],
) -> bool:
    fsq = move & 0x3F
    tsq = (move >> 6) & 0x3F
    flag = (move >> 14) & 0x3

    if flag == 3:  # FLAG_CASTLING — already verified during generation
        return True

    source_bit = _BB[fsq]
    target_bit = _BB[tsq]
    occupied = (all_occ & ~source_bit) | target_bit

    captured_bit = 0
    if flag == 2:  # FLAG_EN_PASSANT
        cap_sq = tsq + (-8 if us == 0 else 8)
        captured_bit = _BB[cap_sq]
        occupied &= ~captured_bit
    elif mailbox[tsq] != 6:  # not NO_PIECE_TYPE
        captured_bit = target_bit

    king = tsq if mailbox[fsq] == 5 else king_sq  # KING == 5

    tp = them_pieces
    if tp[1] & ~captured_bit & _KNIGHT_ATK[king]:
        return False
    if tp[0] & ~captured_bit & _PAWN_ATK[us][king]:
        return False
    if tp[5] & _KING_ATK[king]:
        return False
    bq = (tp[2] | tp[4]) & ~captured_bit
    if bq:
        o = occupied & _BM[king]
        if _BT[king][((o * _BMAG[king]) & _BALL) >> _BSHIFT[king]] & bq:
            return False
    rq = (tp[3] | tp[4]) & ~captured_bit
    if rq:
        o = occupied & _RM[king]
        if _RT[king][((o * _RMAG[king]) & _BALL) >> _RSHIFT[king]] & rq:
            return False
    return True


# ---------------------------------------------------------------------------
# Legal move generation with check evasion
# ---------------------------------------------------------------------------


def generate_legal_moves(board: Board) -> list[int]:
    """Generate all legal moves. Uses evasion generator when in check."""
    us = board.side
    them = 1 - us
    all_occ = board.all_occ
    king_sq = board._king_sqs[us]
    mailbox = board.mailbox
    tp = board.pieces[them]
    bb_squares = _BB
    ball = _BALL

    # --- Inline _checkers ---
    checkers = _PAWN_ATK[us][king_sq] & tp[0]
    checkers |= _KNIGHT_ATK[king_sq] & tp[1]
    o = all_occ & _BM[king_sq]
    checkers |= _BT[king_sq][((o * _BMAG[king_sq]) & ball) >> _BSHIFT[king_sq]] & (tp[2] | tp[4])
    o = all_occ & _RM[king_sq]
    checkers |= _RT[king_sq][((o * _RMAG[king_sq]) & ball) >> _RSHIFT[king_sq]] & (tp[3] | tp[4])

    if checkers:
        # --- In check: evasion generation (kept as-is, ~1% of calls) ---
        them_pieces = tp
        legal: list[int] = []
        nf = ~board.occupancy[us]

        # King moves are always candidates in check
        targets = _KING_ATK[king_sq] & nf
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            m = king_sq | (tsq << 6)
            if _is_legal_move(m, us, them, all_occ, king_sq, mailbox, them_pieces, bb_squares):
                legal.append(m)
            targets &= targets - 1

        # Double check: only king moves are legal
        if checkers & (checkers - 1):
            return legal

        # Single check: can also capture the checker or block the ray
        checker_sq = (checkers & -checkers).bit_length() - 1
        checker_bit = bb_squares[checker_sq]
        block_mask = _BETWEEN[king_sq][checker_sq] | checker_bit

        moves_all: list[int] = []
        _gen_pawn_moves(board, moves_all)
        pieces_us = board.pieces[us]
        occ = board.all_occ

        p_bb = pieces_us[KNIGHT]
        while p_bb:
            fsq = (p_bb & -p_bb).bit_length() - 1
            t = _KNIGHT_ATK[fsq] & nf & block_mask
            while t:
                tsq = (t & -t).bit_length() - 1
                moves_all.append(fsq | (tsq << 6))
                t &= t - 1
            p_bb &= p_bb - 1

        p_bb = pieces_us[BISHOP]
        while p_bb:
            fsq = (p_bb & -p_bb).bit_length() - 1
            o = occ & _BM[fsq]
            t = _BT[fsq][((o * _BMAG[fsq]) & _BALL) >> _BSHIFT[fsq]] & nf & block_mask
            while t:
                tsq = (t & -t).bit_length() - 1
                moves_all.append(fsq | (tsq << 6))
                t &= t - 1
            p_bb &= p_bb - 1

        p_bb = pieces_us[ROOK]
        while p_bb:
            fsq = (p_bb & -p_bb).bit_length() - 1
            o = occ & _RM[fsq]
            t = _RT[fsq][((o * _RMAG[fsq]) & _BALL) >> _RSHIFT[fsq]] & nf & block_mask
            while t:
                tsq = (t & -t).bit_length() - 1
                moves_all.append(fsq | (tsq << 6))
                t &= t - 1
            p_bb &= p_bb - 1

        p_bb = pieces_us[QUEEN]
        while p_bb:
            fsq = (p_bb & -p_bb).bit_length() - 1
            o_r = occ & _RM[fsq]
            o_b = occ & _BM[fsq]
            t = (
                (
                    _RT[fsq][((o_r * _RMAG[fsq]) & _BALL) >> _RSHIFT[fsq]]
                    | _BT[fsq][((o_b * _BMAG[fsq]) & _BALL) >> _BSHIFT[fsq]]
                )
                & nf
                & block_mask
            )
            while t:
                tsq = (t & -t).bit_length() - 1
                moves_all.append(fsq | (tsq << 6))
                t &= t - 1
            p_bb &= p_bb - 1

        for m in moves_all:
            tsq = (m >> 6) & 0x3F
            if not (bb_squares[tsq] & block_mask):
                flag = (m >> 14) & 0x3
                if flag == 2:
                    ep_cap_sq = tsq + (-8 if us == 0 else 8)
                    if bb_squares[ep_cap_sq] != checker_bit:
                        continue
                elif flag == 1:
                    pass
                else:
                    continue
            if _is_legal_move(m, us, them, all_occ, king_sq, mailbox, them_pieces, bb_squares):
                legal.append(m)

        return legal

    # ===================================================================
    # NOT IN CHECK — fully inlined generation + legality in one pass
    # ===================================================================
    moves = [0] * 220
    n = 0

    # Precompute slider attack tables for king_sq (constant for non-king moves)
    bq = tp[2] | tp[4]  # enemy bishops + queens
    rq = tp[3] | tp[4]  # enemy rooks + queens
    bm_king = _BM[king_sq]
    rm_king = _RM[king_sq]
    bmag_king = _BMAG[king_sq]
    rmag_king = _RMAG[king_sq]
    bshift_king = _BSHIFT[king_sq]
    rshift_king = _RSHIFT[king_sq]
    bt_king = _BT[king_sq]
    rt_king = _RT[king_sq]

    pieces_us = board.pieces[us]
    our_pawns = pieces_us[0]
    enemy = board.occupancy[them]
    our_occ = board.occupancy[us]
    nf = ~our_occ
    empty = ~all_occ & ball

    # --- Compute pinned pieces mask and pin rays ---
    # pin_rays[sq] = all squares a pinned piece at sq may legally move to
    # (the squares between the king and the sniper, plus the sniper itself).
    pinned = 0
    pin_rays: dict[int, int] = {}
    # Diagonal pins (bishops + queens)
    b_empty = bt_king[0]  # bishop attacks from king on empty board (key=0)
    snipers = b_empty & bq
    while snipers:
        sniper_sq = (snipers & -snipers).bit_length() - 1
        snipers &= snipers - 1
        between = _BETWEEN[king_sq][sniper_sq]
        blockers = between & all_occ
        if blockers and not (blockers & (blockers - 1)):
            pinned_bb = blockers & our_occ
            if pinned_bb:
                pinned |= pinned_bb
                psq = (pinned_bb & -pinned_bb).bit_length() - 1
                pin_rays[psq] = between | bb_squares[sniper_sq]
    # Straight pins (rooks + queens)
    r_empty = rt_king[0]  # rook attacks from king on empty board (key=0)
    snipers = r_empty & rq
    while snipers:
        sniper_sq = (snipers & -snipers).bit_length() - 1
        snipers &= snipers - 1
        between = _BETWEEN[king_sq][sniper_sq]
        blockers = between & all_occ
        if blockers and not (blockers & (blockers - 1)):
            pinned_bb = blockers & our_occ
            if pinned_bb:
                pinned |= pinned_bb
                psq = (pinned_bb & -pinned_bb).bit_length() - 1
                pin_rays[psq] = between | bb_squares[sniper_sq]
    if us == WHITE:
        promo_rank = BB_RANK_7
        pawn_dir = 8
    else:
        promo_rank = BB_RANK_2
        pawn_dir = -8

    promo_pawns = our_pawns & promo_rank
    non_promo_pawns = our_pawns & ~promo_rank
    patk = _PAWN_ATK[us]

    # ---- Single pushes (non-promoting) ----
    targets = non_promo_pawns << 8 & ball & empty if us == WHITE else non_promo_pawns >> 8 & empty
    bb = targets
    while bb:
        tsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        fsq = tsq - pawn_dir
        source_bit = bb_squares[fsq]
        if (source_bit & pinned) and not (bb_squares[tsq] & pin_rays[fsq]):
            continue
        moves[n] = fsq | (tsq << 6)
        n += 1

    # ---- Double pushes ----
    if us == WHITE:
        push2 = ((((our_pawns & BB_RANK_2) << 8) & ball & empty) << 8) & ball & empty
    else:
        push2 = ((((our_pawns & BB_RANK_7) >> 8) & empty) >> 8) & empty
    bb = push2
    while bb:
        tsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        fsq = tsq - 2 * pawn_dir
        source_bit = bb_squares[fsq]
        if (source_bit & pinned) and not (bb_squares[tsq] & pin_rays[fsq]):
            continue
        moves[n] = fsq | (tsq << 6)
        n += 1

    # ---- Promotions (push, non-capture) ----
    if promo_pawns:
        targets = promo_pawns << 8 & ball & empty if us == WHITE else promo_pawns >> 8 & empty
        bb = targets
        while bb:
            tsq = (bb & -bb).bit_length() - 1
            bb &= bb - 1
            fsq = tsq - pawn_dir
            source_bit = bb_squares[fsq]
            if (source_bit & pinned) and not (bb_squares[tsq] & pin_rays[fsq]):
                continue
            base = fsq | (tsq << 6) | _FLAG_PROMO
            moves[n] = base | _PROMO_Q
            n += 1
            moves[n] = base | _PROMO_R
            n += 1
            moves[n] = base | _PROMO_B
            n += 1
            moves[n] = base | _PROMO_N
            n += 1

    # ---- Pawn captures (non-promoting) ----
    bb = non_promo_pawns
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        source_bit = bb_squares[fsq]
        atk = patk[fsq] & enemy
        if source_bit & pinned:
            atk &= pin_rays[fsq]
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            atk &= atk - 1
            moves[n] = fsq | (tsq << 6)
            n += 1

    # ---- Pawn captures (promoting) ----
    bb = promo_pawns
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        source_bit = bb_squares[fsq]
        atk = patk[fsq] & enemy
        if source_bit & pinned:
            atk &= pin_rays[fsq]
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            atk &= atk - 1
            base = fsq | (tsq << 6) | _FLAG_PROMO
            moves[n] = base | _PROMO_Q
            n += 1
            moves[n] = base | _PROMO_R
            n += 1
            moves[n] = base | _PROMO_B
            n += 1
            moves[n] = base | _PROMO_N
            n += 1

    # ---- En-passant ----
    if board.ep_square != NO_SQUARE:
        ep_sq = board.ep_square
        ep_target_bit = bb_squares[ep_sq]
        cap_sq = ep_sq + (-8 if us == 0 else 8)
        ep_captured_bit = bb_squares[cap_sq]
        capturers = _PAWN_ATK[them][ep_sq] & our_pawns
        while capturers:
            fsq = (capturers & -capturers).bit_length() - 1
            capturers &= capturers - 1
            source_bit = bb_squares[fsq]
            occupied = ((all_occ & ~source_bit) | ep_target_bit) & ~ep_captured_bit
            # EP captures a pawn (never in bq/rq), so bq_eff=bq, rq_eff=rq
            if bq:
                o = occupied & bm_king
                if bt_king[((o * bmag_king) & ball) >> bshift_king] & bq:
                    continue
            if rq:
                o = occupied & rm_king
                if rt_king[((o * rmag_king) & ball) >> rshift_king] & rq:
                    continue
            moves[n] = fsq | (ep_sq << 6) | _FLAG_EP
            n += 1

    # --- Piece moves (non-king) ---
    # Knights — pinned knights can never move legally (no knight move stays on a ray)
    bb = pieces_us[1]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        source_bit = bb_squares[fsq]
        if source_bit & pinned:
            continue
        targets = _KNIGHT_ATK[fsq] & nf
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            moves[n] = fsq | (tsq << 6)
            n += 1

    # Bishops
    bb = pieces_us[2]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        source_bit = bb_squares[fsq]
        o_b = all_occ & _BM[fsq]
        targets = _BT[fsq][((o_b * _BMAG[fsq]) & ball) >> _BSHIFT[fsq]] & nf
        if source_bit & pinned:
            targets &= pin_rays[fsq]
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            moves[n] = fsq | (tsq << 6)
            n += 1

    # Rooks
    bb = pieces_us[3]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        source_bit = bb_squares[fsq]
        o_r = all_occ & _RM[fsq]
        targets = _RT[fsq][((o_r * _RMAG[fsq]) & ball) >> _RSHIFT[fsq]] & nf
        if source_bit & pinned:
            targets &= pin_rays[fsq]
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            moves[n] = fsq | (tsq << 6)
            n += 1

    # Queens
    bb = pieces_us[4]
    while bb:
        fsq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        source_bit = bb_squares[fsq]
        o_r = all_occ & _RM[fsq]
        o_b = all_occ & _BM[fsq]
        targets = (
            _RT[fsq][((o_r * _RMAG[fsq]) & ball) >> _RSHIFT[fsq]]
            | _BT[fsq][((o_b * _BMAG[fsq]) & ball) >> _BSHIFT[fsq]]
        ) & nf
        if source_bit & pinned:
            targets &= pin_rays[fsq]
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            moves[n] = fsq | (tsq << 6)
            n += 1

    # --- King moves (non-castling) — full legality check needed ---
    king_bit = bb_squares[king_sq]
    occ_no_king = all_occ & ~king_bit
    tp0 = tp[0]
    tp1 = tp[1]
    tp2 = tp[2]
    tp3 = tp[3]
    tp4 = tp[4]
    tp5 = tp[5]
    pawn_atk_us = _PAWN_ATK[us]
    knight_atk = _KNIGHT_ATK
    king_atk = _KING_ATK

    targets = king_atk[king_sq] & nf
    while targets:
        tsq = (targets & -targets).bit_length() - 1
        targets &= targets - 1
        target_bit = bb_squares[tsq]
        occupied = occ_no_king | target_bit
        captured_bit = target_bit & enemy
        if tp1 & ~captured_bit & knight_atk[tsq]:
            continue
        if tp0 & ~captured_bit & pawn_atk_us[tsq]:
            continue
        if tp5 & king_atk[tsq]:
            continue
        bq_k = (tp2 | tp4) & ~captured_bit
        if bq_k:
            o = occupied & _BM[tsq]
            if _BT[tsq][((o * _BMAG[tsq]) & ball) >> _BSHIFT[tsq]] & bq_k:
                continue
        rq_k = (tp3 | tp4) & ~captured_bit
        if rq_k:
            o = occupied & _RM[tsq]
            if _RT[tsq][((o * _RMAG[tsq]) & ball) >> _RSHIFT[tsq]] & rq_k:
                continue
        moves[n] = king_sq | (tsq << 6)
        n += 1

    # --- Castling (always legal if generation conditions pass) ---
    if us == WHITE:
        if (
            board.castling & WK_CASTLE
            and not (all_occ & (bb_squares[F1] | bb_squares[G1]))
            and not _sq_attacked(E1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(F1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(G1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
        ):
            moves[n] = E1 | (G1 << 6) | _FLAG_CASTLE
            n += 1
        if (
            board.castling & WQ_CASTLE
            and not (all_occ & (bb_squares[D1] | bb_squares[C1] | bb_squares[B1]))
            and not _sq_attacked(E1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(D1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(C1, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
        ):
            moves[n] = E1 | (C1 << 6) | _FLAG_CASTLE
            n += 1
    else:
        if (
            board.castling & BK_CASTLE
            and not (all_occ & (bb_squares[F8] | bb_squares[G8]))
            and not _sq_attacked(E8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(F8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(G8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
        ):
            moves[n] = E8 | (G8 << 6) | _FLAG_CASTLE
            n += 1
        if (
            board.castling & BQ_CASTLE
            and not (all_occ & (bb_squares[D8] | bb_squares[C8] | bb_squares[B8]))
            and not _sq_attacked(E8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(D8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
            and not _sq_attacked(C8, tp0, tp1, tp2, tp3, tp4, tp5, pawn_atk_us, all_occ)
        ):
            moves[n] = E8 | (C8 << 6) | _FLAG_CASTLE
            n += 1

    del moves[n:]
    return moves


def generate_captures(board: Board) -> list[int]:
    """Return legal capture moves (for quiescence search).

    Fully inlined — no helper function calls in the hot path.
    """
    us = board.side
    them = 1 - us
    all_occ = board.all_occ
    king_sq = board._king_sqs[us]
    them_pieces = board.pieces[them]
    pieces_us = board.pieces[us]
    our_occ = board.occupancy[us]
    enemy = board.occupancy[them]
    bb_squares = _BB
    ball = _BALL

    # Precompute king-square slider tables for legality checks
    bm_king = _BM[king_sq]
    rm_king = _RM[king_sq]
    bmag_king = _BMAG[king_sq]
    rmag_king = _RMAG[king_sq]
    bshift_king = _BSHIFT[king_sq]
    rshift_king = _RSHIFT[king_sq]
    bt_king = _BT[king_sq]
    rt_king = _RT[king_sq]

    tp0 = them_pieces[0]
    tp1 = them_pieces[1]
    tp2 = them_pieces[2]
    tp3 = them_pieces[3]
    tp4 = them_pieces[4]
    tp5 = them_pieces[5]
    bq = tp2 | tp4
    rq = tp3 | tp4

    # --- Compute pinned pieces mask and pin rays ---
    pinned = 0
    pin_rays: dict[int, int] = {}
    b_empty = bt_king[0]
    snipers = b_empty & bq
    while snipers:
        sniper_sq = (snipers & -snipers).bit_length() - 1
        snipers &= snipers - 1
        between = _BETWEEN[king_sq][sniper_sq]
        blockers = between & all_occ
        if blockers and not (blockers & (blockers - 1)):
            pinned_bb = blockers & our_occ
            if pinned_bb:
                pinned |= pinned_bb
                psq = (pinned_bb & -pinned_bb).bit_length() - 1
                pin_rays[psq] = between | bb_squares[sniper_sq]
    r_empty = rt_king[0]
    snipers = r_empty & rq
    while snipers:
        sniper_sq = (snipers & -snipers).bit_length() - 1
        snipers &= snipers - 1
        between = _BETWEEN[king_sq][sniper_sq]
        blockers = between & all_occ
        if blockers and not (blockers & (blockers - 1)):
            pinned_bb = blockers & our_occ
            if pinned_bb:
                pinned |= pinned_bb
                psq = (pinned_bb & -pinned_bb).bit_length() - 1
                pin_rays[psq] = between | bb_squares[sniper_sq]

    legal: list[int] = []
    append = legal.append
    our_pawns = pieces_us[0]
    patk = _PAWN_ATK[us]

    if us == WHITE:
        promo_rank = BB_RANK_7
        pawn_dir = 8
    else:
        promo_rank = BB_RANK_2
        pawn_dir = -8

    promo_pawns = our_pawns & promo_rank
    non_promo_pawns = our_pawns & ~promo_rank

    # --- Pawn captures (non-promoting) ---
    pbb = non_promo_pawns
    while pbb:
        fsq = (pbb & -pbb).bit_length() - 1
        pbb &= pbb - 1
        source_bit = bb_squares[fsq]
        atk = patk[fsq] & enemy
        if source_bit & pinned:
            atk &= pin_rays[fsq]
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            atk &= atk - 1
            append(fsq | (tsq << 6))

    # --- Pawn captures (promoting) ---
    pbb = promo_pawns
    while pbb:
        fsq = (pbb & -pbb).bit_length() - 1
        pbb &= pbb - 1
        source_bit = bb_squares[fsq]
        atk = patk[fsq] & enemy
        if source_bit & pinned:
            atk &= pin_rays[fsq]
        while atk:
            tsq = (atk & -atk).bit_length() - 1
            atk &= atk - 1
            base = fsq | (tsq << 6) | _FLAG_PROMO
            append(base | _PROMO_Q)
            append(base | _PROMO_R)
            append(base | _PROMO_B)
            append(base | _PROMO_N)

    # --- Push-promotions (non-capture but critical for quiescence) ---
    if promo_pawns:
        empty = ~all_occ & ball
        targets = promo_pawns << 8 & ball & empty if us == WHITE else promo_pawns >> 8 & empty
        pbb = targets
        while pbb:
            tsq = (pbb & -pbb).bit_length() - 1
            pbb &= pbb - 1
            fsq = tsq - pawn_dir
            source_bit = bb_squares[fsq]
            if (source_bit & pinned) and not (bb_squares[tsq] & pin_rays[fsq]):
                continue
            base = fsq | (tsq << 6) | _FLAG_PROMO
            append(base | _PROMO_Q)
            append(base | _PROMO_R)
            append(base | _PROMO_B)
            append(base | _PROMO_N)

    # --- En-passant (always full check — EP can expose king via captured pawn) ---
    if board.ep_square != NO_SQUARE:
        ep_sq = board.ep_square
        capturers = _PAWN_ATK[them][ep_sq] & our_pawns
        while capturers:
            fsq = (capturers & -capturers).bit_length() - 1
            capturers &= capturers - 1
            source_bit = bb_squares[fsq]
            target_bit = bb_squares[ep_sq]
            cap_sq = ep_sq + (-8 if us == 0 else 8)
            captured_bit = bb_squares[cap_sq]
            occupied = (all_occ & ~source_bit & ~captured_bit) | target_bit
            is_legal = True
            bq_eff = bq & ~captured_bit
            rq_eff = rq & ~captured_bit
            if bq_eff:
                o = occupied & bm_king
                if bt_king[((o * bmag_king) & ball) >> bshift_king] & bq_eff:
                    is_legal = False
            if is_legal and rq_eff:
                o = occupied & rm_king
                if rt_king[((o * rmag_king) & ball) >> rshift_king] & rq_eff:
                    is_legal = False
            if is_legal:
                append(fsq | (ep_sq << 6) | _FLAG_EP)

    # --- Knight captures ---
    pbb = pieces_us[1]
    while pbb:
        fsq = (pbb & -pbb).bit_length() - 1
        pbb &= pbb - 1
        source_bit = bb_squares[fsq]
        if source_bit & pinned:
            continue
        targets = _KNIGHT_ATK[fsq] & enemy
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            append(fsq | (tsq << 6))

    # --- Bishop captures ---
    pbb = pieces_us[2]
    while pbb:
        fsq = (pbb & -pbb).bit_length() - 1
        pbb &= pbb - 1
        source_bit = bb_squares[fsq]
        if not (_BRAY[fsq] & enemy):
            continue
        o_b = all_occ & _BM[fsq]
        targets = _BT[fsq][((o_b * _BMAG[fsq]) & ball) >> _BSHIFT[fsq]] & enemy
        if source_bit & pinned:
            targets &= pin_rays[fsq]
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            append(fsq | (tsq << 6))

    # --- Rook captures ---
    pbb = pieces_us[3]
    while pbb:
        fsq = (pbb & -pbb).bit_length() - 1
        pbb &= pbb - 1
        source_bit = bb_squares[fsq]
        if not (_RRAY[fsq] & enemy):
            continue
        o_r = all_occ & _RM[fsq]
        targets = _RT[fsq][((o_r * _RMAG[fsq]) & ball) >> _RSHIFT[fsq]] & enemy
        if source_bit & pinned:
            targets &= pin_rays[fsq]
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            append(fsq | (tsq << 6))

    # --- Queen captures ---
    pbb = pieces_us[4]
    while pbb:
        fsq = (pbb & -pbb).bit_length() - 1
        pbb &= pbb - 1
        source_bit = bb_squares[fsq]
        if not ((_BRAY[fsq] | _RRAY[fsq]) & enemy):
            continue
        o_r = all_occ & _RM[fsq]
        o_b = all_occ & _BM[fsq]
        targets = (
            _RT[fsq][((o_r * _RMAG[fsq]) & ball) >> _RSHIFT[fsq]]
            | _BT[fsq][((o_b * _BMAG[fsq]) & ball) >> _BSHIFT[fsq]]
        ) & enemy
        if source_bit & pinned:
            targets &= pin_rays[fsq]
        while targets:
            tsq = (targets & -targets).bit_length() - 1
            targets &= targets - 1
            append(fsq | (tsq << 6))

    # --- King captures (full attack check needed) ---
    ksq = king_sq
    targets = _KING_ATK[ksq] & enemy
    while targets:
        tsq = (targets & -targets).bit_length() - 1
        targets &= targets - 1
        source_bit = bb_squares[ksq]
        target_bit = bb_squares[tsq]
        occupied = (all_occ & ~source_bit) | target_bit
        cb = target_bit
        if tp1 & ~cb & _KNIGHT_ATK[tsq]:
            continue
        if tp0 & ~cb & _PAWN_ATK[us][tsq]:
            continue
        if tp5 & _KING_ATK[tsq]:
            continue
        bq_eff = (tp2 | tp4) & ~cb
        if bq_eff:
            o = occupied & _BM[tsq]
            if _BT[tsq][((o * _BMAG[tsq]) & ball) >> _BSHIFT[tsq]] & bq_eff:
                continue
        rq_eff = (tp3 | tp4) & ~cb
        if rq_eff:
            o = occupied & _RM[tsq]
            if _RT[tsq][((o * _RMAG[tsq]) & ball) >> _RSHIFT[tsq]] & rq_eff:
                continue
        append(ksq | (tsq << 6))

    return legal


# ---------------------------------------------------------------------------
# Perft — node count for validation
# ---------------------------------------------------------------------------


def perft(board: Board, depth: int) -> int:
    """Count leaf nodes at *depth* plies.  Used to validate move generation."""
    if depth == 0:
        return 1
    if depth == 1:
        return len(generate_legal_moves(board))

    nodes = 0
    for move in generate_legal_moves(board):
        board.make_move(move)
        nodes += perft(board, depth - 1)
        board.unmake_move(move)
    return nodes


def divide(board: Board, depth: int) -> dict[str, int]:
    """Perft with per-move breakdown (useful for debugging)."""
    result: dict[str, int] = {}
    for move in generate_legal_moves(board):
        board.make_move(move)
        nodes = perft(board, depth - 1)
        board.unmake_move(move)
        result[move_to_uci(move)] = nodes
    return result


# ===== hydra/evaluation.py =====
"""Classical hand-crafted evaluation framework."""




# ---------------------------------------------------------------------------
# Magic bitboard helpers (mirrored from engine for sliding-piece mobility
# and king-safety attack counting)
# ---------------------------------------------------------------------------

_RM = _rook_masks
_BM = _bishop_masks
_RT = _rook_table
_BT = _bishop_table
_RMAG = ROOK_MAGICS
_BMAG = BISHOP_MAGICS
_RSHIFT = ROOK_SHIFTS
_BSHIFT = BISHOP_SHIFTS
_BALL = BB_ALL


def _rook_atk(sq: int, occ: int) -> int:
    o = occ & _RM[sq]
    return _RT[sq][((o * _RMAG[sq]) & _BALL) >> _RSHIFT[sq]]


def _bishop_atk(sq: int, occ: int) -> int:
    o = occ & _BM[sq]
    return _BT[sq][((o * _BMAG[sq]) & _BALL) >> _BSHIFT[sq]]


# ---------------------------------------------------------------------------
# Evaluator protocol
# ---------------------------------------------------------------------------


class Evaluator(Protocol):
    """Protocol that every evaluation backend must satisfy."""

    def evaluate(self, board: Board) -> int:
        """Return static evaluation in centipawns from side-to-move's POV."""
        ...

    def invalidate_caches(self) -> None:
        """Clear internal caches (called on ucinewgame or evaluator reset)."""
        ...


# ---------------------------------------------------------------------------
# Piece values  (middlegame / endgame)
# ---------------------------------------------------------------------------

_MG_VAL = (100, 320, 330, 500, 900, 0)  # P N B R Q K
_EG_VAL = (120, 300, 320, 520, 950, 0)

# ---------------------------------------------------------------------------
# Piece-square tables  (LERF: a1 = 0 … h8 = 63, White's perspective)
# ---------------------------------------------------------------------------

# fmt: off
_PAWN_PST = (
      0, 0, 0, 0, 0, 0, 0, 0,
      5, 10, 10, -20, -20, 10, 10, 5,
      5, -5, -10, 0, 0, -10, -5, 5,
      0, 0, 0, 20, 20, 0, 0, 0,
      5, 5, 10, 25, 25, 10, 5, 5,
     10, 10, 20, 30, 30, 20, 10, 10,
     50, 50, 50, 50, 50, 50, 50, 50,
      0, 0, 0, 0, 0, 0, 0, 0,
)
_KNIGHT_PST = (
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
)
_BISHOP_PST = (
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
)
_ROOK_PST = (
      0, 0, 0, 5, 5, 0, 0, 0,
     -5, 0, 0, 0, 0, 0, 0, -5,
     -5, 0, 0, 0, 0, 0, 0, -5,
     -5, 0, 0, 0, 0, 0, 0, -5,
     -5, 0, 0, 0, 0, 0, 0, -5,
     -5, 0, 0, 0, 0, 0, 0, -5,
      5, 10, 10, 10, 10, 10, 10, 5,
      0, 0, 0, 0, 0, 0, 0, 0,
)
_QUEEN_PST = (
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
      0, 0, 5, 5, 5, 5, 0, -5,
     -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
)
_KING_MG_PST = (
     20, 30, 10, 0, 0, 10, 30, 20,
     20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
)
_KING_EG_PST = (
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -50, -40, -30, -20, -20, -30, -40, -50,
)
# fmt: on

_MG_PST = (_PAWN_PST, _KNIGHT_PST, _BISHOP_PST, _ROOK_PST, _QUEEN_PST, _KING_MG_PST)
_EG_PST = (_PAWN_PST, _KNIGHT_PST, _BISHOP_PST, _ROOK_PST, _QUEEN_PST, _KING_EG_PST)


_MG_W: tuple[int, ...] = tuple(_MG_VAL[pt] + _MG_PST[pt][sq] for pt in range(6) for sq in range(64))
_MG_B: tuple[int, ...] = tuple(
    _MG_VAL[pt] + _MG_PST[pt][sq ^ 56] for pt in range(6) for sq in range(64)
)
_EG_W: tuple[int, ...] = tuple(_EG_VAL[pt] + _EG_PST[pt][sq] for pt in range(6) for sq in range(64))
_EG_B: tuple[int, ...] = tuple(
    _EG_VAL[pt] + _EG_PST[pt][sq ^ 56] for pt in range(6) for sq in range(64)
)

# ---------------------------------------------------------------------------
# Evaluation bonuses / penalties
# ---------------------------------------------------------------------------

_BISHOP_PAIR_MG = 30
_BISHOP_PAIR_EG = 50

_DOUBLED_MG = -10
_DOUBLED_EG = -20
_ISOLATED_MG = -15
_ISOLATED_EG = -20

# Passed-pawn bonus indexed by rank (0 = rank 1, 7 = rank 8)
_PASSED_MG = (0, 5, 10, 20, 35, 60, 100, 0)
_PASSED_EG = (0, 10, 20, 40, 70, 120, 200, 0)

_ROOK_OPEN_MG = 25
_ROOK_OPEN_EG = 15
_ROOK_SEMI_MG = 15
_ROOK_SEMI_EG = 10
_ROOK_7TH_MG = 20
_ROOK_7TH_EG = 30

_TEMPO = 10

_PAWN_SHIELD = 10  # per shield pawn, MG only

_TOTAL_PHASE = 24

# Pawn structure
_CONNECTED_MG = 8
_CONNECTED_EG = 12
_BACKWARD_MG = -10
_BACKWARD_EG = -8

# Knight outpost bonus (enemy half, square not attackable by enemy pawn)
_OUTPOST_MG = 25
_OUTPOST_EG = 15

# Pawn threat: our pawn attacks an enemy non-pawn
_PAWN_THREAT_MG = 20
_PAWN_THREAT_EG = 10

# Rook behind passed pawn (same file, rook is behind the passer)
_ROOK_BEHIND_PASSED_MG = 5
_ROOK_BEHIND_PASSED_EG = 20

# Endgame king centralization bonus (per unit of 7 - center_dist, EG only)
_EG_KING_CENTER = 5

# Mobility bonus tables per piece type (indexed by safe-square mobility count)
# "Safe" = not attacked by an enemy pawn
_KNIGHT_MOB_MG = (-20, -10, -5, 0, 5, 8, 10, 12, 12)
_KNIGHT_MOB_EG = (-30, -15, -5, 0, 5, 10, 13, 15, 15)
_BISHOP_MOB_MG = (-15, -10, -5, 0, 3, 5, 7, 9, 10, 10, 10, 10, 10, 10)
_BISHOP_MOB_EG = (-20, -12, -5, 0, 5, 9, 12, 14, 15, 16, 16, 16, 16, 16)
_ROOK_MOB_MG = (-12, -8, -4, 0, 2, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5)
_ROOK_MOB_EG = (-18, -12, -6, 0, 4, 8, 12, 15, 17, 18, 19, 20, 20, 20, 20)
_QUEEN_MOB_MG = (
    -10,
    -8,
    -5,
    -2,
    0,
    2,
    3,
    4,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
)
_QUEEN_MOB_EG = (
    -15,
    -10,
    -5,
    0,
    2,
    4,
    6,
    8,
    10,
    12,
    13,
    14,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
    15,
)

# King safety: attack-unit weights per piece type [P, N, B, R, Q, K]
_ATK_WEIGHT = (0, 2, 2, 3, 5, 0)
# MG penalty table indexed by total attack units (quadratic growth, capped at 99)
_KING_SAFETY: tuple[int, ...] = tuple(min(500, i * i // 4 + i * 3) for i in range(100))

# ---------------------------------------------------------------------------
# Precomputed masks
# ---------------------------------------------------------------------------

_FILE_BB: tuple[int, ...] = tuple(0x0101_0101_0101_0101 << f for f in range(8))

_ADJ_FILE_BB: tuple[int, ...] = tuple(
    (_FILE_BB[f - 1] if f > 0 else 0) | (_FILE_BB[f + 1] if f < 7 else 0) for f in range(8)
)

_FILE_A_BB = _FILE_BB[0]
_FILE_H_BB = _FILE_BB[7]

# Passed-pawn sentinel: squares that, if occupied by enemy pawns, prevent
# the pawn from being passed.
_PASSED_W: tuple[int, ...] = tuple(
    sum(
        1 << (rank * 8 + file)
        for file in range(max(0, (sq & 7) - 1), min(8, (sq & 7) + 2))
        for rank in range((sq >> 3) + 1, 8)
    )
    for sq in range(64)
)
_PASSED_B: tuple[int, ...] = tuple(
    sum(
        1 << (rank * 8 + file)
        for file in range(max(0, (sq & 7) - 1), min(8, (sq & 7) + 2))
        for rank in range(sq >> 3)
    )
    for sq in range(64)
)

# Cumulative rank masks: all squares at ranks 0..r (inclusive)
_RANKS_UP_TO: tuple[int, ...] = tuple(
    sum(0xFF << (8 * r2) for r2 in range(r + 1)) for r in range(8)
)

# Connected-pawn masks: squares where a friendly pawn would make the pawn
# at sq "connected" (side-by-side or defended from behind).
_PAWN_CONNECTED_W: tuple[int, ...] = tuple(
    (
        ((1 << (sq - 1)) if (sq & 7) > 0 else 0)  # left same rank
        | ((1 << (sq + 1)) if (sq & 7) < 7 else 0)  # right same rank
        | ((1 << (sq - 9)) if (sq & 7) > 0 and sq >= 9 else 0)  # below-left
        | ((1 << (sq - 7)) if (sq & 7) < 7 and sq >= 7 else 0)  # below-right
    )
    for sq in range(64)
)
_PAWN_CONNECTED_B: tuple[int, ...] = tuple(
    (
        ((1 << (sq - 1)) if (sq & 7) > 0 else 0)
        | ((1 << (sq + 1)) if (sq & 7) < 7 else 0)
        | ((1 << (sq + 7)) if (sq & 7) > 0 and sq + 7 < 64 else 0)  # above-left
        | ((1 << (sq + 9)) if (sq & 7) < 7 and sq + 9 < 64 else 0)  # above-right
    )
    for sq in range(64)
)

# Backward pawn support: adjacent-file squares at ranks <= rank(sq) for white
# (if occupied by a friendly pawn they provide chain support).
_BACKWARD_SUPPORT_W: tuple[int, ...] = tuple(
    _ADJ_FILE_BB[sq & 7] & _RANKS_UP_TO[sq >> 3] for sq in range(64)
)
# For black: adjacent-file squares at ranks >= rank(sq)
_BACKWARD_SUPPORT_B: tuple[int, ...] = tuple(
    _ADJ_FILE_BB[sq & 7]
    & ~(_RANKS_UP_TO[max(0, (sq >> 3) - 1)] if (sq >> 3) > 0 else 0)
    & 0xFFFF_FFFF_FFFF_FFFF
    for sq in range(64)
)

# Outpost squares: enemy half of the board
_OUTPOST_MASK_W = 0xFFFF_FFFF_0000_0000  # ranks 4-7 for white knights
_OUTPOST_MASK_B = 0x0000_0000_FFFF_FFFF  # ranks 0-3 for black knights


# King safety zones: king square + king attacks + one rank forward
def _make_king_zone(sq: int, fwd: int) -> int:
    mask = KING_ATTACKS[sq] | (1 << sq)
    r = sq >> 3
    f = sq & 7
    nr = r + fwd
    if 0 <= nr < 8:
        for df in range(max(0, f - 1), min(8, f + 2)):
            mask |= 1 << (nr * 8 + df)
    return mask


_KING_ZONE_W: tuple[int, ...] = tuple(_make_king_zone(sq, 1) for sq in range(64))
_KING_ZONE_B: tuple[int, ...] = tuple(_make_king_zone(sq, -1) for sq in range(64))


def _make_shield(sq: int, direction: int) -> int:
    """Pawn-shield mask: 2 ranks in *direction*, 3 files wide around *sq*."""
    f, mask = sq & 7, 0
    for df in range(max(0, f - 1), min(8, f + 2)):
        for step in (1, 2):
            r = (sq >> 3) + direction * step
            if 0 <= r < 8:
                mask |= 1 << (r * 8 + df)
    return mask


_SHIELD_W: tuple[int, ...] = tuple(_make_shield(sq, 1) for sq in range(64))
_SHIELD_B: tuple[int, ...] = tuple(_make_shield(sq, -1) for sq in range(64))

# Local aliases for attack tables
_PAWN_ATK = PAWN_ATTACKS
_NATT = KNIGHT_ATTACKS

# Pawn-hash multiplier for the structure cache key
_PAWN_HASH_MUL = 0x9E3779B97F4A7C15


def _eval_pawns(w_pawns: int, b_pawns: int) -> tuple[int, int, int, int]:
    """Evaluate pawn structure; returns ``(mg, eg, passed_w_bb, passed_b_bb)``.

    Covers: doubled, isolated, connected, backward, and passed pawns.
    Results are cached by the caller via the pawn hash.
    """
    mg = eg = passed_w = passed_b = 0

    # Doubled and isolated penalties (file loop is faster for these)
    for f in range(8):
        fbb = _FILE_BB[f]
        adj = _ADJ_FILE_BB[f]
        wc = (w_pawns & fbb).bit_count()
        bc = (b_pawns & fbb).bit_count()
        if wc > 1:
            d = wc - 1
            mg += d * _DOUBLED_MG
            eg += d * _DOUBLED_EG
        if bc > 1:
            d = bc - 1
            mg -= d * _DOUBLED_MG
            eg -= d * _DOUBLED_EG
        if wc and not (w_pawns & adj):
            mg += wc * _ISOLATED_MG
            eg += wc * _ISOLATED_EG
        if bc and not (b_pawns & adj):
            mg -= bc * _ISOLATED_MG
            eg -= bc * _ISOLATED_EG

    # Per-pawn features: passed, connected, backward
    bb = w_pawns
    while bb:
        sq = (bb & -bb).bit_length() - 1
        if not (b_pawns & _PASSED_W[sq]):
            r = sq >> 3
            mg += _PASSED_MG[r]
            eg += _PASSED_EG[r]
            passed_w |= 1 << sq
        if w_pawns & _PAWN_CONNECTED_W[sq]:
            mg += _CONNECTED_MG
            eg += _CONNECTED_EG
        stop = sq + 8
        if (
            stop < 64
            and (b_pawns & _PAWN_ATK[0][stop])  # enemy pawn controls our stop sq
            and not (w_pawns & _BACKWARD_SUPPORT_W[sq])
        ):
            mg += _BACKWARD_MG
            eg += _BACKWARD_EG
        bb &= bb - 1

    bb = b_pawns
    while bb:
        sq = (bb & -bb).bit_length() - 1
        if not (w_pawns & _PASSED_B[sq]):
            r = 7 - (sq >> 3)
            mg -= _PASSED_MG[r]
            eg -= _PASSED_EG[r]
            passed_b |= 1 << sq
        if b_pawns & _PAWN_CONNECTED_B[sq]:
            mg -= _CONNECTED_MG
            eg -= _CONNECTED_EG
        stop = sq - 8
        if (
            stop >= 0
            and (w_pawns & _PAWN_ATK[1][stop])  # white pawn controls black's stop sq
            and not (b_pawns & _BACKWARD_SUPPORT_B[sq])
        ):
            mg -= _BACKWARD_MG
            eg -= _BACKWARD_EG
        bb &= bb - 1

    return mg, eg, passed_w, passed_b


# ---------------------------------------------------------------------------
# Classical evaluation
# ---------------------------------------------------------------------------


_EVAL_CACHE_MAX: int = 65536
_PAWN_CACHE_MAX: int = 32768


class ClassicalEvaluator:
    """Classical hand-crafted evaluation with tapered MG / EG scoring.

    Features: material + PST, pawn structure (doubled, isolated, connected,
    backward, passed), bishop pair, rook on open/semi-open files and 7th rank,
    rook behind passed pawn, piece mobility (safe squares), knight outposts,
    pawn threats, king safety (attack units + pawn shield), endgame king
    activity, and tempo.  Pawn structure and full eval are cached for speed.
    """

    def __init__(self) -> None:
        # Pawn structure cache: pawn_hash -> (mg, eg, passed_w_bb, passed_b_bb)
        self._pawn_cache: dict[int, tuple[int, int, int, int]] = {}
        # Full eval result cache: board_hash -> eval score (side-to-move POV)
        self._eval_cache: dict[int, int] = {}

    def invalidate_caches(self) -> None:
        """Clear all eval caches (call on ucinewgame or evaluator reset)."""
        self._pawn_cache.clear()
        self._eval_cache.clear()

    def evaluate(self, board: Board) -> int:
        key = board.hash
        cached = self._eval_cache.get(key)
        if cached is not None:
            return cached
        result = self._evaluate_internal(board)
        if len(self._eval_cache) >= _EVAL_CACHE_MAX:
            self._eval_cache.clear()
        self._eval_cache[key] = result
        return result

    def _evaluate_internal(self, board: Board) -> int:
        pieces = board.pieces

        mg = eg = phase = 0

        # ---- Material + PST (flat lookup for speed) ----
        for pt in range(6):
            off = pt * 64
            bb = pieces[0][pt]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                mg += _MG_W[off + sq]
                eg += _EG_W[off + sq]
                bb &= bb - 1
            bb = pieces[1][pt]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                mg -= _MG_B[off + sq]
                eg -= _EG_B[off + sq]
                bb &= bb - 1

        # ---- Game phase (for tapered eval) ----
        for c in range(2):
            phase += pieces[c][1].bit_count() + pieces[c][2].bit_count()
            phase += pieces[c][3].bit_count() * 2
            phase += pieces[c][4].bit_count() * 4
        phase = min(phase, _TOTAL_PHASE)

        w_pawns = pieces[0][0]
        b_pawns = pieces[1][0]
        occ = board.all_occ

        # ---- Bulk pawn attack maps (for mobility safe-square filter) ----
        w_pawn_atk = (
            ((w_pawns & ~_FILE_A_BB) << 7)  # attacks up-right (our left)
            | ((w_pawns & ~_FILE_H_BB) << 9)  # attacks up-left
        ) & 0xFFFF_FFFF_FFFF_FFFF
        b_pawn_atk = ((b_pawns & ~_FILE_H_BB) >> 7) | ((b_pawns & ~_FILE_A_BB) >> 9)

        # ---- Pawn structure (cached) ----
        pawn_key = (w_pawns ^ b_pawns * _PAWN_HASH_MUL) & 0xFFFF_FFFF_FFFF_FFFF
        entry = self._pawn_cache.get(pawn_key)
        if entry is None:
            entry = _eval_pawns(w_pawns, b_pawns)
            if len(self._pawn_cache) >= _PAWN_CACHE_MAX:
                self._pawn_cache.clear()
            self._pawn_cache[pawn_key] = entry
        pawn_mg, pawn_eg, passed_w, passed_b = entry
        mg += pawn_mg
        eg += pawn_eg

        # ---- Bishop pair ----
        if pieces[0][2].bit_count() >= 2:
            mg += _BISHOP_PAIR_MG
            eg += _BISHOP_PAIR_EG
        if pieces[1][2].bit_count() >= 2:
            mg -= _BISHOP_PAIR_MG
            eg -= _BISHOP_PAIR_EG

        # ---- Rook on open / semi-open files + 7th rank + behind passed pawn ----
        for c, sign in ((0, 1), (1, -1)):
            own_pawns = pieces[c][0]
            enemy_pawns = pieces[1 - c][0]
            all_pawns = own_pawns | enemy_pawns
            rank7 = 6 if c == 0 else 1
            passed_own = passed_w if c == 0 else passed_b
            bb = pieces[c][3]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                fbb = _FILE_BB[sq & 7]
                if not (all_pawns & fbb):
                    mg += sign * _ROOK_OPEN_MG
                    eg += sign * _ROOK_OPEN_EG
                elif not (own_pawns & fbb):
                    mg += sign * _ROOK_SEMI_MG
                    eg += sign * _ROOK_SEMI_EG
                if (sq >> 3) == rank7:
                    mg += sign * _ROOK_7TH_MG
                    eg += sign * _ROOK_7TH_EG
                # Rook behind passed pawn: same file, rook is behind passer
                if passed_own & fbb:
                    pp = passed_own & fbb
                    while pp:
                        pp_sq = (pp & -pp).bit_length() - 1
                        if (c == 0 and sq < pp_sq) or (c == 1 and sq > pp_sq):
                            mg += sign * _ROOK_BEHIND_PASSED_MG
                            eg += sign * _ROOK_BEHIND_PASSED_EG
                        pp &= pp - 1
                bb &= bb - 1

        # ---- Mobility (safe squares = not attacked by enemy pawns) ----
        w_safe = ~b_pawn_atk & 0xFFFF_FFFF_FFFF_FFFF
        b_safe = ~w_pawn_atk

        for c, sign, safe_mask in ((0, 1, w_safe), (1, -1, b_safe)):
            own_occ = board.occupancy[c]
            mob_safe = safe_mask & ~own_occ

            # Knights
            bb = pieces[c][1]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                mob = (_NATT[sq] & mob_safe).bit_count()
                mob = min(mob, 8)
                mg += sign * _KNIGHT_MOB_MG[mob]
                eg += sign * _KNIGHT_MOB_EG[mob]
                bb &= bb - 1

            # Bishops
            bb = pieces[c][2]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                mob = (_bishop_atk(sq, occ) & mob_safe).bit_count()
                mob = min(mob, 13)
                mg += sign * _BISHOP_MOB_MG[mob]
                eg += sign * _BISHOP_MOB_EG[mob]
                bb &= bb - 1

            # Rooks
            bb = pieces[c][3]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                mob = (_rook_atk(sq, occ) & mob_safe).bit_count()
                mob = min(mob, 14)
                mg += sign * _ROOK_MOB_MG[mob]
                eg += sign * _ROOK_MOB_EG[mob]
                bb &= bb - 1

            # Queens
            bb = pieces[c][4]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                mob = ((_bishop_atk(sq, occ) | _rook_atk(sq, occ)) & mob_safe).bit_count()
                mob = min(mob, 27)
                mg += sign * _QUEEN_MOB_MG[mob]
                eg += sign * _QUEEN_MOB_EG[mob]
                bb &= bb - 1

        # ---- Knight outposts ----
        # White knights on enemy half not attackable by black pawns
        bb = pieces[0][1] & _OUTPOST_MASK_W
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if not (b_pawns & _PAWN_ATK[0][sq]):
                mg += _OUTPOST_MG
                eg += _OUTPOST_EG
            bb &= bb - 1
        bb = pieces[1][1] & _OUTPOST_MASK_B
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if not (w_pawns & _PAWN_ATK[1][sq]):
                mg -= _OUTPOST_MG
                eg -= _OUTPOST_EG
            bb &= bb - 1

        # ---- Pawn threats (our pawns attacking enemy non-pawns) ----
        enemy_non_pawns = pieces[1][1] | pieces[1][2] | pieces[1][3] | pieces[1][4]
        if w_pawn_atk & enemy_non_pawns:
            count = (w_pawn_atk & enemy_non_pawns).bit_count()
            mg += count * _PAWN_THREAT_MG
            eg += count * _PAWN_THREAT_EG
        own_non_pawns = pieces[0][1] | pieces[0][2] | pieces[0][3] | pieces[0][4]
        if b_pawn_atk & own_non_pawns:
            count = (b_pawn_atk & own_non_pawns).bit_count()
            mg -= count * _PAWN_THREAT_MG
            eg -= count * _PAWN_THREAT_EG

        # ---- King safety: pawn shield (MG only) ----
        w_king_sq = board.king_sq(0)
        b_king_sq = board.king_sq(1)
        mg += (w_pawns & _SHIELD_W[w_king_sq]).bit_count() * _PAWN_SHIELD
        mg -= (b_pawns & _SHIELD_B[b_king_sq]).bit_count() * _PAWN_SHIELD

        # ---- King safety: attack units ----
        w_zone = _KING_ZONE_W[w_king_sq]
        b_zone = _KING_ZONE_B[b_king_sq]
        w_atk_units = b_atk_units = 0

        # Attacks on white's king zone by black pieces
        bb = pieces[1][1]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if _NATT[sq] & w_zone:
                b_atk_units += _ATK_WEIGHT[1]
            bb &= bb - 1
        bb = pieces[1][2]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if _bishop_atk(sq, occ) & w_zone:
                b_atk_units += _ATK_WEIGHT[2]
            bb &= bb - 1
        bb = pieces[1][3]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if _rook_atk(sq, occ) & w_zone:
                b_atk_units += _ATK_WEIGHT[3]
            bb &= bb - 1
        bb = pieces[1][4]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if (_bishop_atk(sq, occ) | _rook_atk(sq, occ)) & w_zone:
                b_atk_units += _ATK_WEIGHT[4]
            bb &= bb - 1

        # Attacks on black's king zone by white pieces
        bb = pieces[0][1]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if _NATT[sq] & b_zone:
                w_atk_units += _ATK_WEIGHT[1]
            bb &= bb - 1
        bb = pieces[0][2]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if _bishop_atk(sq, occ) & b_zone:
                w_atk_units += _ATK_WEIGHT[2]
            bb &= bb - 1
        bb = pieces[0][3]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if _rook_atk(sq, occ) & b_zone:
                w_atk_units += _ATK_WEIGHT[3]
            bb &= bb - 1
        bb = pieces[0][4]
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if (_bishop_atk(sq, occ) | _rook_atk(sq, occ)) & b_zone:
                w_atk_units += _ATK_WEIGHT[4]
            bb &= bb - 1

        mg -= _KING_SAFETY[min(b_atk_units, 99)]
        mg += _KING_SAFETY[min(w_atk_units, 99)]

        # ---- Endgame king activity ----
        if phase < _TOTAL_PHASE:
            # King centralization: reward kings near center in endgame
            # Center distance: sum of file and rank distance from d4/e4 area
            for c, sign in ((0, 1), (1, -1)):
                ksq = board.king_sq(c)
                kf, kr = ksq & 7, ksq >> 3
                center_dist = abs(kf - 3.5) + abs(kr - 3.5)
                eg += sign * int((7 - center_dist) * _EG_KING_CENTER)

            # King proximity to own passed pawns
            for c, sign in ((0, 1), (1, -1)):
                ksq = board.king_sq(c)
                kf, kr = ksq & 7, ksq >> 3
                passed_own = passed_w if c == 0 else passed_b
                bb = passed_own
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    dist = max(abs((sq & 7) - kf), abs((sq >> 3) - kr))
                    eg += sign * (7 - dist) * 2
                    bb &= bb - 1

        # ---- Tapered score ----
        score = (mg * phase + eg * (_TOTAL_PHASE - phase)) // _TOTAL_PHASE

        # Tempo bonus
        score += _TEMPO

        return score if board.side == 0 else -score


# ---------------------------------------------------------------------------
# Evaluator registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[Evaluator]] = {
    "classical": ClassicalEvaluator,
}


def register_evaluator(name: str, cls: type[Evaluator]) -> None:
    """Register a new evaluation backend (e.g. NNUE)."""
    _REGISTRY[name.lower()] = cls


def available_evaluators() -> list[str]:
    """Return the names of all registered evaluation backends."""
    return list(_REGISTRY)


def create_evaluator(name: str = "classical") -> Evaluator:
    """Instantiate an evaluator by name.

    Raises :class:`ValueError` if *name* is not registered.
    """
    key = name.lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        msg = f"Unknown evaluator {name!r}. Available: {available_evaluators()}"
        raise ValueError(msg)
    return cls()


# ===== hydra/transposition.py =====
"""Transposition table — hash table for caching search results.

Uses Zobrist keys (computed incrementally by :mod:`hydra.board`) to
index into a fixed-size table with a depth-preferred replacement scheme.
"""


# ---------------------------------------------------------------------------
# TT entry bound types
# ---------------------------------------------------------------------------
TT_EXACT: int = 0
TT_ALPHA: int = 1  # Upper bound (score failed low)
TT_BETA: int = 2  # Lower bound (score failed high)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


class TTEntry:
    """Single transposition-table entry."""

    __slots__ = ("depth", "flag", "key", "move", "score")

    def __init__(
        self,
        key: int = 0,
        depth: int = 0,
        score: int = 0,
        flag: int = 0,
        move: int = 0,
    ) -> None:
        self.key = key
        self.depth = depth
        self.score = score
        self.flag = flag
        self.move = move


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class TranspositionTable:
    """Fixed-size hash table with depth-preferred replacement."""

    def __init__(self, size_mb: int = 64) -> None:
        self._num_entries = max(1, (size_mb * 1024 * 1024) // 64)
        self._table: list[TTEntry | None] = [None] * self._num_entries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def probe(self, key: int) -> TTEntry | None:
        """Look up a position.  Returns the entry on key-match, else *None*."""
        entry = self._table[key % self._num_entries]
        if entry is not None and entry.key == key:
            return entry
        return None

    def store(
        self,
        key: int,
        depth: int,
        score: int,
        flag: int,
        move: int,
    ) -> None:
        """Store a search result.  Replaces if same position or at least as deep."""
        idx = key % self._num_entries
        old = self._table[idx]
        if old is None or old.key == key or depth >= old.depth:
            self._table[idx] = TTEntry(key, depth, score, flag, move)

    def clear(self) -> None:
        """Remove all entries."""
        self._table = [None] * self._num_entries

    def resize(self, size_mb: int) -> None:
        """Resize (and clear) the table."""
        self._num_entries = max(1, (size_mb * 1024 * 1024) // 64)
        self._table = [None] * self._num_entries

    def hashfull(self) -> int:
        """Return fill rate in per-mille (0–1000), sampled from first 1000 entries."""
        sample = min(1000, self._num_entries)
        used = sum(1 for i in range(sample) if self._table[i] is not None)
        return (used * 1000) // sample


# ===== hydra/syzygy.py =====
"""Syzygy tablebase adapter backed by the vendored Fathom probe code."""




_fathom = None

TB_LOSS = 0
TB_BLESSED_LOSS = 1
TB_DRAW = 2
TB_CURSED_WIN = 3
TB_WIN = 4

TB_PROMOTES_NONE = 0
TB_PROMOTES_QUEEN = 1
TB_PROMOTES_ROOK = 2
TB_PROMOTES_BISHOP = 3
TB_PROMOTES_KNIGHT = 4


class RootProbeResult(NamedTuple):
    wdl: int
    from_sq: int
    to_sq: int
    promotes: int
    ep: bool
    dtz: int


def native_available() -> bool:
    return _fathom is not None


def _position_args(board, *, use_50_move_rule: bool = True):
    pieces = board.pieces
    ep = 0 if board.ep_square == NO_SQUARE else board.ep_square
    rule50 = board.halfmove if use_50_move_rule else 0
    return (
        board.occupancy[WHITE],
        board.occupancy[BLACK],
        pieces[WHITE][KING] | pieces[BLACK][KING],
        pieces[WHITE][QUEEN] | pieces[BLACK][QUEEN],
        pieces[WHITE][ROOK] | pieces[BLACK][ROOK],
        pieces[WHITE][BISHOP] | pieces[BLACK][BISHOP],
        pieces[WHITE][KNIGHT] | pieces[BLACK][KNIGHT],
        pieces[WHITE][PAWN] | pieces[BLACK][PAWN],
        rule50,
        board.castling,
        ep,
        board.side == WHITE,
    )


def _root_probe_result(result) -> RootProbeResult:
    wdl, from_sq, to_sq, promotes, ep, dtz = result
    return RootProbeResult(
        int(wdl),
        int(from_sq),
        int(to_sq),
        int(promotes),
        bool(ep),
        int(dtz),
    )


class SyzygyTablebase:
    """Loaded Syzygy state.

    Fathom stores table metadata globally, so the UCI protocol owns one shared
    instance. Path changes and root DTZ probes are serialized.
    """

    __slots__ = ("_enabled", "_lock", "_path", "largest")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._path = ""
        self._enabled = False
        self.largest = 0

    @property
    def enabled(self) -> bool:
        return self._enabled and self.largest > 0

    @property
    def path(self) -> str:
        return self._path

    def set_path(self, path: str) -> int:
        if _fathom is None:
            msg = "Syzygy support is unavailable: native Fathom extension not built"
            raise RuntimeError(msg)

        normalized = "" if path in {"", "<empty>"} else path
        with self._lock:
            self.largest = int(_fathom.init(normalized))
            self._path = normalized
            self._enabled = self.largest > 0
            return self.largest

    def can_probe(self, board, limit: int) -> bool:
        if limit <= 0 or not self.enabled:
            return False
        piece_count = board.all_occ.bit_count()
        return piece_count <= limit and piece_count <= self.largest

    def probe_wdl(self, board, *, use_50_move_rule: bool = True) -> int | None:
        if not self.enabled:
            return None
        result = _fathom.probe_wdl(*_position_args(board, use_50_move_rule=use_50_move_rule))
        return None if result is None else int(result)

    def probe_root(self, board, *, use_50_move_rule: bool = True) -> RootProbeResult | None:
        if not self.enabled:
            return None
        with self._lock:
            result = _fathom.probe_root(
                *_position_args(board, use_50_move_rule=use_50_move_rule)
            )
        if result is None:
            return None
        return _root_probe_result(result)


# ===== hydra/engine.py =====
"""Search engine — iterative-deepening alpha-beta with PVS and enhancements.

Features implemented:
   1.  Negamax with alpha-beta pruning
   2.  Iterative deepening
   3.  Quiescence search (captures + queen promotions)
   4.  Transposition table (probe / store with mate-score adjustment)
   5.  Move ordering: TT → queen-promo → good captures (SEE+cap-hist) →
       killers → countermove → history+cont-hist(1+2-ply) → bad captures
   6.  Check extensions (+1 ply when in check)
   7.  Null-move pruning (dynamic reduction: 4 + depth/4 + eval-margin)
   8.  Late-move reductions (LMR) with improving-flag and cont-hist adjustment
   9.  Principal-variation search (PVS)
  10.  Aspiration windows
  11.  Static Exchange Evaluation (SEE) for capture ordering and pruning
  12.  Continuation history (1-ply + 2-ply, indexed by prev/prev-prev destination)
  13.  Improving flag (used in RFP margin scaling and LMR)
  14.  History and continuation history capped at ±16 384 to prevent overflow
  15.  Mate distance pruning (tighten alpha/beta to shortest mate bounds)
  16.  LMP asymmetry (more aggressive when not improving)
  17.  History pruning (skip quiet moves with very negative history at depth≤5)
  18.  Capture history (per attacker/target/captured-type, used in ordering)
  19.  Correction history (pawn-hash keyed eval bias correction)
  20.  Singular extensions (+ double extension + multicut + negative extension)
  21.  ProbCut (depth≥5, SEE-filtered captures verified by qsearch + reduced search)
  22.  Soft/hard time management with best-move stability scaling
  23.  History aging between searches (all tables halved at start of each call)
  24.  LMR for bad captures (negative-SEE captures reduced by (r-1)//2)
"""




# Piece-type indices used in insufficient-material check
_KNIGHT = 1
_BISHOP = 2
_ROOK = 3
_QUEEN = 4

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INFINITY: int = 30_000
MATE_SCORE: int = 29_000
MAX_DEPTH: int = 100
MAX_PLY: int = 128
ASPIRATION_WINDOW: int = 30

# Piece values for MVV-LVA ordering and SEE (indexed by piece type)
PIECE_VALUES: tuple[int, ...] = (100, 320, 330, 500, 900, 20_000)

# Search tuning constants
_REVERSE_FUTILITY_MARGIN: int = 150
_RAZORING_MARGIN: int = 300
_FUTILITY_MARGIN: int = 200
_DELTA_MARGIN: int = 200
_LMP_BASE: int = 3
_UCI_INFO_LINE_LIMIT: int = 96
_TB_WIN_SCORE: int = 20_000
_TB_CURSED_WIN_SCORE: int = 2
_TB_BLESSED_LOSS_SCORE: int = -2
_TB_PROMO_TO_HYDRA: dict[int, int] = {
    TB_PROMOTES_QUEEN: PROMO_QUEEN,
    TB_PROMOTES_ROOK: PROMO_ROOK,
    TB_PROMOTES_BISHOP: PROMO_BISHOP,
    TB_PROMOTES_KNIGHT: PROMO_KNIGHT,
}

# Pre-computed LMR reduction table  [depth][move_index] — aggressive
_LMR: list[list[int]] = [[0] * 64 for _ in range(MAX_DEPTH + 1)]
for _d in range(1, MAX_DEPTH + 1):
    for _m in range(1, 64):
        _LMR[_d][_m] = max(0, int(0.5 + math.log(_d) * math.log(_m) / 1.6))

_HIST_LIMIT: int = 16_384
_PAWN_ATK = PAWN_ATTACKS
_KNIGHT_ATK = KNIGHT_ATTACKS
_KING_ATK = KING_ATTACKS
_RM = _rook_masks
_BM = _bishop_masks
_RT = _rook_table
_BT = _bishop_table
_RMAG = ROOK_MAGICS
_BMAG = BISHOP_MAGICS
_RSHIFT = ROOK_SHIFTS
_BSHIFT = BISHOP_SHIFTS
_BALL = BB_ALL

# Multiplier for the pawn-structure hash used by correction history
_PAWN_HASH_MUL = 0x9E3779B97F4A7C15


def _rook_atk(sq: int, occ: int) -> int:
    o = occ & _RM[sq]
    return _RT[sq][((o * _RMAG[sq]) & _BALL) >> _RSHIFT[sq]]


def _bishop_atk(sq: int, occ: int) -> int:
    o = occ & _BM[sq]
    return _BT[sq][((o * _BMAG[sq]) & _BALL) >> _BSHIFT[sq]]


def _clamp_history(value: int) -> int:
    return max(-_HIST_LIMIT, min(_HIST_LIMIT, value))


def _see_lva(to_sq: int, side: int, occ: int, pieces: list[list[int]]) -> tuple[int, int]:
    bb = _PAWN_ATK[side ^ 1][to_sq] & pieces[side][PAWN] & occ
    if bb:
        return (bb & -bb).bit_length() - 1, PAWN

    bb = _KNIGHT_ATK[to_sq] & pieces[side][KNIGHT] & occ
    if bb:
        return (bb & -bb).bit_length() - 1, KNIGHT

    bishop_atk = _bishop_atk(to_sq, occ)
    bb = bishop_atk & pieces[side][BISHOP] & occ
    if bb:
        return (bb & -bb).bit_length() - 1, BISHOP

    rook_atk = _rook_atk(to_sq, occ)
    bb = rook_atk & pieces[side][ROOK] & occ
    if bb:
        return (bb & -bb).bit_length() - 1, ROOK

    bb = (bishop_atk | rook_atk) & pieces[side][QUEEN] & occ
    if bb:
        return (bb & -bb).bit_length() - 1, QUEEN

    bb = _KING_ATK[to_sq] & pieces[side][KING] & occ
    if bb:
        return (bb & -bb).bit_length() - 1, KING

    return -1, _NPT


def _see_sub(
    to_sq: int,
    occ: int,
    piece_value: int,
    side: int,
    pieces: list[list[int]],
) -> int:
    sq, pt = _see_lva(to_sq, side, occ, pieces)
    if sq == -1:
        return 0

    gain = piece_value - _see_sub(to_sq, occ ^ (1 << sq), PIECE_VALUES[pt], side ^ 1, pieces)
    return max(0, gain)


def _see(board: Board, move: int) -> int:
    to_sq = move_to_sq(move)
    from_sq = move_from_sq(move)
    piece_type = board.mailbox[from_sq]
    flag = move_flag(move)

    if flag == FLAG_EN_PASSANT:
        ep_pawn_sq = to_sq - 8 if board.side == WHITE else to_sq + 8
        occ = (board.all_occ ^ (1 << from_sq) ^ (1 << ep_pawn_sq)) | (1 << to_sq)
        cap_value = PIECE_VALUES[PAWN]
    else:
        captured = board.mailbox[to_sq]
        if captured == _NPT:
            return 0
        occ = (board.all_occ ^ (1 << from_sq)) | (1 << to_sq)
        cap_value = PIECE_VALUES[captured]

    return cap_value - _see_sub(to_sq, occ, PIECE_VALUES[piece_type], board.side ^ 1, board.pieces)


# ---------------------------------------------------------------------------
# Persistent history tables (survive across search calls within a game)
# ---------------------------------------------------------------------------


class HistoryTables:
    """Mutable history tables that persist between searches.

    Pass into :func:`search` via *history_tables*; they are aged (all values
    halved) at the start of each call so stale knowledge decays naturally.
    Maintain one instance per game in the UCI layer and reset on
    ``ucinewgame``.
    """

    __slots__ = ("cap_hist", "cont_hist", "cont_hist2", "corr_hist", "countermoves", "history")

    def __init__(self) -> None:
        self.history: list[list[list[int]]] = [[[0] * 64 for _ in range(64)] for _ in range(2)]
        self.cont_hist: list[list[int]] = [[0] * 64 for _ in range(64)]
        self.cont_hist2: list[list[int]] = [[0] * 64 for _ in range(64)]
        self.cap_hist: list[list[list[int]]] = [[[0] * 6 for _ in range(64)] for _ in range(6)]
        self.corr_hist: list[list[int]] = [[0] * 65536 for _ in range(2)]
        self.countermoves: list[list[int]] = [[MOVE_NONE] * 64 for _ in range(64)]

    def age(self) -> None:
        """Halve all history values to decay stale information between searches."""
        for c in range(2):
            for f in range(64):
                row = self.history[c][f]
                for t in range(64):
                    row[t] >>= 1
        for f in range(64):
            row = self.cont_hist[f]
            for t in range(64):
                row[t] >>= 1
        for f in range(64):
            row = self.cont_hist2[f]
            for t in range(64):
                row[t] >>= 1
        for a in range(6):
            for t in range(64):
                row = self.cap_hist[a][t]
                for cp in range(6):
                    row[cp] >>= 1


# ---------------------------------------------------------------------------
# Search parameters  (parsed from the UCI ``go`` command)
# ---------------------------------------------------------------------------


class SearchParams:
    """Parameters that control a single search invocation."""

    __slots__ = (
        "binc",
        "btime",
        "depth",
        "infinite",
        "move_overhead",
        "movestogo",
        "movetime",
        "nodes",
        "ponder",
        "winc",
        "wtime",
    )

    def __init__(self) -> None:
        self.depth: int = MAX_DEPTH
        self.movetime: int = 0  # milliseconds
        self.move_overhead: int = 10  # milliseconds
        self.wtime: int = 0
        self.btime: int = 0
        self.winc: int = 0
        self.binc: int = 0
        self.movestogo: int = 0
        self.infinite: bool = False
        self.nodes: int = 0
        self.ponder: bool = False


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------


class SearchResult:
    """Result returned by :func:`search`."""

    __slots__ = ("bestmove", "depth", "nodes", "pv", "score")

    def __init__(
        self,
        bestmove: int = MOVE_NONE,
        score: int = 0,
        depth: int = 0,
        nodes: int = 0,
        pv: list[int] | None = None,
    ) -> None:
        self.bestmove = bestmove
        self.score = score
        self.depth = depth
        self.nodes = nodes
        self.pv = pv or []


# ---------------------------------------------------------------------------
# Mate-score adjustment for TT storage
# ---------------------------------------------------------------------------


def _score_to_tt(score: int, ply: int) -> int:
    if score > MATE_SCORE - MAX_PLY:
        return score + ply
    if score < -MATE_SCORE + MAX_PLY:
        return score - ply
    return score


def _score_from_tt(score: int, ply: int) -> int:
    if score > MATE_SCORE - MAX_PLY:
        return score - ply
    if score < -MATE_SCORE + MAX_PLY:
        return score + ply
    return score


# ---------------------------------------------------------------------------
# UCI score formatting
# ---------------------------------------------------------------------------


def _format_score(score: int) -> str:
    if score > MATE_SCORE - MAX_PLY:
        moves = (MATE_SCORE - score + 1) // 2
        return f"score mate {moves}"
    if score < -MATE_SCORE + MAX_PLY:
        moves = (MATE_SCORE + score + 1) // 2
        return f"score mate -{moves}"
    return f"score cp {score}"


def _info_with_pv(info: str, pv: list[int], limit: int = _UCI_INFO_LINE_LIMIT) -> str:
    """Append only complete PV moves that fit old GUI output buffers."""
    if not pv:
        return info
    line = info
    for index, move in enumerate(pv):
        prefix = " pv " if index == 0 else " "
        token = move_to_uci(move)
        candidate = line + prefix + token
        if len(candidate) > limit:
            break
        line = candidate
    return line


def _tb_score(wdl: int, ply: int) -> int | None:
    if wdl == TB_WIN:
        return _TB_WIN_SCORE - ply
    if wdl == TB_CURSED_WIN:
        return _TB_CURSED_WIN_SCORE
    if wdl == TB_DRAW:
        return 0
    if wdl == TB_BLESSED_LOSS:
        return _TB_BLESSED_LOSS_SCORE
    if wdl == TB_LOSS:
        return -_TB_WIN_SCORE + ply
    return None


def _tb_root_move(root_result, legal_moves: list[int]) -> int:
    promo = _TB_PROMO_TO_HYDRA.get(root_result.promotes, -1)
    for move in legal_moves:
        if move_from_sq(move) != root_result.from_sq or move_to_sq(move) != root_result.to_sq:
            continue
        if root_result.promotes == TB_PROMOTES_NONE and move_flag(move) != FLAG_PROMOTION:
            return move
        if move_flag(move) == FLAG_PROMOTION and move_promo(move) == promo:
            return move
    return MOVE_NONE


def _root_syzygy_result(
    board: Board,
    legal_moves: list[int],
    syzygy: SyzygyTablebase | None,
    probe_limit: int,
    use_50_move_rule: bool,
) -> SearchResult | None:
    if board.castling != 0 or syzygy is None or not syzygy.can_probe(board, probe_limit):
        return None

    root_result = syzygy.probe_root(board, use_50_move_rule=use_50_move_rule)
    if root_result is None:
        return None

    move = _tb_root_move(root_result, legal_moves)
    score = _tb_score(root_result.wdl, 0)
    if move == MOVE_NONE or score is None:
        return None

    return SearchResult(bestmove=move, score=score, depth=0, nodes=1, pv=[move])


def _probe_syzygy_wdl(ss: _SS, depth: int) -> int | None:
    if (
        ss.syzygy is None
        or depth < ss.syzygy_probe_depth
        or ss.syzygy_probe_limit <= 0
        or ss.board.castling != 0
        or (ss.syzygy_50_move_rule and ss.board.halfmove != 0)
        or not ss.syzygy.can_probe(ss.board, ss.syzygy_probe_limit)
    ):
        return None

    wdl = ss.syzygy.probe_wdl(ss.board, use_50_move_rule=ss.syzygy_50_move_rule)
    if wdl is None:
        return None

    score = _tb_score(wdl, ss.ply)
    if score is None:
        return None

    ss.tb_hits += 1
    ss.tt.store(ss.board.hash, max(depth, 0), _score_to_tt(score, ss.ply), TT_EXACT, MOVE_NONE)
    return score


# ---------------------------------------------------------------------------
# Draw detection
# ---------------------------------------------------------------------------


def _is_insufficient_material(board: Board) -> bool:
    """KvK, KNvK, KBvK, or KBvKB with same-colour bishops."""
    for c in range(2):
        if board.pieces[c][PAWN] | board.pieces[c][_ROOK] | board.pieces[c][_QUEEN]:
            return False
    wn = board.pieces[0][_KNIGHT].bit_count()
    wb = board.pieces[0][_BISHOP].bit_count()
    bn = board.pieces[1][_KNIGHT].bit_count()
    bb_ = board.pieces[1][_BISHOP].bit_count()
    wm, bm = wn + wb, bn + bb_
    # KvK
    if wm == 0 and bm == 0:
        return True
    # KN vs K  or  KB vs K
    if (wm == 1 and bm == 0) or (wm == 0 and bm == 1):
        return True
    # KBvKB on same-colour squares
    if wm == 1 and bm == 1 and wn == 0 and bn == 0:
        wsq = (board.pieces[0][_BISHOP] & -board.pieces[0][_BISHOP]).bit_length() - 1
        bsq = (board.pieces[1][_BISHOP] & -board.pieces[1][_BISHOP]).bit_length() - 1
        if ((wsq >> 3) ^ (wsq & 7)) & 1 == ((bsq >> 3) ^ (bsq & 7)) & 1:
            return True
    return False


def _is_draw(board: Board) -> bool:
    """Fifty-move rule, insufficient material, or two-fold repetition."""
    if board.halfmove >= 100:
        return True
    if _is_insufficient_material(board):
        return True
    n = len(board.history)
    limit = min(board.halfmove, n)
    if limit >= 4:
        h = board.hash
        for i in range(4, limit + 1, 2):
            if board.history[n - i][4] == h:
                return True
    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_non_pawn_material(board: Board, colour: int) -> bool:
    p = board.pieces[colour]
    return bool(p[1] | p[2] | p[3] | p[4])


def _extract_pv(board: Board, tt: TranspositionTable, depth: int) -> list[int]:
    """Walk the TT to reconstruct the principal variation."""
    pv: list[int] = []
    seen: set[int] = set()
    for _ in range(depth):
        h = board.hash
        if h in seen:
            break
        seen.add(h)
        entry = tt.probe(h)
        if entry is None or entry.move == MOVE_NONE:
            break
        legal = generate_legal_moves(board)
        if entry.move not in legal:
            break
        pv.append(entry.move)
        board.make_move(entry.move)
    for move in reversed(pv):
        board.unmake_move(move)
    return pv


# ---------------------------------------------------------------------------
# Time management
# ---------------------------------------------------------------------------


def _compute_time_limits(params: SearchParams, side: int) -> tuple[float, float]:
    """Return ``(soft_limit, hard_limit)`` in seconds (0 = unlimited).

    *soft_limit* is the target time per move; the search stops early when the
    best move has been stable for several depths.  *hard_limit* is the absolute
    maximum and is checked in :meth:`_SS.check_stop`.
    """
    overhead = max(params.move_overhead, 0)
    if params.movetime > 0:
        hard = max(params.movetime - overhead, 1) / 1000.0
        return hard, hard

    remaining = params.wtime if side == WHITE else params.btime
    inc = params.winc if side == WHITE else params.binc

    if remaining <= 0 and inc <= 0:
        return 0.0, 0.0

    remaining = max(remaining - overhead, 1)

    base = remaining / (params.movestogo + 3) if params.movestogo > 0 else remaining / 25
    soft_ms = base + inc * 0.75

    if remaining < 1000:
        hard_ms = remaining * 0.20
    elif remaining < 5000:
        hard_ms = remaining * 0.30
    else:
        hard_ms = remaining * 0.50
    hard_ms = max(soft_ms, hard_ms)
    soft_ms = max(soft_ms, min(50, remaining * 0.1))
    hard_ms = max(hard_ms, min(50, remaining * 0.1))

    return soft_ms / 1000.0, hard_ms / 1000.0


# ---------------------------------------------------------------------------
# Move ordering
# ---------------------------------------------------------------------------

_NPT = NO_PIECE_TYPE


def _score_move(
    move: int,
    board: Board,
    tt_move: int,
    killers: list[int],
    history: list[list[int]],
    countermove: int,
    cont_hist_row: list[int] | None,
    cont_hist2_row: list[int] | None,
    cap_hist: list[list[list[int]]],
) -> int:
    if move == tt_move:
        return 10_000_000

    flag = move_flag(move)
    to = move_to_sq(move)
    frm = move_from_sq(move)

    if flag == FLAG_PROMOTION:
        if move_promo(move) == PROMO_QUEEN:
            return 9_000_000
        return -3_000_000

    if board.mailbox[to] != _NPT or flag == FLAG_EN_PASSANT:
        cap_pt = PAWN if flag == FLAG_EN_PASSANT else board.mailbox[to]
        attacker_pt = board.mailbox[frm]
        ch = cap_hist[attacker_pt][to][cap_pt] >> 4  # scale down to ~±1024
        # Skip SEE for clearly winning captures — use MVV-LVA directly
        if PIECE_VALUES[cap_pt] > PIECE_VALUES[attacker_pt]:
            return 6_000_000 + PIECE_VALUES[cap_pt] - PIECE_VALUES[attacker_pt] + ch
        see = _see(board, move)
        if see >= 0:
            return 6_000_000 + see + ch
        return -9_000_000 + see + ch

    if move == killers[0]:
        return 4_000_000
    if move == killers[1]:
        return 3_900_000
    if move == countermove:
        return 3_800_000

    score = history[frm][to]
    if cont_hist_row is not None:
        score += cont_hist_row[to]
    if cont_hist2_row is not None:
        score += cont_hist2_row[to]
    return score


def _order_moves(
    moves: list[int],
    board: Board,
    tt_move: int,
    killers: list[int],
    history: list[list[int]],
    countermove: int,
    cont_hist_row: list[int] | None,
    cont_hist2_row: list[int] | None,
    cap_hist: list[list[list[int]]],
) -> list[int]:
    scored = [
        (
            _score_move(
                m,
                board,
                tt_move,
                killers,
                history,
                countermove,
                cont_hist_row,
                cont_hist2_row,
                cap_hist,
            ),
            m,
        )
        for m in moves
    ]
    scored.sort(reverse=True)
    return [m for _, m in scored]


# ---------------------------------------------------------------------------
# Internal search state
# ---------------------------------------------------------------------------


class _SS:
    """Mutable state shared by all recursive search calls."""

    __slots__ = (
        "board",
        "cap_hist",
        "cont_hist",
        "cont_hist2",
        "corr_hist",
        "countermoves",
        "evaluator",
        "excluded",
        "hard_limit",
        "history",
        "info_cb",
        "killers",
        "nodes",
        "params",
        "ply",
        "pondering",
        "prev_move",
        "seldepth",
        "soft_limit",
        "start_time",
        "static_evals",
        "stop_event",
        "stop_on_ponderhit",
        "stopped",
        "syzygy",
        "syzygy_50_move_rule",
        "syzygy_probe_depth",
        "syzygy_probe_limit",
        "tb_hits",
        "tt",
    )

    def __init__(
        self,
        board: Board,
        params: SearchParams,
        evaluator: Evaluator,
        tt: TranspositionTable,
        stop_event: threading.Event,
        info_cb: Callable[[str], None] | None,
        history_tables: HistoryTables | None = None,
        syzygy: SyzygyTablebase | None = None,
        syzygy_probe_depth: int = 1,
        syzygy_probe_limit: int = 7,
        syzygy_50_move_rule: bool = True,
    ) -> None:
        self.board = board
        self.params = params
        self.evaluator = evaluator
        self.tt = tt
        self.stop_event = stop_event
        self.info_cb = info_cb
        self.syzygy = syzygy
        self.syzygy_probe_depth = syzygy_probe_depth
        self.syzygy_probe_limit = syzygy_probe_limit
        self.syzygy_50_move_rule = syzygy_50_move_rule

        self.nodes: int = 0
        self.tb_hits: int = 0
        self.ply: int = 0
        self.seldepth: int = 0
        self.stopped: bool = False
        self.pondering: bool = params.ponder
        self.stop_on_ponderhit: bool = False
        self.start_time: float = time.perf_counter()
        self.soft_limit: float
        self.hard_limit: float
        self.soft_limit, self.hard_limit = _compute_time_limits(params, board.side)

        # Excluded move per ply (for singular extensions)
        self.excluded: list[int] = [MOVE_NONE] * MAX_PLY
        # Killer moves — two per ply
        self.killers: list[list[int]] = [[MOVE_NONE, MOVE_NONE] for _ in range(MAX_PLY)]
        # Previous move at each ply (for countermove and cont-hist indexing)
        self.prev_move: list[int] = [MOVE_NONE] * MAX_PLY
        # Static evals for improving detection
        self.static_evals: list[int] = [-INFINITY] * MAX_PLY

        if history_tables is not None:
            # Reuse persistent history tables (aged by the caller)
            self.history = history_tables.history
            self.cont_hist = history_tables.cont_hist
            self.cont_hist2 = history_tables.cont_hist2
            self.cap_hist = history_tables.cap_hist
            self.corr_hist = history_tables.corr_hist
            self.countermoves = history_tables.countermoves
        else:
            self.history = [[[0] * 64 for _ in range(64)] for _ in range(2)]
            self.cont_hist = [[0] * 64 for _ in range(64)]
            self.cont_hist2 = [[0] * 64 for _ in range(64)]
            self.cap_hist = [[[0] * 6 for _ in range(64)] for _ in range(6)]
            self.corr_hist = [[0] * 65536 for _ in range(2)]
            self.countermoves = [[MOVE_NONE] * 64 for _ in range(64)]

    def switch_from_ponder(self) -> None:
        """Called on ``ponderhit`` — switch to normal time-managed search."""
        self.pondering = False
        if self.stop_on_ponderhit:
            self.stopped = True

    def check_stop(self) -> bool:
        if self.stopped:
            return True
        if self.stop_event.is_set():
            self.stopped = True
            return True
        if self.params.nodes > 0 and self.nodes >= self.params.nodes:
            if self.pondering:
                self.stop_on_ponderhit = True
                return False
            self.stopped = True
            return True
        if (
            self.hard_limit > 0
            and self.nodes & 4095 == 0
            and time.perf_counter() - self.start_time >= self.hard_limit
        ):
            if self.pondering:
                self.stop_on_ponderhit = True
                return False
            self.stopped = True
            return True
        return False

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.start_time) * 1000)


# ---------------------------------------------------------------------------
# Quiescence search
# ---------------------------------------------------------------------------


def _quiescence(ss: _SS, alpha: int, beta: int) -> int:
    ss.nodes += 1
    ss.seldepth = max(ss.seldepth, ss.ply)
    if ss.check_stop():
        return 0

    board = ss.board
    if _is_draw(board):
        return 0

    in_check = board.is_in_check()

    # When in check we must search all evasions
    if in_check:
        moves = generate_legal_moves(board)
        if not moves:
            return -MATE_SCORE + ss.ply
        best = -INFINITY
        for move in moves:
            board.make_move(move)
            ss.ply += 1
            score = -_quiescence(ss, -beta, -alpha)
            ss.ply -= 1
            board.unmake_move(move)
            best = max(best, score)
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best

    # Stand-pat
    stand_pat = ss.evaluator.evaluate(board)
    if stand_pat >= beta:
        return beta
    alpha = max(alpha, stand_pat)

    # Big delta cutoff: if even capturing a queen can't raise alpha, prune
    if stand_pat + PIECE_VALUES[QUEEN] + _DELTA_MARGIN < alpha:
        return alpha

    mailbox = board.mailbox
    scored: list[tuple[int, int]] = []
    scored_append = scored.append
    for move in generate_captures(board):
        flag = move_flag(move)
        if flag == FLAG_PROMOTION:
            if move_promo(move) != PROMO_QUEEN:
                continue
            scored_append((9_000_000, move))
            continue

        cap = mailbox[move_to_sq(move)]
        if cap != _NPT and stand_pat + PIECE_VALUES[cap] + _DELTA_MARGIN < alpha:
            continue

        see = _see(board, move)
        if see < 0:
            continue
        scored_append((6_000_000 + see, move))
    scored.sort(reverse=True)

    for _, move in scored:
        board.make_move(move)
        ss.ply += 1
        score = -_quiescence(ss, -beta, -alpha)
        ss.ply -= 1
        board.unmake_move(move)

        if ss.stopped:
            return 0
        alpha = max(alpha, score)
        if alpha >= beta:
            return beta

    return alpha


# ---------------------------------------------------------------------------
# Negamax  (alpha-beta + TT + NMP + PVS + LMR + check extension)
# ---------------------------------------------------------------------------


def _negamax(ss: _SS, depth: int, alpha: int, beta: int, *, do_null: bool = True) -> int:
    ss.nodes += 1
    ss.seldepth = max(ss.seldepth, ss.ply)
    if ss.check_stop():
        return 0

    board = ss.board
    is_root = ss.ply == 0
    is_pv = beta - alpha > 1

    # Mate distance pruning — tighten bounds to shortest possible mate
    if not is_root:
        alpha = max(alpha, -(MATE_SCORE - ss.ply))
        beta = min(beta, MATE_SCORE - ss.ply - 1)
        if alpha >= beta:
            return alpha

    # Ply limit
    if ss.ply >= MAX_PLY:
        return ss.evaluator.evaluate(board)

    # Draw
    if not is_root and _is_draw(board):
        return 0

    if not is_root and ss.syzygy is not None:
        tb_score = _probe_syzygy_wdl(ss, depth)
        if tb_score is not None:
            return tb_score

    in_check = board.is_in_check()

    # Check extension
    if in_check:
        depth += 1

    # Transition to quiescence
    if depth <= 0:
        return _quiescence(ss, alpha, beta)

    # --- TT probe ---
    tt_move = MOVE_NONE
    tt_score = -INFINITY
    tt_depth = 0
    tt_flag = TT_ALPHA
    entry = ss.tt.probe(board.hash)
    if entry is not None:
        tt_move = entry.move
        tt_score = _score_from_tt(entry.score, ss.ply)
        tt_depth = entry.depth
        tt_flag = entry.flag
        if not is_pv and tt_depth >= depth and ss.excluded[ss.ply] == MOVE_NONE:
            if tt_flag == TT_EXACT:
                return tt_score
            if tt_flag == TT_ALPHA and tt_score <= alpha:
                return alpha
            if tt_flag == TT_BETA and tt_score >= beta:
                return beta

    # Static eval for pruning decisions; apply correction history to reduce
    # systematic bias between eval and search score.
    if not in_check:
        raw_eval = ss.evaluator.evaluate(board)
        ph = (
            (board.pieces[0][PAWN] ^ board.pieces[1][PAWN] * _PAWN_HASH_MUL)
            & 0xFFFF_FFFF_FFFF_FFFF
            & 0xFFFF
        )
        static_eval = raw_eval + ss.corr_hist[board.side][ph] // 256
    else:
        raw_eval = -INFINITY
        static_eval = -INFINITY
        ph = 0
    ss.static_evals[ss.ply] = static_eval
    improving = not in_check and ss.ply >= 2 and static_eval > ss.static_evals[ss.ply - 2]

    # --- Reverse futility pruning (static null move pruning) ---
    if (
        not is_pv
        and not in_check
        and depth <= 7
        and static_eval - _REVERSE_FUTILITY_MARGIN * depth * (2 - improving) >= beta
    ):
        return static_eval

    # --- Razoring ---
    if not is_pv and not in_check and depth <= 3 and static_eval + _RAZORING_MARGIN < alpha:
        score = _quiescence(ss, alpha, beta)
        if score <= alpha:
            return score

    # --- Null-move pruning ---
    if (
        do_null
        and not is_pv
        and not in_check
        and depth >= 3
        and static_eval >= beta
        and _has_non_pawn_material(board, board.side)
    ):
        r = 4 + depth // 4 + min((static_eval - beta) // 200, 3)
        board.make_null_move()
        ss.ply += 1
        ss.prev_move[ss.ply - 1] = MOVE_NONE  # null move has no from/to square
        null_score = -_negamax(ss, depth - 1 - r, -beta, -beta + 1, do_null=False)
        ss.ply -= 1
        board.unmake_null_move()
        if ss.stopped:
            return 0
        if null_score >= beta:
            return beta

    # --- ProbCut ---
    # If a capture passes a reduced search at a raised beta, prune early.
    if (
        not is_pv
        and not in_check
        and depth >= 5
        and abs(beta) < MATE_SCORE - MAX_PLY
        and ss.excluded[ss.ply] == MOVE_NONE
        and static_eval != -INFINITY
    ):
        pc_beta = min(beta + 200, MATE_SCORE - MAX_PLY - 1)
        for cap_move in generate_captures(board):
            if _see(board, cap_move) < pc_beta - static_eval:
                continue
            board.make_move(cap_move)
            ss.ply += 1
            ss.prev_move[ss.ply - 1] = cap_move
            pc_val = -_quiescence(ss, -pc_beta, -pc_beta + 1)
            if pc_val >= pc_beta and not ss.stopped:
                pc_val = -_negamax(ss, depth - 4, -pc_beta, -pc_beta + 1, do_null=True)
            ss.ply -= 1
            board.unmake_move(cap_move)
            if ss.stopped:
                return 0
            if pc_val >= pc_beta:
                ss.tt.store(
                    board.hash,
                    depth - 3,
                    _score_to_tt(pc_beta, ss.ply),
                    TT_BETA,
                    cap_move,
                )
                return pc_beta

    # --- Internal iterative reduction (IIR) ---
    if tt_move == MOVE_NONE and depth >= 4:
        depth -= 1

    # --- Generate & order moves ---
    moves = generate_legal_moves(board)
    excluded_move = ss.excluded[ss.ply]
    if excluded_move != MOVE_NONE:
        moves = [m for m in moves if m != excluded_move]
    if not moves:
        return (-MATE_SCORE + ss.ply) if in_check else 0

    prev = ss.prev_move[ss.ply - 1] if ss.ply > 0 else MOVE_NONE
    prev_from = prev_to = 0
    countermove = MOVE_NONE
    cont_hist_row = None
    if prev != MOVE_NONE:
        prev_from = move_from_sq(prev)
        prev_to = move_to_sq(prev)
        countermove = ss.countermoves[prev_from][prev_to]
        cont_hist_row = ss.cont_hist[prev_to]

    # 2-ply continuation history (our own last move, 2 plies back)
    cont_hist2_row = None
    if ss.ply >= 2:
        prev_prev = ss.prev_move[ss.ply - 2]
        if prev_prev != MOVE_NONE:
            cont_hist2_row = ss.cont_hist2[move_to_sq(prev_prev)]

    history_row = ss.history[board.side]
    history_delta = depth * depth
    orig_alpha = alpha
    best_score = -INFINITY
    best_move = MOVE_NONE

    can_futility = (
        not is_pv and not in_check and depth <= 3 and static_eval + _FUTILITY_MARGIN * depth < alpha
    )
    if not is_pv and depth <= 8:
        lmp_threshold = (3 + depth * depth) if improving else (1 + depth * depth // 2)
    else:
        lmp_threshold = 999
    quiets_tried = 0

    # --- Try TT move first (skip sort if it causes cutoff) ---
    tt_tried = False
    if tt_move != MOVE_NONE and tt_move in moves:
        tt_tried = True

        # Singular extension: verify the TT move is significantly better than all
        # other moves by doing a reduced search with that move excluded.
        extension = 0
        if (
            not is_root
            and excluded_move == MOVE_NONE
            and depth >= 8
            and entry is not None
            and tt_depth >= depth - 3
            and tt_flag in {TT_BETA, TT_EXACT}
            and abs(tt_score) < MATE_SCORE - MAX_PLY
        ):
            s_beta = tt_score - 2 * depth
            s_depth = (depth - 1) // 2
            ss.excluded[ss.ply] = tt_move
            s_val = _negamax(ss, s_depth, s_beta - 1, s_beta, do_null=False)
            ss.excluded[ss.ply] = MOVE_NONE
            if ss.stopped:
                return 0
            if s_val < s_beta:
                # TT move is singular — extend it (double if clearly best)
                extension = 2 if (not is_pv and s_val < s_beta - 20) else 1
            elif s_beta >= beta:
                # Multicut: even without the TT move the position likely fails high
                return s_beta
            elif tt_score >= beta:
                extension = -1  # negative extension: not clearly the best

        board.make_move(tt_move)
        ss.ply += 1
        ss.prev_move[ss.ply - 1] = tt_move
        score = -_negamax(ss, depth - 1 + extension, -beta, -alpha)
        ss.ply -= 1
        board.unmake_move(tt_move)

        if ss.stopped:
            return 0

        if score > best_score:
            best_score = score
            best_move = tt_move
        alpha = max(alpha, score)
        if alpha >= beta:
            is_capture = (
                board.mailbox[move_to_sq(tt_move)] != _NPT or move_flag(tt_move) == FLAG_EN_PASSANT
            )
            is_promo = move_flag(tt_move) == FLAG_PROMOTION
            if not is_capture and not is_promo:
                ply = ss.ply
                if ss.killers[ply][0] != tt_move:
                    ss.killers[ply][1] = ss.killers[ply][0]
                    ss.killers[ply][0] = tt_move
                frm = move_from_sq(tt_move)
                to = move_to_sq(tt_move)
                history_row[frm][to] = _clamp_history(history_row[frm][to] + history_delta)
                if prev != MOVE_NONE:
                    ss.countermoves[prev_from][prev_to] = tt_move
                    ss.cont_hist[prev_to][to] = _clamp_history(
                        ss.cont_hist[prev_to][to] + history_delta
                    )
                if cont_hist2_row is not None:
                    pp_to = move_to_sq(ss.prev_move[ss.ply - 2]) if ss.ply >= 2 else 0
                    ss.cont_hist2[pp_to][to] = _clamp_history(cont_hist2_row[to] + history_delta)
            elif is_capture and not is_promo:
                to = move_to_sq(tt_move)
                attacker_pt = board.mailbox[move_from_sq(tt_move)]
                tt_flag_cap = move_flag(tt_move)
                cap_pt = PAWN if tt_flag_cap == FLAG_EN_PASSANT else board.mailbox[to]
                ss.cap_hist[attacker_pt][to][cap_pt] = _clamp_history(
                    ss.cap_hist[attacker_pt][to][cap_pt] + history_delta
                )
            ss.tt.store(
                board.hash,
                depth,
                _score_to_tt(best_score, ss.ply),
                TT_BETA,
                best_move,
            )
            return best_score

    ordered = _order_moves(
        moves,
        board,
        tt_move,
        ss.killers[ss.ply],
        history_row,
        countermove,
        cont_hist_row,
        cont_hist2_row,
        ss.cap_hist,
    )

    for i, move in enumerate(ordered):
        if move == tt_move and tt_tried:
            continue

        flag = move_flag(move)
        is_capture = board.mailbox[move_to_sq(move)] != _NPT or flag == FLAG_EN_PASSANT
        is_promo = flag == FLAG_PROMOTION
        is_quiet = not is_capture and not is_promo

        # Pre-compute SEE for non-promotion captures once; reused by both the
        # SEE-pruning check and the bad-capture LMR block below.
        move_see = _see(board, move) if is_capture and not is_promo else 0

        if is_quiet and quiets_tried >= lmp_threshold:
            continue

        if can_futility and is_quiet and (i > 0 or tt_tried):
            quiets_tried += 1
            continue

        if (
            not is_pv
            and not is_root
            and not in_check
            and depth <= 6
            and is_capture
            and not is_promo
            and (i > 0 or tt_tried)
            and move_see < -depth * 80
        ):
            continue

        # History pruning: skip quiet moves with very negative history at low depth
        if is_quiet and not is_root and depth <= 5:
            frm_h = move_from_sq(move)
            to_h = move_to_sq(move)
            hist_score = history_row[frm_h][to_h]
            if cont_hist_row is not None:
                hist_score += cont_hist_row[to_h]
            if hist_score < -(3072 * depth):
                continue

        if is_quiet:
            quiets_tried += 1

        board.make_move(move)
        ss.ply += 1
        ss.prev_move[ss.ply - 1] = move

        if i == 0 and not tt_tried:
            score = -_negamax(ss, depth - 1, -beta, -alpha)
        else:
            reduction = 0
            if i >= 3 and depth >= 2 and not in_check:
                if is_quiet:
                    reduction = _LMR[min(depth, MAX_DEPTH)][min(i, 63)]
                    if is_pv:
                        reduction = max(0, reduction - 1)
                    frm = move_from_sq(move)
                    to = move_to_sq(move)
                    if history_row[frm][to] < 0:
                        reduction += 1
                    if not improving:
                        reduction += 1
                    if cont_hist_row is not None:
                        reduction -= cont_hist_row[to] // 5000
                    if cont_hist2_row is not None:
                        reduction -= cont_hist2_row[to] // 5000
                    reduction = max(0, min(reduction, depth - 1))
                elif is_capture and not is_promo and move_see < 0:
                    # Bad captures also get reduced, but less aggressively than quiets
                    base_r = _LMR[min(depth, MAX_DEPTH)][min(i, 63)]
                    reduction = max(0, (base_r - 1) // 2)

            score = -_negamax(ss, depth - 1 - reduction, -alpha - 1, -alpha)
            if reduction > 0 and score > alpha:
                score = -_negamax(ss, depth - 1, -alpha - 1, -alpha)
            if score > alpha and score < beta:
                score = -_negamax(ss, depth - 1, -beta, -alpha)

        ss.ply -= 1
        board.unmake_move(move)

        if ss.stopped:
            return best_score if is_root and best_move != MOVE_NONE else 0

        if score > best_score:
            best_score = score
            best_move = move

        alpha = max(alpha, score)

        if alpha >= beta:
            if is_quiet:
                ply = ss.ply
                if ss.killers[ply][0] != move:
                    ss.killers[ply][1] = ss.killers[ply][0]
                    ss.killers[ply][0] = move
                frm = move_from_sq(move)
                to = move_to_sq(move)
                history_row[frm][to] = _clamp_history(history_row[frm][to] + history_delta)
                if prev != MOVE_NONE:
                    ss.countermoves[prev_from][prev_to] = move
                    ss.cont_hist[prev_to][to] = _clamp_history(
                        ss.cont_hist[prev_to][to] + history_delta
                    )
                if cont_hist2_row is not None:
                    cont_hist2_row[to] = _clamp_history(cont_hist2_row[to] + history_delta)
            elif is_capture and not is_promo:
                to = move_to_sq(move)
                attacker_pt = board.mailbox[move_from_sq(move)]
                cap_pt = PAWN if flag == FLAG_EN_PASSANT else board.mailbox[to]
                ss.cap_hist[attacker_pt][to][cap_pt] = _clamp_history(
                    ss.cap_hist[attacker_pt][to][cap_pt] + history_delta
                )
            break

    if best_move == MOVE_NONE:
        return alpha

    if best_score >= beta:
        is_best_capture = (
            board.mailbox[move_to_sq(best_move)] != _NPT or move_flag(best_move) == FLAG_EN_PASSANT
        )
        if not is_best_capture and move_flag(best_move) != FLAG_PROMOTION:
            for move in ordered:
                if move == best_move:
                    break
                flag = move_flag(move)
                to = move_to_sq(move)
                if board.mailbox[to] == _NPT and flag not in {FLAG_EN_PASSANT, FLAG_PROMOTION}:
                    frm = move_from_sq(move)
                    history_row[frm][to] = _clamp_history(history_row[frm][to] - history_delta)
                    if prev != MOVE_NONE:
                        ss.cont_hist[prev_to][to] = _clamp_history(
                            ss.cont_hist[prev_to][to] - history_delta
                        )
                    if cont_hist2_row is not None:
                        cont_hist2_row[to] = _clamp_history(cont_hist2_row[to] - history_delta)
                elif board.mailbox[to] != _NPT and flag not in {FLAG_EN_PASSANT, FLAG_PROMOTION}:
                    to = move_to_sq(move)
                    attacker_pt = board.mailbox[move_from_sq(move)]
                    cap_pt = board.mailbox[to]
                    ss.cap_hist[attacker_pt][to][cap_pt] = _clamp_history(
                        ss.cap_hist[attacker_pt][to][cap_pt] - history_delta
                    )
                elif flag == FLAG_EN_PASSANT:
                    to = move_to_sq(move)
                    attacker_pt = board.mailbox[move_from_sq(move)]
                    ss.cap_hist[attacker_pt][to][PAWN] = _clamp_history(
                        ss.cap_hist[attacker_pt][to][PAWN] - history_delta
                    )

    if not ss.stopped:
        if best_score >= beta:
            tt_flag = TT_BETA
        elif best_score > orig_alpha:
            tt_flag = TT_EXACT
        else:
            tt_flag = TT_ALPHA
        ss.tt.store(
            board.hash,
            depth,
            _score_to_tt(best_score, ss.ply),
            tt_flag,
            best_move,
        )

        # Update correction history when we have a reliable score from a
        # non-pruned search (best_move found means we searched ≥1 move).
        if not in_check and best_move != MOVE_NONE:
            delta = max(-512, min(512, best_score - raw_eval))
            old_corr = ss.corr_hist[board.side][ph]
            ss.corr_hist[board.side][ph] = max(
                -32768,
                min(32768, old_corr + delta * 16 - old_corr * 16 // 1024),
            )

    return best_score


# ---------------------------------------------------------------------------
# Iterative deepening with aspiration windows  (public entry point)
# ---------------------------------------------------------------------------


def search(
    board: Board,
    *,
    params: SearchParams | None = None,
    evaluator: Evaluator | None = None,
    tt: TranspositionTable | None = None,
    stop_event: threading.Event | None = None,
    info_cb: Callable[[str], None] | None = None,
    ponder_switch: list[_SS] | None = None,
    history_tables: HistoryTables | None = None,
    syzygy: SyzygyTablebase | None = None,
    syzygy_probe_depth: int = 1,
    syzygy_probe_limit: int = 7,
    syzygy_50_move_rule: bool = True,
) -> SearchResult:
    """Find the best move using iterative-deepening alpha-beta search.

    *ponder_switch* — if provided, must be a single-element list.  The
    internal ``_SS`` object will be stored into ``ponder_switch[0]`` so
    the caller (UCI layer) can invoke ``ss.switch_from_ponder()`` on a
    ``ponderhit`` command.

    *history_tables* — persistent history from previous searches.  When
    provided, the tables are aged (halved) at the start of the call and
    updated in-place during the search so they carry useful information
    into future calls.
    """

    if params is None:
        params = SearchParams()
        params.depth = 6
    if evaluator is None:
        evaluator = create_evaluator()
    if tt is None:
        tt = TranspositionTable()
    if stop_event is None:
        stop_event = _threading.Event()

    # Age history tables to decay stale information from prior searches.
    if history_tables is not None:
        history_tables.age()

    ss = _SS(
        board,
        params,
        evaluator,
        tt,
        stop_event,
        info_cb,
        history_tables,
        syzygy,
        syzygy_probe_depth,
        syzygy_probe_limit,
        syzygy_50_move_rule,
    )
    if ponder_switch is not None:
        ponder_switch.append(ss)

    # Quick exit when there are zero or one legal moves
    legal_moves = generate_legal_moves(board)
    if not legal_moves:
        return SearchResult()

    tb_result = _root_syzygy_result(
        board,
        legal_moves,
        syzygy,
        syzygy_probe_limit,
        syzygy_50_move_rule,
    )
    if tb_result is not None:
        ss.tb_hits += 1
        if info_cb is not None:
            info = (
                f"info depth 0 seldepth 0 {_format_score(tb_result.score)} "
                f"nodes {tb_result.nodes} nps 0 hashfull {tt.hashfull()} "
                f"tbhits {ss.tb_hits} time 0"
            )
            info_cb(_info_with_pv(info, tb_result.pv))
        return tb_result

    if len(legal_moves) == 1:
        return SearchResult(bestmove=legal_moves[0], score=0, depth=1, nodes=1, pv=[legal_moves[0]])

    best_result = SearchResult()
    prev_score = 0
    max_depth = max(1, min(params.depth, MAX_DEPTH))
    prev_best_move = MOVE_NONE
    best_stability = 0

    for depth in range(1, max_depth + 1):
        ss.ply = 0
        ss.seldepth = 0

        # Aspiration windows. Once the previous score is mate-like, search with
        # a full window so deeper iterations can still improve the mate length.
        delta = ASPIRATION_WINDOW
        if depth >= 4 and abs(prev_score) < MATE_SCORE - MAX_PLY:
            alpha = max(-INFINITY, prev_score - delta)
            beta = min(INFINITY, prev_score + delta)
        else:
            alpha = -INFINITY
            beta = INFINITY

        while True:
            score = _negamax(ss, depth, alpha, beta)
            if ss.stopped:
                break
            if score <= alpha:
                alpha = max(-INFINITY, alpha - delta)
                delta *= 4
            elif score >= beta:
                beta = min(INFINITY, beta + delta)
                delta *= 4
            else:
                break

        if ss.stopped and depth > 1:
            break

        # Extract PV from TT
        pv = _extract_pv(board, tt, depth)

        best_result = SearchResult(
            bestmove=pv[0] if pv else MOVE_NONE,
            score=score,
            depth=depth,
            nodes=ss.nodes,
            pv=pv,
        )
        prev_score = score

        # Track best-move stability for adaptive soft time management
        cur_best = best_result.bestmove
        if cur_best == prev_best_move:
            best_stability += 1
        else:
            best_stability = 0
            prev_best_move = cur_best

        # Send UCI info
        if info_cb is not None:
            elapsed = ss.elapsed_ms()
            nps = int(ss.nodes / (elapsed / 1000)) if elapsed > 0 else 0
            hf = tt.hashfull()
            info_str = (
                f"info depth {depth} seldepth {ss.seldepth} "
                f"{_format_score(score)} nodes {ss.nodes} nps {nps} "
                f"hashfull {hf}"
            )
            if ss.syzygy is not None:
                info_str += f" tbhits {ss.tb_hits}"
            info_str += f" time {elapsed}"
            info_cb(_info_with_pv(info_str, pv))

        # Do not stop at the first forced mate. A deeper iteration may find a
        # shorter mating net; only mate-in-1 cannot be improved.
        if score >= MATE_SCORE - 1:
            break

        # Adaptive soft time: fewer iterations when the best move is stable.
        # stability=0 → 100 % of soft limit; stability≥6 → ~64 % of soft limit.
        if ss.soft_limit > 0:
            stability_scale = 1.0 - 0.06 * min(best_stability, 6)
            if time.perf_counter() - ss.start_time >= ss.soft_limit * stability_scale:
                if ss.pondering:
                    ss.stop_on_ponderhit = True
                else:
                    break

    # Fallback if no completed iteration
    if best_result.bestmove == MOVE_NONE and legal_moves:
        best_result.bestmove = legal_moves[0]

    return best_result


# ---------------------------------------------------------------------------
# ChessAgents stdin/stdout adapter
# ---------------------------------------------------------------------------

_AGENT_MOVETIME_MS = 2200
_AGENT_MOVE_OVERHEAD_MS = 100
_AGENT_HASH_MB = 12


def _position_key_fields(board: Board) -> list[str]:
    fields = board.to_fen().split()
    return fields[:3]


def _rebuild_board(fen: str, history: list[str]) -> Board:
    board = Board.from_fen(fen)
    if not history:
        return board

    # ChessAgents supplies the full move list from the initial position. Replay it
    # so Board.history contains prior hashes for repetition detection.
    replay = Board.from_fen(STARTING_FEN)
    for uci in history:
        legal = generate_legal_moves(replay)
        move = uci_to_move(uci, legal)
        if move == MOVE_NONE:
            return board
        replay.make_move(move)

    # Trust the FEN for clocks, but use replay when it matches the actual position.
    if _position_key_fields(replay) == _position_key_fields(board):
        replay.ep_square = board.ep_square
        replay.halfmove = board.halfmove
        replay.fullmove = board.fullmove
        replay._init_hash()
        replay._check_cache_key = -1
        return replay
    return board


def _choose_move(line: str) -> str:
    parts = line.strip().split()
    if len(parts) < 6:
        return "0000"

    fen = " ".join(parts[:6])
    moves_idx = parts.index("moves") if "moves" in parts[6:] else -1
    history = parts[moves_idx + 1 :] if moves_idx >= 0 else []

    board = _rebuild_board(fen, history)
    legal = generate_legal_moves(board)
    if not legal:
        return "0000"
    if len(legal) == 1:
        return move_to_uci(legal[0])

    params = SearchParams()
    params.movetime = _AGENT_MOVETIME_MS
    params.move_overhead = _AGENT_MOVE_OVERHEAD_MS

    result = search(
        board,
        params=params,
        evaluator=create_evaluator(),
        tt=TranspositionTable(_AGENT_HASH_MB),
        stop_event=threading.Event(),
        info_cb=None,
        syzygy=None,
        syzygy_probe_limit=0,
    )
    move = result.bestmove if result.bestmove in legal else legal[0]
    return move_to_uci(move)


def main() -> None:
    line = sys.stdin.readline()
    try:
        move = _choose_move(line)
    except Exception:
        move = "0000"
    sys.stdout.write(move + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
