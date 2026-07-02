"""Classical hand-crafted evaluation framework."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NamedTuple, Protocol

from hydra.attacks import (
    BISHOP_MAGICS,
    BISHOP_SHIFTS,
    KING_ATTACKS,
    KNIGHT_ATTACKS,
    PAWN_ATTACKS,
    ROOK_MAGICS,
    ROOK_SHIFTS,
    _bishop_masks,
    _bishop_table,
    _rook_masks,
    _rook_table,
)
from hydra.bitboard import BB_ALL
from hydra.tuned_eval import TUNED_WEIGHTS

if TYPE_CHECKING:
    from hydra.board import Board


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

    def evaluate(self, board: Board, alpha: int = 0, beta: int = 0, lazy_margin: int = 0) -> int:
        """Static eval in centipawns (side-to-move POV).

        When ``lazy_margin > 0`` and ``beta > alpha``, a backend may return a
        cheap approximation if it is more than ``lazy_margin`` outside the window.
        """
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


# Flat material+PST lookup arrays (mg_w/mg_b/eg_w/eg_b) are built per-weight-set
# inside EvalParams.rebuild() so they track Texel-tuned values; see EvalParams.

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
# King-safety MG penalty curve params (quadratic, capped); table built in EvalParams.
_KS_CAP = 500
_KS_QUAD_DIV = 4
_KS_LIN_MUL = 3

# Endgame scale factor: eg is scaled by scale/_SCALE_NORMAL (Phase 3.3). Rule-50
# damping multiplies the final score by r50/_RULE50_BASE.
_SCALE_NORMAL = 64
_RULE50_BASE = 128

# ---------------------------------------------------------------------------
# Precomputed masks
# ---------------------------------------------------------------------------

_FILE_BB: tuple[int, ...] = tuple(0x0101_0101_0101_0101 << f for f in range(8))

_ADJ_FILE_BB: tuple[int, ...] = tuple(
    (_FILE_BB[f - 1] if f > 0 else 0) | (_FILE_BB[f + 1] if f < 7 else 0) for f in range(8)
)

_FILE_A_BB = _FILE_BB[0]
_FILE_H_BB = _FILE_BB[7]

# Flank masks for the winnable/initiative term (files a-d vs e-h).
_QUEENSIDE_BB = _FILE_BB[0] | _FILE_BB[1] | _FILE_BB[2] | _FILE_BB[3]
_KINGSIDE_BB = _FILE_BB[4] | _FILE_BB[5] | _FILE_BB[6] | _FILE_BB[7]

# Square-colour masks (bad bishop) and central space areas (Phase 3.6).
_LIGHT_SQ = sum(1 << sq for sq in range(64) if ((sq >> 3) + (sq & 7)) & 1)
_DARK_SQ = 0xFFFF_FFFF_FFFF_FFFF ^ _LIGHT_SQ
_CENTER_FILES = _FILE_BB[2] | _FILE_BB[3] | _FILE_BB[4] | _FILE_BB[5]
_SPACE_W = _CENTER_FILES & 0x0000_0000_FFFF_FF00  # ranks 2-4 (white side, in front of pawns)
_SPACE_B = _CENTER_FILES & 0x00FF_FFFF_0000_0000  # ranks 5-7 (black side)

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


def _eval_pawns(w_pawns: int, b_pawns: int, p: EvalParams) -> tuple[int, int, int, int]:
    """Evaluate pawn structure; returns ``(mg, eg, passed_w_bb, passed_b_bb)``.

    Covers: doubled, isolated, connected, backward, and passed pawns.
    Results are cached by the caller via the pawn hash (one cache per weight set).
    """
    mg = eg = passed_w = passed_b = 0
    doubled_mg, doubled_eg = p.doubled_mg, p.doubled_eg
    isolated_mg, isolated_eg = p.isolated_mg, p.isolated_eg
    connected_mg, connected_eg = p.connected_mg, p.connected_eg
    backward_mg, backward_eg = p.backward_mg, p.backward_eg
    passed_mg, passed_eg = p.passed_mg, p.passed_eg

    # Doubled and isolated penalties (file loop is faster for these)
    for f in range(8):
        fbb = _FILE_BB[f]
        adj = _ADJ_FILE_BB[f]
        wc = (w_pawns & fbb).bit_count()
        bc = (b_pawns & fbb).bit_count()
        if wc > 1:
            d = wc - 1
            mg += d * doubled_mg
            eg += d * doubled_eg
        if bc > 1:
            d = bc - 1
            mg -= d * doubled_mg
            eg -= d * doubled_eg
        if wc and not (w_pawns & adj):
            mg += wc * isolated_mg
            eg += wc * isolated_eg
        if bc and not (b_pawns & adj):
            mg -= bc * isolated_mg
            eg -= bc * isolated_eg

    # Per-pawn features: passed, connected, backward
    bb = w_pawns
    while bb:
        sq = (bb & -bb).bit_length() - 1
        if not (b_pawns & _PASSED_W[sq]):
            r = sq >> 3
            mg += passed_mg[r]
            eg += passed_eg[r]
            passed_w |= 1 << sq
        if w_pawns & _PAWN_CONNECTED_W[sq]:
            mg += connected_mg
            eg += connected_eg
        stop = sq + 8
        if (
            stop < 64
            and (b_pawns & _PAWN_ATK[0][stop])  # enemy pawn controls our stop sq
            and not (w_pawns & _BACKWARD_SUPPORT_W[sq])
        ):
            mg += backward_mg
            eg += backward_eg
        bb &= bb - 1

    bb = b_pawns
    while bb:
        sq = (bb & -bb).bit_length() - 1
        if not (w_pawns & _PASSED_B[sq]):
            r = 7 - (sq >> 3)
            mg -= passed_mg[r]
            eg -= passed_eg[r]
            passed_b |= 1 << sq
        if b_pawns & _PAWN_CONNECTED_B[sq]:
            mg -= connected_mg
            eg -= connected_eg
        stop = sq - 8
        if (
            stop >= 0
            and (w_pawns & _PAWN_ATK[1][stop])  # white pawn controls black's stop sq
            and not (b_pawns & _BACKWARD_SUPPORT_B[sq])
        ):
            mg -= backward_mg
            eg -= backward_eg
        bb &= bb - 1

    return mg, eg, passed_w, passed_b


# ---------------------------------------------------------------------------
# Eval coefficient trace (Phase 1.3) — for the Texel gradient (Phase 4)
#
# The classical eval is linear in nearly all its weights, so it can be written
# as  score = (Σ cmg[k]·w_k + res_mg)·phase + (Σ ceg[k]·w_k + res_eg)·(24-phase)
#             ────────────────────────────────────────────────────────────── + tempo
#                                          24
# where each coefficient key k is an (EvalParams-attribute, *indices) tuple and
# cmg/ceg are signed white-minus-black application counts. The two terms that are
# NOT linear in their weights — king safety (quadratic table lookup) and endgame
# king centralization (float truncation) — are carried as fixed residuals so
# reconstruction is exact; Phase 4 tunes those by finite difference.
# ---------------------------------------------------------------------------


class EvalTrace(NamedTuple):
    cmg: dict[tuple, int]  # mg-weight coefficients (key -> signed count)
    ceg: dict[tuple, int]  # eg-weight coefficients
    residual_mg: int  # king-safety mg delta (nonlinear)
    residual_eg: int  # eg king-centralization (truncation-nonlinear)
    phase: int
    white_to_move: bool
    eg_scale: int = _SCALE_NORMAL  # Phase 3.3 eg scale factor (identity default)
    winnable: int = 0  # Phase 3.3 additive winnable/initiative
    r50_num: int = _RULE50_BASE  # Phase 3.3 rule-50 damping numerator


def _weight_of(p: EvalParams, key: tuple) -> int:
    """Fetch a scalar weight from EvalParams given an (attr, *indices) key."""
    val = getattr(p, key[0])
    for idx in key[1:]:
        val = val[idx]
    return val


def _add(d: dict[tuple, int], key: tuple, n: int) -> None:
    if n:
        d[key] = d.get(key, 0) + n


def _trace_pawns(w_pawns: int, b_pawns: int, cmg: dict, ceg: dict) -> tuple[int, int]:
    """Mirror of _eval_pawns that accumulates coefficients; returns passed bbs."""
    passed_w = passed_b = 0
    for f in range(8):
        fbb = _FILE_BB[f]
        adj = _ADJ_FILE_BB[f]
        wc = (w_pawns & fbb).bit_count()
        bc = (b_pawns & fbb).bit_count()
        if wc > 1:
            _add(cmg, ("doubled_mg",), wc - 1)
            _add(ceg, ("doubled_eg",), wc - 1)
        if bc > 1:
            _add(cmg, ("doubled_mg",), -(bc - 1))
            _add(ceg, ("doubled_eg",), -(bc - 1))
        if wc and not (w_pawns & adj):
            _add(cmg, ("isolated_mg",), wc)
            _add(ceg, ("isolated_eg",), wc)
        if bc and not (b_pawns & adj):
            _add(cmg, ("isolated_mg",), -bc)
            _add(ceg, ("isolated_eg",), -bc)

    bb = w_pawns
    while bb:
        sq = (bb & -bb).bit_length() - 1
        if not (b_pawns & _PASSED_W[sq]):
            r = sq >> 3
            _add(cmg, ("passed_mg", r), 1)
            _add(ceg, ("passed_eg", r), 1)
            passed_w |= 1 << sq
        if w_pawns & _PAWN_CONNECTED_W[sq]:
            _add(cmg, ("connected_mg",), 1)
            _add(ceg, ("connected_eg",), 1)
        stop = sq + 8
        if (
            stop < 64
            and (b_pawns & _PAWN_ATK[0][stop])
            and not (w_pawns & _BACKWARD_SUPPORT_W[sq])
        ):
            _add(cmg, ("backward_mg",), 1)
            _add(ceg, ("backward_eg",), 1)
        bb &= bb - 1

    bb = b_pawns
    while bb:
        sq = (bb & -bb).bit_length() - 1
        if not (w_pawns & _PASSED_B[sq]):
            r = 7 - (sq >> 3)
            _add(cmg, ("passed_mg", r), -1)
            _add(ceg, ("passed_eg", r), -1)
            passed_b |= 1 << sq
        if b_pawns & _PAWN_CONNECTED_B[sq]:
            _add(cmg, ("connected_mg",), -1)
            _add(ceg, ("connected_eg",), -1)
        stop = sq - 8
        if (
            stop >= 0
            and (w_pawns & _PAWN_ATK[1][stop])
            and not (b_pawns & _BACKWARD_SUPPORT_B[sq])
        ):
            _add(cmg, ("backward_mg",), -1)
            _add(ceg, ("backward_eg",), -1)
        bb &= bb - 1

    return passed_w, passed_b


def reconstruct_eval(tr: EvalTrace, p: EvalParams) -> int:
    """Rebuild the side-to-move eval from a trace + a weight set (Phase 1.3 gate)."""
    mg = tr.residual_mg + sum(c * _weight_of(p, k) for k, c in tr.cmg.items())
    eg = tr.residual_eg + sum(c * _weight_of(p, k) for k, c in tr.ceg.items())
    eg_w = eg * (_TOTAL_PHASE - tr.phase) * tr.eg_scale // _SCALE_NORMAL
    score = (mg * tr.phase + eg_w) // _TOTAL_PHASE + p.tempo + tr.winnable
    score = score * tr.r50_num // _RULE50_BASE
    return score if tr.white_to_move else -score


def _king_danger_extra(
    p: EvalParams,
    my_n: int,
    my_b: int,
    my_r: int,
    my_q: int,
    my_full: int,
    their_full: int,
    eksq: int,
    e_zone: int,
    occ: int,
    my_occ: int,
    my_queens: int,
) -> int:
    """King-safety-v2 danger beyond the base attacker units, for one attacking side.

    Adds safe checks (a check square our piece attacks that the enemy does not
    defend and we do not block), king-ring weak squares (enemy king-zone squares
    we attack that the enemy does not defend), and a no-queen attenuation. All
    weights seed to 0, so the returned danger is 0 by default (king safety
    unchanged). Called by both evaluate() and trace() so the residual matches.
    """
    safe = ~their_full & ~my_occ
    n_check = KNIGHT_ATTACKS[eksq]
    b_check = _bishop_atk(eksq, occ)
    r_check = _rook_atk(eksq, occ)
    d = (n_check & my_n & safe).bit_count() * p.safe_check_knight
    d += (b_check & my_b & safe).bit_count() * p.safe_check_bishop
    d += (r_check & my_r & safe).bit_count() * p.safe_check_rook
    d += ((b_check | r_check) & my_q & safe).bit_count() * p.safe_check_queen
    d += (e_zone & my_full & ~their_full).bit_count() * p.king_weak_square
    if not my_queens:
        d -= p.no_queen_atten
    return d


def _scale_factor(board: Board, p: EvalParams) -> int:
    """Endgame scale for the eg score (Phase 3.3). Only opposite-coloured-bishop
    endings scale (to ``p.ocb_scale``); everything else is _SCALE_NORMAL."""
    pieces = board.pieces
    if (
        pieces[0][2].bit_count() == 1
        and pieces[1][2].bit_count() == 1
        and not (
            pieces[0][1] | pieces[0][3] | pieces[0][4] | pieces[1][1] | pieces[1][3] | pieces[1][4]
        )
    ):
        wb = (pieces[0][2] & -pieces[0][2]).bit_length() - 1
        bb_ = (pieces[1][2] & -pieces[1][2]).bit_length() - 1
        if (((wb >> 3) ^ (wb & 7)) & 1) != (((bb_ >> 3) ^ (bb_ & 7)) & 1):
            return p.ocb_scale
    return _SCALE_NORMAL


def _winnable(board: Board, p: EvalParams) -> int:
    """Initiative/winnable correction (Phase 3.3), white-POV additive. Seeded 0."""
    all_pawns = board.pieces[0][0] | board.pieces[1][0]
    both_flanks = 1 if (all_pawns & _QUEENSIDE_BB) and (all_pawns & _KINGSIDE_BB) else 0
    return (
        p.winnable_const
        + p.winnable_pawn * all_pawns.bit_count()
        + p.winnable_flanks * both_flanks
    )


def _final_transform(p: EvalParams, board: Board) -> tuple[int, int, int]:
    """Return (eg_scale, winnable, rule50_numerator) for the final-score transform.

    Seeded identity: (_SCALE_NORMAL, 0, _RULE50_BASE). Called by both evaluate()
    and trace() so the reconstruction matches when these are later tuned.
    """
    eg_scale = _scale_factor(board, p) if p.scale_active else _SCALE_NORMAL
    winnable = _winnable(board, p) if p.winnable_active else 0
    r50_num = _RULE50_BASE
    if p.rule50_damp:
        r50_num = max(0, _RULE50_BASE - p.rule50_damp * board.halfmove // 100)
    return eg_scale, winnable, r50_num


def _passer_counts(board: Board, atk_full: list[int], passed_w: int, passed_b: int) -> tuple:
    """Passed-pawn richness counts (Phase 3.4), white-minus-black.

    Returns (blocked, free, ekdist, protected):
      blocked   - stop square occupied by an enemy piece;
      free      - stop square empty and not attacked by the enemy;
      ekdist    - enemy-king Chebyshev distance to the queening square (summed);
      protected - passer defended by a friendly pawn.
    """
    pieces = board.pieces
    occ = board.all_occ
    occ_w, occ_b = board.occupancy[0], board.occupancy[1]
    w_pawns, b_pawns = pieces[0][0], pieces[1][0]
    wk, bk = board.king_sq(0), board.king_sq(1)
    wkf, wkr, bkf, bkr = wk & 7, wk >> 3, bk & 7, bk >> 3
    blocked = free = ekdist = protected = 0
    bb = passed_w
    while bb:
        sq = (bb & -bb).bit_length() - 1
        stopbb = 1 << (sq + 8)
        if occ_b & stopbb:
            blocked += 1
        elif not (occ & stopbb) and not (atk_full[1] & stopbb):
            free += 1
        if w_pawns & _PAWN_ATK[1][sq]:
            protected += 1
        ekdist += max(abs(bkf - (sq & 7)), abs(bkr - 7))
        bb &= bb - 1
    bb = passed_b
    while bb:
        sq = (bb & -bb).bit_length() - 1
        stopbb = 1 << (sq - 8)
        if occ_w & stopbb:
            blocked -= 1
        elif not (occ & stopbb) and not (atk_full[0] & stopbb):
            free -= 1
        if b_pawns & _PAWN_ATK[0][sq]:
            protected -= 1
        ekdist -= max(abs(wkf - (sq & 7)), wkr)
        bb &= bb - 1
    return blocked, free, ekdist, protected


def _imbalance_terms(pieces: list[list[int]]) -> tuple:
    """Material-imbalance count-products (Phase 3.5), white-minus-black:
    (knights*pawns, rooks*pawns, bishops*pawns)."""
    wp, bp = pieces[0][0].bit_count(), pieces[1][0].bit_count()
    wn, bn = pieces[0][1].bit_count(), pieces[1][1].bit_count()
    wbi, bbi = pieces[0][2].bit_count(), pieces[1][2].bit_count()
    wr, br = pieces[0][3].bit_count(), pieces[1][3].bit_count()
    return (wn * wp - bn * bp, wr * wp - br * bp, wbi * wp - bbi * bp)


def _minor_terms(
    pieces: list[list[int]],
    w_pawns: int,
    b_pawns: int,
    w_pawn_atk: int,
    b_pawn_atk: int,
    atk_rook: list[int],
) -> tuple:
    """Space / bad-bishop / connected-rooks counts (Phase 3.6), white-minus-black.

    space     - safe central squares in own half (not attacked by an enemy pawn);
    bad       - own pawns on a bishop's own colour, summed over bishops;
    connected - a side's rooks defend each other (flag).
    """
    space = (_SPACE_W & ~b_pawn_atk).bit_count() - (_SPACE_B & ~w_pawn_atk).bit_count()
    wbl = (pieces[0][2] & _LIGHT_SQ).bit_count()
    wbd = (pieces[0][2] & _DARK_SQ).bit_count()
    bbl = (pieces[1][2] & _LIGHT_SQ).bit_count()
    bbd = (pieces[1][2] & _DARK_SQ).bit_count()
    bad = (
        wbl * (w_pawns & _LIGHT_SQ).bit_count()
        + wbd * (w_pawns & _DARK_SQ).bit_count()
        - bbl * (b_pawns & _LIGHT_SQ).bit_count()
        - bbd * (b_pawns & _DARK_SQ).bit_count()
    )
    cr = (1 if atk_rook[0] & pieces[0][3] else 0) - (1 if atk_rook[1] & pieces[1][3] else 0)
    return space, bad, cr


# ---------------------------------------------------------------------------
# Tunable evaluation weights
#
# Every magic number the eval uses lives here so the Phase 4 Texel campaign can
# fit them. Defaults are pulled directly from the module literals above, so a
# default EvalParams() reproduces the historical eval bit-for-bit (verified by
# tools/eval_equiv.py). Structural masks (files, zones, passed-pawn spans) are
# geometry, not weights, and stay module-level. PIECE_VALUES used by search
# move-ordering live in hydra.engine and are intentionally separate.
# ---------------------------------------------------------------------------


class EvalParams:
    """Mutable evaluation weight set. ``ClassicalEvaluator`` reads from one."""

    def __init__(self) -> None:
        # Material (mg/eg, indexed by piece type P N B R Q K)
        self.mg_val = list(_MG_VAL)
        self.eg_val = list(_EG_VAL)
        # Piece-square tables, white a1-first (mg uses king-mg, eg uses king-eg)
        self.pst_mg = [list(t) for t in _MG_PST]
        self.pst_eg = [list(t) for t in _EG_PST]
        # Pawn structure
        self.doubled_mg, self.doubled_eg = _DOUBLED_MG, _DOUBLED_EG
        self.isolated_mg, self.isolated_eg = _ISOLATED_MG, _ISOLATED_EG
        self.connected_mg, self.connected_eg = _CONNECTED_MG, _CONNECTED_EG
        self.backward_mg, self.backward_eg = _BACKWARD_MG, _BACKWARD_EG
        self.passed_mg = list(_PASSED_MG)
        self.passed_eg = list(_PASSED_EG)
        # Pieces
        self.bishop_pair_mg, self.bishop_pair_eg = _BISHOP_PAIR_MG, _BISHOP_PAIR_EG
        self.rook_open_mg, self.rook_open_eg = _ROOK_OPEN_MG, _ROOK_OPEN_EG
        self.rook_semi_mg, self.rook_semi_eg = _ROOK_SEMI_MG, _ROOK_SEMI_EG
        self.rook_7th_mg, self.rook_7th_eg = _ROOK_7TH_MG, _ROOK_7TH_EG
        self.rook_behind_passed_mg = _ROOK_BEHIND_PASSED_MG
        self.rook_behind_passed_eg = _ROOK_BEHIND_PASSED_EG
        self.outpost_mg, self.outpost_eg = _OUTPOST_MG, _OUTPOST_EG
        self.pawn_threat_mg, self.pawn_threat_eg = _PAWN_THREAT_MG, _PAWN_THREAT_EG
        # Piece threats (Phase 3.1 — seeded inert = 0, tuned in Phase 4)
        self.threat_minor_major_mg = 0
        self.threat_minor_major_eg = 0
        self.threat_rook_queen_mg = 0
        self.threat_rook_queen_eg = 0
        self.threat_weak_mg = 0
        self.threat_weak_eg = 0
        # Mobility (per safe-square count)
        self.knight_mob_mg = list(_KNIGHT_MOB_MG)
        self.knight_mob_eg = list(_KNIGHT_MOB_EG)
        self.bishop_mob_mg = list(_BISHOP_MOB_MG)
        self.bishop_mob_eg = list(_BISHOP_MOB_EG)
        self.rook_mob_mg = list(_ROOK_MOB_MG)
        self.rook_mob_eg = list(_ROOK_MOB_EG)
        self.queen_mob_mg = list(_QUEEN_MOB_MG)
        self.queen_mob_eg = list(_QUEEN_MOB_EG)
        # King safety
        self.atk_weight = list(_ATK_WEIGHT)
        self.ks_cap, self.ks_quad_div, self.ks_lin_mul = _KS_CAP, _KS_QUAD_DIV, _KS_LIN_MUL
        # King-safety v2 danger components (Phase 3.2 — seeded inert = 0, tuned in
        # Phase 4.3 by finite difference since king safety is nonlinear).
        self.safe_check_knight = 0
        self.safe_check_bishop = 0
        self.safe_check_rook = 0
        self.safe_check_queen = 0
        self.king_weak_square = 0
        self.no_queen_atten = 0
        # Scale factors / winnable / rule-50 (Phase 3.3 — seeded inert: scale &
        # winnable disabled, rule50 damping off → eval unchanged. Nonlinear/
        # conditional → tuned by finite difference in Phase 4).
        self.scale_active = False
        self.ocb_scale = _SCALE_NORMAL  # <_SCALE_NORMAL = drawish opposite-coloured bishops
        self.winnable_active = False
        self.winnable_const = 0
        self.winnable_pawn = 0  # per pawn on the board
        self.winnable_flanks = 0  # bonus when pawns are on both flanks
        self.rule50_damp = 0  # >0 damps the score as the halfmove clock climbs
        # Passed-pawn richness (Phase 3.4 — seeded inert = 0, tuned in Phase 4).
        self.passed_blocked_mg = 0  # stop square occupied by an enemy piece
        self.passed_blocked_eg = 0
        self.passed_free_mg = 0  # stop square empty and not attacked by the enemy
        self.passed_free_eg = 0
        self.passed_protected_mg = 0  # passer defended by a friendly pawn
        self.passed_protected_eg = 0
        self.passed_ekdist_eg = 0  # per unit of enemy-king distance to the queening square
        # Material imbalance (Phase 3.5 — piece value adjusts with own pawn count;
        # seeded inert = 0, tuned in Phase 4). Applied equally to mg and eg.
        self.imb_knight_pawn = 0  # knights gain value with more pawns
        self.imb_rook_pawn = 0  # rooks lose value with more pawns
        self.imb_bishop_pawn = 0  # bishops lose value with more pawns
        # Space + minor positional terms (Phase 3.6 — seeded inert = 0).
        self.space_mg = 0  # safe central squares in own half (mg only)
        self.bad_bishop_mg = 0  # own pawns on the bishop's own colour
        self.bad_bishop_eg = 0
        self.connected_rooks_mg = 0  # rooks that defend each other
        self.connected_rooks_eg = 0
        # Misc
        self.pawn_shield = _PAWN_SHIELD
        self.eg_king_center = _EG_KING_CENTER
        self.king_passer_prox = 2  # eg bonus per (7 - king distance) to own passer
        self.tempo = _TEMPO
        # Overlay the SPRT-passed Texel weights baked into hydra/tuned_eval.py
        # (empty tuple until the first bake; kept in a separate uncompiled module
        # because a large literal blows the C-compiler limits under mypyc).
        for attr, idxs, value in TUNED_WEIGHTS:
            if idxs:
                container = getattr(self, attr)
                for i in idxs[:-1]:
                    container = container[i]
                container[idxs[-1]] = value
            else:
                setattr(self, attr, value)
        self.rebuild()

    def rebuild(self) -> None:
        """Recompute derived lookup tables after any weight change."""
        mg_val, eg_val, pst_mg, pst_eg = self.mg_val, self.eg_val, self.pst_mg, self.pst_eg
        self.mg_w = tuple(mg_val[pt] + pst_mg[pt][sq] for pt in range(6) for sq in range(64))
        self.mg_b = tuple(mg_val[pt] + pst_mg[pt][sq ^ 56] for pt in range(6) for sq in range(64))
        self.eg_w = tuple(eg_val[pt] + pst_eg[pt][sq] for pt in range(6) for sq in range(64))
        self.eg_b = tuple(eg_val[pt] + pst_eg[pt][sq ^ 56] for pt in range(6) for sq in range(64))
        self.king_safety = tuple(
            min(self.ks_cap, i * i // self.ks_quad_div + i * self.ks_lin_mul) for i in range(100)
        )
        # Skip inert additive terms in evaluate() (they cost nothing until tuned).
        self.threats_active = bool(
            self.threat_minor_major_mg
            or self.threat_minor_major_eg
            or self.threat_rook_queen_mg
            or self.threat_rook_queen_eg
            or self.threat_weak_mg
            or self.threat_weak_eg
        )
        self.ks_v2_active = bool(
            self.safe_check_knight
            or self.safe_check_bishop
            or self.safe_check_rook
            or self.safe_check_queen
            or self.king_weak_square
            or self.no_queen_atten
        )
        self.passers_v2_active = bool(
            self.passed_blocked_mg
            or self.passed_blocked_eg
            or self.passed_free_mg
            or self.passed_free_eg
            or self.passed_protected_mg
            or self.passed_protected_eg
            or self.passed_ekdist_eg
        )
        self.imbalance_active = bool(
            self.imb_knight_pawn or self.imb_rook_pawn or self.imb_bishop_pawn
        )
        self.minor_terms_active = bool(
            self.space_mg
            or self.bad_bishop_mg
            or self.bad_bishop_eg
            or self.connected_rooks_mg
            or self.connected_rooks_eg
        )


# Shared default weight set. The live engine's evaluator AND the Board's
# incremental PSQT accumulators both reference THIS instance, so the fast eval
# path reads board.mg_acc/eg_acc directly. A custom weight set (Texel) gets a
# fresh EvalParams and takes the recompute path.
DEFAULT_EVAL_PARAMS = EvalParams()


def _apply_eval_overrides(p: EvalParams, path: str) -> None:
    """Apply ``attr [idx ...] value`` weight overrides to *p* in place.

    Dev/SPRT hook for the Phase 4 Texel campaign (``HYDRA_EVAL_FILE`` env var):
    loads a candidate weight set into a compiled build without recompiling, so an
    SPRT can pit the same binary with two weight sets. Gated by the env var, so
    the packaged release (which never sets it) is unaffected. Runs at import time,
    before ``board.py`` captures the derived PSQT arrays, keeping ``evaluate()``
    and the Board fast path consistent.
    """
    with open(path, encoding="utf-8") as fh:  # noqa: PTH123
        for raw in fh:
            fields = raw.split("#", 1)[0].split()
            if not fields:
                continue
            attr = fields[0]
            token = fields[-1]
            idxs = [int(x) for x in fields[1:-1]]
            value: object
            if attr.endswith("_active"):
                value = bool(int(token))
            elif "." in token:
                value = float(token)
            else:
                value = int(token)
            if idxs:
                container = getattr(p, attr)
                for i in idxs[:-1]:
                    container = container[i]
                container[idxs[-1]] = value
            else:
                setattr(p, attr, value)
    p.rebuild()


_EVAL_FILE = os.environ.get("HYDRA_EVAL_FILE")
if _EVAL_FILE:
    _apply_eval_overrides(DEFAULT_EVAL_PARAMS, _EVAL_FILE)


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

    def __init__(self, params: EvalParams | None = None) -> None:
        # Weight set. None -> the shared default (enables the Board fast path).
        self.p: EvalParams = params if params is not None else DEFAULT_EVAL_PARAMS
        # Pawn structure cache: pawn_hash -> (mg, eg, passed_w_bb, passed_b_bb)
        self._pawn_cache: dict[int, tuple[int, int, int, int]] = {}
        # Full eval result cache: board_hash -> eval score (side-to-move POV)
        self._eval_cache: dict[int, int] = {}

    def invalidate_caches(self) -> None:
        """Clear all eval caches (call on ucinewgame or evaluator reset)."""
        self._pawn_cache.clear()
        self._eval_cache.clear()

    def evaluate(self, board: Board, alpha: int = 0, beta: int = 0, lazy_margin: int = 0) -> int:
        key = board.hash
        cached = self._eval_cache.get(key)
        if cached is not None:
            return cached
        # Lazy eval: if the cheap part (material+PST+pawns+tempo) is already more
        # than lazy_margin outside the (alpha, beta) window, the expensive
        # mobility/king-safety terms can't change the cutoff decision, so skip
        # them. The approximate value is NOT cached (it isn't the true eval).
        if lazy_margin and beta > alpha:
            cheap = self._cheap_eval(board)
            if cheap >= beta + lazy_margin or cheap <= alpha - lazy_margin:
                return cheap
        result = self._evaluate_internal(board)
        if len(self._eval_cache) >= _EVAL_CACHE_MAX:
            self._eval_cache.clear()
        self._eval_cache[key] = result
        return result

    def _cheap_eval(self, board: Board) -> int:
        """Material+PST (accumulator) + pawn structure + tempo, side-to-move POV."""
        p = self.p
        phase = min(board.phase_acc, _TOTAL_PHASE)
        if p is DEFAULT_EVAL_PARAMS:
            mg = board.mg_acc
            eg = board.eg_acc
        else:
            mg = eg = 0
            mg_w, mg_b, eg_w, eg_b = p.mg_w, p.mg_b, p.eg_w, p.eg_b
            pieces = board.pieces
            for pt in range(6):
                off = pt * 64
                bb = pieces[0][pt]
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    mg += mg_w[off + sq]
                    eg += eg_w[off + sq]
                    bb &= bb - 1
                bb = pieces[1][pt]
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    mg -= mg_b[off + sq]
                    eg -= eg_b[off + sq]
                    bb &= bb - 1
        w_pawns = board.pieces[0][0]
        b_pawns = board.pieces[1][0]
        pawn_key = (w_pawns ^ b_pawns * _PAWN_HASH_MUL) & 0xFFFF_FFFF_FFFF_FFFF
        entry = self._pawn_cache.get(pawn_key)
        if entry is None:
            entry = _eval_pawns(w_pawns, b_pawns, p)
            if len(self._pawn_cache) >= _PAWN_CACHE_MAX:
                self._pawn_cache.clear()
            self._pawn_cache[pawn_key] = entry
        mg += entry[0]
        eg += entry[1]
        score = (mg * phase + eg * (_TOTAL_PHASE - phase)) // _TOTAL_PHASE + p.tempo
        return score if board.side == 0 else -score

    def _evaluate_internal(self, board: Board) -> int:
        pieces = board.pieces
        p = self.p

        # ---- Material + PST + phase from the Board's incremental accumulators.
        # Phase is weight-independent, so it always comes from the accumulator;
        # material+PST comes from it too for the shared default weights (fast
        # path), and is recomputed for a custom weight set (Texel). ----
        phase = board.phase_acc
        phase = min(phase, _TOTAL_PHASE)
        if p is DEFAULT_EVAL_PARAMS:
            mg = board.mg_acc
            eg = board.eg_acc
        else:
            mg = eg = 0
            mg_w, mg_b, eg_w, eg_b = p.mg_w, p.mg_b, p.eg_w, p.eg_b
            for pt in range(6):
                off = pt * 64
                bb = pieces[0][pt]
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    mg += mg_w[off + sq]
                    eg += eg_w[off + sq]
                    bb &= bb - 1
                bb = pieces[1][pt]
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    mg -= mg_b[off + sq]
                    eg -= eg_b[off + sq]
                    bb &= bb - 1

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
            entry = _eval_pawns(w_pawns, b_pawns, p)
            if len(self._pawn_cache) >= _PAWN_CACHE_MAX:
                self._pawn_cache.clear()
            self._pawn_cache[pawn_key] = entry
        pawn_mg, pawn_eg, passed_w, passed_b = entry
        mg += pawn_mg
        eg += pawn_eg

        # ---- Bishop pair ----
        if pieces[0][2].bit_count() >= 2:
            mg += p.bishop_pair_mg
            eg += p.bishop_pair_eg
        if pieces[1][2].bit_count() >= 2:
            mg -= p.bishop_pair_mg
            eg -= p.bishop_pair_eg

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
                    mg += sign * p.rook_open_mg
                    eg += sign * p.rook_open_eg
                elif not (own_pawns & fbb):
                    mg += sign * p.rook_semi_mg
                    eg += sign * p.rook_semi_eg
                if (sq >> 3) == rank7:
                    mg += sign * p.rook_7th_mg
                    eg += sign * p.rook_7th_eg
                # Rook behind passed pawn: same file, rook is behind passer
                if passed_own & fbb:
                    pp = passed_own & fbb
                    while pp:
                        pp_sq = (pp & -pp).bit_length() - 1
                        if (c == 0 and sq < pp_sq) or (c == 1 and sq > pp_sq):
                            mg += sign * p.rook_behind_passed_mg
                            eg += sign * p.rook_behind_passed_eg
                        pp &= pp - 1
                bb &= bb - 1

        # ---- Mobility + king-safety attack units (single pass) ----
        # Each piece's attack bitboard is computed ONCE and reused for both its
        # mobility (safe squares = not attacked by an enemy pawn) and its
        # contribution to the enemy king-zone attack count.
        w_safe = ~b_pawn_atk & 0xFFFF_FFFF_FFFF_FFFF
        b_safe = ~w_pawn_atk
        knight_mob_mg, knight_mob_eg = p.knight_mob_mg, p.knight_mob_eg
        bishop_mob_mg, bishop_mob_eg = p.bishop_mob_mg, p.bishop_mob_eg
        rook_mob_mg, rook_mob_eg = p.rook_mob_mg, p.rook_mob_eg
        queen_mob_mg, queen_mob_eg = p.queen_mob_mg, p.queen_mob_eg
        atk_weight = p.atk_weight
        w_king_sq = board.king_sq(0)
        b_king_sq = board.king_sq(1)
        w_zone = _KING_ZONE_W[w_king_sq]
        b_zone = _KING_ZONE_B[b_king_sq]
        atk_units = [0, 0]  # [white's attacks on black king, black's on white king]
        # Per-piece-type + full attack maps (threats + king-safety-v2 safe checks).
        atk_full = [0, 0]
        atk_knight = [0, 0]
        atk_bishop = [0, 0]
        atk_rook = [0, 0]
        atk_queen = [0, 0]

        for c, sign, safe_mask, zone in ((0, 1, w_safe, b_zone), (1, -1, b_safe, w_zone)):
            mob_safe = safe_mask & ~board.occupancy[c]
            units = 0
            af = ak = ab = ar = aq = 0

            # Knights
            bb = pieces[c][1]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _NATT[sq]
                mob = min((raw & mob_safe).bit_count(), 8)
                mg += sign * knight_mob_mg[mob]
                eg += sign * knight_mob_eg[mob]
                if raw & zone:
                    units += atk_weight[1]
                af |= raw
                ak |= raw
                bb &= bb - 1

            # Bishops
            bb = pieces[c][2]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _bishop_atk(sq, occ)
                mob = min((raw & mob_safe).bit_count(), 13)
                mg += sign * bishop_mob_mg[mob]
                eg += sign * bishop_mob_eg[mob]
                if raw & zone:
                    units += atk_weight[2]
                af |= raw
                ab |= raw
                bb &= bb - 1

            # Rooks
            bb = pieces[c][3]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _rook_atk(sq, occ)
                mob = min((raw & mob_safe).bit_count(), 14)
                mg += sign * rook_mob_mg[mob]
                eg += sign * rook_mob_eg[mob]
                if raw & zone:
                    units += atk_weight[3]
                af |= raw
                ar |= raw
                bb &= bb - 1

            # Queens
            bb = pieces[c][4]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _bishop_atk(sq, occ) | _rook_atk(sq, occ)
                mob = min((raw & mob_safe).bit_count(), 27)
                mg += sign * queen_mob_mg[mob]
                eg += sign * queen_mob_eg[mob]
                if raw & zone:
                    units += atk_weight[4]
                af |= raw
                aq |= raw
                bb &= bb - 1

            atk_units[c] = units
            atk_full[c] = af
            atk_knight[c] = ak
            atk_bishop[c] = ab
            atk_rook[c] = ar
            atk_queen[c] = aq

        # Fold pawn + king attacks into the full "defended/attacked" maps.
        atk_full[0] |= w_pawn_atk | KING_ATTACKS[w_king_sq]
        atk_full[1] |= b_pawn_atk | KING_ATTACKS[b_king_sq]

        # ---- Knight outposts ----
        # White knights on enemy half not attackable by black pawns
        bb = pieces[0][1] & _OUTPOST_MASK_W
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if not (b_pawns & _PAWN_ATK[0][sq]):
                mg += p.outpost_mg
                eg += p.outpost_eg
            bb &= bb - 1
        bb = pieces[1][1] & _OUTPOST_MASK_B
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if not (w_pawns & _PAWN_ATK[1][sq]):
                mg -= p.outpost_mg
                eg -= p.outpost_eg
            bb &= bb - 1

        # ---- Pawn threats (our pawns attacking enemy non-pawns) ----
        enemy_non_pawns = pieces[1][1] | pieces[1][2] | pieces[1][3] | pieces[1][4]
        if w_pawn_atk & enemy_non_pawns:
            count = (w_pawn_atk & enemy_non_pawns).bit_count()
            mg += count * p.pawn_threat_mg
            eg += count * p.pawn_threat_eg
        own_non_pawns = pieces[0][1] | pieces[0][2] | pieces[0][3] | pieces[0][4]
        if b_pawn_atk & own_non_pawns:
            count = (b_pawn_atk & own_non_pawns).bit_count()
            mg -= count * p.pawn_threat_mg
            eg -= count * p.pawn_threat_eg

        # ---- Piece threats (Phase 3.1; seeded inert — skipped until tuned) ----
        # minor-on-major: our N/B attacks an enemy rook/queen; rook-on-queen: our
        # rook attacks an enemy queen; weak: an enemy non-pawn we attack that the
        # enemy does not defend. Counts are white-minus-black.
        if p.threats_active:
            b_np = pieces[1][1] | pieces[1][2] | pieces[1][3] | pieces[1][4]
            w_np = pieces[0][1] | pieces[0][2] | pieces[0][3] | pieces[0][4]
            b_major = pieces[1][3] | pieces[1][4]
            w_major = pieces[0][3] | pieces[0][4]
            w_minor_atk = atk_knight[0] | atk_bishop[0]
            b_minor_atk = atk_knight[1] | atk_bishop[1]
            t_minor = (w_minor_atk & b_major).bit_count() - (b_minor_atk & w_major).bit_count()
            t_rook = (atk_rook[0] & pieces[1][4]).bit_count() - (
                atk_rook[1] & pieces[0][4]
            ).bit_count()
            t_weak = (b_np & atk_full[0] & ~atk_full[1]).bit_count() - (
                w_np & atk_full[1] & ~atk_full[0]
            ).bit_count()
            mg += (
                t_minor * p.threat_minor_major_mg
                + t_rook * p.threat_rook_queen_mg
                + t_weak * p.threat_weak_mg
            )
            eg += (
                t_minor * p.threat_minor_major_eg
                + t_rook * p.threat_rook_queen_eg
                + t_weak * p.threat_weak_eg
            )

        # ---- King safety: pawn shield (MG only) ----
        mg += (w_pawns & _SHIELD_W[w_king_sq]).bit_count() * p.pawn_shield
        mg -= (b_pawns & _SHIELD_B[b_king_sq]).bit_count() * p.pawn_shield

        # ---- King safety v2: structured king-danger through the quadratic curve.
        # Base danger = the attacker units counted above; the extra components
        # (safe checks, weak squares, no-queen) are seeded inert, so by default
        # danger == atk_units and this reproduces the old attack-unit penalty. ----
        king_safety = p.king_safety
        danger_w = atk_units[0]  # white's danger to the black king
        danger_b = atk_units[1]  # black's danger to the white king
        if p.ks_v2_active:
            danger_w += _king_danger_extra(
                p, atk_knight[0], atk_bishop[0], atk_rook[0], atk_queen[0], atk_full[0],
                atk_full[1], b_king_sq, b_zone, occ, board.occupancy[0], pieces[0][4],
            )
            danger_b += _king_danger_extra(
                p, atk_knight[1], atk_bishop[1], atk_rook[1], atk_queen[1], atk_full[1],
                atk_full[0], w_king_sq, w_zone, occ, board.occupancy[1], pieces[1][4],
            )
        mg += king_safety[max(0, min(danger_w, 99))]
        mg -= king_safety[max(0, min(danger_b, 99))]

        # ---- Endgame king activity ----
        if phase < _TOTAL_PHASE:
            # King centralization: reward kings near center in endgame
            # Center distance: sum of file and rank distance from d4/e4 area
            for c, sign in ((0, 1), (1, -1)):
                ksq = board.king_sq(c)
                kf, kr = ksq & 7, ksq >> 3
                center_dist = abs(kf - 3.5) + abs(kr - 3.5)
                eg += sign * int((7 - center_dist) * p.eg_king_center)

            # King proximity to own passed pawns
            for c, sign in ((0, 1), (1, -1)):
                ksq = board.king_sq(c)
                kf, kr = ksq & 7, ksq >> 3
                passed_own = passed_w if c == 0 else passed_b
                bb = passed_own
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    dist = max(abs((sq & 7) - kf), abs((sq >> 3) - kr))
                    eg += sign * (7 - dist) * p.king_passer_prox
                    bb &= bb - 1

        # ---- Passed-pawn richness (Phase 3.4; seeded inert — skipped until tuned) ----
        if p.passers_v2_active and (passed_w or passed_b):
            blocked, free, ekdist, protected = _passer_counts(board, atk_full, passed_w, passed_b)
            mg += (
                blocked * p.passed_blocked_mg
                + free * p.passed_free_mg
                + protected * p.passed_protected_mg
            )
            eg += (
                blocked * p.passed_blocked_eg
                + free * p.passed_free_eg
                + protected * p.passed_protected_eg
                + ekdist * p.passed_ekdist_eg
            )

        # ---- Material imbalance (Phase 3.5; seeded inert). Phase-independent:
        # added equally to mg and eg. ----
        if p.imbalance_active:
            kn_p, rk_p, bp_p = _imbalance_terms(pieces)
            imb = kn_p * p.imb_knight_pawn + rk_p * p.imb_rook_pawn + bp_p * p.imb_bishop_pawn
            mg += imb
            eg += imb

        # ---- Space + bad bishop + connected rooks (Phase 3.6; seeded inert) ----
        if p.minor_terms_active:
            space, bad, cr = _minor_terms(
                pieces, w_pawns, b_pawns, w_pawn_atk, b_pawn_atk, atk_rook
            )
            mg += space * p.space_mg + bad * p.bad_bishop_mg + cr * p.connected_rooks_mg
            eg += bad * p.bad_bishop_eg + cr * p.connected_rooks_eg

        # ---- Tapered score with scale / winnable / rule-50 (Phase 3.3;
        # seeded identity: eg_scale=_SCALE_NORMAL, winnable=0, r50=_RULE50_BASE) ----
        transform = _final_transform(p, board)
        eg_scaled = eg * (_TOTAL_PHASE - phase) * transform[0] // _SCALE_NORMAL
        score = (mg * phase + eg_scaled) // _TOTAL_PHASE + p.tempo + transform[1]
        score = score * transform[2] // _RULE50_BASE

        return score if board.side == 0 else -score

    def trace(self, board: Board) -> EvalTrace:
        """Return the eval coefficient decomposition (Phase 1.3; for Texel).

        ``reconstruct_eval(self.trace(board), self.p) == self.evaluate(board)``.
        """
        pieces = board.pieces
        p = self.p
        cmg: dict[tuple, int] = {}
        ceg: dict[tuple, int] = {}

        # ---- Material + PST ----
        for pt in range(6):
            bb = pieces[0][pt]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                _add(cmg, ("mg_val", pt), 1)
                _add(ceg, ("eg_val", pt), 1)
                _add(cmg, ("pst_mg", pt, sq), 1)
                _add(ceg, ("pst_eg", pt, sq), 1)
                bb &= bb - 1
            bb = pieces[1][pt]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                _add(cmg, ("mg_val", pt), -1)
                _add(ceg, ("eg_val", pt), -1)
                _add(cmg, ("pst_mg", pt, sq ^ 56), -1)
                _add(ceg, ("pst_eg", pt, sq ^ 56), -1)
                bb &= bb - 1

        # ---- Phase ----
        phase = 0
        for c in range(2):
            phase += pieces[c][1].bit_count() + pieces[c][2].bit_count()
            phase += pieces[c][3].bit_count() * 2
            phase += pieces[c][4].bit_count() * 4
        phase = min(phase, _TOTAL_PHASE)

        w_pawns = pieces[0][0]
        b_pawns = pieces[1][0]
        occ = board.all_occ
        w_pawn_atk = (
            ((w_pawns & ~_FILE_A_BB) << 7) | ((w_pawns & ~_FILE_H_BB) << 9)
        ) & 0xFFFF_FFFF_FFFF_FFFF
        b_pawn_atk = ((b_pawns & ~_FILE_H_BB) >> 7) | ((b_pawns & ~_FILE_A_BB) >> 9)

        # ---- Pawn structure ----
        passed_w, passed_b = _trace_pawns(w_pawns, b_pawns, cmg, ceg)

        # ---- Bishop pair ----
        if pieces[0][2].bit_count() >= 2:
            _add(cmg, ("bishop_pair_mg",), 1)
            _add(ceg, ("bishop_pair_eg",), 1)
        if pieces[1][2].bit_count() >= 2:
            _add(cmg, ("bishop_pair_mg",), -1)
            _add(ceg, ("bishop_pair_eg",), -1)

        # ---- Rooks: open / semi / 7th / behind passer ----
        for c, sign in ((0, 1), (1, -1)):
            own_pawns = pieces[c][0]
            all_pawns = own_pawns | pieces[1 - c][0]
            rank7 = 6 if c == 0 else 1
            passed_own = passed_w if c == 0 else passed_b
            bb = pieces[c][3]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                fbb = _FILE_BB[sq & 7]
                if not (all_pawns & fbb):
                    _add(cmg, ("rook_open_mg",), sign)
                    _add(ceg, ("rook_open_eg",), sign)
                elif not (own_pawns & fbb):
                    _add(cmg, ("rook_semi_mg",), sign)
                    _add(ceg, ("rook_semi_eg",), sign)
                if (sq >> 3) == rank7:
                    _add(cmg, ("rook_7th_mg",), sign)
                    _add(ceg, ("rook_7th_eg",), sign)
                if passed_own & fbb:
                    pp = passed_own & fbb
                    while pp:
                        pp_sq = (pp & -pp).bit_length() - 1
                        if (c == 0 and sq < pp_sq) or (c == 1 and sq > pp_sq):
                            _add(cmg, ("rook_behind_passed_mg",), sign)
                            _add(ceg, ("rook_behind_passed_eg",), sign)
                        pp &= pp - 1
                bb &= bb - 1

        # ---- Mobility (+ per-type attack maps for threats & king-safety v2) ----
        w_safe = ~b_pawn_atk & 0xFFFF_FFFF_FFFF_FFFF
        b_safe = ~w_pawn_atk
        atk_full = [0, 0]
        atk_knight = [0, 0]
        atk_bishop = [0, 0]
        atk_rook = [0, 0]
        atk_queen = [0, 0]
        for c, sign, safe_mask in ((0, 1, w_safe), (1, -1, b_safe)):
            mob_safe = safe_mask & ~board.occupancy[c]
            af = ak = ab = ar = aq = 0
            bb = pieces[c][1]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _NATT[sq]
                mob = min((raw & mob_safe).bit_count(), 8)
                _add(cmg, ("knight_mob_mg", mob), sign)
                _add(ceg, ("knight_mob_eg", mob), sign)
                af |= raw
                ak |= raw
                bb &= bb - 1
            bb = pieces[c][2]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _bishop_atk(sq, occ)
                mob = min((raw & mob_safe).bit_count(), 13)
                _add(cmg, ("bishop_mob_mg", mob), sign)
                _add(ceg, ("bishop_mob_eg", mob), sign)
                af |= raw
                ab |= raw
                bb &= bb - 1
            bb = pieces[c][3]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _rook_atk(sq, occ)
                mob = min((raw & mob_safe).bit_count(), 14)
                _add(cmg, ("rook_mob_mg", mob), sign)
                _add(ceg, ("rook_mob_eg", mob), sign)
                af |= raw
                ar |= raw
                bb &= bb - 1
            bb = pieces[c][4]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                raw = _bishop_atk(sq, occ) | _rook_atk(sq, occ)
                mob = min((raw & mob_safe).bit_count(), 27)
                _add(cmg, ("queen_mob_mg", mob), sign)
                _add(ceg, ("queen_mob_eg", mob), sign)
                af |= raw
                aq |= raw
                bb &= bb - 1
            atk_full[c] = af
            atk_knight[c] = ak
            atk_bishop[c] = ab
            atk_rook[c] = ar
            atk_queen[c] = aq
        atk_full[0] |= w_pawn_atk | KING_ATTACKS[board.king_sq(0)]
        atk_full[1] |= b_pawn_atk | KING_ATTACKS[board.king_sq(1)]

        # ---- Knight outposts ----
        bb = pieces[0][1] & _OUTPOST_MASK_W
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if not (b_pawns & _PAWN_ATK[0][sq]):
                _add(cmg, ("outpost_mg",), 1)
                _add(ceg, ("outpost_eg",), 1)
            bb &= bb - 1
        bb = pieces[1][1] & _OUTPOST_MASK_B
        while bb:
            sq = (bb & -bb).bit_length() - 1
            if not (w_pawns & _PAWN_ATK[1][sq]):
                _add(cmg, ("outpost_mg",), -1)
                _add(ceg, ("outpost_eg",), -1)
            bb &= bb - 1

        # ---- Pawn threats ----
        enemy_non_pawns = pieces[1][1] | pieces[1][2] | pieces[1][3] | pieces[1][4]
        own_non_pawns = pieces[0][1] | pieces[0][2] | pieces[0][3] | pieces[0][4]
        _add(cmg, ("pawn_threat_mg",), (w_pawn_atk & enemy_non_pawns).bit_count())
        _add(ceg, ("pawn_threat_eg",), (w_pawn_atk & enemy_non_pawns).bit_count())
        _add(cmg, ("pawn_threat_mg",), -(b_pawn_atk & own_non_pawns).bit_count())
        _add(ceg, ("pawn_threat_eg",), -(b_pawn_atk & own_non_pawns).bit_count())

        # ---- Piece threats (Phase 3.1) ----
        b_major = pieces[1][3] | pieces[1][4]
        w_major = pieces[0][3] | pieces[0][4]
        w_minor_atk = atk_knight[0] | atk_bishop[0]
        b_minor_atk = atk_knight[1] | atk_bishop[1]
        t_minor = (w_minor_atk & b_major).bit_count() - (b_minor_atk & w_major).bit_count()
        t_rook = (atk_rook[0] & pieces[1][4]).bit_count() - (atk_rook[1] & pieces[0][4]).bit_count()
        b_np = pieces[1][1] | pieces[1][2] | pieces[1][3] | pieces[1][4]
        w_np = pieces[0][1] | pieces[0][2] | pieces[0][3] | pieces[0][4]
        t_weak = (b_np & atk_full[0] & ~atk_full[1]).bit_count() - (
            w_np & atk_full[1] & ~atk_full[0]
        ).bit_count()
        _add(cmg, ("threat_minor_major_mg",), t_minor)
        _add(ceg, ("threat_minor_major_eg",), t_minor)
        _add(cmg, ("threat_rook_queen_mg",), t_rook)
        _add(ceg, ("threat_rook_queen_eg",), t_rook)
        _add(cmg, ("threat_weak_mg",), t_weak)
        _add(ceg, ("threat_weak_eg",), t_weak)

        # ---- King safety: pawn shield (linear) + attack units (residual) ----
        w_king_sq = board.king_sq(0)
        b_king_sq = board.king_sq(1)
        _add(
            cmg,
            ("pawn_shield",),
            (w_pawns & _SHIELD_W[w_king_sq]).bit_count()
            - (b_pawns & _SHIELD_B[b_king_sq]).bit_count(),
        )

        w_zone = _KING_ZONE_W[w_king_sq]
        b_zone = _KING_ZONE_B[b_king_sq]
        atk_weight = p.atk_weight
        w_units = b_units = 0
        for pt in (1, 2, 3, 4):
            bb = pieces[1][pt]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                if pt == 1:
                    hit = _NATT[sq] & w_zone
                elif pt == 2:
                    hit = _bishop_atk(sq, occ) & w_zone
                elif pt == 3:
                    hit = _rook_atk(sq, occ) & w_zone
                else:
                    hit = (_bishop_atk(sq, occ) | _rook_atk(sq, occ)) & w_zone
                if hit:
                    b_units += atk_weight[pt]
                bb &= bb - 1
            bb = pieces[0][pt]
            while bb:
                sq = (bb & -bb).bit_length() - 1
                if pt == 1:
                    hit = _NATT[sq] & b_zone
                elif pt == 2:
                    hit = _bishop_atk(sq, occ) & b_zone
                elif pt == 3:
                    hit = _rook_atk(sq, occ) & b_zone
                else:
                    hit = (_bishop_atk(sq, occ) | _rook_atk(sq, occ)) & b_zone
                if hit:
                    w_units += atk_weight[pt]
                bb &= bb - 1
        king_safety = p.king_safety
        danger_w = w_units
        danger_b = b_units
        if p.ks_v2_active:
            danger_w += _king_danger_extra(
                p, atk_knight[0], atk_bishop[0], atk_rook[0], atk_queen[0], atk_full[0],
                atk_full[1], b_king_sq, b_zone, occ, board.occupancy[0], pieces[0][4],
            )
            danger_b += _king_danger_extra(
                p, atk_knight[1], atk_bishop[1], atk_rook[1], atk_queen[1], atk_full[1],
                atk_full[0], w_king_sq, w_zone, occ, board.occupancy[1], pieces[1][4],
            )
        residual_mg = king_safety[max(0, min(danger_w, 99))] - king_safety[
            max(0, min(danger_b, 99))
        ]

        # ---- Endgame king activity ----
        residual_eg = 0
        if phase < _TOTAL_PHASE:
            for c, sign in ((0, 1), (1, -1)):
                ksq = board.king_sq(c)
                kf, kr = ksq & 7, ksq >> 3
                center_dist = abs(kf - 3.5) + abs(kr - 3.5)
                residual_eg += sign * int((7 - center_dist) * p.eg_king_center)
            for c, sign in ((0, 1), (1, -1)):
                ksq = board.king_sq(c)
                kf, kr = ksq & 7, ksq >> 3
                bb = passed_w if c == 0 else passed_b
                prox = 0
                while bb:
                    sq = (bb & -bb).bit_length() - 1
                    prox += 7 - max(abs((sq & 7) - kf), abs((sq >> 3) - kr))
                    bb &= bb - 1
                _add(ceg, ("king_passer_prox",), sign * prox)

        # ---- Passed-pawn richness (Phase 3.4) ----
        blocked, free, ekdist, protected = _passer_counts(board, atk_full, passed_w, passed_b)
        _add(cmg, ("passed_blocked_mg",), blocked)
        _add(ceg, ("passed_blocked_eg",), blocked)
        _add(cmg, ("passed_free_mg",), free)
        _add(ceg, ("passed_free_eg",), free)
        _add(cmg, ("passed_protected_mg",), protected)
        _add(ceg, ("passed_protected_eg",), protected)
        _add(ceg, ("passed_ekdist_eg",), ekdist)

        # ---- Material imbalance (Phase 3.5; added equally to mg and eg) ----
        kn_p, rk_p, bp_p = _imbalance_terms(pieces)
        _add(cmg, ("imb_knight_pawn",), kn_p)
        _add(ceg, ("imb_knight_pawn",), kn_p)
        _add(cmg, ("imb_rook_pawn",), rk_p)
        _add(ceg, ("imb_rook_pawn",), rk_p)
        _add(cmg, ("imb_bishop_pawn",), bp_p)
        _add(ceg, ("imb_bishop_pawn",), bp_p)

        # ---- Space + bad bishop + connected rooks (Phase 3.6) ----
        space, bad, cr = _minor_terms(pieces, w_pawns, b_pawns, w_pawn_atk, b_pawn_atk, atk_rook)
        _add(cmg, ("space_mg",), space)
        _add(cmg, ("bad_bishop_mg",), bad)
        _add(ceg, ("bad_bishop_eg",), bad)
        _add(cmg, ("connected_rooks_mg",), cr)
        _add(ceg, ("connected_rooks_eg",), cr)

        transform = _final_transform(p, board)
        return EvalTrace(
            cmg, ceg, residual_mg, residual_eg, phase, board.side == 0,
            transform[0], transform[1], transform[2],
        )


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
