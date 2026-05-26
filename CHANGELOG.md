# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.2] — 2026-05-26

Fast time-control reliability release.

### Added
- Added configurable `Move Overhead` UCI option, defaulting to `20` ms
- Added regression coverage for move-overhead parsing, time-limit calculation, and short time-control clock-check intervals

### Changed
- Search now checks wall-clock time more frequently at short time controls:
  - every 64 nodes at 200 ms or less
  - every 128 nodes at 1 second or less
  - every 512 nodes at 5 seconds or less

### Fixed
- Reduced late-move and timeout risk at fast controls by reserving GUI/process overhead instead of searching almost to the full requested `movetime`
- Verified saved LittleBlitzer illegal-move reports replay with legal bestmoves from the rebuilt engine
- Verified direct concurrent UCI `go movetime 100` stress returns bestmoves without timeouts or malformed output
- Verified fixed-depth regressions against Hydra 1.1.2 are even at depth 5 (`+5 =10 -5`) and depth 4 (`+17 =6 -17`)

## [1.3.1] — 2026-05-26

Regression repair release based on the 1.1.2 search/evaluation baseline, with focused Syzygy support re-added.

### Added
- Added Syzygy tablebase support via the bundled Fathom probe code
- Added UCI options matching common Stockfish defaults: `SyzygyPath`, `SyzygyProbeDepth`, `Syzygy50MoveRule`, and `SyzygyProbeLimit`
- Added root DTZ probing, in-search WDL probing, and `tbhits` reporting
- Added regression tests for tablebase probing, root promotion moves, UCI option forwarding, illegal bestmove/ponder fallback, malformed UCI tokens, LittleBlitzer-style FEN handling, and release build configuration

### Changed
- Switched release executable builds to Python 3.12 after local PyInstaller benchmarking showed it was fastest among Python 3.11, 3.12, 3.13, and 3.14
- Updated the GitHub release workflow to build the native Fathom extension before PyInstaller and smoke-test Syzygy extension initialization

### Fixed
- Restored the 1.1.2 playing-strength baseline by dropping the later search/evaluation changes that caused the regression
- Prevented truncated LittleBlitzer PV output from ending on partial move tokens
- Accepted legacy FENs with fullmove number `0` by normalizing them to `1`
- Guarded UCI `bestmove` and ponder output so only legal moves are emitted
- Packaged Fathom source and license files so source builds and PyInstaller releases include the native tablebase probe code

## [1.1.2] — 2026-05-23

UCI ponder/infinite-search correctness release.

### Fixed
- Prevented completed `go ponder` searches from emitting `bestmove` before the GUI sends `stop` or `ponderhit`
- Prevented completed `go infinite` searches from emitting `bestmove` before `stop`
- Delayed fallback `bestmove 0000` after search errors during ponder/infinite searches until the GUI allows a best move
- Kept `isready` responsive while a completed ponder/infinite search is waiting to report its result
- Added regression coverage from the tournament illegal-move final position

## [1.1.1] — 2026-05-22

Mate-search correctness release.

### Fixed
- Iterative deepening no longer stops at the first forced mate unless it is already mate-in-1
- Mate-like previous scores now disable aspiration windows, allowing deeper searches to improve mate length instead of staying trapped around an earlier mate score
- Added regression coverage for continuing iterative deepening after a forced mate score

### Changed
- Bumped package and engine version metadata to `1.1.1`
- Kept `Threads` documented as single-threaded (`min 1`, `max 1`) to match the current supported engine behavior

## [1.1.0] — 2026-05-20

Performance release. Estimated strength: **~2000 Elo** (based on +120 Elo measured against Beast at 100 ms/move).

### Changed
- Evaluation cache added to `ClassicalEvaluator` (up to 65 536 entries) — avoids recomputing static eval for repeated positions during search
- Pawn structure cache enlarged from 4 096 → 32 768 entries
- Removed hanging-pieces detection from static eval; SEE in search handles tactical compensation more accurately and at lower cost
- Conditional SEE skip: captures where the victim is worth more than the attacker are ordered directly via MVV-LVA, saving an SEE call per move
- History-malus loop micro-optimised: destination square hoisted out of inner loop; set-literal allocations eliminated
- LSB extraction in move generation rewritten from De Bruijn multiplication + table lookup to `(bb & -bb).bit_length() - 1`, leveraging CPython's native integer representation (~21 % faster per extraction)

### Net result
- **+121 % NPS** (≈ 17 k → ≈ 37 k nodes/second)
- **+120 Elo** confirmed over 81 games at 100 ms/move (SPRT H1, LOS 100 %)

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
- Pawn cache (4 096 entries) for structure reuse

#### Infrastructure
- Bitboard board representation with magic bitboard sliding attacks
- Full legal move generation with check evasion, validated by perft
- Make / unmake with history stack — no board copying
- Full UCI protocol with threaded search (always-responsive input loop)
- Pondering support
- `bench` command — fixed-depth search over 16 positions, node count as regression fingerprint
- Standalone executables for Windows (x64, arm64), macOS (arm64), Linux (x64, arm64)
- Zero external dependencies — pure Python 3.11+

[1.3.2]: https://github.com/maelic13/hydra/releases/tag/v1.3.2
[1.3.1]: https://github.com/maelic13/hydra/releases/tag/v1.3.1
[1.1.2]: https://github.com/maelic13/hydra/releases/tag/v1.1.2
[1.1.1]: https://github.com/maelic13/hydra/releases/tag/v1.1.1
[1.1.0]: https://github.com/maelic13/hydra/releases/tag/v1.1.0
[1.0.0]: https://github.com/maelic13/hydra/releases/tag/v1.0.0
