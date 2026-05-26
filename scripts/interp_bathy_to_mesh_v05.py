"""Interpolate topobathy_combined.nc onto the face centres of the v05 mesh.

The mesh net.nc produced by build_mesh_v05.py has only geometry (face_x, face_y,
edge_x, edge_y, faces). FM expects `mesh2d_face_z` (= bedlevel per cell) before
the model can run. This script:

  1. Opens data/processed/mesh_v05/Stagnone_v05_net.nc (NETCDF3_CLASSIC, int32 conn)
  2. Loads data/processed/mesh_v05/topobathy_combined.nc
  3. Bilinearly samples topobathy at each face centre
  4. Adds mesh2d_face_z to the net.nc IN-PLACE (preserves QuickPlot compat)

FM bedlevel convention (bedLevType=1, project default):
  - positive z = above MSL (dry land; floods when WL > bl)
  - negative z = below MSL (wet)
This matches our signed topobathy directly. Islands (Marettimo, Egadi, Stagnone
barrier, Sicily mainland) get +z from TINITALY -> SLR/flooding scenarios ready.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import xarray as xr

MESH = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
TOPOBATHY = Path('data/processed/mesh_v05/topobathy_combined.nc')
FIG = Path('data/processed/mesh_v05/Stagnone_v05_bathy.png')


def main():
    if not MESH.exists():
        raise SystemExit(f'{MESH} not found. Run build_mesh_v05.py first.')
    if not TOPOBATHY.exists():
        raise SystemExit(f'{TOPOBATHY} not found. Run build_topobathy_v05.py first.')

    # Read face centres from net.nc (already computed by build_mesh_v05.py patcher)
    print(f'Loading mesh {MESH}')
    ds = nc.Dataset(MESH, 'r')
    if 'mesh2d_face_x' not in ds.variables:
        ds.close()
        raise SystemExit('mesh2d_face_x not in file -- rebuild with the latest build_mesh_v05.py')
    fx = np.asarray(ds.variables['mesh2d_face_x'][:])
    fy = np.asarray(ds.variables['mesh2d_face_y'][:])
    has_face_z = 'mesh2d_face_z' in ds.variables
    ds.close()
    n_faces = len(fx)
    print(f'  faces: {n_faces}')
    print(f'  bbox: lon=[{fx.min():.4f}, {fx.max():.4f}] lat=[{fy.min():.4f}, {fy.max():.4f}]')
    if has_face_z:
        print('  WARN: mesh2d_face_z already exists -- will be overwritten')

    print(f'\nLoading topobathy {TOPOBATHY}')
    topo_ds = xr.open_dataset(TOPOBATHY)
    topo = topo_ds['topobathy']
    print(f'  topo grid: {dict(topo.sizes)} range=({float(topo.min()):.1f}, {float(topo.max()):.1f})')

    print(f'\nSampling topobathy at {n_faces} face centres (bilinear)')
    da_at_faces = topo.interp(
        lon=xr.DataArray(fx, dims='face'),
        lat=xr.DataArray(fy, dims='face'),
        method='linear',
    )
    face_z = da_at_faces.values.astype(np.float32)
    nan_mask = ~np.isfinite(face_z)
    if nan_mask.any():
        print(f'  {nan_mask.sum()} faces outside topo grid -- nearest neighbour fill')
        from scipy.interpolate import NearestNDInterpolator
        valid = np.isfinite(topo.values)
        lat2 = topo['lat'].values
        lon2 = topo['lon'].values
        LON, LAT = np.meshgrid(lon2, lat2)
        interp_n = NearestNDInterpolator(
            list(zip(LON[valid].ravel(), LAT[valid].ravel())),
            topo.values[valid].ravel()
        )
        face_z[nan_mask] = interp_n(fx[nan_mask], fy[nan_mask])

    print(f'  face_z range: ({face_z.min():.2f}, {face_z.max():.2f})')
    print(f'  median: {np.median(face_z):.2f}')
    print(f'  land  faces (z>0): {(face_z > 0).sum()} ({100*(face_z>0).sum()/n_faces:.1f}%)')
    print(f'  sea   faces (z<0): {(face_z < 0).sum()} ({100*(face_z<0).sum()/n_faces:.1f}%)')

    # Add face_z in place via netCDF4 (preserves QuickPlot patch from build_mesh)
    print(f'\nAdding mesh2d_face_z to {MESH} (in-place)')
    ds = nc.Dataset(MESH, 'r+')
    if 'mesh2d_face_z' in ds.variables:
        ds.variables['mesh2d_face_z'][:] = face_z
    else:
        v = ds.createVariable('mesh2d_face_z', 'f4', ('mesh2d_nFaces',))
        v[:] = face_z
        v.standard_name = 'sea_floor_depth_below_geoid'
        v.long_name = 'bedlevel at face centre (positive=land, negative=sea)'
        v.units = 'm'
        v.mesh = 'mesh2d'
        v.location = 'face'
        v.source = str(TOPOBATHY)
    ds.close()
    print('  done')

    # Sanity plot
    print(f'\nPlotting {FIG}')
    fig, ax = plt.subplots(figsize=(11, 11))
    sc = ax.scatter(fx, fy, c=face_z, s=1.5, cmap='terrain', vmin=-50, vmax=200)
    ax.set_aspect(1 / np.cos(np.radians(np.mean(fy))))
    ax.set_xlabel('lon')
    ax.set_ylabel('lat')
    ax.set_title(f'Stagnone v05 mesh ({n_faces} cells) -- bedlevel from topobathy_combined')
    plt.colorbar(sc, ax=ax, shrink=0.8, label='face_z [m]  (positive=land)')
    plt.tight_layout()
    plt.savefig(FIG, dpi=140, bbox_inches='tight')
    print(f'  saved {FIG}')


if __name__ == '__main__':
    main()
