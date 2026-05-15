"""Zobrist hashing tables.

A random 64-bit key is assigned to every (colour, piece-type, square) triple,
plus keys for castling rights, en-passant file and side-to-move.  The board
hash is the XOR of the keys for all features present in the position.

Keys are generated deterministically from a fixed seed so that hashes are
reproducible across runs.
"""

from __future__ import annotations

import random as _random

from hydra.types import COLOR_NB, PIECE_TYPE_NB, SQUARE_NB

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
