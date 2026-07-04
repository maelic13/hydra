# Hydra Strength Improvement Plan

**The one goal:** make Hydra — the UCI chess engine in `hydra/` — as strong as
possible *as a Python engine*. This is the master plan; the user-facing
checklist and command cheat-sheet live in `user_dev_guide.md` — **keep the two
in lockstep, in the same commit, every step** (§1 rule 8).

Modeled on the sibling engines `D:\code\rarog` (Rust) and `D:\code\basilisk`
(C++) — same SPRT gate discipline and "build structure first, tune once"
sequencing — but **specialized for Python**: the levers, the ordering, the NPS
economics, and the "faster build" story are all different when the engine is
interpreted CPython at ~23k NPS instead of compiled at ~5M NPS.

**Branching & releases:** day-to-day work happens on the **`development`**
branch. `master` only ever receives squashed `Version X.Y.Z` release commits
(see §11 Release discipline). Commit each kept step separately on `development`,
**no co-author trailer**.

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
full-eval cache.

**Infrastructure:** bitboards + mailbox + magic sliding attacks; make/unmake with
history stack (incremental Zobrist); full UCI with threaded search, ponder,
infinite; Syzygy via bundled Fathom; `bench` node-count fingerprint.
Version 1.4.1. No runtime package dependencies. Fully type-annotated (matters for
the mypyc speed path, §5 2.6).

### The three real gaps (this plan attacks them in Elo order, dependency-respecting)

1. **Zero tuning.** Every weight is a hand-set textbook constant — the PSTs are
   the Michniewski *Simplified Evaluation Function* tables, material is
   `100/320/330/500/900`, every margin/bonus is a round number. **Nothing has
   ever been Texel-fit or SPSA-tuned.** A complete-but-untuned eval is the single
   biggest pool of free Elo in the whole project. There is also **no UCI
   exposure** of any tunable constant, so neither Texel nor SPSA can run yet.
2. **No harness.** No fastchess runner, SPRT script, SPSA driver, Texel tuner,
   labelled dataset, or opening book. (`tools/spsa`, `tools/results` are stale
   *lite*-line artifacts — reference only.) This is Phase 0.
3. **Speed: ~23k NPS in CPython** (bench depth 9 = **559 253 nodes**, ~23.4k
   nps dev box — the fingerprint anchor). The eval recomputes per node; the TT
   allocates a Python object per store; sliding attacks recompute up to 3× per
   eval. In an interpreted engine NPS *is* strength: at a fixed clock +1
   effective ply ≈ +40–70 Elo. **Speed work here is real Elo**, and makes every
   later SPRT/SPSA/datagen run cheaper.

### Research addendum — what strong HCE engines do (present vs added this revision)

Audited against late-HCE Stockfish (≤16.1), Ethereal, Berserk/Koivisto-HCE and
the chessprogramming wiki. **Already present in Hydra:** the full modern search
list above; tapered PST; mobility; pawn structure; outposts; basic king safety;
basic passers; tempo. **Confirmed missing → now scheduled in this plan:**

- **Correction-history family** — Hydra has only pawn-keyed corr-hist; SF uses
  pawn + non-pawn(per-side) + major + minor + **continuation** corr-hist. → §9 Phase 7.
- **Upcoming-repetition / cuckoo cycle detection** (SF10) — prune when a draw by
  repetition is reachable. Hydra lacks it. → §9 Phase 7.
- **Threats package** (weak/hanging pieces, minor-on-rook/queen, rook-on-queen,
  pawn-push threats, restricted squares). → §6 Phase 3.1.
- **King-safety v2** (king-danger model: attacker scaling, **safe checks**,
  king-ring weak squares, queen-contact, pawn shelter/storm, flank attacks). → §6 Phase 3.2.
- **Scale factors + specialized endgames** (OCB drawishness, KPK, KBNK, KRKP, …)
  plus **initiative/winnable** correction and **rule-50 eval damping**. → §6 Phase 3.3.
- **Material-key table** (imbalance + phase + endgame/scale-function dispatch,
  cached by material key — also a Python speed win). → §6 Phase 3.5.
- **Bad bishop / bishop-blocked-by-own-pawns, minor-behind-pawn, trapped rook,
  connected rooks, queen-pin.** → §6 Phase 3.6.
- **Node-based + instability time management.** → §9 Phase 6.

**Python-specific levers strong compiled engines don't need but Hydra does:**
incremental eval accumulators, lazy eval, packed TT, attack-map reuse (§5 Phase
2.1–2.5); a **faster runtime/compiler** (mypyc/PyPy/Cython — the pext/PGO analog,
§5 2.6); **Lazy-SMP threading** via free-threaded CPython 3.13+ or
multiprocessing + shared-memory TT (§5 2.7).

### Honest expectation (estimates; SPRT is the only verdict; gains overlap)

| Phase | Work | Expected Elo |
|---|---|---|
| 0 | Harness | 0 (enabler) |
| 1 | Expose constants + tunable-eval refactor (default-equivalent) | 0 (enabler) |
| **2** | **Python speed wave** (incremental eval, lazy eval, packed TT, faster build, threads) | **+30–120** (real, via deeper search at a fixed TC; threads/build are the high end) |
| 3 | Eval structure completion (seeded inert) | 0 direct (enabler for one-shot Texel) |
| **4** | **Texel eval data-fit campaign** (the multiplier) | **+80–160** |
| **5** | **Search-constant SPSA wave** (once, at final eval scale) | **+20–50** |
| 6 | Time-management hardening + tuning | +5–25 (clock TCs) |
| 7 | Search-efficiency refinements (corr-hist family, cuckoo, …) | +15–50 |
| 8 | Eval-refresh cycles (non-NNUE ceiling) | +10–30 (diminishing) |
| 9 | NNUE (terminal option) | +200–600, but Python-inference is the hard problem |

---

## 1. Non-negotiable gates (apply to every phase)

1. **SPRT-gate every strength change.** Default `elo0=0 elo1=5 alpha=0.05
   beta=0.05`; `elo1=3` for small single features. Nothing is "good" until SPRT
   says so.
2. **One change at a time.** Never bundle features. Implement, gate, keep/revert,
   commit, move on.
3. **Texel/SPSA propose; SPRT decides.** A tuned value set is a *candidate* until
   it survives a game gate. Lower loss that fails SPRT is overfitting — revert.
4. **Default-equivalence first.** Every refactor introducing a struct/option must
   reproduce current behaviour exactly: the `bench` fingerprint (**1 002 645 @
   depth 9**, 40-position suite adopted 2026-07-01 to match Rarog/Basilisk; was
   559 253 over the old 16-position suite) must be **identical**, *and*
   `evaluate()` must match on the **eval-equivalence corpus** (a balanced
   ~50k-FEN sample from `A:\Chess\Beast\data\txt\positions.txt`, extracted once
   in Phase 0.6) before tuning begins. Record a fresh anchor whenever behaviour
   intentionally changes.
5. **Tune and gate at the *same* time control.** SPSA/Texel-confirm TC == SPRT
   TC. Default gate **`tc=8+0.08`** (clock, not fixed movetime; locked in Phase
   0). LTC confirmation at phase boundaries and for TC-suspect features.
6. **`bench` is the refactor fingerprint, not an Elo proxy.** Refactors: must
   match exactly. Behaviour changes: record the new number, read no Elo into it.
7. **Preserve the eval boundary.** Search calls `Evaluator.evaluate(board)`; no
   eval internals leak into search. Keeps the Texel campaign tractable and the
   NNUE door open.
8. **Update `PLAN.md` and `user_dev_guide.md` in lockstep — same commit, every
   step.** Statuses, §10 results log, measured numbers, and the guide's "Next
   action" pointer. The user reads the guide to see where we are; a stale guide
   breaks the loop. Most-skipped rule — treat as mandatory.
9. **Commit each kept step separately on `development`, no co-author trailer.**
   One feature per commit for surgical revert.
10. **Review tuned constants before baking.** Check every value against its
    bounds and re-read the code it feeds. A value pinned at a bound or driven to
    a no-op is a signal to inspect the implementation, not to bake blindly.
11. **Use the model named in each step.** Reasoning-dense / correctness-critical
    steps (make/unmake, eval refactor, king-safety, tuner math, concurrency,
    NNUE) run on **Opus 4.8 high**; mechanical, well-specified steps run on
    **Sonnet 4.6 medium**; trivial wiring on **Sonnet 4.6 low**. Each step states
    its **Model:**. If the user is on a weaker model for a `high` step, stop and
    ask them to switch.

### The Python advantage — no build step (in dev)

Rarog/Basilisk must compile a PGO test binary before every SPRT. **Hydra does
not** (in development): fastchess runs `python -m hydra` directly, so a candidate
is testable the instant it is edited and a revert is `git restore`. The compiled
*release* artifact (mypyc/PyPy, §5 2.6 / §11) is a separate, periodic concern.

---

## 2. Sequencing principle — build structure first, tune once (READ THIS)

Three kinds of tuning, very different costs:

- **Texel weight-fitting** — gradient fit over a fixed labelled dataset. Minutes
  of offline CPU, **zero games**. Cheap to repeat; the per-feature inner loop,
  **not** a conserved resource.
- **SPSA** (search-constant tuning) and **SPRT** game gates — **thousands of
  self-play games each**, *expensive* in CPython. The conserved resource.

Search margins (RFP, razoring, futility, delta, history-pruning thresholds,
parts of LMR/NMP) are denominated in **eval centipawns**. Re-fitting the eval
changes what a centipawn means, so an SPSA wave run before the eval is final is
thrown away. Therefore the order is forced:

1. **Build all eval structure first**, each new sub-term **seeded inert**
   (zero-effect) or **linear-equivalent**, so `bench` is unchanged and the gate
   is the fingerprint + reconstruction — **no games**.
2. **Fit the whole enlarged eval once** (one staged Texel campaign; biggest lever
   first, PSTs + material last).
3. **Run the one search-constant SPSA wave last**, at the final centipawn scale.
4. **Speed work is behaviour-identical** → invalidates no tuning; placed **early
   (Phase 2)** because in CPython faster NPS is both real Elo and a cheaper
   everything-after.

> By raw "most Elo" the Texel campaign (Phase 4) ranks first. But it depends on
> the harness (0), tunable exposure (1), and — to be done *once* — the full eval
> structure (3). Texel is cheap to repeat, so we accept it landing mid-plan and
> conserve the expensive resource (self-play games) instead.

### Execution order

| Phase | Role | Gate | Release |
|---|---|---|---|
| **0** | Harness + dataset/book prep | ✅ DONE — calibration healthy (48.6%, no bias, 1016 games) | — |
| **1** | Expose search constants + tunable `EvalParams` refactor | ✅ DONE — bench + corpus + trace identical | — |
| **2** | Python speed wave — 2.1✅+2.2✅+2.6✅ done (**~3.2× NPS**); 2.3/2.5 deferred; 2.4 inert; 2.7 blocked (3.13t) | identical parts no games; lazy eval / SMP SPRT-gated | — (ships in v1.5.0) |
| **3** | Eval structure completion (threats, KS-v2, scale/winnable/rule50, passers, imbalance, minor terms) — seeded inert | bench + corpus identical | — |
| **4** | Texel eval data-fit campaign (staged; PST/material last) | per-stage SPRT | **v1.5.0** |
| **5** | Search-constant SPSA wave (once, final scale) | confirming SPRT | — |
| **6** | Time-management hardening + TM SPSA + clock-TC validation | SPRT (+ LTC) | **v1.6.0** |
| **7** | Search-efficiency refinements (corr-hist family, cuckoo, history formula, fractional LMR, qsearch checks, TT aging, staged movegen) | per-feature SPRT | **v1.7.0** |
| **8** | Eval-refresh cycles — non-NNUE ceiling | per-cycle SPRT | (roll into v1.7.x) |
| **9** | NNUE (terminal; Python-inference is the design problem) | SPRT vs HCE head | **v2.0.0** |

---

## 3. Phase 0 — Harness + data prep (prerequisite; do this first)

**Goal:** one-command SPRT self-play, an SPSA loop, a Texel tuner, the dataset
pipeline, and an opening book — all driving `python -m hydra` directly. Nothing
else proceeds until calibration (engine vs identical engine) reproduces ≈0-Elo H0.

> **Status 2026-06-29 — 0.1–0.6 DONE; 0.7 is the only remaining step (user-run).**
> Built: `tools/bin/fastchess.exe` (v1.8.0-alpha); `tools/run_hydra.cmd` (shim,
> `python -S` baseline isolation **verified**: a tagged snapshot reported its own
> version, not the editable install); `tools/snapshot_engine.ps1`; `tools/sprt.ps1`
> (default `tc=8+0.08`); `tools/spsa/tune.py` + `config_search.json` (scaffold —
> needs Phase 1.1 options); `tools/texel/tune.py` (`--smoke`/`--find-k`
> functional); `tools/build_data.py`. Data: **`tests/data/eval_corpus.epd`** =
> 5000 FENs, perfectly phase-balanced (1000 each opening / early-mid /
> middlegame / endgame / deep-endgame); **`tools/book/openings.epd`** = 3000
> opening positions — both from the 122.66M-FEN dump (40M scanned). **Eval-equiv
> baseline fingerprint: `c4e9c6109970e676`** (all 5000 load, 0 unparseable).
> Engine handshake through the shim is clean (`uciok`/`readyok`/`bestmove`).
> **Remaining: 0.7 — the user runs the calibration SPRT.**

- **0.1 Match runner.** ✅ **DONE.** Install [fastchess](https://github.com/Disservin/fastchess)
  to `tools/bin/fastchess.exe`. — **Model: Sonnet 4.6 low.**
- **0.2 Engine launch shim.** ✅ **DONE** (`tools/run_hydra.cmd`). Wrapper so fastchess starts the engine with chosen
  `Hash`/options and chosen Python (CPython now; PyPy/mypyc later). Prove a clean
  `uci`/`isready`/`go`/`bestmove`/`stop` round-trip with **zero forfeits** (the
  lite line was bitten by a bad adapter). — **Model: Sonnet 4.6 medium.**
- **0.3 `tools/sprt.ps1`.** ✅ **DONE.** Wraps fastchess SPRT (`-EngineA -EngineB -TC
  -Concurrency -Elo0 -Elo1`), repo-local book, Hash 64MB, Threads 1, prints the
  standard report line, default `tc=8+0.08`. — **Model: Sonnet 4.6 medium.**
- **0.4 SPSA driver.** ✅ **DONE (scaffold)** (`tools/spsa/tune.py` + `config_search.json`); tunes real params once Phase 1.1 exposes the UCI options. Port the *lite* line's self-contained Hydra-native SPSA
  driver (no external weather-factory): perturbs UCI options, runs fastchess
  mini-matches, saves/resumes `tools/spsa/state.json`. Needs Phase 1 options to
  tune anything. — **Model: Sonnet 4.6 medium** (Opus 4.8 medium if written fresh).
- **0.5 Texel tuner (offline dev tool — may use numpy).** ✅ **DONE (scaffold)** (`tools/texel/tune.py`); `--smoke`/`--find-k` work now, the staged weight fit plugs in at Phase 4.2 once Phase 1.2/1.3 land. Standalone script:
  load labelled FENs → run Hydra's eval-coefficient trace (1.3) → gradient
  descent on the weight vector. **The engine stays stdlib-only; the *tuner* is a
  dev tool and may import numpy/scipy** for a fast vectorized gradient + parallel
  scoring. Key Python lever: heavy math is allowed offline. — **Model: Opus 4.8
  high.**
- **0.6 Dataset + book prep** ✅ **DONE** (`tools/build_data.py` → corpus + book;
  `tools/eval_equiv.py` fingerprint tool). (see §7 Phase 4.1 for the full recipe):
  - Source: **`A:\Chess\Beast\data\txt\positions.txt`** — **122 656 978 FENs,
    label-free** (one 6-field FEN per line, no result). Diverse: ICCF computer
    chess → human club play. **We do not generate more.**
  - Extract a **balanced eval-equivalence corpus** (~50k FENs, stratified across
    opening/middlegame/endgame by phase — see Phase 4.1 bucketing) into a
    repo-local file for the rule-4 reconstruction gates used by Phases 1–3.
  - Choose/commit an **opening book** for match variety + (optional) datagen
    seeds. A book wants *opening* positions; if positions.txt early-ply FENs are
    used, filter to low fullmove counts — but a purpose-built balanced book is
    preferable. — **Model: Sonnet 4.6 medium.**
- **0.7 Calibration.** ✅ **DONE 2026-06-30.** 1016 self-play games: **48.57%,
  Elo −9.92 ± 16.73** (0 within CI → no systematic bias), 0 crashes/disconnects/
  illegal, 1 lone time-loss (~0.1%, mitigated by Move Overhead 10→50ms). Harness
  healthy. (SPRT doesn't converge at true≈0 between ±3 bounds — stopped by
  design once enough games confirmed no bias + no forfeits.)

**TC decision (Python-specific).** Compiled siblings gate at `tc=3+0.03`
(~depth 16); at 23k NPS Hydra is far shallower in 3s, where its margins barely
bite. Lock **`tc=8+0.08`** (deeper, margins active, the lite line's validated
operating point) as the primary gate for both SPSA and the confirming SPRT, with
an optional **fixed-nodes** pre-screen and an LTC confirmation at phase
boundaries. Re-check this number after every NPS-changing step (2.x).

**Done when:** `sprt.ps1` runs end-to-end, calibration accepts H0 with zero
forfeits, SPSA/Texel scripts each execute one smoke iteration, the corpus +
book exist.

---

## 4. Phase 1 — Expose constants + tunable-eval refactor (default-equivalent)

> **Status 2026-06-30 — Phase 1 COMPLETE (1.1, 1.2, 1.3 all done & verified).**
> bench 559 253 @ depth 9 unchanged; eval fingerprint `c4e9c6109970e676`
> unchanged; trace reconstructs evaluate() exactly over all 5000 corpus
> positions; 112 tests pass; ruff clean. **Next: Phase 2.1.**

Make every constant Phases 4/5 will tune *reachable*, without changing
behaviour. `bench` must stay 559 253 @ depth 9 and `evaluate()` must match on the
Phase-0.6 corpus.

- **1.1 ✅ DONE.** Expose search constants as UCI spin options (behind a `Tune` flag).
  `ASPIRATION_WINDOW`, `_REVERSE_FUTILITY_MARGIN`, `_RAZORING_MARGIN`,
  `_FUTILITY_MARGIN`, `_DELTA_MARGIN`, `_LMP_BASE`, NMP base+divisor, the `_LMR`
  log-formula coefficients (0.5 / 1.6), history-pruning thresholds, SEE-pruning
  depth multipliers, ProbCut margin, singular margins/depths. Read from a params
  object defaulting to today's values; keep release UCI clean. **Gate:**
  bench-identical. — **Model: Sonnet 4.6 medium.**
- **1.2 ✅ DONE.** Refactor eval weights into a tunable `EvalParams` table
  (default-equivalent — the big infra step). Move every magic number in
  `evaluation.py` (piece values, all PST entries, bonuses/penalties, mobility
  tables, king-safety weights + quadratic) behind a parameter object whose
  defaults reproduce current values bit-for-bit. Tune-time loader (file/UCI);
  releases run baked defaults. **Gate:** bench-identical + corpus reconstruction
  exact. **Trap:** one wrong PST orientation silently poisons the whole campaign.
  — **Model: Opus 4.8 high** (review the diff).
- **1.3 ✅ DONE** (`ClassicalEvaluator.trace` + `reconstruct_eval`; KS &
  eg-centralization carried as residuals for finite-diff). Eval-coefficient trace
  (tune-only mode). `evaluate` also returns the
  per-position **coefficient vector** (count of each weight's application, MG/EG,
  with the phase blend) for the Texel gradient. **Gate:** `sum(coeff·weight)`
  tapered == `evaluate()` on the corpus. — **Model: Opus 4.8 high.**

---

## 5. Phase 2 — Python speed wave (the Hydra-specialized phase) → ships in v1.5.0 (no standalone release)

Behaviour-identical speed never invalidates tuning, and in CPython NPS converts
to real Elo at a fixed clock *and* makes every later game cheaper. Profile with
`cProfile` before/after each step; record NPS in §10.

> **Status 2026-06-30.** Bench NPS **23.4k → 41.0k (1.75×)** so far, all
> behaviour-identical (bench `559253`, eval fingerprint `c4e9c6109970e676`, trace
> 0-mismatch unchanged throughout).
> - **2.1 ✅ DONE** — incremental eval accumulators (1.6×).
> - **2.2 ✅ DONE** — slider attacks computed once (mobility+king-safety merge).
> - **2.3 ⏸ DEFERRED (profile-justified).** After 2.1/2.2, a re-profile shows
>   `_evaluate_internal` tottime nearly halved (1.37s→0.78s) and `transposition.py`
>   **does not appear in the top-12 hotspots** — packing the TT would be an
>   engine.py refactor for an estimated ~1–2% with real risk. Revisit only if a
>   future profile (e.g. at long TC) shows TT allocation mattering.
> - **2.5 ⏸ DEFERRED.** The eval/pawn caches rarely hit the clear-on-full path in
>   bench, so the benefit isn't bench-measurable; revisit when testing at
>   deployment time controls (long searches that fill the caches).
> - **2.6 ✅ DONE (~1.8× more, cumulative ~3.2×).** mypyc-compiled build
>   (`tools/build_mypyc.ps1` → `tools/engines/compiled/`, git-ignored). Proven
>   bit-identical (eval fp, bench, uninterrupted depth-11 Kiwipete all match
>   pure). **Pending: user runs the compiled-vs-pure confirming SPRT** + the
>   v1.5.0 release wires the compiled artifact into the pyinstaller build.
> - **2.4 ✅ DONE but INERT (no gain).** Lazy-eval infra + `LazyMargin` tunable
>   implemented; measured a +8% node cost at margin 250 with no NPS gain (eval is
>   already cheap), so **default `lazy_margin=0` (off)** — bench `559253` exact.
>   Kept for the Phase 5 SPSA to revisit post-refit.
> - **2.7 ⛔ BLOCKED** on a free-threaded CPython 3.13t (dev box is 3.12). Needs
>   the user to install `python3.13t`; then implement Lazy SMP + raise Threads cap.
>
> **Phase 2 actionable work is complete: ~3.2× NPS banked (2.1+2.2+2.6).** Phase 2
> is speed-only → **no standalone release** (per user, 2026-06-30); the compiled
> build ships bundled with **v1.5.0** (after Phase 4). Next high-value move: start
> the eval campaign (Phase 3 → Phase 4 Texel, the +80–160 Elo). Runtime
> comparison (mypyc vs PyPy) prepped in `tools/` (see §5 2.6).
>
> Remaining bench hotspots are now movegen + SEE (out of Phase-2 scope; candidates
> for Phase 7 search-efficiency) and the eval (further reduced by 2.4 lazy eval).

- **2.1 ✅ DONE (1.6× NPS).** Incremental eval accumulators (behaviour-identical — biggest NPS lever).
  Maintain running `mg`, `eg`, `phase` on the `Board`, updated in
  `make_move`/`unmake_move` where the Zobrist hash is, so the per-node
  material+PST loop disappears. The *lite* line measured **2.6×**. Output
  unchanged → no re-tune; the Phase-4 PST refit just changes summed values.
  **Gate:** bench-identical (node count same, NPS up), perft + suite green.
  — **Model: Opus 4.8 high** (make/unmake correctness; perft gate).
- **2.2 ✅ DONE (→41.0k NPS).** Attack-map compute-once (behaviour-identical + structure enabler).
  `evaluate` recomputes sliding attacks for mobility and again for king safety.
  Compute per-side per-piece attack bitboards **once**, reuse across
  mobility/king-safety/(future) threats. Speed win + the substrate Phase 3 needs.
  **Gate:** bench-identical. — **Model: Opus 4.8 medium.**
- **2.3 ⏸ DEFERRED (not a hotspot per re-profile).** Packed TT (behaviour-identical — Python-specific). Replace
  object-per-entry `list[TTEntry|None]` with packed ints in a flat list/`array`;
  a store mutates ints in place, no `TTEntry` allocation. Keep depth-preferred
  replacement identical. **Gate:** bench-identical (NPS up). — **Model: Sonnet
  4.6 medium.**
- **2.4 ✅ DONE but INERT (measured no gain; `lazy_margin=0`).** Lazy eval (behaviour-CHANGING — SPRT-gated; durable NPS lever). Compute
  material+PST(accumulator)+pawn-cache first; if far outside `(alpha,beta)` by a
  lazy margin, return it and skip mobility/king-safety/threats. The lazy margin
  is cp-denominated → **confirm it in the Phase-5 SPSA**. **Gate:** SPRT
  (`elo1=0`: keep if ≥0). — **Model: Opus 4.8 high.**
- **2.5 ⏸ DEFERRED (benefit not bench-measurable).** Cache-eviction polish (behaviour-identical). The eval/pawn caches
  wholesale-clear when full; switch to bounded eviction / generation tagging.
  **Gate:** bench-identical. — **Model: Sonnet 4.6 medium.**
- **2.6 ✅ DONE — mypyc compiled build (~1.8×).** Faster runtime/compiler — the pext/PGO analog (RESEARCH + SHIP).
  Compiled siblings get pext+PGO for free speed; Hydra's analog is choosing the
  fastest runtime for the hot path. Evaluate, in order of expected fit:
  - **mypyc (recommended primary).** Compiles type-annotated Python to C
    extensions using mypy's type analysis. Hydra is *already fully annotated*;
    mypyc keeps CPython semantics and the C-API, so **ctypes/Fathom Syzygy keeps
    working** and the pyinstaller exe story is unchanged — it just ships compiled
    `.pyd`/`.so` modules. Typical 2.4–14× on numeric/loop code. Lowest-risk
    large win.
  - **PyPy (high-upside alternative).** JIT; typically 6–66× on this style of
    code — potentially the single largest NPS lever — but complicates packaging
    and slows the `ctypes` Syzygy path. Benchmark `bench`, perft, suite, and a
    Syzygy probe under PyPy; decide whether to ship a PyPy build (or use PyPy
    only as a cheaper *tuning* runtime).
  - **Cython (targeted).** Reserve for hand-optimizing the single hottest module
    (movegen or eval inner loop) with `cdef` types if mypyc isn't enough.
  - **Nuitka** — whole-program C compile (mypyc-range speed), mainly a packaging
    option; keep as fallback.
  **Action:** benchmark each on `bench` + a short SPRT, verify correctness
  (perft + suite + Syzygy probe), pick the runtime, wire it into the release
  build (§11). Document the verdict + NPS in §10. TM constants are NPS-relative
  → a runtime switch re-opens Phase 6. **Gate:** behaviour-identical (same nodes;
  NPS up) + SPRT non-regression. — **Model: Opus 4.8 high** (research + packaging
  + ctypes correctness).

  > **RESOLVED 2026-07-01 — ship mypyc.** SPRT (mypyc vs pure, 8+0.08):
  > **+184.6 ± 30.9 Elo, H1, LOS 100%, 442 games, 74.3%** (1 pure-side timeout,
  > 0 crashes). `bench_runtimes` (depth 10, warm, all nodes=840811 → bit-identical):
  > CPython **38.8k** · mypyc **77.4k (2.00×)** · PyPy **35.4k (0.91× — slower than
  > CPython!)**. PyPy loses because the hot path is arbitrary-precision 64-bit int
  > (bitboard) ops its JIT can't accelerate; mypyc's win is killing bytecode-
  > dispatch overhead on everything else. **Cython `cdef` (native `uint64`) could
  > beat mypyc but isn't worth the port** given mypyc's 2× + confirmed +185 Elo.
  > Nuitka not pursued. **Ship target = mypyc; v1.5.0 wires it into pyinstaller.**
- **2.7 Lazy SMP multi-threading (RESEARCH → SHIP if it gates).** UCI currently
  caps `Threads` at 1. The GIL blocks `threading` from giving CPU-bound speedup,
  so the two real Python paths are:
  - **Free-threaded CPython 3.13+ (`python3.13t`, PEP 703, no-GIL).** Real
    threads sharing one TT — the cleanest Lazy SMP. Requires shipping/targeting a
    free-threaded interpreter; benchmark the single-thread no-GIL penalty first.
  - **`multiprocessing` + shared-memory TT** (`multiprocessing.shared_memory`
    for the packed TT from 2.3). Real parallelism on stock CPython, but IPC /
    shared-array overhead and a more complex stop protocol.
  Implement Lazy SMP (independent searches sharing TT, root-move dispersion),
  raise the `Threads` max, and SPRT N-thread vs 1-thread at equal **total** time.
  Expect a smaller multi-thread gain than compiled engines (overhead), but
  positive. This is the gnarliest concurrency work in the plan. **Gate:** SPRT
  (multi vs single, equal wall-clock). — **Model: Opus 4.8 high (max reasoning).**

> **No standalone Phase-2 release** (decided 2026-06-30): the speed wave is
> behaviour-neutral, so the ~3.2× NPS ships bundled with **v1.5.0** (after Phase
> 4), not on its own.

---

## 6. Phase 3 — Eval structure completion (seeded inert; no games)

Add the terms Hydra lacks, **all seeded zero-effect or current-equivalent**, so
`bench`+corpus are unchanged and Phase 4 fits them in **one** campaign. Each
consumes the Phase-2.2 attack maps.

> **Workflow (from 2026-07-01, per user): the compiled build is the primary
> target.** After each step, verify on pure (bench 1002645 + eval fp + trace +
> suite + ruff) **and** rebuild `build_mypyc.ps1` + confirm compiled bench 1002645
> (ensures the new code stays mypyc-compilable). Seeded-inert additive terms use
> an `<term>_active` guard so they cost ~0 while dormant; the shared attack-map
> accumulation stays on (substrate). Expect a modest cumulative NPS dip across
> Phase 3 (structure cost) — recover it in a hot-loop-cleanup pass before Phase 4
> if it grows large.

- **3.1 ✅ DONE (seeded inert).** Threats package: weak/hanging
  (attacked-undefended) pieces, minor-attacks-rook/queen, rook-attacks-queen.
  (Pawn-push threats / restricted squares deferred — can fold into Phase 4 or a
  follow-on.) Per-side attack maps (full/minor/rook) now accumulated in the
  mobility pass (substrate for 3.2). 6 weights default 0 + `threats_active`
  guard; `trace()` mirrored. Verified: bench 559253 / eval fp / trace all exact
  (pure **and** compiled); non-zero-weight reconstruction 0-mismatch, term moves
  eval in 17% of corpus. — **Model: Opus 4.8 high.**
- **3.2 ✅ DONE (seeded ≈ current).** King-safety v2 — explicit king-danger sum
  through the same quadratic curve: base attacker units + **safe checks**
  (N/B/R/Q, on undefended squares), king-ring weak squares, no-queen attenuation
  (all weights 0 → danger == units → penalty unchanged). Mobility pass now
  accumulates **per-type** attack maps (N/B/R/Q + full; 3.1 threats derive
  minor). Shared `_king_danger_extra` helper called by evaluate() **and** trace()
  (KS is nonlinear → trace *residual*, finite-diff tuned in Phase 4.3); `ks_v2_active`
  guard. Verified: bench 1002645 / eval fp / trace exact on **pure and compiled**;
  non-zero-weight reconstruction 0-mismatch, moves eval in 38% of corpus.
  (Pawn shelter/storm + flank deferred to a follow-on / Phase 4.) — **Model: Opus
  4.8 high (max reasoning).**
- **3.3 ✅ DONE (framework, seeded inert).** Final-score transform: eg **scale
  factor** (OCB drawishness via `ocb_scale`; `scale_active` guard), **winnable**
  (const + per-pawn + both-flanks; `winnable_active` guard), **rule-50 damping**
  (`rule50_damp=0`). `EvalTrace` carries (eg_scale, winnable, r50_num);
  `reconstruct_eval` applies them; shared `_final_transform` for evaluate()+trace()
  (finite-diff tuned in 4.x). Verified bench 1002645 / eval fp / trace exact on
  **pure and compiled**; non-zero reconstruction 0-mismatch, moves eval 4998/5000.
  (Deeper endgame funcs — KPK/KBNK/KRKP — are a follow-on.) Original description:
  scale factors + endgame knowledge + winnable/rule50 (seeded scale=1.0,
  winnable=0 — Hydra's biggest correctness gap; today only insufficient-material
  draw): OCB drawish scaling, KPK, KBNK, KRKP, KQKP, lone-minor-can't-win,
  drawish-material downscaling — multiplicative scale on the EG score. **Plus**
  an **initiative/winnable** correction (pawns-on-both-flanks, pawn count,
  opposite bishops, infiltration → pushes the score toward/away from draw) and
  **rule-50 damping** (scale eval down as `halfmove` climbs). — **Model: Opus 4.8
  high.**
- **3.4 ✅ DONE (seeded inert).** Passed-pawn richness: stop-square blocker,
  free-path (empty+unattacked), passer protected by a friendly pawn, enemy-king
  distance to the queening square. Shared `_passer_counts`; 7 weights default 0;
  `passers_v2_active` guard. Verified pure+compiled (bench 1002645); non-zero
  reconstruction 0-mismatch, moves eval 2344/5000. — **Model: Opus 4.8 medium.**
- **3.5 ✅ DONE (seeded inert).** Imbalance terms: piece counts scaled by pawn
  count (knight-likes-pawns, rook-hates-pawns, bishop-likes-pawns) via a shared
  `_imbalance_terms` helper; 3 weights default 0; `imbalance_active` guard.
  (Material-key caching folded into the same helper path; the dispatch-dict speed
  win is left for the Phase 4 hot-loop cleanup.) Verified pure+compiled (bench
  1002645); non-zero reconstruction 0-mismatch, moves eval 4980/5000. — **Model:
  Opus 4.8 high.**
- **3.6 ✅ DONE (seeded inert).** Space + small positional terms: safe central
  space (files c-f, own half, not attacked by an enemy pawn), **bad bishop** (own
  pawns on each bishop's colour), **connected rooks** (rooks defending each
  other), via a shared `_minor_terms` helper; 5 weights default 0;
  `minor_terms_active` guard. (Trapped-rook/queen-pin deferred as low-value.)
  Verified pure+compiled (bench 1002645); non-zero reconstruction 0-mismatch,
  moves eval 4040/5000. — **Model: Sonnet 4.6 medium (done on Opus 4.8).**

**Gate (all of Phase 3):** ✅ bench-identical (`1002645`) + corpus reconstruction
(0/5000) + suite (114) — met on **pure and compiled** at every step. No self-play
games until Phase 4. **Phase 3 COMPLETE 2026-07-01.**

---

## 7. Phase 4 — Texel eval data-fit campaign (the multiplier) → release v1.5.0

The biggest Elo pool. Fit the whole enlarged eval **once**.

- **4.1 ✅ DONE (2026-07-01). Dataset prep — label source DECIDED: Beast
  Stockfish-WDL, not self-play.** The plan assumed we'd run a reference engine;
  the decision point resolved better than that. The Beast dataset already ships a
  read-only `evaluated/` dir: **123 shards ≈ 123M positions**, each
  `FEN<TAB>win-prob` scored by **Stockfish** (`evaluated_positions_*.txt`),
  aligned 1:1 with `positions.txt`. Analysis (vs the siblings, which self-play):
  - **Rarog + Basilisk both label by self-play game results** (Beast = start
    positions only); Rarog documents SF-WDL as an *optional* path ("can chase SF
    quirks that don't transfer"). **Hydra diverges** — decisive factor: Hydra
    self-play is **~30–50× slower** (~20–34 h/regen at ~70k nps vs <1 h native).
    The pre-computed SF labels are **free** (minutes), **denser** (continuous
    WDL), and from a **far stronger judge**; the "chase quirks" risk is minor for
    an *underfit* from-scratch eval, and the **SPRT gate** protects transfer.
  - Label is **side-to-move win-prob**; convert to White POV
    (`p if wtm else 1−p`). **No cp conversion** — the WDL % *is* the Texel target.
    (Confirmed empirically: corr(Hydra white-POV eval, stm→white label) = +0.42
    raw → **+0.58** after quiet+balance.)
  - **`tools/texel/import_beast.py`** (Hydra-native, uses engine SEE+movegen):
    streams shards (shuffled) → quiescence filter (drop in-check + `SEE>0`
    tactical, ~68% kept) → 5-bucket phase-balanced reservoirs (deep-endgame ~4%
    gates scan size) → dedup by position → disjoint holdout →
    `beast_train.csv`/`beast_holdout.csv` (git-ignored). Default ~2M balanced
    (400k×5) + 5% holdout from a ~20M scan (~25–30 min).
  - **Reconstruction gate** wired into `tools/texel/tune.py --verify` (0/5000 on
    the extracted FENs); `--find-k` reports K/MSE/correlation. Self-play stays a
    documented fallback (`tools/texel/README.md`).
  — **Model: Opus 4.8 high** (labeling strategy, balancing, leakage avoidance).
- **4.2 Staged fit, biggest lever first, each stage SPRT-gated** (rules 1/3):
  1. Material (piece values MG/EG) · 2. Mobility tables · 3. Pawn-structure
  scalars · 4. Passed-pawn-richness block (3.4) · 5. King-safety-v2 block (3.2;
  nonlinear — may need a finite-difference path in the tuner) · 6. Threats block
  (3.1) · 7. Scale/imbalance/space/winnable (3.3/3.5/3.6) · 8. **PST + material
  refit LAST** (most parameters, highest overfitting risk; they absorb residual
  error from every earlier stage — fitting them first wastes the others).
  Texel proposes → bake → confirming SPRT at the gate TC → keep on H1, revert on
  clean H0. Re-running Texel between stages is cheap and expected.
  — **Model: Sonnet 4.6 medium** to drive; **Opus 4.8 high** for the KS/scale
  nonlinear stages and any tuner-core change.

> **Release v1.5.0** after Phase 4 — the major strength jump.

---

## 8. Phases 5–11 — REWORKED 2026-07-02 (post-Phase-4 deep review)

> **Why the rework.** Two pieces of hard evidence forced it: (a) **Rarog burned
> 30 h of SPSA for a negative gain** — blanket search-constant SPSA at hobbyist
> game budgets is EV≈0 with real downside risk (32k games spread over 15 params
> ≈ ±10 Elo noise per param-direction; fishtest does this with millions); (b) the
> **KS lesson** — game SPRTs found +20 Elo where MSE saw ~1%, so cheap
> hypothesis-driven SPRTs beat both MSE *and* SPSA for dynamic/search terms.
> Blanket SPSA is therefore **demoted to an optional appendix**; its budget goes
> to targeted SPRTs and to the feature/speed work below.
>
> **Elo evidence base used for the estimates** (all measured on THIS engine at
> 8+0.08 unless noted): mypyc 2.0× NPS = **+184.6±31** (≈ +12–25 per 10% NPS);
> linfit **+57±18**; KS bundle **+19.6±9.3**; evalmisc probe **≈0** (verified
> optimal); Rarog SPSA **negative after 30 h** (sibling, native speed).
> Estimates are point ± honest range; "cost" = your wall-clock (mostly SPRTs at
> ~450 games/h compiled).

### Phase 5 — Targeted search calibration (SPRT-driven; replaces the SPSA wave)
**Expected: +4 (range 0…+12) · cost 1 evening–1 day · Model: Sonnet 4.6 medium
(drive), Opus 4.8 medium (review).**
Hypothesis-driven single-candidate SPRTs via `HYDRA_TUNE` setoption (no rebuild):
- **5.1 Margin-rescale probe.** linfit moved piece values +15–40% (pawn anchored).
  One candidate scaling ALL cp margins (RFP/razor/futility/delta/probcut/
  NMPEvalDiv/SEEPruneMul) by ~1.2× → one SPRT (~2–3 h). If it passes, a 1.4×
  probe next; if clean H0, margins are confirmed calibrated and the question is
  CLOSED for free. (+0–8)
- **5.2 Lazy-eval re-test.** Phase-3 terms are now ACTIVE (threats/KS-v2/passers
  compute every eval) — eval is heavier than when 2.4 measured "no gain".
  `LazyMargin≈250` candidate → one SPRT. (+0–8, also NPS)
- **5.3 Aspiration-window A/B** (30 vs 20) — one cheap SPRT only if 5.1/5.2 leave
  appetite. (+0–3)
- **5.4 (OPTIONAL, default SKIP) full 15-param SPSA** — only if 5.1 shows margins
  are far off. 12–30 h, EV ≈ 0±10 given the Rarog result. Not recommended.

### Phase 6 — Search-efficiency features → v1.6.0
**Expected: +30 (range +15…+55) · cost ~6–9 SPRTs over days · the biggest
reliable pre-NNUE pool.** Verified against `engine.py` (audit 2026-07-02): each
item below is genuinely absent. One SPRT each, biggest first; failures are normal
(expect ~⅔ to pass).
- **6.1 Staged move generation** — currently every node generates+scores ALL
  moves even when the TT move cuts immediately. In Python, movegen is a top-3
  hotspot, so this is worth far more here than in C engines: TT-move → captures →
  killers → quiets, generated lazily. (+8–20; also NPS) — **Fable 5 medium**
  (hot-path restructure with mypyc constraints).
- **6.2 Qsearch checks at the first qsearch ply** — qsearch is captures-only
  today (verified); missing mate/check tactics at the horizon. (+4–10) —
  **Opus 4.8 medium.**
- **6.3 TT aging/replacement** — the TT has NO generation field (verified);
  stale entries from old searches never expire, hurting long games + Hash
  pressure. Add generation + depth-preferred-with-age replacement. (+3–8) —
  **Sonnet 4.6 medium.**
- **6.4 Correction-history family** — only pawn-keyed today (verified); add
  non-pawn/minor/major + continuation correction. (+4–12) — **Opus 4.8 high.**
- **6.5 History gravity** — replace add+clamp with gravity-toward-zero
  bonus/malus. (+2–6) — **Sonnet 4.6 medium.**
- **6.6 Cuckoo upcoming-repetition** (SF10) — detect reachable repetitions
  in-search; fixes shuffle/fortress blindness (we SAW this: the 50-move PV
  shuffling in the linfit SPRT). (+2–6) — **Fable 5 high** (subtle hashing
  correctness).
- **6.7 LMR refinements** — fractional accumulation + condition set
  (cutnode/TT-capture/hist-based) on top of the existing table. (+3–10) —
  **Opus 4.8 medium.**

### Phase 7 — Python speed wave 2 (profile-driven) → v1.6.0
**Expected: +12 (range +5…+25, via 5–15% NPS at our measured ≈+12–25/10%) ·
cost 1–2 dev days + 1 SPRT · Model: Fable 5 medium (hot loops), Sonnet 4.6
medium (mechanical).**
Compiled NPS drifted 70k→67.5k as Phase-3 terms activated. Re-profile the
compiled+tuned build, then: recover the eval-pass additions (per-type attack
maps assembled once, no per-node list allocs), the **material-key cache**
deferred from 3.5 (imbalance/phase/scale keyed by material signature), movegen
micro-opts surfaced by the profile, eval/pawn-cache sizing. Gate: bench NPS
uplift + ONE confirming SPRT (speed is only Elo if the tree stays sane).

### Phase 8 — Time management → v1.6.0
**Expected: +8 (range +3…+15) · cost ~2 SPRTs (incl. one longer-TC) · Model:
Opus 4.8 medium.**
On top of the 2026-07-02 hardening (clamp + poll-rate): **node-based TM**
(allocate by fraction of nodes on the best root move), **instability extension**
(fail-low / best-move-change / score-drop), easy-move fast play. Hand-derived
constants, each gated by SPRT at 8+0.08 **plus one 60+0.6 confirmation** (TM
gains must survive longer TC).

### Phase 9 — On-policy eval refresh → v1.7.0
**Expected: +10 (range +3…+25) · cost ~3 h annotation + 1 SPRT · Model:
Sonnet 4.6 medium (pipeline), Opus 4.8 medium (review).**
The 2M training set is off-policy (Beast games). We now have tens of thousands
of HYDRA games (SPRT PGNs, on disk) — extract quiet positions from them
(extract-from-PGN, dedup vs train), annotate with SF (`annotate_sf.py`, ~2–3 h),
**refit linear+KS on the merged set** (fix-k 1), SPRT. On-policy data patches the
eval's own blind spots — the standard second-cycle gain. Repeat once more only if
the first cycle passes convincingly.

### Phase 10 — Lazy SMP (BLOCKED — revisit when toolchain allows)
**Expected: +40…+80 at Threads=2–4 · Model: Fable 5 high.**
Needs free-threaded CPython (3.13t/3.14t) AND mypyc support for it (not there
yet). Re-check the toolchain each release; do not start before.

### Phase 11 — NNUE → v2.0.0 (terminal)
**Expected: +80…+250 NET (wide — see gate) · cost: a 1–2 week project ·
Model: Fable 5 high (architecture + training), max reasoning for the
incremental-inference design.**
Everything is now in place except inference speed: training data pipeline exists
(`annotate_sf.py` at scale / 123M pre-labelled Beast positions for pretraining),
eval boundary is clean, trainer infra in `D:/code/net_trainer`. **Hard gate
before committing:** prototype the int8/int16 incremental accumulator in
mypyc-compiled code and MEASURE inference NPS on real positions. Rough math: HCE
nets ~67k NPS; a net worth +250 raw must still run ≥~25–30k NPS to net positive
at our +Elo/NPS slope. If the prototype can't hit that, NNUE waits for a faster
substrate (SMP/3.14) — the gate costs ~2 days and saves the fortnight.

### Release checkpoints
- **v1.5.0 — cut NOW** (recommended before Phase 5): Phase 2 (+185) + Phase 4
  (+77) ≈ **+260 banked** over v1.4.1. Nothing in flight; anchors stable.
- **v1.6.0** after Phases 5–8 (calibration + search features + speed 2 + TM):
  honest expectation **+50 (range +25…+95)**.
- **v1.7.0** after Phase 9 (+ any 6.x stragglers): **+10 (range +3…+25)**.
- **v2.0.0** after Phase 11 (NNUE, gated): **+80…+250**.

---

## 10. Results log (append-only — newest last)

| Date | Phase/Step | Result | Notes / numbers |
|---|---|---|---|
| 2026-06-29 | audit | PLAN + user_dev_guide created | v1.4.1; search complete, eval complete-but-untuned, no harness. Bench anchor: **559 253 nodes @ depth 9, ~23.4k nps**. |
| 2026-06-29 | revision | data source + releases + models + research items added | Texel source = `A:\Chess\Beast\data\txt\positions.txt` (122.66M label-free FENs). Added: faster-build (mypyc/PyPy/Cython, §5 2.6), Lazy SMP threading (§5 2.7), corr-hist family + cuckoo (§9 Phase 7), winnable/rule50 + scale factors (§6 3.3), material-key table (§6 3.5), node-based/instability TM (§9 6). Release checkpoints v1.5.0/1.6.0/1.7.0/1.8.0/2.0.0. Work moved to `development` branch. |
| 2026-06-29 | Phase 0 | **0.1–0.6 DONE; 0.7 pending (user-run).** Harness built: fastchess v1.8.0-alpha, run_hydra.cmd shim (`-S` isolation verified), snapshot_engine.ps1, sprt.ps1, spsa/tune.py+config (scaffold), texel/tune.py (smoke OK), build_data.py, eval_equiv.py. | Corpus 5000 FENs phase-balanced (1000×5); book 3000; **eval-equiv fingerprint `c4e9c6109970e676`** (0 unparseable); engine handshake clean via shim. Gate TC locked `tc=8+0.08`. Next: user runs calibration SPRT. |
| 2026-06-30 | 0.7 calibration | **PASS — harness healthy. Phase 0 CLOSED.** 1016 games self-play (S1 vs S2), **48.57%, Elo −9.92 ± 16.73** (0 within CI → no bias), 0 crashes/disconnects/illegal. SPRT can't converge (true≈0 between ±3 bounds), stopped by design. | Only anomaly: 1 time-loss in 1016 (~0.1%) → bumped `sprt.ps1` Move Overhead 10→50ms to protect gain SPRTs (`timeouts>0`=void); root TM hardening stays Phase 6. Benign fastchess warnings (PV-past-draw, no-score-on-quick-return) noted for a Phase 7 cosmetic cleanup. **Next: Phase 1.1.** |
| 2026-06-30 | Phase 1 | **COMPLETE (1.1+1.2+1.3), default-equivalent.** 1.1: 15 search constants → `engine.PARAMS` + UCI spin options (HYDRA_TUNE-gated). 1.2: all eval weights → `EvalParams` (ClassicalEvaluator reads from it). 1.3: `trace()`+`reconstruct_eval()` coefficient decomposition for Texel. | bench 559253 unchanged; eval fingerprint `c4e9c6109970e676` unchanged; trace reconstructs evaluate() exactly over 5000 positions (0 mismatch); 112 tests (+6 trace); ruff clean. SPSA driver + Texel tuner now have the knobs/trace they need. |
| 2026-06-30 | Phase 2.1 | **DONE — incremental eval accumulators, behaviour-identical.** Board maintains mg/eg/phase accumulators in make/unmake (old values in history tuple; unmake restores). eval fast path reads them for the shared default weight set. | bench 559253 unchanged; eval fp `c4e9c6109970e676`; trace 0-mismatch; 114 tests (+test_eval_incremental); **NPS 23.4k→37.8k (1.6×)**. |
| 2026-06-30 | Phase 2.2 | **DONE — slider attacks computed once.** Merged mobility + king-safety into one pass; each B/R/Q attack bb computed once, reused. Bit-identical (integer-additive order). | bench 559253; eval fp unchanged; trace 0-mismatch; 114 tests; **NPS 37.8k→41.0k (cumulative 1.75×)**. Substrate for Phase 3. |
| 2026-06-30 | Phase 2.3/2.5 | **DEFERRED (profile-justified).** Re-profile after 2.1/2.2: `_evaluate_internal` tottime 1.37s→0.78s; `transposition.py` not in top-12. TT packing ≈1–2% for engine.py refactor risk; cache-eviction benefit not bench-visible. | Revisit at long TC if profile shifts. Remaining hotspots: movegen, SEE, eval. |
| 2026-06-30 | Phase 2.4 | **DONE but INERT — lazy eval doesn't pay for Hydra.** Windowed `evaluate` + `_cheap_eval` + `LazyMargin` tunable wired into qsearch. Margin 250 → +8% bench nodes, no NPS gain (eval already cheap; approximation destabilises qsearch). Default `lazy_margin=0` → bench 559253 exact. | Infra kept for Phase 5 SPSA to revisit post-refit. 2.7 (Lazy SMP) ⛔ blocked on CPython 3.13t. |
| 2026-06-30 | Phase 2.6 | **DONE — mypyc compiled build (~1.8×, cumulative Phase 2 ~3.2×).** 10 hot modules → C ext via `tools/build_mypyc.ps1` (working tree stays pure; compiled tree in git-ignored `tools/engines/compiled/`). uci/bench/syzygy uncompiled (ctypes safe). Fixed 2 mypyc-arg-check issues (movegen tuple annotation, `_PonderSwitch` list subclass). | bench 559253 + eval fp `c4e9c6109970e676` + uninterrupted depth-11 Kiwipete all identical pure-vs-compiled; pure tree 114 tests, ruff clean. |
| 2026-07-01 | Phase 2.6 gate | **mypyc CONFIRMED — SHIP IT.** SPRT mypyc vs pure @ 8+0.08: **+184.6 ± 30.9 Elo, H1, LOS 100%, 442 games, 74.3%** (1 pure-side timeout → Phase 6 TM, 0 crashes). | `bench_runtimes` depth-10 warm (all nodes=840811, bit-identical): CPython 38.8k · **mypyc 77.4k (2.00×)** · PyPy 35.4k (**0.91× — slower!**). Runtime question closed: ship mypyc, PyPy rejected (JIT can't speed big-int bitboards). **Phase 2 fully complete (~3.2× NPS, +185 Elo). Next: Phase 3.** |
| 2026-07-01 | release prep | CHANGELOG [Unreleased], README compiled-build section, mypy in `[build]` extra; **skipped standalone v1.5.0** (Phase 2 speed ships with v1.5.0=Phase 4); forward releases renumbered. | Version stays 1.4.1 (no cut yet). |
| 2026-07-01 | Phase 3.1 | **DONE — threats package, seeded inert.** weak/hanging + minor-on-major + rook-on-queen; per-side attack maps (full/minor/rook) accumulated in the mobility pass (substrate for 3.2). 6 weights default 0 + `threats_active` guard; trace() mirrored. | bench 559253 / eval fp `c4e9c6109970e676` / trace 0-mismatch exact on **pure and compiled**; non-zero-weight reconstruction 0-mismatch, term moves eval in 864/5000. Compiled ~71k NPS. **Next: 3.2 king-safety v2.** |
| 2026-07-01 | bench harness | **NEW fingerprint anchor `1 002 645` @ depth 9 (bench-only change; play/eval/search unchanged).** Ported Rarog/Basilisk 40-position suite (16 curated + 24 self-play, piece counts 30→8; legal white-a3 position 4). `bench [depth] [repeats]` (best-of-N NPS); added EBF / geomean-EBF / median / top-share diagnostics. | **Top-pos share 35%→12.3%** (no single position dominates). Deterministic across runs **and** pure-vs-compiled (1002645). 114 tests, ruff clean. Old anchor was 559253 over 16 positions. |
| 2026-07-01 | Phase 3.2 | **DONE — king-safety v2, seeded inert.** Explicit king-danger sum (base units + safe checks N/B/R/Q + king-ring weak squares + no-queen atten, all weights 0). Mobility pass → per-type attack maps; shared `_king_danger_extra` for evaluate()+trace() (KS residual, finite-diff in 4.3); `ks_v2_active` guard. | bench 1002645 / eval fp `c4e9c6109970e676` / trace 0-mismatch exact **pure and compiled**; non-zero-weight reconstruction 0-mismatch, moves eval in 1903/5000 (38%). Compiled ~70k NPS. **Next: 3.3 scale factors + winnable + rule50.** |
| 2026-07-01 | Phase 3.3 | **DONE — scale/winnable/rule50 framework, seeded inert.** Final-score transform: eg scale (OCB drawishness) + winnable (const/per-pawn/both-flanks) + rule-50 damping, all identity; guards `scale_active`/`winnable_active`/`rule50_damp=0`. EvalTrace carries (eg_scale, winnable, r50_num); shared `_final_transform` for evaluate()+trace(). mypyc: renamed local eg_w→eg_scaled (collided with flat PST array). | bench 1002645 / eval fp `c4e9c6109970e676` / trace 0-mismatch exact **pure and compiled**; non-zero reconstruction 0-mismatch, moves eval 4998/5000. Compiled ~70k NPS. **Next: 3.4 passed-pawn richness.** |
| 2026-07-01 | Phase 3.4 | **DONE — passed-pawn richness, seeded inert.** Shared `_passer_counts`: stop-square blocker, free path (empty+unattacked), passer protected by friendly pawn, enemy-king distance to queening square. 7 weights default 0 + `passers_v2_active` guard; trace() mirrored (consumes 3.1/3.2 attack maps). | bench 1002645 / eval fp `c4e9c6109970e676` / trace 0-mismatch exact **pure and compiled**; non-zero reconstruction 0-mismatch, moves eval 2344/5000. **Next: 3.5 imbalance.** |
| 2026-07-01 | Phase 3.5 | **DONE — imbalance terms, seeded inert.** Shared `_imbalance_terms`: piece counts × own pawn count (knight-likes-pawns, rook-hates-pawns, bishop-likes-pawns). 3 weights default 0 + `imbalance_active` guard; trace() mirrored. (Material-key dispatch-dict speed win deferred to Phase 4 hot-loop cleanup.) | bench 1002645 / eval fp `c4e9c6109970e676` / trace 0-mismatch exact **pure and compiled**; non-zero reconstruction 0-mismatch, moves eval 4980/5000. **Next: 3.6 space/bad-bishop/connected-rooks.** |
| 2026-07-02 | PLAN REWORK §8 | **Phases 5–11 reworked after deep review (user request; Rarog burned 30h SPSA for NEGATIVE gain).** Blanket SPSA demoted to optional 5.4 (default SKIP; EV≈0±10 at hobbyist budgets). New: 5 targeted-SPRT calibration (+4, 0…+12) · 6 search features, audit-verified missing: staged movegen/qsearch checks/TT aging/corr-hist family/gravity/cuckoo/LMR (+30, +15…+55) · 7 speed wave 2 (+12 via 5–15% NPS; compiled drifted 70k→67.5k) · 8 TM (+8) · 9 on-policy eval refresh reusing SPRT PGNs + annotate_sf (+10) · 10 Lazy SMP blocked · 11 NNUE with a HARD 2-day inference-NPS prototype gate (+80…+250 net). Per-phase Elo + model + reasoning level in §8. Evidence base: mypyc +184.6/2×, linfit +57, KS +19.6, evalmisc ≈0, Rarog SPSA<0. | **Recommend: cut v1.5.0 NOW (+260 banked), then Phase 5.** Note: 5.1 needs a tiny sprt.ps1 tweak (per-engine `option.X` passthrough, ~10 min) before its first SPRT. |
| 2026-07-02 | Phase 4.2 KS — **PHASE 4 COMPLETE** | **King-safety bundle BAKED, +19.6 Elo; Texel eval tuning done (~+77 cumulative).** Built a finite-difference tuner (`fit.py` `_fd_fit`) for nonlinear groups. Probe: base KS curve already well-calibrated to SF cp (raising ks_cap does nothing; scaling attacker weights up hurts MSE) → tuned only the KS-v2 safe-check extras (knight 7/bishop 5/rook 6/queen 5; weak-sq+no-queen→0). Holdout MSE only 0.019741→0.019540 (~1%) but **SPRT ks vs linfit @8+0.08: +19.59±9.32, LOS 100%, H1, 3124 games, 0 timeouts** — MSE badly under-values dynamic KS; the SPRT is the judge. Baked cumulatively → `tuned_eval.py` (926 wts). **scale/winnable/rule50 deferred to Phase 5 SPSA** (MSE makes them WORSE; FD `scale` group defined for that). **NEW anchors: bench 1185906→1101946, eval fp c4ceb797cbec0d4a→d21d497ae7d9ccef.** | Baked==candidate (1101946 pure==compiled), trace 0/5000, 114 tests. **Next: Phase 5 SPSA — re-tune cp-denominated search margins to linfit's new eval scale + deferred eval scalars.** |
| 2026-07-02 | Phase 4.2 linfit | **BAKED — first shipped eval tuning, +57 Elo.** Re-annotated 2.1M positions with SF dev-20260630 raw cp (`annotate_sf.py`, `go nodes 60k`; saturation 26.6%→1.1%, corr +0.69). Combined fit of all 9 LINEAR groups (material+mobility+pawns+PST+passers+pieces+imbalance+minor+threats) `--cp-labels --fix-k 1` (K-anchor kills inflation): holdout MSE 0.0259→0.0198, values sane (max|w|=1275). **SPRT linfit vs base @8+0.08: +56.99±17.94, LOS 100%, H1, 1218 games, 58.13%, 0 crashes.** Baked 922 weights → `hydra/tuned_eval.py` (uncompiled module; overlaid in EvalParams.__init__ — a big literal in the compiled evaluation.py overflows MSVC), via `tools/texel/bake.py` (cumulative). **NEW anchors: bench 1002645→1185906, eval fp c4e9c6109970e676→c4ceb797cbec0d4a.** Also PV 50-move display fix (aad3e30). | Baked==candidate (1185906 pure==compiled), trace 0/5000, 114 tests. **Next: nonlinear bundles — king-safety, then scale/winnable/rule50 — need a finite-difference tuner path (linear surrogate doesn't apply).** |
| 2026-07-02 | Phase 4 diagnosis | **bundle1 SPRT: H1 accepted but weak (+10.54±7.01, LOS 99.84%, 7948 games, 14 timeouts) → NOT baked; root-caused and superseded.** (1) **Label pathology**: legacy labels = old-SF depth-10 `wdl().expectation()` (net_trainer) — SF's WDL squash is far steeper than a Texel logistic; measured 26.6% of train labels fully saturated (17% exactly 0/1) → no magnitude gradient in tails → material inflation (Q 900→1308) + degraded cp-margin/search interaction. (2) **bundle1 only refit textbook terms** — all Phase-3 inert terms still 0; most projected Elo sits in bundles 2–4 regardless. (3) **Timeouts (fixed, e4d2e1d)**: TM banked the increment before it is credited (soft=base+inc·0.75 could exceed the clock; now capped at 80% remaining), clock polled every 4096 nodes (~60ms@70k NPS; now 1024), forced-move fast path sent bestmove with no scored info line (fastchess warnings; now emits one). Bench 1002645 exact, 114 tests. | **Relabel path (4.1b, 3dab931)**: user compiled SF dev-20260630 → `annotate_sf.py` (multi-worker UCI, `go nodes 60k` ≈ depth 16-18, `FEN;cp` White-POV, resume/merge; validated corr +0.705 vs +0.59 WDL, no saturation). `fit.py --cp-labels --fix-k 1` anchors eval to SF's normalized cp scale (100cp≈1 pawn) — kills the inflation channel. **Next: user runs annotation (~2.5-4h), then refit + re-SPRT.** |
| 2026-07-01 | Phase 4.2 | **Campaign infra + bundle-1 candidate ready (awaiting SPRT).** SPRT cadence = **hybrid** (user pick): 4 bundles — (1) material+mobility+pawns+PST, (2) passers+pieces+imbalance+minor+threats, (3) king-safety, (4) scale/winnable/rule50. **`HYDRA_EVAL_FILE` loader** (evaluation.py, env-gated, mypyc-safe, applied at import before board.py captures PSQT arrays → consistent; off=1002645/fp unchanged). `run_hydra.cmd` 2nd arg + `sprt.ps1 -EvalFileA` (wrapper .cmd) → one compiled build SPRTs itself with two weight sets. `fit.py` bundle mode (sequential stages, private params, invalidate_caches for ground-truth holdout). | **bundle1** (200k/300ep): train MSE 0.0574→0.0489, **holdout 0.0556→0.0475 (−14.5%)**, 889 wts → `tools/texel/data/bundle1.txt` (git-ignored). Candidate bench 1184879 identical pure==compiled; 114 tests. **Next: user runs bundle1 SPRT.** |
| 2026-07-01 | Phase 4.2 | **Tooling built + material stage validated (offline; no SPRT yet).** `tools/texel/fit.py`: staged Adam fit with an **exact linear surrogate** `eval_white(w)=A·w+b` (phase taper + frozen 3.3 transform are per-position constants → linear in the weights; self-check |model−eval|=0.000). numpy dev dep in `[tune]` extra. Linear groups material/mobility/pawns/passers/threats/imbalance/minor/pieces/pst; KS + scale need a finite-diff path (TODO). Material fit (400k/400ep): train MSE 0.0573→0.0548, **holdout 0.0556→0.0534 (improves)**; piece values run heavy (Q 900→1308 mg) as expected for a WDL target. **Next: pick SPRT cadence, then bake+gate.** |
| 2026-07-01 | Phase 4.1 | **DONE — Texel dataset prep; label source DECIDED = Beast Stockfish-WDL (not self-play).** Found Beast `evaluated/` (123 shards ≈123M positions, `FEN<TAB>SF-win-prob`, stm POV, 1:1 with positions.txt). Chose SF-WDL over the siblings' self-play: Hydra self-play is ~30–50× slower (~20–34h/regen vs <1h native), SF labels free+denser+stronger, SPRT gates transfer. `import_beast.py` (engine SEE quiet-filter, phase-balanced reservoirs, dedup, disjoint holdout, stm→White POV, no cp conversion); `tune.py --verify` reconstruction gate + `--find-k` corr. | small run (400k scan, 3k/bucket): recon 0/5000, K=0.967, **corr eval↔target +0.579** (raw +0.42), target mean 0.553. Data git-ignored; self-play kept as documented fallback. Recommended real run: `--per-bucket 400000 --max-scan 20000000` (~2M, ~27min). **Next: 4.2 staged fit.** |
| 2026-07-01 | Phase 3.6 | **DONE — space + bad bishop + connected rooks, seeded inert. PHASE 3 COMPLETE.** Shared `_minor_terms`: safe central space (files c-f, own half, not enemy-pawn-attacked), bad bishop (own pawns on each bishop's colour), connected rooks (rooks defending each other). 5 weights default 0 + `minor_terms_active` guard; new light/dark-square + central masks; trace() mirrored. | bench 1002645 / eval fp `c4e9c6109970e676` / trace 0-mismatch exact **pure and compiled**; non-zero reconstruction 0-mismatch, moves eval 4040/5000. **Phase 3 done — eval structure fully built + trace-ready. Next: Phase 4 Texel campaign (v1.5.0).** |

---

## 11. Release discipline

Releases are **explicit steps** so they are not forgotten. Version is bumped in
`pyproject.toml` (and any `__init__`/spec that carries it).

**Version map (SemVer-adapted):**

| Version | After | Theme |
|---|---|---|
| — | Phase 2 | **No standalone release** (speed-only; the ~3.2× NPS ships bundled with v1.5.0). |
| **v1.5.0** | Phase 4 | **Phase 2 speed (compiled build) + tuned evaluation** — major strength jump |
| **v1.6.0** | Phase 5 + 6 | Tuned search constants + time management |
| **v1.7.0** | Phase 7 (+ 8) | Search-efficiency refinements + eval-refresh maturity |
| **v2.0.0** | Phase 9 | NNUE (architectural change) |

Patch releases (`v1.5.1`, …) for a single follow-up fix or a deferred sub-step.

**Release-checkpoint procedure (the agent runs prep; the user does the
release):**
1. **Agent:** bump version in `pyproject.toml`; run the full suite + `bench`
   (record fingerprint); run a final SPRT of the release candidate vs the
   previous release tag (expect clearly positive); update `CHANGELOG.md`, §10,
   and the guide. Commit on `development`. State **"ready to release vX.Y.Z."**
2. **User:** squash all `development` commits since the last release into a
   single **`Version X.Y.Z`** commit, cherry-pick it onto `master`, push.
3. **User:** ask the agent for **release notes** (agent drafts from the §10 log
   + CHANGELOG + the squashed diff).
4. **User:** create the GitHub release (tag `vX.Y.Z`, attach the built
   executables — built with the §5 2.6 runtime).
5. **After release:** reset `development` onto the new `master` HEAD so histories
   don't diverge, and continue. — **Model for prep/notes: Sonnet 4.6 medium.**

---

## 12. Quick command reference

```powershell
# Tests
& .venv\Scripts\python.exe -m pytest -q

# Bench fingerprint (refactor gate; must equal 1101946 @ depth 9, 40-pos suite, until behaviour changes)
# (was 1002645 pre-tuning; moved to 1185906 when linfit was baked 2026-07-02)
"bench 9`nquit" | & .venv\Scripts\python.exe -m hydra

# SPRT a candidate (gate TC = clock 8+0.08); Phase 0.3 builds sprt.ps1
.\tools\sprt.ps1 -EngineA <cand> -EngineB <baseline> -TC "8+0.08" -Concurrency <cores-1>

# Calibration (must accept H0, ~0 Elo, zero forfeits)
.\tools\sprt.ps1 -EngineA <baseline> -EngineB <baseline> -Elo0 -3 -Elo1 3

# SPSA (Phase 0.4; needs Phase 1 options)         | Texel fit (Phase 0.5; offline, may use numpy)
& .venv\Scripts\python.exe tools\spsa\tune.py     | & .venv\Scripts\python.exe tools\texel\tune.py --stage material

# Profile a hot path (Phase 2)
& .venv\Scripts\python.exe -m cProfile -s tottime -m hydra   # then: bench 9 / quit
```

---

## 13. Reference

- Sibling plans: `D:\code\rarog\PLAN.md` + `user_dev_guide.md` (Rust),
  `D:\code\basilisk\PLAN.md` + `user_dev_guide.md` (C++) — proven shape of the
  Texel campaign, SPSA grouping, and release discipline.
- The removed *lite* line proved the Python levers this plan leans on:
  incremental eval accumulators (2.6× NPS), a self-contained Hydra-native SPSA
  driver, and that small-sample quickmatches mislead near 50% — trust SPRT.
- Sources consulted this revision: Stockfish (correction history, cuckoo
  upcoming-repetition, initiative/winnable, scale factors) and the
  chessprogramming wiki; Python speed (mypyc 2.4–14×, PyPy 6–66×, Cython highest,
  Nuitka mypyc-range).
