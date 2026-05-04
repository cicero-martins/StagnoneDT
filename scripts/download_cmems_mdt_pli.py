"""Download CMEMS Mediterranean MDT (Mean Dynamic Topography) static product
for the Stagnone PLI bbox + 0.1° buffer. Used as the spatial spreading layer
for the BC offset across the 49 .pli nodes (see marettimo_offset_anchor_2025.md).

Product: SEALEVEL_MED_PHY_MDT_L4_STATIC_008_066
Dataset: cnes_obs-mdt_med-phy-mdt_my_l4-static_P20Y
Resolution: 0.0417 deg (~4.6 km), 1993-2012 reference period
Static (single time slice).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / 'data' / 'raw' / 'cmems' / 'mdt_static'
OUT_FILENAME = 'cmems_mdt_med_pli_bbox.nc'
OUT_FILE = OUT_DIR / OUT_FILENAME

# PLI extent + 0.1 deg buffer
LON_MIN, LON_MAX = 11.85, 12.65
LAT_MIN, LAT_MAX = 37.60, 38.20


def main() -> int:
    if OUT_FILE.exists():
        print(f'Cached: {OUT_FILE.relative_to(PROJECT_ROOT)}')
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    import copernicusmarine
    print(f'Downloading MDT (static) for PLI bbox...')
    print(f'  bbox: lon=[{LON_MIN},{LON_MAX}], lat=[{LAT_MIN},{LAT_MAX}]')
    copernicusmarine.subset(
        dataset_id='cmems_obs-sl_med_phy-mdt_my_l4-0.0417deg_P20Y',
        variables=['mdt', 'err_mdt'],
        minimum_longitude=LON_MIN, maximum_longitude=LON_MAX,
        minimum_latitude=LAT_MIN, maximum_latitude=LAT_MAX,
        output_filename=OUT_FILENAME,
        output_directory=str(OUT_DIR),
    )
    print(f'  saved: {OUT_FILE.relative_to(PROJECT_ROOT)}')

    import xarray as xr
    ds = xr.open_dataset(OUT_FILE)
    print()
    print('Inspection:')
    print(f'  Variables: {list(ds.data_vars)}')
    print(f'  Coords: {list(ds.coords)}')
    for v in ds.data_vars:
        a = ds[v]
        print(f'  {v}: dims={a.dims}, shape={a.shape}, '
              f'range=[{float(a.min()):.4f},{float(a.max()):.4f}], mean={float(a.mean()):.4f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
