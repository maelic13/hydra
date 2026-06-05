# Hydra Open Lite Improvement Plan

Goal: make `hydra_lite/hydra_lite.py` as strong as practical under the ChessAgents Open limit: single `.py`, under 50KB, no external packages, one stdin FEN/history line, one legal UCI move, fresh process per move.

## Current State

| Item | Status |
|---|---|
| Plan file | `hydra_lite/PLAN_lite.md` |
| Engine | `hydra_lite/hydra_lite.py` |
| Size | ~19.7KB, under 50KB |
| Protocol | ChessAgents-compatible, not UCI |
| Search | Iterative deepening, alpha-beta/PVS, TT, null move, LMR, qsearch |
| Eval | Material, Hydra PSTs, mobility, pawn structure, king shield, rook files |
| Book | Compact opening lines |
| Main gap | No repeatable Fastchess/weather-factory SPRT/SPSA loop yet |

Unless a command says otherwise, run it from the repository root: `D:\code\hydra`.

## Always Keep This Plan Updated

After every implementation step or reported experiment result, the agent must update this file before ending the turn.

| Trigger | Required Plan Update |
|---|---|
| Agent implements a task | Mark the task done or in-progress, add generated files/commands. |
| User reports SPRT/SPSA/validation result | Record the result and mark keep/revert/continue. |
| A change is rejected | Mark rejected and add the reason. |
| A baseline is replaced | Record old/new baseline filenames and date. |
| Tooling changes | Record exact tool path and clone/source URL. |

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
| [ ] | Copy current lite engine to a frozen baseline. | `hydra_lite/hydra_lite_baseline.py` | `python -m py_compile hydra_lite\hydra_lite_baseline.py` |
| [ ] | Record baseline size, timings, and sample outputs. | Notes appended here. | Agent-provided smoke command |

Gate: baseline exists before further strength work.

### Phase 1: Install Local Tooling

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

### Phase 2: Fastchess UCI Wrapper

`hydra_lite/hydra_lite.py` is not UCI, so Fastchess needs a wrapper that speaks UCI and launches the ChessAgents script once per move.

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Add `tools/chessagents_uci_wrapper.py`. | UCI wrapper around any ChessAgents script. | `python tools/chessagents_uci_wrapper.py --help` |
| [ ] | Add wrapper config examples for current and baseline. | Commands for Fastchess engine entries. | Fastchess 2-game smoke |
| [ ] | Verify history replay in wrapper. | UCI `position ... moves ...` becomes ChessAgents line. | Agent-provided smoke command |

Gate: Fastchess can complete a 2-game match with zero illegal moves/timeouts.

### Phase 3: Opening Suite And Validation

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Add `tools/openings.epd`. | Balanced opening positions. | Fastchess smoke with openings |
| [ ] | Add `tests/test_lite_agent.py`. | Syntax, size, forbidden APIs, legality, timeout tests. | `pytest tests/test_lite_agent.py -q` |
| [ ] | Add book validator. | Verifies every embedded book move is legal. | Same pytest command |

Gate: validation passes before every upload candidate.

### Phase 4: First Fastchess SPRT

| Status | Task | Agent Output | You Run |
|---|---|---|---|
| [ ] | Run current vs frozen baseline with Fastchess SPRT. | Exact command. | Long SPRT command below |
| [ ] | Interpret result and update this plan. | Accept/reject/continue recorded. | Report result format above |
| [ ] | Replace baseline if accepted. | New baseline copied and recorded. | Compile baseline |

Command shape:

```powershell
tmp\engine-tools\fastchess\fastchess.exe `
  -engine cmd="python tools/chessagents_uci_wrapper.py --script hydra_lite/hydra_lite.py" name=lite_new `
  -engine cmd="python tools/chessagents_uci_wrapper.py --script hydra_lite/hydra_lite_baseline.py" name=lite_base `
  -each tc=5+0.05 proto=uci `
  -openings file=tools/openings.epd format=epd order=random `
  -rounds 10000 -games 2 -repeat -recover `
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 `
  -pgnout tmp\lite_sprt.pgn
```

Gate: do not start broad tuning until the current engine is accepted or at least not rejected versus baseline.

## Improvement Phases

### Phase 5: Search Experiments With Fastchess SPRT

Implement one candidate at a time. Every kept change needs Fastchess SPRT.

| Status | Candidate | Method |
|---|---|---|
| [ ] | TT replacement policy: prefer deeper entries, retain best move on alpha nodes. | Fastchess SPRT |
| [ ] | LMR table/formula by depth and move count. | Fastchess SPRT |
| [ ] | Null-move reduction and verification conditions. | Fastchess SPRT |
| [ ] | Futility/reverse futility margins. | Fastchess SPRT, then SPSA later |
| [ ] | Qsearch SEE-lite for captures. | Fastchess SPRT |
| [ ] | Countermove or capture-history ordering. | Fastchess SPRT |

Workflow:

```text
You: Implement next search experiment.
Agent: Implements exactly one experiment, updates this plan, gives Fastchess SPRT command.
You: Run SPRT and report result.
Agent: Updates this plan and keeps/reverts/refines.
```

### Phase 6: Eval/Search Constants With weather-factory SPSA

Use weather-factory for SPSA only after Fastchess/wrapper validation is stable. SPSA proposes constants; Fastchess SPRT confirms them.

| Status | Tune Group | Tool | Constants |
|---|---|---|---|
| [ ] | Search margins | weather-factory SPSA + Fastchess SPRT | null reduction, futility, qsearch delta, LMR thresholds |
| [ ] | PST/material scale | weather-factory SPSA + Fastchess SPRT | PST scale, bishop pair, rook file bonuses |
| [ ] | Pawns | weather-factory SPSA + Fastchess SPRT | isolated, doubled, connected, passed pawn by rank |
| [ ] | Pieces | weather-factory SPSA + Fastchess SPRT | mobility weights, outpost, early queen penalty |
| [ ] | King | weather-factory SPSA + Fastchess SPRT | shield bonus, MG/EG king blend threshold |

Workflow:

```text
You: Implement SPSA for pawn constants.
Agent: Exposes constants, configures weather-factory, updates this plan, gives SPSA command.
You: Run SPSA and report best vector.
Agent: Applies vector, updates this plan, gives Fastchess SPRT confirmation command.
You: Run SPRT and report verdict.
Agent: Keeps only if SPRT accepts.
```

### Phase 7: Opening Book

| Status | Task | Method |
|---|---|---|
| [ ] | Expand compact book to ply 10-12. | Validate, then Fastchess SPRT book-on vs baseline |
| [ ] | Remove bad lines from logs. | Fastchess PGN/log review |
| [ ] | Add generated compact book format if needed. | Keep final under 50KB |

### Phase 8: Speed And Size

| Status | Task | Method |
|---|---|---|
| [ ] | Profile node speed locally. | Temporary counters, remove before upload |
| [ ] | Consider packed-int moves. | Only after profile evidence |
| [ ] | Minify final script. | Keep source/generator if needed |
| [ ] | Final size gate. | `< 50,000` bytes |

## Final Upload Checklist

| Status | Check | Command |
|---|---|---|
| [ ] | Syntax | `python -m py_compile hydra_lite\hydra_lite.py` |
| [ ] | Size under 50KB | `(Get-Item hydra_lite\hydra_lite.py).Length` |
| [ ] | Forbidden APIs absent | `rg -n "\b(open|eval|exec|compile|__import__|subprocess|socket|urllib|requests|http|os\.|pathlib|importlib|ctypes|multiprocessing|child_process|fs)\b" hydra_lite\hydra_lite.py` |
| [ ] | Curated legality tests | `pytest tests/test_lite_agent.py -q` |
| [ ] | Fastchess smoke | 20 games, zero illegal moves/crashes |
| [ ] | Strength | Fastchess SPRT accepted vs previous baseline |

## Recommended Next Action

Implement Phase 0 through Phase 2 first: freeze baseline, install Fastchess locally under `tmp/engine-tools`, resolve weather-factory, and add the UCI wrapper. Do not start SPSA until the wrapper and validation suite are stable.
