"""Merge v04AE lagoon interior mesh (triangular, hand-built, faithful to the
Stagnone barrier contour) into v05 (4-pass tier-refined, deep-ocean ready).

Workflow:
  1. Load v04AE master net.nc -> select cells inside lagoon polygon -> mk_lagoon
  2. Load v05 master net.nc -> delete cells inside the SAME polygon -> mk_v05_clip
  3. mesh2d_connect_meshes(mk_v05_clip, mk_lagoon) -> auto-stitch interface
  4. mesh2d_merge_nodes_with_merging_distance(1 m) -> dedupe overlapping nodes
  5. mesh2d_remove_disconnected_regions -> cleanup orphans
  6. Save as data/processed/mesh_v05_v04lagoon/Stagnone_v05_net.nc

The lagoon polygon covers the Stagnone barrier zone where v04AE has triangles.
Adjusted from earlier 12.38-12.55 / 37.76-37.97 to match v04AE's triangle area.

Output: data/processed/mesh_v05_v04lagoon/Stagnone_v05_net.nc + overview PNG
"""
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import xugrid as xu
from meshkernel import MeshKernel, GeometryList, Mesh2d, DeleteMeshOption

V04AE_NET = Path('model/dflowfm_v04AE/Stagnone_dxy01_15m_net.nc')
V05_NET   = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
OUT_DIR   = Path('data/processed/mesh_v05_v04lagoon')
OUT_NET   = OUT_DIR / 'Stagnone_v05_net.nc'

# Polygon covering v04AE lagoon-interior region (Stagnone barrier zone).
# Slightly bigger than the lagoon bbox to capture the v04AE triangle area
# fully: lon 12.38-12.52, lat 37.78-37.96
LAGOON_POLY_LON = np.array([12.38, 12.52, 12.52, 12.38, 12.38])
LAGOON_POLY_LAT = np.array([37.78, 37.78, 37.96, 37.96, 37.78])

MERGE_TOL_M = 5.0  # nodes within 5 m are merged (1 cell-edge tolerance)


def net_to_meshkernel(path: Path, name='') -> MeshKernel:
    """Load a Stagnone *_net.nc into a MeshKernel via raw netCDF4 read.

    Bug-workaround: passing face_nodes+nodes_per_face crashes meshkernel
    (access violation). Passing edge_nodes only WORKS -- meshkernel re-derives
    the faces internally.
    """
    print(f'  loading {path.name}...')
    from meshkernel import ProjectionType
    with nc.Dataset(path, 'r') as ds:
        nx = np.asarray(ds.variables['mesh2d_node_x'][:], dtype=np.float64)
        ny = np.asarray(ds.variables['mesh2d_node_y'][:], dtype=np.float64)
        en_var = ds.variables['mesh2d_edge_nodes']
        en = np.asarray(en_var[:], dtype=np.int32)
        si = int(getattr(en_var, 'start_index', 1))
    en_flat = (en - si).astype(np.int32).flatten()
    mesh2d = Mesh2d(node_x=nx, node_y=ny, edge_nodes=en_flat)
    mk = MeshKernel(projection=ProjectionType.SPHERICAL)
    mk.mesh2d_set(mesh2d)
    info = mk.mesh2d_get()
    print(f'    {name or path.stem}: {len(info.face_x)} cells, {len(info.node_x)} nodes')
    return mk


def write_lagoon_polygon_to_gl() -> GeometryList:
    return GeometryList(
        x_coordinates=LAGOON_POLY_LON.astype(np.float64),
        y_coordinates=LAGOON_POLY_LAT.astype(np.float64),
    )


def clip_mesh_outside_polygon(mk: MeshKernel, poly_gl: GeometryList, label='') -> MeshKernel:
    """Return mk with cells INSIDE poly_gl removed (keeps outside)."""
    info_before = mk.mesh2d_get()
    n_before = len(info_before.face_x)
    mk.mesh2d_delete(poly_gl, DeleteMeshOption.INSIDE_NOT_INTERSECTED, invert_deletion=False)
    info_after = mk.mesh2d_get()
    print(f'    {label}: {n_before} -> {len(info_after.face_x)} cells (deleted {n_before - len(info_after.face_x)} inside polygon)')
    return mk


def keep_mesh_inside_polygon(mk: MeshKernel, poly_gl: GeometryList, label='') -> MeshKernel:
    """Return mk with cells OUTSIDE poly_gl removed (keeps inside)."""
    info_before = mk.mesh2d_get()
    n_before = len(info_before.face_x)
    mk.mesh2d_delete(poly_gl, DeleteMeshOption.INSIDE_NOT_INTERSECTED, invert_deletion=True)
    info_after = mk.mesh2d_get()
    print(f'    {label}: {n_before} -> {len(info_after.face_x)} cells (kept {len(info_after.face_x)} inside polygon)')
    return mk


def save_mesh_to_netcdf(mk: MeshKernel, out_path: Path):
    """Write the merged mesh in a minimal v04AE-style UGRID layout that FM can read."""
    info = mk.mesh2d_get()
    nx = np.asarray(info.node_x)
    ny = np.asarray(info.node_y)
    face_nodes_flat = np.asarray(info.face_nodes, dtype=np.int32)
    nodes_per_face = np.asarray(info.nodes_per_face, dtype=np.int32)
    n_faces = len(info.face_x)
    max_nodes_per_face = int(nodes_per_face.max())
    # Reconstruct rectangular face_nodes matrix with fill values
    face_nodes_mat = np.full((n_faces, max_nodes_per_face), -1, dtype=np.int32)
    pos = 0
    for i in range(n_faces):
        npf = nodes_per_face[i]
        face_nodes_mat[i, :npf] = face_nodes_flat[pos:pos + npf]
        pos += npf

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with nc.Dataset(out_path, 'w', format='NETCDF3_CLASSIC') as ds:
        ds.createDimension('mesh2d_nNodes', len(nx))
        ds.createDimension('mesh2d_nFaces', n_faces)
        ds.createDimension('mesh2d_nMax_face_nodes', max_nodes_per_face)
        ds.Conventions = 'CF-1.8 UGRID-1.0 Deltares-0.10'

        mesh_var = ds.createVariable('mesh2d', 'i4', ())
        mesh_var.cf_role = 'mesh_topology'
        mesh_var.long_name = 'Topology data of 2D mesh'
        mesh_var.topology_dimension = 2
        mesh_var.node_coordinates = 'mesh2d_node_x mesh2d_node_y'
        mesh_var.face_node_connectivity = 'mesh2d_face_nodes'
        mesh_var.node_dimension = 'mesh2d_nNodes'
        mesh_var.face_dimension = 'mesh2d_nFaces'
        mesh_var.max_face_nodes_dimension = 'mesh2d_nMax_face_nodes'

        wgs_var = ds.createVariable('wgs84', 'i4', ())
        wgs_var.EPSG_code = 'EPSG:4326'
        wgs_var.epsg = np.int32(4326)
        wgs_var.grid_mapping_name = 'latitude_longitude'
        wgs_var.setncattr('name', 'WGS84')

        for vn, data, attrs in [
            ('mesh2d_node_x', nx, dict(units='degrees_east', standard_name='longitude', long_name='x-coordinate of mesh nodes', mesh='mesh2d', location='node')),
            ('mesh2d_node_y', ny, dict(units='degrees_north', standard_name='latitude', long_name='y-coordinate of mesh nodes', mesh='mesh2d', location='node')),
        ]:
            v = ds.createVariable(vn, 'f8', ('mesh2d_nNodes',))
            v[:] = data
            for k, val in attrs.items():
                v.setncattr(k, val)

        fn_var = ds.createVariable('mesh2d_face_nodes', 'i4',
                                   ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'),
                                   fill_value=np.int32(-1))
        fn_var[:] = face_nodes_mat
        fn_var.cf_role = 'face_node_connectivity'
        fn_var.mesh = 'mesh2d'
        fn_var.location = 'face'
        fn_var.start_index = np.int32(1)
    print(f'  wrote {out_path}')


def main():
    if not V04AE_NET.exists() or not V05_NET.exists():
        raise SystemExit('inputs missing')

    poly = write_lagoon_polygon_to_gl()

    print('\n[1] load v04AE master mesh, extract lagoon cells')
    mk_v04 = net_to_meshkernel(V04AE_NET, name='v04AE')
    mk_v04 = keep_mesh_inside_polygon(mk_v04, poly, label='v04AE lagoon clip')

    print('\n[2] load v05 master mesh, delete cells inside lagoon polygon')
    mk_v05 = net_to_meshkernel(V05_NET, name='v05')
    mk_v05 = clip_mesh_outside_polygon(mk_v05, poly, label='v05 outside-lagoon clip')

    print('\n[3] merge v05_outside + v04AE_lagoon via mesh2d_connect_meshes')
    # Pass via edge_nodes (face_nodes form crashes meshkernel)
    info_lagoon = mk_v04.mesh2d_get()
    nx_l = np.asarray(info_lagoon.node_x, dtype=np.float64)
    ny_l = np.asarray(info_lagoon.node_y, dtype=np.float64)
    en_l = np.asarray(info_lagoon.edge_nodes, dtype=np.int32)   # already flat
    mesh2d_lagoon = Mesh2d(node_x=nx_l, node_y=ny_l, edge_nodes=en_l)
    print(f'    lagoon mesh2d to inject: {len(nx_l)} nodes, {len(en_l)//2} edges, {len(info_lagoon.face_x)} faces')
    n_before = len(mk_v05.mesh2d_get().face_x)
    mk_v05.mesh2d_connect_meshes(mesh2d_lagoon, connect=True, polygon=GeometryList(), search_fraction=0.4)
    info_after = mk_v05.mesh2d_get()
    print(f'    merged: {n_before} -> {len(info_after.face_x)} cells (gained {len(info_after.face_x) - n_before})')

    print(f'\n[4] mesh2d_merge_nodes_with_merging_distance (tol={MERGE_TOL_M} m)')
    poly_full = GeometryList(
        x_coordinates=np.array([11.5, 13.0, 13.0, 11.5, 11.5], dtype=np.float64),
        y_coordinates=np.array([37.5, 37.5, 38.5, 38.5, 37.5], dtype=np.float64),
    )
    mk_v05.mesh2d_merge_nodes_with_merging_distance(poly_full, MERGE_TOL_M / 111000)   # deg
    info_dedup = mk_v05.mesh2d_get()
    print(f'    after dedup: {len(info_dedup.face_x)} cells, {len(info_dedup.node_x)} nodes')

    print('\n[5] save merged net.nc')
    save_mesh_to_netcdf(mk_v05, OUT_NET)

    print('\n[6] overview plot')
    fig, ax = plt.subplots(figsize=(11, 11))
    info = mk_v05.mesh2d_get()
    nx = np.asarray(info.node_x)
    ny = np.asarray(info.node_y)
    ax.scatter(info.face_x, info.face_y, c='blue', s=0.5, alpha=0.5,
               label=f'{len(info.face_x)} cells')
    ax.plot(LAGOON_POLY_LON, LAGOON_POLY_LAT, 'r--', lw=1.5, label='lagoon polygon')
    ax.set_aspect(1 / np.cos(np.radians(37.9)))
    ax.set_xlabel('lon'); ax.set_ylabel('lat')
    ax.set_title(f'v05 + v04AE lagoon merge: {len(info.face_x)} cells')
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / 'mesh_overview.png', dpi=140, bbox_inches='tight')
    print(f'  saved {OUT_DIR / "mesh_overview.png"}')

    print('\nDone.')


if __name__ == '__main__':
    main()
