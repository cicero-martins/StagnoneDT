"""Build nudge_salinity_temperature_2025-07-13_00-00-00.nc for v04AE_jul13jul20.

The v04AE Jul 1-10 setup includes nudge file that smooths CMEMS T/S into
interior cells over first ~24h. This is critical to avoid baroclinic shock
at cold-start when interior IC (T=24, S=hypersaline) differs from CMEMS at
boundary.

Our Jul 13-21 setup REMOVED this because v04AE's nudge was for Jul 1. We need
to regenerate it for Jul 13.

Inputs (already downloaded):
  - data/raw/cmems_v04AE_jul13jul20/cmems_so_2025-07-12_2025-07-22.nc
  - data/raw/cmems_v04AE_jul13jul20/cmems_thetao_2025-07-12_2025-07-22.nc

Output:
  - model/dflowfm_v04AE_jul13jul20/nudge_salinity_temperature_2025-07-13_00-00-00.nc
  - 2 timesteps: 12h before start + 12h after start (Jul 12 12:00 + Jul 13 12:00)
    or 24h coverage that includes Jul 13 00:00

Then patch _old.ext to add the QUANTITY=nudge_salinity_temperature block.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
CMEMS_DIR = ROOT / 'data' / 'raw' / 'cmems_v04AE_jul13jul20'
DST = ROOT / 'model' / 'dflowfm_v04AE_jul13jul20'
OUT = DST / 'nudge_salinity_temperature_2025-07-13_00-00-00.nc'

# Match v04AE convention: 2 timesteps spanning 24h
T_START = pd.Timestamp('2025-07-12 12:00')
T_END   = pd.Timestamp('2025-07-13 12:00')


def main():
    so_path = CMEMS_DIR / 'cmems_so_2025-07-12_2025-07-22.nc'
    th_path = CMEMS_DIR / 'cmems_thetao_2025-07-12_2025-07-22.nc'
    for p in [so_path, th_path]:
        if not p.exists():
            raise FileNotFoundError(p)

    so = xr.open_dataset(so_path)
    th = xr.open_dataset(th_path)
    print(f'so: dims={dict(so.sizes)}, time range={str(so.time.values[0])[:16]} -> {str(so.time.values[-1])[:16]}')
    print(f'thetao: dims={dict(th.sizes)}, time range={str(th.time.values[0])[:16]} -> {str(th.time.values[-1])[:16]}')

    # Both are daily (P1D-m). Need values at T_START (Jul 12 12:00) and T_END (Jul 13 12:00).
    # CMEMS daily files have midnight timestamps. We interpolate to midday.
    so_2t = so['so'].interp(time=[T_START, T_END])
    th_2t = th['thetao'].interp(time=[T_START, T_END])

    # Build dataset matching v04AE convention
    ds = xr.Dataset(
        {
            'so': so_2t,
            'thetao': th_2t,
        },
        attrs={
            'Conventions': 'CF-1.8',
            'source': 'CMEMS Mediterranean reanalysis MEDSEA_MULTIYEAR_PHY_006_004 sal+temp daily',
            'history': 'Created by scripts/build_nudge_jul13.py for Opt-A Jul 13-21 cold-start',
            'comment': 'Nudge T/S field for FM to soften baroclinic shock at cold-start. '
                       'Matches v04AE Jul 1-2 nudge file convention. Replaces removed Jul 1 nudge for the new window.',
        },
    )

    # FM expects standard names that match the meteo file conventions
    ds['so'].attrs.clear()
    ds['so'].attrs.update({
        'standard_name': 'sea_water_salinity',
        'long_name': 'Salinity',
        'units': 'ppt',
    })
    ds['thetao'].attrs.clear()
    ds['thetao'].attrs.update({
        'standard_name': 'sea_water_potential_temperature',
        'long_name': 'Sea water potential temperature',
        'units': 'degree_Celsius',
    })

    enc = {
        'so':     {'zlib': True, 'complevel': 4, '_FillValue': np.float32(-32767.0)},
        'thetao': {'zlib': True, 'complevel': 4, '_FillValue': np.float32(-32767.0)},
    }
    ds.to_netcdf(OUT, encoding=enc)
    print(f'wrote {OUT}')
    print(f'  size: {OUT.stat().st_size / 1024:.1f} KB')
    print(f'  so range t=0: {float(ds.so.isel(time=0).min()):.2f} .. {float(ds.so.isel(time=0).max()):.2f} ppt')
    print(f'  thetao range t=0: {float(ds.thetao.isel(time=0).min()):.2f} .. {float(ds.thetao.isel(time=0).max()):.2f} degC')

    so.close()
    th.close()


if __name__ == '__main__':
    main()
