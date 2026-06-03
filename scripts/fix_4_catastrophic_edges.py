"""Run mesh2d_compute_orthogonalization in 4 small polygons covering the
catastrophically non-orthogonal edges (abs(ortho)=1.0):
  #1 (12.5817, 38.0611) — Sicily NE coast
  #2 (12.5798, 38.0560) — same area (close to #1)
  #3 (12.3286, 38.1545) — offshore N
  #4 (12.0611, 37.9404) — offshore E of Marettimo

Strategy: 1 merged polygon for #1+#2 (close together) + 1 each for #3, #4.
Aggressive settings (10 outer × 25 inner iterations) inside polygon — many
nodes move there but the rest of the mesh is untouched.

Preserves node_z by NN interpolation from original positions.

Reads + writes: model/dflowfm_v05/Stagnone_v05_net.nc
"""
from __future__ import annotations
from pathlib import Path
import shutil
import numpy as np
import netCDF4 as nc
from meshkernel import (
    MeshKernel, Mesh2d, ProjectionType,
    OrthogonalizationParameters, ProjectToLandBoundaryOption,
    GeometryList,
)
from scipy.spatial import cKDTree

NET = Path('model/dflowfm_v05/Stagnone_v05_net.nc')
RADIUS_DEG = 0.005  # ~500m at lat 37.9

# Catastrophic edge midpoints (lon, lat)
HOTSPOTS = [
    # Sicily NE pair (close enough to merge)
    {'name': 'sicily_NE',  'lon': 12.5807, 'lat': 38.0585, 'r': 0.008},
    {'name': 'offshore_N', 'lon': 12.3286, 'lat': 38.1545, 'r': 0.005},
    {'name': 'marettimo_E','lon': 12.0611, 'lat': 37.9404, 'r': 0.005},
]


def make_box_polygon(lon, lat, r):
    """Square polygon centered at (lon,lat) of half-side r. CCW with closing point."""
    return GeometryList(
        x_coordinates=np.array([lon-r, lon+r, lon+r, lon-r, lon-r], dtype=np.float64),
        y_coordinates=np.array([lat-r, lat-r, lat+r, lat+r, lat-r], dtype=np.float64),
    )


def main():
    with nc.Dataset(NET, 'r') as ds:
        nx0 = np.asarray(ds.variables['mesh2d_node_x'][:], dtype=np.float64)
        ny0 = np.asarray(ds.variables['mesh2d_node_y'][:], dtype=np.float64)
        nz0 = np.asarray(ds.variables['mesh2d_node_z'][:], dtype=np.float64)
        en = np.asarray(ds.variables['mesh2d_edge_nodes'][:], dtype=np.int32)
        si = int(getattr(ds.variables['mesh2d_edge_nodes'], 'start_index', 1))
    en_flat = (en - si).astype(np.int32).flatten()

    mk = MeshKernel(projection=ProjectionType.SPHERICAL)
    mk.mesh2d_set(Mesh2d(node_x=nx0, node_y=ny0, edge_nodes=en_flat))
    info0 = mk.mesh2d_get()
    print(f'Loaded: {len(info0.node_x)} nodes')

    ortho_before = np.asarray(mk.mesh2d_get_orthogonality().values)
    bad_before = ((ortho_before > -100) & (np.abs(ortho_before) > 0.5)).sum()
    print(f'Before: {bad_before} edges with abs(ortho) > 0.5')

    op = OrthogonalizationParameters(
        outer_iterations=10,
        boundary_iterations=25,
        inner_iterations=25,
        orthogonalization_to_smoothing_factor=0.975,
        orthogonalization_to_smoothing_factor_at_boundary=1.0,
        areal_to_angle_smoothing_factor=1.0,
    )

    for hs in HOTSPOTS:
        poly = make_box_polygon(hs['lon'], hs['lat'], hs['r'])
        print(f'\nOrthogonalizing {hs["name"]} at ({hs["lon"]:.4f},{hs["lat"]:.4f}) r={hs["r"]}...')
        mk.mesh2d_compute_orthogonalization(
            project_to_land_boundary_option=ProjectToLandBoundaryOption.DO_NOT_PROJECT_TO_LANDBOUNDARY,
            orthogonalization_parameters=op,
            selecting_polygon=poly,
            land_boundaries=GeometryList(),
        )
        ortho_now = np.asarray(mk.mesh2d_get_orthogonality().values)
        bad_now = ((ortho_now > -100) & (np.abs(ortho_now) > 0.5)).sum()
        print(f'  bad edges (>0.5): {bad_now}')

    info1 = mk.mesh2d_get()
    nx1 = np.asarray(info1.node_x, dtype=np.float64)
    ny1 = np.asarray(info1.node_y, dtype=np.float64)
    print(f'\nAfter all 4 hotspots: {len(nx1)} nodes')

    # Displacement check
    if len(nx1) == len(nx0):
        disp = np.sqrt((nx1-nx0)**2 + (ny1-ny0)**2) * 111000  # meters
        print(f'  max displacement: {disp.max():.1f} m')
        print(f'  nodes moved > 1m: {(disp > 1).sum()}')
        print(f'  nodes moved > 10m: {(disp > 10).sum()}')

    # Final ortho check
    ortho_final = np.asarray(mk.mesh2d_get_orthogonality().values)
    real = ortho_final[ortho_final > -100]
    print(f'\nFinal ortho stats:')
    print(f'  abs max: {np.abs(real).max():.4f}')
    print(f'  edges abs > 0.95: {(np.abs(real) > 0.95).sum()}')
    print(f'  edges abs > 0.5: {(np.abs(real) > 0.5).sum()}')

    # Preserve node_z via NN
    print('\nRe-interpolating node_z via NN...')
    tree = cKDTree(np.column_stack([nx0, ny0]))
    _, idx = tree.query(np.column_stack([nx1, ny1]), k=1)
    nz1 = nz0[idx]

    # Backup + rewrite IN-PLACE (only updates nx, ny, nz; preserves all other vars/structure)
    bak = NET.with_suffix('.nc.bak_pre_aggro_ortho')
    if not bak.exists():
        shutil.copy2(NET, bak)
        print(f'backup: {bak.name}')

    # Update mesh2d_node_x, node_y, node_z in-place
    with nc.Dataset(NET, 'r+') as ds:
        ds.variables['mesh2d_node_x'][:] = nx1
        ds.variables['mesh2d_node_y'][:] = ny1
        ds.variables['mesh2d_node_z'][:] = nz1
        # Update edge_x, edge_y midpoints
        if 'mesh2d_edge_x' in ds.variables:
            en = np.asarray(ds.variables['mesh2d_edge_nodes'][:], dtype=np.int32)
            si = int(getattr(ds.variables['mesh2d_edge_nodes'], 'start_index', 1))
            ex = (nx1[en[:,0]-si] + nx1[en[:,1]-si]) * 0.5
            ey = (ny1[en[:,0]-si] + ny1[en[:,1]-si]) * 0.5
            ds.variables['mesh2d_edge_x'][:] = ex
            ds.variables['mesh2d_edge_y'][:] = ey
        # Update face_x, face_y centroids
        if 'mesh2d_face_x' in ds.variables:
            fn = np.asarray(ds.variables['mesh2d_face_nodes'][:], dtype=np.int32)
            n_faces = fn.shape[0]
            fx = np.zeros(n_faces, dtype=np.float64)
            fy = np.zeros(n_faces, dtype=np.float64)
            for i in range(n_faces):
                ids = fn[i]
                mask = ids != -999
                idxs = ids[mask] - 1
                fx[i] = nx1[idxs].mean()
                fy[i] = ny1[idxs].mean()
            ds.variables['mesh2d_face_x'][:] = fx
            ds.variables['mesh2d_face_y'][:] = fy
            if 'mesh2d_face_x_bnd' in ds.variables:
                # bnd is per-vertex-of-face
                fxb = np.full(ds.variables['mesh2d_face_x_bnd'].shape, np.nan, dtype=np.float64)
                fyb = np.full(ds.variables['mesh2d_face_y_bnd'].shape, np.nan, dtype=np.float64)
                for i in range(n_faces):
                    ids = fn[i]
                    mask = ids != -999
                    idxs = ids[mask] - 1
                    fxb[i, :len(idxs)] = nx1[idxs]
                    fyb[i, :len(idxs)] = ny1[idxs]
                ds.variables['mesh2d_face_x_bnd'][:] = fxb
                ds.variables['mesh2d_face_y_bnd'][:] = fyb
    print(f'updated {NET} in-place')


if __name__ == '__main__':
    main()
