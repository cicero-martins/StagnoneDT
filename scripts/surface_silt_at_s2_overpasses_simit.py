"""Surface-layer silt in the lagoon at the Sentinel-2 overpasses of July 2025 (simit).

The lagoon is that of the renewal computations (renewal_common.lagoon_faces,
the samples of lagoon_tracer_init.xyz within 150 m), the same as for the
satellite retrieval (s2_suspended_matter_lagoon.py). The top sigma layer is the
one comparable to a red-band reflectance retrieval, and the percentiles are
weighted by face area, as the 10 m pixels of the satellite weight the lagoon by
area. Prints one CSV row per member and overpass with the percentiles 25, 50,
75 and 95 in mg/l at the map record nearest to the overpass, within one hour.

Usage, on simit:  python surface_silt_at_s2_overpasses_simit.py <member dir> ...
"""
import glob
import sys
from datetime import datetime
from pathlib import Path

import netCDF4 as nc
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from renewal_common import lagoon_faces  # noqa: E402

PASSES = ['2025-06-30 09:50', '2025-07-03 10:00', '2025-07-05 09:50', '2025-07-07 09:50',
          '2025-07-08 10:00', '2025-07-10 09:50']
XYZ_DIR = Path(__file__).resolve().parents[1] / 'model' / 'dflowfm_v04AE_dens_ic3d'


def t_rec(x):
    return f'{x.year}-{x.month:02d}-{x.day:02d} {x.hour:02d}:{x.minute:02d}'


def wpercentile(v, w, q):
    o = np.argsort(v)
    c = np.cumsum(w[o]) / w.sum()
    return np.interp(q / 100, c, v[o])


print('member,overpass,record,p25,p50,p75,p95')
for d in sys.argv[1:]:
    files = sorted(glob.glob(f"{d}/DFM_OUTPUT_*/*_00[0-9][0-9]_map.nc"))
    ds = nc.Dataset(files[0])
    times = nc.num2date(ds['time'][:], ds['time'].units)
    ds.close()
    masks = {}
    for p in PASSES:
        t = datetime.strptime(p, '%Y-%m-%d %H:%M')
        dt = [abs((datetime(x.year, x.month, x.day, x.hour, x.minute) - t).total_seconds()) for x in times]
        i = int(np.argmin(dt))
        if dt[i] > 3600:
            continue
        vals, area = [], []
        for f in files:
            ds = nc.Dataset(f)
            if f not in masks:
                part = int(f.split('_map.nc')[0][-4:])
                m = lagoon_faces(XYZ_DIR, ds['mesh2d_face_x'][:], ds['mesh2d_face_y'][:])
                if 'mesh2d_flowelem_domain' in ds.variables:
                    m &= ds['mesh2d_flowelem_domain'][:] == part
                masks[f] = m
            m = masks[f]
            names = [b''.join(r).decode().strip().lower() for r in ds['sussedfrac_name'][:]]
            isil = [k for k, n in enumerate(names) if 'silt' in n][0]
            s = np.ma.filled(ds['mesh2d_sedfrac_concentration'][i, isil], np.nan)
            if s.ndim == 2:
                s = s[:, -1]
            vals.append(s[m])
            area.append(ds['mesh2d_flowelem_ba'][:][m])
            ds.close()
        v = 1000 * np.concatenate(vals); a = np.concatenate(area)
        ok = np.isfinite(v)
        print(f"{d.rstrip('/').split('/')[-1]},{p},{t_rec(times[i])},"
              + ','.join(f'{wpercentile(v[ok], a[ok], q):.2f}' for q in (25, 50, 75, 95)), flush=True)
