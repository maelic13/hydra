# Hydra Development Workflow Guide

Your single source of truth for the day-to-day loop. Full reasoning lives in
**`PLAN.md`**; this file is the checklist, the cheat-sheet, and the **"Next
action"** pointer. The two are kept in lockstep — if they disagree, `PLAN.md`
wins and the guide is stale (fix it in the same commit).

**Branch:** all work is on **`development`**. `master` only receives squashed
`Version X.Y.Z` release commits. Commit each step separately, **no co-author**.

---

## Current checkpoint

- **Engine:** Hydra v1.4.1 — Python UCI engine in `hydra/` (fully type-annotated).
- **State (2026-06-29):** Search is **feature-complete**. Eval is a **complete
  classical HCE** — but **every weight is an untuned textbook constant**, and
  there is **no harness** (no SPRT/SPSA/Texel) yet.
- **Bench anchor:** `559 253 nodes @ depth 9`, ~23.4k nps. The refactor
  fingerprint — must not change on a pure refactor.
- **Texel data:** `A:\Chess\Beast\data\txt\positions.txt` — **122.66M diverse,
  label-free FENs** (ICCF computer chess → human club). We do **not** generate
  more; we label + balance these (Phase 4.1). Also the source of the ~50k
  eval-equivalence corpus used by the refactor gates (Phase 0.6).
- **Thesis:** biggest free Elo = *tuning the complete-but-untuned eval* + *making
  CPython faster*. Build the harness, expose the knobs, speed up the interpreter,
  complete the eval structure, then fit it **once**.

## Next action

> **Phase 2 COMPLETE — ~3.2× NPS, and mypyc confirmed +184.6 ± 30.9 Elo** (SPRT
> vs pure @ 8+0.08, H1, LOS 100%). Runtime settled: **ship mypyc** (2.00× NPS);
> PyPy rejected (0.91× — slower; its JIT can't speed 64-bit-int bitboards). 2.4
> lazy eval inert; 2.7 Lazy SMP ⛔ (needs CPython 3.13t). Phase 2 ships bundled
> with **v1.5.0** (after Phase 4) — no standalone release.
>
> **Next: Phase 3 — eval structure completion (seeded inert, no games).** Add the
> terms Hydra lacks (threats package, king-safety v2, scale factors/winnable/
> rule50, passer richness, material-key/imbalance, minor positional terms), each
> **seeded to zero-effect** so bench `559253` + eval fingerprint `c4e9c6109970e676`
> stay exact — so Phase 4 fits them all in **one** Texel campaign. Start with
> **3.1 threats package** (`O-hi`).
>
> *SPRT workflow note for the campaign:* strength SPRTs can run on the compiled
> build for 2× more games/hour — build candidate + baseline with `build_mypyc.ps1`
> and SPRT compiled-vs-compiled. (Relative Elo is the same on pure; compiled is
> just faster + deployment-representative.)

Say **"start Phase 3"** (or "implement the next step in PLAN.md").

---

## The basic rhythm (ping-pong loop)

1. **Use the model named on the step** (tracker below). `Opus 4.8 high` for
   reasoning/correctness-dense steps; `Sonnet 4.6 medium` for mechanical ones. If
   you're on a weaker model for a `high` step, the agent will ask you to switch.
2. Say **"Implement the next step in PLAN.md."**
3. The agent edits, runs self-checks (tests + bench fingerprint + corpus
   equivalence), prints **one command**.
4. You run it — a `bench`/test for refactors, an SPRT (or SPSA/Texel) for
   strength steps — and paste the result back.
5. The agent banks (commit on `development`, tick the box, log §10) or reverts,
   and refreshes "Next action". **Timeouts/crashes/illegal > 0 = void run** — fix
   the harness, not the engine.

**Python advantage:** no build step in dev — fastchess runs `python -m hydra`
directly; revert is `git restore`. (The compiled *release* build, §2.6, is a
separate periodic concern.)

---

## Phase progress tracker

Legend: `[ ]` todo · `[~]` in progress / awaiting gate · `[x]` done · `[R]` reverted.
Model tags: **O-hi** = Opus 4.8 high · **O-hi+** = Opus 4.8 high, max reasoning ·
**O-med** = Opus 4.8 medium · **S-med** = Sonnet 4.6 medium · **S-lo** = Sonnet 4.6 low.

- [x] **Phase 0 — Harness + data prep** *(DONE)*
  - [x] 0.1 fastchess · [x] 0.2 launch shim (`-S` isolation verified) · [x] 0.3 `sprt.ps1`
  - [x] 0.4 SPSA driver (scaffold) · [x] 0.5 Texel tuner (smoke OK) · [x] 0.6 corpus(5000, balanced)+book(3000)+eval_equiv (`c4e9c6109970e676`)
  - [x] 0.7 **calibration healthy** — 1016 games, 48.57%, no bias, 0 crashes
- [x] **Phase 1 — Expose constants + tunable-eval refactor** *(DONE; default-equivalent, 112 tests)*
  - [x] 1.1 search constants → `engine.PARAMS` + UCI · [x] 1.2 `EvalParams` table · [x] 1.3 coefficient trace (`reconstruct_eval`, 0 mismatch/5000)
- [x] **Phase 2 — Python speed wave** *(~3.2× NPS; mypyc +184.6±30.9 Elo SPRT)* → ships with v1.5.0
  - [x] 2.1 incremental eval accumulators (1.6×) · [x] 2.2 slider attacks once (→1.75×)
  - [x] 2.6 **mypyc build** — 2.00× NPS, +184.6 Elo confirmed; PyPy rejected (0.91×)
  - [⏸] 2.3 packed TT · [⏸] 2.5 cache eviction — *deferred (not hotspots)* · [x] 2.4 lazy eval INERT
  - [ ] 2.7 **Lazy SMP** `O-hi+` — ⛔ *blocked: needs CPython 3.13t*
- [ ] **Phase 3 — Eval structure completion** *(seeded inert, no games)*
  - [ ] 3.1 threats package `O-hi` · 3.2 king-safety v2 `O-hi+` · 3.3 scale factors + winnable + rule50 `O-hi`
  - [ ] 3.4 passed-pawn richness `O-med` · 3.5 material-key table + imbalance `O-hi` · 3.6 space + bad-bishop/trapped/connected-rook `S-med`
- [ ] **Phase 4 — Texel eval data-fit campaign** *(+80–160 Elo)* → **release v1.5.0**
  - [ ] 4.1 dataset prep from positions.txt (label + quiesce-filter + phase-balance) `O-hi`
  - [ ] 4.2 staged fit: material→mobility→pawns→passers→KS→threats→scale→PST/material last `S-med` (KS/scale `O-hi`)
- [ ] **Phase 5 — Search-constant SPSA wave** *(+20–50 Elo, once, final scale)* `S-med` / review `O-med`
- [ ] **Phase 6 — Time management** *(+5–25 Elo)* → ships with **v1.6.0**
  - [ ] node-based TM + instability extension + TM SPSA + LTC `O-med`/`S-med`
- [ ] **Phase 7 — Search-efficiency refinements** *(+15–50 Elo)* → **release v1.7.0**
  - [ ] corr-hist family (non-pawn/major/minor/cont) `O-hi` · cuckoo upcoming-rep `O-hi` · history-gravity `S-med`
  - [ ] fractional LMR `O-med` · qsearch checks `S-med` · TT aging `S-med` · staged movegen `O-med`
- [ ] **Phase 8 — Eval-refresh cycles** *(+10–30, diminishing)* `S-med` → roll into v1.7.x
- [ ] **Phase 9 — NNUE** *(terminal; Python-inference is the design problem)* → **release v2.0.0** `O-hi+`

### Release checkpoints (don't forget these)

At each release the **agent** bumps `pyproject.toml`, runs suite+bench+a final
SPRT vs the previous release, updates `CHANGELOG.md`/§10/guide, commits, and says
**"ready to release vX.Y.Z."** Then **you**: squash all `development` commits
since the last release into one **`Version X.Y.Z`** commit → cherry-pick onto
`master` → push → ask the agent for **release notes** → create the GitHub release
(attach the compiled executables) → reset `development` onto the new `master`.

- [ ] **v1.5.0** — after Phase 4 (Phase 2 speed/compiled build **+** tuned eval — major jump)
- [ ] **v1.6.0** — after Phases 5 + 6 (tuned search + TM)
- [ ] **v1.7.0** — after Phase 7 (+8) (search refinements + refresh maturity)
- [ ] **v2.0.0** — after Phase 9 (NNUE)

*(Phase 2 is speed-only → no standalone release; it ships bundled with v1.5.0.)*

---

## Common commands

```powershell
# Tests
& .venv\Scripts\python.exe -m pytest -q

# Bench fingerprint (must equal 559253 @ depth 9 on a pure refactor)
"bench 9`nquit" | & .venv\Scripts\python.exe -m hydra

# SPRT a candidate (gate TC = clock 8+0.08); Phase 0.3 builds sprt.ps1
.\tools\sprt.ps1 -EngineA <cand> -EngineB <baseline> -TC "8+0.08" -Concurrency <cores-1>

# Calibration — must accept H0 (~0 Elo, zero forfeits)
.\tools\sprt.ps1 -EngineA <baseline> -EngineB <baseline> -Elo0 -3 -Elo1 3

# SPSA (needs Phase 1 options) / Texel fit (offline, may use numpy)
& .venv\Scripts\python.exe tools\spsa\tune.py
& .venv\Scripts\python.exe tools\texel\tune.py --stage <name>

# Profile a hot path (Phase 2): run, then type `bench 9` then `quit`
& .venv\Scripts\python.exe -m cProfile -s tottime -m hydra
```

## What to report back after a run

```text
games=...  score%=...  elo=...±...  LOS=...  sprt=accept-H1|accept-H0|continue
timeouts=...  crashes=...  illegal=...  TC=...  notes=...
```
Any run with `timeouts/crashes/illegal > 0` is **void** — fix the harness first.

---

## Ground rules (short version)

- **One change per step, in order. SPRT decides — Texel/SPSA only propose.**
- **Use the model tagged on the step.**
- **Default-equivalence before tuning:** refactors keep the bench fingerprint
  *and* the eval-corpus output identical.
- **Build all eval structure first (seeded inert), then fit once.** Don't tune,
  add a term, re-tune — that wastes self-play games (the conserved resource in
  CPython). Texel is the cheap inner loop; SPSA/SPRT games are not.
- **Same TC for tuning and the confirming gate** (currently `8+0.08`).
- **Update `PLAN.md` + this guide in the same commit as the code**; refresh
  "Next action" every time.
- **Commit each kept step separately on `development`, no co-author.**
- **Keep release UCI clean:** tuning knobs stay behind the `Tune` flag.
- The eval boundary stays clean (`Evaluator.evaluate(board)`) so Phase 9 NNUE
  stays possible.
