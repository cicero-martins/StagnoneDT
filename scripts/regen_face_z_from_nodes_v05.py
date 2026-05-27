"""Re-compute mesh2d_face_z as the mean of surrounding mesh2d_node_z values
for the v05 net.nc files (master + 8 partitioned).

Critical lesson (docs/fm_2026_gotchas.md gotcha #5 and scripts/add_face_z_to_netfile.py):
FM 2026.01 with bedLevType=1 expects face_z to be derivable from node_z
(equivalent to what bedLevType=3 would compute at runtime). Our v05 had
face_z and node_z computed as INDEPENDENT interpolations of topobathy at
face centres vs node coords -- their numerical values differ slightly,
and FM apparently rejects this inconsistency: every cell falls back to
BedlevUni=+5m, `my model volume = 0`, output is all-zero/NaN.

Aligning face_z = mean(node_z[face_nodes]) reproduces the v04AE convention
(per the Deltares D-Morphology tutorial reference straight_coast_net.nc).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4 as nc
import numpy as np

MASTER = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
MODEL_DIR = Path('model/dflowfm_v05')
FILL_VALUE = -999.0

ATTRS = {
    'mesh': 'mesh2d',
    'location': 'face',
    'coordinates': 'mesh2d_face_x mesh2d_face_y',
    'standard_name': 'altitude',
    'long_name': 'z-coordinate of mesh faces',
    'units': 'm',
}


def compute_face_z_from_nodes(ds: nc.Dataset) -> np.ndarray:
    nz = np.asarray(ds.variables['mesh2d_node_z'][:], dtype=np.float64)
    fn_var = ds.variables['mesh2d_face_nodes']
    fn = np.asarray(fn_var[:])
    fn_fill = int(fn_var._FillValue) if '_FillValue' in fn_var.ncattrs() else -1
    start_index = int(getattr(fn_var, 'start_index', 1))

    n_faces = fn.shape[0]
    face_z = np.full(n_faces, FILL_VALUE, dtype=np.float64)
    for i in range(n_faces):
        nodes = fn[i]
        valid = nodes[(nodes != fn_fill) & (nodes >= start_index)]
        if len(valid) == 0:
            continue
        idx = (valid - start_index).astype(int)
        zs = nz[idx]
        zs = zs[np.isfinite(zs)]
        if len(zs):
            face_z[i] = float(zs.mean())
    return face_z


def patch_file(path: Path):
    print(f'\n=== {path.name} ===')
    bak = path.with_suffix('.nc.bak_pre_regen')
    if not bak.exists():
        shutil.copy2(path, bak)
    with nc.Dataset(path, 'r+') as ds:
        old = np.asarray(ds.variables['mesh2d_face_z'][:])
        face_z = compute_face_z_from_nodes(ds)
        # update values
        ds.variables['mesh2d_face_z'][:] = face_z
        # re-apply attrs
        var = ds.variables['mesh2d_face_z']
        for k, v in ATTRS.items():
            var.setncattr(k, v)
        # remove grid_mapping if present (v04AE doesn't have it on face_z)
        if 'grid_mapping' in var.ncattrs():
            var.delncattr('grid_mapping')
        n_valid = int((face_z != FILL_VALUE).sum())
        print(f'  before: range=({old.min():.1f}, {old.max():.1f})')
        print(f'  after:  range=({face_z[face_z != FILL_VALUE].min():.1f}, '
              f'{face_z[face_z != FILL_VALUE].max():.1f}), valid={n_valid}/{len(face_z)}')


def main():
    patch_file(MASTER)
    shutil.copy2(MASTER, MODEL_DIR / 'Stagnone_v05_net.nc')
    print(f'\nSynced master -> {MODEL_DIR / "Stagnone_v05_net.nc"}')
    for p in sorted(MODEL_DIR.glob('Stagnone_v05_000*_net.nc')):
        patch_file(p)


if __name__ == '__main__':
    main()
