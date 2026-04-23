"""PlanetScope multi-date mosaicking + temporal composites for Stagnone DT.

Pipeline:
1. Index `.tif` scenes under `data/raw/satellite/planet/summer2025/PSScene/`
   by acquisition date (YYYYMMDD prefix in filename).
2. For each date, merge the 2-3 adjacent PSScene footprints with UDM2
   "clear" mask applied (UDM2 band 1 == 1 means clear).
3. Re-sample every per-date mosaic onto a single canonical target grid
   (from the first date) so pixels align across time.
4. Compute per-pixel, per-band composites: median, 10th percentile, std.
5. Save composites as a single multi-band NetCDF with 8 source bands x 3
   statistics = 24 layers, in the canonical grid.

Processing strategy: one band at a time. Stack of 9 dates for a single
band is ~80 MB; full 8-band stack would be ~5.4 GB and does not fit
comfortably on a 16 GB laptop alongside the rest of the workflow.

Usage:
    python scripts/planet_mosaic_composite.py              # build composite (cached)
    python scripts/planet_mosaic_composite.py --force      # rebuild even if cache present
    python scripts/planet_mosaic_composite.py --list       # just list per-date scenes
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.warp import reproject
from rasterio.io import MemoryFile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PSDIR = PROJECT_ROOT / 'data' / 'raw' / 'satellite' / 'planet' / 'summer2025' / 'PSScene'
CACHE_PATH = PROJECT_ROOT / 'data' / 'processed' / 'planet_composite_summer2025.nc'

SR_GLOB = '*_3B_AnalyticMS_SR_8b_harmonized_clip_file_format.tif'
UDM_NAME_MAP = ('_3B_AnalyticMS_SR_8b_harmonized_clip_file_format.tif',
                '_3B_udm2_clip_file_format.tif')

# PlanetScope SuperDove 8-band wavelengths (center, nm)
BAND_NAMES = ['coastal_blue', 'blue', 'green_i', 'green',
              'yellow', 'red', 'red_edge', 'nir']
BAND_WAVELENGTHS_NM = [443, 490, 531, 565, 610, 665, 705, 865]


def scenes_by_date() -> Dict[str, List[Path]]:
    """Index PSScene tifs by YYYYMMDD acquisition date."""
    buckets: Dict[str, List[Path]] = {}
    for s in sorted(PSDIR.glob(SR_GLOB)):
        m = re.match(r'(\d{8})_', s.name)
        if not m:
            continue
        buckets.setdefault(m.group(1), []).append(s)
    return buckets


def _mask_scene_with_udm2(sr_path: Path):
    """Return a MemoryFile rasterio dataset with non-clear pixels zeroed."""
    udm_path = sr_path.with_name(sr_path.name.replace(*UDM_NAME_MAP))
    with rasterio.open(sr_path) as src:
        sr = src.read()
        profile = src.profile.copy()
    if udm_path.exists():
        with rasterio.open(udm_path) as u:
            clear = u.read(1)  # band 1: 1=clear, 0=not clear
        sr = np.where(clear[None, :, :] == 1, sr, 0)
    memfile = MemoryFile()
    with memfile.open(**profile) as dst:
        dst.write(sr)
    return memfile


def mosaic_date(sr_tifs: List[Path]):
    """Merge all scenes of one date with UDM2 masking. Returns (arr, transform, profile)."""
    memfiles = [_mask_scene_with_udm2(t) for t in sr_tifs]
    opens = [m.open() for m in memfiles]
    try:
        arr, transform = merge(opens, method='first', nodata=0)
        profile = opens[0].profile.copy()
    finally:
        for o in opens:
            o.close()
        for m in memfiles:
            m.close()
    profile.update({
        'height': arr.shape[1],
        'width': arr.shape[2],
        'transform': transform,
    })
    return arr, transform, profile


def reproject_to(src_arr: np.ndarray, src_transform, src_crs,
                 dst_shape, dst_transform, dst_crs, nodata=0):
    """Reproject a (bands, H, W) uint16 array to a target grid. Returns (bands, dH, dW)."""
    n_bands = src_arr.shape[0]
    out = np.zeros((n_bands, dst_shape[0], dst_shape[1]), dtype=src_arr.dtype)
    for b in range(n_bands):
        reproject(
            source=src_arr[b],
            destination=out[b],
            src_transform=src_transform, src_crs=src_crs,
            dst_transform=dst_transform, dst_crs=dst_crs,
            src_nodata=nodata, dst_nodata=nodata,
            resampling=Resampling.nearest,  # nearest preserves cloud-masked zeros
        )
    return out


def build_composite(force: bool = False):
    """Build the temporal composite NetCDF, caching the result."""
    if CACHE_PATH.exists() and not force:
        print(f'Composite cache exists: {CACHE_PATH.relative_to(PROJECT_ROOT)}. '
              f'Use --force to rebuild.')
        return CACHE_PATH

    buckets = scenes_by_date()
    dates = list(buckets)
    print(f'Building composite from {len(dates)} dates.')

    # Canonical grid: from the first date's mosaic.
    print(f'[1/{len(dates)}] anchor  {dates[0]} ...')
    arr0, tfm0, prof0 = mosaic_date(buckets[dates[0]])
    canonical_shape = (arr0.shape[1], arr0.shape[2])
    canonical_tfm = tfm0
    canonical_crs = prof0['crs']
    n_bands = arr0.shape[0]
    print(f'         canonical grid: {canonical_shape} (H,W), crs={canonical_crs}')

    # Memory: full 9-date x 8-band stack as float32 is ~11 GB. nanmedian/nanpercentile
    # materialize a sort buffer internally, pushing peak to ~20+ GB. Not feasible on a
    # 16 GB laptop. Process one band at a time: 9 dates x 1 band x float32 ~ 1.4 GB, OK.
    print('Mosaicking all dates (uint16, 9 x 8 x H x W) ...')
    stack = np.zeros((len(dates), n_bands, *canonical_shape), dtype=np.uint16)
    stack[0] = arr0
    del arr0
    for i, d in enumerate(dates[1:], start=1):
        print(f'[{i+1}/{len(dates)}] mosaic  {d} ...')
        arr, tfm, prof = mosaic_date(buckets[d])
        if (arr.shape[1], arr.shape[2]) != canonical_shape or tfm != canonical_tfm:
            print(f'         reprojecting from {arr.shape[1:]} to {canonical_shape}')
            arr = reproject_to(arr, tfm, prof['crs'],
                               canonical_shape, canonical_tfm, canonical_crs)
        stack[i] = arr

    import xarray as xr
    print(f'Computing composites per band ({n_bands} x 9 dates) ...')

    median = np.zeros((n_bands, *canonical_shape), dtype=np.float32)
    p10    = np.zeros((n_bands, *canonical_shape), dtype=np.float32)
    std    = np.zeros((n_bands, *canonical_shape), dtype=np.float32)

    for b in range(n_bands):
        # Slice one band across dates: (n_dates, H, W) uint16
        band_stack = stack[:, b].astype(np.float32)
        band_stack[stack[:, b] == 0] = np.nan  # cloud-masked pixels -> NaN
        median[b] = np.nanmedian(band_stack, axis=0)
        p10[b]    = np.nanpercentile(band_stack, 10, axis=0)
        std[b]    = np.nanstd(band_stack, axis=0)
        del band_stack
        print(f'  band {b+1}/{n_bands} ({BAND_NAMES[b]}) done')

    # Build a georeferenced xarray Dataset
    # Coordinate arrays from the canonical transform
    H, W = canonical_shape
    x_coords = canonical_tfm.c + (np.arange(W) + 0.5) * canonical_tfm.a
    y_coords = canonical_tfm.f + (np.arange(H) + 0.5) * canonical_tfm.e

    ds = xr.Dataset(
        data_vars={
            'median': (('band', 'y', 'x'), median),
            'p10':    (('band', 'y', 'x'), p10),
            'std':    (('band', 'y', 'x'), std),
        },
        coords={
            'band':          ('band', BAND_NAMES),
            'wavelength_nm': ('band', BAND_WAVELENGTHS_NM),
            'x':             ('x', x_coords),
            'y':             ('y', y_coords),
        },
        attrs={
            'crs_wkt':   str(canonical_crs.to_wkt()) if canonical_crs else '',
            'crs_epsg':  32633,
            'n_dates':   len(dates),
            'dates':     ','.join(dates),
            'source':    'PlanetScope Analytic MS SR 8b harmonized, UDM2-masked',
            'pixel_res_m': 3.0,
        },
    )
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(CACHE_PATH)
    print(f'Saved {CACHE_PATH.relative_to(PROJECT_ROOT)}  '
          f'({CACHE_PATH.stat().st_size/1e6:.0f} MB)')
    return CACHE_PATH


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--force', action='store_true', help='Rebuild even if cache present')
    ap.add_argument('--list', action='store_true', help='Only print per-date scene list')
    args = ap.parse_args()

    if args.list:
        for d, tifs in scenes_by_date().items():
            print(f'{d}: {len(tifs)} scene(s)')
            for t in tifs:
                print(f'    {t.name}')
        return 0

    build_composite(force=args.force)
    return 0


if __name__ == '__main__':
    sys.exit(main())
