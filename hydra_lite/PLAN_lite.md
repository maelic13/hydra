# Hydra Lite — ChessAgents Open Plan

**The one goal:** make `hydra_lite/hydra_lite.py` win the ChessAgents **Open** division (https://chessagents.ai/). One single Python file, **< 50,000 bytes**, stdlib only, fresh process per move.

This file is the **complete instruction set for the implementing agent** (usually a smaller model: Sonnet 4.6 / Codex 5.5 medium). Each step in §5 is a self-contained recipe with exact edits, exact self-checks, and an exact acceptance gate. **Read §3 (Operating Protocol) before touching anything.** The user-facing quick checklist lives in `hydra_lite/GUIDE.md` — keep its checkboxes in sync with this file.

---

## 0. Platform contract (verified against the submit page, 2026-06-10)

| Item | Value |
|---|---|
| Input | One stdin line: 6 FEN fields, optionally ` moves <uci> <uci> ...` (full game history) |
| Output | One legal UCI move (`e2e4`, `e7e8q`), newline, exit |
| Time | **5 seconds per move** (per-move budget, not a game clock) |
| Memory / CPU | 256MB, 1 core |
| Process model | **Fresh process every move** — no state survives between moves; rebuild from FEN + history |
| History purpose | Threefold-repetition detection (a bare FEN has no history) — `build()` handles this |
| Size cap | **50,000 bytes** (enforced by `tests/test_lite_agent.py::test_size_under_limit`) |
| Libraries | stdlib only; `math`/`random`/`sys` explicitly allowed. **No `open`/file I/O, no `subprocess`, no network, no `ctypes`/`importlib`** (enforced by `test_no_forbidden_apis`). `time` is proven safe — the live v1.0 submission imports it and plays games. |
| Match format | 2 games per match, alternating colors |

---

## 1. Diagnosis — why this plan is architecture-first (read once)

Live result for **Hydra Lite v1.0**: Open division, **Elo 808, record 1/12/431** (as of 2026-06-06). It loses ~97% of games because it is **node-starved**, not because the eval is crude:

- v1.0 measured **~28k nodes/s on the midgame test position** (~6 ply); opponents reach 9–11 ply.
- **`attacked()` fires ~once per node** — caused by per-move legality (`legal()` = make+incheck+unmake for *every* pseudo move at *every* node) and by `mscore()` calling `attacked()` on every capture.
- Eval was recomputed from scratch at every leaf, including an O(64)-per-pawn passed-pawn scan.

Reference point: **Sunfish** (pure Python, ~2000 Lichess) reaches hundreds of k nps with a *simpler* search than ours. The gap is board/eval mechanics, not search features. At ~6 ply, **+1.5 ply of depth beats any eval-term tweak**, so speed (A-items) comes first and eval quality (E-items) second, where it compounds with the extra depth.

**Bitboards were considered and rejected** as the primary lever: magic-table construction adds cold-start under fresh-process-per-move, Python big-int overhead erodes the win, and Sunfish proves mailbox suffices. (Optional later experiment — §7.)

**Lite is not a shrunk Hydra:** every feature must pay at lite's operating point (pure Python, one ~4.4s search, ~6–10 ply, no persistent state). Removing a feature that doesn't pay is a *speed win*. Keep/cut is decided by SPRT, never opinion (§6).

---

## 2. Current state (updated 2026-06-10)

| Item | Status |
|---|---|
| Engine | `hydra_lite/hydra_lite.py` — **21,826 bytes** (28KB headroom) |
| Baseline | `hydra_lite/hydra_lite_baseline.py` — frozen 2026-06-05 (= live v1.0, Elo 808) |
| Tests | `tests/test_lite_agent.py` — **49 pass** (syntax, size, forbidden APIs, legality, history, perft ×10, timeout, promotion, book, eval guardrails) |
| Implemented, **not yet SPRT-accepted** | **A1 incremental eval**: `p.score` = material+PST, O(1) delta in `make`/`unmake`; `ab()` uses it for RFP/null/futility static. evalp() unchanged (verified identical to baseline via `tools/eval_equiv.py`). |
| Node rate (2026-06-10, `tools/noderate.py`, 3s × 4 positions) | **avg 66k NPS** (start 102k, **midgame 31k**, tactical 35k, endgame 97k) = **1.58×** the 42k baseline. `attacked()` still ~1.06/node (848k calls / 801k nodes) → **S2 is the next big lever** |
| Search | ID + PVS + TT + null move + LMR + RFP/futility + qsearch + aspiration; **per-move legality via `legal()` everywhere (the bottleneck)** |
| Eval | full `evalp()` at qsearch stand-pat: material, PST (king MG/EG by crude phase), mobility, pawn structure (O(64)/pawn passed scan), king shield, rook files, bishop pair |
| Book | ~45 lines; **bug: lines run to 12 ply but `BOOK_PLY=8` cuts them off at 8** (fixed in S9) |
| Time | `SEARCH_TIME=4.3` (cold-start measured ~56–123ms on dev machine) |
| Harness | `tools/ca_uci_persistent.py` (fast SPRTs; exposes tunables as UCI options), `tools/ca_uci_coldspawn.py` (deployment-realistic), `tools/sprt_lite.ps1` (runner), `tools/noderate.py` (speed gate), `tools/eval_equiv.py` (eval-refactor gate) |
| History note | The 2026-06-07 A1 SPRT runs are **void** (time forfeits at st=0.5/concurrency 8). Adapter fixed; persistent defaults are now st=0.7, concurrency 2. The old fastchess autosave `config.json` was deleted — never resume it. |
| Removed 2026-06-10 | `hydra_full.py` + `PLAN_full.md` + generator — this repo's competition effort is **lite only** now. |

---

## 3. Operating protocol (binding rules for the implementing agent)

1. **One step per session.** Implement exactly the first step in §5 whose Status is `[ ]` (or the step the user names). Nothing else. No drive-by refactors, no "while I'm here" improvements, no touching other steps' code.
2. **Announce the step and its Tier on your first line.** If the Tier is **Large** and the user appears to be on a small model, STOP and ask them to switch models before writing any code.
3. **Follow the Recipe literally.** The recipes encode correctness traps that were already thought through. If the recipe seems wrong, say why and stop — don't improvise.
4. **Self-checks are mandatory and local.** Run every listed self-check; all must pass before you declare the step implemented. If you can't get them green after 3 honest attempts: `git restore hydra_lite/hydra_lite.py`, re-run the tests to confirm the revert, and report what failed.
5. **You implement; the user runs SPRTs.** SPRTs take minutes-to-hours of wall time. End your turn by printing the step's exact **Strength gate** command and the report format (§4.4). Do not attempt to run fastchess yourself.
6. **When the user reports a verdict:**
   - **Accepted** → run the *acceptance procedure* (§3.1), tick the step `[x]` here and in `GUIDE.md`, append a row to §8 Results Log.
   - **Rejected** (with zero time forfeits/crashes) → follow the step's **On failure** branch; default is revert + log the result and your hypothesis in §8.
   - **Forfeits/crashes > 0** → the run is void. Diagnose the harness, not the engine.
7. **Invariants after every edit:** file `< 50,000` bytes; tunable constants stay module-level with their existing names (`tools/ca_uci_persistent.py::_SPIN_OPTIONS` references them — update it when you add/rename one); no forbidden APIs; all 49+ tests pass.
8. **Never edit** `hydra_lite_baseline.py` (except via §3.1 re-freeze) or `hydra_lite_v10_live.py` (the archived live submission, created in S1).
9. **Update this file and `GUIDE.md` before ending every turn** — status boxes, Results Log, and any measured numbers.

### 3.1 Acceptance procedure (after an accepted SPRT)

```powershell
# 1. Re-freeze: the accepted candidate becomes the new baseline
Copy-Item hydra_lite\hydra_lite.py hydra_lite\hydra_lite_baseline.py -Force
# 2. Confirm everything is still green
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q
# 3. Suggest the user commits:
git add -A
git commit -m "lite: accept <STEP-ID> (<one-line summary>, SPRT ~+X Elo)"
```

Every SPRT therefore always tests **exactly one change**: `hydra_lite.py` (candidate) vs `hydra_lite_baseline.py` (everything accepted so far).

---

## 4. Infrastructure reference

### 4.1 Test suite — `tests/test_lite_agent.py` (run time ~30s)

```powershell
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q
```

Key gates: `test_size_under_limit` (50KB), `test_no_forbidden_apis`, `test_perft` (10 known node counts across 4 positions — catches any movegen/make/unmake bug), `test_returns_legal_move` / `test_no_legal_moves_returns_0000` (root legality, mate/stalemate), `test_eval_unmake_consistency` (unmake has no side effects), `test_incremental_score_matches_evalp` (after every make, `p.score` == from-scratch material+PST via `_mat_pst_scratch()` — **if a step changes the eval representation, update `_mat_pst_scratch` in the same step**), `test_wall_time_under_limit`.

### 4.2 Node-rate gate — `tools/noderate.py`

```powershell
& .venv\Scripts\python.exe tools/noderate.py            # 3s × 4 fixed positions
```

Reports per-position NPS, eval/s, attacked/s and an avg-NPS ratio vs the **fixed historical reference 42k** (don't edit that constant — it's the v1.0 anchor). Record the **absolute avg and midgame NPS** in §8 for every speed step. Current: avg 66k, midgame 31k.

### 4.3 SPRT runner — `tools/sprt_lite.ps1` (user-run)

Wraps fastchess (reused from `D:\code\basilisk\tools\bin\fastchess.exe` + SuperGM book). Two adapters:

- **persistent** (st=0.7, concurrency 2 defaults): engine imported once, cold-start excluded. Use for all in-tree feature/speed comparisons. *Not valid for time-manager questions.* Don't raise concurrency — the old st=0.5/c8 setting caused time forfeits.
- **coldspawn** (st=5.0, concurrency 3 defaults): fresh process per move = deployment-exact. Use for block confirmation and time-budget validation.

| Purpose | Command template | Pass condition |
|---|---|---|
| Calibration (self vs self) | `.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite_baseline.py -EngineB hydra_lite\hydra_lite_baseline.py -NameA S1 -NameB S2 -Adapter persistent -Elo0 -3 -Elo1 3` | **H0** (~0 Elo). H1 = broken harness. |
| Gainer (new feature / speed) | `.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_baseline.py -Adapter persistent` | **H1** (elo ≥ 5). Defaults Elo0=0, Elo1=5. |
| Simplify (cut a feature) | same + `-Mode simplify` | **H1** (elo ≥ 0 ⇒ cut is free or better ⇒ keep the cut). H0 (≤ −5) ⇒ restore. |
| Block confirmation | `-Adapter coldspawn` gainer vs the **archived** reference | **H1**, expect large Elo |

Every SPRT result with `timeouts>0` or `crashes>0` is **void** regardless of Elo.

### 4.4 Report formats

```text
SPRT : games=...  score=+W -L =D  elo=...  sprt=accepted|rejected|continue  timeouts=...  crashes=...  notes=...
Speed: avg_nps=...  midgame_nps=...  attacked/s=...  delta_vs_prev=...x
```

---

## 5. Step queue — do strictly in order

Status: `[ ]` todo · `[~]` implemented, awaiting SPRT · `[x]` accepted · `[R]` rejected/reverted.

> Tier guide: **Small** = mechanical, has an exact local self-check (perft / equivalence / unit test) — Sonnet 4.6 / Codex medium can own it. **Large** = a subtle bug passes local tests but loses games — use the strongest available model and review the diff carefully.

---

### S0 `[ ]` Calibration SPRT — prove the harness before trusting it · *user-run, any model interprets*

**Why:** all later verdicts are meaningless if self-vs-self doesn't come out ~0.

**User runs:**
```powershell
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite_baseline.py -EngineB hydra_lite\hydra_lite_baseline.py -NameA S1 -NameB S2 -Adapter persistent -Elo0 -3 -Elo1 3
```
**Pass:** H0 accepted, zero forfeits/crashes. **On failure:** H1 or forfeits ⇒ the harness (TC, concurrency, machine load) is broken — investigate `tools/ca_uci_persistent.py` timing and machine load; do NOT proceed to S1.

---

### S1 `[ ]` A1 acceptance — SPRT the already-implemented incremental eval · *user-run + Small for bookkeeping*

**State:** A1 is already in `hydra_lite.py` (1.58× node rate, evalp provably unchanged). The 2026-06-07 SPRT attempts were void (forfeits). This step just re-tests it cleanly.

**Before the run (agent, once):** archive the live submission so block-level comparisons keep a fixed anchor:
```powershell
Copy-Item hydra_lite\hydra_lite_baseline.py hydra_lite\hydra_lite_v10_live.py
```

**User runs:**
```powershell
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_baseline.py -NameA A1 -NameB base -Adapter persistent
```
**Pass:** H1 ⇒ acceptance procedure (§3.1).
**On failure (H0/rejected, zero forfeits):** the speedup didn't convert. Most likely cause: A1 changed *pruning behavior* — `ab()` now feeds RFP/null/futility a material+PST-only `static` where v1.0 used the full `evalp()` (missing ~mobility/pawn-structure terms ⇒ margins effectively tighter). Recovery ladder, one SPRT each: (1) widen `RFP_MARGIN` 90→130 and `FP_MARGIN` 160→200 (compensates the missing terms); (2) if still rejected, in `ab()` use `static=evalp(p)` again but **keep** the `p.score` infrastructure (S7 needs it), and re-SPRT — the win then comes from S2 instead. Log whichever branch ran in §8.

---

### S2 `[ ]` A2 — kill per-node legality (lazy legality in search) · *Tier: **Large***

**The single biggest lever left.** Today `ab()` and `q()` call `legal()`, which does make+`incheck`+unmake for **every pseudo move** at **every node** — even moves that are never searched because of a beta cutoff. Replace with: generate **pseudo** moves, and after `make`, skip the move if the mover left their king in check. Cost per *searched* move: one `incheck` on a position we had to make anyway. Cut-nodes stop paying for the 25 moves they never try.

**Files:** `hydra_lite/hydra_lite.py` only (functions `ab` and `q` inside `search()`). `legal()` itself stays — root, `parseuci`, perft and the final fallback still use it.

**Recipe — `ab()` (currently `ms=legal(p)` ... see the loop near `hydra_lite.py:335-361`):**

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

The five load-bearing details — get each one right:
1. **`incheck(p, not p.w)` after `make`**: `make` flips `p.w`, so `not p.w` is the side that just moved. If their king is attacked, the move was illegal → `unmake` + `continue`.
2. **`cnt` now counts *legal* moves only**, incremented after the legality check. This keeps PVS (`cnt>1` ⇒ null-window) and LMR (`cnt>1`) semantics: first *legal* move gets the full window.
3. **Futility skip is guarded by `cnt>0`** (at least one legal move already played). This is what keeps mate/stalemate detection *exact*: if the loop ends with `cnt==0`, every pseudo move was actually made and refuted as illegal, so `return -MATE+ply if inc else 0` is correct.
4. The rep-counter bookkeeping (`k=key(p); rep[k]+=1 ... finally: rep[k]-=1; unmake`) moves *inside* the legal branch — an illegal move must not touch `rep` (its unmake happens before the try block).
5. Everything else in the loop body — PVS/LMR re-search ladder, killer/history update, TT `store` on cutoff — is unchanged.

**Recipe — `q()` (currently `ms=legal(p,True)`):** same transformation, simpler: `ms=pseudo(p,True)`; after `u=make(p,m)`, `if incheck(p,not p.w): unmake(p,u); continue`; then the rep/try/finally body unchanged. No `cnt` needed (qsearch has stand-pat, no mate claims).

**Do NOT touch:** the root loop in `search()` (keeps `legal(p)` — root legality must be exact), the `incheck` null-move guard, the check-extension `inc` logic, `pseudo()`'s castling checks (they already verify transit squares — castling moves arriving from `pseudo()` are fully legal except for the post-move check the new test catches anyway).

**Why this is already safe-by-construction:** TT/killer moves that are illegal in the current node simply get made, detected, skipped. En-passant discovered check (the classic horizontal-pin trap) is caught because `incheck` runs *after* `make` removed both pawns.

**Self-checks (all must pass):**
1. *Add two tests first* (in `tests/test_lite_agent.py`, pattern-match the existing ones): `test_mate_in_one` — engine output must be the mating move: FEN `6k1/5ppp/8/8/8/8/8/4K2R w K - 0 1` → expect `h1h8`; FEN `R6k/6pp/8/8/8/8/8/4K3 b - - 0 1` (Black to move, mated-in-0 is not it — use instead `7k/5Q2/5K2/8/8/8/8/8 w - - 0 1` → expect `f7g7`). Verify each FEN/answer with the engine *before* relying on it; if the engine pre-change fails them, fix the test position, not the engine.
2. `pytest tests/test_lite_agent.py -q` → all pass (perft is the movegen gate; legality/mate tests are the search gate).
3. `tools/noderate.py` → expect **avg ≥ 100k NPS, midgame ≥ 55k** (from 66k/31k). If avg < 85k, stop — profile where `attacked()` calls remain (mscore still has one until S3) and report before any SPRT.

**Strength gate:** persistent gainer SPRT (template §4.3). Expect clearly positive.
**On failure:** H0 with zero forfeits ⇒ revert (`git restore hydra_lite/hydra_lite.py`, remove nothing from tests — the mate tests stay) and report; the thesis of the whole plan is then in question, so STOP and re-plan with the user.
**Size:** roughly neutral (≤ +0.3KB).

---

### S3 `[ ]` A3 — drop `attacked()` from move ordering · *Tier: Small*

**What:** `mscore()` (`hydra_lite.py:265-277`) burns an `attacked()` call per capture for a crude "bad capture" penalty:
```python
if c!="." and VAL.get(c,0)+80<VAL.get(a,0) and attacked(p,to,not p.w): s-=550
```
**Recipe:** delete exactly that line. Ordering becomes pure MVV-LVA + promo + killers + history. (Real SEE arrives in S8 and does this job properly.)
**Self-checks:** tests pass; `noderate.py` — attacked/s drops, NPS up (record numbers).
**Strength gate:** persistent SPRT, **`-Mode simplify`** (this trades a bit of ordering quality for speed; elo ≥ 0 keeps the cut).
**On failure:** H0 ⇒ restore the line but try the cheap variant `... and a in "QR" ...` (penalty only for heavy attackers, fewer `attacked` calls) and re-SPRT once; if that also fails, restore original and mark `[R]`.

---

### S4 `[ ]` A5 — fix the TT wipe-on-overflow · *Tier: Small*

**What:** `store()` inside `search()` (`hydra_lite.py:295-297`) does `if len(TT)>TT_MAX_ENTRIES: TT.clear()` — at post-S2 speeds a single 4.3s search overflows 25k entries and **wipes the whole table mid-search**, repeatedly.
**Recipe:**
1. Replace the body of `store` with:
   ```python
   def store(h,d,v,fl,bm):
       if h in TT or len(TT)<TT_MAX_ENTRIES: TT[h]=(d,v,fl,bm)
   ```
   (existing keys always update; new keys only while under the cap — never wipe, bounded memory).
2. Set `TT_MAX_ENTRIES=300000` (≈ 60–90MB worst case, comfortably under 256MB for one search).
3. Update `tools/ca_uci_persistent.py::_SPIN_OPTIONS["TT_MAX_ENTRIES"]` to `(300000, 1000, 1000000)`.
**Self-checks:** tests pass; `noderate.py` no regression (likely a gain at depth).
**Strength gate:** persistent gainer SPRT. **On failure:** H0 ⇒ keep the no-wipe scheme but try `TT_MAX_ENTRIES=100000` once (memory pressure hypothesis); then revert if still H0.
**Size:** −bytes.

---

### S5 `[ ]` A4 — eval speed pass (passed-pawn scan) · *Tier: Small*

**What:** the passed-pawn test inside `evalp()` (`hydra_lite.py:236-239`) loops over **all 64 squares for every pawn**. Replace with per-file extremes computed once per call. **This is a pure refactor — evalp must return bit-identical values.**

**Recipe:**
1. Snapshot first: `Copy-Item hydra_lite\hydra_lite.py tmp_eval_ref.py`.
2. In `evalp`'s first pass (where `pawns[16]` is filled), also build:
   - `bmax[f]` = highest rank of any black pawn on file `f`, else `-1`
   - `wmin[f]` = lowest rank of any white pawn on file `f`, else `8`
3. Replace the inner 64-square loop: a **white** pawn at rank `r`, file `f` is passed iff `bmax[ff] <= r` for every `ff in (f-1, f, f+1)` that's on the board; a **black** pawn iff `wmin[ff] >= r` likewise. (Same semantics as the old code: only *strictly ahead* pawns on the three files block.)
4. Verify: `& .venv\Scripts\python.exe tools/eval_equiv.py --ref tmp_eval_ref.py --new hydra_lite/hydra_lite.py` → must print PASS. Then delete `tmp_eval_ref.py`.
**Self-checks:** eval_equiv PASS; tests pass; `noderate.py` — tactical/midgame eval/s up.
**Strength gate:** persistent gainer SPRT (pure speed at fixed time ⇒ should be positive; weak-positive is fine, pair it with S4's run if the user prefers one combined SPRT — note it in §8 either way).
**On failure:** eval_equiv FAIL ⇒ your rank/file logic is off (remember rank = `i>>3`, white moves toward rank 7) — fix before anything else.

---

### S6 `[ ]` Block-1 gate — cold-spawn confirmation + upload · *user-run*

**Precondition:** S1–S5 resolved (accepted or consciously rejected), node rate ≥ 100k avg.
**User runs** the deployment-exact confirmation vs the archived live version:
```powershell
.\tools\sprt_lite.ps1 -EngineA hydra_lite\hydra_lite.py -EngineB hydra_lite\hydra_lite_v10_live.py -NameA block1 -NameB v10 -Adapter coldspawn
```
**Expect:** fast, strongly positive (the thesis predicts triple digits — fastchess will stop early). Zero timeouts is mandatory (this run also validates `SEARCH_TIME=4.3` under cold-spawn; if any timeout appears, lower `SEARCH_TIME` to 4.2 and re-run).
**Then:** upload `hydra_lite/hydra_lite.py` to https://chessagents.ai/, record the new live Elo/W-D-L in §8 after ~a day. The leaderboard is the north star — if local SPRTs and the board disagree badly, our test conditions are off; fix the harness, not the engine.

---

### S7 `[ ]` E1 — tapered PeSTO evaluation · *Tier: **Large***

**What:** replace the single crude PST + KMG/KEG with PeSTO's 12 tables (6 pieces × MG/EG) and MG/EG piece values, interpolated by incremental game phase. This is the classic biggest eval upgrade; it rides on A1's incremental machinery.

**Recipe:**
1. **Tables.** Fetch the exact values from https://www.chessprogramming.org/PeSTO%27s_Evaluation_Function (the `mg_*_table`/`eg_*_table` C arrays and `mg_value`/`eg_value`). Transcribe a1=0 orientation to match `_ps()`'s `sq^56` convention — PeSTO's arrays are a8-first, ours index a1-first for White, so **reuse the existing `si = sq if w else sq^56` flip but verify against known cells** (e.g. PeSTO mg pawn on e4 vs e2). Do not write tables from memory without the checks in step 4.
2. **Representation.** `p.score` becomes two accumulators: simplest is to keep ONE `p.score` but store `(mg<<20) + eg`-style packing — **do not**; keep it readable: add slots `mg`, `eg`, `ph` to `P`, update all three in `__init__`/`make`/`unmake` exactly where `score` is updated today (`_ps` returns an `(mg, eg)` pair or two parallel helpers). Phase weights: N=B=1, R=2, Q=4, capped at 24.
3. **Eval.** In `evalp`/`ab`-static: `base = (p.mg*ph + p.eg*(24-ph)) // 24` with `ph = min(p.ph, 24)`, white-perspective. Keep these hand-crafted terms on top: passed/isolated/doubled pawns, rook (semi-)open file, bishop pair, mobility, king pawn-shield. **Drop**: `center()` bonuses, the `rr*10` pawn advance, the crude `phase>2200`/`<1800` branches (PeSTO covers placement and tapering). Delete `KMG`/`KEG`/old `PST`/`VAL`-as-eval (keep a piece-value dict for MVV-LVA ordering and qsearch delta — ordering can keep the old `VAL`).
4. **Update tests in the same step** (they encode the old representation): rewrite `_mat_pst_scratch()` to recompute `(mg, eg, ph)` from scratch and assert all three against the incremental values; add `test_eval_startpos_zero` (startpos must eval to exactly 0 — catches asymmetric transcription); add `test_eval_mirror` — for each FEN in the perft list, evaluating the color-flipped position (swap piece case, mirror ranks, flip side/castling) must give the exact negation (catches `^56` indexing bugs); assert all 12 tables have length 64.
5. `SEARCH_TIME`, search constants untouched.
**Self-checks:** the new tests + full suite; `eval_equiv` is N/A (values are *supposed* to change); `noderate.py` — small slowdown acceptable (≤ 10%).
**Strength gate:** persistent gainer SPRT. Expect solidly positive at post-S2 depth.
**On failure:** H0 ⇒ first suspect tables/indexing despite tests (spot-check 5 random cells against the source), then try keeping the old pawn-structure weights halved (PeSTO already encodes advance); one retry max, then revert and log.
**Size:** ~+3KB (tables).

---

### S8 `[ ]` E2 — real SEE (static exchange evaluation) · *Tier: **Large***

**What:** a proper swap-off evaluator replacing the heuristic S3 deleted. Used in (a) qsearch: skip captures with `see(p,m) < 0`; (b) ordering: bad captures behind quiets.
**Recipe sketch:** classic gain-array swap algorithm on the target square: collect least-valuable-attacker iteratively using existing ray walks (write a dedicated `lva(p, sq, side, occ_removed)` helper rather than bending `attacked()`); include x-rays for sliders along the capture line; en-passant and promotions may bail out conservatively (treat as always-try). Unit tests first, with hand-verified vectors, e.g.: `1k1r4/1pp4p/p7/4p3/8/P5P1/1PP4P/2K1R3 w - - 0 1`, `e1e5` → SEE = +100 (RxP, rook recaptures... verify by hand when writing the test); simple QxP-defended → −800; equal trade → 0. **Write and hand-check 4–6 vectors before implementing.**
**Self-checks:** SEE unit tests; full suite; noderate (qsearch shrinks ⇒ NPS may *drop* while depth rises — judge by SPRT, not NPS).
**Strength gate:** persistent gainer SPRT. **On failure:** revert; qsearch delta-pruning already covers part of this — log and move on.
**Size:** ~+1KB.

---

### S9 `[ ]` B1 — opening book expansion + `BOOK_PLY` fix · *Tier: Small*

**What:** today `book()` is only consulted while `len(hist) < BOOK_PLY` (=8), but the line-table goes 12 plies deep — **plies 9–12 are dead code**. Also ~28KB of size budget is unused; a deeper book saves clock where search helps least.
**Recipe:** (1) set `BOOK_PLY` to (longest line length) and make `book()`'s `hist[:12]` slice use `BOOK_PLY` too; (2) extend the long-line block `L` with main lines to ~16 plies for the openings already present (Ruy, Italian, Sicilian Najdorf/classical, French, Caro-Kann, QGD, QGA, Slav, KID, Nimzo, English, London vs ...; both colors); aim +5–10KB, keep every line a real mainline from memory of master praxis — **every move must pass `test_book_move_legal`**, which replays lines; (3) bump `_SPIN_OPTIONS["BOOK_PLY"]` max if needed.
**Self-checks:** `test_book_move_legal` (extend its parametrization to cover new lines / longer prefixes); full suite; size check.
**Strength gate:** persistent SPRT book-on vs book-off is noisy at st=0.7 (openings come from the match book anyway) — instead validate by **cold-spawn smoke** (20 games, zero illegal/timeout) and accept on correctness; the real test is the live board.
**Size:** +5–10KB (budget to ~32KB total).

---

### S10 `[ ]` E4 — attack-based king safety · *Tier: **Large***

Attacker count/weights into the 8-square king zone (use existing ray walks; weight N/B=2, R=3, Q=5; scale quadratically by attacker count, MG-weighted via `ph`), replacing/augmenting the bare pawn-shield count. Judgment-heavy: design freely, SPRT decides. Persistent gainer SPRT; revert on H0. ~+1–2KB.

### S11 `[ ]` E5 — threats & positional dribs · *Tier: **Large***

Rook on 7th, knight outposts (already partial), pawn threats on pieces, tempo bonus. One SPRT for the bundle; on H0, bisect once (halve the bundle), then keep/revert. ~+1KB.

### S12 `[ ]` T — time-budget re-validation · *user-run, Small bookkeeping*

After the speed work changes timing: cold-spawn 20-game smoke at defaults; require zero timeouts with `SEARCH_TIME=4.3`. If max move wall-time has > 0.5s headroom vs 5.0s, try 4.5 and re-smoke; SPRT not needed (monotone more-time-is-better), but the smoke must be clean.

### S13 `[ ]` Final upload checklist · *any model*

```powershell
& .venv\Scripts\python.exe -m py_compile hydra_lite\hydra_lite.py
(Get-Item hydra_lite\hydra_lite.py).Length          # < 50000
& .venv\Scripts\python.exe -m pytest tests/test_lite_agent.py -q
# cold-spawn smoke: 20 games, zero illegal/crash/timeout, then upload + record live Elo in §8
```
Minify only if a feature would otherwise bust the cap; keep the readable source in git.

---

## 6. Keep/cut audit (opportunistic — run when a machine is idle)

Full-Hydra habits that may not pay at lite's operating point. Each is one `-Mode simplify` SPRT: **H1 (≥ 0 Elo without it) ⇒ cut it** — the bytes and ns are the win. *Tier: Large for the judgment, Small for the mechanical edit.*

| Candidate | Edit to test | Note |
|---|---|---|
| Aspiration-window widening loop (`search()` root, the `alpha/beta/window` dance) | replace with plain full-window `(-MATE, MATE)` per iteration | shallow noisy scores ⇒ re-searches may cost more than the narrow window saves |
| Separate root move loop duplicating `ab` | make root call `ab` directly (PVS root) | bytes + drift risk; weaker root ordering today |
| LMR aggressiveness (`LMR_DEPTH=2`) | try 1 | at ~10 ply, 2 may over-reduce |

---

## 7. Backlog (only after S1–S13 are banked)

- **X1 — staged move generation**: emit captures first (ordered by MVV-LVA at generation), quiets lazily after — avoids sorting full lists at cut-nodes. Medium effort, do after S8.
- **X2 — bitboard attack generation** (static literal tables only — *no* magic construction at startup): only if post-S6 profiling shows movegen still dominant; must win an SPRT, expect to revert.
- **X3 — SPSA tuning** of search constants via weather-factory (`D:\code\basilisk\tools\weather-factory\`, configs in `tools/spsa/`), persistent adapter, one group per run; SPSA proposes, SPRT decides. Then **Texel-tune** eval weights (label positions with the full `hydra/` package engine in this repo).
- **X4 — platform module probe** (`tools/probe_modules.py` as a throwaway submission) — only if a step ever wants a module beyond `sys/time/math/random` (`time` is already proven live).

---

## 8. Results log (append-only — newest last)

| Date | Step | Result | Decision / numbers |
|---|---|---|---|
| 2026-06-05 | — | baseline frozen (`hydra_lite_baseline.py`) | = live v1.0, Elo 808 (1/12/431) |
| 2026-06-06 | A0 | `tools/noderate.py` landed | v1.0 reference: avg 42k NPS, midgame 25k |
| 2026-06-06 | A1 | implemented + guardrail tests (49 pass) | evalp identical; node rate sample 63k vs 46k direct |
| 2026-06-07 | A1 SPRT | **void** — time forfeits (persistent st=0.5, c8) | adapter fixed; defaults now st=0.7, c2; old `config.json` autosave deleted — never resume |
| 2026-06-10 | cleanup | hydra_full + PLAN_full + generator removed; plan rewritten (this file); `tools/eval_equiv.py` added; `GUIDE.md` added | measured: avg 66k NPS, midgame 31k (1.58×); attacked ≈ 1.06/node; 49 tests pass; 21,826 bytes |
