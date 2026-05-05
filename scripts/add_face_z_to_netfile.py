"""Add mesh2d_face_z (cell-center bed level) to the v04 netfile.

Required when bedLevType=1 (D-Morphology Sedimentmodelnr=4 forces this).
FM 2026.01 dropped bathymetryFile keyword as obsolete; cell-center bathy
must now live inside the netfile as mesh2d_face_z with UGRID attributes.

Without this, FM fell back to bedLevUni=5.0 m for every cell -> all cells
emerged above WaterLevIni=0 -> volume = 0 m^3 (verified empirically in
v04 first 9d run, my model volume = 0 in all partition .dia files).

face_z is computed as mean of node z values per face, identical to what
bedLevType=3 would do at runtime, but stored explicitly so bedLevType=1
can read it.

Backs up the current netfile to *_pre_face_z.nc.bak.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import netCDF4
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NET_FILE = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'Stagnone_dxy01_15m_net.nc'
BACKUP = NET_FILE.with_name(NET_FILE.stem + '_pre_face_z.nc.bak')

# UGRID-compliant attribute set for FM 2026.01 (per Deltares D-Morphology
# tutorial reference: Tutorial_D-Morphology/Breakwater straight_coast_net.nc)
FACE_Z_ATTRS = {
    'mesh': 'mesh2d',
    'location': 'face',
    'coordinates': 'mesh2d_face_x mesh2d_face_y',
    'standard_name': 'altitude',
    'long_name': 'z-coordinate of mesh faces',
    'units': 'm',
}
FILL_VALUE = -999.0


def compute_face_z_from_nodes(nc: netCDF4.Dataset) -> np.ndarray:
    """Per-face mean of surrounding node z values."""
    nz = np.asarray(nc.variables['mesh2d_node_z'][:], dtype=float)
    fn = np.asarray(nc.variables['mesh2d_face_nodes'][:])
    fn_var = nc.variables['mesh2d_face_nodes']
    fn_fill = fn_var._FillValue if hasattr(fn_var, '_FillValue') else -1
    # UGRID start index (0 or 1) — try to detect
    start_index = int(getattr(fn_var, 'start_index', 1))

    n_faces = fn.shape[0]
    face_z = np.full(n_faces, np.nan)
    for i in range(n_faces):
        nodes = fn[i]
        valid = nodes[(nodes != fn_fill) & (nodes >= start_index)]
        if len(valid) == 0:
            continue
        idx = (valid - start_index).astype(int)
        face_z[i] = float(np.nanmean(nz[idx]))
    return face_z


def main() -> int:
    if not NET_FILE.exists():
        print(f'ERROR: {NET_FILE} not found')
        return 1
    if not BACKUP.exists():
        print(f'Backup -> {BACKUP.name}')
        shutil.copy2(NET_FILE, BACKUP)
    else:
        print(f'Backup already exists: {BACKUP.name}')

    with netCDF4.Dataset(NET_FILE, 'r+') as nc:
        # Detect face dimension name (varies between UGRID flavours)
        face_dim_name = nc.variables['mesh2d_face_x'].dimensions[0]
        n_faces = nc.dimensions[face_dim_name].size
        print(f'Face dimension: {face_dim_name} (n={n_faces})')

        face_z = compute_face_z_from_nodes(nc)
        n_valid = int(np.isfinite(face_z).sum())
        print(f'Computed face_z: valid={n_valid}/{n_faces}, '
              f'range=[{np.nanmin(face_z):+.2f},{np.nanmax(face_z):+.2f}], '
              f'mean={np.nanmean(face_z):+.2f}')

        # Replace any remaining NaN with FILL_VALUE for safety, but FM treats
        # cells with _FillValue as needing fallback — so ideally there are 0.
        n_nan = int(np.isnan(face_z).sum())
        if n_nan > 0:
            print(f'  WARNING: {n_nan} faces have NaN face_z (will become _FillValue, '
                  f'FM will fall back to bedLevUni for those cells)')
            face_z[np.isnan(face_z)] = FILL_VALUE

        # Create or overwrite mesh2d_face_z
        if 'mesh2d_face_z' in nc.variables:
            print('mesh2d_face_z already exists; overwriting values + attrs')
            var = nc.variables['mesh2d_face_z']
        else:
            print('Creating mesh2d_face_z')
            var = nc.createVariable(
                'mesh2d_face_z', 'f8', (face_dim_name,),
                fill_value=FILL_VALUE,
            )
        for k, v in FACE_Z_ATTRS.items():
            setattr(var, k, v)
        var[:] = face_z

    # Verify
    with netCDF4.Dataset(NET_FILE, 'r') as nc:
        var = nc.variables['mesh2d_face_z']
        print()
        print('=== Verification ===')
        print(f'Variable: mesh2d_face_z')
        print(f'  dims: {var.dimensions}')
        print(f'  dtype: {var.dtype}')
        for k in FACE_Z_ATTRS.keys():
            print(f'  .{k} = {getattr(var, k)!r}')
        if hasattr(var, '_FillValue'):
            print(f'  ._FillValue = {var._FillValue}')
        data = var[:]
        if hasattr(data, 'mask'):
            valid = data[~data.mask]
        else:
            valid = data[data != FILL_VALUE]
        print(f'  values: n_valid={len(valid)}, '
              f'range=[{float(valid.min()):+.2f},{float(valid.max()):+.2f}], '
              f'mean={float(valid.mean()):+.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
