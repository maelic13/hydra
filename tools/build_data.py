"""Prepare match/test data from a large label-free FEN file (single pass).

Source: A:\\Chess\\Beast\\data\\txt\\positions.txt  (122.66M FENs, one per line,
no result label). Diverse by construction (ICCF computer chess -> human club).

Produces two small, committed artifacts:

  * eval-equivalence corpus  (tests/data/eval_corpus.epd)
        phase-stratified sample used by the behaviour-identical refactor gates
        (PLAN gate rule 4): evaluate() must match before/after on these FENs.
        Good mix of opening / middlegame / endgame is enforced by per-phase
        reservoirs of equal size.

  * opening book  (tools/book/openings.epd)
        near-start positions (low fullmove, full material) for fastchess to
        start games from with colour variety.

Reservoir sampling gives a uniform sample per bucket over the scanned region.
The big source file stays external (never committed); these outputs are tiny.

Usage (offline dev tool):
    python tools/build_data.py \
        --positions "A:\\Chess\\Beast\\data\\txt\\positions.txt" \
        --max-scan 40000000
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Phase weights per piece type (matches hydra.evaluation: N=B=1, R=2, Q=4, cap 24)
_PHASE = {"n": 1, "b": 1, "r": 2, "q": 4, "N": 1, "B": 1, "R": 2, "Q": 4}
_TOTAL_PHASE = 24

# Phase buckets for the eval corpus: (name, lo, hi) inclusive on phase value.
_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("opening", 20, 24),
    ("early_mid", 14, 19),
    ("middlegame", 8, 13),
    ("endgame", 3, 7),
    ("deep_endgame", 0, 2),
)


def _phase_of(board_field: str) -> int:
    ph = 0
    for ch in board_field:
        ph += _PHASE.get(ch, 0)
    return min(ph, _TOTAL_PHASE)


class Reservoir:
    """Classic reservoir sampler (uniform k-sample over an unknown-length stream)."""

    def __init__(self, k: int, rng: random.Random) -> None:
        self.k = k
        self.rng = rng
        self.seen = 0
        self.items: list[str] = []

    def offer(self, item: str) -> None:
        self.seen += 1
        if len(self.items) < self.k:
            self.items.append(item)
        else:
            j = self.rng.randint(0, self.seen - 1)
            if j < self.k:
                self.items[j] = item


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", default=r"A:\Chess\Beast\data\txt\positions.txt")
    ap.add_argument("--corpus-out", default="tests/data/eval_corpus.epd")
    ap.add_argument("--book-out", default="tools/book/openings.epd")
    ap.add_argument("--per-bucket", type=int, default=1000, help="corpus FENs per phase bucket")
    ap.add_argument("--book-size", type=int, default=3000)
    ap.add_argument("--book-max-fullmove", type=int, default=8)
    ap.add_argument("--max-scan", type=int, default=40_000_000, help="0 = whole file")
    ap.add_argument("--seed", type=int, default=20260629)
    args = ap.parse_args()

    src = Path(args.positions)
    if not src.exists():
        print(f"ERROR: source not found: {src}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    corpus = {name: Reservoir(args.per_bucket, rng) for name, _, _ in _BUCKETS}
    book = Reservoir(args.book_size, rng)

    scanned = 0
    with src.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            scanned += 1
            if args.max_scan and scanned > args.max_scan:
                break
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            board_field = parts[0]
            ph = _phase_of(board_field)

            for name, lo, hi in _BUCKETS:
                if lo <= ph <= hi:
                    corpus[name].offer(line)
                    break

            # Opening book: full material, near the start.
            if ph >= 20 and len(parts) >= 6:
                try:
                    fullmove = int(parts[5])
                except ValueError:
                    fullmove = 99
                if fullmove <= args.book_max_fullmove:
                    book.offer(line)

            if scanned % 5_000_000 == 0:
                filled = ", ".join(f"{n}:{len(r.items)}" for n, r in corpus.items())
                print(f"  scanned {scanned:,}  | {filled}  book:{len(book.items)}", file=sys.stderr)

    print(f"scanned {scanned:,} lines", file=sys.stderr)
    _write(args.corpus_out, _flatten(corpus), label="corpus")
    _write(args.book_out, book.items, label="book")
    return 0


def _flatten(corpus: dict[str, Reservoir]) -> list[str]:
    out: list[str] = []
    for name, res in corpus.items():
        print(f"  bucket {name}: {len(res.items)} (saw {res.seen:,})", file=sys.stderr)
        out.extend(res.items)
    return out


def _write(path_str: str, fens: list[str], *, label: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fens) + "\n", encoding="utf-8")
    print(f"wrote {len(fens)} {label} FENs -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
