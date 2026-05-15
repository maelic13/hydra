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

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

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
from hydra.evaluation import Evaluator, create_evaluator
from hydra.movegen import generate_captures, generate_legal_moves
from hydra.moves import (
    FLAG_EN_PASSANT,
    FLAG_PROMOTION,
    MOVE_NONE,
    PROMO_QUEEN,
    move_flag,
    move_from_sq,
    move_promo,
    move_to_sq,
    move_to_uci,
)
from hydra.transposition import TT_ALPHA, TT_BETA, TT_EXACT, TranspositionTable
from hydra.types import BISHOP, KING, KNIGHT, NO_PIECE_TYPE, PAWN, QUEEN, ROOK, WHITE

if TYPE_CHECKING:
    import threading
    from collections.abc import Callable

    from hydra.board import Board

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
        self.history: list[list[list[int]]] = [
            [[0] * 64 for _ in range(64)] for _ in range(2)
        ]
        self.cont_hist: list[list[int]] = [[0] * 64 for _ in range(64)]
        self.cont_hist2: list[list[int]] = [[0] * 64 for _ in range(64)]
        self.cap_hist: list[list[list[int]]] = [
            [[0] * 6 for _ in range(64)] for _ in range(6)
        ]
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
    if params.movetime > 0:
        hard = max(params.movetime - 10, 10) / 1000.0
        return hard, hard

    remaining = params.wtime if side == WHITE else params.btime
    inc = params.winc if side == WHITE else params.binc

    if remaining <= 0 and inc <= 0:
        return 0.0, 0.0

    remaining = max(remaining, 1)

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
        see = _see(board, move)
        attacker_pt = board.mailbox[frm]
        cap_pt = PAWN if flag == FLAG_EN_PASSANT else board.mailbox[to]
        ch = cap_hist[attacker_pt][to][cap_pt] >> 4  # scale down to ~±1024
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
        "stopped",
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
    ) -> None:
        self.board = board
        self.params = params
        self.evaluator = evaluator
        self.tt = tt
        self.stop_event = stop_event
        self.info_cb = info_cb

        self.nodes: int = 0
        self.ply: int = 0
        self.seldepth: int = 0
        self.stopped: bool = False
        self.pondering: bool = params.ponder
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
        """Called on ``ponderhit`` — start the clock and enable time limits."""
        self.pondering = False
        self.start_time = time.perf_counter()
        self.soft_limit, self.hard_limit = _compute_time_limits(self.params, self.board.side)

    def check_stop(self) -> bool:
        if self.stopped:
            return True
        if self.stop_event.is_set():
            self.stopped = True
            return True
        if self.params.nodes > 0 and self.nodes >= self.params.nodes:
            self.stopped = True
            return True
        # While pondering, only stop_event can halt the search
        if self.pondering:
            return False
        if (
            self.hard_limit > 0
            and self.nodes & 4095 == 0
            and time.perf_counter() - self.start_time >= self.hard_limit
        ):
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
            board.pieces[0][PAWN] ^ board.pieces[1][PAWN] * _PAWN_HASH_MUL
        ) & 0xFFFF_FFFF_FFFF_FFFF & 0xFFFF
        static_eval = raw_eval + ss.corr_hist[board.side][ph] // 256
    else:
        raw_eval = -INFINITY
        static_eval = -INFINITY
        ph = 0
    ss.static_evals[ss.ply] = static_eval
    improving = (
        not in_check and ss.ply >= 2 and static_eval > ss.static_evals[ss.ply - 2]
    )

    # --- Reverse futility pruning (static null move pruning) ---
    if (
        not is_pv
        and not in_check
        and depth <= 7
        and static_eval - _REVERSE_FUTILITY_MARGIN * depth * (2 - improving) >= beta
    ):
        return static_eval

    # --- Razoring ---
    if (
        not is_pv
        and not in_check
        and depth <= 3
        and static_eval + _RAZORING_MARGIN < alpha
    ):
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
        not is_pv
        and not in_check
        and depth <= 3
        and static_eval + _FUTILITY_MARGIN * depth < alpha
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
                board.mailbox[move_to_sq(tt_move)] != _NPT
                or move_flag(tt_move) == FLAG_EN_PASSANT
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
                    ss.cont_hist2[pp_to][to] = _clamp_history(
                        cont_hist2_row[to] + history_delta
                    )
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
            board.mailbox[move_to_sq(best_move)] != _NPT
            or move_flag(best_move) == FLAG_EN_PASSANT
        )
        if not is_best_capture and move_flag(best_move) != FLAG_PROMOTION:
            for move in ordered:
                if move == best_move:
                    break
                flag = move_flag(move)
                if board.mailbox[move_to_sq(move)] == _NPT and flag not in {
                    FLAG_EN_PASSANT,
                    FLAG_PROMOTION,
                }:
                    frm = move_from_sq(move)
                    to = move_to_sq(move)
                    history_row[frm][to] = _clamp_history(
                        history_row[frm][to] - history_delta
                    )
                    if prev != MOVE_NONE:
                        ss.cont_hist[prev_to][to] = _clamp_history(
                            ss.cont_hist[prev_to][to] - history_delta
                        )
                    if cont_hist2_row is not None:
                        cont_hist2_row[to] = _clamp_history(
                            cont_hist2_row[to] - history_delta
                        )
                elif board.mailbox[move_to_sq(move)] != _NPT and flag not in {
                    FLAG_EN_PASSANT,
                    FLAG_PROMOTION,
                }:
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
    import threading as _threading

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

    ss = _SS(board, params, evaluator, tt, stop_event, info_cb, history_tables)
    if ponder_switch is not None:
        ponder_switch.append(ss)

    # Quick exit when there are zero or one legal moves
    legal_moves = generate_legal_moves(board)
    if not legal_moves:
        return SearchResult()
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

        # Aspiration windows
        delta = ASPIRATION_WINDOW
        if depth >= 4:
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
                f"hashfull {hf} time {elapsed}"
            )
            if pv:
                info_str += " pv " + " ".join(move_to_uci(m) for m in pv)
            info_cb(info_str)

        # Stop early on forced mate
        if abs(score) > MATE_SCORE - MAX_PLY:
            break

        # Adaptive soft time: fewer iterations when the best move is stable.
        # stability=0 → 100 % of soft limit; stability≥6 → ~64 % of soft limit.
        if not ss.pondering and ss.soft_limit > 0:
            stability_scale = 1.0 - 0.06 * min(best_stability, 6)
            if time.perf_counter() - ss.start_time >= ss.soft_limit * stability_scale:
                break

    # Fallback if no completed iteration
    if best_result.bestmove == MOVE_NONE and legal_moves:
        best_result.bestmove = legal_moves[0]

    return best_result
