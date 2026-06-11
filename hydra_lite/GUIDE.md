# Hydra Lite — Quick Guide

**Goal:** win the ChessAgents **Open** division (https://chessagents.ai/) with one file: `hydra_lite/hydra_lite.py` — Python, < 50,000 bytes, stdlib only, 5s/move, fresh process per move.

All detail lives in **`PLAN_lite.md`**. This file is just your checklist and cheat-sheet.

## The strategy in one paragraph

**Phase A:** bank the standard chess-engine features one by one **without SPRT** — each gets local proofs (tests/perft/equivalence) plus a 15-minute **tripwire** (300 games; score ≥ 47% → bank it, move on). Then one cold-spawn SPRT vs live v1.0 and **upload**. **Phase B:** classic SPRT discipline for everything uncertain, most promising first, including SPSA to refine the constants Phase A inherited.

## How a dev session goes

1. **Pick the model** for the next unchecked step (tier below). Small = Sonnet 4.6 / Codex medium. **Large = strongest model you have.**
2. Say: **"Implement the next step in hydra_lite/PLAN_lite.md."**
3. The agent edits, runs its self-checks, then prints **one command** for you.
4. Run it (~15 min tripwire in Phase A; longer SPRT in Phase B). Paste the result.
5. The agent banks (re-freezes baseline, ticks boxes, tells you what to commit) or reverts. **Timeouts/crashes > 0 = void run.**

## Phase A checklist — bank the standards (tripwire only)

- [~] **P1** Lazy legality in search (the big speed jump) — **Large** — *implemented, run the tripwire*
- [ ] **P2** Pure MVV-LVA ordering (drop attacked() from mscore) — Small
- [ ] **P3** TT fix (never wipe mid-search) — Small
- [ ] **P4** Passed-pawn scan refactor (exact equivalence, no tripwire) — Small
- [ ] **P5** PeSTO tapered eval + cheap evalp (the big eval jump) — **Large**
- [ ] **P6** Book: BOOK_PLY fix + deeper lines — Small
- [ ] **PG** Cold-spawn SPRT vs live v1.0 → **upload to chessagents.ai** — *you run it*

## Phase B checklist — SPRT-gated, most promising first

- [ ] **B1** SEE (qsearch pruning + ordering) — **Large**
- [ ] **B2** SPSA: retune all search constants — **Large** setup
- [ ] **B3** Attack-based king safety — **Large**
- [ ] **B4** Threats bundle + twofold-repetition draw — **Large**
- [ ] **B5** Keep/cut audit (aspiration, root fold, LMR depth) — simplify SPRTs
- [ ] **B6** Texel-tune eval weights — **Large**
- [ ] **B7** Experiments (staged movegen, bitboards) — optional
- [ ] **BT** Time-budget re-validation (cold-spawn smoke) — *you run it*
- [ ] **BF** Final upload checklist → **upload**

Re-upload after each accepted Phase-B step; note live Elo in PLAN_lite.md §7.

## Commands cheat-sheet

```powershell
# Tests (~30s)
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q

# Node rate (current: avg 41k, midgame 25k)
& .venv\Scripts\python.exe tools/noderate.py

# Size (< 50000)
(Get-Item hydra_lite\hydra_lite.py).Length

# TRIPWIRE — Phase A gate, ~15 min (pass: score >= 47%)
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_baseline.py -Adapter persistent -Concurrency 8 -FixedGames 300

# SPRT — Phase B gate (H1 = accept)
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_baseline.py -Adapter persistent -Concurrency 8

# Cold-spawn confirmation vs live v1.0 (PG / before uploads)
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_v10_live.py -Adapter coldspawn
```

## House rules (short version)

- One step per session, in order. The plan's recipe wins over improvisation.
- Tripwire verdicts: **≥ 47% bank · 43–47% escalate to SPRT · < 43% revert.**
- `hydra_lite_baseline.py` = everything banked so far (only updated via acceptance procedure). `hydra_lite_v10_live.py` = frozen live submission (never touched).
- Commit after every banked step.
- Hard limits never bend: **< 50,000 bytes**, stdlib only, no file I/O / subprocess / network.
