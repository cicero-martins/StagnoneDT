# Progress Report — 2026-05-04

**Focus:** WL boundary offset on a rigorous footing (Marettimo annual anchor + MDT spreading), v04 build with D-Morph, and a structural cleanup of the BC pipeline understanding.

## TL;DR

- **CMEMS BC pipeline reviewed**: documented how `dfmt.cmems_nc_to_bc` constructs the `.bc` from CMEMS, including the foot-gun pattern of stacking `constant + tide + CMEMS` blocks on a single `.pli` (root cause of the v03c double-counting). Memos pushed to memory.
- **`zos` vertical reference frame** confirmed (CMEMS PUMs verbatim): `sea_surface_height_above_geoid` is defined only as the NEMO **rest state**, not EGM2008/96 or WGS84. Tide presence in `zos` depends on the product (forecast 006-013 yes, reanalysis 006-004 no, GLO myint 001-030 no).
- **MED-MFC EAS8** documented (NEMO 4.2 + WW3 v6.07 two-way coupled at 1/24°). Implications for v04 saved as project memory.
- **Marettimo long series downloaded** (JRC TAD 658, Jan 2025 - Jan 19 2026, 55 052 samples at 10-min). Annual mean +0.0905 m, std 0.135 m, monthly amplitude ~21 cm.
- **Trapani is NOT in the ISPRA-RMN network** (verified against 4 sources). The previous text in `wl_boundary_offset_justification.md §7.3` was wrong; corrected. Real RMN alternatives: Porto Empedocle (Sicily Channel, ~150 km SE), Palermo (Tyrrhenian, ~80 km NE), Lampedusa.
- **Marettimo offset anchor computed**: `δ = mean(obs) − mean(zos_CMEMS) = +0.4489 m` annual (+0.4812 m for July 2025). Different from the v03d empirical +0.4208 m (tuned downstream of model dynamics).
- **CMEMS MDT product downloaded** for the PLI bbox: spatial spread ~6.5 cm across the 49 boundary nodes, mean ~0 (so the +0.45 m anchor is overwhelmingly datum + product bias, not MDT).
- **EMODnet 2024 bathymetry for Trapani port** downloaded at ~22 m resolution. Captured the approach channel down to −13 m; inner basin still mostly emerges (mean +5 m). Better than GEBCO but insufficient for the basin.
- **v04 build in progress**: per-node WL offset (49 values, range +0.455 to +0.501 m, MDT-spread), Trapani mesh z fix (172 → 85 nodes above MSL in the port bbox), D-Morph 2 fractions (sand 150 µm + silt 30 µm), `bedLevType` 3 → 1, ERA5 evap download running. Smoke test iterating through format issues uncovered along the way.

## 1. CMEMS BC pipeline + `zos` reference frame

The CMEMS modelbuilder (`reference/modelbuilder_example.ipynb`) chains four steps:

1. `dfmt.download_CMEMS(varkey=...)` — daily NetCDFs per variable
2. `dfmt.cmems_nc_to_bc(ext_new, list_quantities=[...], file_pli=..., dir_pattern=...)` — interpolates lat/lon to `.pli` vertices, writes `.bc` with one `[Forcing]` per plipoint
3. `dfmt.cmems_nc_to_ini(ext_old, ['salinitybnd','temperaturebnd'], ...)` — IC nudging fields
4. `mdu.wind.pavbnd = 101330` — inverse barometer correction

**Foot-gun**: the example notebook also stacks two more `waterlevelbnd` blocks on the same `.pli` (`constant_to_bc` + `interpolate_tide_to_bc`). FM combines them additively. For Mediterranean configs where CMEMS forecast already contains tide, this **doubles** the tidal amplitude (the v03c bug fixed in v03d).

The `zos` itself, per the three relevant CMEMS PUMs, is `sea_surface_height_above_geoid` where "geoid" is defined verbatim as *"the surface the ocean would have if at rest"* — the NEMO model rest state. **No EGM2008/96 or WGS84 vertical datum is named anywhere**. Tide-in-zos status by product: forecast 006-013 yes (8 components FES2014); reanalysis 006-004 no; GLOBAL myint 001-030 no. This matters for any historical run choice.

**MED-MFC EAS8** (current operational system): NEMO 4.2 at 1/24° with 141 z* levels, ECMWF IFS-HRES 1/10° atmospheric forcing, 38 rivers + EFAS, OBC at Gibraltar from GLO PSY4, OceanVar 3DVAR assimilation (SLA + SST + T/S), two-way coupled to MED-WAV (WW3 v6.07) at hourly exchange.

**Memories**: [cmems_zos_reference_frame.md](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/cmems_zos_reference_frame.md), [cmems_med_v04_implications.md](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/cmems_med_v04_implications.md).

## 2. Marettimo as offset anchor — full statistical baseline

[scripts/download_marettimo_wl_long.py](../scripts/download_marettimo_wl_long.py) iterates monthly across `https://webcritech.jrc.ec.europa.eu/TAD_server/api/Data/Get/658` and downsamples to 10-min via `resample('10min').mean()` (bin average, NOT moving average — confirmed with the user).

Output: [data/raw/insitu/marettimo_wl_2025_2026_10min.csv](../data/raw/insitu/marettimo_wl_2025_2026_10min.csv) (55 052 rows, Jan 2025 - Jan 19 2026).

Pronounced seasonality: monthly mean −0.041 m (Feb 2025) to +0.174 m (Jan 2026), amplitude ~21 cm. The Marettimo SiAM gauge went **dormant after 2026-01-19** — the 2025 series can be used as a frozen statistical anchor for any post-2026 run, while pre-2026 runs can use the matching subset.

## 3. Trapani RMN — correction of a wrong claim

§7.3 of the WL offset justification recommended Trapani RMN as the formal-datum reference. **It is not RMN**, verified against:

1. ISPRA `mareografico.it` station list — Trapani not present
2. JRC webcritech SeaLevelsDb — no Trapani device ID
3. PSMSL — no Trapani station
4. IOC sealevelmonitoring.org — not in the list

Correction pushed to [docs/wl_boundary_offset_justification.md §7.3](wl_boundary_offset_justification.md). The actual RMN alternatives in western Sicily are **Porto Empedocle** (best regime match — Sicily Channel), Palermo, Lampedusa.

**Memory**: [trapani_not_rmn.md](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/trapani_not_rmn.md).

## 4. Definitive `δ(Marettimo)` anchor

[scripts/compute_marettimo_offset_anchor.py](../scripts/compute_marettimo_offset_anchor.py) downloads CMEMS MED-PHY `zos` daily-mean for the same 13-month window via `copernicusmarine.subset` and computes:

```
δ(Marettimo) = mean(obs) − mean(zos_CMEMS @ Marettimo)
             = +0.0905 − (−0.3584)
             = +0.4489 m   (annual)
```

Monthly breakdown shows a 14 cm seasonal swing in δ (winter low ~+0.36, summer-autumn high ~+0.50). For Jul 2025 (the v04 reference window): **δ_Jul = +0.4812 m**.

Reconciliation with the previous "Marettimo-tuned offset = +0.315 m" estimate: the new anchor is upstream-tuned (BC only, before model dynamics) while the earlier number was downstream-tuned (subtracts the model-internal dynamic effects of ~+0.13 m at Marettimo from wave setup, lagoon non-linearity, residual barometric).

Report + figures: [docs/marettimo_offset_anchor_2025.md](marettimo_offset_anchor_2025.md), [figures/marettimo_offset_*.png](../figures/).

**Memory**: [marettimo_long_series_2025.md](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/marettimo_long_series_2025.md).

## 5. CMEMS MDT product for spatial spreading

[scripts/download_cmems_mdt_pli.py](../scripts/download_cmems_mdt_pli.py) pulls `cmems_obs-sl_med_phy-mdt_my_l4-0.0417deg_P20Y` (SEALEVEL_MED_PHY_MDT_L4_STATIC_008_066, CNES-CLS, 1993-2012 ref) for the PLI bbox (lon 11.85-12.65, lat 37.60-38.20).

| Statistic | Value |
|---|---|
| Resolution | 0.0417° (~4.6 km) |
| MDT range | −0.036 to +0.030 m |
| MDT mean | −0.005 m |
| `err_mdt` | 0.5 - 0.8 cm |

**Insight**: the MDT is essentially zero in this small area (<1° span). The +0.45 m anchor is overwhelmingly **datum + CMEMS product bias**, not MDT. Spreading across the 49 nodes adds ~6 cm of variation (from [build_v04_offset_bc.py](../scripts/build_v04_offset_bc.py): δ ranges from +0.4550 to +0.5010 m).

## 6. EMODnet 2024 bathymetry — Trapani port

EMODnet 2024 DTM (1/16′ ≈ 115 m native) WCS endpoint pulled at 22 m oversampled into the Trapani port bbox (12.48-12.55, 37.99-38.05). Saved to [data/raw/bathymetry/emodnet_2024_trapani_port.tif](../data/raw/bathymetry/emodnet_2024_trapani_port.tif).

| Subset | Size | Range | Mean |
|---|---|---|---|
| Inner port (12.510-12.525, 38.010-38.025) | 75×75 px | −13.23 to +22.43 m | +4.96 m |

EMODnet 2024 is **better than GEBCO** (which had the port basin entirely emergent in v03d) but **still insufficient** for the inner port basin — the approach channel resolves to −13 m, but the harbour basin remains mostly above MSL. For full coverage we'd need IIM nautical chart digitisation (commercial) or the Trapani Port Authority's own surveys.

## 7. v04 build (in progress)

Cloned from v03d via `Copy-Item` excluding `DFM_OUTPUT_*`, partitioned files, `*.bak`, logs. Current scope: **minimum viable + ERA5 evap**, Jul 2025 9-day window, local 4-MPI execution.

### 7.1 Per-node WL offset

[scripts/build_v04_offset_bc.py](../scripts/build_v04_offset_bc.py) reads the 49-node `.pli`, samples MDT at each node and at Marettimo (linear interpolation), and applies:

```
δ(node_i) = δ_anchor_Jul + [MDT(node_i) − MDT(Marettimo)]
```

Output: [model/dflowfm_v04/waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc](../model/dflowfm_v04/waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc) with 49 `[Forcing]` blocks (function = constant). Range +0.4550 to +0.5010 m. The `Stagnone_dxy01_15m_new.ext` was patched to reference the new file (replacing `waterlevelbnd_constant_*.bc`).

### 7.2 Mesh z fix at Trapani port

[scripts/regen_mesh_z_trapani.py](../scripts/regen_mesh_z_trapani.py) overwrites `mesh2d_node_z` for nodes in the bbox (12.500-12.550, 38.005-38.040) with EMODnet samples, only **deepening** existing values (never elevating — safety against accidentally drying valid cells).

| Stat | Before | After |
|---|---|---|
| Nodes in bbox | 626 | 626 |
| Nodes above MSL | 172 | **85** |
| Mean z (bbox) | −2.28 m | **−4.75 m** |

Result: ~half of the previously emerged port nodes were freed to flood. A backup of the original net.nc was kept as `*_pre_trapani.nc.bak` (gitignored).

### 7.3 D-Morph 2-fraction setup

Two fractions per [docs/roadmap_post_v03c.md Track C2](roadmap_post_v03c.md): sand (d50 = 150 µm) + silt (d50 = 30 µm, cohesive). Configuration files written following the **D-Morphology User Manual 2026.02** (Deltares, retrieved 2026-05-04):

- [model/dflowfm_v04/sediment.sed](../model/dflowfm_v04/sediment.sed) — `[SedimentOverall]` Cref + two `[Sediment]` blocks. Sand uses `TraFrm = -2` (Van Rijn 2007, wave-aware), silt uses cohesive defaults (`SalMax`, `WS0`/`WSM`, `TcrSed`, `TcrEro`, `EroPar`).
- [model/dflowfm_v04/morphology.mor](../model/dflowfm_v04/morphology.mor) — `MorFac = 1.0` (real-time), `MorStt = 1440 min` (bed update starts at t = 1 day, after lagoon spin-up), `BedUpd = true`, `CmpUpd = true`, `ISlope = 2` (Bagnold).

**Iteration learned along the way:** my first draft used Delft3D-FLOW-only keywords (`EpsPar`, `IopKCW`, `RDC`, `RDW`, `AksFac`, `RWave`, `IUnderLyr`, `ExchLyr`, `ASKlhe`, `MWUNumPolys`) — these are FM-incompatible per the manual and trigger `unstruc::flow_sedmorinit - Error in subroutine rdstm` at init.

MDU updated: `Sedimentmodelnr = 4`, `MorFile = morphology.mor`, `SedFile = sediment.sed`, **`bedLevType = 3 → 1`** (FM forces bedLevType=1 with morph). The `bathymetryFile` keyword is obsolete in FM 2026.01; bed levels still come from `mesh2d_node_z` in the netfile, just interpreted at cell centers.

### 7.4 ERA5 evaporation (in flight)

[scripts/download_era5_evap_v04.py](../scripts/download_era5_evap_v04.py) running in background — pulls `mer` (mean evaporation rate, kg/m²/s) for Jul 2025 from CDS. Will be integrated into `Stagnone_dxy01_15m_old.ext` via [scripts/integrate_era5_evap_v04.py](../scripts/integrate_era5_evap_v04.py) (factor = −1/1025 to convert from negative-into-ocean kg/m²/s to positive-out-of-ocean m/s expected by FM `evaporation` quantity). Addresses the v03c hipersalinidade-erosion finding (memory `v03c_validation_findings`).

### 7.5 Smoke test status

Three iterations:

1. **#1**: FATAL `rdstm` from Delft3D-FLOW-only keywords in `.mor`.
2. **#2**: rejected by user — needed manual cross-check first.
3. **#3** (running at report time, after manual review): files now strictly conform to the FM 2026.01 spec. FATAL on bedLevType expected to be resolved by the 3 → 1 change.

Pre-smoke partition succeeded with exit 0 — MDU + ext + per-node `.bc` + sediment + mesh all parse cleanly.

## 8. Status, blockers, next steps

### Done today

| Item | Output |
|---|---|
| CMEMS BC pipeline review | Notes + 2 memories |
| Marettimo 13-month series download | [data/raw/insitu/marettimo_wl_2025_2026_10min.csv](../data/raw/insitu/marettimo_wl_2025_2026_10min.csv) + 13 monthly CSVs |
| Trapani-not-RMN correction | [docs/wl_boundary_offset_justification.md §7.3](wl_boundary_offset_justification.md) updated; memory created |
| `δ(Marettimo)` anchor | [docs/marettimo_offset_anchor_2025.md](marettimo_offset_anchor_2025.md) + 5 figures |
| MDT product download | [data/raw/cmems/mdt_static/](../data/raw/cmems/mdt_static/) |
| EMODnet 2024 Trapani port | [data/raw/bathymetry/emodnet_2024_trapani_port.tif](../data/raw/bathymetry/emodnet_2024_trapani_port.tif) |
| v04 dir scaffold | [model/dflowfm_v04/](../model/dflowfm_v04/) cloned + 6 patches applied |
| Per-node BC offset | [model/dflowfm_v04/waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc](../model/dflowfm_v04/waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc) |
| Trapani mesh z fix | net.nc updated in place (172 → 85 emerged) |
| D-Morph configuration | sediment.sed + morphology.mor + MDU |

### In flight at report time

- ERA5 evap download (CDS queue, no error yet)
- Smoke test #3 running (post bedLevType + sediment fixes)

### Pending after smoke validates

1. Integrate ERA5 evap into ext_old (script ready)
2. Repartition + full 9-day run
3. Validation notebook `25_valid_v04.ipynb` (mirror of `22_valid_v03c`)
4. Compare v03d vs v04 metrics — quantify net effect of: per-node offset (vs. constant), Trapani mesh fix, D-Morph activation, ERA5 evap

### Not in v04 minimum viable (deferred)

- SWAN nested 2-level extension (memory `swan_grid_extension`)
- Higher-resolution Trapani port basin (EMODnet HR-DTM or IIM/Port Authority)
- Porto Empedocle RMN validation (formal-datum cross-check)
- ISPRA-SiAM Marettimo datum request

## Deliverables

| File | Description |
|---|---|
| [scripts/download_marettimo_wl_long.py](../scripts/download_marettimo_wl_long.py) | Long-period JRC TAD download + 10-min bin-average |
| [scripts/compute_marettimo_offset_anchor.py](../scripts/compute_marettimo_offset_anchor.py) | δ(Marettimo) anchor calculation, monthly breakdown |
| [scripts/plot_marettimo_offset_monthly.py](../scripts/plot_marettimo_offset_monthly.py) | 4 monthly + 1 annual figure with δ bar subplot |
| [scripts/download_cmems_mdt_pli.py](../scripts/download_cmems_mdt_pli.py) | MDT product subset for PLI bbox |
| [scripts/build_v04_offset_bc.py](../scripts/build_v04_offset_bc.py) | Per-node `.bc` with δ + MDT spreading |
| [scripts/regen_mesh_z_trapani.py](../scripts/regen_mesh_z_trapani.py) | Mesh z patch from EMODnet (deepen-only) |
| [scripts/download_era5_evap_v04.py](../scripts/download_era5_evap_v04.py) | ERA5 mer download via dfm_tools |
| [scripts/integrate_era5_evap_v04.py](../scripts/integrate_era5_evap_v04.py) | ext_old patch for ERA5 evaporation |
| [scripts/make_bathy_xyz_v04.py](../scripts/make_bathy_xyz_v04.py) | Face-center bathy XYZ (legacy — bathymetryFile is obsolete in FM 2026.01) |
| [docs/marettimo_offset_anchor_2025.md](marettimo_offset_anchor_2025.md) | Anchor calculation report + figures |
| [docs/wl_boundary_offset_justification.md](wl_boundary_offset_justification.md) | §7.3 corrected, §7.4 added with the long-anchor methodology |
| [model/dflowfm_v04/](../model/dflowfm_v04/) | Build in progress: BC, mesh, sediment all in place; ERA5 + smoke validation pending |
| [docs/progress_report_2026-05-04.md](progress_report_2026-05-04.md) | This report |
