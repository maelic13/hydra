#!/usr/bin/env python3
"""Build Hydra's Texel training set from the Beast Stockfish-evaluated pool.

Phase 4.1 dataset prep. Unlike the sibling engines (Rarog/Basilisk), which label
by *self-play game results*, Hydra fits against the **pre-computed Stockfish WDL
labels** shipped in the Beast dataset. Rationale (see PLAN.md §7 / dev log):
Hydra's self-play is ~30-50x slower than the native siblings (~20-34 h/regen vs
<1 h), so re-generating self-play data every campaign is prohibitive, while the
Beast `evaluated/` dir already provides 123M Stockfish-WDL-labelled positions
for free. The label is a WDL win-probability in [0,1] for the SIDE TO MOVE; we
convert it to White perspective (the tuner's convention). The percentage IS the
Texel target -- no centipawn conversion (the fit is sigmoid(eval*K) vs target).

Input  (A:\\Chess\\Beast\\data\\evaluated\\evaluated_positions_*.txt):
    <FEN>\\t<target>        target = side-to-move win-prob in [0,1]

Output (tools/texel/data/):
    beast_train.csv         <FEN>;<target>   target = White-perspective, float
    beast_holdout.csv       disjoint by position (no train/holdout leakage)

Hygiene (standard Texel):
  * drop positions in check (static HCE eval is meaningless there);
  * drop *tactical* positions -- side to move has a winning capture (SEE > 0) --
    so the quiet static eval can actually match the (search-derived) label;
  * de-duplicate by position key (first 4 FEN fields);
  * phase-balance: per-bucket reservoir sampling so no game phase dominates.

Usage (offline dev tool; run against the compiled build for speed if desired):
    python tools/texel/import_beast.py \\
        --source "A:\\Chess\\Beast\\data\\evaluated" \\
        --per-bucket 400000 --max-scan 20000000
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from hydra.board import Board
from hydra.engine import _see  # noqa: PLC2701  (engine SEE reused for the quiet filter)
from hydra.movegen import generate_captures

# Phase weights per piece letter (matches hydra.evaluation: N=B=1, R=2, Q=4, cap 24).
_PHASE = {"n": 1, "b": 1, "r": 2, "q": 4, "N": 1, "B": 1, "R": 2, "Q": 4}
_TOTAL_PHASE = 24

# Phase buckets (name, lo, hi) inclusive -- "good mix of opening/middle/endgame".
_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("opening", 20, 24),
    ("early_mid", 14, 19),
    ("middlegame", 8, 13),
    ("endgame", 3, 7),
    ("deep_endgame", 0, 2),
)


def _phase_of(board_field: str) -> int:
    return min(sum(_PHASE.get(ch, 0) for ch in board_field), _TOTAL_PHASE)


def _bucket_of(ph: int) -> int:
    for i, (_, lo, hi) in enumerate(_BUCKETS):
        if lo <= ph <= hi:
            return i
    return -1


def _fen_key(fen: str) -> str:
    """Dedup key: position + side + castling + ep (first 4 FEN fields)."""
    return " ".join(fen.split()[:4])


class Reservoir:
    """Uniform k-sample over a stream of unknown length (classic reservoir)."""

    def __init__(self, k: int, rng: random.Random) -> None:
        self.k = k
        self.rng = rng
        self.seen = 0
        self.items: list[tuple[str, float]] = []

    def offer(self, item: tuple[str, float]) -> None:
        self.seen += 1
        if len(self.items) < self.k:
            self.items.append(item)
        else:
            j = self.rng.randint(0, self.seen - 1)
            if j < self.k:
                self.items[j] = item


def _iter_shards(source: str) -> list[Path]:
    src = Path(source)
    files = sorted(src.glob("evaluated_positions_*.txt")) if src.is_dir() else [src]
    if not files:
        msg = f"no evaluated_positions_*.txt found under {source}"
        raise SystemExit(msg)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=r"A:\Chess\Beast\data\evaluated")
    ap.add_argument("--out-dir", default="tools/texel/data")
    ap.add_argument("--train", default="beast_train.csv")
    ap.add_argument("--holdout", default="beast_holdout.csv")
    ap.add_argument("--per-bucket", type=int, default=400_000, help="train positions/phase bucket")
    ap.add_argument("--holdout-pct", type=float, default=5.0)
    ap.add_argument(
        "--max-scan",
        type=int,
        default=20_000_000,
        help="stop after scanning this many raw lines (0 = whole pool)",
    )
    ap.add_argument("--no-quiet", action="store_true", help="disable the SEE quiet filter")
    ap.add_argument("--seed", type=int, default=20260701)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    shards = _iter_shards(args.source)
    rng.shuffle(shards)  # spread the scan window across the whole pool

    buckets = [Reservoir(args.per_bucket, rng) for _ in _BUCKETS]
    holdout_k = max(1, int(sum(args.per_bucket for _ in _BUCKETS) * args.holdout_pct / 100.0))
    holdout = Reservoir(holdout_k, rng)
    hold_frac = args.holdout_pct / 100.0

    scanned = kept = in_check = tactical = bad = 0
    t0 = time.time()
    print(f"source: {len(shards)} shards | per-bucket {args.per_bucket:,} | "
          f"holdout {args.holdout_pct:g}% | max-scan {args.max_scan or 'all':,} | "
          f"quiet-filter {'off' if args.no_quiet else 'SEE>0'}", file=sys.stderr)

    for path in shards:
        if args.max_scan and scanned >= args.max_scan:
            break
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if args.max_scan and scanned >= args.max_scan:
                    break
                scanned += 1
                tab = line.rstrip("\n").split("\t")
                if len(tab) != 2:
                    bad += 1
                    continue
                fen, raw = tab
                fields = fen.split()
                if len(fields) != 6:
                    bad += 1
                    continue
                try:
                    target = float(raw)
                except ValueError:
                    bad += 1
                    continue
                if not 0.0 <= target <= 1.0:
                    bad += 1
                    continue

                bi = _bucket_of(_phase_of(fields[0]))
                try:
                    board = Board.from_fen(fen)
                except Exception:
                    bad += 1
                    continue
                if board.is_in_check():
                    in_check += 1
                    continue
                if not args.no_quiet and not _is_quiet_captures(board):
                    tactical += 1
                    continue

                # Convert side-to-move win-prob -> White perspective.
                white_target = target if fields[1] == "w" else 1.0 - target
                item = (fen, white_target)
                kept += 1
                if rng.random() < hold_frac:
                    holdout.offer(item)
                else:
                    buckets[bi].offer(item)

                if scanned % 2_000_000 == 0:
                    fill = ",".join(
                        f"{_BUCKETS[i][0][:4]}:{len(b.items) // 1000}k"
                        for i, b in enumerate(buckets)
                    )
                    print(
                        f"  scanned {scanned:,} kept {kept:,} | {fill} "
                        f"hold:{len(holdout.items) // 1000}k | {(time.time() - t0):.0f}s",
                        file=sys.stderr,
                    )

    # De-dup: holdout first, then train excluding any key in holdout (no leakage).
    hold_rows: list[tuple[str, float]] = []
    hold_keys: set[str] = set()
    for fen, tgt in holdout.items:
        k = _fen_key(fen)
        if k in hold_keys:
            continue
        hold_keys.add(k)
        hold_rows.append((fen, tgt))

    train_rows: list[tuple[str, float]] = []
    train_keys: set[str] = set()
    per_bucket_final = [0] * len(_BUCKETS)
    for i, b in enumerate(buckets):
        for fen, tgt in b.items:
            k = _fen_key(fen)
            if k in hold_keys or k in train_keys:
                continue
            train_keys.add(k)
            train_rows.append((fen, tgt))
            per_bucket_final[i] += 1
    rng.shuffle(train_rows)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write(out_dir / args.train, train_rows)
    _write(out_dir / args.holdout, hold_rows)

    dt = time.time() - t0
    rate = 1000 * dt / max(scanned, 1)
    print(f"\nscanned {scanned:,} in {dt:.0f}s ({rate:.3f} ms/line)", file=sys.stderr)
    print(f"  dropped: bad={bad:,} in_check={in_check:,} tactical={tactical:,}", file=sys.stderr)
    print(f"  kept (pre-dedup) {kept:,} | train {len(train_rows):,} | holdout {len(hold_rows):,}")
    mix = " ".join(f"{_BUCKETS[i][0]}={per_bucket_final[i]:,}" for i in range(len(_BUCKETS)))
    print(f"  train phase mix: {mix}")
    tm = sum(t for _, t in train_rows) / max(len(train_rows), 1)
    print(f"  train target mean (White POV) = {tm:.4f}  (0.5 = balanced)")
    return 0


def _is_quiet_captures(board: Board) -> bool:
    """Quiet = the side to move has no winning capture (SEE > 0)."""
    return all(_see(board, mv) <= 0 for mv in generate_captures(board))


def _write(path: Path, rows: list[tuple[str, float]]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(f"{fen};{tgt:.6g}\n" for fen, tgt in rows)
    print(f"wrote {len(rows):,} rows -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
