# Roadmap — post-v03c (2026-04-23)

Consolidated work plan after v03c validation. Four orthogonal tracks
converge on **v03d** as the next major.

## Track A — Tracers via initial buffer

**Scope:** replace laterals + tracer .bc by the `lagoon_tracer_init.xyz`
pattern (init via XYZ + `initialFields.ini`). Removes the lateral + .pli
complexity that failed for the airport point.

**Implementation:**

1. Utility script in `scripts/make_tracer_buffers.py` — takes (lon, lat, radius_m, name), generates an XYZ with value 1.0 in the FM mesh cells inside the circular buffer (via shapely + pyproj in UTM 33N). Output: `model/dflowfm_v03d/turbid_airport_init.xyz` and `turbid_saltpans_init.xyz`.
2. 500 m radius buffers, centred on `(12.468, 37.917)` airport and `(12.507, 37.997)` salt pans.
3. In v03d's `initialFields.ini`, add two `[Initial]` entries referencing the XYZs with `operand = A`, `averagingType = mean`, following the pattern of `lagoon_tracer_init.xyz`.
4. **Remove** from `new.ext`: `[Lateral]` + `[Boundary]` tracerbnd blocks for turbid_airport and turbid_saltpans. Remove `turbid_*.pli`, `turbid_*_discharge.bc`, `turbid_*_tracer.bc` from the v03d directory.
5. Minimal validation: `lateral_geom_node_count` disappears from his.nc (no more lateral); `turbid_airport.max()` and `turbid_saltpans.max()` at t=0 must be 1.0.

**Resulting physical scenario:** plume pre-existing from sim-start (cleaner than the pulse). Useful for measuring controlled spreading.

## Track B — Offshore validation (Marettimo)

**Scope:** compare WL + Hs/Tp/Dir offshore at Marettimo (Egadi, ~12.05°E, 37.96°N) with v03c output.

**Implementation:**

1. Locate the station: does RON (Rete Ondametrica Nazionale, ISPRA) have a buoy at Marettimo? Also check Copernicus CMEMS in-situ marine (`INSITU_MED_PHYBGCWAV_DISCRETE_MYNRT_013_035`). Expected URL: ispra.gov.it/en/topics/sea/wave-meter-national-network.
2. Confirm that the Marettimo point falls inside the SWAN outer domain (which spans ~11.95°E–12.57°E). Add an observation point at Marettimo in v03c's `.xyn` (requires a rerun to extract a his time-series at that station) OR extract via map.nc offline.
3. New notebook `23_valid_v03c_offshore.ipynb` — loads Marettimo obs, interpolates the model at the point, computes RMSE/bias/Willmott/corr separately for WL and for Hs/Tp.
4. Add the result to the existing validation_metrics_v03c.csv table (or create a separate v03c_offshore.csv).

**Success criterion:** RMSE(WL) < 10 cm offshore; Hs bias within ±20 cm.

## Track C — Morphology (investigation + provisioning)

**Part C1 — investigation (before v03d)**:

1. `scripts/compute_uorb_from_map.py` — reads `41_util_edito_map_subset` output (hwav, twav, waterdepth), computes u_orb = π Hs / (T sinh(kh)) at the lagoon-centre points. Reports % of time u_orb > 0.10 m/s (fine-sand resuspension threshold).
2. Notebook `31_analysis_resuspension_feasibility.ipynb`:
   - Section 1: u_orb time series at the 7 stations (from the v03c his.nc, which already contains uorb).
   - Section 2: Sentinel-2 L2A turbidity time series (nominalIIR / CHL_NN) 2025-06-01 to 2025-08-01, extracted from the same bbox.
   - Section 3: cross-correlation of turbidity with ERA5 wind speed (already available locally) + CMEMS Hs.
   - Decision: if turbidity correlates with Hs and u_orb exceeds the threshold > 5% of the time → morph is worth pursuing.
3. Memory to update with the numbers found.

**Part C2 — v03d provisioning**:

If C1 is positive:
- Enable D-Morphology in v03d's MDU: `[Morphology]` section + reference to `sediment.sed` + `morphology.mor`.
- Sediment: 2 fractions. Fraction 1 = fine sand (d50 ≈ 150 µm), fraction 2 = silt (d50 ≈ 30 µm).
- Manning baseline preserved; D-Morph adds bed shear stress from wave orbital.
- Initial bed: uniform (no spatial variation in the first iteration; refine later if useful).
- `morfac = 1` (real-time, no morphological acceleration — short runs).

If C1 is negative: document in the roadmap and skip C2. v03d remains without morph.

**XBeach out**: already decided — it is a surf-zone model, not applicable to a sheltered lagoon.

**C1 result (2026-04-23)**: morph **approved** for v03d. See [notebook 31_analysis_resuspension_feasibility](../notebooks/31_analysis_resuspension_feasibility.ipynb). Evidence: (a) iter-1 SWAN already reports u_orb = 0.186 m/s at BocaNord (above the fine-sand threshold of 0.14); (b) offshore peak Hs = 2.05 m (2025-07-09) → inlet u_orb 0.7-1.7 m/s — exceeds the sand threshold > 30% of the time even with 30% attenuation; (c) S2 scene 2025-10-06 shows a visually confirmed resuspension event (PI). Interior is marginal but mobilises silt + clay. **C2 proceeds**: enable `[Morphology]` + 2 fractions (sand d50 150µm, silt d50 30µm).

## Track D — HDF5 coupling debug (local)

**Scope:** unblock the constant-wave limitation of the FM+SWAN Online with FLOW coupling.

**Implementation (local, no EDITO):**

1. **Baseline run** of the full v03c locally (full 9 days) to reproduce the error locally and provide a comparison baseline.
2. **Test 1 — `ncFormat = 3`**: clone v03c as `v03c_test1_nc3`, change `ncFormat = 4 → 3` in the MDU, rerun. Check whether HDF errors disappear and whether hwav.std() > 0.
3. **Test 2 — serial run (`nPart = 1`)**: clone as `v03c_test2_serial`, change run_model to nPart=1, rerun. Check the same criterion.
4. **Test 3 — combo**: if T1 and T2 fail individually, combine both.
5. **Research**: Deltares OSS forum (`oss.deltares.nl/web/delft3d/forum`) + GitHub `Deltares/dflowfm-repo` issues. Search for "HDF error com.nc SWAN online FLOW".
6. **Escalation**: if everything fails, open a thread on the Deltares forum with anonymised MDU/MDW + log + exact version.

**Deliverable**: memory `hdf5_coupling_resolution.md` with the workaround (or confirmation of a known bug).

**Track D result (2026-04-23)**: **resolved**. Local 2-h sim tests in `model/dflowfm_v03c_hdftest_*/` isolated the cause: **`ncFormat = 3` eliminates the HDF errors and restores time-varying waves**. A 4-test matrix (baseline/nc3/nolock/serial) showed that neither MPI concurrency nor HDF5_USE_FILE_LOCKING resolves the issue in isolation — only classic netCDF cuts it at the root. Trade-off: 2 GB per-file limit. Mitigation by combining wrimap_* reductions + mapInterval=1800 makes 9 days fit. Details in [hdf5_coupling_resolution](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/hdf5_coupling_resolution.md).

## Track E — v03d consolidation

Pulls from A + C2 (if positive) + D (if resolved):

Build in `model/dflowfm_v03d/` (notebook `14_build_v03d.ipynb`):
- A: buffer tracers + lateral removal
- ERA5 evaporation forcing (add `era5_e_2025...nc` + reference in ext)
- C2: sediment + morph if C1 positive
- D: ncFormat=3 or serial setup if D resolved

## Track F — v03d validation

Notebook `24_valid_v03d.ipynb` (reuses the `22_valid_v03c` structure):
- Standard stations (7 + Marettimo offshore)
- Hypersalinity (now expected to persist with evap)
- Tracers (pre-existing dispersion)
- Waves (time-varying, if D resolved)
- Sediment (if C2 enabled)

## Recommended sequence

| # | Track | Duration | Dependency |
|---|---|---|---|
| 1 | **B — Marettimo** | 4–6 h | local map.nc |
| 2 | **D — HDF5 local** | 4–8 h | local Delft3D environment |
| 3 | **C1 — morph investigation** | 3–4 h | his.nc + map subset + Sentinel-2 |
| 4 | **A — tracer buffer script** | 2 h | independent |
| 5 | **E — v03d build** | 4 h | A, C2 (if applicable), D |
| 6 | **F — v03d validation** | 3 h | v03d run on EDITO (~12 h clock time) |

Estimated total ~24 h of work + 12 h of clock time for the v03d run.

## Out of scope (for later)

- SWAN nested grid extension (memory `swan_grid_extension`) — postponed to v04.
- Tier 2 / Tier 3 of the dt_scaling_roadmap.
- Paper drafts.
