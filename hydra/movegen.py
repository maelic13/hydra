"""Legal move generation and perft.

Strategy: generate *pseudo-legal* moves, then filter out those that leave the
own king in check via a lightweight inline legality check.

When in check, a specialised evasion generator restricts candidate moves to
king moves, captures of the checker, and blocks — avoiding full movegen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hydra.attacks import (
    BISHOP_MAGICS,
    BISHOP_SHIFTS,
    KING_ATTACKS,
    KNIGHT_ATTACKS,
    PAWN_ATTACKS,
    # Magic bitboard internals for inlining
    ROOK_MAGICS,
    ROOK_SHIFTS,
    _bishop_masks,
    _bishop_table,
    _rook_masks,
    _rook_table,
)
from hydra.bitboard import (
    BB_ALL,
    BB_RANK_2,
    BB_RANK_7,
    BB_SQUARES,
)
from hydra.moves import (
    PROMO_BISHOP,
    PROMO_KNIGHT,
    PROMO_QUEEN,
    PROMO_ROOK,
    move_to_uci,
)
from hydra.types import (
    B1,
    B8,
    BISHOP,
    BK_CASTLE,
    BQ_CASTLE,
    C1,
    C8,
    D1,
    D8,
    E1,
    E8,
    F1,
    F8,
    G1,
    G8,
    KNIGHT,
    NO_SQUARE,
    PAWN,
    QUEEN,
    ROOK,
    WHITE,
    WK_CASTLE,
    WQ_CASTLE,
)

if TYPE_CHECKING:
    from hydra.board import Board

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
