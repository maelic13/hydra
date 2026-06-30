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
   reproduce current behaviour exactly: the `bench` fingerprint (**559 253 @
   depth 9**, baseline 2026-06-29) must be **identical**, *and* `evaluate()` must
   match on the **eval-equivalence corpus** (a balanced ~50k-FEN sample from
   `A:\Chess\Beast\data\txt\positions.txt`, extracted once in Phase 0.6) before
   tuning begins. Record a fresh anchor whenever behaviour intentionally changes.
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
| **1** | Expose search constants + tunable `EvalParams` refactor | bench + corpus identical | — |
| **2** | Python speed wave (incr-eval, lazy eval, packed TT, attack-map reuse, **faster build**, **Lazy SMP**) | identical parts no games; lazy eval / SMP SPRT-gated | **v1.5.0** |
| **3** | Eval structure completion (threats, KS-v2, scale/winnable/rule50, passers, imbalance, minor terms) — seeded inert | bench + corpus identical | — |
| **4** | Texel eval data-fit campaign (staged; PST/material last) | per-stage SPRT | **v1.6.0** |
| **5** | Search-constant SPSA wave (once, final scale) | confirming SPRT | — |
| **6** | Time-management hardening + TM SPSA + clock-TC validation | SPRT (+ LTC) | **v1.7.0** |
| **7** | Search-efficiency refinements (corr-hist family, cuckoo, history formula, fractional LMR, qsearch checks, TT aging, staged movegen) | per-feature SPRT | **v1.8.0** |
| **8** | Eval-refresh cycles — non-NNUE ceiling | per-cycle SPRT | (roll into v1.8.x) |
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

Make every constant Phases 4/5 will tune *reachable*, without changing
behaviour. `bench` must stay 559 253 @ depth 9 and `evaluate()` must match on the
Phase-0.6 corpus.

- **1.1 Expose search constants as UCI spin options (behind a `Tune` flag).**
  `ASPIRATION_WINDOW`, `_REVERSE_FUTILITY_MARGIN`, `_RAZORING_MARGIN`,
  `_FUTILITY_MARGIN`, `_DELTA_MARGIN`, `_LMP_BASE`, NMP base+divisor, the `_LMR`
  log-formula coefficients (0.5 / 1.6), history-pruning thresholds, SEE-pruning
  depth multipliers, ProbCut margin, singular margins/depths. Read from a params
  object defaulting to today's values; keep release UCI clean. **Gate:**
  bench-identical. — **Model: Sonnet 4.6 medium.**
- **1.2 Refactor eval weights into a tunable `EvalParams` table
  (default-equivalent — the big infra step).** Move every magic number in
  `evaluation.py` (piece values, all PST entries, bonuses/penalties, mobility
  tables, king-safety weights + quadratic) behind a parameter object whose
  defaults reproduce current values bit-for-bit. Tune-time loader (file/UCI);
  releases run baked defaults. **Gate:** bench-identical + corpus reconstruction
  exact. **Trap:** one wrong PST orientation silently poisons the whole campaign.
  — **Model: Opus 4.8 high** (review the diff).
- **1.3 Eval-coefficient trace (tune-only mode).** `evaluate` also returns the
  per-position **coefficient vector** (count of each weight's application, MG/EG,
  with the phase blend) for the Texel gradient. **Gate:** `sum(coeff·weight)`
  tapered == `evaluate()` on the corpus. — **Model: Opus 4.8 high.**

---

## 5. Phase 2 — Python speed wave (the Hydra-specialized phase) → release v1.5.0

Behaviour-identical speed never invalidates tuning, and in CPython NPS converts
to real Elo at a fixed clock *and* makes every later game cheaper. Profile with
`cProfile` before/after each step; record NPS in §10.

- **2.1 Incremental eval accumulators (behaviour-identical — biggest NPS lever).**
  Maintain running `mg`, `eg`, `phase` on the `Board`, updated in
  `make_move`/`unmake_move` where the Zobrist hash is, so the per-node
  material+PST loop disappears. The *lite* line measured **2.6×**. Output
  unchanged → no re-tune; the Phase-4 PST refit just changes summed values.
  **Gate:** bench-identical (node count same, NPS up), perft + suite green.
  — **Model: Opus 4.8 high** (make/unmake correctness; perft gate).
- **2.2 Attack-map compute-once (behaviour-identical + structure enabler).**
  `evaluate` recomputes sliding attacks for mobility and again for king safety.
  Compute per-side per-piece attack bitboards **once**, reuse across
  mobility/king-safety/(future) threats. Speed win + the substrate Phase 3 needs.
  **Gate:** bench-identical. — **Model: Opus 4.8 medium.**
- **2.3 Packed TT (behaviour-identical — Python-specific).** Replace
  object-per-entry `list[TTEntry|None]` with packed ints in a flat list/`array`;
  a store mutates ints in place, no `TTEntry` allocation. Keep depth-preferred
  replacement identical. **Gate:** bench-identical (NPS up). — **Model: Sonnet
  4.6 medium.**
- **2.4 Lazy eval (behaviour-CHANGING — SPRT-gated; durable NPS lever).** Compute
  material+PST(accumulator)+pawn-cache first; if far outside `(alpha,beta)` by a
  lazy margin, return it and skip mobility/king-safety/threats. The lazy margin
  is cp-denominated → **confirm it in the Phase-5 SPSA**. **Gate:** SPRT
  (`elo1=0`: keep if ≥0). — **Model: Opus 4.8 high.**
- **2.5 Cache-eviction polish (behaviour-identical).** The eval/pawn caches
  wholesale-clear when full; switch to bounded eviction / generation tagging.
  **Gate:** bench-identical. — **Model: Sonnet 4.6 medium.**
- **2.6 Faster runtime/compiler — the pext/PGO analog (RESEARCH + SHIP).**
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

> **Release v1.5.0** after Phase 2 (see §11): first shipped strength/speed gain.
> If 2.6/2.7 lag, ship 2.1–2.5 as v1.5.0 and the build/threads work as v1.5.1.

---

## 6. Phase 3 — Eval structure completion (seeded inert; no games)

Add the terms Hydra lacks, **all seeded zero-effect or current-equivalent**, so
`bench`+corpus are unchanged and Phase 4 fits them in **one** campaign. Each
consumes the Phase-2.2 attack maps.

- **3.1 Threats package** (seeded inert): weak/hanging (attacked-undefended)
  pieces, minor-attacks-rook/queen, rook-attacks-queen, pawn-push threats,
  restricted squares. Hydra has only a flat pawn-threat term. — **Model: Opus 4.8
  high.**
- **3.2 King-safety v2** (seeded ≈ current): structured king-danger sum —
  attacker count × weight scaling, **safe checks** (checks on undefended
  squares), king-ring weak squares, queen-contact, no-queen attenuation, pawn
  shelter/storm, flank attacks. Default reproduces today's output. — **Model:
  Opus 4.8 high (max reasoning).**
- **3.3 Scale factors + endgame knowledge + winnable/rule50** (seeded scale=1.0,
  winnable=0 — Hydra's biggest correctness gap; today only insufficient-material
  draw): OCB drawish scaling, KPK, KBNK, KRKP, KQKP, lone-minor-can't-win,
  drawish-material downscaling — multiplicative scale on the EG score. **Plus**
  an **initiative/winnable** correction (pawns-on-both-flanks, pawn count,
  opposite bishops, infiltration → pushes the score toward/away from draw) and
  **rule-50 damping** (scale eval down as `halfmove` climbs). — **Model: Opus 4.8
  high.**
- **3.4 Passed-pawn richness** (extend, seeded equivalent): blocker penalty,
  free/unsafe-path control, **both** kings' distance to the queening square,
  candidate (not-yet-)passers, connected/protected passers. — **Model: Opus 4.8
  medium.**
- **3.5 Material-key table + imbalance** (seeded 0 imbalance, identity dispatch):
  a dict keyed by **material key** caching the imbalance score, game phase, and
  the scale/endgame-function selector (from 3.3). Pairwise piece-combination
  imbalance (knight-pair, rook-redundancy, bishop-vs-knight by pawn count). Also
  a Python **speed** win (avoids recomputing material-only terms). — **Model:
  Opus 4.8 high.**
- **3.6 Space + small positional terms** (seeded 0): space-behind-pawns centre,
  **bad bishop** (own pawns on bishop's colour), minor-behind-pawn, trapped
  rook/bishop, connected rooks, rook-on-closed-file, queen-pin. — **Model: Sonnet
  4.6 medium.**

**Gate (all of Phase 3):** bench-identical + corpus reconstruction + suite. No
self-play games until Phase 4.

---

## 7. Phase 4 — Texel eval data-fit campaign (the multiplier) → release v1.6.0

The biggest Elo pool. Fit the whole enlarged eval **once**.

- **4.1 Dataset prep from `A:\Chess\Beast\data\txt\positions.txt`.** The file is
  **122.66M label-free FENs**, diverse by construction (ICCF computer chess →
  human club). We **do not generate games** — we prepare labelled, balanced data
  from these:
  1. **Labeling (no results are stored in the file — decision point).** Texel
     needs a target per position. Recommended primary: **score each sampled
     position with a strong reference engine** (e.g. Stockfish, if available
     locally) at a shallow fixed depth/nodes → convert to a WDL target via the
     standard logistic. Fallback if no reference: self-label with Hydra's own
     deepened search (weaker, mildly circular). *Surface the reference-engine
     choice to the user before the big run.*
  2. **Quiescence filter (standard Texel hygiene):** drop positions in check or
     where a capture/promotion is best; keep only positions whose static eval ≈
     qsearch eval (run qsearch, keep the resolved quiet position). Noisy
     positions corrupt the gradient.
  3. **Phase balancing — "good mix of opening / middlegame / endgame."** Bucket
     by game phase (the eval's `phase` value / total non-pawn material): opening
     ≈ phase 24, middlegame ≈ 12–23, endgame < 12 (and a deep-endgame ≤6 bucket).
     **Sample evenly across buckets** so no phase dominates — with 122.66M
     positions there is plenty of each; the risk is over-representing crowded
     middlegames, so cap per bucket. De-duplicate by position.
  4. **Subsample + split:** take a balanced **~1–5M** training set + a disjoint
     holdout; **split by source/position carefully** (no leakage). Larger isn't
     always better for Texel — balance and quietness matter more.
  5. **Reconstruction-gate** the extraction (trace coeffs · weights == eval)
     before fitting.
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

> **Release v1.6.0** after Phase 4 — the major strength jump.

---

## 8. Phase 5 — Search-constant SPSA wave (once, at final eval scale)

Now a centipawn means its final thing. Group the Phase-1.1 options and tune them
together at the gate TC (== SPSA TC, rule 5): RFP/razoring/futility/delta margins,
the **lazy-eval margin (2.4)**, LMP base, NMP base+divisor, LMR coefficients,
history-pruning thresholds, SEE-pruning multipliers, ProbCut margin, singular
margins, aspiration window. SPSA proposes → review vs bounds (rule 10) → one
confirming SPRT decides. Clean H0 means the textbook values were already
near-optimal (valid, logged). — **Model: Sonnet 4.6 medium** to drive the
loop; **Opus 4.8 medium** to review degenerate/pinned constants.

---

## 9. Phases 6–9

### Phase 6 — Time management hardening + tuning → release v1.7.0
`_compute_time_limits` is sensible but hand-guessed (`remaining/25`, the
0.20/0.30/0.50 hard-cap tiers, `inc*0.75`, the 0.06 stability scale). Work:
harden against GUI time-losses (the lite line had forfeits); add **node-based
TM** (allocate by fraction of nodes spent on the best move) and **instability
extension** (extend on root fail-low / best-move change / big score drop); then
**SPSA the TM constants** at clock TCs with an **LTC confirmation**. Re-validate
after any NPS-changing step (2.x/2.6/2.7). — **Model: Opus 4.8 medium** (formula),
**Sonnet 4.6 medium** (SPSA driving). Ships as **v1.7.0** with Phase 5.

### Phase 7 — Search-efficiency refinements → release v1.8.0
Each its own SPRT; smaller than the siblings' wave since Hydra has most search
features already.
- **Correction-history family** — add non-pawn (per-side), major, minor, and
  **continuation** correction histories alongside today's pawn-keyed one (the
  README already advertises non-pawn corr-hist that `engine.py` doesn't
  implement — close that gap). — **Model: Opus 4.8 high.**
- **Upcoming-repetition / cuckoo cycle detection** (SF10) — precompute the cuckoo
  tables of reversible-move Zobrist deltas; in-search, detect a reachable
  repetition and return a draw score / prune. Correctly handles many fortress and
  shuffle positions. — **Model: Opus 4.8 high** (subtle algorithm + correctness).
- **History-gravity formula upgrade** (bonus/malus with gravity toward 0 instead
  of plain add + clamp). — **Model: Sonnet 4.6 medium.**
- **Fractional/finer LMR** (sub-ply reductions accumulated, vs the integer
  table). — **Model: Opus 4.8 medium.**
- **Qsearch quiet checks at the first ply.** — **Model: Sonnet 4.6 medium.**
- **TT replacement upgrade** — generation/aging + optional 2-entry bucket, vs
  today's single depth-preferred slot. — **Model: Sonnet 4.6 medium.**
- **Staged move generation** (Python win: don't score all moves when the TT move
  cuts — generate/score lazily by stage). — **Model: Opus 4.8 medium.**
- Double-extension cap tuning, razoring/IIR depth-limit experiments. — **Model:
  Sonnet 4.6 medium.**

### Phase 8 — Eval-refresh cycles (non-NNUE ceiling)
Regenerate labels with the stronger head (re-score the positions.txt sample with
the improved engine, or a stronger reference), refit the eval (Phase 4
machinery), 1–3 cycles, stop when a cycle no longer passes SPRT. Banks
tuning-maturity Elo without new features. Roll into a **v1.8.x**. — **Model:
Sonnet 4.6 medium.**

### Phase 9 — NNUE (terminal option; the real ceiling-raiser) → release v2.0.0
Keep the eval boundary clean (rule 7) so this stays possible. **The Python
problem:** pure-Python NNUE inference (interpreted matrix mults) is far too slow
to net a gain at Hydra's NPS, and a numpy dependency breaks "no runtime deps."
Research before committing: (a) numpy-backed inference accepting the dependency;
(b) a deliberately tiny int16 net with hand-rolled incremental accumulator
updates; (c) NNUE only in a PyPy/mypyc build (§5 2.6) where the inference loop is
compiled/JITed. A project, not a step — scope only after Phases 4–8 plateau.
Major version bump **v2.0.0**. — **Model: Opus 4.8 high (max reasoning).**

---

## 10. Results log (append-only — newest last)

| Date | Phase/Step | Result | Notes / numbers |
|---|---|---|---|
| 2026-06-29 | audit | PLAN + user_dev_guide created | v1.4.1; search complete, eval complete-but-untuned, no harness. Bench anchor: **559 253 nodes @ depth 9, ~23.4k nps**. |
| 2026-06-29 | revision | data source + releases + models + research items added | Texel source = `A:\Chess\Beast\data\txt\positions.txt` (122.66M label-free FENs). Added: faster-build (mypyc/PyPy/Cython, §5 2.6), Lazy SMP threading (§5 2.7), corr-hist family + cuckoo (§9 Phase 7), winnable/rule50 + scale factors (§6 3.3), material-key table (§6 3.5), node-based/instability TM (§9 6). Release checkpoints v1.5.0/1.6.0/1.7.0/1.8.0/2.0.0. Work moved to `development` branch. |
| 2026-06-29 | Phase 0 | **0.1–0.6 DONE; 0.7 pending (user-run).** Harness built: fastchess v1.8.0-alpha, run_hydra.cmd shim (`-S` isolation verified), snapshot_engine.ps1, sprt.ps1, spsa/tune.py+config (scaffold), texel/tune.py (smoke OK), build_data.py, eval_equiv.py. | Corpus 5000 FENs phase-balanced (1000×5); book 3000; **eval-equiv fingerprint `c4e9c6109970e676`** (0 unparseable); engine handshake clean via shim. Gate TC locked `tc=8+0.08`. Next: user runs calibration SPRT. |
| 2026-06-30 | 0.7 calibration | **PASS — harness healthy. Phase 0 CLOSED.** 1016 games self-play (S1 vs S2), **48.57%, Elo −9.92 ± 16.73** (0 within CI → no bias), 0 crashes/disconnects/illegal. SPRT can't converge (true≈0 between ±3 bounds), stopped by design. | Only anomaly: 1 time-loss in 1016 (~0.1%) → bumped `sprt.ps1` Move Overhead 10→50ms to protect gain SPRTs (`timeouts>0`=void); root TM hardening stays Phase 6. Benign fastchess warnings (PV-past-draw, no-score-on-quick-return) noted for a Phase 7 cosmetic cleanup. **Next: Phase 1.1.** |

---

## 11. Release discipline

Releases are **explicit steps** so they are not forgotten. Version is bumped in
`pyproject.toml` (and any `__init__`/spec that carries it).

**Version map (SemVer-adapted):**

| Version | After | Theme |
|---|---|---|
| **v1.5.0** | Phase 2 | Faster engine (incremental/lazy eval, packed TT, compiled build, threads) |
| **v1.6.0** | Phase 4 | Tuned evaluation — major strength jump |
| **v1.7.0** | Phase 5 + 6 | Tuned search constants + time management |
| **v1.8.0** | Phase 7 (+ 8) | Search-efficiency refinements + eval-refresh maturity |
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

# Bench fingerprint (refactor gate; must equal 559253 @ depth 9 until behaviour changes)
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
