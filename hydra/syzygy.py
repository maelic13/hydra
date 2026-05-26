"""Syzygy tablebase adapter backed by the vendored Fathom probe code."""

from __future__ import annotations

import threading
from typing import NamedTuple

from hydra.types import (
    BISHOP,
    BLACK,
    KING,
    KNIGHT,
    NO_SQUARE,
    PAWN,
    QUEEN,
    ROOK,
    WHITE,
)

try:
    from hydra import _fathom
except ImportError:
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
