"""Download CMEMS Mediterranean physical data for the v05 mesh bbox.

v05 .pli reaches lat 38.253 (vs v04AE_d10d12 max 38.063). The existing
CMEMS bbox in data/raw/cmems_v04AE_d10d12/ tops at lat 38.188, leaving
~65/333 of v05 boundary nodes outside the data envelope. This script
re-downloads with extended bbox so cmems_nc_to_bc has full coverage.

Window: Jul 1-13 2025 (same diagnostic 3-day cold-start + Jul 10-12
continuation test). Datasets validated 2026-05-18, see memory
[[cmems_phy_dataset_ids]].

Outputs: data/raw/cmems_v05/
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import os
import urllib3
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOT_ENV = PROJECT_ROOT / '.env'
OUT_DIR = PROJECT_ROOT / 'data' / 'raw' / 'cmems_v05'


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

# v05 mesh bbox is [11.95, 12.60] x [37.65, 38.25]. Add a 1-cell margin
# (CMEMS native ~4.2 km ~= 0.04 deg).
BBOX = dict(
    minimum_longitude=11.65, maximum_longitude=12.75,
    minimum_latitude=37.50,  maximum_latitude=38.30,
)
START = '2025-07-01T00:00:00'
END   = '2025-07-13T23:00:00'

DATASETS = [
    # See memory [[cmems_phy_dataset_ids]] for mixed-mode rationale (anfc SSH
    # has tide; reanalysis 3D cur/sal/temp goes back to Jul 2025).
    ('cmems_mod_med_phy-ssh_anfc_4.2km_PT15M-i', ['zos'],   'cmems_zos_2025-07-01_2025-07-13.nc'),
    ('cmems_mod_med_phy-cur_my_4.2km_P1D-m',  ['uo'],       'cmems_uo_2025-07-01_2025-07-13.nc'),
    ('cmems_mod_med_phy-cur_my_4.2km_P1D-m',  ['vo'],       'cmems_vo_2025-07-01_2025-07-13.nc'),
    ('cmems_mod_med_phy-sal_my_4.2km_P1D-m',  ['so'],       'cmems_so_2025-07-01_2025-07-13.nc'),
    ('cmems_mod_med_phy-temp_my_4.2km_P1D-m', ['thetao'],   'cmems_thetao_2025-07-01_2025-07-13.nc'),
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
    print(f'BBox:       lon[{BBOX["minimum_longitude"]:.2f}, {BBOX["maximum_longitude"]:.2f}] '
          f'lat[{BBOX["minimum_latitude"]:.2f}, {BBOX["maximum_latitude"]:.2f}]')
    print(f'Window:     {START} -> {END}\n')
    for ds_id, vars_, out_fn in DATASETS:
        download_one(ds_id, vars_, out_fn)
    print('\nDone.')
