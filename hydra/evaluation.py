"""Classical hand-crafted evaluation framework."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

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
