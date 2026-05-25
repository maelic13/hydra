# hydra

UCI-compatible chess engine written in Python with an optional vendored Fathom C extension for Syzygy tablebase probing.

**Estimated strength: ~2000 Elo** (Stockfish `UCI_Elo` calibration, 100 ms/move).

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
- **TT-backed quiescence search** with corrected static evaluation and shallow quiet checks
- **Syzygy tablebase probing** through vendored Fathom for exact root DTZ and in-search WDL cutoffs
- **SEE** (Static Exchange Evaluation) — capture ordering and pruning
- **Soft / hard time split** with best-move stability scaling

### Move Ordering
- TT move, MVV-LVA captures, killer moves, countermove heuristic
- Quiet history, capture history, continuation history (1-ply and 2-ply)
- Correction history (pawn and non-pawn)

### Evaluation (classical HCE)
- Material + piece-square tables, tapered middlegame / endgame interpolation
- Mobility for all piece types
- King safety with coordinated attack weighting, pawn shelter, and pawn storms
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
- **Optional Syzygy support** using a vendored Fathom native extension
- **Bench command** for node-count regression testing
- No runtime Python package dependencies

## Releases

- [Current release: v1.2.0](https://github.com/maelic13/hydra/releases/tag/v1.2.0)
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

## Requirements

- Python 3.11 or newer
- A C compiler when installing from source with Syzygy support enabled by the native extension

## Install and Run

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

## UCI Options

| Option             | Type   | Default   | Min | Max      | Description                              |
|--------------------|--------|-----------|-----|----------|------------------------------------------|
| Hash               | spin   | 64        | 1   | 33554432 | Transposition table size in MB           |
| Threads            | spin   | 1         | 1   | 1        | Number of search threads (single-threaded search) |
| Ponder             | check  | false     | —   | —        | Allow engine to think on opponent's time |
| SyzygyPath         | string | `<empty>` | —   | —        | Syzygy tablebase directory or path list  |
| SyzygyProbeDepth   | spin   | 1         | 0   | 100      | Minimum search depth for in-search WDL probes |
| SyzygyProbeLimit   | spin   | 7         | 0   | 7        | Maximum piece count to probe (`0` disables probing) |

`SyzygyPath` accepts the platform path separator used by Fathom (`;` on Windows, `:` on Unix-like systems) when multiple tablebase directories are needed. Hydra probes root DTZ tables for exact tablebase moves and uses WDL probes inside search only when Fathom can answer exactly under the 50-move rule.

## Bench

The `bench` command searches 16 representative positions to a fixed depth and prints a node-count summary. The total node count acts as a fingerprint — any change to search, eval, or move generation produces a different value.

```
bench [depth]   (default: 9)
```

Example output:

```
bench 1/16  depth 9  score 14  nodes 16097  time 649ms  nps 24768
...
=========================
Total time (ms) : 21619
Nodes searched  : 561044
Nodes/second    : 25951
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```

## Build a Local Executable

```bash
# Install build dependencies
pip install ".[build]"

# Build with PyInstaller
pyinstaller --clean --onefile --optimize=2 --noupx --name hydra hydra/uci.py
```

The executable will be created in the `dist/` folder.

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
├── syzygy.py         # Python adapter for vendored Fathom Syzygy probing
├── native/fathom/    # Vendored Fathom C source and CPython wrapper
├── engine.py         # Iterative-deepening PVS search with all heuristics
├── bench.py          # Benchmark: fixed-depth search over 16 positions
└── uci.py            # UCI protocol with threaded search
```

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
- Native Syzygy probes are skipped entirely unless `SyzygyPath` loads tablebases

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). Vendored Fathom code is MIT licensed; see [hydra/native/fathom/LICENSE](hydra/native/fathom/LICENSE).
