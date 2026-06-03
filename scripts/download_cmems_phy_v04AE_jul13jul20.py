"""Download CMEMS Mediterranean BC for v04AE Opt-A cold-start window Jul 13-21 2025.

Strategy per [[opt_a_jul13_jul20_plan]]:
  - Period: Jul 13 00:00 -> Jul 21 00:00 (8 days coupled cold-start)
  - Buffer: download Jul 12 -> Jul 22 (1d each side)
  - SSH: anfc PT15M-i (tide included) — same as d10d12 v2
  - 3D: _my_ reanalysis daily (anfc 3D only from Oct 2025)

Output: data/raw/cmems_v04AE_jul13jul20/
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import os
from pathlib import Path

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOT_ENV = PROJECT_ROOT / '.env'
OUT_DIR = PROJECT_ROOT / 'data' / 'raw' / 'cmems_v04AE_jul13jul20'


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
    minimum_longitude=11.70, maximum_longitude=12.70,
    minimum_latitude=37.55,  maximum_latitude=38.20,
)
# Run window Jul 13 00:00 -> Jul 21 00:00; buffer Jul 12 -> Jul 22
START = '2025-07-12T00:00:00'
END   = '2025-07-22T00:00:00'

DATASETS = [
    ('cmems_mod_med_phy-ssh_anfc_4.2km_PT15M-i', ['zos'],     'cmems_zos_2025-07-12_2025-07-22.nc'),
    ('cmems_mod_med_phy-cur_my_4.2km_P1D-m',     ['uo','vo'], 'cmems_uovo_2025-07-12_2025-07-22.nc'),
    ('cmems_mod_med_phy-sal_my_4.2km_P1D-m',     ['so'],      'cmems_so_2025-07-12_2025-07-22.nc'),
    ('cmems_mod_med_phy-temp_my_4.2km_P1D-m',    ['thetao'],  'cmems_thetao_2025-07-12_2025-07-22.nc'),
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
