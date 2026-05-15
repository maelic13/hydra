"""Bitboard manipulation utilities and precomputed masks.

All bitboards are plain Python ``int`` values, masked to 64 bits where
necessary with ``& BB_ALL``.  This avoids numpy overhead for scalar ops
and still gives fast bitwise operations.
"""

from __future__ import annotations

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
