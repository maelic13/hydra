"""Hydra-native SPSA tuner for search constants (self-contained; no weather-factory).

SPSA = Simultaneous Perturbation Stochastic Approximation. Each iteration:
  1. draw a random +/-1 perturbation `delta` for every parameter,
  2. build two engine variants theta+ = theta + c_k*delta and theta- = theta - c_k*delta,
  3. play a fastchess mini-match theta+ vs theta- (same source tree, different UCI
     options), measure the score from theta+'s side,
  4. nudge every parameter up the estimated gradient,
  5. checkpoint to state.json (resumable).

It drives fastchess exactly like tools/sprt.ps1 does (run_hydra.cmd shim, isolated
`python -S`). The tunable parameters must be exposed as UCI spin options first
(PLAN Phase 1.1); until then this runs but the options are no-ops.

WORKFLOW RULE: the dev agent never runs this (it plays games). The user runs it
and reports back; SPSA only *proposes* values — a confirming SPRT decides.

Run:    python tools/spsa/tune.py --config tools/spsa/config_search.json
Resume: python tools/spsa/tune.py --resume
Smoke:  python tools/spsa/tune.py --config ... --iters 1 --games 2   (plumbing only)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_REPO = _TOOLS.parent
_FASTCHESS = _TOOLS / "bin" / "fastchess.exe"
_SHIM = _TOOLS / "run_hydra.cmd"
_STATE = _HERE / "state.json"

_SCORE_RE = re.compile(r"Score of .*?:\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)")


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _quantize(name: str, value: float, spec: dict) -> int | float:
    v = _clamp(value, spec["min"], spec["max"])
    return int(round(v)) if spec.get("int", True) else round(v, 4)


def play_match(
    theta_plus: dict[str, float],
    theta_minus: dict[str, float],
    cfg: dict,
    specs: dict[str, dict],
) -> float:
    """Return score in [-1, 1] from theta_plus's perspective over the mini-match."""
    def opts(theta: dict[str, float]) -> list[str]:
        out = []
        for name, spec in specs.items():
            out.append(f"option.{name}={_quantize(name, theta[name], spec)}")
        return out

    book = Path(cfg["book"])
    if not book.is_absolute():
        book = _REPO / book
    games = cfg.get("games", 32)
    args = [
        str(_FASTCHESS),
        "-engine", "name=plus", f"cmd={_SHIM}", f"args={_REPO}", *opts(theta_plus),
        "-engine", "name=minus", f"cmd={_SHIM}", f"args={_REPO}", *opts(theta_minus),
        "-each", "proto=uci", f"tc={cfg.get('tc', '8+0.08')}", f"option.Hash={cfg.get('hash', 64)}",
        "-openings", f"file={book}", "format=epd", "order=random",
        "-games", "2", "-repeat",
        "-rounds", str(max(1, games // 2)),
        "-concurrency", str(cfg.get("concurrency", 8)),
    ]
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    m = None
    for line in proc.stdout.splitlines():
        mm = _SCORE_RE.search(line)
        if mm:
            m = mm
    if m is None:
        sys.stderr.write(proc.stdout[-2000:] + "\n" + proc.stderr[-1000:] + "\n")
        raise RuntimeError("could not parse fastchess score line")
    w, lo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    n = w + lo + d
    return (w - lo) / n if n else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(_HERE / "config_search.json"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--iters", type=int, default=0, help="stop after N iters (0 = config A budget)")
    ap.add_argument("--games", type=int, default=0, help="override games per iter")
    args = ap.parse_args()

    if not _FASTCHESS.exists():
        print(f"ERROR: fastchess not found at {_FASTCHESS}", file=sys.stderr)
        return 2

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.games:
        cfg["games"] = args.games
    specs: dict[str, dict] = cfg["params"]
    hp = cfg.get("spsa", {"a": 1.0, "c": 1.0, "A": 250.0, "alpha": 0.602, "gamma": 0.101})

    if args.resume and _STATE.exists():
        state = json.loads(_STATE.read_text(encoding="utf-8"))
        theta = state["theta"]
        k0 = state["k"]
        print(f"resumed at iter {k0}")
    else:
        theta = {n: float(s["start"]) for n, s in specs.items()}
        k0 = 0

    import random
    rng = random.Random(cfg.get("seed", 12345))
    max_iters = args.iters or cfg.get("iters", 2500)

    for k in range(k0, k0 + max_iters):
        a_k = hp["a"] / (hp["A"] + k + 1) ** hp["alpha"]
        c_k = hp["c"] / (k + 1) ** hp["gamma"]
        delta = {n: (1.0 if rng.random() < 0.5 else -1.0) for n in specs}
        theta_plus = {n: theta[n] + c_k * specs[n]["c"] * delta[n] for n in specs}
        theta_minus = {n: theta[n] - c_k * specs[n]["c"] * delta[n] for n in specs}

        score = play_match(theta_plus, theta_minus, cfg, specs)

        for n in specs:
            ghat = score / (c_k * specs[n]["c"] * delta[n])
            theta[n] = _clamp(theta[n] + a_k * specs[n]["r"] * ghat, specs[n]["min"], specs[n]["max"])

        baked = {n: _quantize(n, theta[n], specs[n]) for n in specs}
        print(f"iter {k + 1}: score={score:+.3f}  -> {baked}")
        _STATE.write_text(json.dumps({"k": k + 1, "theta": theta, "baked": baked}, indent=2),
                          encoding="utf-8")

    print("\nProposed values (review against bounds, then SPRT-confirm — PLAN rule 10):")
    print(json.dumps({n: _quantize(n, theta[n], specs[n]) for n in specs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
