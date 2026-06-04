"""Extract Marettimo WL time series from map.nc files on simit-server.

Finds the cell nearest to (12.0753, 37.9747) with bl < -0.3 m
(per marettimo_validation_cell.md convention) and saves a CSV per run.

Usage (on simit-server):
  ~/miniconda3/envs/stagnone_extract/bin/python extract_marettimo_from_map.py

Output: ~/StagnoneDT/runs/forecast/marettimo_wl_chain_jul25.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

RUNS_DIR = Path.home() / 'StagnoneDT' / 'runs' / 'forecast'
OUT_CSV  = RUNS_DIR / 'marettimo_wl_chain_jul25.csv'

# Target: v03d-compatible Marettimo cell (memory: marettimo_validation_cell.md)
LON_TGT = 12.0753
LAT_TGT = 37.9747
BL_MAX  = -0.3   # only cells with bl < this (offshore, not intertidal)

RUNS = sorted([d for d in RUNS_DIR.iterdir()
               if d.is_dir() and d.name.startswith('d2025-07-')])

rows = []
cell_idx = None  # cache after first successful run

for run_dir in RUNS:
    out_dir = run_dir / 'DFM_OUTPUT_Stagnone_dxy01_15m'
    maps = sorted(out_dir.glob('*_0000_map.nc')) if out_dir.exists() else []
    if not maps:
        print(f'[skip] {run_dir.name}: no map.nc')
        continue
    map_nc = maps[0]
    print(f'Processing {run_dir.name} ...', flush=True)
    ds = xr.open_dataset(map_nc, mask_and_scale=False)

    # Find cell index once (same grid for all runs)
    if cell_idx is None:
        lon = ds['mesh2d_face_x'].values
        lat = ds['mesh2d_face_y'].values
        bl  = ds['mesh2d_flowelem_bl'].values
        dist = np.sqrt((lon - LON_TGT)**2 + (lat - LAT_TGT)**2)
        mask = bl < BL_MAX
        dist_masked = np.where(mask, dist, np.inf)
        cell_idx = int(np.argmin(dist_masked))
        print(f'  Marettimo cell: idx={cell_idx}, '
              f'lon={lon[cell_idx]:.4f}, lat={lat[cell_idx]:.4f}, '
              f'bl={bl[cell_idx]:.2f} m')

    wl = ds['mesh2d_s1'].isel(mesh2d_nFaces=cell_idx).to_pandas()
    wl.index = pd.DatetimeIndex(wl.index)
    wl.name = run_dir.name
    for t, v in wl.items():
        rows.append({'run': run_dir.name, 'time': t, 'wl_m': float(v)})
    ds.close()

df = pd.DataFrame(rows)
df.to_csv(OUT_CSV, index=False, float_format='%.6f')
print(f'\nSaved: {OUT_CSV}  ({len(df)} rows, {df["run"].nunique()} runs)')
