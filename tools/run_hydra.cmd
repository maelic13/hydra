@echo off
rem ---------------------------------------------------------------------------
rem Hydra UCI launch shim for fastchess / external GUIs.
rem
rem   run_hydra.cmd [ENGINE_ROOT] [EVAL_FILE]
rem
rem ENGINE_ROOT is a directory that contains the `hydra` package to run. It lets
rem an SPRT pit one source tree (candidate) against another (a frozen baseline
rem snapshot) without either shadowing the other.
rem
rem EVAL_FILE (optional, Phase 4 Texel) is a weight-override file; when given it
rem is exported as HYDRA_EVAL_FILE so the engine loads a candidate weight set.
rem This lets an SPRT pit ONE compiled build against itself (baseline omits it).
rem
rem Isolation: we launch with `python -S`. The repo is editable-installed
rem (a .pth meta-path finder that always resolves `hydra` to the repo root),
rem which would otherwise shadow any snapshot. `-S` skips site/.pth processing,
rem so the `hydra` package found on `cwd` (ENGINE_ROOT) wins. Safe because Hydra
rem has no runtime package dependencies (stdlib + bundled Fathom via ctypes).
rem
rem Interpreter is centralized here so Phase 2.6 (mypyc/PyPy build) only edits
rem this file: set HYDRA_PYTHON to point at an alternative interpreter.
rem ---------------------------------------------------------------------------
setlocal
set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
if not "%~2"=="" set "HYDRA_EVAL_FILE=%~2"
if "%HYDRA_PYTHON%"=="" set "HYDRA_PYTHON=%~dp0..\.venv\Scripts\python.exe"
rem Advertise the tunable search options (Phase 1.1) in dev/SPSA runs; the
rem packaged release exe never sets this, so its UCI option list stays clean.
set "HYDRA_TUNE=1"
cd /d "%ROOT%"
"%HYDRA_PYTHON%" -S -m hydra
