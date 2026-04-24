# Stagnone di Marsala — Digital Twin

3D coupled wave-hydrodynamic Delft3D FM + SWAN digital twin of the Stagnone di Marsala lagoon (Sicily, Italy). The coupled runs are planned to execute on the EDITO Datalab platform (Delft3D FM is natively available there via the `delft3dfmrun-docker` service), with a GitHub Actions (or similar CI) workflow orchestrating the build / upload / launch cycle from the repository.

This repository serves as the computational base for an ongoing **PhD project** at the Università degli Studi di Palermo. The aim is to answer the research questions listed below — 3D hydrodynamics under wind forcing, lagoon residence time, inlet exchange with the open Mediterranean, seagrass-driven bottom roughness and wave attenuation, episodic turbidity sources, and sediment resuspension — contributing to the doctoral thesis and related peer-reviewed publications.

<p align="center">
  <img src="figures/planet_composite_rgb_preview.png" width="520" alt="PlanetScope summer 2025 median composite"/><br/>
  <em>PlanetScope SuperDove 8-band median composite, 9 dates Jun–Sep 2025, 3 m GSD. Lagoon (centre-left), Trapani airport + city (top), western Sicily coastline. See <a href="notebooks/archive/03b_roughness_alternatives.ipynb">03b notebook</a>.</em>
</p>

## Status (April 2026)

| Area | Status |
|------|--------|
| Mesh + bathymetry | Complete — 21 k nodes unstructured FM mesh, 2006 + modern bathy fusion |
| Input forcing | ERA5+in-situ blended wind, CMEMS time-varying wave BCs, hypersaline init |
| v01 (baseline) | 9-day local run complete |
| v02 (calibration fixes) | Validated against 3 WL stations |
| v03a/b/c | Completed on EDITO (9 days, ~12 h wallclock); validated |
| v03d (next) | Planned — D-Morph + `ncFormat=3` fix + ERA5 evap (see [roadmap](docs/roadmap_post_v03c.md)) |
| Offshore validation | WL at Marettimo tide gauge (Trilha B) — BC tide propagates (Corr 0.95); ~1.8× amplitude over |
| Morphology (sediment) | Feasibility complete (Trilha C1) — morph approved for v03d, S2 field event 2025-10-06 |
| HDF5 coupling bug | Workaround identified (Trilha D) — `ncFormat=3`; Deltares support drafted |
| Satellite roughness | Sentinel-2 RF + PlanetScope 8-band RF (CV 0.92) — **experimental, not yet applied to FM** |
| Particle tracking | OpenDrift baseline reproducing July 2025 drifter tracks |
| Residence time | Knudsen bulk estimate; Eulerian tracer recipe for v03d+ |
| EDITO deployment | Functional — `delft3dfmrun-docker` service |

## Site description

The Stagnone di Marsala is a shallow coastal lagoon on Sicily's western coast:

- **Area:** ~12 km²
- **Depth:** 0.5–2 m (microtidal, ~0.2–0.3 m tidal range)
- **Salinity regime:** hypersaline (~42 psu interior vs ~37.5 psu offshore)
- **Vegetation:** extensive *Posidonia oceanica* and *Cymodocea nodosa* seagrass beds
- **Inlets:** two — Boca Nord (~0.3 m deep) and Boca Sud (~1.5 m deep)
- **Centre:** ~37.86°N, 12.46°E (WGS84)
- **Regime:** wind-dominated, despite microtidal forcing

The lagoon is a protected area. Despite its shallow depth, significant vertical flow structure is observed (wind-driven surface currents vs. bottom currents) — this demands a **3D model**.

## Research questions

1. What is the vertical flow structure in such shallow water, and how is it driven by wind?
2. What is the residence time of lagoon water, and how does it vary with wind regimes?
3. How do the two inlets exchange water with the open Mediterranean?
4. What are the effects of seagrass beds on bottom friction and wave attenuation?
5. How do episodic turbidity sources (canal discharges, rain pulses) propagate through the lagoon?
6. Are offshore swell events strong enough to mobilise lagoon sediment, and if so where?

## Methodology — architecture

- **D-Flow FM**: 3D unstructured grid, 10 sigma layers, k-epsilon turbulence, UNESCO density, WGS84
- **SWAN**: nested outer (~800 m) + inner (~80 m) grids, 36 directions, JONSWAP friction + vegetation dissipation
- **DIMR**: couples Flow + Wave every 600 s
- **Reference models** (in `oldModel/`): Model A (simple, lagoon-only) and Model B (modelbuilder-based, offshore boundary); v01 starts from Model B

## Model version history

| Feature | v01 | v02 | v03a | v03b | v03c | v03d (plan) |
|---------|:---:|:---:|:----:|:----:|:----:|:-----------:|
| Datum offset on WL BC | 0.0 m | +0.42 m | +0.42 m | +0.42 m | +0.42 m | +0.42 m |
| Central 3D obs (C1/C2/C3) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Blended wind (ERA5 + in-situ) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Hypersaline init (42 psu interior) | — | — | ✓ | ✓ | ✓ | ✓ |
| SWAN wave coupling | — | — | stationary | CMEMS TPAR (stat.) | TPAR (stat.) | TPAR (stat.) |
| Initial tracer (lagoon) | — | — | ✓ | ✓ | ✓ | ✓ |
| Turbidity tracer buffers (airport + saltpans) | — | — | — | — | pulse (lateral) | init buffer 500 m |
| `ncFormat` (output) | 4 | 4 | 4 | 4 | 4 (waves stuck) | **3** (fixes waves) |
| ERA5 evaporation | — | — | — | — | — | ✓ (plan) |
| D-Morphology (sand + silt) | — | — | — | — | — | ✓ (plan) |
| Simulation period | 9 d | 9 d | 9 d | 9 d | 9 d | 9 d + Oct-event v03e |

## Preliminary results

### Computational grids (v03a and beyond)

<p align="center">
  <img src="figures/swan_grids_v03a.png" width="760" alt="FM mesh + SWAN nested grids overview"/><br/>
  <em>Left: FM unstructured mesh (grey nodes) overlaid with the SWAN outer grid (~800 m, pink) and the new inner nested grid (~100 m, blue) covering the lagoon proper. Right: zoom on the inner-SWAN decision — old bbox (orange dashed) sized to the lagoon, new bbox (blue) extended north to include Trapani port and offshore approaches so the inlet-approach wave field is resolved.</em>
</p>

### Water-level validation

**Inside the lagoon** — three in-situ stations (BocaNord, BocaSud, AltaVilaEst), v03c vs observed for the 9-day July 2025 window:

<p align="center">
  <img src="figures/v03c_wl_validation.png" width="760" alt="v03c water-level validation at 3 lagoon stations"/><br/>
  <em>BocaNord: RMSE = 10.6 cm, r = 0.94, Willmott d = 0.71. BocaSud: RMSE = 7.4 cm, r = 0.92, d = 0.80. AltaVilaEst: RMSE = 10.4 cm, r = 0.81, d = 0.70. Model reproduces phase well; tidal amplitude is slightly overestimated (visible in peaks).</em>
</p>

**Offshore at Marettimo** (Trilha B) — ISPRA tide gauge, ~20 km west of the lagoon:

<p align="center">
  <img src="figures/v03c_wl_marettimo_map.png" width="700" alt="Marettimo ring-scan diagnostic map"/><br/>
  <em>Left: fraction of time each face has a finite s1 value — green = always wet, red = drying frequently. The literal-nearest face to the ISPRA tide gauge (red star) sits at the edge of a drying ring. Right: bed level, confirming the chosen cell is at only −0.41 m.</em>
</p>

<p align="center">
  <img src="figures/v03c_wl_marettimo_best_cell.png" width="780" alt="Marettimo best-cell overlay"/><br/>
  <em>After ring-scanning 1,394 always-wet faces at 0.5–3 km offshore, the best-matching cell (green) recovers the tidal phase almost perfectly (Corr 0.95). The original literal-nearest cell (blue, at the drying edge) had flat-lined. Observed signal (black) from the JRC webcritech ISPRA gauge.</em>
</p>

Ring-scan **isolates the issue**: the CMEMS west-boundary tidal forcing propagates correctly (Corr 0.93–0.96, Willmott d 0.89 across 1,394 cells), but the model over-amplifies the tidal range by ~1.8× at this location (Std_mod 11.2 cm vs Std_obs 6.3 cm). Under investigation as part of v03d. Data fetched from JRC's [webcritech TAD server device 658](https://webcritech.jrc.ec.europa.eu/TAD_server/Device/658). Full analysis in [notebook 23_valid_v03c_offshore](notebooks/23_valid_v03c_offshore.ipynb).

### Sediment resuspension feasibility (Trilha C1)

<p align="center">
  <img src="figures/v03c_proxy_uorb_inlet.png" width="760" alt="Proxy u_orb at inlet vs offshore wave events"/><br/>
  <em>Proxy orbital velocity at the inlet (h = 1.5 m) from the offshore CMEMS wave time series, for three shoaling-attenuation scenarios. Thresholds for incipient motion of silt (0.035 m/s), fine sand (0.14 m/s), and medium sand (0.22 m/s) are crossed during the 2025-07-08/10 swell event.</em>
</p>

Three independent lines of evidence — iter-1 SWAN output (`u_orb` = 0.186 m/s at BocaNord), offshore CMEMS swell propagation, and a Sentinel-2 scene from 2025-10-06 with visible resuspension plumes — all justify adding **D-Morphology** to v03d. Two fractions planned: sand (d50 = 150 µm) for the inlet channel, silt (d50 = 30 µm) for the lagoon interior. XBeach ruled out (surf-zone model; not applicable to a sheltered lagoon). Full analysis in [notebook 31_analysis_resuspension_feasibility](notebooks/31_analysis_resuspension_feasibility.ipynb).

### Satellite-derived bottom roughness — experimental

> **Not yet fed into the FM model.** The current v03c uses a uniform Manning baseline with optional trachytope overlay (see `model/dflowfm_v03c/roughness_satellite.xyz`); the RF-derived classification maps below are an offline experiment.

**Spectral signature QC of the training polygons** — mean reflectance ± 1σ across the 8 PlanetScope bands, for each of the four bottom classes (from `data/processed/training_polygons_03b.geojson`). Classes need to be spectrally separable before it makes sense to train a classifier:

<p align="center">
  <img src="figures/planet_training_spectral_signatures.png" width="720" alt="Spectral signatures of training polygons per class"/><br/>
  <em>Bare sand (orange) is clearly the brightest, peaking around green–yellow. Dense Posidonia (dark green) is the darkest, with a tight envelope. Sparse Cymodocea (light green) sits in between. Rock has the widest intra-class spread (n only 426 pixels). The four curves separate well, justifying an RF over these features.</em>
</p>

**Classification maps** — Sentinel-2 baseline vs PlanetScope 8-band experiment, both over the full FM domain:

<p align="center">
  <img src="figures/roughness_rf_full_domain.png" width="470" alt="Sentinel-2 RF bottom classification"/>
  <img src="figures/planet_rf_classification_full.png" width="470" alt="PlanetScope RF bottom classification"/>
</p>

**Left:** Sentinel-2 L2A + Lyzenga water-column correction + Random Forest over the full FM domain (10 m GSD, CV accuracy ~0.9). **Right:** PlanetScope SuperDove 8-band median composite (3 m GSD, 9 dates), Lyzenga DIIs + RF, CV accuracy **0.922**. Land pixels masked from the v03 LDB coastline files.

Feature importance on the Planet pipeline shows that the four extra Planet bands (coastal_blue, green_i, yellow, red_edge) absent from Sentinel-2 carry **46 % of the classification signal**; DIIs contribute only 1–3 % each. Implication: for this scene, finer spectral sampling outperforms water-column correction. Next step: convert the classification to a spatially-variable Manning / trachytope map and feed into v03d. See [03b_roughness_alternatives notebook](notebooks/archive/03b_roughness_alternatives.ipynb).

### Hypersaline dynamics

<p align="center">
  <img src="figures/v03c_salinity_timeseries.png" width="760" alt="Salinity time series per station"/><br/>
  <em>Interior lagoon salinity starts at 42 psu as intended (fix of v03b's <code>iniWithNudge=2</code> bug), but flushes to ~37.7 psu within ~12 hours under tidal exchange alone. Without surface evaporation the hypersaline regime is not sustainable.</em>
</p>

This drove the decision to add **ERA5 evaporation forcing** in v03d.

### HDF5 coupling debug (Trilha D)

A five-test isolation matrix (baseline / `nc3` / `HDF5_USE_FILE_LOCKING=FALSE` / serial / `AppendCOM=true`) pins down the bug to SWAN's HDF5 re-open-for-write of `com.nc`; only `ncFormat=3` (classic NetCDF) eliminates the error and restores time-varying waves. Trade-off: classic NetCDF has a 2 GB per-file limit — mitigated for the current 9-day window with `wrimap_*` reductions and a longer `mapInterval`. Full report in [docs/deltares_hdf5_coupling_report.md](docs/deltares_hdf5_coupling_report.md) (drafted for Deltares support).

### Wave orbital velocity — spatial pattern

<p align="center">
  <img src="figures/wave_orbital_velocity_v03.png" width="760" alt="Wave orbital velocity spatial field"/><br/>
  <em>Time-mean wave orbital velocity (m s⁻¹) over the FM domain for the v03 July 2025 window. Deep-blue offshore = negligible bed interaction; warm colours trace the coast where shoaling drives u_orb above the sand-mobilisation threshold. The Egadi islands (Marettimo, Levanzo, Favignana, top-left and centre) show the same signature. This spatial pattern is consistent with the inlet-focused resuspension hypothesis and will be revisited once the HDF5 fix feeds through to time-varying wave fields in v03d.</em>
</p>

## Roadmap

The post-v03c roadmap is split into six parallel tracks (A–F) converging on a v03d build + validation — see [docs/roadmap_post_v03c.md](docs/roadmap_post_v03c.md) for the full plan with hour budgets and dependencies. Tracks A, B, C1, D are complete; E (v03d build) + F (validation) are next.

## Notebook catalog

Notebooks live in `notebooks/`, organised in thematic numeric blocks (setup/input/build/valid/analysis/util). See [`notebooks/README.md`](notebooks/README.md) for the full index, per-version tree, and recommended reading order. Compact view:

| Block | Notebooks | Role |
|-------|-----------|------|
| `00–09` | `00_setup_domain_mesh`, `01_input_satellite_roughness`, `02_input_insitu_wl_wind`, `03_input_blended_wind`, `04_input_cmems_waves` | Setup + input forcing (cross-cutting) |
| `10–19` | `10_build_v01`, `11_build_v02`, `12_build_v03`, `13_build_v03_wave_coupling` | Model configuration per version |
| `20–29` | `20_valid_v01_wl`, `21_valid_v03b`, `22_valid_v03c`, `23_valid_v03c_offshore` | Run validation against in-situ / satellite |
| `30–39` | `30_analysis_v01_diagnostics`, `31_analysis_resuspension_feasibility`, `32_analysis_particle_tracking`, `33_analysis_residence_time` | Science analyses |
| `40–49` | `40_util_edito_postproc`, `41_util_edito_map_subset` | EDITO-side tooling |
| `archive/` | `03b_roughness_alternatives` (Planet 8-band experimental), `16_bocasud_investigation` | Experimental / one-off (preserved in git) |

**Convention for new notebooks**: `<NN>_<role>_<version?>_<slug>.ipynb` — role is one of `setup`/`input`/`build`/`valid`/`analysis`/`util`; version tag (`v03c`, `v04`, etc.) only when tied to a specific model revision.

## EDITO deployment

The primary execution target is EDITO Datalab (32 GiB RAM, 8 CPU, 50 GiB storage). Workflow:

```bash
# From your laptop
python scripts/edito_sync.py clean-output --yes
python scripts/edito_sync.py clean-input --yes
python scripts/edito_sync.py upload --model-dir model/dflowfm_v03c
python scripts/edito_sync.py sync-code

# On EDITO Datalab UI: New process → delft3dfm_run_docker
# The service runs `bash run_model.sh` from s3://<user-bucket>/DFM_INPUT/

# Post-processing: launch JupyterLab on EDITO, run 40_util_edito_postproc
# or 41_util_edito_map_subset to compress the 57 GB map.nc output
```

Full operational guide: [docs/EDITO_WORKFLOW.md](docs/EDITO_WORKFLOW.md)

**Critical gotcha:** every model uploaded to EDITO must include `run_model.sh` at the model root (LF line endings). Missing it yields a misleading Kubernetes `kube-root-ca.crt not registered` error. See `docs/EDITO_WORKFLOW.md` for the template.

## Setup

### Python environment

```bash
conda env create -f environment.yml -n dfm_tools_env
conda activate dfm_tools_env
python -m ipykernel install --user --name dfm_tools_env --display-name "dfm_tools (Python 3.12)"
pip install python-docx boto3   # extras for the report generator and EDITO sync
```

### Delft3D FM (local execution only — EDITO uses container)

Download [Delft3D FM Suite 2026.01 HMWQ](https://download.deltares.nl/delft3dfm) and update the path in `model/dflowfm/run_model.bat` if needed.

### Credentials

- **CMEMS** (ocean BC): https://data.marine.copernicus.eu/
- **ECMWF CDS** (ERA5): https://cds.climate.copernicus.eu/
- **CDSE** (Sentinel-2): https://dataspace.copernicus.eu/
- **Planet** (PlanetScope SR): https://www.planet.com/account/
- **EDITO** (Datalab S3): https://datalab.dive.edito.eu/account/storage

Copy `.env.example` → `.env` and fill EDITO S3 credentials. Never commit `.env` — it's in `.gitignore`.

## Reproducing results

Sequence for a fresh run:

1. **Setup env** (above).
2. **Get Delft3D FM** installed (or use EDITO).
3. **Verify reference models** exist: `oldModel/input/` (A), `oldModel/Stagnone_py_lagoon3D.dsproj_data/` (B), `oldModel/Stagnone_justLagoon/` (lagoon polygon source).
4. **Input forcing** (`00–09` block):
   - `02_input_insitu_wl_wind` → QC in-situ data → `data/processed/`
   - `03_input_blended_wind` → blended wind NetCDFs → `model/dflowfm_v02/`
   - `01_input_satellite_roughness` → Sentinel-2 roughness (optional for v02+)
   - `04_input_cmems_waves` → CMEMS wave BCs for v03b+
5. **Build model** (`10–19` block):
   - `11_build_v02` → v02 from v01 lessons
   - `12_build_v03` → v03 from v02
6. **Run**:
   - Local: `cd model/dflowfm_v02 && run_model.bat`
   - EDITO: `python scripts/edito_sync.py upload --model-dir model/dflowfm_v02`, then launch via Datalab UI
7. **Validate + analyse** (`20–39` blocks):
   - Local post-processing: `20_valid_v01_wl`, `21_valid_v03b`, `22_valid_v03c`, `23_valid_v03c_offshore`, `30_analysis_v01_diagnostics`
   - EDITO post-processing: `40_util_edito_postproc` (streams map.nc via s3fs), `41_util_edito_map_subset` (slices 57 GB → ~200 MB)
8. **Research extensions**:
   - `31_analysis_resuspension_feasibility` — u_orb diagnostics + morph justification
   - `32_analysis_particle_tracking` — OpenDrift on v03a surface currents
   - `33_analysis_residence_time` — Eulerian tracer + Knudsen

## Project structure

```
StagnoneDT/
├── notebooks/             # Main workflow (17 Jupyter notebooks + archive/)
├── scripts/               # edito_sync.py, planet_mosaic_composite.py, download_marettimo_wl.py, ...
├── docs/                  # EDITO_WORKFLOW.md, roadmap_post_v03c.md, deltares_hdf5_coupling_report.md, progress_report_*.md
├── model/
│   ├── dflowfm/           # v01 (baseline)
│   ├── dflowfm_v02/       # v02 (calibration fixes)
│   ├── dflowfm_v03a/      # v03a (nested SWAN + hypersaline)
│   ├── dflowfm_v03b/      # v03b (CMEMS time-varying waves)
│   ├── dflowfm_v03c/      # v03c (iniWithNudge + tracer fixes, current validated)
│   └── dflowfm_v03d/      # v03d (morph + ncFormat=3 fix + evaporation, in prep)
├── data/
│   ├── raw/
│   │   ├── insitu/        # 3 WL + 2 wind station CSVs + drifter data + Marettimo tide gauge
│   │   └── satellite/     # Sentinel-2 + PlanetScope 18 scenes (summer 2025, gitignored)
│   └── processed/         # QC'd data + planet composite NetCDF (gitignored) + metrics CSVs
├── oldModel/              # Reference models A & B + 2006 bathymetry (read-only)
├── reference/             # Papers, User Days materials, modelbuilder example
├── figures/               # Generated plots from notebooks
├── memory/                # (not in repo) project context / design decisions
├── environment.yml        # Conda environment spec
├── .env.example           # EDITO credentials template
├── .gitignore
└── README.md              # This file
```

## Critical reference files (read-only)

- `oldModel/Stagnone_py_lagoon3D.dsproj_data/Stagnone_dxy01_15m/input/Stagnone_dxy01_15m_net.nc` — primary mesh
- `oldModel/Stagnone_py_lagoon3D.dsproj_data/Stagnone_dxy01_15m/input/Stagnone_dxy01_15m.pli` — 49-point offshore boundary
- `oldModel/Stagnone_justLagoon/FlowFM_net.nc` — hand-drawn lagoon mesh (used for polygon extraction)
- `oldModel/bat_stagnone_20m_2006.xyz` — 2006 bathymetry (189K points)
- `reference/modelbuilder_example.ipynb` — dfm_tools modelbuilder template

## Publication ideas

Possible directions for peer-reviewed output arising from this work, alongside the PhD thesis. Titles and target journals are tentative; scope and emphasis will evolve with the results:

1. 3D hydrodynamic modelling of a shallow Mediterranean seagrass lagoon — vertical flow structure under wind forcing (candidate venues: *Estuarine, Coastal and Shelf Science* / *Continental Shelf Research*).
2. Satellite-derived bottom roughness for shallow lagoon modelling — PlanetScope 8-band vs Sentinel-2 (candidate venues: *Remote Sensing of Environment* / *Ecological Modelling*).
3. Coupled wave-hydrodynamic modelling in a seagrass lagoon with vegetation drag (candidate venues: *Ocean Modelling* / *Coastal Engineering*).
4. Multi-source bathymetry fusion for vegetated shallow lagoons (candidate venues: *Remote Sensing* / *Journal of Coastal Research*).
5. A reusable digital-twin framework for protected Mediterranean lagoons on the EDITO platform (candidate venues: *Environmental Modelling & Software* / *Science of the Total Environment*).

## Documentation

- [docs/EDITO_WORKFLOW.md](docs/EDITO_WORKFLOW.md) — operational workflow on EDITO Datalab
- [docs/roadmap_post_v03c.md](docs/roadmap_post_v03c.md) — post-v03c roadmap (Trilhas A–F)
- [docs/deltares_hdf5_coupling_report.md](docs/deltares_hdf5_coupling_report.md) — HDF5 coupling bug report + test matrix for Deltares support
- [docs/progress_report_2026-04-22.md](docs/progress_report_2026-04-22.md) — v03b → v03c debugging session
- [docs/satellite_roughness_review.md](docs/satellite_roughness_review.md) — literature review of 28 roughness papers
- [docs/progress_report_v1.docx](docs/progress_report_v1.docx) — internal technical progress report (generated via `scripts/generate_report.py`)

## License

Private repository. No license specified.
