"""Download CMEMS Mediterranean physical reanalysis for v04AE Jul 10->12
continuation run. Window Jul 1-13 (overlaps original v04AE for sanity).

Dataset IDs (validated 2026-05-18, MEDSEA_MULTIYEAR_PHY_006_004):
  - ssh  hourly  : cmems_mod_med_phy-ssh_my_4.2km_PT1H-m         (zos)
  - cur  hourly  : cmems_mod_med_phy-cur_my_4.2km_PT1H-m         (uo, vo)
  - sal  daily   : cmems_mod_med_phy-sal_my_4.2km_P1D-m          (so)
  - temp daily   : cmems_mod_med_phy-temp_my_4.2km_P1D-m         (thetao)

Outputs: data/raw/cmems_v04AE_d10d12/
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import os
import sys
import warnings
from pathlib import Path

import urllib3

# Quiet the InsecureRequestWarning noise from s3.waw3-1.cloudferro.com
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOT_ENV = PROJECT_ROOT / '.env'
OUT_DIR = PROJECT_ROOT / 'data' / 'raw' / 'cmems_v04AE_d10d12'


def load_env():
    if DOT_ENV.exists():
        for raw in DOT_ENV.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
import copernicusmarine

BBOX = dict(
    # Expanded to cover all 49 .pli boundary nodes (lat reaches 38.063, lon 12.537)
    minimum_longitude=11.70, maximum_longitude=12.70,
    minimum_latitude=37.55,  maximum_latitude=38.20,
)
START = '2025-07-01T00:00:00'
END   = '2025-07-13T23:00:00'

DATASETS = [
    # (dataset_id, variables, output_filename)
    # SSH is 2D, hourly: gives tidal signal at the boundary
    ('cmems_mod_med_phy-ssh_my_4.2km_PT1H-m',  ['zos'],         'cmems_zos_2025-07-01_2025-07-13.nc'),
    # Currents: daily 3D (141 z-levels). Hourly cur dataset is depth-averaged surface only,
    # FM v04AE BC expects t3d (50 vertical layers per node).
    ('cmems_mod_med_phy-cur_my_4.2km_P1D-m',   ['uo', 'vo'],    'cmems_uovo_2025-07-01_2025-07-13.nc'),
    # Salinity, temperature: daily 3D (already correct)
    ('cmems_mod_med_phy-sal_my_4.2km_P1D-m',   ['so'],          'cmems_so_2025-07-01_2025-07-13.nc'),
    ('cmems_mod_med_phy-temp_my_4.2km_P1D-m',  ['thetao'],      'cmems_thetao_2025-07-01_2025-07-13.nc'),
]


def download_one(dataset_id, variables, output_filename):
    out = OUT_DIR / output_filename
    if out.exists():
        size = out.stat().st_size / 1024
        print(f'  SKIP (already exists, {size:.1f} KB): {output_filename}', flush=True)
        return
    print(f'  Downloading {dataset_id} -> {output_filename}...', flush=True)
    copernicusmarine.subset(
        dataset_id=dataset_id,
        variables=variables,
        start_datetime=START,
        end_datetime=END,
        output_directory=str(OUT_DIR),
        output_filename=output_filename,
        **BBOX,
        username=os.environ['CMEMS_USERNAME'],
        password=os.environ['CMEMS_PASSWORD'],
    )
    size = out.stat().st_size / 1024
    print(f'  OK ({size:.1f} KB)', flush=True)


if __name__ == '__main__':
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f'Output dir: {OUT_DIR}')
    print(f'Window:     {START} -> {END}\n')
    for ds_id, vars, out_fn in DATASETS:
        download_one(ds_id, vars, out_fn)
    print('\nDone. Files in', OUT_DIR)
