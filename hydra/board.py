"""Board state — the central data structure of the engine.

Maintains **bitboards** (fast set operations), a **mailbox** array (fast
piece-on-square lookup), incrementally updated **Zobrist hash**, and a
**history stack** for unmake.
"""

from __future__ import annotations

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
from hydra.bitboard import BB_ALL, BB_SQUARES
from hydra.moves import (
    FLAG_CASTLING,
    FLAG_EN_PASSANT,
    FLAG_PROMOTION,
)
from hydra.types import (
    A1,
    A8,
    ALL_CASTLING,
    BK_CASTLE,
    BLACK,
    BQ_CASTLE,
    CASTLING_MASKS,
    CASTLING_NONE,
    COLOR_NB,
    D1,
    D8,
    F1,
    F8,
    FILE_NAMES,
    H1,
    H8,
    KING,
    KNIGHT,
    NO_PIECE_TYPE,
    NO_SQUARE,
    PAWN,
    PIECE_CHARS,
    PIECE_TYPE_NB,
    RANK_NAMES,
    ROOK,
    SQUARE_NAMES,
    SQUARE_NB,
    WHITE,
    WK_CASTLE,
    WQ_CASTLE,
    make_square,
)
from hydra.zobrist import CASTLING_KEYS, EP_KEYS, PIECE_KEYS, SIDE_KEY

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
