# Stagnone di Marsala — Digital Twin

3D coupled wave-hydrodynamic Delft3D FM + SWAN digital twin for the Stagnone di Marsala lagoon (Sicily, Italy), designed to run on the EDITO Datalab platform.

## Project status

| Component | Status |
|---|---|
| v01 model (baseline) | Complete — 9 days simulated locally |
| v02 model (calibration fixes) | Running on EDITO |
| v03 model (waves + tracer + hypersaline) | Built, pending v02 validation |
| EDITO deployment | Functional — `delft3dfm_run_docker` process |
| Particle tracking (`32_analysis_particle_tracking`) | Framework ready, execution pending |
| Residence time (`33_analysis_residence_time`) | Methodology + post-processing ready |
| Post-processing on EDITO (`40_util_edito_postproc`) | Streaming workflow validated |

## Site description

The Stagnone di Marsala is a shallow coastal lagoon on Sicily's western coast:
- **Area:** ~12 km²
- **Depth:** 0.5–2 m (microtidal, ~0.2–0.3 m tidal range)
- **Salinity regime:** hypersaline (~42 psu interior vs ~37.5 psu offshore)
- **Vegetation:** extensive *Posidonia oceanica* and *Cymodocea nodosa* seagrass beds
- **Inlets:** two — Boca Nord (~0.3 m deep) and Boca Sud (~1.5 m deep)
- **Center:** ~37.86°N, 12.46°E (WGS84)
- **Regime:** wind-dominated, despite microtidal forcing

The lagoon is a protected area. Despite its shallow depth, significant vertical flow structure is observed (wind-driven surface currents vs. bottom currents) — this demands a **3D model**.

## Research questions

1. What is the vertical flow structure in such shallow water, and how is it driven by wind?
2. What is the residence time of lagoon water, and how does it vary with wind regimes?
3. How do the two inlets exchange water with the open Mediterranean?
4. What are the effects of seagrass beds on bottom friction and wave attenuation?
5. How do episodic turbidity sources (canal discharges) propagate through the lagoon?

## Methodology — architecture

```
                +--------------------+
                |   EDITO Datalab    |
                |   (S3 + compute)   |
                +---------+----------+
                          |
          +---------------+----------------+
          |                                |
  +-------+-------+                +-------+--------+
  | D-Flow FM 3D  | <-- DIMR --->  |      SWAN      |
  | (hydrodynamic)|                |    (waves)     |
  +-------+-------+                +----------------+
          |
          v
   in-situ + satellite validation
```

- **D-Flow FM**: 3D unstructured grid, 10 sigma layers, k-epsilon turbulence, UNESCO density, WGS84
- **SWAN**: structured grid ~50 m, 36 directions, JONSWAP friction + vegetation dissipation
- **DIMR**: couples Flow + Wave every 600 s
- **Reference models** (in `oldModel/`): Model A (simple, lagoon-only) and Model B (modelbuilder-based, offshore boundary); v01 starts from Model B

## Model version comparison

| Feature | v01 | v02 | v03 |
|---------|-----|-----|-----|
| Datum offset (WL BC) | 0.0 m | +0.42 m | +0.42 m |
| Obs points BS / AE | drying issues | always-wet cells | always-wet cells |
| Central 3D obs (C1/C2/C3) | none | added | added |
| Wind forcing | ERA5 only | blended ERA5 + in-situ | blended ERA5 + in-situ |
| Initial salinity | uniform 37.5 psu | uniform 37.5 psu | **42 psu interior, 37.5 offshore** |
| Passive residence-time tracer | no | no | **yes** |
| SWAN wave coupling | no | no | **yes** (`Wavemodelnr=3`) |
| Simulation period | 9 days (Jul 1–10, 2025) | 9 days | **extended to ≥30 days (pending BC download)** |

## Notebook catalog

Notebooks live in `notebooks/`, organized in thematic numeric blocks. See [`notebooks/README.md`](notebooks/README.md) for the full index, per-version tree, and recommended reading order. Compact view:

| Block | Notebooks | Role |
|-------|-----------|------|
| `00–09` | `00_setup_domain_mesh`, `01_input_satellite_roughness`, `02_input_insitu_wl_wind`, `03_input_blended_wind`, `04_input_cmems_waves` | Setup + input forcing (cross-cutting) |
| `10–19` | `10_build_v01`, `11_build_v02`, `12_build_v03`, `13_build_v03_wave_coupling` | Model configuration per version |
| `20–29` | `20_valid_v01_wl`, `21_valid_v03b`, `22_valid_v03c` | Run validation against in-situ / satellite |
| `30–39` | `30_analysis_v01_diagnostics`, `32_analysis_particle_tracking`, `33_analysis_residence_time` | Science analyses |
| `40–49` | `40_util_edito_postproc`, `41_util_edito_map_subset` | EDITO-side tooling |
| `archive/` | `03b_roughness_alternatives`, `16_bocasud_investigation` | Experimental / one-off (preserved in git) |

**Convention for new notebooks**: `<NN>_<role>_<version?>_<slug>.ipynb` — role is one of `setup`/`input`/`build`/`valid`/`analysis`/`util`; version tag (`v03c`, `v04`, etc.) only when tied to a specific model revision.

## EDITO deployment

The primary execution target is EDITO Datalab (32 GiB RAM, 8 CPU, 50 GiB storage). Workflow:

```bash
# From your laptop
python scripts/edito_sync.py clean-output --yes
python scripts/edito_sync.py clean-input --yes
python scripts/edito_sync.py upload --model-dir model/dflowfm_v02
python scripts/edito_sync.py sync-code

# On EDITO Datalab UI: New process → delft3dfm_run_docker
# The service runs `bash run_model.sh` from s3://<user-bucket>/DFM_INPUT/

# Post-processing: launch JupyterLab on EDITO, run 40_util_edito_postproc (or 41_util_edito_map_subset)
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
7. **Validate + analyze** (`20–39` blocks):
   - Local post-processing: `20_valid_v01_wl`, `21_valid_v03b`, `22_valid_v03c`, `30_analysis_v01_diagnostics`
   - EDITO post-processing: `40_util_edito_postproc` (streams map.nc via s3fs), `41_util_edito_map_subset` (slices 57 GB → ~200 MB)
8. **Research extensions**:
   - `32_analysis_particle_tracking` — OpenDrift on v03a surface currents
   - `33_analysis_residence_time` — Eulerian tracer + Knudsen

## Project structure

```
StagnoneDT/
├── notebooks/             # Main workflow (13 Jupyter notebooks)
├── scripts/               # edito_sync.py + generate_report.py
├── docs/                  # EDITO_WORKFLOW.md + progress_report_v1.docx
├── model/
│   ├── dflowfm/           # v01 (baseline)
│   ├── dflowfm_v02/       # v02 (calibration fixes)
│   └── dflowfm_v03/       # v03 (waves + tracer + hypersaline)
├── data/
│   ├── raw/
│   │   ├── insitu/        # 3 WL + 2 wind station CSVs + drifter data
│   │   └── satellite/     # Sentinel-2 archive (gitignored, download on-demand)
│   └── processed/         # QC'd data + lagoon polygon
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

## Planned publications (5 Q1 papers)

1. **Paper 1:** "3D hydrodynamic modeling of a shallow Mediterranean seagrass lagoon: vertical flow structure under wind forcing" — *Estuarine, Coastal and Shelf Science* / *Continental Shelf Research*
2. **Paper 2:** "Satellite-derived bottom roughness for shallow lagoon modeling" — *Remote Sensing of Environment* / *Ecological Modelling*
3. **Paper 3:** "Coupled wave-hydrodynamic modeling in a seagrass lagoon" — *Ocean Modelling* / *Coastal Engineering*
4. **Paper 4:** "Multi-source bathymetry fusion for vegetated shallow lagoons" — *Remote Sensing* / *Journal of Coastal Research*
5. **Paper 5:** "A digital twin framework for protected Mediterranean lagoons on the EDITO platform" — *Environmental Modelling & Software* / *Science of the Total Environment*

## Documentation

- [docs/EDITO_WORKFLOW.md](docs/EDITO_WORKFLOW.md) — operational workflow on EDITO Datalab
- [docs/progress_report_v1.docx](docs/progress_report_v1.docx) — internal technical progress report (generated via `scripts/generate_report.py`)

## License

Private repository. No license specified.
