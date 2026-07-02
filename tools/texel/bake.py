#!/usr/bin/env python3
"""Bake an SPRT-passed Texel weight file into the engine source (Phase 4).

Rewrites the auto-generated `_TUNED_WEIGHTS` tuple in `hydra/evaluation.py` with
the CUMULATIVE tuned weight set: the weights already baked there, merged with the
new file (new file wins per key). So each accepted bundle stacks on the last, and
the structural default constants stay untouched (readable scaffold); the tuned
values live in one clearly-labelled, generated block that every EvalParams
instance overlays.

    python tools/texel/bake.py --weights tools/texel/data/eval_linear.txt

Run the fingerprint gate afterwards (bench + trace) — a bake legitimately MOVES
the bench/eval fingerprints (it is a real eval change); record the new anchors.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

_EVAL = Path(__file__).resolve().parent.parent.parent / "hydra" / "tuned_eval.py"
_HEADER = "TUNED_WEIGHTS: tuple[tuple[str, tuple[int, ...], object], ...] = "
_HEADER_RE = re.escape(_HEADER)

# Attributes whose values are floats/bools rather than ints (none tuned yet, but
# keep the door open for the scale/winnable bundle).
_BOOL_ATTRS = {"scale_active", "winnable_active"}


def _parse_weight_file(path: Path) -> dict[tuple, object]:
    out: dict[tuple, object] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        fields = raw.split("#", 1)[0].split()
        if not fields:
            continue
        attr = fields[0]
        idxs = tuple(int(x) for x in fields[1:-1])
        token = fields[-1]
        if attr in _BOOL_ATTRS:
            value: object = bool(int(token))
        elif "." in token:
            value = float(token)
        else:
            value = int(token)
        out[attr, *idxs] = value
    return out


def _read_existing(src: str) -> dict[tuple, object]:
    """Parse the current `_TUNED_WEIGHTS = (...)` literal, if non-empty."""
    m = re.search(_HEADER_RE + r"(\(.*?\))\s*\n", src, re.DOTALL)
    if not m:
        return {}
    literal = ast.literal_eval(m.group(1))  # tuple of (attr, (idxs...), value)
    return {(attr, *idxs): value for attr, idxs, value in literal}


def _format_block(weights: dict[tuple, object]) -> str:
    ordered = sorted(weights, key=lambda k: (str(k[0]), k[1:]))
    entries = [f'    ("{key[0]}", {key[1:]!r}, {weights[key]!r}),' for key in ordered]
    return _HEADER + "(\n" + "\n".join(entries) + "\n)\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, help="SPRT-passed weight file (attr idx.. value)")
    args = ap.parse_args()

    src = _EVAL.read_text(encoding="utf-8")
    merged = _read_existing(src)
    before = len(merged)
    merged.update(_parse_weight_file(Path(args.weights)))

    block = _format_block(merged)
    new_src, n = re.subn(_HEADER_RE + r"\(.*?\)\s*\n", block, src, count=1, flags=re.DOTALL)
    if n != 1:
        msg = f"could not locate the {_HEADER!r} block in {_EVAL}"
        raise SystemExit(msg)
    _EVAL.write_text(new_src, encoding="utf-8", newline="\n")
    print(f"baked {len(merged)} tuned weights into {_EVAL} "
          f"({before} pre-existing, {len(merged) - before} new keys)")
    print("Now verify: bench + trace fingerprint (they will MOVE — record the new anchors).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
