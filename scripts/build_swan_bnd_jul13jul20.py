"""Download CMEMS waves Jul 13-21 + build SWAN TPAR .bnd files for v04AE_jul13jul20.

Output: model/dflowfm_v04AE_jul13jul20/wave/{west,south,north}_seg{1,2,3}.bnd

TPAR format expected by SWAN:
    TPAR
    YYYYMMDD.HHMM  Hs(m)  Tp(s)  Dir(deg,nautical)  DirSpread(deg)
    ...

Sample point locations per notebook 04 (just outside outer SWAN grid).
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOT_ENV = PROJECT_ROOT / '.env'
CMEMS_OUT = PROJECT_ROOT / 'data' / 'raw' / 'cmems_v04AE_jul13jul20'
WAVE_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_jul13jul20' / 'wave'

START = '2025-07-12T00:00:00'  # 1d buffer before run start Jul 13
END   = '2025-07-22T00:00:00'  # 1d buffer after run stop Jul 21

BBOX = {'lon_min': 11.85, 'lon_max': 12.60, 'lat_min': 37.65, 'lat_max': 38.10}
VARIABLES = ['VHM0', 'VTPK', 'VMDR']
REANALYSIS_ID = 'med-hcmr-wav-rean-h'
FORECAST_ID = 'cmems_mod_med_wav_anfc_4.2km_PT1H-i'

# Per notebook 04
SAMPLE_POINTS = {
    'west':  [('seg1', 11.90, 37.75), ('seg2', 11.90, 37.88), ('seg3', 11.90, 38.00)],
    'south': [('seg1', 12.05, 37.67), ('seg2', 12.25, 37.67), ('seg3', 12.45, 37.67)],
    'north': [('seg1', 12.10, 38.08), ('seg2', 12.30, 38.08), ('seg3', 12.50, 38.08)],
}
DIR_SPREAD = 4.0  # power-law spreading in original MDW


def load_env():
    if DOT_ENV.exists():
        for line in DOT_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def download_cmems_waves():
    """Download CMEMS wave file for Jul 13-21 window."""
    out_name = 'MEDSEA_WAV_2025-07-12_2025-07-22.nc'
    out_path = CMEMS_OUT / out_name
    if out_path.exists():
        print(f'CMEMS wave file exists: {out_path}')
        return out_path

    import copernicusmarine
    load_env()
    user = os.environ.get('CMEMS_USERNAME')
    pw = os.environ.get('CMEMS_PASSWORD')
    kwargs = dict(
        variables=VARIABLES,
        minimum_longitude=BBOX['lon_min'], maximum_longitude=BBOX['lon_max'],
        minimum_latitude=BBOX['lat_min'], maximum_latitude=BBOX['lat_max'],
        start_datetime=START, end_datetime=END,
        output_directory=str(CMEMS_OUT), output_filename=out_name,
    )
    if user and pw:
        kwargs['username'] = user
        kwargs['password'] = pw

    CMEMS_OUT.mkdir(parents=True, exist_ok=True)
    try:
        print(f'Downloading wave {REANALYSIS_ID}...')
        copernicusmarine.subset(dataset_id=REANALYSIS_ID, **kwargs)
    except Exception as exc:
        print(f'Reanalysis failed: {exc}\nTrying analysis-forecast {FORECAST_ID}...')
        copernicusmarine.subset(dataset_id=FORECAST_ID, **kwargs)
    print(f'OK: {out_path} ({out_path.stat().st_size/1e6:.1f} MB)')
    return out_path


def extract_series(ds, lon, lat):
    """Nearest-neighbor time series at a point, with NaN check."""
    pt = ds.sel(lon=lon, lat=lat, method='nearest')
    nan_frac = float(np.isnan(pt['VHM0']).mean())
    if nan_frac > 0.1:
        print(f'  WARNING: ({lon:.3f},{lat:.3f}) has {nan_frac*100:.0f}% NaN; '
              'consider shifting offshore')
    return pt


def write_tpar(path, pt):
    """Write SWAN TPAR .bnd file."""
    times = pd.to_datetime(pt.time.values)
    hs = pt['VHM0'].values
    tp = pt['VTPK'].values
    dr = pt['VMDR'].values

    # Drop NaN rows (CMEMS wave can have masked land cells)
    mask = ~(np.isnan(hs) | np.isnan(tp) | np.isnan(dr))
    times = times[mask]
    hs = hs[mask]
    tp = tp[mask]
    dr = dr[mask]

    with open(path, 'w') as f:
        f.write('TPAR\n')
        for t, h, p_, d in zip(times, hs, tp, dr):
            ts = t.strftime('%Y%m%d.%H%M')
            f.write(f'{ts}  {h:.3f}  {p_:.2f}  {d:.2f}  {DIR_SPREAD:.2f}\n')
    return len(times)


def main():
    WAVE_DIR.mkdir(parents=True, exist_ok=True)
    nc_path = download_cmems_waves()
    ds = xr.open_dataset(nc_path)
    if 'longitude' in ds.coords:
        ds = ds.rename({'longitude': 'lon', 'latitude': 'lat'})
    print(f'CMEMS wave: {len(ds.time)} times, '
          f'{str(ds.time.values[0])[:13]} -> {str(ds.time.values[-1])[:13]}')

    for boundary, pts in SAMPLE_POINTS.items():
        for name, lo, la in pts:
            pt = extract_series(ds, lo, la)
            out = WAVE_DIR / f'{boundary}_{name}.bnd'
            n = write_tpar(out, pt)
            print(f'  {out.name}: {n} rows  (lon {lo}, lat {la})')

    ds.close()
    print('\nDone.')


if __name__ == '__main__':
    main()
