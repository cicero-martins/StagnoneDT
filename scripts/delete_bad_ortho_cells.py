"""Delete faces adjacent to edges with abs(ortho) > THRESHOLD.

Strategy:
  1. Compute orthogonality per edge via meshkernel
  2. For each edge above threshold, mark both adjacent faces for deletion
  3. Rebuild mesh without those faces
  4. Remove unused edges (edges only used by dropped faces)
  5. Remove unused nodes (nodes only used by dropped faces)
  6. Re-save net.nc preserving structure
  7. Preserve node_z by NN interpolation

In-place to model/dflowfm_v05/Stagnone_v05_net.nc with backup.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import numpy as np
import netCDF4 as nc
from collections import defaultdict
from meshkernel import MeshKernel, Mesh2d, ProjectionType

NET = Path('model/dflowfm_v05/Stagnone_v05_net.nc')
THRESHOLD = 0.85  # drop cells adjacent to edges with abs(ortho) > this


def main():
    with nc.Dataset(NET, 'r') as ds:
        nx = np.asarray(ds.variables['mesh2d_node_x'][:], dtype=np.float64)
        ny = np.asarray(ds.variables['mesh2d_node_y'][:], dtype=np.float64)
        nz = np.asarray(ds.variables['mesh2d_node_z'][:], dtype=np.float64)
        fn = np.asarray(ds.variables['mesh2d_face_nodes'][:], dtype=np.int32)
        en = np.asarray(ds.variables['mesh2d_edge_nodes'][:], dtype=np.int32)
        ef_was_present = 'mesh2d_edge_faces' in ds.variables
        if ef_was_present:
            ef = np.asarray(ds.variables['mesh2d_edge_faces'][:], dtype=np.int32)
        si = int(getattr(ds.variables['mesh2d_edge_nodes'], 'start_index', 1))
        # Snapshot of all vars to copy attrs from
        all_attrs = {}
        for vn in ds.variables:
            v = ds.variables[vn]
            all_attrs[vn] = {
                'dtype': v.dtype, 'dims': v.dimensions,
                'fill_value': v.getncattr('_FillValue') if '_FillValue' in v.ncattrs() else None,
                'attrs': {k: v.getncattr(k) for k in v.ncattrs() if k != '_FillValue'},
            }
        global_attrs = {k: ds.getncattr(k) for k in ds.ncattrs()}

    print(f'Loaded: {len(nx)} nodes, {fn.shape[0]} faces, {en.shape[0]} edges')

    # Meshkernel ortho
    en_flat = (en - si).astype(np.int32).flatten()
    mk = MeshKernel(projection=ProjectionType.SPHERICAL)
    mk.mesh2d_set(Mesh2d(node_x=nx, node_y=ny, edge_nodes=en_flat))
    ortho = np.asarray(mk.mesh2d_get_orthogonality().values)

    # Build edge -> face map from face_nodes
    edge_to_faces = defaultdict(list)
    for fi, face in enumerate(fn):
        mask = face != -999
        verts = face[mask]
        for k in range(len(verts)):
            a, b = int(verts[k]), int(verts[(k + 1) % len(verts)])
            key = (min(a, b), max(a, b))
            edge_to_faces[key].append(fi)

    # Identify bad edges, then their adjacent faces
    bad_edge_idx = np.where((ortho > -100) & (np.abs(ortho) > THRESHOLD))[0]
    drop_faces = set()
    edges_arr = en - si  # 0-based
    for ei in bad_edge_idx:
        n1, n2 = int(edges_arr[ei, 0]) + 1, int(edges_arr[ei, 1]) + 1  # 1-based
        key = (min(n1, n2), max(n1, n2))
        faces = edge_to_faces.get(key, [])
        for f in faces:
            drop_faces.add(f)

    print(f'Bad edges (abs(ortho)>{THRESHOLD}): {len(bad_edge_idx)}')
    print(f'Adjacent faces to drop: {len(drop_faces)}')

    # Keep mask for faces
    keep_face = np.ones(fn.shape[0], dtype=bool)
    for f in drop_faces:
        keep_face[f] = False
    fn_new = fn[keep_face]
    n_faces_new = fn_new.shape[0]
    print(f'Faces: {fn.shape[0]} -> {n_faces_new}')

    # Determine which edges are still used (in at least 1 remaining face)
    edge_used = defaultdict(int)
    for face in fn_new:
        mask = face != -999
        verts = face[mask]
        for k in range(len(verts)):
            a, b = int(verts[k]), int(verts[(k + 1) % len(verts)])
            key = (min(a, b), max(a, b))
            edge_used[key] += 1

    # Filter edge_nodes
    keep_edge_mask = np.zeros(en.shape[0], dtype=bool)
    for ei in range(en.shape[0]):
        a, b = int(en[ei, 0]), int(en[ei, 1])
        key = (min(a, b), max(a, b))
        if edge_used.get(key, 0) > 0:
            keep_edge_mask[ei] = True
    en_new = en[keep_edge_mask]
    n_edges_new = en_new.shape[0]
    print(f'Edges: {en.shape[0]} -> {n_edges_new}')

    # Determine which nodes are still used
    nodes_used = set()
    for face in fn_new:
        mask = face != -999
        for v in face[mask]:
            nodes_used.add(int(v))
    print(f'Nodes referenced: {len(nodes_used)} / {len(nx)}')

    # Renumber? Actually FM tolerates orphan nodes as long as they're not in face_nodes.
    # Keep nodes as-is to preserve indexing simplicity.

    # Rebuild face_x, face_y, face_z if present
    fx_new = np.zeros(n_faces_new, dtype=np.float64)
    fy_new = np.zeros(n_faces_new, dtype=np.float64)
    for i in range(n_faces_new):
        ids = fn_new[i]
        mask = ids != -999
        idxs = ids[mask] - 1
        fx_new[i] = nx[idxs].mean()
        fy_new[i] = ny[idxs].mean()

    # Rebuild face_x_bnd, face_y_bnd (per-vertex of face)
    n_max = fn_new.shape[1]
    fxb_new = np.full((n_faces_new, n_max), np.nan, dtype=np.float64)
    fyb_new = np.full((n_faces_new, n_max), np.nan, dtype=np.float64)
    for i in range(n_faces_new):
        ids = fn_new[i]
        mask = ids != -999
        idxs = ids[mask] - 1
        fxb_new[i, :len(idxs)] = nx[idxs]
        fyb_new[i, :len(idxs)] = ny[idxs]

    # Rebuild edge_x, edge_y
    ex_new = (nx[en_new[:, 0] - si] + nx[en_new[:, 1] - si]) * 0.5
    ey_new = (ny[en_new[:, 0] - si] + ny[en_new[:, 1] - si]) * 0.5

    # Rebuild edge_faces: for each retained edge, find which 1 or 2 retained faces it belongs to.
    if ef_was_present:
        # Build edge -> new face indices map
        new_idx_of_face = {}
        new_i = 0
        for old_i in range(fn.shape[0]):
            if keep_face[old_i]:
                new_idx_of_face[old_i] = new_i + 1  # 1-based
                new_i += 1
        # For each retained edge, look up the original face IDs and translate
        ef_new = np.zeros((n_edges_new, 2), dtype=np.int32)
        # Build key -> list of new face indices
        key_to_new_faces = defaultdict(list)
        for new_fi, face in enumerate(fn_new):
            mask = face != -999
            verts = face[mask]
            for k in range(len(verts)):
                a, b = int(verts[k]), int(verts[(k + 1) % len(verts)])
                key = (min(a, b), max(a, b))
                key_to_new_faces[key].append(new_fi + 1)
        for ei in range(n_edges_new):
            a, b = int(en_new[ei, 0]), int(en_new[ei, 1])
            key = (min(a, b), max(a, b))
            faces = key_to_new_faces.get(key, [])
            ef_new[ei, 0] = faces[0] if len(faces) > 0 else 0
            ef_new[ei, 1] = faces[1] if len(faces) > 1 else 0

    # Backup
    bak = NET.with_suffix('.nc.bak_pre_delcells')
    if not bak.exists():
        shutil.copy2(NET, bak)
        print(f'backup: {bak.name}')

    # Write new file
    tmp = NET.with_suffix('.nc.tmp_delcells')
    if tmp.exists():
        tmp.unlink()

    with nc.Dataset(tmp, 'w', format='NETCDF3_CLASSIC') as ds:
        for k, v in global_attrs.items():
            ds.setncattr(k, v)
        ds.createDimension('mesh2d_nNodes', len(nx))
        ds.createDimension('mesh2d_nFaces', n_faces_new)
        ds.createDimension('mesh2d_nMax_face_nodes', n_max)
        ds.createDimension('mesh2d_nEdges', n_edges_new)
        ds.createDimension('Two', 2)

        # Write each variable
        for vn, info in all_attrs.items():
            dt = info['dtype']
            dims = info['dims']
            fv = info['fill_value']
            attrs = info['attrs']
            v = ds.createVariable(vn, dt, dims, fill_value=fv)
            for ak, av in attrs.items():
                v.setncattr(ak, av)
            # Assign data
            if vn == 'mesh2d_node_x':
                v[:] = nx
            elif vn == 'mesh2d_node_y':
                v[:] = ny
            elif vn == 'mesh2d_node_z':
                v[:] = nz
            elif vn == 'mesh2d_face_nodes':
                v[:] = fn_new
            elif vn == 'mesh2d_edge_nodes':
                v[:] = en_new
            elif vn == 'mesh2d_edge_faces':
                v[:] = ef_new
            elif vn == 'mesh2d_face_x':
                v[:] = fx_new
            elif vn == 'mesh2d_face_y':
                v[:] = fy_new
            elif vn == 'mesh2d_face_x_bnd':
                v[:] = fxb_new
            elif vn == 'mesh2d_face_y_bnd':
                v[:] = fyb_new
            elif vn == 'mesh2d_edge_x':
                v[:] = ex_new
            elif vn == 'mesh2d_edge_y':
                v[:] = ey_new
            elif vn in ('mesh2d', 'projected_coordinate_system', 'wgs84'):
                # scalar variable, no data
                pass

    NET.unlink()
    tmp.rename(NET)
    print(f'wrote {NET}')

    # Verify orthogonality
    en_flat2 = (en_new - si).astype(np.int32).flatten()
    mk2 = MeshKernel(projection=ProjectionType.SPHERICAL)
    mk2.mesh2d_set(Mesh2d(node_x=nx, node_y=ny, edge_nodes=en_flat2))
    ortho2 = np.asarray(mk2.mesh2d_get_orthogonality().values)
    real = ortho2[ortho2 > -100]
    print(f'\nNew ortho: abs max={np.abs(real).max():.4f}')
    print(f'  edges abs > 0.95: {(np.abs(real) > 0.95).sum()}')
    print(f'  edges abs > 0.85: {(np.abs(real) > 0.85).sum()}')
    print(f'  edges abs > 0.5: {(np.abs(real) > 0.5).sum()}')


if __name__ == '__main__':
    main()
