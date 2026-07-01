# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

In-progress work on the `development` branch toward the next release. **Playing
behaviour is unchanged so far** — search, evaluation, and move generation are
bit-identical — so the strength gain below comes entirely from searching *faster*
(deeper in the same time), not from evaluating differently.

### Performance
- **~3.3× faster search** (dev-box bench NPS ~23k → ~77k), from three
  behaviour-preserving changes:
  - incremental material + piece-square + phase evaluation accumulators
    (maintained in make/unmake instead of recomputed every node);
  - single-pass attack generation shared between mobility and king safety;
  - an optional **mypyc-compiled build** of the hot modules (~2× on its own).
- Measured **+184.6 ± 30.9 Elo** (SPRT, 8 s + 0.08 s, single-threaded) for the
  compiled build vs the pure-Python engine — purely from the extra depth.
- PyPy was evaluated and **rejected** (~0.91× — slower than CPython for this
  bitboard workload; its JIT cannot accelerate arbitrary-precision 64-bit-int
  operations).

### Changed (internal, behaviour-preserving)
- Search constants and evaluation weights refactored behind tunable parameter
  objects whose defaults reproduce the previous values exactly, preparing an
  evaluation-tuning campaign. The extra knobs are hidden unless the `HYDRA_TUNE`
  environment variable is set, so the released UCI option list is unchanged.

### Changed
- **`bench` harness** upgraded to a 40-position suite (matching the sibling
  engines Rarog and Basilisk for cross-engine comparison) so no single position
  dominates the node total (top-position share ~35% → 12.3%). New syntax
  `bench [depth] [repeats]` adds a best-of-N nodes/second reading and effective
  branching factor / median / top-share diagnostics, so the deterministic node
  total reads as a fingerprint rather than a speed or strength proxy.

### Added (development tooling; not part of the shipped engine)
- fastchess-based SPRT harness, a self-contained SPSA driver, an offline Texel
  tuner + evaluation coefficient-trace, and `tools/build_mypyc.ps1` for the
  compiled build.

## [1.4.1] — 2026-05-28

Ponder-completion release for GUI tournament use.

### Fixed
- Completed UCI ponder handling:
  - completed `go ponder` searches still wait for `stop` or `ponderhit` before emitting `bestmove`
  - ponder searches keep thinking after their normal time or node budget is reached
  - `ponderhit` immediately releases a ponder search whose normal budget was already satisfied
  - early `ponderhit` commands are applied when the search state is registered
  - legal ponder moves are emitted from the PV or transposition table when available
- Kept ponder output gated behind the `Ponder` UCI option

### Added
- Added protocol-level regression tests for `go ponder`, `stop`, `ponderhit`, early `ponderhit`, ponder time-limit deferral, legal ponder output, disabled ponder output, and transposition-table ponder fallback

### Validation
- `python -m pytest -q`: `106 passed`
- `python -m ruff check .`: passed
- Verified subprocess UCI ponder sequences against a reference engine:
  - `go ponder depth 1` does not emit `bestmove` before `stop` or `ponderhit`
  - `go ponder movetime 100` waits past the normal budget and returns promptly after `ponderhit`

## [1.4.0] — 2026-05-28

Baseline recovery release for renewed regression testing against Hydra 1.1.2. This
release supersedes the 1.3.x line for strength testing and release builds.

### Changed
- Restored the search, evaluation, transposition-table, and time-management behavior to the 1.1.2 baseline
- Removed `EvalType` from UCI; Hydra now exposes only the classical evaluator
- Kept Syzygy tablebase integration while returning search strength to the 1.1.2 baseline:
  - bundled Fathom probe code
  - `SyzygyPath`, `SyzygyProbeDepth`, `Syzygy50MoveRule`, and `SyzygyProbeLimit` UCI options
  - root DTZ probing, in-search WDL probing, and `tbhits` reporting
- Kept UCI and GUI safety fixes:
  - legal `bestmove` and ponder fallback
  - truncated PV output guarded to complete move tokens
  - malformed UCI move-token handling
  - legacy FEN fullmove `0` normalization

### Added
- Reintroduced configurable `Move Overhead` as a UCI spin option, defaulting to `10` ms
- Added release guardrail tests for version metadata consistency, the restored depth-6 search API baseline, move-overhead parsing/clamping/time budgeting, and Syzygy castling/depth probe guards

### Removed
- Removed the 1.3.2 short-control time-polling changes from the active release
- Removed the speculative strength changes from the active release:
  - quiescence TT probing/storage and static-eval TT reuse
  - untuned evaluation additions
  - check-preserving pruning/reduction probes
  - exact-only correction-history update changes

### Validation
- `python -m pytest -q`: `98 passed`
- `python -m ruff check hydra tests`: passed
- `bench 9`: `559253` nodes, matching the Hydra 1.1.2 search/evaluation node tree
- Baseline-only 300-game Cutechess match at `3+0.2` against Hydra 1.1.2 before reintroducing `Move Overhead`: `+129 =65 -106`, 53.83%, `+26.7 +/- 34.9` Elo, LOS 93.3%
- Non-time-forfeit games from that baseline-only match were effectively even: `+76 =64 -75`, 50.23%, `+1.6` Elo

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
- Added common Syzygy UCI options: `SyzygyPath`, `SyzygyProbeDepth`, `Syzygy50MoveRule`, and `SyzygyProbeLimit`
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

First stable release. Estimated strength: **~1900 Elo** at short time controls.

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

[1.4.1]: https://github.com/maelic13/hydra/releases/tag/v1.4.1
[1.4.0]: https://github.com/maelic13/hydra/releases/tag/v1.4.0
[1.3.2]: https://github.com/maelic13/hydra/releases/tag/v1.3.2
[1.3.1]: https://github.com/maelic13/hydra/releases/tag/v1.3.1
[1.1.2]: https://github.com/maelic13/hydra/releases/tag/v1.1.2
[1.1.1]: https://github.com/maelic13/hydra/releases/tag/v1.1.1
[1.1.0]: https://github.com/maelic13/hydra/releases/tag/v1.1.0
[1.0.0]: https://github.com/maelic13/hydra/releases/tag/v1.0.0
