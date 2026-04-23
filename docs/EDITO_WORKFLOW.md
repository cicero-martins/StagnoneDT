# EDITO Datalab workflow — Stagnone DT

Short operational guide. Full context in `memory/reference_edito.md`.

## Setup (once)

1. Fill `.env` with temporary credentials from https://datalab.dive.edito.eu/account/storage.
2. `pip install boto3` in `dfm_tools_env`.

## Run cycle (per model version)

```bash
# 1. Clean old run artefacts
python scripts/edito_sync.py clean-output --yes
python scripts/edito_sync.py clean-input --yes

# 2. Upload model inputs (~140 MB for v02)
#    Ensure run_model.sh is present at model root (LF endings, nPart=1 or 4).
python scripts/edito_sync.py upload --model-dir model/dflowfm_v02

# 3. Upload project code (notebooks + scripts + small processed/)
python scripts/edito_sync.py sync-code

# 4. Launch the run via Datalab UI:
#    My Processes → New process → delft3dfm_run_docker (2D3D-HMWQ)
#    If nPart>1, confirm the pod requests >= nPart CPUs (advanced options or Process API).

# 5. Wait / monitor via Datalab UI.

# 6. Post-process on EDITO JupyterLab (recommended for large map.nc):
#    - Start JupyterLab service from the catalog
#    - In JupyterLab, pull code: see notebook 40_util_edito_postproc cell 2 (it uses boto3 to mirror CODE/)
#    - Run notebook 40_util_edito_postproc to validate S3 access + streaming of map.nc

# 7. Download small artefacts locally
python scripts/edito_sync.py download-his
```

## Gotchas discovered

- **`run_model.sh` must be present** at the model root with LF endings. Missing it produces a misleading `kube-root-ca.crt not registered` Kubernetes error that looks like infra but is actually the entrypoint missing. See `memory/feedback_edito_run_model_sh.md`.
- **Parallel runs** (`nPart > 1`) need `<process></process>` tag inside `<component>` in `dimr_config.xml` AND pod CPU request ≥ `nPart`.
- **Credentials expire** (usually 24h session). When `upload` fails with 403, refresh `.env` from the EDITO storage settings page.
- **Never re-upload while a run is active** — overwrites files being read by the pod.
- **Never download `map.nc` locally** — use s3fs streaming from EDITO JupyterLab (notebook 40_util_edito_postproc).

## Cost / storage strategy

- Keep only **1 model version's output** in `DFM_OUTPUT/` at a time.
- Clean between versions to stay under 50 GiB quota.
- Push analysis artefacts (CSV, PNG) to a separate `RESULTS/` prefix instead of leaving them in `DFM_OUTPUT/`.
