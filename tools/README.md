# Hydra dev harness (`tools/`)

Local testing + tuning infrastructure (PLAN Phase 0). External binaries live here
too but are git-ignored — only source/config/small-data is committed.

| Path | Committed? | What |
|---|---|---|
| `bin/fastchess.exe` | no (`*.exe`) | [fastchess](https://github.com/Disservin/fastchess) match runner (v1.8.0-alpha). Re-download if missing. |
| `run_hydra.cmd` | yes | UCI launch shim. Runs `python -S -m hydra` from a given engine root so a baseline snapshot isn't shadowed by the editable install. Set `HYDRA_PYTHON` to swap interpreters (Phase 2.6). |
| `snapshot_engine.ps1` | yes | Freeze the working-tree `hydra/` package as a named baseline → `engines/<name>/`. |
| `sprt.ps1` | yes | fastchess SPRT / fixed-games match between two source trees. Default gate `tc=8+0.08`, `elo0=0 elo1=5`. **User runs this**, not the agent. |
| `build_mypyc.ps1` | yes | Build a **mypyc-compiled** engine (~1.8× NPS) into `engines/compiled/` (git-ignored), leaving the working tree pure Python. Needs `mypy` + a C compiler (MSVC). Run it via `run_hydra.cmd engines\compiled`. |
| `build_data.py` | yes | Single-pass extractor: builds the phase-balanced eval corpus + opening book from the external `positions.txt`. |
| `eval_equiv.py` | yes | Eval-equivalence fingerprint over the corpus (refactor gate, PLAN rule 4). Baseline `c4e9c6109970e676`. |
| `spsa/tune.py` + `config_search.json` | yes | Hydra-native SPSA driver for the Phase 5 search-constant wave. Needs Phase 1.1 UCI options to tune. **User runs this.** |
| `spsa/state.json` | no | SPSA run state (resumable). |
| `texel/tune.py` | yes | Offline Texel eval tuner (may use numpy). `--smoke` / `--find-k` functional; weight fit pending Phase 1.2/1.3. |
| `engines/` | no | Baseline snapshots (regenerable). |
| `results/` | no (`*.pgn`) | Match PGNs. |
| `book/openings.epd` | yes | 3000 opening positions (from positions.txt, fullmove ≤ 8). |
| `../tests/data/eval_corpus.epd` | yes | 5000 phase-balanced FENs (1000 each: opening/early-mid/middlegame/endgame/deep-endgame). |

## Quick use

```powershell
# Calibration (engine vs itself — must accept H0, ~0 Elo, zero forfeits)
.\tools\sprt.ps1 -Elo0 -3 -Elo1 3 -NameA S1 -NameB S2

# A gain test vs a frozen baseline
.\tools\snapshot_engine.ps1 -Name baseline
.\tools\sprt.ps1 -EngineB (Resolve-Path tools\engines\baseline)

# Eval-equivalence fingerprint (before/after a refactor — must match)
& .venv\Scripts\python.exe tools\eval_equiv.py

# Rebuild corpus + book from the external position dump
& .venv\Scripts\python.exe tools\build_data.py --positions "A:\Chess\Beast\data\txt\positions.txt"
```

**Data source:** `A:\Chess\Beast\data\txt\positions.txt` — 122.66M label-free
FENs (external, never committed). See PLAN §7 Phase 4.1 for labeling/balancing.
