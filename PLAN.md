# Hydra Strength Improvement Plan

**The one goal:** make Hydra — the UCI chess engine in `hydra/` — as strong as
possible *as a Python engine*. This is the master plan; the user-facing
checklist and command cheat-sheet live in `user_dev_guide.md` — **keep the two
in lockstep, in the same commit, every step** (§1 rule 8).

Modeled on the sibling engines `D:\code\rarog` (Rust) and `D:\code\basilisk`
(C++) — same gate discipline, same "build structure first, tune once"
sequencing — but **specialized for Python**: the levers, the ordering, and the
NPS economics are different when the engine is interpreted CPython at ~23k NPS
instead of compiled at ~5M NPS.

---

## 0. Current state audit (2026-06-29)

### What Hydra already is

Hydra is **not** a weak or skeletal engine. Its *feature set* already rivals the
sibling C++/Rust engines. The gap is **tuning and speed, not features.**

**Search (`hydra/engine.py`, 1537 lines) — essentially complete:**
PVS + iterative deepening + aspiration windows · transposition table
(mate-adjusted) · null-move pruning (dynamic reduction) · LMR (log table +
improving + cont-hist adjustment + PV) · reverse futility / static null ·
razoring · futility pruning · late-move pruning (improving asymmetry) · history
pruning · SEE pruning (qsearch + main) · ProbCut · singular extensions (+ double
extension + multicut + negative extension) · internal iterative reduction ·
correction history (pawn-hash keyed) · mate-distance pruning · check extension ·
Syzygy TB probing · soft/hard time management with best-move-stability scaling ·
history aging between searches.

Move ordering: TT → queen-promo → SEE-ordered good captures + capture-history →
killers → countermove → quiet history + continuation history (1-ply + 2-ply) →
bad captures.

**Eval (`hydra/evaluation.py`, 813 lines) — complete classical HCE:**
material + PST (tapered MG/EG) · pawn structure (doubled, isolated, connected,
backward, passed) · bishop pair · rook open/semi-open/7th/behind-passed-pawn ·
per-count mobility tables (safe squares) for N/B/R/Q · knight outposts · pawn
threats · king safety (attack-unit count + pawn shield) · endgame king
centralization + king-to-passer proximity · tempo. Pawn-structure cache +
full-eval cache (keyed by board hash).

**Infrastructure:** bitboards + mailbox + magic sliding attacks; make/unmake with
history stack (incremental Zobrist); full UCI with threaded search, ponder,
infinite; Syzygy via bundled Fathom; `bench` node-count fingerprint.
Version 1.4.1. No runtime package dependencies.

### The three real gaps (this plan attacks them in Elo order, dependency-respecting)

1. **Zero tuning.** Every weight is a hand-set textbook constant — the PSTs are
   the Michniewski *Simplified Evaluation Function* tables, material is
   `100/320/330/500/900`, every margin/bonus is a round number. **Nothing has
   ever been Texel-fit or SPSA-tuned.** A complete-but-untuned eval is the single
   biggest pool of free Elo in the whole project (sibling engines gained
   +80–160 from their eval data-fit alone). There is also **no UCI exposure** of
   any tunable constant, so neither Texel nor SPSA can even be run yet.

2. **No harness.** There is no fastchess runner, no SPRT script, no SPSA driver,
   no Texel tuner, no labelled dataset, no opening book wired in. (`tools/spsa`
   and `tools/results` are stale artifacts from the now-removed *lite* line —
   treat them as reference only.) Nothing can be measured or tuned until this
   exists. This is Phase 0.

3. **Speed: ~23k NPS in CPython** (bench depth 9 = **559 253 nodes**, ~23.4k
   nps on the dev box — the fingerprint anchor). The eval is recomputed from
   scratch every node (then hash-cached); the TT allocates a Python object per
   store; sliding attacks are recomputed up to 3× per eval. In an interpreted
   engine NPS *is* playing strength: at a fixed clock, +1 effective ply ≈
   +40–70 Elo. So unlike a compiled engine, **speed work here is real Elo, not
   just convenience** — and it makes every later SPRT/SPSA/datagen run cheaper.

### Honest expectation (estimates; SPRT is the only verdict; gains overlap)

| Phase | Work | Expected Elo |
|---|---|---|
| 0 | Harness | 0 (enabler) |
| 1 | Expose constants + tunable-eval refactor (default-equivalent) | 0 (enabler) |
| **2** | **Python speed wave** (incremental eval, lazy eval, TT packing) | **+30–80** (real, via deeper search at a fixed TC) |
| 3 | Eval structure completion (seeded inert) | 0 direct (enabler for one-shot Texel) |
| **4** | **Texel eval data-fit campaign** (the multiplier) | **+80–160** |
| **5** | **Search-constant SPSA wave** (once, at final eval scale) | **+20–50** |
| 6 | Time-management hardening + tuning | +5–25 (clock TCs) |
| 7 | Search-efficiency refinements | +10–40 |
| 8 | Eval-refresh cycles (non-NNUE ceiling) | +10–30 (diminishing) |
| 9 | NNUE (terminal option) | +200–600, but Python-inference is the hard problem |

---

## 1. Non-negotiable gates (apply to every phase)

1. **SPRT-gate every strength change.** Default bound `elo0=0 elo1=5
   alpha=0.05 beta=0.05`; tighten to `elo1=3` for small single features. A pass
   = "≥0 Elo with 95% confidence." Nothing is "good" until SPRT says so.
2. **One change at a time.** Never bundle features. Port/implement one, gate it,
   keep or revert, commit, move on.
3. **Texel/SPSA propose; SPRT decides.** A tuned value set is only a *candidate*
   until it survives a game gate. Lower training loss that fails SPRT is
   overfitting — revert it.
4. **Default-equivalence first.** Every refactor that introduces a struct/option
   must reproduce current behaviour exactly: the `bench` fingerprint
   (**559 253 nodes @ depth 9**, baseline 2026-06-29) must be **identical**
   before tuning begins. Record a fresh anchor whenever behaviour intentionally
   changes.
5. **Tune and gate at the *same* time control.** The SPSA/Texel-confirm TC and
   the SPRT TC must match, or you tune under one condition and judge under
   another. Default gate TC is set in Phase 0 (proposed **`tc=8+0.08`**, clock,
   not fixed movetime — a clock exercises time management and generalizes).
   Add an LTC confirmation at phase boundaries and for TC-suspect features.
6. **`bench` is the refactor fingerprint, not an Elo proxy.** Pure refactors:
   fingerprint must match exactly. Tuned/behaviour changes: record the new
   number, never read Elo into it.
7. **Preserve the eval boundary.** Search calls `Evaluator.evaluate(board)`;
   do not leak eval internals into search. This keeps the Texel campaign
   tractable and keeps the NNUE door open (Phase 9).
8. **Update `PLAN.md` and `user_dev_guide.md` in lockstep — same commit, every
   step.** Statuses, the §10 results log, measured numbers, and the guide's
   "Next action" pointer. A stale guide breaks the loop. This is the most
   commonly skipped rule; treat it as mandatory.
9. **Commit each kept step separately, no co-author.** Descriptive message; one
   feature per commit for surgical revert. (User standing instruction: omit the
   `Co-Authored-By` trailer on this project.)
10. **Review tuned constants before baking.** After SPSA/Texel, check every
    value against its bounds and re-read the code it feeds. A value pinned at a
    bound or driven to a no-op is a signal to inspect the implementation, not to
    bake blindly.

### The Python advantage — no build step

Rarog/Basilisk must compile a PGO test binary before every SPRT. **Hydra does
not.** fastchess runs `python -m hydra` (or the source tree) directly, so a
candidate is testable the instant it is edited and a revert is `git restore`.
Iteration is faster than the compiled siblings — spend the saved time on more
games per gate, not on builds.

---

## 2. Sequencing principle — build structure first, tune once (READ THIS)

There are three kinds of tuning, with very different costs:

- **Texel weight-fitting** — a gradient fit over a fixed labelled dataset.
  Minutes of offline CPU, **zero games**. Cheap to repeat; it is the per-feature
  inner loop, **not** a conserved resource.
- **SPSA** (search-constant tuning) and **SPRT** game gates — **thousands of
  self-play games each**. In CPython these are *expensive* (slow NPS → slow
  games). These are the conserved resource.

Search margins (RFP, razoring, futility, delta, history-pruning thresholds,
parts of LMR/NMP) are denominated in **eval centipawns**. Re-fitting the eval
changes what a centipawn means, so any SPSA wave run *before* the eval is final
is thrown away. Therefore the order is forced:

1. **Build all eval structure first**, each new sub-term **seeded inert**
   (zero-effect) or **linear-equivalent** to what it replaces, so `bench` is
   unchanged and the gate is the fingerprint + reconstruction test — **no games**.
2. **Fit the whole enlarged eval once** (one staged Texel campaign; biggest lever
   first, PSTs + material last), not two campaigns.
3. **Run the one search-constant SPSA wave last**, at the final centipawn scale.
4. **Speed work is behaviour-identical** → it invalidates no tuning and may run
   any time, but is placed **early (Phase 2)** because in CPython faster NPS is
   both real Elo *and* a cheaper everything-after (datagen, every SPRT/SPSA).

> By raw "most Elo" the Texel campaign (Phase 4) ranks first. But it depends on
> the harness (0), tunable exposure (1), and — to be done *once* — the full eval
> structure (3). Texel is cheap to repeat, so we accept it landing mid-plan and
> conserve the expensive resource (self-play games) instead. This is exactly the
> lesson the sibling engines paid for; we adopt it up front.

### Execution order

| Phase | Role | Gate |
|---|---|---|
| **0** | Harness: fastchess + SPRT + SPSA driver + Texel tuner + dataset + book | calibration H0 reproduces |
| **1** | Expose search constants (UCI) + refactor eval weights to a tunable table | bench-identical |
| **2** | Python speed wave (incremental eval, lazy eval, TT packing, attack-map reuse) | bench-identical parts no games; lazy eval SPRT-gated |
| **3** | Eval structure completion (threats v2, king-safety v2, scale factors/EG knowledge, passer richness, imbalance) — all seeded inert | bench-identical |
| **4** | Texel eval data-fit campaign (staged, biggest lever first, PST/material last) | per-stage SPRT |
| **5** | Search-constant SPSA wave (once, final scale) | confirming SPRT |
| **6** | Time-management hardening + TM SPSA + clock-TC validation | SPRT (incl. LTC) |
| **7** | Search-efficiency refinements (history formula, fractional LMR, qsearch checks, TT aging, non-pawn corr-hist, …) | per-feature SPRT |
| **8** | Eval-refresh cycles (regen data with stronger head, refit) — non-NNUE ceiling | per-cycle SPRT |
| **9** | NNUE (terminal option; Python-inference is the design problem) | SPRT vs HCE head |

---

## 3. Phase 0 — Harness (prerequisite; do this first)

**Goal:** one-command SPRT self-play, an SPSA loop, a Texel tuner, a dataset
pipeline, and an opening book — all driving `python -m hydra` directly. Nothing
else proceeds until calibration (engine vs identical engine) reproduces the
expected ≈0-Elo H0.

### Steps

- **0.1 Match runner.** Install [fastchess](https://github.com/Disservin/fastchess)
  to `tools/bin/fastchess.exe`. fastchess speaks UCI to `python -m hydra`. (No
  SPSA built in — that is 0.4.)
- **0.2 Engine launch shim.** A tiny wrapper so fastchess can start the engine
  with a chosen `Hash`/options and a chosen Python (CPython now; PyPy later, see
  §5 Phase 2 experiment). Verify `uci`/`isready`/`go`/`bestmove`/`stop` round-trip
  cleanly under fastchess (the lite line hit forfeit bugs from a bad adapter —
  prove zero forfeits before trusting any number).
- **0.3 `tools/sprt.ps1`.** Wraps fastchess SPRT: args `-EngineA -EngineB
  -TC -Concurrency -Elo0 -Elo1`, repo-local opening book, Hash 64MB, Threads 1.
  Prints the standard report line (§3.4 of the guide). Default `tc=8+0.08`.
- **0.4 SPSA driver.** Port the *lite* line's self-contained Hydra-native SPSA
  driver pattern (no external weather-factory needed): it perturbs UCI options,
  runs fastchess mini-matches, saves/resumes `tools/spsa/state.json`. Requires
  Phase 1 UCI options to exist before it can tune anything.
- **0.5 Texel tuner (offline dev tool — may use numpy).** A standalone script
  that loads labelled FENs, runs Hydra's eval-coefficient trace (Phase 1.3) per
  position, and does gradient descent on the weight vector. **The engine stays
  stdlib-only; the *tuner* is a dev tool and may import numpy/scipy** for a fast
  vectorized gradient. This is a key Python lever: the offline fit is where heavy
  math is allowed.
- **0.6 Dataset + book.** Pick a diverse opening book (e.g. a 4-move
  `SuperGM`-style PGN/EPD) for both match variety and datagen seeds. Decide the
  labelled-data source for Phase 4 (self-play datagen vs public set) — finalize
  in Phase 4, but stub the pipeline now.
- **0.7 Calibration.** Engine vs byte-identical engine SPRT, `elo0=-3 elo1=3`:
  must accept **H0** (~0 Elo, zero forfeits/crashes/illegal moves). If H1 fires,
  the harness is broken — fix before trusting any result.

**TC decision (Python-specific).** Compiled siblings gate at `tc=3+0.03`
(~depth 16). At 23k NPS Hydra reaches far shallower depth in 3s, where its
pruning margins barely bite. Propose **`tc=8+0.08`** as the primary gate
(deeper, margins active, the lite line's validated operating point), with an
optional **fixed-nodes** pre-screen for fast reproducible signal and an LTC
confirmation at phase boundaries. Lock the exact number here and use it for
*both* SPSA and the confirming SPRT (gate rule 5).

**Done when:** `tools/sprt.ps1` runs end-to-end, calibration accepts H0 with zero
forfeits, and the SPSA/Texel scripts execute one smoke iteration each.

---

## 4. Phase 1 — Expose constants + tunable-eval refactor (default-equivalent)

**Goal:** make every constant that Phases 4/5 will tune *reachable*, without
changing behaviour. The `bench` fingerprint must stay **559 253 @ depth 9**.

- **1.1 Expose search constants as UCI spin options (TUNE-gated).** The margins
  and coefficients in `engine.py`: `ASPIRATION_WINDOW`, `_REVERSE_FUTILITY_MARGIN`,
  `_RAZORING_MARGIN`, `_FUTILITY_MARGIN`, `_DELTA_MARGIN`, `_LMP_BASE`, NMP base
  reduction + divisor, LMR `log`-formula coefficients (the `0.5` / `1.6` in the
  `_LMR` table build), history-pruning thresholds, SEE-pruning depth multipliers,
  ProbCut margin, singular-extension margins/depths. Read them from a module-level
  params object that defaults to today's values. Keep them behind a `Tune` flag so
  release UCI stays clean. **Gate:** bench-identical.
- **1.2 Refactor eval weights into a tunable `EvalParams` table
  (default-equivalent — the big infra step).** Move all of `evaluation.py`'s
  magic numbers (piece values, every PST entry, all bonuses/penalties, mobility
  tables, king-safety weights, the king-safety quadratic) behind a parameter
  object whose defaults reproduce the current values bit-for-bit. Provide a
  loader (read weights from a file/UCI) used only at tune time; releases run the
  baked defaults (gate rule 9). **Gate:** bench-identical + a reconstruction test
  (eval(board) equal for a corpus of FENs before/after).
- **1.3 Eval-coefficient trace.** Add a tune-only mode where `evaluate` also
  returns, per position, the **coefficient vector** (how many times each weight
  is applied, MG and EG, with the phase blend) — this is what the Texel gradient
  needs. Verify reconstruction: `sum(coeff_i * weight_i)` tapered == `evaluate()`
  for a FEN corpus. **Gate:** reconstruction exact.

**Model note:** 1.2 is dense and correctness-critical (one wrong PST flip silently
poisons the whole campaign) → strongest model, review the diff. 1.1/1.3 are
mechanical → mid model.

---

## 5. Phase 2 — Python speed wave (the Hydra-specialized phase)

**Why here:** behaviour-identical speed never invalidates tuning, and in CPython
NPS converts to real Elo at a fixed clock *and* makes every later game cheaper.
Profile with `cProfile` before and after each step; record NPS in §10.

- **2.1 Incremental eval accumulators (behaviour-identical — the biggest NPS
  lever).** Maintain running `mg`, `eg`, `phase` accumulators on the `Board`,
  updated in `make_move`/`unmake_move` exactly where the Zobrist hash is updated,
  so the per-node material+PST loop over all pieces disappears. The *lite* line
  measured **2.6×** from exactly this. Eval output is unchanged (same tables) →
  **no re-tune**, and the Phase-4 PST refit just changes the summed values, the
  accumulator stays valid. **Gate:** bench-identical (node count same; NPS up),
  full suite green.
- **2.2 Attack-map compute-once (behaviour-identical + structure enabler).**
  `evaluate` currently recomputes sliding attacks separately for mobility and
  again for king-safety. Compute each side's per-piece attack bitboards **once**,
  reuse across mobility / king-safety / (future) threats. This is both a speed
  win and the substrate Phase 3 needs (3.x threats/KS-v2 consume attack maps).
  **Gate:** bench-identical.
- **2.3 TT packing (behaviour-identical — Python-specific).** Replace the
  object-per-entry `list[TTEntry|None]` with packed integers in a flat list (or
  `array`): one store should mutate ints in place, not allocate a `TTEntry`.
  Object churn is a real CPython cost at every store. Keep depth-preferred
  replacement semantics identical. **Gate:** bench-identical (NPS up).
- **2.4 Lazy eval (behaviour-CHANGING — SPRT-gated; the durable NPS lever).**
  Compute the cheap part (material+PST from the accumulator + pawn-cache) first;
  if it is far outside `(alpha,beta)` by a lazy margin, return it and skip
  mobility/king-safety/threats. Saves the expensive terms on most cut-nodes.
  The lazy margin is a tunable; **place the term now, confirm its margin in the
  Phase-5 SPSA** (it is cp-denominated). **Gate:** SPRT (`elo1=0`, a speed
  simplification: keep if ≥0 Elo).
- **2.5 Cache-eviction polish (behaviour-identical).** The eval/pawn caches and
  any wholesale-clear-on-full logic wipe everything periodically (same pattern as
  the lite TT bug). Switch to bounded eviction / generation tagging so a long
  search keeps useful entries. **Gate:** bench-identical.
- **2.6 PyPy evaluation — RESEARCH EXPERIMENT (the wildcard Python multiplier).**
  CPython is the NPS ceiling. PyPy typically runs this style of code **5–10×**
  faster — by far the largest single NPS lever available. Cost: it complicates
  the pyinstaller packaging and the Fathom/Syzygy `ctypes` path. **Action:**
  benchmark `bench` under PyPy, confirm correctness (perft + suite + a syzygy
  probe), and decide go/no-go on shipping a PyPy build (or a PyPy *tuning* build
  used only to make the campaign cheaper). Document the verdict in §10; do not
  let packaging block measuring the upside. Time-management constants are
  NPS-relative, so a PyPy switch re-opens Phase 6.

**Model note:** 2.1 (make/unmake correctness) → strong model + perft gate. Others
mid model. Each step independently revertible.

---

## 6. Phase 3 — Eval structure completion (seeded inert; no games)

Add the terms Hydra lacks, **all seeded to zero-effect or current-equivalent**,
so `bench` is unchanged and Phase 4 fits them in **one** campaign. Each consumes
the Phase-2.2 attack maps.

- **3.1 Threats package** (seeded inert): minor-attacks-rook/queen,
  rook-attacks-queen, hanging (undefended attacked) pieces, pawn-push threats,
  restricted squares. Hydra has only a flat pawn-threat term today.
- **3.2 King-safety v2** (seeded ≈ current): full danger model — attacker
  count × weight scaling, **safe checks** (checks on squares not defended),
  king-ring weak squares, queen-contact, no-queen attenuation, shelter/storm
  pawn terms. Replace the flat attack-unit quadratic with a structured, tunable
  danger sum whose default reproduces today's output.
- **3.3 Scale factors / endgame knowledge** (seeded scale = 1.0 — Hydra's
  biggest correctness gap; it has only insufficient-material draw detection):
  opposite-colored-bishop drawish scaling, KPK, KBNK, KRKP, KQKP, "lone-minor
  can't win", general drawish-material downscaling. A scale-factor framework
  multiplies the EG score; seeded at 1.0 it is inert until tuned/enabled.
- **3.4 Passed-pawn richness** (extend, seeded equivalent): blocker penalty,
  free-path / unsafe-path control, distance of *both* kings to the queening
  square, candidate (not-yet-)passers, connected/protected passers.
- **3.5 Material imbalance** (optional, seeded 0): pairwise piece-combination
  table (e.g. knight-pair, rook-redundancy, bishop-vs-knight by pawn count).
- **3.6 Space + small positional terms** (optional, seeded 0): space-behind-pawns
  in the centre, trapped-bishop, rook-on-closed-file, etc.

**Gate for all of Phase 3:** bench-identical fingerprint + eval reconstruction
test + full suite. No self-play games until Phase 4.

**Model note:** 3.2 and 3.3 are dense and correctness-critical → strongest model.

---

## 7. Phase 4 — Texel eval data-fit campaign (the multiplier)

**The biggest Elo pool in the plan.** Fit the whole enlarged eval **once**.

- **4.1 Dataset.** Finalize the labelled set: self-play datagen from the book
  with the current head (node- or depth-limited; label by game result, optionally
  blended with a shallow search score), extracted to train/holdout **split by
  game** (no position from one game in both splits). Reconstruction-gate the
  extraction (trace coeffs · weights == eval) before fitting.
- **4.2 Staged fit, biggest lever first, each stage SPRT-gated** (gate rules 1/3):
  1. Material (piece values, MG/EG).
  2. Mobility tables.
  3. Pawn-structure scalars (doubled/isolated/backward/connected/passed-by-rank).
  4. Passed-pawn-richness block (Phase 3.4).
  5. King-safety-v2 block (Phase 3.2) — nonlinear; may need a finite-difference
     path in the tuner.
  6. Threats block (Phase 3.1).
  7. Scale-factor / imbalance / space (Phases 3.3/3.5/3.6) if enabled.
  8. **PST + material refit LAST** (most parameters, highest overfveter risk;
     they absorb residual error from every earlier stage (highest overfitting
     risk) — fitting them first
     wastes the other stages).
- **4.3 Per-stage discipline.** Texel proposes a weight delta → bake →
  confirming SPRT at the gate TC → keep on H1, revert on clean H0. Lower holdout
  loss that fails SPRT is overfitting (gate rule 3). Re-running Texel between
  stages is cheap and expected.

**Model note:** stage-driving is mid model; the tuner-core (nonlinear KS gradient,
trace-cache format) and the KS/scale stages earn the strongest model.

---

## 8. Phase 5 — Search-constant SPSA wave (once, at final eval scale)

Now that a centipawn means its final thing, run the conserved SPSA. Group the
Phase-1.1 options and tune them together at the gate TC (== SPSA TC, rule 5):
RFP/razoring/futility/delta margins, lazy-eval margin (from 2.4), LMP base,
NMP base+divisor, LMR coefficients, history-pruning thresholds, SEE-pruning
multipliers, ProbCut margin, singular margins, aspiration window. SPSA proposes
→ review against bounds (rule 10) → one confirming SPRT decides. Expected
+20–50; clean H0 means the textbook values were already near-optimal at this
operating point (a valid, logged outcome).

---

## 9. Phases 6–9 — TM, search refinements, refresh cycles, NNUE

- **Phase 6 — Time management.** `_compute_time_limits` is sensible but its
  constants (`remaining/25`, the 0.20/0.30/0.50 hard-cap tiers, `inc*0.75`,
  the 0.06 stability scale) are hand-guessed. Harden against GUI time-losses
  (the lite line had forfeit problems), then SPSA the TM constants at clock TCs,
  with an LTC confirmation. Re-validate after any NPS-changing step (2.x, 2.6).
- **Phase 7 — Search-efficiency refinements** (each its own SPRT; Hydra already
  has most search features, so this wave is smaller than the siblings'):
  history-gravity formula upgrade; **non-pawn / material correction history**
  (the README already advertises it but `engine.py` implements only the pawn-hash
  one — close that gap); fractional/finer LMR; qsearch quiet checks at the first
  ply; TT replacement upgrade (generation/aging + maybe a 2-entry bucket, vs
  today's single depth-preferred slot); double-extension cap tuning; razoring/IIR
  depth-limit experiments; staged move generation (Python win: don't score all
  moves when the TT move cuts).
- **Phase 8 — Eval-refresh cycles.** Regenerate self-play data with the stronger
  head, refit the eval (Phase 4 machinery), 1–3 cycles, stop when a cycle no
  longer passes SPRT. Banks the "tuning maturity" Elo without new features.
- **Phase 9 — NNUE (terminal option; the real ceiling-raiser).** Keep the eval
  boundary clean (gate rule 7) so this stays possible. **The Python problem:**
  pure-Python NNUE inference (matrix mults, interpreted) is far too slow to net a
  gain at Hydra's NPS, and a numpy dependency breaks "no runtime deps." Options
  to research before committing: (a) numpy-backed inference accepting the
  dependency; (b) a deliberately tiny net (small hidden layer, int16) with
  hand-rolled vectorized accumulation and incremental updates; (c) ship NNUE only
  in a PyPy build (§5 2.6) where the inference loop is JIT-compiled. This is a
  project, not a step — scope it only after Phases 4–8 plateau.

---

## 10. Results log (append-only — newest last)

| Date | Phase/Step | Result | Notes / numbers |
|---|---|---|---|
| 2026-06-29 | audit | PLAN + user_dev_guide created | Engine v1.4.1; search feature-complete, eval complete-but-untuned, no harness. Bench anchor: **559 253 nodes @ depth 9, ~23.4k nps** (dev box). |

---

## 11. Quick command reference

```powershell
# Tests
& .venv\Scripts\python.exe -m pytest -q

# Bench fingerprint (refactor gate; must equal 559253 @ depth 9 until behaviour changes)
"bench 9`nquit" | & .venv\Scripts\python.exe -m hydra

# Run the engine interactively as UCI
& .venv\Scripts\python.exe -m hydra

# SPRT a candidate (Phase 0.3 builds this) — clock tc=8+0.08, the gate TC
.\tools\sprt.ps1 -EngineA <cand> -EngineB <baseline> -TC "8+0.08" -Concurrency <cores-1>

# Calibration (must accept H0, ~0 Elo, zero forfeits)
.\tools\sprt.ps1 -EngineA <baseline> -EngineB <baseline> -Elo0 -3 -Elo1 3

# SPSA (Phase 0.4 builds this; needs Phase 1 UCI options)
& .venv\Scripts\python.exe tools\spsa\tune.py

# Texel fit (Phase 0.5 builds this; offline dev tool, may use numpy)
& .venv\Scripts\python.exe tools\texel\tune.py --data <set> --stage material
```

---

## 12. Reference

- Sibling plans: `D:\code\rarog\PLAN.md` + `user_dev_guide.md` (Rust),
  `D:\code\basilisk\PLAN.md` + `user_dev_guide.md` (C++). Same gate discipline
  and "build-structure-first, tune-once" sequencing; consult them for the proven
  shape of the Texel campaign, SPSA grouping, and release discipline.
- The removed *lite* line (single-file Python, ChessAgents) proved the
  Python-specific levers that this plan leans on: incremental eval accumulators
  (2.6× NPS), self-contained Hydra-native SPSA driver, and that small-sample
  quickmatches mislead near 50% — trust SPRT.
