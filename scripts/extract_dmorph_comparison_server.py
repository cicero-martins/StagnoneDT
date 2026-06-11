"""Server-side extraction of D-Morph bed level change for vr and nodm runs.

Extracts mesh2d_mor_bl at t0 and t_final from all 8 partitions.
Saves: data/processed/dmorph_delta_vr.npz, dmorph_delta_bl.npz
Keys: face_x, face_y, bl_t0, bl_final, delta_bl

Run on simit server where full map.nc outputs exist.
"""
from pathlib import Path
import numpy as np
import xarray as xr

HOME = Path.home()
ROOT = HOME / 'StagnoneDT'
PROC = ROOT / 'data' / 'processed'
PROC.mkdir(parents=True, exist_ok=True)

RUNS = {
    'vr':  ROOT / 'model' / 'dflowfm_v04AE_vr'  / 'DFM_OUTPUT_Stagnone_dxy01_15m',
    'bl':  ROOT / 'model' / 'dflowfm_v04AE'      / 'DFM_OUTPUT_Stagnone_dxy01_15m',
}

BL_VAR = 'mesh2d_mor_bl'
NPART  = 8


def extract_run(run_name, out_dir):
    out_f = out_dir / f'dmorph_delta_{run_name}.npz'
    if out_f.exists():
        print(f'{run_name}: {out_f.name} already exists, skipping')
        return

    all_x, all_y, all_t0, all_tf = [], [], [], []
    for p in range(NPART):
        mp = out_dir / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not mp.exists():
            print(f'  partition {p}: NOT FOUND — {mp}')
            continue
        ds = xr.open_dataset(mp)
        if BL_VAR not in ds:
            print(f'  partition {p}: {BL_VAR} not found, vars: {list(ds.data_vars)[:5]}')
            ds.close()
            continue
        bl = ds[BL_VAR]   # (time, nFaces)
        fx = ds['mesh2d_face_x'].values
        fy = ds['mesh2d_face_y'].values
        t0 = bl.isel(time=0).values
        tf = bl.isel(time=-1).values
        n_t = bl.sizes['time']
        t_start = str(ds.time.values[0])[:19]
        t_end   = str(ds.time.values[-1])[:19]
        ds.close()
        all_x.append(fx);  all_y.append(fy)
        all_t0.append(t0); all_tf.append(tf)
        print(f'  partition {p}: {n_t} steps  {t_start} -> {t_end}  '
              f'delta range [{(tf-t0).min():.3f}, {(tf-t0).max():.3f}] m')

    if not all_x:
        print(f'{run_name}: no data extracted')
        return

    face_x   = np.concatenate(all_x)
    face_y   = np.concatenate(all_y)
    bl_t0    = np.concatenate(all_t0)
    bl_final = np.concatenate(all_tf)
    delta_bl = bl_final - bl_t0

    np.savez(out_f, face_x=face_x, face_y=face_y,
             bl_t0=bl_t0, bl_final=bl_final, delta_bl=delta_bl)
    print(f'{run_name}: saved {out_f.name}  '
          f'({len(face_x)} cells)  '
          f'delta range [{delta_bl.min():.3f}, {delta_bl.max():.3f}] m')


for run_name, run_dir in RUNS.items():
    print(f'\n=== {run_name} ===')
    extract_run(run_name, run_dir)

print('\nDone.')
