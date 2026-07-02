#!/usr/bin/env python3
"""Annotate FEN positions with Stockfish search scores (Phase 4.1b relabel).

Replaces the legacy net_trainer labels (old SF, depth 10, WDL-expectation) with
fresh, gradient-friendly labels: **raw centipawn scores** from a current
Stockfish dev at a fixed node budget.

Why cp and not win-prob: the legacy labels went through python-chess's
`wdl().expectation()` -- Stockfish's own WDL model, which is far steeper than a
Texel logistic. 26.6% of the 2M training labels were fully saturated (<=0.01 or
>=0.99; 17% exactly 0/1), carrying no gradient about *magnitude*. Storing raw cp
keeps the full signal; the tuner applies ONE well-conditioned squash
(target = 1 / (1 + 10^(-cp/400))) at load time, and fitting with K fixed at 1
anchors Hydra's eval to Stockfish's normalized cp scale (100cp ~ 1 pawn), so the
cp-denominated search margins keep their meaning (no scale inflation).

Input : FEN-per-line file; a trailing `;target` (previous label) is stripped,
        so beast_train.csv / beast_holdout.csv are valid inputs directly.
Output: `FEN;cp` per line, cp = White-POV integer, mates/limits clamped to
        +/-2000.

Workers: N threads, each owning one single-threaded engine process (the parent
does no real work). Worker i takes input lines i, i+N, i+2N... and appends to
its own shard (`<out>.w<i>`); on restart, a worker skips as many inputs as its
shard already holds -> crash/stop-safe resume. When every shard is complete the
shards are merged (interleaved back to input order) into <out> and removed.

    python tools/texel/annotate_sf.py --input tools/texel/data/beast_train.csv \
        --out tools/texel/data/sf_train.csv --nodes 60000 --workers 12
"""

from __future__ import annotations

import argparse
import subprocess  # noqa: S404  (drives the local Stockfish binary over UCI)
import sys
import threading
import time
from pathlib import Path

_CLAMP = 2000


class _Engine:
    def __init__(self, exe: str, hash_mb: int) -> None:
        self.proc = subprocess.Popen(  # noqa: S603
            [exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self._cmd("uci")
        self._until("uciok")
        self._cmd("setoption name Threads value 1")
        self._cmd(f"setoption name Hash value {hash_mb}")
        self._cmd("isready")
        self._until("readyok")

    def _cmd(self, c: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(c + "\n")

    def _until(self, tok: str) -> str:
        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                msg = "engine process died"
                raise RuntimeError(msg)
            if line.startswith(tok):
                return line

    def score_white_pov(self, fen: str, nodes: int) -> int | None:
        """Search the position; return the last-reported score in White-POV cp."""
        self._cmd(f"position fen {fen}")
        self._cmd(f"go nodes {nodes}")
        assert self.proc.stdout is not None
        last: str | None = None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                msg = "engine process died"
                raise RuntimeError(msg)
            if line.startswith("info") and " score " in line and " lowerbound" not in line \
                    and " upperbound" not in line:
                last = line
            if line.startswith("bestmove"):
                break
        if last is None:
            return None
        toks = last.split()
        i = toks.index("score")
        kind, val = toks[i + 1], int(toks[i + 2])
        cp = val if kind == "cp" else (_CLAMP if val > 0 else -_CLAMP)
        cp = max(-_CLAMP, min(_CLAMP, cp))
        # UCI score is side-to-move POV; our datasets are White-POV.
        stm_white = fen.split()[1] == "w"
        return cp if stm_white else -cp

    def quit(self) -> None:
        try:
            self._cmd("quit")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def _worker(wid: int, fens: list[str], shard: Path, exe: str, nodes: int,
            hash_mb: int, progress: list[int], lock: threading.Lock) -> None:
    done = 0
    if shard.exists():
        done = sum(1 for _ in shard.open(encoding="utf-8"))
    todo = fens[done:]
    with lock:
        progress[wid] = done
    if not todo:
        return
    eng = _Engine(exe, hash_mb)
    try:
        _annotate_slice(eng, todo, shard, nodes, wid, done, progress, lock)
    finally:
        eng.quit()


def _annotate_slice(eng: _Engine, todo: list[str], shard: Path, nodes: int,
                    wid: int, done: int, progress: list[int], lock: threading.Lock) -> None:
    with shard.open("a", encoding="utf-8", newline="\n") as out:
        for i, fen in enumerate(todo, start=1):
            cp = eng.score_white_pov(fen, nodes)
            if cp is None:  # no scored line (should not happen) -> neutral marker
                cp = 0
            out.write(f"{fen};{cp}\n")
            if i % 200 == 0:
                out.flush()
                with lock:
                    progress[wid] = done + i
    with lock:
        progress[wid] = done + len(todo)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="FEN-per-line file (';target' suffix stripped)")
    ap.add_argument("--out", required=True, help="merged output file (FEN;cp)")
    ap.add_argument("--engine", default=r"D:\chess\engines\stockfish.exe")
    ap.add_argument("--nodes", type=int, default=60_000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--hash-mb", type=int, default=16)
    args = ap.parse_args()

    fens = []
    for raw in Path(args.input).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            fens.append(line.rsplit(";", 1)[0].strip())
    print(f"{len(fens):,} positions | engine {args.engine} | nodes {args.nodes} "
          f"| {args.workers} workers", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    slices = [fens[w::args.workers] for w in range(args.workers)]
    shards = [out.with_suffix(out.suffix + f".w{w}") for w in range(args.workers)]

    progress = [0] * args.workers
    lock = threading.Lock()
    threads = [
        threading.Thread(target=_worker, daemon=True,
                         args=(w, slices[w], shards[w], args.engine, args.nodes,
                               args.hash_mb, progress, lock))
        for w in range(args.workers)
    ]
    t0 = time.time()
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(15)
        with lock:
            done = sum(progress)
        pct = 100 * done / max(len(fens), 1)
        rate = done / max(time.time() - t0, 1)
        eta = (len(fens) - done) / max(rate, 1e-9) / 3600
        print(f"  {done:,}/{len(fens):,} ({pct:.1f}%)  {rate:.0f} pos/s  ETA {eta:.2f} h",
              file=sys.stderr)
    for t in threads:
        t.join()

    # Merge shards back to input order (round-robin interleave).
    shard_lines = [s.read_text(encoding="utf-8").splitlines() for s in shards]
    if any(len(sl) != len(slices[w]) for w, sl in enumerate(shard_lines)):
        print("ERROR: incomplete shards -- rerun to resume; shards kept.", file=sys.stderr)
        return 1
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for i in range(len(fens)):
            fh.write(shard_lines[i % args.workers][i // args.workers] + "\n")
    for s in shards:
        s.unlink()
    print(f"wrote {len(fens):,} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
