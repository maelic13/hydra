#!/usr/bin/env python3
"""Build the fast, standalone Hydra executable — the one the GUIs and releases use.

This is THE way to produce a Hydra executable. It builds a **native, single-file,
mypyc-compiled** binary (`dist/hydra` / `dist/hydra.exe`) — about 2× the node rate
of pure Python, which is worth ~+185 Elo. Steps:

  0. Build the native **Fathom** (Syzygy tablebase) C extension in place, so it can
     be bundled. Optional: if the C toolchain can't build it the executable still
     works, just without tablebase support.
  1. Compile the hot modules with **mypyc**, in place (`hydra/<mod>.*.pyd` on
     Windows / `.so` on Linux+macOS, plus a shared `*__mypyc*` runtime lib).
  2. Bundle `hydra/uci.py` with **PyInstaller**. The compiled extension modules
     take import precedence over their `.py` sources, so the bundled engine is the
     compiled build. The mypyc runtime is imported at the C level (invisible to
     PyInstaller's analysis), so it is added explicitly with `--add-binary`.

    python tools/build_release.py

Requires the `[build]` extra (mypy + pyinstaller + setuptools) and a C compiler
(MSVC on Windows, gcc/clang on Linux/macOS — the same compiler a source install
already needs). The working tree is left with the compiled `.pyd`/`.so` in place;
`git clean -fdx` (or deleting `hydra/*.pyd hydra/*.so *__mypyc*`) restores it.
"""

from __future__ import annotations

import os
import subprocess  # noqa: S404  (drives setuptools + mypyc + PyInstaller; trusted)
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Hot modules to compile (uci/bench/syzygy/__init__/__main__ stay pure Python —
# syzygy uses ctypes/Fathom; uci/bench are cold). Mirrors tools/build_mypyc.ps1.
_HOT = (
    "types", "bitboard", "moves", "zobrist", "attacks",
    "transposition", "board", "movegen", "evaluation", "engine",
)


def _run(cmd: list[str], *, check: bool = True) -> int:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, cwd=_REPO).returncode  # noqa: S603


def main() -> int:
    py = sys.executable

    # 0. Native Fathom (Syzygy) extension — best-effort so `pip install .` users
    #    still get a working (TB-less) exe if the extension can't build.
    print("== [0/3] native Fathom (Syzygy) extension ==", flush=True)
    if _run([py, "setup.py", "build_ext", "--inplace"], check=False) != 0:
        print("WARNING: Fathom build failed -> executable will lack Syzygy support",
              file=sys.stderr)

    # 1. Compile the hot modules with mypyc, in place.
    print("== [1/3] mypyc-compile hot modules ==", flush=True)
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
    print(f"mypyc OK: {len(compiled)} module ext + runtime {runtimes[0].name}")

    # 3. PyInstaller, adding the mypyc runtime (C-level import → invisible to
    #    PyInstaller's static analysis, so add it by hand). cwd is the repo root,
    #    so the runtime is referenced by name; --paths . makes the compiled
    #    checkout package win over any installed copy.
    print("== [2/3] PyInstaller bundle ==", flush=True)
    add_binary: list[str] = []
    for rt in runtimes:
        add_binary += ["--add-binary", f"{rt.name}{os.pathsep}."]
    _run([
        py, "-m", "PyInstaller", "--clean", "--onefile", "--optimize=2",
        "--noupx", "--name", "hydra", "--paths", ".", *add_binary, "hydra/uci.py",
    ])

    exe = _REPO / "dist" / ("hydra.exe" if os.name == "nt" else "hydra")
    print(f"== [3/3] done: {exe} ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
