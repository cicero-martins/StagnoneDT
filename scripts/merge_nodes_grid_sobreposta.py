"""Deduplicate coincident nodes at the v04AE-lagoon / v05-offshore interface.

Input:  data/processed/mesh_v05/grid_sobreposta_net.nc  (user-stitched in RGFGRID)
Output: data/processed/mesh_v05/grid_sobreposta_merged_net.nc

Strategy:
  1. KDTree on (node_x, node_y), find pairs within MERGE_TOL_M
  2. For each pair (i, j) with i<j: map j -> i in all face_nodes and edge_nodes
  3. Compact node array: drop nodes that became unreachable
  4. Update _x, _y, _z, face_nodes, edge_nodes with remapped indices
  5. Drop zero-length edges (start == end after merge)
  6. Save corrected net.nc

NB: face_x, face_y, face_x_bnd, face_y_bnd, edge_x, edge_y are recomputed
from the new connectivity to ensure consistency.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4 as nc
import numpy as np
from scipy.spatial import cKDTree

INPUT  = Path('data/processed/mesh_v05/grid_sobreposta_net.nc')
OUTPUT = Path('data/processed/mesh_v05/grid_sobreposta_merged_net.nc')
# 50 m tolerance: above 50 m we start collapsing legitimate triangle edges
# (v04AE lagoon mesh has nearest-neighbour spacing ~50-100 m). Below 50 m we
# capture only the interface duplicates (RGFGRID-stitched edges that aren't
# perfectly aligned). Tolerance sweep showed pair count jumps from 722@50m
# to 24531@100m -- clear natural cutoff.
MERGE_TOL_DEG = 50.0 / 111000   # ~50 m at lat 37.9


def main():
    assert INPUT.exists(), f'{INPUT} not found'

    # Backup input as bak if no merged exists
    if OUTPUT.exists():
        OUTPUT.unlink()

    src = nc.Dataset(INPUT, 'r')

    nx = np.asarray(src.variables['mesh2d_node_x'][:], dtype=np.float64)
    ny = np.asarray(src.variables['mesh2d_node_y'][:], dtype=np.float64)
    has_nz = 'mesh2d_node_z' in src.variables
    nz = np.asarray(src.variables['mesh2d_node_z'][:], dtype=np.float64) if has_nz else None
    n_nodes_in = len(nx)

    fn_var = src.variables['mesh2d_face_nodes']
    fn = np.asarray(fn_var[:], dtype=np.int64)
    fn_fill = int(fn_var._FillValue) if '_FillValue' in fn_var.ncattrs() else -999
    fn_start = int(getattr(fn_var, 'start_index', 1))

    en_var = src.variables['mesh2d_edge_nodes']
    en = np.asarray(en_var[:], dtype=np.int64)
    en_start = int(getattr(en_var, 'start_index', 1))

    n_faces = fn.shape[0]
    n_edges = en.shape[0]
    print(f'INPUT: {n_nodes_in} nodes, {n_edges} edges, {n_faces} faces')

    # === STEP 1: find coincident node pairs ===
    tree = cKDTree(np.column_stack([nx, ny]))
    pairs = sorted(tree.query_pairs(r=MERGE_TOL_DEG))
    print(f'\n[1] coincident pairs (tol={MERGE_TOL_DEG} deg ~= 1.1 m): {len(pairs)}')

    if not pairs:
        print('No pairs found, nothing to merge.')
        shutil.copy2(INPUT, OUTPUT)
        return

    # === STEP 2: build remap[old_index] -> new_index ===
    # Use Union-Find so chains of duplicates resolve correctly
    parent = list(range(n_nodes_in))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            # keep smaller index as root
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    for a, b in pairs:
        union(int(a), int(b))

    # Build canonical map: every node -> root, then compact roots into 0..n_unique-1
    roots = np.array([find(i) for i in range(n_nodes_in)], dtype=np.int64)
    unique_roots, new_idx = np.unique(roots, return_inverse=True)
    n_nodes_out = len(unique_roots)
    print(f'\n[2] union-find: {n_nodes_in} -> {n_nodes_out} unique nodes (merged {n_nodes_in - n_nodes_out})')

    # Compact node coords (use root's coords)
    nx_out = nx[unique_roots]
    ny_out = ny[unique_roots]
    nz_out = nz[unique_roots] if has_nz else None

    # === STEP 3: remap face_nodes + edge_nodes ===
    # Convert from 1-based start_index to 0-based, apply new_idx, then back to 1-based
    fn_zero = fn.copy()
    valid_face_mask = (fn != fn_fill) & (fn >= fn_start)
    fn_zero[valid_face_mask] -= fn_start
    # apply remap only to valid entries
    fn_remap = fn_zero.copy()
    fn_remap[valid_face_mask] = new_idx[fn_zero[valid_face_mask]]
    fn_remap[~valid_face_mask] = -1   # mark as fill (we'll reset later)

    en_zero = en - en_start
    en_remap = new_idx[en_zero]   # all entries valid

    print(f'\n[3] face_nodes remapped: {valid_face_mask.sum()} entries')
    print(f'    edge_nodes remapped: {en.size} entries')

    # === STEP 4: detect & remove zero-length edges (start==end after merge) ===
    edge_collapsed = en_remap[:, 0] == en_remap[:, 1]
    n_edges_collapsed = int(edge_collapsed.sum())
    print(f'\n[4] zero-length edges (collapsed): {n_edges_collapsed}')
    en_keep = en_remap[~edge_collapsed]

    # Also: detect duplicate edges (same node pair after merge) and dedupe
    # Normalize as (min, max) pairs
    edge_pairs = np.sort(en_keep, axis=1)
    edge_unique, edge_inv = np.unique(edge_pairs, axis=0, return_index=True)
    print(f'    unique edges after dedup: {len(edge_unique)} (was {len(en_keep)})')
    en_final = edge_unique

    # === STEP 5: clean up degenerate faces ===
    # A face is degenerate if any 2 of its valid nodes are the same after merge.
    # Resolution:
    #   - unique_count == original valid count -> face OK, keep as-is
    #   - unique_count == original - 1 (quad with 1 dup) -> convert to triangle
    #     (drop duplicate, preserving cyclic order)
    #   - unique_count <= 2 -> drop the face (invalid)
    fn_clean = fn_remap.copy()
    valid_mask_clean = valid_face_mask.copy()
    keep_face = np.ones(n_faces, dtype=bool)
    n_quad_to_tri = 0
    n_dropped = 0
    for i in range(n_faces):
        valid = fn_remap[i][valid_face_mask[i]]
        if len(valid) == 0:
            continue
        # preserve order while finding uniques (np.unique sorts, we want stable)
        seen = set()
        unique_ordered = []
        for nidx in valid:
            if nidx not in seen:
                seen.add(int(nidx))
                unique_ordered.append(int(nidx))
        n_unique = len(unique_ordered)
        if n_unique == len(valid):
            continue   # OK
        if n_unique <= 2:
            keep_face[i] = False
            n_dropped += 1
            continue
        # n_unique = len(valid) - 1 (or more dups but still >=3 unique): rebuild row
        n_quad_to_tri += 1
        new_row = np.full(fn_remap.shape[1], -1, dtype=fn_remap.dtype)
        new_row[:n_unique] = unique_ordered
        fn_clean[i] = new_row
        valid_mask_clean[i] = new_row >= 0

    print(f'\n[5] degenerate face cleanup:')
    print(f'    quads with 1 dup -> triangles (or similar): {n_quad_to_tri}')
    print(f'    dropped (<= 2 unique nodes): {n_dropped}')

    # Apply face mask: keep only valid faces
    fn_remap = fn_clean[keep_face]
    valid_face_mask = valid_mask_clean[keep_face]
    n_faces_out = fn_remap.shape[0]
    print(f'    n_faces: {n_faces} -> {n_faces_out}')

    # === STEP 6: recompute face/edge centers and bnd from new connectivity ===
    # Face center = mean of valid node coords
    face_x_out = np.zeros(n_faces_out, dtype=np.float64)
    face_y_out = np.zeros(n_faces_out, dtype=np.float64)
    max_npf = fn_remap.shape[1]
    face_x_bnd = np.full((n_faces_out, max_npf), nx_out.mean(), dtype=np.float64)
    face_y_bnd = np.full((n_faces_out, max_npf), ny_out.mean(), dtype=np.float64)
    for i in range(n_faces_out):
        nodes = fn_remap[i][valid_face_mask[i]]
        if len(nodes) == 0:
            continue
        xs = nx_out[nodes]
        ys = ny_out[nodes]
        face_x_out[i] = xs.mean()
        face_y_out[i] = ys.mean()
        face_x_bnd[i, :len(nodes)] = xs
        face_y_bnd[i, :len(nodes)] = ys

    edge_x_out = 0.5 * (nx_out[en_final[:, 0]] + nx_out[en_final[:, 1]])
    edge_y_out = 0.5 * (ny_out[en_final[:, 0]] + ny_out[en_final[:, 1]])

    print(f'\n[6] recomputed face_x/y, face_x/y_bnd, edge_x/y')

    # === STEP 7: write output ===
    # Convert back to 1-based for FM
    fn_out = fn_remap.copy() + 1
    fn_out[~valid_face_mask] = -999  # use -999 as fill (v04AE convention)
    en_out = en_final + 1

    with nc.Dataset(OUTPUT, 'w', format='NETCDF3_CLASSIC') as dst:
        # Global attrs
        for k in src.ncattrs():
            dst.setncattr(k, src.getncattr(k))
        if 'Conventions' not in dst.ncattrs():
            dst.Conventions = 'CF-1.8 UGRID-1.0 Deltares-0.10'

        # Dims
        dst.createDimension('mesh2d_nNodes', n_nodes_out)
        dst.createDimension('mesh2d_nEdges', len(en_out))
        dst.createDimension('mesh2d_nFaces', n_faces_out)
        dst.createDimension('mesh2d_nMax_face_nodes', max_npf)
        dst.createDimension('Two', 2)

        # mesh2d topology var
        mesh_v = dst.createVariable('mesh2d', 'i4', ())
        for k, v in {
            'cf_role': 'mesh_topology',
            'long_name': 'Topology data of 2D mesh',
            'topology_dimension': np.int32(2),
            'node_coordinates': 'mesh2d_node_x mesh2d_node_y',
            'face_coordinates': 'mesh2d_face_x mesh2d_face_y',
            'edge_coordinates': 'mesh2d_edge_x mesh2d_edge_y',
            'face_node_connectivity': 'mesh2d_face_nodes',
            'edge_node_connectivity': 'mesh2d_edge_nodes',
            'node_dimension': 'mesh2d_nNodes',
            'edge_dimension': 'mesh2d_nEdges',
            'face_dimension': 'mesh2d_nFaces',
            'max_face_nodes_dimension': 'mesh2d_nMax_face_nodes',
        }.items():
            mesh_v.setncattr(k, v)

        # wgs84 CRS
        wgs_v = dst.createVariable('wgs84', 'i4', ())
        for k, v in {
            'EPSG_code': 'EPSG:4326',
            'epsg': np.int32(4326),
            'grid_mapping_name': 'latitude_longitude',
            'longitude_of_prime_meridian': np.float64(0.0),
            'semi_major_axis': np.float64(6378137.0),
            'semi_minor_axis': np.float64(6356752.314245),
            'inverse_flattening': np.float64(298.257223563),
            'proj4_params': '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs',
            'value': 'value is equal to EPSG code',
        }.items():
            wgs_v.setncattr(k, v)
        wgs_v.setncattr('name', 'WGS84')

        # node_x, node_y
        for name, data, attrs in [
            ('mesh2d_node_x', nx_out, dict(units='degrees_east', standard_name='longitude',
                                            long_name='x-coordinate of mesh nodes', mesh='mesh2d',
                                            location='node', grid_mapping='wgs84')),
            ('mesh2d_node_y', ny_out, dict(units='degrees_north', standard_name='latitude',
                                            long_name='y-coordinate of mesh nodes', mesh='mesh2d',
                                            location='node', grid_mapping='wgs84')),
        ]:
            v = dst.createVariable(name, 'f8', ('mesh2d_nNodes',))
            v[:] = data
            for k, val in attrs.items():
                v.setncattr(k, val)

        if has_nz:
            v = dst.createVariable('mesh2d_node_z', 'f8', ('mesh2d_nNodes',),
                                    fill_value=np.float64(-999.0))
            v[:] = nz_out
            for k, val in dict(units='m', standard_name='altitude',
                                long_name='z-coordinate of mesh nodes',
                                mesh='mesh2d', location='node',
                                grid_mapping='wgs84',
                                coordinates='mesh2d_node_x mesh2d_node_y').items():
                v.setncattr(k, val)

        # face_nodes
        v = dst.createVariable('mesh2d_face_nodes', 'i4',
                                ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'),
                                fill_value=np.int32(-999))
        v[:] = fn_out.astype(np.int32)
        for k, val in dict(cf_role='face_node_connectivity', mesh='mesh2d',
                            location='face', start_index=np.int32(1)).items():
            v.setncattr(k, val)

        # edge_nodes
        v = dst.createVariable('mesh2d_edge_nodes', 'i4',
                                ('mesh2d_nEdges', 'Two'))
        v[:] = en_out.astype(np.int32)
        for k, val in dict(cf_role='edge_node_connectivity', mesh='mesh2d',
                            location='edge', start_index=np.int32(1)).items():
            v.setncattr(k, val)

        # face_x, face_y
        for name, data, std in [('mesh2d_face_x', face_x_out, 'longitude'),
                                  ('mesh2d_face_y', face_y_out, 'latitude')]:
            v = dst.createVariable(name, 'f8', ('mesh2d_nFaces',))
            v[:] = data
            v.standard_name = std
            v.long_name = f'Characteristic {std} of mesh face'
            v.units = 'degrees_east' if 'lon' in std else 'degrees_north'
            v.mesh = 'mesh2d'
            v.location = 'face'

        # face_x_bnd, face_y_bnd
        for name, data in [('mesh2d_face_x_bnd', face_x_bnd),
                            ('mesh2d_face_y_bnd', face_y_bnd)]:
            v = dst.createVariable(name, 'f8', ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'))
            v[:] = data
            v.mesh = 'mesh2d'
            v.location = 'face'

        # edge_x, edge_y
        for name, data, std in [('mesh2d_edge_x', edge_x_out, 'longitude'),
                                  ('mesh2d_edge_y', edge_y_out, 'latitude')]:
            v = dst.createVariable(name, 'f8', ('mesh2d_nEdges',))
            v[:] = data
            v.standard_name = std
            v.long_name = f'Characteristic {std} of mesh edge'
            v.units = 'degrees_east' if 'lon' in std else 'degrees_north'
            v.mesh = 'mesh2d'
            v.location = 'edge'

    src.close()

    print(f'\n[7] wrote {OUTPUT} ({OUTPUT.stat().st_size/1e6:.1f} MB)')
    print(f'    {n_nodes_out} nodes, {len(en_out)} edges, {n_faces} faces')

    # Quick verification - reopen and check coincident pairs again
    with nc.Dataset(OUTPUT) as ds:
        nx2 = np.asarray(ds.variables['mesh2d_node_x'][:])
        ny2 = np.asarray(ds.variables['mesh2d_node_y'][:])
    tree2 = cKDTree(np.column_stack([nx2, ny2]))
    pairs2 = tree2.query_pairs(r=MERGE_TOL_DEG)
    print(f'\nVerify: coincident pairs after merge: {len(pairs2)} (was {len(pairs)})')


if __name__ == '__main__':
    main()
