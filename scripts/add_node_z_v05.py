"""Add mesh2d_node_z to v05 net.nc by sampling topobathy at node coordinates.

DeltaShell's GridApi requires `mesh2d_node_z` (UGRID node z-coordinates) to
load a grid -- error -1015 'Couldn't get z node coordinates'. xugrid writes
only node_x/y; we computed face_z via interp_bathy_to_mesh_v05.py but never
generated node_z.

Also wires mesh2d.node_coordinates to include the new variable and tags
mesh2d_node_z with standard_name / units so the UI recognises it as bathy.

Output: data/processed/mesh_v05/Stagnone_v05_net.nc updated IN PLACE +
        propagated to partitioned files Stagnone_v05_NNNN_net.nc.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4 as nc
import numpy as np
import xarray as xr

MASTER = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
TOPOBATHY = Path('data/processed/mesh_v05/topobathy_combined.nc')
MODEL_DIR = Path('model/dflowfm_v05')


def sample_topobathy_at_nodes(node_x: np.ndarray, node_y: np.ndarray) -> np.ndarray:
    """Bilinear sample of topobathy at node (lon, lat). NaN-fill via nearest."""
    topo_ds = xr.open_dataset(TOPOBATHY)
    topo = topo_ds['topobathy']
    z = topo.interp(
        lon=xr.DataArray(node_x, dims='node'),
        lat=xr.DataArray(node_y, dims='node'),
        method='linear',
    ).values.astype(np.float32)
    nan = ~np.isfinite(z)
    if nan.any():
        print(f'  {int(nan.sum())} nodes outside topo grid -- nearest fill')
        from scipy.interpolate import NearestNDInterpolator
        valid = np.isfinite(topo.values)
        LON, LAT = np.meshgrid(topo['lon'].values, topo['lat'].values)
        nn = NearestNDInterpolator(
            list(zip(LON[valid].ravel(), LAT[valid].ravel())),
            topo.values[valid].ravel(),
        )
        z[nan] = nn(node_x[nan], node_y[nan])
    topo_ds.close()
    return z


def add_node_z_inplace(path: Path):
    """Open netCDF in append mode, compute node_z, write variable."""
    ds = nc.Dataset(path, 'r+')
    if 'mesh2d_node_z' in ds.variables:
        print(f'  {path.name}: mesh2d_node_z already present, overwriting')
    nx = ds.variables['mesh2d_node_x'][:]
    ny = ds.variables['mesh2d_node_y'][:]
    z = sample_topobathy_at_nodes(np.asarray(nx), np.asarray(ny))
    if 'mesh2d_node_z' in ds.variables:
        ds.variables['mesh2d_node_z'][:] = z
    else:
        v = ds.createVariable('mesh2d_node_z', 'f8', ('mesh2d_nNodes',))
        v[:] = z
        v.standard_name = 'altitude'
        v.long_name = 'z-coordinate of mesh nodes (bedlevel)'
        v.units = 'm'
        v.mesh = 'mesh2d'
        v.location = 'node'
        v.coordinates = 'mesh2d_node_x mesh2d_node_y'

    # Update mesh2d.node_coordinates attribute to include the new var
    if 'mesh2d' in ds.variables:
        m = ds.variables['mesh2d']
        cur = m.node_coordinates if 'node_coordinates' in m.ncattrs() else ''
        if 'mesh2d_node_z' not in cur:
            m.node_coordinates = (cur + ' mesh2d_node_z').strip()

    print(f'  {path.name}: node_z range=({z.min():.1f}, {z.max():.1f}) '
          f'median={np.median(z):.1f}')
    ds.close()


def main():
    if not MASTER.exists():
        raise SystemExit(f'{MASTER} not found')
    if not TOPOBATHY.exists():
        raise SystemExit(f'{TOPOBATHY} not found')

    # Backup once
    bak = MASTER.with_suffix('.nc.bak_pre_node_z')
    if not bak.exists():
        shutil.copy2(MASTER, bak)
        print(f'Backup -> {bak.name}')

    print(f'\n[master] {MASTER}')
    add_node_z_inplace(MASTER)

    # Sync to model dir master copy + all partitioned files
    model_master = MODEL_DIR / 'Stagnone_v05_net.nc'
    if model_master.exists():
        shutil.copy2(MASTER, model_master)
        print(f'\nCopied master -> {model_master}')

    partitioned = sorted(MODEL_DIR.glob('Stagnone_v05_000*_net.nc'))
    if partitioned:
        print(f'\n[{len(partitioned)} partitioned files]')
        for p in partitioned:
            add_node_z_inplace(p)


if __name__ == '__main__':
    main()
