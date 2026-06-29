# Hydra Development Workflow Guide

Your single source of truth for the day-to-day loop. The full reasoning lives in
**`PLAN.md`**; this file is the checklist, the cheat-sheet, and the **"Next
action"** pointer. The two are kept in lockstep — if they ever disagree,
`PLAN.md` wins and the guide is stale (fix it).

---

## Current checkpoint

- **Engine:** Hydra v1.4.1 — Python UCI engine in `hydra/`.
- **State (2026-06-29):** Search is **feature-complete** (PVS, TT, NMP, LMR,
  RFP, razoring, futility, LMP, history pruning, SEE, ProbCut, singular
  extensions, IIR, correction history, mate-distance pruning, Syzygy, stability
  TM). Eval is a **complete classical HCE** — but **every weight is an untuned
  textbook constant**, and there is **no harness** (no SPRT/SPSA/Texel) yet.
- **Bench anchor:** `559 253 nodes @ depth 9`, ~23.4k nps (dev box). This is the
  refactor fingerprint — it must not change on a pure refactor.
- **The thesis:** the biggest free Elo is *tuning the complete-but-untuned eval*
  and *speeding up CPython*. We build the harness, expose the knobs, speed up the
  interpreter, complete the eval structure, then fit it **once**.

## Next action

> **Phase 0.1 — install fastchess** to `tools/bin/fastchess.exe`, then build the
> launch shim (0.2) and `tools/sprt.ps1` (0.3), and run the **calibration SPRT**
> (engine vs identical engine, `-Elo0 -3 -Elo1 3`). It must accept **H0** with
> zero forfeits before any strength work begins.

Say to the dev agent: **"Implement the next step in PLAN.md."**

---

## The basic rhythm (ping-pong loop)

1. **Pick the model** for the next step (tier in the tracker below; dense
   eval/correctness steps want the strongest model).
2. Say **"Implement the next step in PLAN.md."**
3. The agent edits, runs its local self-checks (tests + bench fingerprint), then
   prints **one command** for you to run.
4. You run it — a `bench`/test for refactors, an SPRT (or SPSA/Texel) for
   strength steps — and paste the result back.
5. The agent banks (commit, tick the box, log §10) or reverts, and updates the
   "Next action" pointer. **Timeouts/crashes/illegal-moves > 0 = void run** —
   fix the harness, not the engine.

**Python advantage:** no build step. fastchess runs `python -m hydra` directly,
so candidates are testable immediately and reverts are `git restore`.

---

## Phase progress tracker

Legend: `[ ]` todo · `[~]` in progress / awaiting gate · `[x]` done · `[R]` reverted.

- [ ] **Phase 0 — Harness** *(enabler)*
  - [ ] 0.1 fastchess installed · 0.2 launch shim · 0.3 `sprt.ps1`
  - [ ] 0.4 SPSA driver · 0.5 Texel tuner · 0.6 dataset + book
  - [ ] 0.7 **calibration accepts H0** (gate to leave Phase 0)
- [ ] **Phase 1 — Expose constants + tunable-eval refactor** *(bench-identical)*
  - [ ] 1.1 search constants → UCI options · 1.2 `EvalParams` table · 1.3 eval-coefficient trace
- [ ] **Phase 2 — Python speed wave** *(+30–80 Elo)*
  - [ ] 2.1 incremental eval accumulators · 2.2 attack-map compute-once · 2.3 TT packing
  - [ ] 2.4 lazy eval (SPRT) · 2.5 cache eviction · 2.6 **PyPy experiment** (go/no-go)
- [ ] **Phase 3 — Eval structure completion** *(seeded inert, no games)*
  - [ ] 3.1 threats package · 3.2 king-safety v2 · 3.3 scale factors / EG knowledge
  - [ ] 3.4 passed-pawn richness · 3.5 material imbalance · 3.6 space + small terms
- [ ] **Phase 4 — Texel eval data-fit campaign** *(+80–160 Elo, the multiplier)*
  - [ ] 4.1 dataset · 4.2 staged fit (material → mobility → pawns → passers → KS → threats → PST/material last)
- [ ] **Phase 5 — Search-constant SPSA wave** *(+20–50 Elo, once, final scale)*
- [ ] **Phase 6 — Time management hardening + SPSA** *(+5–25 Elo, clock TCs)*
- [ ] **Phase 7 — Search-efficiency refinements** *(+10–40 Elo)*
  - [ ] non-pawn corr-hist (README claims it; not yet implemented) · history-gravity · fractional LMR · qsearch checks · TT aging
- [ ] **Phase 8 — Eval-refresh cycles** *(+10–30, diminishing)*
- [ ] **Phase 9 — NNUE** *(terminal; Python-inference is the design problem)*

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

# SPSA (needs Phase 1 UCI options)
& .venv\Scripts\python.exe tools\spsa\tune.py

# Texel fit (offline; may use numpy)
& .venv\Scripts\python.exe tools\texel\tune.py --data <set> --stage <name>

# Profile a hot path (Phase 2)
& .venv\Scripts\python.exe -m cProfile -s tottime -m hydra <<< "bench 9`nquit"
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
- **Default-equivalence before tuning:** refactors must keep the bench
  fingerprint identical.
- **Build all eval structure first (seeded inert), then fit once.** Don't tune
  the eval, add a term, and re-tune — that wastes self-play games (the conserved
  resource in CPython). Texel is the cheap inner loop; SPSA/SPRT games are not.
- **Same TC for tuning and the confirming gate** (currently `8+0.08`).
- **Update `PLAN.md` + this guide in the same commit as the code.** Refresh the
  "Next action" pointer every time.
- **Commit each kept step separately, no co-author trailer.**
- **Keep release UCI clean:** tuning knobs stay behind the `Tune` flag.
- The eval boundary stays clean (`Evaluator.evaluate(board)`), so Phase 9 NNUE
  stays possible.
