"""Overwrite mesh2d_node_z values in the Trapani port bbox using EMODnet 2024
bathymetry, leaving the rest of the mesh untouched.

Background: GEBCO-derived z values made the Trapani port basin emerge above
MSL (z ~ +0.5 to +1.6 m on most port-area nodes). EMODnet 2024 at 22 m
resolution captures the approach channel down to -13 m and brings most of
the inner basin to negative values, freeing those cells to flood.

In: model/dflowfm_v03d/Stagnone_dxy01_15m_net.nc  (read for original z)
Out: model/dflowfm_v04/Stagnone_dxy01_15m_net.nc  (overwritten in place)
EMODnet src: data/raw/bathymetry/emodnet_2024_trapani_port.tif

Bbox of update: 12.50 <= lon <= 12.55, 38.005 <= lat <= 38.040 (Trapani port +
approaches). Nodes outside this bbox keep their original z.

The original v04 net.nc is backed up to *_pre_trapani.nc.bak.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import netCDF4
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NET_FILE = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'Stagnone_dxy01_15m_net.nc'
BACKUP = NET_FILE.with_name(NET_FILE.stem + '_pre_trapani.nc.bak')
EMODNET_TIF = (PROJECT_ROOT / 'data' / 'raw' / 'bathymetry'
               / 'emodnet_2024_trapani_port.tif')

# Update bbox (slightly larger than the port basin to capture approaches)
LON_MIN_UPD, LON_MAX_UPD = 12.500, 12.550
LAT_MIN_UPD, LAT_MAX_UPD = 38.005, 38.040

# Safety: do not overwrite z to a positive value that would emerge a cell
# that is currently submerged. Only LOWER existing z values (deepen). This
# avoids accidentally drying valid cells if EMODnet reports land there.
ONLY_DEEPEN = True


def main() -> int:
    if not BACKUP.exists():
        print(f'Backing up {NET_FILE.name} -> {BACKUP.name}')
        shutil.copy2(NET_FILE, BACKUP)
    else:
        print(f'Backup already exists: {BACKUP.name} (will use as read source)')

    print(f'Loading EMODnet GeoTIFF: {EMODNET_TIF.name}')
    import rasterio
    src = rasterio.open(EMODNET_TIF)
    arr = src.read(1).astype(float)
    nodata = src.nodatavals[0]
    if nodata is not None:
        arr[arr == nodata] = np.nan
    print(f'  {arr.shape} pixels, range=[{np.nanmin(arr):+.2f},{np.nanmax(arr):+.2f}]')
    print(f'  bbox: {src.bounds}')

    print(f'\nLoading mesh net.nc: {NET_FILE.name}')
    with netCDF4.Dataset(NET_FILE, 'r+') as nc:
        nx = nc.variables['mesh2d_node_x'][:]
        ny = nc.variables['mesh2d_node_y'][:]
        nz_var = nc.variables['mesh2d_node_z']
        nz = nz_var[:]
        n_total = len(nx)
        print(f'  {n_total} nodes, z range=[{nz.min():+.2f},{nz.max():+.2f}]')

        # Identify nodes inside update bbox
        inside = ((nx >= LON_MIN_UPD) & (nx <= LON_MAX_UPD)
                  & (ny >= LAT_MIN_UPD) & (ny <= LAT_MAX_UPD))
        idx_in = np.where(inside)[0]
        print(f'  Nodes in update bbox: {len(idx_in)} (lon=[{LON_MIN_UPD},{LON_MAX_UPD}], '
              f'lat=[{LAT_MIN_UPD},{LAT_MAX_UPD}])')

        if len(idx_in) == 0:
            print('  No mesh nodes in bbox; nothing to do.')
            return 0

        # Sample EMODnet at node coordinates (rasterio.sample returns generator)
        sample_pts = list(zip(nx[idx_in], ny[idx_in]))
        sampled = np.array([v[0] if v is not None and not np.isnan(v[0]) else np.nan
                            for v in src.sample(sample_pts)])
        n_valid = int(np.isfinite(sampled).sum())
        print(f'  EMODnet samples: {n_valid}/{len(idx_in)} valid '
              f'(others NaN -> kept original z)')

        # Compute new z values: EMODnet convention is positive UP (elevation),
        # FM mesh2d_node_z is also positive UP. So a depth -10 m below MSL
        # appears as -10 in both => no sign flip needed.
        new_z = nz[idx_in].copy()
        n_changed = 0
        n_deepened = 0
        n_unchanged = 0
        for k, src_val in enumerate(sampled):
            i = idx_in[k]
            if not np.isfinite(src_val):
                n_unchanged += 1
                continue
            if ONLY_DEEPEN and src_val >= nz[i]:
                # EMODnet says shallower or equal -> keep original (don't elevate)
                n_unchanged += 1
                continue
            new_z[k] = src_val
            n_changed += 1
            if src_val < nz[i]:
                n_deepened += 1

        # Write back
        nz_full = nz.copy()
        nz_full[idx_in] = new_z
        nz_var[:] = nz_full
        print(f'  Updated nodes: changed={n_changed}, '
              f'deepened={n_deepened}, kept={n_unchanged}')
        print(f'  New z range: [{nz_full.min():+.2f},{nz_full.max():+.2f}]')

        # Stats just on the updated bbox
        in_z_old = nz[idx_in]
        in_z_new = nz_full[idx_in]
        print(f'\n  Bbox stats:')
        print(f'    z_old: range=[{in_z_old.min():+.2f},{in_z_old.max():+.2f}], '
              f'mean={in_z_old.mean():+.2f}, n_above_msl={int((in_z_old>0).sum())}')
        print(f'    z_new: range=[{in_z_new.min():+.2f},{in_z_new.max():+.2f}], '
              f'mean={in_z_new.mean():+.2f}, n_above_msl={int((in_z_new>0).sum())}')

    src.close()
    print(f'\nWrote: {NET_FILE.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
