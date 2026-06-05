# Hydra Python Category Single-File Plan

Goal: make `hydra_lite/hydra_full.py` the strongest reliable Python-category ChessAgents submission. This category has no 50KB cap, so prioritize full Hydra strength, correctness, reproducible generation, and time safety.

## Current State

| Item | Status |
|---|---|
| Plan file | `hydra_lite/PLAN_full.md` |
| Engine | `hydra_lite/hydra_full.py` |
| Size | ~172.9KB |
| Category | Python Only |
| Protocol | ChessAgents-compatible, not UCI |
| Source basis | Full Hydra modules inlined into one file |
| Search | Full Hydra PVS/ID/TT/null move/LMR/futility/ProbCut/singular/etc. |
| Eval | Full Hydra classical evaluator |
| Syzygy | Disabled for submission; no external files/native extension |
| Adapter params | `movetime=2200ms`, `move_overhead=100ms`, `Hash=12MB` |
| Main gap | No reproducible generator, no Fastchess/weather-factory validation loop yet |

Unless a command says otherwise, run it from the repository root: `D:\code\hydra`.

## Always Keep This Plan Updated

After every implementation step or reported experiment result, the agent must update this file before ending the turn.

| Trigger | Required Plan Update |
|---|---|
| Agent implements a task | Mark the task done or in-progress, add generated files/commands. |
| User reports SPRT/SPSA/validation result | Record result and keep/revert/continue decision. |
| A change is rejected | Mark rejected and add reason. |
| Baseline changes | Record old/new baseline filenames and date. |
| Tooling changes | Record exact tool path and clone/source URL. |
| Adapter constants change | Record timing data and new values. |

## Collaboration Workflow

| Role | Action |
|---|---|
| You | Say: `Implement next step` or name a specific unchecked task. |
| Agent | Implements the next unchecked task, explains it briefly, and updates this plan. |
| Agent | Gives the exact command for you to run locally. |
| You | Run the command and report score, games, crashes, timeouts, and SPRT/SPSA verdict. |
| Agent | Interprets the result, updates this plan, and keeps/reverts/refines the change. |

## Tooling Policy

Use Fastchess for matches/SPRT and weather-factory for SPSA tuning. Both must be downloaded into a temporary local directory under this repo and never committed.

| Tool | Purpose | Local Location | Git Policy |
|---|---|---|---|
| Fastchess | SPRT, fixed-game matches, gauntlets | `tmp/engine-tools/fastchess/` | Do not commit |
| weather-factory | SPSA parameter tuning | `tmp/engine-tools/weather-factory/` | Do not commit |
| UCI wrapper | Lets Fastchess run ChessAgents stdin/stdout scripts | `tools/chessagents_uci_wrapper.py` | Commit OK |

Notes:
- Fastchess canonical repo: `https://github.com/Disservin/fastchess.git`.
- weather-factory is commonly referenced as `weather-factory`/`weather factory by jnlt` in engine release notes. First tooling task must resolve and pin the exact repository URL before cloning. If it cannot be found publicly, stop and ask for the URL rather than inventing one.
- Add `tmp/` to `.git/info/exclude` or `.gitignore` before cloning tools.

## Result Format To Report

For SPRT:

```text
games=...
score=+W -L =D
elo=...
sprt=accepted|rejected|continue
timeouts=...
crashes=...
notes=...
```

For SPSA:

```text
iterations=...
games_per_iteration=...
best_params=...
elo_vs_baseline=...
sprt_confirmed=yes|no
timeouts=...
crashes=...
notes=...
```

## Phase Checklist

### Phase 0: Freeze Baseline

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Copy current full single-file engine to baseline. | `hydra_lite/hydra_full_baseline.py` | `python -m py_compile hydra_lite\hydra_full_baseline.py` |
| [ ] | Record baseline size, timings, and sample outputs. | Notes appended here. | Agent-provided smoke command |

Gate: baseline exists before strength work.

### Phase 1: Reproducible Build Pipeline

The current full single file was generated from Hydra modules. Make that generation repeatable before making deeper changes.

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Add `tools/build_chessagents_full.py`. | Regenerates `hydra_lite/hydra_full.py` from `hydra/`. | `python tools/build_chessagents_full.py` |
| [ ] | Make generator strip unused UCI/bench/native-Syzygy code safely. | Smaller/faster generated file. | Compile and smoke test |
| [ ] | Add generated-file header with source version/date. | Traceable artifact. | Inspect first lines |
| [ ] | Confirm generated output is deterministic. | Re-run produces no diff. | `git diff -- hydra_lite/hydra_full.py` |

Gate: never hand-edit `hydra_lite/hydra_full.py` except emergency fixes; edit source/generator and regenerate.

### Phase 2: Install Local Tooling

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Exclude local temp tool dir from git. | `tmp/` ignored locally. | `git status --short` |
| [ ] | Clone/build Fastchess locally. | `tmp/engine-tools/fastchess/fastchess.exe` or binary path. | `tmp\engine-tools\fastchess\fastchess.exe --help` |
| [ ] | Resolve and clone weather-factory locally. | Pinned repo URL and local path. | Tool-specific `--help` command |

Expected Fastchess setup:

```powershell
mkdir tmp\engine-tools
git clone https://github.com/Disservin/fastchess.git tmp\engine-tools\fastchess
```

Gate: Fastchess runs locally; weather-factory URL is resolved or explicitly blocked awaiting user input.

### Phase 3: Fastchess UCI Wrapper

`hydra_lite/hydra_full.py` is not UCI, so Fastchess needs a wrapper that speaks UCI and launches the ChessAgents script once per move.

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Add/reuse `tools/chessagents_uci_wrapper.py`. | UCI wrapper around any ChessAgents script. | `python tools/chessagents_uci_wrapper.py --help` |
| [ ] | Verify wrapper preserves move history. | UCI `position ... moves ...` becomes ChessAgents FEN/history line. | Wrapper smoke command |
| [ ] | Verify wrapper reports legal move to Fastchess. | 2-game Fastchess smoke. | Agent-provided command |

Gate: Fastchess completes a 2-game match with zero illegal moves/timeouts.

### Phase 4: Validation Suite

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Add `tests/test_chessagents_full.py`. | Syntax, protocol, legality, timeout, forbidden API checks. | `pytest tests/test_chessagents_full.py -q` |
| [ ] | Add randomized FEN/history replay tests. | Generate legal games using Hydra and feed full bundle. | Same pytest command |
| [ ] | Add wall-time benchmark tests. | Measures cold process time on curated positions. | Agent-provided benchmark command |

Gate: validation passes before upload or SPRT.

### Phase 5: Adapter Parameter Experiments

These are likely the highest-impact Python-category changes because the core engine is already full Hydra.

| Status | Candidate | Method |
|---|---|---|
| [ ] | Tune `movetime` for the ChessAgents 5s process wall limit. | Fastchess fixed games, timeout logs |
| [ ] | Tune `Hash` under 256MB memory. | Fastchess SPRT or fixed-game filter |
| [ ] | Tune `move_overhead`. | Timeout safety benchmark |
| [ ] | Improve fallback: output first legal move if search crashes after FEN parse. | Validation tests |
| [ ] | Strip unused code to reduce cold-start time. | Wall-time benchmark, then Fastchess SPRT |

Initial parameter test grid:

| Param | Values |
|---|---|
| `movetime` | 2200, 2600, 3000, 3400 |
| `Hash` | 8, 12, 16, 24, 32 MB |
| `move_overhead` | 50, 100, 150, 250 ms |

Gate: keep only values with zero timeouts and accepted/positive Fastchess result versus baseline.

### Phase 6: First Fastchess SPRT

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Run current full bundle vs frozen baseline. | Exact Fastchess SPRT command. | Long command below |
| [ ] | Interpret result and update this plan. | Accept/reject/continue recorded. | Report format above |
| [ ] | Replace baseline if accepted. | New baseline copied and recorded. | Compile baseline |

Command shape:

```powershell
tmp\engine-tools\fastchess\fastchess.exe `
  -engine cmd="python tools/chessagents_uci_wrapper.py --script hydra_lite/hydra_full.py" name=full_new `
  -engine cmd="python tools/chessagents_uci_wrapper.py --script hydra_lite/hydra_full_baseline.py" name=full_base `
  -each tc=5+0.05 proto=uci `
  -openings file=tools/openings.epd format=epd order=random `
  -rounds 10000 -games 2 -repeat -recover `
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 `
  -pgnout tmp\full_sprt.pgn
```

Gate: no broader tuning until current bundle is not rejected versus baseline.

## Improvement Phases

### Phase 7: Full Hydra Feature Candidates

Because this version is not size-limited, prefer changes to Hydra source modules plus generator regeneration. Every strength change requires Fastchess SPRT.

| Status | Candidate | Method |
|---|---|---|
| [ ] | Add compact opening book to save early-move time and avoid weak openings. | Validate book, Fastchess SPRT book-on vs book-off |
| [ ] | Add root-level move filters/extensions specialized for short 5s fresh process. | Fastchess SPRT |
| [ ] | Add small endgame heuristics for no-Syzygy positions. | Fastchess SPRT |
| [ ] | Improve repetition/draw handling using supplied history. | Validation + Fastchess SPRT |
| [ ] | Optimize startup-heavy precomputations if profiling identifies them. | Wall-time benchmark + SPRT |
| [ ] | Add generator option for stripped submission build vs normal package build. | Validation |

### Phase 8: weather-factory SPSA

Use weather-factory for SPSA after Fastchess validation is stable. Tune source constants, regenerate `hydra_lite/hydra_full.py`, then confirm with Fastchess SPRT.

| Status | Tune Group | Tool | Constants |
|---|---|---|---|
| [ ] | Time management | weather-factory SPSA + Fastchess SPRT | movetime budget, overhead, stability thresholds |
| [ ] | Search margins | weather-factory SPSA + Fastchess SPRT | null, futility, razoring, ProbCut, LMR |
| [ ] | History/search weights | weather-factory SPSA + Fastchess SPRT | history bonuses, pruning thresholds |
| [ ] | Evaluation | weather-factory SPSA + Fastchess SPRT | pawn, mobility, king safety, passed-pawn terms |

Workflow:

```text
You: Implement SPSA for search margins.
Agent: Exposes constants in source/generator, configures weather-factory, updates this plan, gives SPSA command.
You: Run SPSA and report best vector.
Agent: Applies vector, regenerates full bundle, updates this plan, gives Fastchess SPRT command.
You: Run SPRT and report verdict.
Agent: Keeps only if SPRT accepts.
```

### Phase 9: Release Candidate

| Status | Task | Method |
|---|---|---|
| [ ] | Regenerate full single-file bundle from clean source. | `python tools/build_chessagents_full.py` |
| [ ] | Run full validation. | `pytest tests/test_chessagents_full.py -q` |
| [ ] | Run Fastchess smoke. | 20 games, zero illegal moves/crashes/timeouts |
| [ ] | Run final SPRT vs previous baseline. | Accepted or no-regression result |
| [ ] | Upload to Python Only section. | Manual submission |

## Final Upload Checklist

| Status | Check | Command |
|---|---|---|
| [ ] | Syntax | `python -m py_compile hydra_lite\hydra_full.py` |
| [ ] | Protocol smoke | `"<FEN>" | python hydra_lite\hydra_full.py` |
| [ ] | Forbidden APIs acceptable | No network/subprocess/file access in submitted runtime path |
| [ ] | Curated legality tests | `pytest tests/test_chessagents_full.py -q` |
| [ ] | Timeout safety | Curated benchmark under 5s wall time |
| [ ] | Fastchess smoke | 20 games, zero illegal moves/crashes |
| [ ] | Strength | Fastchess SPRT accepted vs previous baseline |

## Recommended Next Action

Implement Phase 0 through Phase 3:

1. Freeze `hydra_lite/hydra_full.py` as `hydra_lite/hydra_full_baseline.py`.
2. Add deterministic `tools/build_chessagents_full.py`.
3. Install Fastchess under `tmp/engine-tools`.
4. Resolve weather-factory URL or block with a clear question.
5. Add the UCI wrapper shared with the lite plan.

Do not start SPSA until the generator, wrapper, and validation suite are stable.
