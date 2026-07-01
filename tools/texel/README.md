# Hydra Texel tuning data pipeline

Phase 4 eval data-fit (PLAN.md §7). The tuner fits eval weights so that
`sigmoid(eval · K)` predicts a per-position `target` in `[0,1]`. Two artifacts
feed it, both in `FEN;target` text (White-perspective target):

```
tools/texel/data/beast_train.csv     # fit against this
tools/texel/data/beast_holdout.csv   # disjoint by position; early-stopping / reporting
```

The `data/` dir is git-ignored (the CSVs are large and regenerable).

## Label source — why Hydra differs from the siblings

Rarog and Basilisk label by **self-play game results** (they play the Beast
positions out and record WDL). Hydra instead fits against the **pre-computed
Stockfish-WDL labels** already shipped in the Beast dataset
(`A:\Chess\Beast\data\evaluated\evaluated_positions_*.txt`, 123 shards ≈ 123M
positions, `FEN<TAB>win-prob`). Rationale:

- **Self-play is ~30–50× more expensive in Python.** Native Rarog/Basilisk
  generate a dataset in well under an hour; Hydra (compiled, ~70k nps) needs
  **~20–34 h** of pinned machine for a comparable run, and it recurs every
  regeneration. The Beast labels cost **minutes**.
- **Denser, stronger labels.** A continuous Stockfish WDL is lower-variance and
  a far stronger judge than an untuned-Hydra game result.
- **The risk is bounded.** Distilling a stronger engine can chase quirks the HCE
  can't represent — but that bites a *strong* eval; Hydra's is untuned and
  **underfit**, so broad agreement with SF is almost pure upside. And the
  **SPRT gate is ground truth**: if a stage's fit doesn't transfer to game
  strength it simply won't pass, at a cost of minutes, not a machine-day.

The label is a win-probability for the **side to move**; we convert it to White
perspective (`target = p if white-to-move else 1 − p`). No centipawn conversion —
the WDL percentage *is* the Texel target.

Self-play (the sibling path) stays available as a fallback/comparison if a stage
underwhelms; it is not wired up yet because Path B is the cheap option to spend
first.

## Build the dataset (`import_beast.py`)

```powershell
# ~2M balanced train + ~5% holdout; ~20M scan ≈ 25–30 min single-thread.
& .venv\Scripts\python.exe tools\texel\import_beast.py `
    --source "A:\Chess\Beast\data\evaluated" `
    --per-bucket 400000 --max-scan 20000000
```

Hygiene applied while streaming:

- **Quiescence filter** — drop positions in check (static HCE eval is
  meaningless there) and *tactical* positions where the side to move has a
  winning capture (`SEE > 0`), so the quiet static eval can match the
  search-derived label. (`--no-quiet` disables the SEE part.)
- **Phase balance** — five phase buckets (opening → deep-endgame), each a
  reservoir of `--per-bucket`, so no phase dominates. Deep-endgame is the
  sparse bucket (~4% of the pool) and gates the scan size.
- **De-dup** by position key (first 4 FEN fields); holdout split off first so
  train and holdout never share a position.

## Sanity-check before fitting

```powershell
# Reconstruction gate (PLAN 4.1 step 5) + optimal K + eval/target correlation.
& .venv\Scripts\python.exe tools\texel\tune.py `
    --data tools\texel\data\beast_train.csv --verify --find-k
```

- `--verify` confirms `reconstruct_eval(trace) == evaluate()` on the extracted
  FENs (0 mismatches) — the same coefficient-trace gate used through Phase 1–3.
- `--find-k` reports the sigmoid scale `K`, the MSE, and the correlation between
  the current (untuned) eval and the target. A healthy positive correlation
  means there is signal to fit.

## Scripts

| Script | Role |
|--------|------|
| `import_beast.py` | Stream the Beast SF-WDL shards → balanced, quiet, deduped `beast_train.csv` + `beast_holdout.csv` (White-perspective targets). Hydra-specific (uses the engine's SEE + movegen for the quiet filter). |
| `tune.py` | `--verify` reconstruction gate · `--find-k` K/MSE/correlation · `--smoke` self-test. The staged weight fit (Phase 4.2) plugs in where `main()` is marked TODO. |

## Next: Phase 4.2 staged fit

Biggest lever first, each stage SPRT-gated (compiled-vs-compiled, TC `8+0.08`):
material → mobility → pawns → passers → king-safety-v2 → threats →
scale/imbalance/space/winnable → **PST + material refit last**. Texel proposes;
the SPRT decides; re-running Texel between stages is cheap and expected.
