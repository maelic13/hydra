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
- **State (2026-07-01):** Search is **feature-complete**. Harness done (Phase 0),
  constants+eval exposed and coefficient-traced (Phase 1), Python speed wave +
  mypyc compiled build done (Phase 2, +184.6 Elo), and the **eval structure is
  fully built and seeded inert** (Phase 3 complete). Every weight is still an
  **untuned textbook constant / 0-seed** — the whole enlarged eval is fit **once**
  in Phase 4 (Texel), the biggest remaining Elo pool.
- **Bench anchor:** `1 002 645 nodes @ depth 9` (40-position suite matching
  Rarog/Basilisk, adopted 2026-07-01; was 559 253 over 16 positions). The
  refactor fingerprint — must not change on a pure refactor. `bench [depth]
  [repeats]`; reports EBF / median / top-share diagnostics + best-of-N NPS.
- **Texel data:** `A:\Chess\Beast\data\txt\positions.txt` — **122.66M diverse,
  label-free FENs** (ICCF computer chess → human club). We do **not** generate
  more; we label + balance these (Phase 4.1). Also the source of the ~50k
  eval-equivalence corpus used by the refactor gates (Phase 0.6).
- **Thesis:** biggest free Elo = *tuning the complete-but-untuned eval* + *making
  CPython faster*. Build the harness, expose the knobs, speed up the interpreter,
  complete the eval structure, then fit it **once**.

## Next action

> **Phase 4 relabel in progress (2026-07-02).** bundle1 SPRT accepted H1 but weak
> (+10.5±7.0, 7948 games) → **not baked**; root causes found: (1) legacy labels
> (old-SF depth-10 WDL-expectation from net_trainer) are 26.6% saturated → no
> magnitude gradient, material inflation; (2) bundle1 only refit textbook terms
> (Phase-3 inert terms still 0 — their Elo sits in bundle 2+); (3) three TM/info
> defects caused the 14 timeouts + fastchess warnings — **fixed** (e4d2e1d: hard
> cap ≤80% of remaining clock, 1024-node time polls, forced-move info line).
>
> **New label path (4.1b):** your SF dev-20260630 re-annotates our curated 2.1M
> positions with **raw White-POV cp** at `go nodes 60000` (≈depth 16-18 vs the
> legacy depth 10). The tuner squashes cp through one consistent K=1 logistic and
> fits with **K pinned at 1** — anchoring Hydra's eval to SF's normalized cp
> scale (100cp ≈ 1 pawn), so search margins keep meaning (no inflation channel).
> Validated on 600 positions: corr +0.705 (vs +0.59 WDL), no saturation.
>
> **Run the annotation (you run this — ~2.5–4 h at 12 workers, resume-safe;
> rerun the same command to resume if interrupted):**
> ```powershell
> & .venv\Scripts\python.exe tools\texel\annotate_sf.py `
>     --input tools\texel\data\beast_train.csv --out tools\texel\data\sf_train.csv `
>     --nodes 60000 --workers 12
> & .venv\Scripts\python.exe tools\texel\annotate_sf.py `
>     --input tools\texel\data\beast_holdout.csv --out tools\texel\data\sf_holdout.csv `
>     --nodes 60000 --workers 12
> ```
> Paste the tail output back. Then I refit (bundle1+2 combined this time — the
> linear groups incl. the inert Phase-3 terms) with `--cp-labels --fix-k 1` and
> hand you ONE SPRT with a much larger expected effect.
>
> *Workflow reminder:* the agent never runs SPRT/SPSA — I prepare, you run and
> paste back the result line.

Say **"continue"** after the annotation finishes (paste the summary).

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
- [x] **Phase 3 — Eval structure completion** *(DONE 2026-07-01; seeded inert, no games; bench 1002645 pure+compiled at every step)*
  - [x] 3.1 threats package (weak/minor-major/rook-queen; inert; verified pure+compiled)
  - [x] 3.2 king-safety v2 (safe checks + weak squares + no-queen; per-type attack maps; inert)
  - [x] 3.3 scale factors + winnable + rule50 (final-score transform, inert; EvalTrace extended)
  - [x] 3.4 passed-pawn richness (blocker/free-path/protected/enemy-king-dist; inert)
  - [x] 3.5 imbalance terms (knight/rook/bishop × pawn count; inert)
  - [x] 3.6 space + bad-bishop + connected-rooks (inert)
- [~] **Phase 4 — Texel eval data-fit campaign** *(+80–160 Elo)* → **release v1.5.0**
  - [x] 4.1 dataset prep — label source = **Beast Stockfish-WDL** (not self-play; ~30–50× cheaper for Python). `import_beast.py` (quiet-filter+phase-balance+dedup), `tune.py --verify/--find-k` (recon 0/5000, corr +0.58) `O-hi`
  - [~] 4.2 staged fit — fitter (`fit.py`, linear surrogate+Adam) + `HYDRA_EVAL_FILE` loader done; **hybrid SPRT cadence** (4 bundles); bundle1 candidate ready (holdout −14.5%), awaiting SPRT `S-med` (KS/scale `O-hi`)
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

# Bench fingerprint (must equal 1002645 @ depth 9 (40-pos suite) on a pure refactor)
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
