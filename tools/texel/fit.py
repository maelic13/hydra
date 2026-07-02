#!/usr/bin/env python3
"""Staged Texel gradient fit (Phase 4.2).

Fits eval weights so `sigmoid(K * eval)` predicts the dataset target, one weight
GROUP (stage) at a time, biggest lever first (PLAN §7). Each stage:

    extract → fit (Adam) → report holdout → propose ints → (you) bake + SPRT.

The maths that makes this fast and exact for the *linear* weight groups: the
White-POV eval is an exact linear function of the weights, because the phase
taper and the frozen Phase-3.3 transform (eg-scale / winnable / rule-50) are
per-position constants. So for a stage's active keys we precompute, per position,
the effective slope `a_j = d(eval)/d(w_j)` and a frozen constant `b`, giving
`eval(w) = A·w + b`. Gradient descent then runs in numpy over compact arrays.

    eval_white(w) = (r50/128) * [ (mg·phase + eg·(24-phase)·eg_scale/64)/24
                                  + tempo + winnable ]
    mg = residual_mg + Σ cmg[k]·w_k ,  eg = residual_eg + Σ ceg[k]·w_k

The nonlinear groups (king-safety-v2, scale/winnable/rule-50) are NOT linear in
their own weights and need a finite-difference path — not yet implemented here.

Dev tool: uses numpy (`pip install -e ".[tune]"`). The engine stays stdlib-only.

    python tools/texel/fit.py --stage material \
        --data tools/texel/data/beast_train.csv \
        --holdout tools/texel/data/beast_holdout.csv
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np

from hydra.board import Board
from hydra.evaluation import ClassicalEvaluator, EvalParams

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tune import load_labelled

_LN10 = math.log(10.0)
_TOTAL_PHASE = 24
_SCALE_NORMAL = 64
_RULE50_BASE = 128

# Linear weight groups → the EvalParams attributes they cover. Indexed (list)
# attributes are expanded to one key per element. Order = PLAN §7 staging.
_LINEAR_GROUPS: dict[str, tuple[str, ...]] = {
    # 1. Material — piece values (pawn anchored as the scale reference via K; king
    #    is not a material term). Handled specially in _stage_keys.
    "material": ("mg_val", "eg_val"),
    # 2. Mobility tables.
    "mobility": (
        "knight_mob_mg", "knight_mob_eg", "bishop_mob_mg", "bishop_mob_eg",
        "rook_mob_mg", "rook_mob_eg", "queen_mob_mg", "queen_mob_eg",
    ),
    # 3. Pawn-structure scalars + passed-rank table.
    "pawns": (
        "doubled_mg", "doubled_eg", "isolated_mg", "isolated_eg",
        "connected_mg", "connected_eg", "backward_mg", "backward_eg",
        "passed_mg", "passed_eg",
    ),
    # 4. Passed-pawn-richness block (Phase 3.4).
    "passers": (
        "passed_blocked_mg", "passed_blocked_eg", "passed_free_mg", "passed_free_eg",
        "passed_protected_mg", "passed_protected_eg", "passed_ekdist_eg",
    ),
    # 6. Threats block (Phase 3.1).
    "threats": (
        "threat_minor_major_mg", "threat_minor_major_eg",
        "threat_rook_queen_mg", "threat_rook_queen_eg",
        "threat_weak_mg", "threat_weak_eg",
    ),
    # 7a. Imbalance (Phase 3.5).
    "imbalance": ("imb_knight_pawn", "imb_rook_pawn", "imb_bishop_pawn"),
    # 7b. Space + minor positional (Phase 3.6).
    "minor": (
        "space_mg", "bad_bishop_mg", "bad_bishop_eg",
        "connected_rooks_mg", "connected_rooks_eg",
    ),
    # Piece scalars (rooks/bishop-pair/outpost/pawn-threat).
    "pieces": (
        "bishop_pair_mg", "bishop_pair_eg", "rook_open_mg", "rook_open_eg",
        "rook_semi_mg", "rook_semi_eg", "rook_7th_mg", "rook_7th_eg",
        "rook_behind_passed_mg", "rook_behind_passed_eg", "outpost_mg", "outpost_eg",
        "pawn_threat_mg", "pawn_threat_eg",
    ),
    # 8. PST (material is its own stage; kept disjoint so the two stay identifiable).
    "pst": ("pst_mg", "pst_eg"),
}

# Nonlinear groups — tuned by finite difference (the A·w+b surrogate does not
# apply). Each: (weight specs [(attr, lo, hi, step)], activation-flag attrs to
# force True while tuning). King safety runs its danger sum through a quadratic
# curve + array index; the scale group gates/multiplies the final transform.
_FD_GROUPS: dict[str, tuple[list[tuple[str, int, int, int]], tuple[str, ...]]] = {
    "kingsafety": (
        [
            ("safe_check_knight", 0, 150, 6),
            ("safe_check_bishop", 0, 150, 6),
            ("safe_check_rook", 0, 150, 6),
            ("safe_check_queen", 0, 150, 6),
            ("king_weak_square", 0, 80, 4),
            ("no_queen_atten", 0, 80, 4),
        ],
        (),  # ks_v2_active auto-enables from the weights in rebuild()
    ),
    "scale": (
        [
            ("ocb_scale", 16, 64, 4),      # <64 scales opposite-bishop endings toward draw
            ("winnable_const", -80, 80, 4),
            ("winnable_pawn", -20, 20, 2),
            ("winnable_flanks", -80, 80, 4),
            ("rule50_damp", 0, 64, 4),     # damp the score as the halfmove clock climbs
        ],
        ("scale_active", "winnable_active"),
    ),
}

# Hybrid SPRT bundles (PLAN §7 / user decision): each is fit stage-by-stage,
# re-tracing between stages, then baked + gated as ONE candidate.
_BUNDLES: dict[str, tuple[str, ...]] = {
    "bundle1": ("material", "mobility", "pawns", "pst"),
    "bundle2": ("passers", "pieces", "imbalance", "minor", "threats"),
    # bundle3 = king-safety only. scale/winnable/rule50 are game-situational
    # (rare trigger) — MSE-vs-cp can't tune them (it gets WORSE); they belong in
    # the Phase 5 SPSA wave (game-result tuning). The "scale" FD group stays
    # defined for that optional use, but is not gated here.
    "bundle3": ("kingsafety",),
}


def _weight_of(p: EvalParams, key: tuple) -> float:
    val = getattr(p, key[0])
    for idx in key[1:]:
        val = val[idx]
    return float(val)


def _stage_keys(p: EvalParams, stage: str) -> list[tuple]:
    """Flat list of (attr, *idx) keys tuned by a stage."""
    if stage not in _LINEAR_GROUPS:
        msg = f"unknown/non-linear stage {stage!r}; linear stages: {sorted(_LINEAR_GROUPS)}"
        raise SystemExit(msg)
    keys: list[tuple] = []
    for attr in _LINEAR_GROUPS[stage]:
        val = getattr(p, attr)
        if isinstance(val, list):
            if attr in {"mg_val", "eg_val"}:
                # piece values: N,B,R,Q only (pawn anchored, king not material)
                keys.extend((attr, pt) for pt in (1, 2, 3, 4))
            elif attr in {"pst_mg", "pst_eg"}:
                for pt in range(6):
                    keys.extend((attr, pt, sq) for sq in range(64))
            else:
                keys.extend((attr, i) for i in range(len(val)))
        else:
            keys.append((attr,))
    return keys


def _extract(rows: list[tuple[str, float]], keys: list[tuple], ev, limit: int):
    """Trace positions → (A, b, y): eval_white(w) = A·w + b (float, exact linear)."""
    p = ev.p
    key_index = {k: j for j, k in enumerate(keys)}
    w0 = np.array([_weight_of(p, k) for k in keys], dtype=np.float64)
    n = min(len(rows), limit)
    a_rows = np.zeros((n, len(keys)), dtype=np.float32)
    bvec = np.zeros(n, dtype=np.float64)
    yvec = np.zeros(n, dtype=np.float64)
    tempo = float(p.tempo)

    kept = 0
    diffsum = 0.0
    diffmax = 0.0
    for fen, target in rows[:n]:
        try:
            board = Board.from_fen(fen)
        except Exception:
            continue
        tr = ev.trace(board)
        phase = tr.phase
        egf = (_TOTAL_PHASE - phase) * (tr.eg_scale / _SCALE_NORMAL)
        r50 = tr.r50_num / _RULE50_BASE
        # full mg/eg with current weights
        mg = float(tr.residual_mg) + sum(c * _weight_of(p, k) for k, c in tr.cmg.items())
        eg = float(tr.residual_eg) + sum(c * _weight_of(p, k) for k, c in tr.ceg.items())
        # active-key slopes + subtract their current contribution to get frozen mg0/eg0
        a_row = a_rows[kept]
        mg_active = eg_active = 0.0
        for k, c in tr.cmg.items():
            j = key_index.get(k)
            if j is not None:
                a_row[j] += r50 * (c * phase) / _TOTAL_PHASE
                mg_active += c * w0[j]
        for k, c in tr.ceg.items():
            j = key_index.get(k)
            if j is not None:
                a_row[j] += r50 * (c * egf) / _TOTAL_PHASE
                eg_active += c * w0[j]
        mg0 = mg - mg_active
        eg0 = eg - eg_active
        b = r50 * ((mg0 * phase + eg0 * egf) / _TOTAL_PHASE + tempo + tr.winnable)
        bvec[kept] = b
        yvec[kept] = target
        # self-check: b + a·w0 must reproduce the float eval (mg,eg through taper)
        model = b + float(a_row @ w0)
        ref = r50 * ((mg * phase + eg * egf) / _TOTAL_PHASE + tempo + tr.winnable)
        d = abs(model - ref)
        diffsum += d
        diffmax = max(diffmax, d)
        kept += 1

    return a_rows[:kept], bvec[:kept], yvec[:kept], w0, (diffsum / max(kept, 1), diffmax)


def _sigmoid(e: np.ndarray, k: float) -> np.ndarray:
    return 1.0 / (1.0 + np.power(10.0, -k * e / 400.0))


def _mse(e: np.ndarray, y: np.ndarray, k: float) -> float:
    return float(np.mean((_sigmoid(e, k) - y) ** 2))


def _find_k(e: np.ndarray, y: np.ndarray) -> float:
    lo, hi = 0.1, 3.0
    gr = (math.sqrt(5) - 1) / 2
    c, d = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fc, fd = _mse(e, y, c), _mse(e, y, d)
    for _ in range(40):
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - gr * (hi - lo)
            fc = _mse(e, y, c)
        else:
            lo, c, fc = c, d, fd
            d = lo + gr * (hi - lo)
            fd = _mse(e, y, d)
    return (lo + hi) / 2


def _fit(A, b, y, w0, epochs, lr, fix_k=0.0):
    """Adam on the weight vector; K refit every 10 epochs unless *fix_k* pins it.

    Pinning K (``--fix-k 1``) anchors the eval to the label's cp scale: the fit
    can no longer trade a global eval inflation against a smaller K, so the
    cp-denominated search margins (futility/razoring/aspiration...) keep their
    meaning.
    """
    w = w0.astype(np.float64).copy()
    m = np.zeros_like(w)
    v = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8
    n = len(y)
    k = fix_k if fix_k > 0 else _find_k(A @ w + b, y)
    for t in range(1, epochs + 1):
        e = A @ w + b
        s = _sigmoid(e, k)
        # dL/de = 2/n (s - y) · s(1-s) · ln10·K/400
        dloss_de = (2.0 / n) * (s - y) * s * (1.0 - s) * (_LN10 * k / 400.0)
        grad = A.T @ dloss_de
        m = b1 * m + (1 - b1) * grad
        v = b2 * v + (1 - b2) * grad * grad
        mhat = m / (1 - b1**t)
        vhat = v / (1 - b2**t)
        w -= lr * mhat / (np.sqrt(vhat) + eps)
        if fix_k <= 0 and t % 10 == 0:
            k = _find_k(A @ w + b, y)
    if fix_k <= 0:
        k = _find_k(A @ w + b, y)
    return w, k


def _prebuild(rows: list[tuple[str, float]], limit: int) -> tuple[list, np.ndarray]:
    """Parse subsample FENs to Board objects ONCE (the FD loop re-evals many times)."""
    boards = []
    targets = []
    for fen, target in rows[:limit]:
        try:
            board = Board.from_fen(fen)
        except Exception:
            continue
        boards.append(board)
        targets.append(target)
    return boards, np.array(targets, dtype=np.float64)


def _fd_loss(boards: list, y: np.ndarray, ev, k: float) -> float:
    """MSE of sigmoid(K·eval) vs target over prebuilt boards, at the CURRENT weights."""
    ev.invalidate_caches()
    e = np.empty(len(boards), dtype=np.float64)
    for i, board in enumerate(boards):
        s = ev.evaluate(board)
        e[i] = s if board.side == 0 else -s
    return _mse(e, y, k)


def _fd_fit(boards, y, ev, specs, activate, epochs, lr, fix_k):
    """Finite-difference Adam for a small set of nonlinear integer weights.

    The weights are used as danger indices / curve inputs / conditional
    multipliers, so they must stay integer: keep a float accumulator but ALWAYS
    evaluate at round(w), and estimate the gradient by central difference with a
    PER-WEIGHT step (scales differ — e.g. safe-check ~6 vs ocb_scale). Cheap
    because each group is only a handful of weights.
    """
    keys = [(spec[0],) for spec in specs]
    lo = np.array([spec[1] for spec in specs], dtype=np.float64)
    hi = np.array([spec[2] for spec in specs], dtype=np.float64)
    steps = np.array([spec[3] for spec in specs], dtype=np.float64)
    for flag in activate:  # e.g. scale_active/winnable_active — enable the term
        setattr(ev.p, flag, True)
    w = np.clip([_weight_of(ev.p, k) for k in keys], lo, hi)
    m = np.zeros_like(w)
    v = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8
    k = fix_k if fix_k > 0 else 1.0

    def loss_at(vec: np.ndarray) -> float:
        _apply(ev.p, keys, vec)
        return _fd_loss(boards, y, ev, k)

    base = loss_at(np.round(w))
    for t in range(1, epochs + 1):
        cur = np.clip(np.round(w), lo, hi)
        grad = np.zeros_like(w)
        for j in range(len(keys)):
            up = cur.copy()
            up[j] = min(hi[j], up[j] + steps[j])
            dn = cur.copy()
            dn[j] = max(lo[j], dn[j] - steps[j])
            span = up[j] - dn[j]
            if span > 0:
                grad[j] = (loss_at(up) - loss_at(dn)) / span
        m = b1 * m + (1 - b1) * grad
        v = b2 * v + (1 - b2) * grad * grad
        mhat = m / (1 - b1**t)
        vhat = v / (1 - b2**t)
        # Adam's normalised step is ~lr uniformly; scale it per-weight by `step`
        # so wide-range weights (ocb_scale) move proportionally to narrow ones.
        w = np.clip(w - lr * steps * mhat / (np.sqrt(vhat) + eps), lo, hi)
    end = np.clip(np.round(w), lo, hi)
    base_end = loss_at(end)
    return end, base, base_end


def _apply(p: EvalParams, keys: list[tuple], w: np.ndarray) -> None:
    """Write fitted (rounded) weights into *p* in place, then rebuild derived tables."""
    for j, key in enumerate(keys):
        val = round(float(w[j]))
        if len(key) == 1:
            setattr(p, key[0], val)
        else:
            container = getattr(p, key[0])
            for i in key[1:-1]:
                container = container[i]
            container[key[-1]] = val
    p.rebuild()


def _direct_mse(rows: list[tuple[str, float]], ev, limit: int,
                fix_k: float = 0.0) -> tuple[float, float]:
    """Ground-truth MSE (integer eval, not the linear surrogate): White-POV eval
    each row with the evaluator's CURRENT weights, fit K, return (mse, K)."""
    ev.invalidate_caches()  # weights changed since the last call -> drop stale cache
    e = np.empty(min(len(rows), limit), dtype=np.float64)
    y = np.empty_like(e)
    n = 0
    for fen, target in rows[:limit]:
        try:
            board = Board.from_fen(fen)
        except Exception:
            continue
        s = ev.evaluate(board)
        e[n] = s if board.side == 0 else -s
        y[n] = target
        n += 1
    e, y = e[:n], y[:n]
    k = fix_k if fix_k > 0 else _find_k(e, y)
    return _mse(e, y, k), k


def _expand_stages(stages: str) -> list[str]:
    out: list[str] = []
    for raw in stages.split(","):
        token = raw.strip()
        if token in _BUNDLES:
            out.extend(_BUNDLES[token])
        elif token:
            out.append(token)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", required=True,
                    help="comma-separated stage/bundle names (e.g. 'material' or 'bundle1')")
    ap.add_argument("--data", required=True, help="train FEN;target file")
    ap.add_argument("--holdout", help="holdout FEN;target file")
    ap.add_argument("--max-positions", type=int, default=400_000)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--lr", type=float, default=2.0)
    ap.add_argument("--cp-labels", action="store_true",
                    help="labels are raw White-POV centipawns (annotate_sf.py output)")
    ap.add_argument("--fix-k", type=float, default=0.0,
                    help="pin the sigmoid K (use 1.0 with --cp-labels to anchor the eval scale)")
    ap.add_argument("--out", help="write the combined fitted weights as 'attr idx.. value' lines")
    args = ap.parse_args()

    stages = _expand_stages(args.stages)
    # Private (non-shared) params so mutating between stages never touches the
    # global DEFAULT_EVAL_PARAMS singleton; forces the recompute path in evaluate().
    ev = ClassicalEvaluator(EvalParams())
    print(f"stages: {stages}", file=sys.stderr)

    train = load_labelled(Path(args.data), cp_labels=args.cp_labels)
    hold = load_labelled(Path(args.holdout), cp_labels=args.cp_labels) if args.holdout else None
    h_lim = min(args.max_positions, 100_000)

    base_hmse = None
    if hold is not None:
        base_hmse, _ = _direct_mse(hold, ev, h_lim, fix_k=args.fix_k)

    touched: dict[tuple, int] = {}
    fd_boards = None  # lazily built once for the finite-difference stages
    for stage in stages:
        t0 = time.time()
        if stage in _FD_GROUPS:
            specs, activate = _FD_GROUPS[stage]
            attrs = [s[0] for s in specs]
            if fd_boards is None:
                fd_boards = _prebuild(train, min(args.max_positions, 40_000))
            boards, yb = fd_boards
            fk = args.fix_k if args.fix_k > 0 else 1.0
            fd_epochs = min(args.epochs, 40)  # each epoch re-evals the subsample
            w, l0, l1 = _fd_fit(boards, yb, ev, specs, activate, fd_epochs, args.lr, fk)
            keys = [(a,) for a in attrs]
            _apply(ev.p, keys, w)
            vals = [int(x) for x in w]
            for a, val in zip(attrs, vals, strict=True):
                touched[a,] = val
            for flag in activate:  # bake the enable flag (1 -> loader/bake read as True)
                touched[flag,] = 1
            fitted = dict(zip(attrs, vals, strict=True))
            print(f"  [{stage:9s}] {len(attrs):4d} wts  FD MSE {l0:.6f}->{l1:.6f}  "
                  f"({time.time() - t0:.0f}s)  {fitted}", file=sys.stderr)
            continue
        keys = _stage_keys(ev.p, stage)
        amat, b, y, w0, (_dmean, dmax) = _extract(train, keys, ev, args.max_positions)
        k_init = args.fix_k if args.fix_k > 0 else _find_k(amat @ w0 + b, y)
        mse0 = _mse(amat @ w0 + b, y, k_init)
        w, k = _fit(amat, b, y, w0, args.epochs, args.lr, fix_k=args.fix_k)
        mse1 = _mse(amat @ w + b, y, k)
        _apply(ev.p, keys, w)  # bake into the working params so later stages see it
        for j, key in enumerate(keys):
            touched[key] = round(float(w[j]))
        print(f"  [{stage:9s}] {len(keys):4d} wts  train MSE {mse0:.6f}->{mse1:.6f}  "
              f"K={k:.3f}  ({time.time() - t0:.0f}s, self-check max={dmax:.3f})", file=sys.stderr)

    # Ground-truth cumulative holdout with the fully-tuned working params.
    if hold is not None:
        tuned_hmse, kt = _direct_mse(hold, ev, h_lim, fix_k=args.fix_k)
        flag = "OK (improved)" if tuned_hmse < base_hmse else "WARN (no gain)"
        print(f"\nholdout MSE {base_hmse:.6f} -> {tuned_hmse:.6f}  [K={kt:.3f}]  [{flag}]")

    # Combined fitted weights (only those that changed from the ORIGINAL defaults).
    orig = EvalParams()
    lines = []
    for key, new in touched.items():
        if round(_weight_of(orig, key)) != new:
            idx = " ".join(str(i) for i in key[1:])
            lines.append(f"{key[0]} {idx} {new}".rstrip())
    print(f"\n{len(lines)} weights changed across {len(stages)} stage(s)")
    if args.out:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} weights -> {args.out}")
    else:
        print("(pass --out <file> to write the weight file for baking / SPRT)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
