"""Build uxuyadvectionvelocitybnd .bc for v05 manually (bypass dfm_tools/hydrolib).

Use only if `build_cmems_bc_v05.py` failed to produce
`uxuyadvectionvelocitybnd_CMEMS_Stagnone_v05.bc` due to the hydrolib 1.0.0
vector quantity bug (see memory [[dfm_tools_hydrolib_mismatch_2026]]).

This bypasses dfm_tools entirely and writes the T3D vector format directly.
Format reference: model/dflowfm_v04AE/uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc

Inputs:
  - data/raw/cmems_v05/cmems_uo_2025-07-01_2025-07-13.nc  (daily, ~141 z, eastward current)
  - data/raw/cmems_v05/cmems_vo_2025-07-01_2025-07-13.nc  (daily, ~141 z, northward current)
  - model/dflowfm_v05/Stagnone_v05.pli                     (333 nodes)

Output:
  - model/dflowfm_v05/uxuyadvectionvelocitybnd_CMEMS_Stagnone_v05.bc
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
CMEMS_DIR = ROOT / 'data' / 'raw' / 'cmems_v05'
DST_DIR = ROOT / 'model' / 'dflowfm_v05'
PLI = DST_DIR / 'Stagnone_v05.pli'
OUT_BC = DST_DIR / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_v05.bc'

REFDATE = pd.Timestamp('2025-01-01 00:00')
T_START = pd.Timestamp('2025-07-01 00:00')
T_STOP  = pd.Timestamp('2025-07-13 00:00')


def parse_pli(path: Path):
    """Yield (name, [(x,y), ...]) per polyline block. Stagnone_v05.pli has 1 block."""
    blocks = []
    cur_name = None
    cur_pts = []
    with open(path) as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        # Header: name on its own, then "<n_pts> 2"
        if not ln[0].isdigit() and ln[0] != '-':
            cur_name = ln.strip()
            i += 1
            parts = lines[i].split()
            n_pts = int(parts[0])
            i += 1
            cur_pts = []
            for _ in range(n_pts):
                xs, ys = lines[i].split()[:2]
                cur_pts.append((float(xs), float(ys)))
                i += 1
            blocks.append((cur_name, cur_pts))
        else:
            i += 1
    return blocks


def main():
    uo_path = next(CMEMS_DIR.glob('cmems_uo_*.nc'))
    vo_path = next(CMEMS_DIR.glob('cmems_vo_*.nc'))
    print(f'uo: {uo_path.name}')
    print(f'vo: {vo_path.name}')

    uo_ds = xr.open_dataset(uo_path)
    vo_ds = xr.open_dataset(vo_path)
    uo = uo_ds['uo']
    vo = vo_ds['vo']
    print(f'  uo dims: {dict(uo.sizes)}, depth: {len(uo.depth)} levels')

    # Subset time
    uo = uo.sel(time=slice(T_START, T_STOP))
    vo = vo.sel(time=slice(T_START, T_STOP))
    print(f'  time range: {pd.Timestamp(uo.time.values[0])} -> {pd.Timestamp(uo.time.values[-1])}')

    # Depth: CMEMS z is positive-down (e.g. 1.0, 3.0, ...). The .bc expects
    # ZDatum (positive-up): write as negative numbers.
    depths_pos = uo.depth.values.astype(float)
    depths_neg = (-depths_pos).tolist()
    n_z = len(depths_pos)
    print(f'  depth range: {depths_pos[0]:.2f} -> {depths_pos[-1]:.2f} m (will write as {depths_neg[0]} .. {depths_neg[-1]})')

    # Times in 'minutes since refdate'
    times = pd.to_datetime(uo.time.values)
    t_min = ((times - REFDATE).total_seconds() / 60.0).astype(float)
    n_t = len(t_min)

    # Parse .pli
    blocks = parse_pli(PLI)
    assert len(blocks) == 1, f'Expected 1 polyline, got {len(blocks)}'
    pli_name, pts = blocks[0]
    print(f'  .pli: name={pli_name!r}, {len(pts)} nodes')

    # Open .bc
    OUT_BC.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_BC, 'w') as bc:
        bc.write('# written by build_uxuy_bc_v05_manual.py (manual fallback)\n')
        bc.write('\n[General]\nfileVersion = 1.01\nfileType    = boundConds\n')

        vertPos_str = ' '.join(f'{d:.6f}' for d in depths_neg)
        for k, (xn, yn) in enumerate(pts, start=1):
            # Bilinear interp uo, vo at (xn, yn)
            u_n = uo.interp(longitude=xn, latitude=yn, method='linear')
            v_n = vo.interp(longitude=xn, latitude=yn, method='linear')
            u_arr = u_n.values  # shape (n_t, n_z)
            v_arr = v_n.values
            # Replace NaN (below seafloor) with 0.0 — FM treats as no advection at that z
            u_arr = np.nan_to_num(u_arr, nan=0.0)
            v_arr = np.nan_to_num(v_arr, nan=0.0)

            node_name = f'{pli_name}_{k:04d}'
            bc.write('\n[Forcing]\n')
            bc.write(f'name              = {node_name}\n')
            bc.write('function          = t3d\n')
            bc.write('offset            = 0.0\n')
            bc.write('factor            = 1.0\n')
            bc.write(f'vertPositions     = {vertPos_str}\n')
            bc.write('vertInterpolation = linear\n')
            bc.write('vertPositionType  = ZDatum\n')
            bc.write('timeInterpolation = linear\n')
            bc.write('quantity          = time\n')
            bc.write(f'unit              = minutes since {REFDATE.strftime("%Y-%m-%d %H:%M:%S")} +00:00\n')
            bc.write('vector            = uxuyadvectionvelocitybnd:ux,uy\n')
            # Quantity headers interleaved by z-level
            for iz in range(1, n_z + 1):
                bc.write('quantity          = ux\n')
                bc.write('unit              = m s-1\n')
                bc.write(f'vertPositionIndex = {iz}\n')
                bc.write('quantity          = uy\n')
                bc.write('unit              = m s-1\n')
                bc.write(f'vertPositionIndex = {iz}\n')
            # Time series: each row = time(min) ux_z1 uy_z1 ux_z2 uy_z2 ... ux_zN uy_zN
            for it in range(n_t):
                row = [f'{t_min[it]:.6f}']
                for iz in range(n_z):
                    row.append(f'{u_arr[it, iz]:.6f}')
                    row.append(f'{v_arr[it, iz]:.6f}')
                bc.write(' '.join(row) + '\n')

            if (k % 50 == 0) or (k == len(pts)):
                print(f'    [{k}/{len(pts)}] wrote forcing for {node_name}')

    sz_kb = OUT_BC.stat().st_size / 1024
    print(f'\nWROTE: {OUT_BC}  ({sz_kb:.0f} KB)')

    uo_ds.close()
    vo_ds.close()


if __name__ == '__main__':
    main()
