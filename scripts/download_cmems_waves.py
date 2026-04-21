"""Download CMEMS Mediterranean wave reanalysis for Stagnone boundary conditions.

Product tried first: MEDSEA_MULTIYEAR_WAV_006_012 (reanalysis, ~4.2 km, hourly).
If the requested window is not covered, falls back to the analysis-forecast
product MEDSEA_ANALYSISFORECAST_WAV_006_017.

Variables:
    VHM0  — spectral significant wave height Hm0 (m)  [~ Hs]
    VTPK  — peak wave period Tp (s)
    VMDR  — mean wave direction (deg, nautical)

Credentials: reads CMEMS_USERNAME / CMEMS_PASSWORD from environment or .env.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import copernicusmarine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOT_ENV = PROJECT_ROOT / '.env'
OUT_DIR = PROJECT_ROOT / 'data' / 'raw' / 'cmems'

BBOX = {'lon_min': 11.85, 'lon_max': 12.60, 'lat_min': 37.65, 'lat_max': 38.10}
START = '2025-07-01T00:00:00'
END = '2025-07-10T23:00:00'
VARIABLES = ['VHM0', 'VTPK', 'VMDR']

REANALYSIS_ID = 'med-hcmr-wav-rean-h'        # hourly reanalysis dataset
FORECAST_ID = 'cmems_mod_med_wav_anfc_4.2km_PT1H-i'  # hourly analysis-forecast


def load_env():
    if DOT_ENV.exists():
        for line in DOT_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def subset(dataset_id: str, output_filename: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        dataset_id=dataset_id,
        variables=VARIABLES,
        minimum_longitude=BBOX['lon_min'],
        maximum_longitude=BBOX['lon_max'],
        minimum_latitude=BBOX['lat_min'],
        maximum_latitude=BBOX['lat_max'],
        start_datetime=START,
        end_datetime=END,
        output_directory=str(OUT_DIR),
        output_filename=output_filename,
    )
    # Only pass credentials if explicitly set in env; otherwise rely on the
    # cached config from `copernicusmarine login` (~/.copernicusmarine/)
    user = os.environ.get('CMEMS_USERNAME') or os.environ.get('COPERNICUSMARINE_SERVICE_USERNAME')
    pw = os.environ.get('CMEMS_PASSWORD') or os.environ.get('COPERNICUSMARINE_SERVICE_PASSWORD')
    if user and pw:
        kwargs['username'] = user
        kwargs['password'] = pw
    copernicusmarine.subset(**kwargs)
    return OUT_DIR / output_filename


def main():
    load_env()
    out_name = f'MEDSEA_WAV_{START[:10].replace("-","")}_{END[:10].replace("-","")}.nc'
    try:
        print(f'Trying reanalysis: {REANALYSIS_ID}')
        path = subset(REANALYSIS_ID, out_name)
    except Exception as exc:
        print(f'Reanalysis failed ({type(exc).__name__}: {exc}).')
        print(f'Falling back to analysis-forecast: {FORECAST_ID}')
        path = subset(FORECAST_ID, out_name)

    print(f'\nDownloaded: {path}')
    print(f'Size: {path.stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
