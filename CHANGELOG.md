# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] — 2026-05-25

NPS recovery release after the 1.2.0 Syzygy and 1.1.3 tactical-search work.

### Added
- Added regression coverage proving the targeted quiet-check generator matches the previous full legal-move scan for direct checks, discovered checks, pawn pushes, castling, and tactical middlegame positions

### Changed
- Replaced qsearch's brute-force quiet-check scan with targeted direct/discovered/castling check generation, preserving the searched checking moves while avoiding repeated full legal move generation
- Reused evaluation attack bitboards for both mobility and king-safety attack counting, removing duplicate magic-bitboard lookups without changing static evaluation scores
- Increased the full evaluation cache from 65 536 to 262 144 entries to reduce cache churn in deeper searches
- Bumped package and engine version metadata to `1.2.1`

### Fixed
- Recovered a large part of the NPS regression introduced after 1.1.2 while keeping the `bench 9` node fingerprint unchanged at 588 991 nodes

## [1.2.0] — 2026-05-25

Syzygy tablebase support release.

### Added
- Vendored the Fathom C Syzygy probing source and added a native CPython wrapper
- Added `SyzygyPath`, `SyzygyProbeDepth`, and `SyzygyProbeLimit` UCI options
- Added exact root DTZ probing so tablebase positions can immediately choose a WDL-preserving move
- Added conservative in-search WDL probing for exact tablebase cutoffs after irreversible moves
- Added regression coverage for root tablebase short-circuiting and in-search WDL probing

### Changed
- Switched packaging from Hatchling to Setuptools so the vendored native extension is built from source
- Updated documentation for Syzygy configuration, native build requirements, and vendored Fathom licensing
- Bumped package and engine version metadata to `1.2.0`

### Fixed
- Fixed isolated wheel builds by using setup-relative native-extension source paths

## [1.1.3] — 2026-05-25

Playing-strength release based on tournament-result analysis.

### Added
- Added shallow quiet-check search to quiescence so forcing checking moves are not dropped at tactical leaves
- Added regression coverage for quiet-check quiescence and quiescence transposition-table storage

### Changed
- Strengthened king-safety evaluation with coordinated-attacker bonuses, queen-aware attack scaling, castled-king pawn shelter, and enemy pawn-storm penalties
- Quiescence search now probes/stores the transposition table and uses the same correction-history-adjusted static evaluation as the main search
- Removed the `EvalType` UCI option and evaluator registry; Hydra now always uses the classical evaluator
- Bumped package and engine version metadata to `1.1.3`

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

[1.2.1]: https://github.com/maelic13/hydra/releases/tag/v1.2.1
[1.2.0]: https://github.com/maelic13/hydra/releases/tag/v1.2.0
[1.1.3]: https://github.com/maelic13/hydra/releases/tag/v1.1.3
[1.1.2]: https://github.com/maelic13/hydra/releases/tag/v1.1.2
[1.1.1]: https://github.com/maelic13/hydra/releases/tag/v1.1.1
[1.1.0]: https://github.com/maelic13/hydra/releases/tag/v1.1.0
[1.0.0]: https://github.com/maelic13/hydra/releases/tag/v1.0.0
