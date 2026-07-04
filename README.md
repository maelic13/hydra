# Hydra

<p align="center">
  <img src="logo/hydra_detailed.png" alt="Hydra logo" width="260">
</p>

UCI-compatible chess engine written in Python, with optional native Syzygy tablebase support through the bundled Fathom probe code.

---

## Features

### Search
- **Principal Variation Search** (PVS) with iterative deepening
- **Transposition table** with Zobrist hashing
- **Null Move Pruning** (NMP) with verification
- **Late Move Reductions** (LMR) tuned with continuation history
- **Futility Pruning** and **Reverse Futility Pruning**
- **Late Move Pruning** (LMP)
- **Singular Extensions** — double extension, multicut, negative extension
- **ProbCut** with quiescence pre-filter
- **SEE** (Static Exchange Evaluation) — capture ordering and pruning
- **Soft / hard time split** with best-move stability scaling

### Move Ordering
- TT move, MVV-LVA captures, killer moves, countermove heuristic
- Quiet history, capture history, continuation history (1-ply and 2-ply)
- Correction history (pawn and non-pawn)

### Evaluation (classical HCE)
- Material + piece-square tables, tapered middlegame / endgame interpolation
- Mobility for all piece types
- King safety with attack weighting
- Pawn structure — passed pawns, isolated, doubled, backward, phalanx
- Knight outposts
- Evaluation cache (65 536 entries) for repeated-position reuse
- Pawn cache (32 768 entries) for structure reuse

### Infrastructure
- **Bitboard representation** with magic bitboard sliding attacks
- **Full legal move generation** with check evasion and perft validation
- **Make / Unmake** with history stack — no board copying
- **Full UCI protocol** with threaded search (always-responsive input loop)
- **Correct ponder / infinite handling** — no early `bestmove` before `stop` or `ponderhit`
- **Pondering** support
- **Syzygy tablebase probing** through UCI-compatible options
- **Bench command** for node-count regression testing
- No runtime Python package dependencies

---

## Releases

- [Latest release](https://github.com/maelic13/hydra/releases/latest)
- [All releases](https://github.com/maelic13/hydra/releases)

Release assets include standalone executables for
Windows (x64, arm64), macOS (arm64), and Linux (x64, arm64).

### macOS permissions

To run on macOS, allow the executable with:

```bash
xattr -d com.apple.quarantine <path_to_executable>
chmod +x <path_to_executable>
```

---

## Requirements

- Python 3.11 or newer
- Use the same Python version when comparing release builds or strength-test results; Python runtime changes can affect nodes/second
- A C/C++ compiler when installing from source or building Syzygy support

### Source install toolchains

Installing from source builds the bundled Fathom tablebase extension. If you only want to run Hydra, download a standalone
executable from the [latest release](https://github.com/maelic13/hydra/releases/latest) instead.

| Platform | Required toolchain |
|----------|--------------------|
| Windows x64 | Visual Studio Build Tools or Visual Studio with **Desktop development with C++**, **MSVC Build Tools for x64/x86 (Latest)**, and a Windows 10/11 SDK |
| Windows ARM64 | Visual Studio Build Tools or Visual Studio with **Desktop development with C++**, **MSVC Build Tools for ARM64/ARM64EC (Latest)**, **MSVC Build Tools for x64/x86 (Latest)**, and a Windows 10/11 SDK. The x64/x86 tools are recommended because some Python packaging tools still use host utilities from that toolchain. |
| macOS ARM64 | Apple command line developer tools: `xcode-select --install` |
| Linux x64 | GCC or Clang plus Python development headers. On Debian/Ubuntu: `sudo apt install build-essential python3-dev`; Fedora: `sudo dnf install gcc gcc-c++ python3-devel`; Arch: `sudo pacman -S base-devel python` |
| Linux ARM64 | GCC or Clang plus Python development headers. On Debian/Ubuntu: `sudo apt install build-essential python3-dev`; Fedora: `sudo dnf install gcc gcc-c++ python3-devel`; Arch: `sudo pacman -S base-devel python` |

Windows users can install Build Tools from
[visualstudio.microsoft.com/visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/). Open a
new PowerShell window after installing the toolchain, then reactivate the virtual environment before rerunning `pip install`.

---

## Install and Run

After the required platform toolchain is installed, install Hydra from a virtual environment:

```bash
# Install (use a virtual environment)
pip install .

# Start the UCI engine
hydra
```

Or run directly without installing:

```bash
python -m hydra.uci
```

---

## UCI Options

| Option   | Type  | Default   | Min | Max      | Description                              |
|----------|-------|-----------|-----|----------|------------------------------------------|
| Hash     | spin  | 64        | 1   | 33554432 | Transposition table size in MB           |
| Threads  | spin  | 1         | 1   | 1        | Number of search threads (single-threaded search) |
| Ponder   | check | false     | —   | —        | Allow engine to think on opponent's time |
| Move Overhead | spin | 10 | 0 | 5000 | Time buffer in milliseconds kept for GUI/process overhead |
| SyzygyPath | string | `<empty>` | — | — | Syzygy tablebase directory |
| SyzygyProbeDepth | spin | 1 | 1 | 100 | Minimum search depth for in-search WDL probes |
| Syzygy50MoveRule | check | true | — | — | Respect the 50-move rule in tablebase root probes |
| SyzygyProbeLimit | spin | 7 | 0 | 7 | Maximum piece count for tablebase probing |

---

## Bench

The `bench` command searches 40 representative positions (the suite shared with
the sibling engines Rarog and Basilisk) to a fixed depth and prints a node-count
summary. Run single-threaded, the total node count is a deterministic
fingerprint — any change to search, eval, or move generation produces a
different value. Effective-branching-factor, median, and top-position-share
diagnostics are printed so the total reads as a fingerprint, not a speed or
strength proxy.

```
bench [depth] [repeats]   (defaults: depth 9, repeats 1)
```

`repeats > 1` re-runs the whole suite for a best-of-N nodes/second reading; the
fingerprint and diagnostics come from run 1.

Example output:

```
bench 1/40  depth 9  score 22  nodes 13204  ebf 3.10  time 340ms  nps 38835
...
=========================
Nodes searched  : 1101946
Geomean EBF     : 3.256
Median nodes    : 17406
Top-pos share   : 12.3%  (122928 nodes)
Total time (ms) : 25993
Nodes/second    : 38573
```

---

## Development

Development installs use the same compiler requirement as normal source installs. On Windows, if editable install fails
with `Microsoft Visual C++ 14.0 or greater is required`, install the C++ Build Tools listed in Requirements, open a new
shell, reactivate the virtual environment, and rerun the install command.

```bash
# Install with dev dependencies
pip install -e ".[build,dev]"

# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```

Current regression coverage includes unit tests for move generation, search, UCI protocol behavior, ponder handling, Syzygy probing, malformed GUI input, FEN compatibility, release build configuration, version metadata consistency, and release baseline guardrails.

```bash
pytest -q
ruff check hydra tests
```

The current **1.5.0** release is the largest strength jump in the project's
history — Hydra both searches ~3× faster (the mypyc-compiled build) and evaluates
far better (a data-tuned evaluation). Cumulative gain over 1.4.1 is **≈ +250 Elo**,
SPRT-confirmed at 8 s + 0.08 s single-threaded: **+184.6 ± 30.9** for the compiled
build vs pure Python, **+57.0 ± 17.9** for the tuned evaluation, and **+19.6 ± 9.3**
for a king-safety refinement on top. This is the first release whose evaluation
weights are data-tuned (Texel-style fit against ~2 M Stockfish-labelled positions)
rather than textbook constants. Hydra 1.5.0 passes `114` tests, passes Ruff, and
`bench 9` searches `1101946` nodes (the current deterministic fingerprint). The
released executables are the compiled build.

---

## Build a standalone executable

Most users should just download a release binary. If you want to build one
yourself, **a single command** produces the same executable the GitHub releases
ship — a **native, single-file, [mypyc](https://mypyc.readthedocs.io/)-compiled**
binary that searches ~2× faster than pure Python (worth ~+185 Elo) with identical
playing behaviour:

```bash
# From a clean virtual environment — Python 3.12 recommended for release builds:
pip install -e ".[build]"
python tools/build_release.py
```

The binary is written to **`dist/hydra`** (`dist/hydra.exe` on Windows). It is a
normal native executable — point any UCI GUI (Cutechess, Arena, BanksiaGUI, …)
straight at it. `build_release.py` runs three steps for you:

1. build the native **Fathom** extension (for **Syzygy tablebase** support);
2. compile the hot modules with **mypyc** (the speed win);
3. bundle everything into one file with **PyInstaller**.

A C/C++ compiler is required (see the toolchain table under
[Requirements](#source-install-toolchains)) — it is what makes the fast build.
Without one, download a pre-built binary from the
[latest release](https://github.com/maelic13/hydra/releases/latest) or run from
source (pure Python, slower).

### Verify the build

```bash
# (Windows: .\dist\hydra.exe)
./dist/hydra
uci
setoption name SyzygyPath value /path/to/syzygy
isready
position fen 8/8/8/8/4k3/8/8/5QK1 w - - 0 1
go depth 1
quit
```

The engine should advertise the `Syzygy*` UCI options and, for the sample
tablebase position, print an `info` line containing `tbhits` (confirming the
bundled Fathom extension works). `bench 9` should report `1101946` nodes.

> **Developer build (not a standalone exe).** For SPRT / benchmarking during
> development, `tools/build_mypyc.ps1` (Windows) compiles the hot modules into
> `tools/engines/compiled/`, run via `.\tools\run_hydra.cmd tools\engines\compiled`.
> That needs a Python interpreter and is only for the dev loop — end users and
> GUIs want `tools/build_release.py` above.

---

## Project Structure

```
hydra/
├── __init__.py       # Package metadata and version
├── types.py          # Constants: squares, pieces, castling, directions
├── bitboard.py       # Bit manipulation utilities, file/rank masks
├── attacks.py        # Magic bitboard sliding attacks, leaper tables
├── zobrist.py        # Deterministic Zobrist hash keys
├── moves.py          # 16-bit integer move encoding
├── board.py          # Board state: bitboards + mailbox + Zobrist
├── movegen.py        # Legal move generation, check evasion, perft
├── transposition.py  # Transposition table
├── evaluation.py     # Classical hand-crafted evaluation (HCE)
├── engine.py         # Iterative-deepening PVS search with all heuristics
├── syzygy.py         # Syzygy/Fathom tablebase adapter
├── bench.py          # Benchmark: fixed-depth search over 16 positions
├── uci.py            # UCI protocol with threaded search
└── native/fathom/    # Vendored Fathom tablebase probe code
```

---

## Architecture

### Board Representation

- **LERF square mapping**: a1 = 0, b1 = 1, …, h8 = 63
- **12 bitboards** (one per piece type per colour) plus colour occupancy and total occupancy
- **Mailbox array** (64 entries) for O(1) piece-on-square lookup
- **Piece types**: Pawn = 0, Knight = 1, Bishop = 2, Rook = 3, Queen = 4, King = 5

### Move Encoding

16-bit integer: `from_sq:6 | to_sq:6 | promotion:2 | flag:2`

Flags: 0 = normal, 1 = promotion, 2 = en passant, 3 = castling

### Performance Optimizations

- Inlined make/unmake helpers (no function call overhead)
- Lightweight legality check without full make/unmake (occupancy simulation)
- Bulk counting at perft leaf nodes
- Check evasion generator (precomputed between-squares table)
- Inlined magic bitboard lookups with local aliases
- Dedicated capture-only generation for quiescence search
- Cached king squares updated incrementally

---

## Acknowledgements

Thank you to the Stockfish project and team for their long-standing work on chess engine design, UCI behavior, testing culture, and open-source engine development.

---

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). The bundled Fathom probe code is MIT licensed; see [hydra/native/fathom/LICENSE](hydra/native/fathom/LICENSE).
