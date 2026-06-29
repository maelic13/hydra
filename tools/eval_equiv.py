"""Eval-equivalence fingerprint over the phase-balanced corpus.

PLAN gate rule 4: a behaviour-identical refactor (Phases 1-3) must leave
evaluate() unchanged. This computes a fingerprint of evaluate() across every FEN
in tests/data/eval_corpus.epd. Record it before a refactor; it must match after.

    python tools/eval_equiv.py            # print fingerprint + stats
    python tools/eval_equiv.py --verbose  # also per-phase sums
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from hydra.board import Board
from hydra.evaluation import create_evaluator

_REPO = Path(__file__).resolve().parent.parent
_CORPUS = _REPO / "tests" / "data" / "eval_corpus.epd"


def fingerprint(corpus: Path) -> tuple[str, int, int, int]:
    ev = create_evaluator()
    h = hashlib.sha256()
    n = total = bad = 0
    for line in corpus.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            board = Board.from_fen(line)
            score = ev.evaluate(board)
        except Exception:  # noqa: BLE001 - report unparseable/illegal FENs as bad
            bad += 1
            continue
        h.update(f"{score}\n".encode())
        total += score
        n += 1
    return h.hexdigest()[:16], n, total, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(_CORPUS))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    fp, n, total, bad = fingerprint(Path(args.corpus))
    print(f"eval fingerprint : {fp}")
    print(f"positions        : {n}")
    print(f"unparseable      : {bad}")
    print(f"score sum        : {total}")
    if bad:
        print("WARNING: some FENs failed to load — investigate before trusting the gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
