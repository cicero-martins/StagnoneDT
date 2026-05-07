# StagnoneDT — context for Claude

3D coupled wave-hydrodynamic Delft3D FM + SWAN digital twin of the Stagnone di Marsala lagoon (Sicily). PhD project at Università degli Studi di Palermo.

## Current state

- **Latest validated model:** `model/dflowfm_v04/` — wave coupling, volume mass balance, hipersaline IC, BC offset (per-node Marettimo-anchored), Trapani port mesh patch, D-Morph 2 fractions, ERA5 evaporation. 9-day Jul 2025 validated.
- **Active focus:** v04.1 fixes — (i) salt blowup mitigation in 3.2% intertidal cells; (ii) WL datum recalibration to remove +12-17 cm bias.
- **Validation reference:** v03d (in `model/dflowfm_v03d/`) — same window, no per-node BC, no D-Morph.

Always check `git log --oneline -10` and read [README.md](README.md) at the start of a new session. Memory entries in `~/.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/` are auto-loaded.

## Stack

- **D-Flow FM Suite 2026.01 HMWQ** (kernel `dflowfm 1.2.184`) at `C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\`
- **Python env:** `dfm_tools_env` at `C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe` — dfm_tools 0.45.0, HYDROLIB-core 1.0.0, copernicusmarine 2.3.0, xarray, netCDF4, numpy, pandas, matplotlib, rasterio
- **Run target:** local Windows (4-MPI dev, 8-MPI on the higher-core machine) is the current default; EDITO Datalab (`delft3dfmrun-docker`) is operational fallback

Credentials live in `.env` (gitignored): `CDSAPI_URL`, `CDSAPI_KEY`, EDITO S3, etc. The download scripts include a minimal `load_dotenv()` helper.

## Project conventions

**Versioning** — model dirs `model/dflowfm_v01/`, `_v02/`, ..., `_v04/`. Major versions only (no v04a/v04b). Cloning pattern: copy from previous validated version, exclude `DFM_OUTPUT_*/`, `_000?_*` partitioned files, `*.bak`, runtime logs. Document the new version's scope in `docs/progress_report_YYYY-MM-DD.md`.

**Notebooks** — numeric blocks: `00-09` input forcing, `10-19` model build, `20-29` validation, `30-39` analysis, `40-49` EDITO util. Naming: `<NN>_<role>_<version?>_<slug>.ipynb`. See `notebooks/README.md` for the full index.

**Scripts** — naming: `<verb>_<scope>_<version?>.py`. Examples: `download_marettimo_wl_long.py`, `build_v04_offset_bc.py`, `validate_v03d_marettimo.py`. Internal helpers prefixed `_`. Throwaway scripts go in `scripts/_*` (gitignored).

**Docs** — `docs/progress_report_YYYY-MM-DD.md` for milestones; `docs/<topic>.md` for durable analyses; `docs/fm_2026_gotchas.md` for parser/runtime gotchas; `docs/marettimo_offset_anchor_2025.md` for the anchored-offset methodology; `docs/wl_boundary_offset_justification.md` for the multi-component offset breakdown.

**Memory entries** — `~/.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/MEMORY.md` indexes them. Save when: non-obvious gotcha, reusable convention, project state that decays differently from code. Don't save: stuff already in commits/docs, ephemeral state.

**Old-ext format (legacy `.ext`)** — comments use `*` (asterisk), NEVER `#`. Never write `QUANTITY=` literal inside any comment text — the parser may capture trailing comment text as the actual quantity value. See [docs/fm_2026_gotchas.md](docs/fm_2026_gotchas.md) §3.

## Validation philosophy

**Raw + anomaly metrics together.** RMSE² = bias² + RMSE_anom² (Pythagoras). Bias = datum/offset error; RMSE_anom = dynamic skill (phase + amplitude). Reporting only one of them obscures the source of error.

**Post-spinup window.** Drop the first sim-day (`T_MIN + 1d` to `T_MAX`) — the IC ramp-up generates spurious large transients. v03d used 1.5d-9d explicitly.

**Marettimo cell selection — non-trivial.** The literal nearest cell to the JRC TAD 658 gauge picks a deep-water cell in the lee of the island that flat-lines (std~0). Use the v03d-compatible target (12.0753, 37.9747) with `bl < -0.3 m` constraint — see `scripts/v04_health_check.py::_find_marettimo_cell_v03d_compat`. Memory: `marettimo_validation_cell.md`.

**Cells, not stations, are the unit of analysis for offshore.** For interior obs (BocaNord/BocaSud/AltaVilaEst), use his.nc which writes per-station time series. For Marettimo and other offshore points (no obs.xyn entry), extract from map.nc with explicit cell selection.

**Sanity checks before trusting metrics:** confirm `my model volume > 0` in partition .dia files (else `bedLevType=1` fell back to `bedLevUni`); confirm `mesh2d_hwav.std() > 0` (else SWAN HDF re-open is broken — fix is `ncFormat=3`); confirm `mesh2d_sa1` doesn't have outlier values >>50 ppt indicating intertidal blowup.

## Workflow rules

**End-of-day review.** When the session is wrapping up (signals: "vamos parar", "amanhã continuamos", end-of-day commit, "boa noite"), proactively ask whether anything from the session belongs in memory. Don't wait for the user to remember. See `feedback_end_of_day_review.md`.

**Commit cadence.** Granular: 1 commit ≈ 1 coherent change. Multiple per session is normal. Use Conventional Commits-ish prefixes: `fix(v04):`, `validate(v04 9d):`, `docs(readme):`, `chore:`, `build(v04):`. Reference root causes in commit body, not just symptoms.

**README updates** — only on version transitions (v04 → validated, v04 → v04.1, etc.) or new major findings. Don't update README per-commit.

**Long-running runs** — use `run_in_background: true` for partition+dimr (~9h for 9d at 8 MPI). Use `Monitor` to stream FATAL/ERROR/Complete% lines from the log instead of polling. The Bash tool blocks naive `sleep` patterns.

## Recurring gotchas (full detail in memory + docs)

- [docs/fm_2026_gotchas.md](docs/fm_2026_gotchas.md) — five interlocking parser/config issues for ERA5 evap + D-Morph in FM 2026.01. Read before adding any meteo forcing or sediment config.
- `cmems_zos_reference_frame` — `zos` is anomaly around NEMO rest-state, not EGM/WGS84. Tide is in zos for forecast 006-013, NOT for reanalysis 006-004 or GLO myint 001-030.
- `cmems_med_v04_implications` — MED-MFC EAS8 setup (NEMO 4.2 + WW3 acoplado at 1/24°)
- `dimr_time_vs_startdatetime` — D-Waves MDW SimMode must be `stationary` in DIMR Online with FLOW; time-varying comes from re-evaluated TPAR
- `hdf5_coupling_resolution` — `ncFormat=3` resolves SWAN HDF re-open of `com.nc`; trade-off: 2 GB per-file limit
- `notebook_unicode_writing` — prefer ASCII in `.ipynb`; Unicode only via `Write` with explicit utf-8 (Write tool sometimes double-encodes)

## Areas not to modify casually

- `oldModel/` — read-only reference (Model A, Model B Stagnone_py_lagoon3D, hand-drawn Stagnone_justLagoon mesh, 2006 bathymetry XYZ)
- `model/dflowfm_v0X/DFM_OUTPUT_*/` — gitignored; outputs are regenerable, NEVER commit (16-26 GB each)
- `data/raw/satellite/` — gitignored, 18 PlanetScope + Sentinel-2 scenes (summer 2025), regenerable via Planet/CDSE downloads
- `reference/` — third-party material (modelbuilder example, papers); cite but don't restructure

## Quick orientation

- `git log --oneline -10` — recent decisions
- `cat docs/progress_report_*.md | head` — latest milestone narrative
- `cat ~/.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/MEMORY.md` — what's tribal knowledge vs. what's in code
- `ls model/` — version landscape
- `ls scripts/` — workflow building blocks
