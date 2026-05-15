"""Precomputed attack tables for all piece types.

* **Leapers** (knight, king, pawn): simple 64-entry lookup tables.
* **Sliders** (rook, bishop, queen): magic-bitboard indexed tables.

All tables are initialised at module import time.
"""

from __future__ import annotations

from hydra.bitboard import (
    BB_ALL,
    BB_NOT_FILE_A,
    BB_NOT_FILE_AB,
    BB_NOT_FILE_GH,
    BB_NOT_FILE_H,
    BB_SQUARES,
    shift_east,
    shift_north,
    shift_north_east,
    shift_north_west,
    shift_south,
    shift_south_east,
    shift_south_west,
    shift_west,
)
from hydra.types import BLACK, WHITE

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
    from hydra.types import BISHOP, KING, KNIGHT, PAWN, QUEEN, ROOK

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
