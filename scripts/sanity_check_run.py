"""The project's standing sanity checks, before trusting any of these runs.

From CLAUDE.md:
  - 'my model volume' > 0 in the partition .dia, else bedLevType=1 silently fell
    back to bedLevUni and the bathymetry never loaded
  - mesh2d_hwav.std() > 0 on wave-coupled members, else the SWAN re-open of
    com.nc is broken and the coupling did nothing
  - mesh2d_sa1 with no values far above 50 ppt, which would mean an intertidal
    salinity blow-up

Plus, for this batch specifically, the bed change: DensIn = false removes the
suspended-sediment contribution to density, so the morphology should still act
but the offshore runaway should be gone.
"""
import glob
import os
import sys

import netCDF4 as nc
import numpy as np

LAGOON = dict(lon=(12.418, 12.492), lat=(37.815, 37.914))

for d in sys.argv[1:]:
    out = os.path.join(d, 'DFM_OUTPUT_Stagnone_dxy01_15m')
    print(f'\n===== {d} =====')

    dias = sorted(glob.glob(os.path.join(out, '*_000?.dia')))
    vols = []
    for f in dias:
        for ln in open(f, errors='ignore'):
            if 'my model volume' in ln.lower():
                vols.append(float(ln.split(':')[-1].strip().split()[0]))
                break
    if vols:
        ok = all(v > 0 for v in vols)
        print(f'  volume    {"OK " if ok else "FAIL"} min={min(vols):.3e} '
              f'over {len(vols)} partitions')
    else:
        print('  volume    (not reported in .dia)')

    maps = sorted(glob.glob(os.path.join(out, '*_000?_map.nc')))
    hw, sa, dz, lon, lat = [], [], [], [], []
    for f in maps:
        ds = nc.Dataset(f)
        if 'mesh2d_hwav' in ds.variables:
            hw.append(np.asarray(ds['mesh2d_hwav'][:]).ravel())
        if 'mesh2d_sa1' in ds.variables:
            sa.append(np.asarray(ds['mesh2d_sa1'][-1]).ravel())
        if 'mesh2d_mor_bl' in ds.variables:
            b = np.asarray(ds['mesh2d_mor_bl'][:])
            dz.append(b[-1] - b[0])
            lon.append(np.asarray(ds['mesh2d_face_x'][:]))
            lat.append(np.asarray(ds['mesh2d_face_y'][:]))
        ds.close()

    if hw:
        h = np.concatenate(hw)
        h = h[np.isfinite(h)]
        print(f'  hwav      {"OK " if h.std() > 0 else "FAIL"} '
              f'std={h.std():.4f} max={h.max():.3f} m')
    else:
        print('  hwav      n/a (no-wave member)')

    if sa:
        s = np.concatenate(sa)
        s = s[np.isfinite(s)]
        bad = (s > 80).sum()
        print(f'  salinity  {"OK " if bad == 0 else "FAIL"} '
              f'max={s.max():.1f} ppt, {bad} cells above 80')

    if dz:
        z = np.concatenate(dz)
        lo, la = np.concatenate(lon), np.concatenate(lat)
        m = np.isfinite(z)
        inl = (m & (lo >= LAGOON['lon'][0]) & (lo <= LAGOON['lon'][1])
               & (la >= LAGOON['lat'][0]) & (la <= LAGOON['lat'][1]))
        print(f'  bed change  domain |max|={np.abs(z[m]).max():.3f} m   '
              f'lagoon |max|={np.abs(z[inl]).max():.3f} m   '
              f'median={np.median(z[inl]):+.3f} m')
