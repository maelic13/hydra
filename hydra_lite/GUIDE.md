# Hydra Lite — Quick Guide

**Goal:** win the ChessAgents **Open** division (https://chessagents.ai/) with one file: `hydra_lite/hydra_lite.py` — Python, < 50,000 bytes, stdlib only, 5s/move, fresh process per move.

All detail lives in **`PLAN_lite.md`**. This file is just your checklist and cheat-sheet.

## How a dev session goes

1. **Pick the model** for the next unchecked step (tier is listed below and in the plan).
   - **Small** = Sonnet 4.6 / Codex 5.5 medium is fine.
   - **Large** = use the strongest model you have; review the diff.
2. Say: **"Implement the next step in hydra_lite/PLAN_lite.md."**
3. The agent edits, runs its self-checks, then prints **one command** for you (usually an SPRT — takes minutes to hours).
4. Run it. Paste the result block back (games / score / elo / sprt / **timeouts** / crashes).
5. The agent accepts (re-freezes baseline, ticks boxes, tells you what to commit) or reverts. Any run with timeouts/crashes > 0 is void — don't argue with its Elo.

## Step checklist (mirror of PLAN_lite.md §5 — agent keeps these in sync)

- [ ] **S0** Calibration SPRT (self vs self → must be ~0) — *you run it*
- [ ] **S1** A1 acceptance SPRT (incremental eval, already coded) — *you run it*
- [ ] **S2** A2 lazy-legality search (the big speed jump) — **Large**
- [ ] **S3** A3 cheap move ordering (drop attacked() from mscore) — Small
- [ ] **S4** A5 TT fix (no wipe-on-overflow) — Small
- [ ] **S5** A4 passed-pawn speed pass (exact refactor) — Small
- [ ] **S6** Block-1 cold-spawn confirmation vs live v1.0 → **upload to chessagents.ai**
- [ ] **S7** E1 PeSTO tapered eval — **Large**
- [ ] **S8** E2 SEE — **Large**
- [ ] **S9** B1 bigger book + BOOK_PLY fix — Small
- [ ] **S10** E4 king safety — **Large**
- [ ] **S11** E5 threats/positional — **Large**
- [ ] **S12** Time-budget re-validation (cold-spawn smoke) — *you run it*
- [ ] **S13** Final upload checklist → **upload**

After S6 and after each later accepted step: re-upload and note the live Elo in PLAN_lite.md §8.

## Commands cheat-sheet

```powershell
# Tests (~30s, 49 tests)
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q

# Node-rate gate (current: avg 66k, midgame 31k)
& .venv\Scripts\python.exe tools/noderate.py

# Size (< 50000)
(Get-Item hydra_lite\hydra_lite.py).Length

# Calibration SPRT (S0)
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite_baseline.py -EngineB hydra_lite\hydra_lite_baseline.py -NameA S1 -NameB S2 -Adapter persistent -Elo0 -3 -Elo1 3

# Feature SPRT (candidate vs baseline, fast persistent mode)
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_baseline.py -Adapter persistent

# Deployment-realistic SPRT (cold-spawn, 5s/move)
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_v10_live.py -Adapter coldspawn
```

## House rules (short version)

- One step per session, in order. The plan's recipe wins over anyone's improvisation.
- Nothing is "done" without its self-checks **and** its SPRT verdict.
- `hydra_lite_baseline.py` = everything accepted so far (only updated via the acceptance procedure). `hydra_lite_v10_live.py` = the frozen live submission (never touched).
- Commit after every accepted step.
