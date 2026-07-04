#!/usr/bin/env python3
"""Build the mypyc-compiled Hydra release executable (used by CI and locally).

Steps:
  1. Compile the hot modules with **mypyc**, in place (produces `hydra/<mod>.*.pyd`
     on Windows / `.so` on Linux+macOS, plus a shared `*__mypyc*` runtime lib at
     the repo root).
  2. Bundle `hydra/uci.py` with **PyInstaller**. The compiled extension modules
     take import precedence over their `.py` sources, so the bundled engine is the
     fast build. The mypyc shared runtime is imported at the C level and is
     therefore invisible to PyInstaller's analysis, so it is added explicitly with
     `--add-binary`.

The result is `dist/hydra` (`dist/hydra.exe` on Windows) — the ~2×-faster build.
Run `python setup.py build_ext --inplace` first if you want Syzygy/Fathom bundled.

    python tools/build_release.py

Requires the `[build]` extra (mypy + pyinstaller) and a C compiler.
"""

from __future__ import annotations

import os
import subprocess  # noqa: S404  (drives mypyc + PyInstaller; trusted local tools)
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Hot modules to compile (uci/bench/syzygy/__init__/__main__ stay pure Python —
# syzygy uses ctypes/Fathom; uci/bench are cold). Mirrors tools/build_mypyc.ps1.
_HOT = (
    "types", "bitboard", "moves", "zobrist", "attacks",
    "transposition", "board", "movegen", "evaluation", "engine",
)


def _run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=_REPO)  # noqa: S603


def main() -> int:
    py = sys.executable

    # 1. Compile the hot modules with mypyc, in place.
    _run([py, "-m", "mypyc", *[f"hydra/{m}.py" for m in _HOT]])

    # 2. Verify the extensions were actually produced (fail loudly if mypyc
    #    silently no-op'd — otherwise we would ship a pure-Python binary).
    hyd = _REPO / "hydra"
    compiled = list(hyd.glob("engine.*.pyd")) + list(hyd.glob("engine.*.so"))
    if not compiled:
        print("ERROR: mypyc produced no compiled extension for hydra.engine", file=sys.stderr)
        return 1
    runtimes = list(_REPO.glob("*__mypyc*.pyd")) + list(_REPO.glob("*__mypyc*.so"))
    if not runtimes:
        print("ERROR: mypyc shared runtime (*__mypyc*) not found", file=sys.stderr)
        return 1
    print(f"mypyc OK: {len(compiled)} module ext + runtime {Path(runtimes[0]).name}")

    # 3. PyInstaller, adding the mypyc runtime (C-level import → invisible to
    #    PyInstaller's static analysis, so add it by hand). cwd is the repo root,
    #    so the runtime is referenced by name.
    add_binary: list[str] = []
    for rt in runtimes:
        add_binary += ["--add-binary", f"{Path(rt).name}{os.pathsep}."]
    _run([
        py, "-m", "PyInstaller", "--clean", "--onefile", "--optimize=2",
        "--noupx", "--name", "hydra", "--paths", ".", *add_binary, "hydra/uci.py",
    ])

    exe = _REPO / "dist" / ("hydra.exe" if os.name == "nt" else "hydra")
    print(f"Built compiled release: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
