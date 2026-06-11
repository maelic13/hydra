# Hydra Lite — ChessAgents Open Plan

**The one goal:** make `hydra_lite/hydra_lite.py` win the ChessAgents **Open** division (https://chessagents.ai/). One single Python file, **< 50,000 bytes**, stdlib only, fresh process per move.

This file is the **complete instruction set for the implementing agent** (usually a smaller model: Sonnet 4.6 / Codex 5.5 medium). Each step in §5/§6 is a self-contained recipe with exact edits, exact self-checks, and an exact gate. **Read §3 (Operating Protocol) before touching anything.** The user-facing quick checklist lives in `hydra_lite/GUIDE.md` — keep its checkboxes in sync with this file.

**Two-phase strategy (decided 2026-06-10):**
- **Phase A (§5)** — bank the *standard* features every strong engine has, one by one, **without SPRT**. Gate = local proofs + a 15-minute **tripwire match** (300 fixed games; score ≥ 47% → bank it). We are at Elo 808 losing 97% of games; hour-long SPRTs per feature are the wrong economics when the known-good gap is hundreds of Elo. Constants get refined later (Phase B SPSA).
- **Phase B (§6)** — once Phase A is uploaded and confirmed, switch to classic SPRT discipline for everything uncertain, ordered most→least promising.

---

## 0. Platform contract (verified against the submit page, 2026-06-10)

| Item | Value |
|---|---|
| Input | One stdin line: 6 FEN fields, optionally ` moves <uci> <uci> ...` (full game history) |
| Output | One legal UCI move (`e2e4`, `e7e8q`), newline, exit |
| Time | **5 seconds per move** (per-move budget, not a game clock) |
| Memory / CPU | 256MB, 1 core |
| Process model | **Fresh process every move** — rebuild from FEN + history; no state survives |
| History purpose | Threefold-repetition detection — `build()` handles this |
| Size cap | **50,000 bytes** (enforced by `tests/test_lite_agent.py::test_size_under_limit`) |
| Libraries | stdlib only; `math`/`random`/`sys` explicitly allowed. **No `open`/file I/O, no `subprocess`, no network, no `ctypes`/`importlib`** (enforced by `test_no_forbidden_apis`). `time` is proven safe — the live v1.0 imports it and plays. |
| Match format | 2 games per match, alternating colors |

---

## 1. Diagnosis — why this plan is architecture-first (read once)

Live result for **Hydra Lite v1.0**: Open division, **Elo 808, record 1/12/431**. It loses because it is **node-starved**, not because the eval is crude: ~25–42k NPS (≈6 ply) vs opponents at 9–11 ply. `attacked()` fires ~once per node (per-move legality + capture ordering); eval is recomputed from scratch at every leaf. Sunfish (pure Python, ~2000 Lichess) proves mailbox + pseudo-legal search + O(1) incremental eval reaches hundreds of k NPS. At 6 ply, +1.5 ply beats any eval-term tweak — so speed first, eval quality second, where it compounds.

**Bitboards rejected** as primary lever (magic-table build = cold-start cost per move; Python big-int overhead; Sunfish proves mailbox suffices).

**The A1 lesson (2026-06-10, −60 Elo):** "textbook-safe" is not the same as "safe as wired". Incremental eval itself was fine (1.58× NPS, evalp provably unchanged) — but feeding the *pruning heuristics* (RFP/null/futility) a material+PST-only static where they were calibrated for the full eval cost −60.2 ± 20 Elo over 1154 games. Moral, now baked into this plan: **every banked feature keeps the meaning of existing inputs unchanged**, cheap-static returns only when the cheap value *is* the real eval (P5 PeSTO), and even "blind" steps get a 15-minute tripwire.

**Lite is not a shrunk Hydra:** every feature must pay at lite's operating point (pure Python, one ~4.4s search, no persistent state). Removing a feature that doesn't pay is a speed win (§6 audit).

---

## 2. Current state (updated 2026-06-10, after A1 SPRT rejection + revert)

| Item | Status |
|---|---|
| Engine | `hydra_lite/hydra_lite.py` — **21,806 bytes** (28KB headroom) |
| Baseline | `hydra_lite/hydra_lite_baseline.py` — frozen 2026-06-05 (= live v1.0, Elo 808) |
| Archive | `hydra_lite/hydra_lite_v10_live.py` — permanent copy of live v1.0 (never touch) |
| Tests | `tests/test_lite_agent.py` — **49 pass** |
| vs baseline | Only difference: `p.score` (incremental material+PST) maintained in `make`/`unmake` — **currently unused by search** (the A1 static-eval wiring was reverted after the −60 SPRT). Node rate ≈ baseline: **avg 41k, midgame ~25k**. `p.score` becomes load-bearing in P5 (PeSTO). |
| Search | ID + PVS + TT + null move + LMR + RFP/futility + qsearch + aspiration; **per-move legality via `legal()` everywhere — the bottleneck (P1)** |
| Eval | full `evalp()` for `static` and qsearch stand-pat: material, PST (king MG/EG by crude phase), mobility, pawn structure (O(64)/pawn passed scan), king shield, rook files, bishop pair |
| Book | ~45 lines; **bug: lines run to 12 ply but `BOOK_PLY=8` cuts them off (P6)** |
| Time | `SEARCH_TIME=4.3` (cold-start ~56–123ms on dev machine) |
| Harness | `tools/sprt_lite.ps1` (SPRT **and** `-FixedGames` tripwire mode), `tools/ca_uci_persistent.py` (st=0.7; **c=8 verified clean** on the 16-core dev box — 6000 forfeit-free calibration games), `tools/ca_uci_coldspawn.py`, `tools/noderate.py`, `tools/eval_equiv.py` |
| Calibration | 2026-06-10: self-vs-self 6000 games, 49.37%, elo −4.4 ± 8, **zero forfeits** → harness healthy (small fixed-book color bias is normal) |

---

## 3. Operating protocol (binding rules for the implementing agent)

1. **One step per session.** Implement exactly the first `[ ]` step (or the one the user names). No drive-by refactors, no "while I'm here".
2. **Announce the step and Tier on your first line.** **Large** + user on a small model → STOP, ask them to switch first.
3. **Follow the Recipe literally.** The recipes encode traps already paid for (see the A1 lesson). If a recipe seems wrong, say why and stop — don't improvise.
4. **Local self-checks are mandatory.** All listed checks green before declaring a step implemented. Stuck after 3 honest attempts → `git restore hydra_lite/hydra_lite.py`, confirm tests, report.
5. **You implement; the user runs matches.** End your turn by printing the step's exact gate command. Don't run fastchess yourself.
6. **Gates by phase:**
   - **Phase A — tripwire** (user runs, ~15 min): 300 fixed games vs current baseline, persistent adapter, c=8.
     - **score ≥ 47%** → banked: run §3.1 acceptance, tick boxes, log in §7, next step.
     - **43–47%** → ambiguous: escalate to a real gainer SPRT before proceeding.
     - **< 43%** → disaster: revert, diagnose, log.
     - Pure-equivalence steps (marked *no-tripwire*) skip the match: the equivalence proof is stronger than 300 games.
   - **Phase B — SPRT** (§4.3 templates): H1 → accept (§3.1); H0 with zero forfeits → step's On-failure branch (default revert + log); any timeouts/crashes → run is void, fix harness first.
7. **Invariants after every edit:** file < 50,000 bytes; tunables stay module-level with stable names (`tools/ca_uci_persistent.py::_SPIN_OPTIONS` mirrors them — update together); no forbidden APIs; all tests pass.
8. **Never edit** `hydra_lite_baseline.py` (except §3.1) or `hydra_lite_v10_live.py` (never).
9. **Update this file and `GUIDE.md` before ending every turn** — statuses, §7 log, measured numbers.

### 3.1 Acceptance procedure (after a banked tripwire or accepted SPRT)

```powershell
Copy-Item hydra_lite\hydra_lite.py hydra_lite\hydra_lite_baseline.py -Force
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q
git add -A
git commit -m "lite: bank <STEP-ID> (<summary>, tripwire XX% | SPRT +X)"
```

Each gate therefore always tests **exactly one change**: `hydra_lite.py` vs `hydra_lite_baseline.py` (everything banked so far).

---

## 4. Infrastructure reference

### 4.1 Test suite (~30s)
```powershell
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q
```
Key gates: size cap, forbidden APIs, **perft ×10** (movegen/make/unmake), root legality + mate/stalemate (`test_no_legal_moves_returns_0000`), `test_eval_unmake_consistency`, `test_incremental_score_matches_evalp` (update `_mat_pst_scratch` whenever the eval representation changes), wall-time.

### 4.2 Node-rate gate
```powershell
& .venv\Scripts\python.exe tools/noderate.py
```
Reports NPS/eval-s/attacked-s vs the fixed 42k v1.0 anchor. Current: **avg 41k, midgame 25k**. Record absolute numbers in §7 for every speed step.

### 4.3 Match runner — `tools/sprt_lite.ps1` (user-run; persistent st=0.7 **c=8** is verified clean)

| Purpose | Command | Pass |
|---|---|---|
| **Tripwire (Phase A)** | `.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_baseline.py -Adapter persistent -Concurrency 8 -FixedGames 300` | score ≥ 47% |
| Gainer SPRT (Phase B) | same minus `-FixedGames` | H1 (elo ≥ 5) |
| Simplify SPRT (cuts) | same + `-Mode simplify` | H1 (elo ≥ 0 ⇒ keep the cut) |
| Cold-spawn confirmation | `-EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_v10_live.py -Adapter coldspawn` | H1, expect large |
| Eval-refactor proof | `& .venv\Scripts\python.exe tools/eval_equiv.py --ref tmp_eval_ref.py --new hydra_lite/hydra_lite.py` | PASS |

Any run with `timeouts>0` or `crashes>0` is **void** regardless of score.

### 4.4 Report format
```text
games=...  score%=...  elo=...±...  timeouts=...  crashes=...  notes=...
```

---

## 5. PHASE A — bank the standards (tripwire-gated, no SPRT)

Status: `[ ]` todo · `[~]` implemented, awaiting tripwire · `[x]` banked · `[R]` reverted.
Tier: **Small** = mechanical + exact local proof. **Large** = correctness-dense; strongest model, review the diff.

Order is deliberate: speed first (P1–P4), then eval quality on the faster core (P5), then book (P6), then the one real SPRT + upload (PG).

---

### P1 `[ ]` Lazy legality in search — kill per-node `legal()` · *Tier: **Large*** *(was S2)*

**The single biggest lever.** `ab()` and `q()` call `legal()`, which does make+`incheck`+unmake for **every pseudo move** at **every node** — even moves never searched past a beta cutoff. Replace with: generate **pseudo** moves; after `make`, skip if the mover left their king in check. Cut-nodes stop paying for the ~25 moves they never try. Standard in every strong engine.

**Files:** `hydra_lite/hydra_lite.py` only — functions `ab` and `q` inside `search()`. **`legal()` itself stays** (root loop, `parseuci`, perft, final fallback).

**Recipe — `ab()`:**
```python
# BEFORE                                      # AFTER
ms=legal(p)                                   ms=pseudo(p)
if not ms: return -MATE+ply if inc else 0     # (deleted — handled after the loop)
if inc: d+=1                                  if inc: d+=1
... bestm=None; cnt=0                         ... bestm=None; cnt=0
for m in order(p,ms,bm,killers[ply],hist):    for m in order(p,ms,bm,killers[ply],hist):
    cnt+=1                                        if cnt>0 and d<=2 and not inc and quiet(p,m) \
    if d<=2 and not inc and quiet(p,m) \              and static+FP_MARGIN*d<=a: continue
        and static+FP_MARGIN*d<=a: continue       u=make(p,m)
    u=make(p,m); k=key(p); ...                    if incheck(p,not p.w): unmake(p,u); continue
                                                  cnt+=1
                                                  k=key(p); rep[k]=rep.get(k,0)+1
                                                  try: ... (PVS body unchanged, uses cnt>1) ...
                                                  finally: rep[k]-=1; unmake(p,u)
# after the loop, before store():
                                              if cnt==0: return -MATE+ply if inc else 0
```

Five load-bearing details:
1. **`incheck(p, not p.w)` after `make`** — `make` flips `p.w`, so `not p.w` is the side that just moved. King attacked → illegal → `unmake` + `continue`.
2. **`cnt` counts *legal* moves only** (incremented after the check) — keeps PVS (`cnt>1` ⇒ null-window) and LMR semantics: first *legal* move gets the full window.
3. **Futility skip guarded by `cnt>0`** — keeps mate/stalemate detection *exact*: `cnt==0` at loop end means every pseudo move was made and refuted, so `return -MATE+ply if inc else 0` is correct.
4. Rep bookkeeping (`k=key(p); rep[k]+=1 … finally: rep[k]-=1; unmake`) moves *inside* the legal branch; an illegal move's unmake happens before the try block and must not touch `rep`.
5. PVS/LMR ladder, killer/history update, TT `store` on cutoff — unchanged.

**Recipe — `q()`:** same, simpler: `ms=pseudo(p,True)`; after `u=make(p,m)`: `if incheck(p,not p.w): unmake(p,u); continue`; rest unchanged. No `cnt` (stand-pat exists, no mate claims).

**Do NOT touch:** root loop in `search()` (keeps `legal(p)`), the `incheck` null-move guard, check extension, `pseudo()`'s castling transit checks.

**Why safe-by-construction:** illegal TT/killer moves just get made, detected, skipped. En-passant discovered check is caught because `incheck` runs *after* `make` removed both pawns.

**Self-checks:**
1. *Add two tests first*: `test_mate_in_one` — `6k1/5ppp/8/8/8/8/8/4K2R w K - 0 1` → `h1h8`; `7k/5Q2/5K2/8/8/8/8/8 w - - 0 1` → `f7g7`. Verify each against the *current* engine before relying on it; if it fails pre-change, fix the test position.
2. Full suite green (perft = movegen gate; mate tests = search gate).
3. `noderate.py`: expect **avg ≥ 70k, midgame ≥ 45k** (from 41k/25k). Below 60k avg → profile before the tripwire, report.

**Gate:** tripwire (§4.3). Expect well above 50%.
**On failure (< 43%):** revert; the plan's central thesis is wrong — stop and re-plan with the user.
**Size:** ≤ +0.3KB.

---

### P2 `[ ]` Pure MVV-LVA ordering — drop `attacked()` from `mscore` · *Tier: Small* *(was S3)*

**Recipe:** in `mscore()` delete exactly:
```python
if c!="." and VAL.get(c,0)+80<VAL.get(a,0) and attacked(p,to,not p.w): s-=550
```
Ordering becomes MVV-LVA + promo + killers + history (real SEE arrives in B1).
**Self-checks:** suite green; `noderate.py` — attacked/s drops, NPS up (record).
**Gate:** tripwire. **On failure:** restore the line with `and a in "QR"` variant, re-tripwire once; still failing → restore original, mark `[R]`.

---

### P3 `[ ]` TT fix — never wipe mid-search · *Tier: Small* *(was S4)*

**What:** `store()` does `if len(TT)>TT_MAX_ENTRIES: TT.clear()` — at post-P1 speed a 4.3s search overflows 25k entries and wipes the table repeatedly. Pure defect.
**Recipe:** (1) `def store(h,d,v,fl,bm):` body → `if h in TT or len(TT)<TT_MAX_ENTRIES: TT[h]=(d,v,fl,bm)`; (2) `TT_MAX_ENTRIES=300000` (≈60–90MB worst case, fits 256MB); (3) mirror in `_SPIN_OPTIONS["TT_MAX_ENTRIES"]` → `(300000, 1000, 1000000)`.
**Self-checks:** suite green; `noderate.py` no regression.
**Gate:** tripwire (can share one tripwire with P4 if landed together — note it in §7).

---

### P4 `[ ]` Passed-pawn scan refactor · *Tier: Small · no-tripwire (exact equivalence)* *(was S5)*

**What:** the passed-pawn test inside `evalp()` loops over all 64 squares per pawn. Replace with per-file extremes computed once per call. **Bit-identical output required.**
**Recipe:** (1) `Copy-Item hydra_lite\hydra_lite.py tmp_eval_ref.py`; (2) in `evalp`'s first pass also build `bmax[f]` = highest black-pawn rank per file (else −1) and `wmin[f]` = lowest white-pawn rank per file (else 8); (3) white pawn (r,f) passed ⟺ `bmax[ff] <= r` for all on-board `ff in (f-1,f,f+1)`; black ⟺ `wmin[ff] >= r`; (4) `tools/eval_equiv.py --ref tmp_eval_ref.py --new hydra_lite/hydra_lite.py` → **PASS**, then delete the snapshot.
**Self-checks:** eval_equiv PASS; suite green; noderate (eval/s up).
**Gate:** none needed (equivalence proof beats 300 games). Bank via §3.1 directly.

---

### P5 `[ ]` PeSTO tapered eval — and make `evalp` cheap · *Tier: **Large*** *(was S7, expanded)*

**What:** replace the crude eval with PeSTO's 12 tables (6 pieces × MG/EG) + MG/EG piece values, interpolated by incremental phase — **and restructure so the tapered base comes from the incremental accumulators**, making `evalp()` near-O(1). This is where the A1 idea returns *safely*: the cheap value now **is** the eval, so `static=evalp(p)` stays correct and becomes fast. Biggest expected eval gain in the whole plan.

**Recipe:**
1. **Tables:** fetch exact values from https://www.chessprogramming.org/PeSTO%27s_Evaluation_Function (`mg_*_table`/`eg_*_table`, `mg_value`/`eg_value`). PeSTO arrays are a8-first; our `_ps()` flips with `si = sq if w else sq^56` for a1-first — verify orientation against known cells (e.g. mg pawn e4 vs e2) rather than trusting either convention blindly. **Do not write tables from memory without step-5 checks.**
2. **Representation:** replace `p.score` with three slots `mg`, `eg`, `ph` on `P` (update `__slots__`), maintained in `__init__`/`make`/`unmake` exactly where `score` is updated today. Phase weights N=B=1, R=2, Q=4, capped at 24 in use.
3. **Eval:** `evalp(p)` = `base = (p.mg*ph + p.eg*(24-ph)) // 24` (white-perspective, `ph=min(p.ph,24)`) **plus only cheap terms**: passed/isolated/doubled pawns (per-file arrays from P4), rook (semi-)open file, bishop pair, king pawn-shield. **Drop:** `center()` bonuses, `rr*10` pawn advance, crude `phase>2200`-style branches, `KMG`/`KEG`/old `PST`, **and `mob()` entirely** — it is the most expensive remaining term and PeSTO's PSTs encode piece activity; mobility may return in Phase B if an SPRT earns it. Keep old `VAL` for MVV-LVA ordering + qsearch delta margins only.
4. `static=evalp(p)` and qsearch stand-pat: unchanged call sites — they just got fast.
5. **Tests in the same step:** rewrite `_mat_pst_scratch()` to recompute `(mg, eg, ph)` from scratch and assert all three vs the incremental values; add `test_eval_startpos_zero` (startpos must eval to exactly 0); add `test_eval_mirror` (color-flipped position ⇒ exact negation — catches `^56` bugs); assert all 12 tables length 64.
**Self-checks:** new tests + full suite; `noderate.py` — expect a further **large NPS jump** (eval is now ~O(1)); eval_equiv N/A (values change by design).
**Gate:** tripwire. Expect well above 50%.
**On failure:** first suspect table orientation/transcription (spot-check 5 random cells against source); second, re-add king pawn-shield weight ×2; one retry, then revert + log.
**Size:** ~+3KB.

---

### P6 `[ ]` Book: `BOOK_PLY` fix + expansion · *Tier: Small* *(was S9)*

**Recipe:** (1) set `BOOK_PLY` = longest line length and make `book()`'s `hist[:12]` slice use `BOOK_PLY` (today plies 9–12 are dead code); (2) extend the line block `L` to ~16 plies of mainlines for openings already present (Ruy, Italian, Sicilian, French, Caro-Kann, QGD/QGA, Slav, KID, Nimzo, English; both colors), +5–10KB; every move must pass `test_book_move_legal` — extend its parametrization; (3) bump `_SPIN_OPTIONS["BOOK_PLY"]` max if needed.
**Self-checks:** suite green (book legality test is the real gate); size check.
**Gate:** none (book lines either replay legally or the test fails). Bank directly. Live board validates.

---

### PG `[ ]` Phase-A gate — cold-spawn SPRT + **upload** · *user-run*

The one real SPRT in Phase A — deployment-exact, against the archived live version:
```powershell
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_v10_live.py -NameA phaseA -NameB v10 -Adapter coldspawn
```
**Expect:** fast, strongly positive (cumulative Phase A should be worth hundreds of Elo; fastchess stops early). **Zero timeouts mandatory** — this run also validates `SEARCH_TIME=4.3` under cold-spawn; any timeout → drop to 4.2, re-run.
**Then:** upload `hydra_lite/hydra_lite.py` to https://chessagents.ai/; record live Elo/W-D-L in §7 after ~a day. The leaderboard is the north star — if it disagrees badly with local results, fix the harness, not the engine.

---

## 6. PHASE B — SPRT-gated refinements (most → least promising)

Classic discipline resumes: one change, one gainer SPRT (H1 = accept), §3.1 on accept, revert on clean H0.

| # | Status | Item | Tier | Notes |
|---|---|---|---|---|
| B1 | `[ ]` | **SEE** (static exchange eval) for qsearch pruning (`see<0` → skip) + capture ordering | **Large** | Classic swap algorithm on the target square via a dedicated least-valuable-attacker helper with x-rays; promotions/EP may bail conservatively. **Write 4–6 hand-verified unit vectors first.** NPS may drop while depth rises — judge only by SPRT. ~+1KB. *(was S8)* |
| B2 | `[ ]` | **SPSA on search constants** — `RFP_MARGIN`, `FP_MARGIN`, `NULL_*`, `LMR_*`, `QDELTA_MARGIN`, `ASPIRATION_WINDOW` | **Large** setup, then mechanical | The "refine constants later" step: every margin was hand-guessed for the old slow engine; after P1+P5 they're stale. weather-factory (`D:\code\basilisk\tools\weather-factory\`) + `tools/spsa/` configs + persistent adapter. SPSA proposes → one confirming SPRT decides. |
| B3 | `[ ]` | **Attack-based king safety** (attacker count/weights into king zone, MG-scaled) | **Large** | Design freely, SPRT decides. ~+1–2KB. *(was S10)* |
| B4 | `[ ]` | **Threats bundle**: rook on 7th, knight outposts, pawn threats, tempo; + treat in-search **twofold repetition as draw** (standard; avoids repetition blindness) | **Large** | One SPRT for the bundle; on H0 halve the bundle once, then keep/revert. *(was S11)* |
| B5 | `[ ]` | **Keep/cut audit** (simplify-mode SPRTs): aspiration-window loop → plain full window; fold root loop into `ab` (PVS root); `LMR_DEPTH` 2→1 | Large judgment, Small edits | H1 in simplify mode (≥0 without it) ⇒ cut — bytes and ns are the win. |
| B6 | `[ ]` | **Texel-tune eval weights** (label positions with the full `hydra/` package engine) | **Large** | After B1–B4 settle. |
| B7 | `[ ]` | Experiments: staged movegen; bitboard attack-gen (static literal tables only); platform module probe (`tools/probe_modules.py`) if ever needed | **Large** | Each must beat an SPRT; expect to revert. |
| BT | `[ ]` | **Time-budget re-validation**: cold-spawn 20-game smoke, zero timeouts at `SEARCH_TIME=4.3`; if >0.5s headroom, try 4.5 + re-smoke | user-run | After any speed-profile change. *(was S12)* |
| BF | `[ ]` | **Final upload checklist**: `py_compile`, size < 50000, full suite, cold-spawn smoke, upload, record live Elo | any | *(was S13)* |

---

## 7. Results log (append-only — newest last)

| Date | Step | Result | Decision / numbers |
|---|---|---|---|
| 2026-06-05 | — | baseline frozen | = live v1.0, Elo 808 (1/12/431) |
| 2026-06-06 | A0 | noderate.py landed | v1.0: avg 42k NPS, midgame 25k |
| 2026-06-06 | A1 | incremental eval implemented (49 tests) | evalp identical; 66k avg NPS with cheap static |
| 2026-06-07 | A1 SPRT | **void** — forfeits (st=0.5, c8) | adapter fixed; old autosave config.json deleted |
| 2026-06-10 | cleanup | hydra_full removed; plan v2; eval_equiv.py, GUIDE.md added | 49 tests; 21,826B |
| 2026-06-10 | S0 calib | 6000 games, 49.37%, elo −4.4±8, **0 forfeits** (st=0.7 **c=8**) | harness healthy; slight book color bias is normal; c=8 adopted |
| 2026-06-10 | S1 A1 SPRT | **REJECTED**: −60.2±20 Elo, 1154 games, H0 | root cause: RFP/null/futility static switched to material+PST-only → systematic mispruning. Reverted `static=evalp(p)`; kept `p.score` infra (unused until P5). NPS back to 41k avg. |
| 2026-06-10 | replan | **Plan v3**: Phase A safe-queue (tripwire, no SPRT) + Phase B SPRT queue; `-FixedGames` tripwire mode added to sprt_lite.ps1 | step map: S2→P1, S3→P2, S4→P3, S5→P4, S7→P5, S9→P6, S6→PG, S8→B1, S10→B3, S11→B4, S12→BT, S13→BF |
