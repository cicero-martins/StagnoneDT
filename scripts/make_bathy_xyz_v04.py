"""Generate a face-center bathymetry XYZ file from the v04 net.nc node values,
required when D-Morph (Sedimentmodelnr=4) is active. FM forces BedlevType=1
in that case, which reads bed levels via the BathymetryFile.

Output: model/dflowfm_v04/bathymetry_v04.xyz (3-col: lon, lat, z)
Also patches MDU: bathymetryFile=bathymetry_v04.xyz, bedLevType=1
"""
from __future__ import annotations

import sys
from pathlib import Path

import netCDF4
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NET_FILE = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'Stagnone_dxy01_15m_net.nc'
XYZ_OUT = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'bathymetry_v04.xyz'
MDU_FILE = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'Stagnone_dxy01_15m.mdu'


def main() -> int:
    print(f'Reading {NET_FILE}')
    with netCDF4.Dataset(NET_FILE, 'r') as nc:
        nx = nc.variables['mesh2d_node_x'][:]
        ny = nc.variables['mesh2d_node_y'][:]
        nz = nc.variables['mesh2d_node_z'][:]
        face_nodes = nc.variables['mesh2d_face_nodes'][:]
        fill_value = nc.variables['mesh2d_face_nodes']._FillValue if hasattr(
            nc.variables['mesh2d_face_nodes'], '_FillValue') else -1
        face_x = nc.variables['mesh2d_face_x'][:]
        face_y = nc.variables['mesh2d_face_y'][:]

    n_faces = len(face_x)
    print(f'  Nodes: {len(nx)}  Faces: {n_faces}')

    # Compute mean node z per face (matches bedLevType=3 default behavior)
    face_z = np.full(n_faces, np.nan)
    fn = np.asarray(face_nodes)
    if fn.ndim != 2:
        print(f'  ERROR: face_nodes shape unexpected: {fn.shape}')
        return 1
    for i in range(n_faces):
        nodes = fn[i]
        valid = nodes[(nodes != fill_value) & (nodes >= 0)]
        if len(valid) == 0:
            continue
        # netCDF face_node indices are typically 1-based per UGRID, check
        # Apply 0-based assumption (most ugrid files have 0-based now)
        idx = (valid - 1).astype(int) if valid.min() >= 1 else valid.astype(int)
        face_z[i] = float(np.nanmean(nz[idx]))

    # Sanity check: if all NaN, try 0-based without subtracting
    if np.all(np.isnan(face_z)):
        for i in range(n_faces):
            nodes = fn[i]
            valid = nodes[(nodes != fill_value) & (nodes >= 0)]
            if len(valid) == 0:
                continue
            face_z[i] = float(np.nanmean(nz[valid.astype(int)]))

    n_valid = int(np.isfinite(face_z).sum())
    print(f'  Valid face_z: {n_valid}/{n_faces}')
    print(f'  z range: [{np.nanmin(face_z):+.2f},{np.nanmax(face_z):+.2f}], '
          f'mean={np.nanmean(face_z):+.2f}')

    # Write XYZ (lon, lat, z), one row per face
    print(f'Writing {XYZ_OUT.name}')
    valid_mask = np.isfinite(face_z)
    n_write = int(valid_mask.sum())
    with XYZ_OUT.open('w', encoding='ascii', newline='\n') as f:
        for x, y, z in zip(face_x[valid_mask], face_y[valid_mask], face_z[valid_mask]):
            f.write(f'{x:.7f}  {y:.7f}  {z:.4f}\n')
    print(f'  wrote {n_write} points')

    # Patch MDU
    print(f'\nPatching {MDU_FILE.name}')
    text = MDU_FILE.read_text(encoding='utf-8')

    # Set bedLevType=1
    import re
    text_new = re.sub(
        r'^(bedLevType\s*=\s*)\d+(.*)$',
        r'\g<1>1\g<2>',
        text, count=1, flags=re.MULTILINE,
    )
    if text_new == text:
        print('  WARN: bedLevType not patched (pattern not found)')
    else:
        print('  bedLevType -> 1')

    # Set bathymetryFile = bathymetry_v04.xyz (replace the empty value)
    text_new = re.sub(
        r'^(bathymetryFile\s*=\s*)([^#\n]*)(.*)$',
        lambda m: f'{m.group(1)}{XYZ_OUT.name}                 {m.group(3)}',
        text_new, count=1, flags=re.MULTILINE,
    )
    if 'bathymetryFile' not in text_new:
        print('  WARN: bathymetryFile keyword not found')

    MDU_FILE.write_text(text_new, encoding='utf-8')
    print('  bathymetryFile -> bathymetry_v04.xyz')
    return 0


if __name__ == '__main__':
    sys.exit(main())
