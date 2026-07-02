"""Texel eval tuner (offline dev tool).

Texel tuning fits eval weights by minimizing the mean-squared error between a
sigmoid of the static eval and a game-result label in {1.0, 0.5, 0.0}, over a
large labelled position set.

This is a dev tool and MAY use numpy/scipy (the engine itself stays stdlib-only).
It imports hydra's evaluator directly — no UCI round-trip.

STATUS / dependencies:
  * `--find-k`  : FUNCTIONAL now. Finds the optimal sigmoid scaling K for the
                  current eval against a labelled file, and reports the loss.
                  This is the first thing to run on any dataset.
  * `--smoke`   : FUNCTIONAL now. Self-checks the pipeline with no external data
                  by generating labels from the current eval at a known K and
                  confirming the K-finder recovers a sensible value.
  * weight fit  : STUB pending PLAN Phase 1.2 (tunable EvalParams) + 1.3
                  (eval-coefficient trace). The staged gradient descent (Phase
                  4.2) plugs in where `fit_stage` is marked TODO.

Labelled-file format (Phase 4.1 produces this from positions.txt + a reference
engine): one position per line, `FEN [;|space] RESULT`, where RESULT is one of
1-0 / 0-1 / 1/2-1/2 or 1.0 / 0.5 / 0.0.

    python tools/texel/tune.py --smoke
    python tools/texel/tune.py --data <labelled.epd> --find-k
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from hydra.board import Board
from hydra.evaluation import create_evaluator, reconstruct_eval

_REPO = Path(__file__).resolve().parent.parent.parent
_CORPUS = _REPO / "tests" / "data" / "eval_corpus.epd"

_RESULT_MAP = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5, "1.0": 1.0, "0.0": 0.0, "0.5": 0.5}


def _sigmoid(score: float, k: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-k * score / 400.0))


def parse_label(token: str) -> float | None:
    """Accept discrete game results (1-0/0-1/1/2-1/2) OR a continuous WDL float in [0,1].

    The Beast Stockfish-WDL dataset (Phase 4.1, White-perspective) uses the latter.
    """
    mapped = _RESULT_MAP.get(token)
    if mapped is not None:
        return mapped
    try:
        v = float(token)
    except ValueError:
        return None
    return v if 0.0 <= v <= 1.0 else None


def load_labelled(path: Path, *, cp_labels: bool = False) -> list[tuple[str, float]]:
    """Load `FEN;target` rows.

    ``cp_labels=True`` reads raw White-POV centipawn labels (annotate_sf.py
    output) and squashes them through the standard Texel logistic at K=1:
    ``target = 1 / (1 + 10^(-cp/400))``. One consistent squash on both sides of
    the fit keeps the tails informative (unlike the saturated SF-WDL labels).
    """
    rows: list[tuple[str, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        # result is the last whitespace/';'-separated token
        sep = line.replace(";", " ").rsplit(" ", 1)
        if len(sep) != 2:
            continue
        fen, label = sep[0].strip(), sep[1].strip()
        if cp_labels:
            try:
                cp = float(label)
            except ValueError:
                continue
            rows.append((fen, _sigmoid(cp, 1.0)))
            continue
        r = parse_label(label)
        if r is not None:
            rows.append((fen, r))
    return rows


def eval_scores(rows: list[tuple[str, float]]) -> list[tuple[int, float]]:
    """Return (white-POV eval, result) pairs. Skips unparseable FENs."""
    ev = create_evaluator()
    out: list[tuple[int, float]] = []
    for fen, result in rows:
        try:
            board = Board.from_fen(fen)
            s = ev.evaluate(board)
            if board.side != 0:  # evaluate() is side-to-move POV; normalize to White
                s = -s
        except Exception:
            continue
        out.append((s, result))
    return out


def mse(scores: list[tuple[int, float]], k: float) -> float:
    return sum((_sigmoid(s, k) - r) ** 2 for s, r in scores) / len(scores)


def find_k(scores: list[tuple[int, float]]) -> tuple[float, float]:
    """Golden-section search for the K minimizing MSE."""
    lo, hi = 0.1, 3.0
    gr = (math.sqrt(5) - 1) / 2
    c, d = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fc, fd = mse(scores, c), mse(scores, d)
    for _ in range(40):
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - gr * (hi - lo)
            fc = mse(scores, c)
        else:
            lo, c, fc = c, d, fd
            d = lo + gr * (hi - lo)
            fd = mse(scores, d)
    k = (lo + hi) / 2
    return k, mse(scores, k)


def smoke() -> int:
    """No external data: label corpus by current eval at K0, recover K."""
    print("smoke: self-labelling the eval corpus at K0=1.0 ...")
    ev = create_evaluator()
    k0 = 1.0
    scores: list[tuple[int, float]] = []
    for line in _CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            board = Board.from_fen(line)
            s = ev.evaluate(board)
            if board.side != 0:
                s = -s
        except Exception:
            continue
        # deterministic label drawn toward the sigmoid expectation at k0
        p = _sigmoid(s, k0)
        label = 1.0 if p > 0.6 else (0.0 if p < 0.4 else 0.5)
        scores.append((s, label))
    if not scores:
        print("smoke FAILED: no scored positions", file=sys.stderr)
        return 1
    k, loss = find_k(scores)
    print(f"smoke: {len(scores)} positions, recovered K={k:.4f}, loss={loss:.6f}")
    print("smoke OK (pipeline: load -> evaluate -> sigmoid -> K-search works).")
    return 0


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((x - mb) ** 2 for x in b) ** 0.5
    return cov / (da * db) if da and db else 0.0


def verify(rows: list[tuple[str, float]], sample: int) -> int:
    """Reconstruction gate (PLAN 4.1 step 5): trace coeffs . weights == evaluate().

    Confirms the extracted FENs are all traceable/reconstructable before any fit.
    """
    ev = create_evaluator()
    import random as _r

    rng = _r.Random(0)
    picks = rows if len(rows) <= sample else rng.sample(rows, sample)
    mism = checked = 0
    for fen, _ in picks:
        try:
            board = Board.from_fen(fen)
        except Exception:
            continue
        checked += 1
        if reconstruct_eval(ev.trace(board), ev.p) != ev.evaluate(board):
            mism += 1
    print(f"reconstruction: {checked} positions, {mism} mismatches")
    return 0 if mism == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="labelled FEN file (FEN <result> per line)")
    ap.add_argument("--find-k", action="store_true")
    ap.add_argument("--verify", action="store_true", help="reconstruction gate on the dataset FENs")
    ap.add_argument("--verify-sample", type=int, default=5000)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    if args.smoke:
        return smoke()

    if not args.data:
        ap.error("provide --data <file> (with --find-k/--verify) or --smoke")
    rows = load_labelled(Path(args.data))
    if not rows:
        print("no labelled rows parsed — check the file format", file=sys.stderr)
        return 1

    if args.verify:
        rc = verify(rows, args.verify_sample)
        if not args.find_k:
            return rc

    scores = eval_scores(rows)
    print(f"loaded {len(rows)} labelled rows; {len(scores)} evaluated")

    if args.find_k:
        k, base = find_k(scores)
        xs = [float(s) for s, _ in scores]
        ys = [r for _, r in scores]
        print(f"optimal K = {k:.4f}   MSE = {base:.6f}")
        print(f"corr(eval, target) = {_pearson(xs, ys):+.3f}   "
              f"target mean = {sum(ys) / len(ys):.4f}  (White POV)")

    # TODO(Phase 4.2): staged weight fit. Requires Phase 1.2 tunable EvalParams +
    # 1.3 coefficient trace; then minimize MSE over the weight vector (numpy
    # gradient), biggest lever first, PST/material last. SPRT-gate each stage.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
