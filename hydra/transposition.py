"""Transposition table — hash table for caching search results.

Uses Zobrist keys (computed incrementally by :mod:`hydra.board`) to
index into a fixed-size table with a depth-preferred replacement scheme.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# TT entry bound types
# ---------------------------------------------------------------------------
TT_EXACT: int = 0
TT_ALPHA: int = 1  # Upper bound (score failed low)
TT_BETA: int = 2  # Lower bound (score failed high)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


class TTEntry:
    """Single transposition-table entry."""

    __slots__ = ("depth", "flag", "key", "move", "score")

    def __init__(
        self,
        key: int = 0,
        depth: int = 0,
        score: int = 0,
        flag: int = 0,
        move: int = 0,
    ) -> None:
        self.key = key
        self.depth = depth
        self.score = score
        self.flag = flag
        self.move = move


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class TranspositionTable:
    """Fixed-size hash table with depth-preferred replacement."""

    def __init__(self, size_mb: int = 64) -> None:
        self._num_entries = max(1, (size_mb * 1024 * 1024) // 64)
        self._table: list[TTEntry | None] = [None] * self._num_entries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def probe(self, key: int) -> TTEntry | None:
        """Look up a position.  Returns the entry on key-match, else *None*."""
        entry = self._table[key % self._num_entries]
        if entry is not None and entry.key == key:
            return entry
        return None

    def store(
        self,
        key: int,
        depth: int,
        score: int,
        flag: int,
        move: int,
    ) -> None:
        """Store a search result.  Replaces if same position or at least as deep."""
        idx = key % self._num_entries
        old = self._table[idx]
        if old is None or old.key == key or depth >= old.depth:
            self._table[idx] = TTEntry(key, depth, score, flag, move)

    def clear(self) -> None:
        """Remove all entries."""
        self._table = [None] * self._num_entries

    def resize(self, size_mb: int) -> None:
        """Resize (and clear) the table."""
        self._num_entries = max(1, (size_mb * 1024 * 1024) // 64)
        self._table = [None] * self._num_entries

    def hashfull(self) -> int:
        """Return fill rate in per-mille (0–1000), sampled from first 1000 entries."""
        sample = min(1000, self._num_entries)
        used = sum(1 for i in range(sample) if self._table[i] is not None)
        return (used * 1000) // sample
