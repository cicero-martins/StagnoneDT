"""Build extended uxuyadvectionvelocitybnd .bc for v04AE 49-node .pli (Jul 1-13).

The existing uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc in
model/dflowfm_v04AE_d10d12/ only covers Jul 1 -> Jul 10 12:00 (copied from
v04AE master that was for Jul 1-10 window). The continuation pipeline N-2 needs
coverage through Jul 13+ when publish day approaches Jul 13.

Adapted from build_uxuy_bc_v05_manual.py.

Inputs:
  - data/raw/cmems_v04AE_d10d12/cmems_uo_2025-07-01_2025-07-13.nc
  - data/raw/cmems_v04AE_d10d12/cmems_vo_2025-07-01_2025-07-13.nc
  - model/dflowfm_v04AE/Stagnone_dxy01_15m.pli (49 nodes)

Output:
  - model/dflowfm_v04AE_d10d12/uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc
    (covers 2025-07-01 00:00 -> 2025-07-13 00:00, 49 nodes)
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
CMEMS_DIR = ROOT / 'data' / 'raw' / 'cmems_v04AE_d10d12'
PLI = ROOT / 'model' / 'dflowfm_v04AE' / 'Stagnone_dxy01_15m.pli'
DST_DIR = ROOT / 'model' / 'dflowfm_v04AE_d10d12'
OUT_BC = DST_DIR / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'

REFDATE = pd.Timestamp('2025-01-01 00:00')
T_START = pd.Timestamp('2025-07-01 00:00')
T_STOP  = pd.Timestamp('2025-07-13 00:00')


def parse_pli(path: Path):
    """Yield (name, [(x,y,name), ...]) per polyline block."""
    blocks = []
    with open(path) as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln and not ln[0].isdigit() and ln[0] != '-':
            cur_name = ln.strip()
            i += 1
            parts = lines[i].split()
            n_pts = int(parts[0])
            i += 1
            cur_pts = []
            for _ in range(n_pts):
                row = lines[i].split()
                x = float(row[0]); y = float(row[1])
                pt_name = row[2] if len(row) > 2 else None
                cur_pts.append((x, y, pt_name))
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
    uo = uo_ds['uo'].sel(time=slice(T_START, T_STOP))
    vo = vo_ds['vo'].sel(time=slice(T_START, T_STOP))
    print(f'  dims: {dict(uo.sizes)}')
    print(f'  time range: {pd.Timestamp(uo.time.values[0])} -> {pd.Timestamp(uo.time.values[-1])}')

    depths_pos = uo.depth.values.astype(float)
    depths_neg = (-depths_pos).tolist()
    n_z = len(depths_pos)
    print(f'  depth: {n_z} levels, {depths_pos[0]:.2f} -> {depths_pos[-1]:.2f} m')

    times = pd.to_datetime(uo.time.values)
    t_min = ((times - REFDATE).total_seconds() / 60.0).astype(float)
    n_t = len(t_min)

    blocks = parse_pli(PLI)
    assert len(blocks) == 1, f'Expected 1 polyline, got {len(blocks)}'
    pli_name, pts = blocks[0]
    print(f'  .pli: name={pli_name!r}, {len(pts)} nodes')

    DST_DIR.mkdir(parents=True, exist_ok=True)
    # Backup existing
    if OUT_BC.exists():
        bak = OUT_BC.with_suffix('.bc.bak.pre_extended')
        if not bak.exists():
            import shutil
            shutil.copy2(OUT_BC, bak)
            print(f'  backup: {bak.name}')

    with open(OUT_BC, 'w') as bc:
        bc.write('# written by build_uxuy_bc_v04AE_d10d12_extended.py\n')
        bc.write('# Extended uxuy covering 2025-07-01 -> 2025-07-13 for v04AE 49-node .pli\n')
        bc.write('\n[General]\nfileVersion = 1.01\nfileType    = boundConds\n')

        vertPos_str = ' '.join(f'{d:.6f}' for d in depths_neg)
        for k, (xn, yn, pt_name) in enumerate(pts, start=1):
            u_n = uo.interp(longitude=xn, latitude=yn, method='linear')
            v_n = vo.interp(longitude=xn, latitude=yn, method='linear')
            u_arr = np.nan_to_num(u_n.values, nan=0.0)
            v_arr = np.nan_to_num(v_n.values, nan=0.0)

            node_name = pt_name if pt_name else f'{pli_name}_{k:04d}'

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
            for iz in range(1, n_z + 1):
                bc.write('quantity          = ux\n')
                bc.write('unit              = m s-1\n')
                bc.write(f'vertPositionIndex = {iz}\n')
                bc.write('quantity          = uy\n')
                bc.write('unit              = m s-1\n')
                bc.write(f'vertPositionIndex = {iz}\n')
            for it in range(n_t):
                row = [f'{t_min[it]:.6f}']
                for iz in range(n_z):
                    row.append(f'{u_arr[it, iz]:.6f}')
                    row.append(f'{v_arr[it, iz]:.6f}')
                bc.write(' '.join(row) + '\n')

    sz_kb = OUT_BC.stat().st_size / 1024
    print(f'\nWROTE: {OUT_BC}  ({sz_kb:.0f} KB)')
    uo_ds.close()
    vo_ds.close()


if __name__ == '__main__':
    main()
