# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-20

First stable release. Estimated strength: **~1900 Elo** (Stockfish `UCI_Elo` calibration, 100 ms/move).

### Added

#### Search
- Principal Variation Search (PVS) with iterative deepening
- Transposition table with Zobrist hashing and configurable size
- Null Move Pruning (NMP) with verification search
- Late Move Reductions (LMR) tuned with continuation history
- Futility Pruning and Reverse Futility Pruning
- Late Move Pruning (LMP)
- Singular Extensions — double extension, multicut, negative extension
- ProbCut with quiescence search pre-filter
- Static Exchange Evaluation (SEE) — capture ordering and pruning
- LMR reduction for bad captures (negative SEE)
- Soft / hard time split with best-move stability scaling
- Check extensions, improving flag
- History tables with aging across iterations: quiet history, capture history,
  continuation history (1-ply and 2-ply), correction history (pawn and non-pawn)
- Countermove heuristic
- Killer moves

#### Evaluation
- Material and piece-square tables with tapered middlegame / endgame interpolation
- Mobility for all piece types
- King safety with attack weighting
- Pawn structure: passed pawns, isolated, doubled, backward, phalanx
- Knight outposts
- Hanging pieces detection
- Pawn cache (4096 entries) for structure reuse

#### Infrastructure
- Bitboard board representation with magic bitboard sliding attacks
- Full legal move generation with check evasion, validated by perft
- Make / unmake with history stack — no board copying
- Full UCI protocol with threaded search (always-responsive input loop)
- Pondering support
- `bench` command — fixed-depth search over 16 positions, node count as regression fingerprint
- Standalone executables for Windows (x64, arm64), macOS (arm64), Linux (x64, arm64)
- Zero external dependencies — pure Python 3.11+

[1.0.0]: https://github.com/maelic13/hydra/releases/tag/v1.0.0
