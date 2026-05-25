from __future__ import annotations

import sys
from pathlib import Path

from setuptools import Extension, setup

ROOT = Path(__file__).parent
FATHOM_DIR = ROOT / "hydra" / "native" / "fathom"

extra_compile_args: list[str] = []
extra_link_args: list[str] = []
libraries: list[str] = []
tbprobe_source = FATHOM_DIR / "tbprobe.c"

if sys.platform != "win32":
    extra_compile_args.append("-std=gnu11")
    libraries.append("pthread")
else:
    tbprobe_source = FATHOM_DIR / "tbprobe_cpp.cpp"
    extra_compile_args.extend(["/std:c++17", "/D_CRT_SECURE_NO_WARNINGS"])

setup(
    ext_modules=[
        Extension(
            "hydra._fathom",
            sources=[
                str(FATHOM_DIR / "hydra_fathom.c"),
                str(tbprobe_source),
            ],
            include_dirs=[str(FATHOM_DIR)],
            define_macros=[("TB_NO_HELPER_API", "1")],
            extra_compile_args=extra_compile_args,
            extra_link_args=extra_link_args,
            libraries=libraries,
        )
    ]
)
