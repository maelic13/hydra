# hydra

UCI-compatible chess engine written in pure Python — no C extensions, no numpy, no external dependencies.

**Estimated strength: ~1900 Elo** (Stockfish `UCI_Elo` calibration, 100 ms/move).

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
- Knight outposts, hanging pieces detection
- Pawn cache (4096 entries) for structure reuse

### Infrastructure
- **Bitboard representation** with magic bitboard sliding attacks
- **Full legal move generation** with check evasion and perft validation
- **Make / Unmake** with history stack — no board copying
- **Full UCI protocol** with threaded search (always-responsive input loop)
- **Pondering** support
- **Bench command** for node-count regression testing
- Zero external dependencies — pure Python 3.11+

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

## Requirements

- Python 3.11 or newer

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

| Option   | Type  | Default   | Min | Max        | Description                              |
|----------|-------|-----------|-----|------------|------------------------------------------|
| Hash     | spin  | 64        | 1   | 33554432   | Transposition table size in MB           |
| Threads  | spin  | 1         | 1   | 1          | Number of search threads                 |
| Ponder   | check | false     | —   | —          | Allow engine to think on opponent's time |
| EvalType | combo | classical | —   | —          | Evaluation backend (`classical`)         |

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

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
