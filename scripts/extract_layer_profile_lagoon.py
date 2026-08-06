"""Mean speed per sigma layer, restricted to the lagoon interior.

Run on simit-server, where every member's map.nc lives. Emits CSV to stdout.
Lagoon interior = inside the box, wet (bl below the threshold), and excluding
the inlets so the profile describes the basin rather than the throats.
"""
import glob, sys
import numpy as np
import xarray as xr

ROOT = '/home/ciceromartinsjr/StagnoneDT/model/'
MEMBERS = [('nowaves', 'dflowfm_v04AE_nowaves'), ('nodm', 'dflowfm_v04AE_nodm'),
           ('nodm_vr', 'dflowfm_v04AE_nodm_vr'), ('bl', 'dflowfm_v04AE'),
           ('vr', 'dflowfm_v04AE_vr')]
LON = (12.432, 12.484)
LAT = (37.828, 37.900)
BL_MAX = -0.15
T0, T1 = '2025-07-07', '2025-07-10'

print('member,layer,mean_speed,n_faces')
for key, d in MEMBERS:
    files = sorted(glob.glob(ROOT + d + '/DFM_OUTPUT_Stagnone_dxy01_15m/*_0*_map.nc'))
    files = [f for f in files if '.bak' not in f]
    acc, nf = None, 0
    for f in files:
        ds = xr.open_dataset(f)
        fx = ds['mesh2d_face_x'].values
        fy = ds['mesh2d_face_y'].values
        bl = ds['mesh2d_flowelem_bl'].values
        m = ((fx >= LON[0]) & (fx <= LON[1]) & (fy >= LAT[0]) & (fy <= LAT[1])
             & (bl < BL_MAX))
        if m.sum() == 0:
            ds.close(); continue
        u = ds['mesh2d_ucx'].sel(time=slice(T0, T1)).isel(mesh2d_nFaces=np.where(m)[0])
        v = ds['mesh2d_ucy'].sel(time=slice(T0, T1)).isel(mesh2d_nFaces=np.where(m)[0])
        s = np.hypot(u, v).mean(dim=['time', 'mesh2d_nFaces']).values * m.sum()
        acc = s if acc is None else acc + s
        nf += int(m.sum())
        ds.close()
    prof = acc / nf
    for i, val in enumerate(prof):
        print(f'{key},{i},{val:.6f},{nf}')
    sys.stdout.flush()
