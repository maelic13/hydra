#!/usr/bin/env python3
"""Self-contained SPSA tuner for Hydra Lite.

No external tuner dependency. Drives fastchess matches between two perturbed
parameter sets of the engine (via the persistent UCI adapter) and walks the
parameters by SPSA, saving/resuming state in tools/spsa/state.json.

Why custom: weather-factory's runner assumes a single compiled .exe engine in
a tuner/ folder (cmd=./tuner/{engine} + cmd.split()), and fastchess on Windows
cannot drive a Python engine through a .bat shim. This driver launches the
engine the *exact* proven way tools/sprt_lite.ps1 does -- cmd=python "adapter"
--script "engine" passed as one argv token -- which fastchess handles fine.

The SPSA update math is ported verbatim from weather-factory's spsa.py
(simultaneous perturbation, Spall): perturb all params by +/- step*c_t, play
A vs B, move along the estimated gradient by a_t. Steps come from
config_b2.json (sized for a 2-3 Elo swing); a/c/A from spsa.json
(A ~= target_iterations / 10).

The only shared *binaries* are fastchess + the opening book -- the same ones
sprt_lite.ps1 reuses -- both overridable in match_b2.json.

Usage (run from the repo root):
    .venv\\Scripts\\python.exe tools\\spsa\\tune.py
    .venv\\Scripts\\python.exe tools\\spsa\\tune.py --resume      # continue a run
    .venv\\Scripts\\python.exe tools\\spsa\\tune.py --iters 2500  # stop after N

Acceptance: SPSA only *proposes*. After it converges, set the proposed values
in hydra_lite.py and run ONE confirming gainer SPRT (persistent, st=0.7) --
that is the real gate. See PLAN_lite.md section 6, B2.
"""
import argparse
import copy
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # tools/spsa/tune.py -> repo root
STATE_PATH = HERE / "state.json"


@dataclass
class Param:
    name: str
    value: float
    min_value: int
    max_value: int
    step: float

    def get(self) -> int:
        return round(self.value)

    def update(self, amt: float) -> None:
        self.value = min(max(self.value + amt, self.min_value), self.max_value)

    def as_uci(self) -> str:
        return f"option.{self.name}={self.get()}"

    def __str__(self) -> str:
        d = self.value - self._start
        sign = f"+{d:.2f}" if d > 0 else (f"{d:.2f}" if d < 0 else "+-0")
        return f"{self.name} = {self.get()}({sign}) in [{self.min_value}, {self.max_value}]"


@dataclass
class Spsa:
    a: float
    c: float
    A: int
    alpha: float = 0.601
    gamma: float = 0.102


def load_params(path: Path) -> list[Param]:
    cfg = json.loads(path.read_text())
    params = [Param(name, **c) for name, c in cfg.items()]
    for p in params:
        p._start = p.value
    return params


def build_engine_cmd(adapter: Path, engine: Path) -> str:
    # Same shape sprt_lite.ps1 uses: fastchess takes everything after cmd= as
    # the command line. sys.executable pins the exact interpreter running us.
    return f'"{sys.executable}" "{adapter}" --script "{engine}"'


def run_match(args, params_a: list[Param], params_b: list[Param]) -> tuple[int, int, int]:
    cmd_engine = build_engine_cmd(Path(args.adapter), Path(args.engine))
    fc = [
        args.fastchess,
        "-engine", f"cmd={cmd_engine}", "name=A", "proto=uci",
        *[p.as_uci() for p in params_a],
        "-engine", f"cmd={cmd_engine}", "name=B", "proto=uci",
        *[p.as_uci() for p in params_b],
        "-each", f"tc={args.tc}+{args.inc}",
        "-openings", f"file={args.book}", "format=pgn", "order=random", f"plies={args.plies}",
        "-repeat", "2", "-games", "2", "-rounds", str(args.games // 2),
        "-concurrency", str(args.concurrency),
        "-resign", "movecount=3", "score=400",
        "-draw", "movenumber=40", "movecount=8", "score=10",
        "-recover",
        "-output", "format=cutechess",
    ]
    w = l = d = 0
    saw_score = False
    try:
        proc = subprocess.Popen(fc, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, cwd=str(REPO))
    except OSError as e:
        print(f"  !! could not launch fastchess: {e}", flush=True)
        return 0, 0, 0
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("Score of"):
            seg = line[line.find(":") + 1: line.find("[")].split(" - ")
            try:
                w, l, d = int(seg[0]), int(seg[1]), int(seg[2])
                saw_score = True
            except (ValueError, IndexError):
                pass
        elif "startup failure" in line or "Fatal" in line:
            print(f"  !! fastchess: {line}", flush=True)
    proc.wait()
    if not saw_score:
        print("  !! match produced no score line (engine launch/timeout problem?)", flush=True)
    return w, l, d


def spsa_step(spsa: Spsa, params: list[Param], t: int, games: int, args) -> tuple[int, tuple[int, int, int]]:
    t += games
    a_t = spsa.a / (t + spsa.A) ** spsa.alpha
    c_t = spsa.c / t ** spsa.gamma
    delta = [random.randint(0, 1) * 2 - 1 for _ in params]

    pa: list[Param] = []
    pb: list[Param] = []
    for p, dl in zip(params, delta):
        s = dl * p.step * c_t
        a = copy.copy(p)
        b = copy.copy(p)
        a.update(s)
        b.update(-s)
        pa.append(a)
        pb.append(b)

    w, l, d = run_match(args, pa, pb)
    gradient = l - w  # A (the +delta side) loses more than it wins -> push away from A

    if (w + l + d) > 0:  # only move on a real result; a failed match leaves params put
        for p, dl in zip(params, delta):
            p.update(-(gradient / (dl * c_t)) * a_t * p.step)
    return t, (w, l, d)


def save_state(params: list[Param], t: int) -> None:
    STATE_PATH.write_text(json.dumps({
        "t": t,
        "params": [
            {"name": p.name, "value": p.value, "min_value": p.min_value,
             "max_value": p.max_value, "step": p.step, "start": p._start}
            for p in params
        ],
    }, indent=2))


def load_state() -> tuple[list[Param], int]:
    s = json.loads(STATE_PATH.read_text())
    params = []
    for c in s["params"]:
        p = Param(c["name"], c["value"], c["min_value"], c["max_value"], c["step"])
        p._start = c.get("start", c["value"])
        params.append(p)
    return params, s["t"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Self-contained SPSA tuner for Hydra Lite")
    ap.add_argument("--params", default=str(HERE / "config_b2.json"))
    ap.add_argument("--spsa", default=str(HERE / "spsa.json"))
    ap.add_argument("--match", default=str(HERE / "match_b2.json"),
                    help="JSON with tc/inc/games/concurrency/plies/fastchess/book")
    ap.add_argument("--engine", default=str(REPO / "hydra_lite" / "hydra_lite.py"))
    ap.add_argument("--adapter", default=str(REPO / "tools" / "ca_uci_persistent.py"))
    ap.add_argument("--resume", action="store_true", help="continue from state.json")
    ap.add_argument("--iters", type=int, default=0, help="stop after N iterations (0 = run until Ctrl+C)")
    ap.add_argument("--save-rate", type=int, default=10, help="save state every N iterations")
    cli = ap.parse_args()

    # Match settings: file provides defaults, then fold into the args namespace.
    m = json.loads(Path(cli.match).read_text())
    for k in ("tc", "inc", "games", "concurrency", "plies", "fastchess", "book"):
        setattr(cli, k, m[k])

    for p in (cli.fastchess, cli.book, cli.engine, cli.adapter):
        if not Path(p).exists():
            sys.exit(f"Not found: {p}")

    spsa_cfg = json.loads(Path(cli.spsa).read_text())
    spsa = Spsa(**spsa_cfg)

    if cli.resume and STATE_PATH.exists():
        params, t = load_state()
        print(f"Resuming from {STATE_PATH.name} at t={t} ({t // cli.games} iters)")
    else:
        if STATE_PATH.exists() and not cli.resume:
            print(f"NOTE: {STATE_PATH.name} exists but --resume not given; starting FRESH (it will be overwritten).")
        params = load_params(Path(cli.params))
        t = 0

    print("Engine:", cli.engine)
    print("Match: ", f"tc={cli.tc}+{cli.inc}  games/iter={cli.games}  concurrency={cli.concurrency}  plies={cli.plies}")
    print("SPSA:  ", spsa)
    print("Initial parameters:")
    for p in params:
        print("  ", p)
    print()

    avg = 0.0
    n = 0
    empty_streak = 0
    try:
        while True:
            if cli.iters and (t // cli.games) >= cli.iters:
                print(f"Reached --iters {cli.iters}; stopping.")
                break
            start = time.time()
            t, (w, l, d) = spsa_step(spsa, params, t, cli.games, cli)
            avg += time.time() - start
            n += 1
            it = t // cli.games

            if (w + l + d) == 0:
                empty_streak += 1
                if empty_streak >= 3:
                    sys.exit("Aborting: 3 consecutive matches produced no result. Check fastchess/engine setup.")
            else:
                empty_streak = 0

            print(f"iter {it}  (last match W{w} L{l} D{d}, {avg / n:.1f}s/iter)")
            for p in params:
                print("  ", p)
            print()
            if it % cli.save_rate == 0:
                save_state(params, t)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        save_state(params, t)
        print(f"Saved state to {STATE_PATH} (t={t}, {t // cli.games} iters).")
        print("Final parameters:")
        for p in params:
            print("  ", p)
        print("\nNext: set these in hydra_lite.py, then run the confirming SPRT (PLAN_lite.md B2).")


if __name__ == "__main__":
    main()
