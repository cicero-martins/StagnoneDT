# Notebook index — Stagnone DT

Thematic numeric blocks encode role. File names follow `<NN>_<role>_<version?>_<slug>.ipynb`.

## Blocks

| Range | Role | Reading hint |
|-------|------|--------------|
| `00–09` | Setup + input forcing | Run once per dataset; outputs consumed by `10–19` builds |
| `10–19` | Model build (per version) | One notebook per canonical model version |
| `20–29` | Validation | Compares a run against in-situ / satellite / reference |
| `30–39` | Science analyses | Post-hoc investigations (diagnostics, tracking, residence time) |
| `40–49` | Utility | EDITO-side tooling (post-processing, map subsetting) |
| `archive/` | Experimental / one-off | Kept for history; not part of the main pipeline |

## Full catalog

### Setup + input forcing (`00–09`)

| Notebook | Purpose | Consumers |
|---|---|---|
| [00_setup_domain_mesh](00_setup_domain_mesh.ipynb) | Evaluate mesh quality, domain extent, inlet resolution, boundary adequacy | All builds |
| [01_input_satellite_roughness](01_input_satellite_roughness.ipynb) | Sentinel-2 seagrass classification → Manning roughness map | v02+ (optional) |
| [02_input_insitu_wl_wind](02_input_insitu_wl_wind.ipynb) | QC 3 WL + 2 wind stations; CET→UTC; 3 m → 10 m wind adjustment | All builds |
| [03_input_blended_wind](03_input_blended_wind.ipynb) | Blend ERA5 + in-situ wind via IDW → NetCDF forcing | v02+ |
| [04_input_cmems_waves](04_input_cmems_waves.ipynb) | Time-varying Hs/Tp/Dir from CMEMS → 9 segmented TPAR `.bnd` | v03b+ |

### Model builds (`10–19`)

| Notebook | Model |
|---|---|
| [10_build_v01](10_build_v01.ipynb) | **v01** — baseline 3D hydro (fixes applied to Model B) |
| [11_build_v02](11_build_v02.ipynb) | **v02** — v01 + datum offset, obs-point relocation, central C1/C2/C3 |
| [12_build_v03](12_build_v03.ipynb) | **v03** — v02 + waves + tracer + hypersaline init + extended period |
| [13_build_v03_wave_coupling](13_build_v03_wave_coupling.ipynb) | v03 SWAN + DIMR coupler setup (run alongside 12) |

### Validation (`20–29`)

| Notebook | Target | Coverage |
|---|---|---|
| [20_valid_v01_wl](20_valid_v01_wl.ipynb) | v01 & v02 | Water level vs in-situ tide gauges + Willmott skill |
| [21_valid_v03b](21_valid_v03b.ipynb) | v03b (CMEMS waves) | WL + wave sanity; flagged `hwav.std=0` + `iniWithNudge` bugs |
| [22_valid_v03c](22_valid_v03c.ipynb) | v03c (bugfixes + tracers) | Hypersaline init confirmed; tracer + lateral diagnostics |

### Science analyses (`30–39`)

| Notebook | Purpose |
|---|---|
| [30_analysis_v01_diagnostics](30_analysis_v01_diagnostics.ipynb) | v01 datum bias, drying, vertical profile extraction |
| [32_analysis_particle_tracking](32_analysis_particle_tracking.ipynb) | OpenDrift + windage vs July 2025 Stokes drifter tracks |
| [33_analysis_residence_time](33_analysis_residence_time.ipynb) | Knudsen bulk estimate + Eulerian passive-tracer recipe |

### Utility (`40–49`)

| Notebook | Runs on | Purpose |
|---|---|---|
| [40_util_edito_postproc](40_util_edito_postproc.ipynb) | EDITO JupyterLab | Validate S3 access + stream map.nc via s3fs (no local download) |
| [41_util_edito_map_subset](41_util_edito_map_subset.ipynb) | EDITO JupyterLab | Merge 4-partition 57 GB map.nc, subset to ~300 MB, upload to `DFM_OUTPUT_SUBSET/` |

### Archive

- [archive/03b_roughness_alternatives](archive/03b_roughness_alternatives.ipynb) — experimental Lyzenga + Random Forest roughness method; not used by any canonical build.
- [archive/16_bocasud_investigation](archive/16_bocasud_investigation.ipynb) — one-off diagnostic that solved the v02 BocaSud WL outlier; results already rolled into v03.

## Reading order

For someone returning to the project after a break, a minimal path to reproduce the current state:

1. **Setup**: [00_setup_domain_mesh](00_setup_domain_mesh.ipynb).
2. **Inputs** (in any order): [02_input_insitu_wl_wind](02_input_insitu_wl_wind.ipynb), [03_input_blended_wind](03_input_blended_wind.ipynb), [04_input_cmems_waves](04_input_cmems_waves.ipynb), [01_input_satellite_roughness](01_input_satellite_roughness.ipynb).
3. **Build v03** (current reference): [12_build_v03](12_build_v03.ipynb) + [13_build_v03_wave_coupling](13_build_v03_wave_coupling.ipynb).
4. **Run** (see root [README](../README.md) for EDITO workflow).
5. **Validate**: [22_valid_v03c](22_valid_v03c.ipynb) for the latest run.
6. **Post-process large output**: [41_util_edito_map_subset](41_util_edito_map_subset.ipynb) if running on EDITO, else [40_util_edito_postproc](40_util_edito_postproc.ipynb).

## Convention for new notebooks

- Pick the next free number inside the appropriate block (gaps like `05–09`, `14–19`, `23–29`, `31`, `34–39`, `42–49` are intentionally reserved).
- Name as `<NN>_<role>_<version?>_<slug>.ipynb`. Version tag is present when the notebook targets a specific model revision; omit for cross-cutting utilities.
- If the notebook is clearly experimental / one-off / superseded by a later version, move it to `archive/` once its lessons are rolled into the mainline.
- Keep the ASCII safe: use `->` over `→`, `deg` over `°` (see `memory/notebook_unicode_writing.md`).
