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

from __future__ import annotations

from hydra.types import FILE_NAMES, KNIGHT, RANK_NAMES, SQUARE_NAMES, make_square

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
