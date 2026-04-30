# Progress Report — 2026-04-22

**Focus:** v03b validation, v03c design & EDITO debugging, FM+SWAN coupling deep-dive.

## TL;DR

- **v03b validation notebook** produced a detailed diagnostic of the v03b run (hydrodynamics, salinity, tracers, waves) and revealed three silent bugs.
- **v03c** created, fixing the three bugs + adding two experimental turbidity tracers (Birgi airport + Trapani salt pans) triggered by a rain pulse on day 3.
- **Currently running on EDITO** via `delft3dfmrun-docker` (5th successful attempt after 4 config failures). Reached sim-time `2025-07-01 03:40` after ~17 min of real-time — expected pace (~8 min per sim-day).
- **Structural issue identified**: HDF5 error when SWAN reopens com.nc after iteration 1 — pre-existing in v03/v03b, prevents temporal variation of waves in the coupling. Does not block the simulation; topic for separate investigation.

## 1. v03b validation ([notebook 21_valid_v03b](../notebooks/21_valid_v03b.ipynb))

Structured in 5 sections: 1) input/setup verification, 2) sea level vs Trapani tide gauge + GTSM, 3) waves vs CMEMS (adapted — no in-situ data available), 4) salinity, 5) tracer. The Summary section consolidates the findings.

**Metrics saved** in [data/processed/validation_metrics_v03b.csv](../data/processed/validation_metrics_v03b.csv), plots in [figures/v03b_*.png](../figures/).

**Findings:**

| Component | Status | Root cause |
|---|---|---|
| Sea level | ✓ OK (RMSE ~6 cm) | — |
| Currents | ✓ Compatible with CMEMS | — |
| **Waves** | **✗ `hwav.std() = 0`** | SWAN only writes com.nc on the 1st iteration; HDF errors on subsequent ones (see §4) |
| **Salinity** | **✗ Starts at ~38 ppt, not 42** | `iniWithNudge = 2` in the MDU overwrote the hypersaline XYZ |
| **Tracer1** | **✗ No output** | Boundary spec broken in `.ext` |

## 2. v03c — design and changes ([model/dflowfm_v03c](../model/dflowfm_v03c))

Base: clone of v03b with the following changes:

**Bug fixes:**
- `iniWithNudge = 0` (MDU) → 42-ppt hypersaline XYZ effectively applied
- Tracer1 removed (boundary + initial condition + .ext)

**Finer temporal sampling:**
- `mapInterval = 900.0` (was 1800.0) → output every 15 min

**New turbidity tracers (rain pulse on day 3):**
- `turbid_airport` — Birgi airport (12.468, 37.917), ~1000 m³ over 2 h → `discharge = 0.139 m³/s`
- `turbid_saltpans` — Trapani salt pans (12.507, 37.997), ~10000 m³ over 2 h → `discharge = 1.389 m³/s`
- Both with unit concentration (tracer = 1) during the pulse (day 3, 00h–02h), zero before and after
- Files: `turbid_*.pli` (location), `turbid_*_discharge.bc` (lateral discharge), `turbid_*_tracer.bc` (concentration)

**Other adjustments identified during EDITO debugging:**
- `run_model.sh` converted to LF (Docker Linux did not interpret `#!/bin/bash\r`)
- Removed 14 virtual GTSM observation points that fell outside the mesh, causing `find_flowlinks lies outside` warnings — kept only the 7 local points (AltaVilaEst, BocaNord, BocaSud, ObservationPoint01, C1/C2/C3_Central)

## 3. EDITO debugging — lessons learned

Sequence of failures before stabilising (7 logs saved in `output/delft3d-run-docker-*.txt`, gitignored):

1. `run_model.sh: no such file` — CRLF in the shebang.
2. GTSM observation point warnings.
3. Wrong `.bc` format for `Lateral` (lowercase `[forcing]`, keys without underscore). Should be `[Forcing]` + `fileVersion=1.01` + `quantity=lateral_discharge`.
4. `SimMode = nonstationary` rejected — manual requires the hyphen: `non-stationary`.
5. Tried `SimMode = non-stationary` to obtain time-varying waves — **WRONG**. In the DIMR Online with FLOW coupling it must be `stationary`. Temporal variation comes from SWAN re-solving at every coupling step with a re-sampled TPAR. Reverted to v03b default.
6. Tried to align `refDate` / remove the `tStart=0`+`startDateTime=20250701` duality — **WRONG**. DIMR accepts the duality; this was a regression.
7. After reverting to the v03b config in the MDW (stationary + `[TimePoint]` placeholder), the simulation started running normally.

**Memories created/updated** (persistent memory): [dimr_time_vs_startdatetime.md](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/dimr_time_vs_startdatetime.md) with the lesson on `SimMode=stationary` + quasi-stationary sequence in Online with FLOW.

## 4. Structural issue — HDF error in com.nc

**Symptom** (present in v03/v03b/v03c, pre-existing):

```
ERROR opening file. NetCDF file : "..._com.nc". Error message: NetCDF: HDF error
ERROR: time_read(0.00000E+00) is not equal to curtime(0.15639E+08)
```

**Mechanism** (reconstructed from the current iteration's log):
1. 1st `wave.Update`: SWAN reads flow fields + writes hrms/tp/dir to `com.nc` ✓
2. `DFlowFM.Update(600s)` advances 9 sim-hours
3. 2nd `wave.Update`: SWAN reopens `com.nc` for reading (warnings "time not found", uses last available timestep) → runs SWAN internally → **fails to reopen for write** with `HDF error`
4. Subsequent iterations repeat the pattern of step 3

**Consequence**: FM reads hrms/tp/dir only from the 1st successful write → waves remain quasi-constant. **This is the reason for `hwav.std()=0` in v03b**.

**Hypotheses for future investigation** (option B of the next step):
- HDF5 file-handle conflict between FM ranks (parallel) and SWAN (serial)
- `ncFormat = 3` (classic netCDF without HDF5) as workaround
- Flush/sync flags between FM and SWAN on com.nc
- Possible known bug of the EDITO-specific Delft3D Docker image

**Not investigating yet**: the simulation completes despite the errors (v03 already validated this); validating the other v03c improvements (salinity, tracers) is worth waiting for the run to finish.

## 5. Current status and next steps

**Currently running on EDITO:** v03c via `delft3dfmrun-docker`. Progress: sim-time `2025-07-01 03:40` in 17 real minutes. Estimated completion: ~1.5–2 h for 9 sim-days.

**After the run completes:**
1. Output download (`edito_sync.py download-his` script + map/com via mc)
2. Run [notebook 21_valid_v03b](../notebooks/21_valid_v03b.ipynb) adapted to v03c — verify:
   - Initial salinity = 42 ppt in the lagoon interior ✓ (expected with `iniWithNudge=0`)
   - Tracers turbid_airport / turbid_saltpans with a plausible dispersion pattern from day 3
   - Waves: confirm `hwav.std()=0` (known limitation) and document explicitly
3. Open the HDF-error investigation as a separate track — requires consulting the Deltares forum / GitHub or testing workarounds in a local environment

**Other fronts (not touched today, context):**
- Notebook 03b (roughness alternatives) — interactive training polygons + RF classification already delivered
- OpenDrift pipeline — functional
- Planet imagery — awaiting manual user download

## Deliverables

| File | Description |
|---|---|
| [model/dflowfm_v03c/](../model/dflowfm_v03c/) | Complete v03c model (ready for rerun) |
| [notebooks/21_valid_v03b.ipynb](../notebooks/21_valid_v03b.ipynb) | v03b validation (reusable for v03c) |
| [figures/v03b_*.png](../figures/) | Validation plots (3 series + metrics) |
| [data/processed/validation_metrics_v03b.csv](../data/processed/validation_metrics_v03b.csv) | Quantitative metrics |
| [docs/progress_report_2026-04-22.md](progress_report_2026-04-22.md) | This report |
