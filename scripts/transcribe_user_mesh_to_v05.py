"""Transcribe user-edited grid_sobreposta_merged_net.nc into the FM-ready
v05 net.nc layout matching the WORKING v04AE/v05 convention exactly.

Key differences from naive xugrid-style output:
  - mesh2d.node_coordinates lists THREE vars: 'mesh2d_node_x mesh2d_node_y mesh2d_node_z'
  - mesh2d.face_coordinates / edge_coordinates listed in mesh2d topology
  - mesh2d_node_x/y: _FillValue=nan, only standard_name+grid_mapping (no units/long_name)
  - mesh2d_node_z: standard_name+long_name+units+mesh+location+coordinates (NO grid_mapping)
  - mesh2d_edge_nodes/face_nodes: cf_role, start_index, grid_mapping=wgs84, _FillValue
  - mesh2d_face_x/y/edge_x/y: standard_name+long_name+units only
  - mesh2d_face_z: full UGRID attrs incl. coordinates + grid_mapping

Plus:
  - Drop the 1 hex face (artifact from stitching)
  - Re-derive edges from cleaned face_nodes (dedup)
  - Re-derive face_x/y/z centroids
  - Convert CRS from EPSG:0 (projected_coordinate_system) to wgs84 EPSG:4326
"""
from __future__ import annotations
from pathlib import Path
import shutil
import numpy as np
import netCDF4 as nc

SRC = Path('model/dflowfm_v05/Stagnone_v05_manual_net.nc')
DST_MASTER = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
DST_MODEL = Path('model/dflowfm_v05/Stagnone_v05_net.nc')

WGS84_WKT = ('GEOGCRS["WGS 84",ENSEMBLE["World Geodetic System 1984 ensemble",'
             'MEMBER["World Geodetic System 1984 (Transit)"],'
             'MEMBER["World Geodetic System 1984 (G730)"],'
             'MEMBER["World Geodetic System 1984 (G873)"],'
             'MEMBER["World Geodetic System 1984 (G1150)"],'
             'MEMBER["World Geodetic System 1984 (G1674)"],'
             'MEMBER["World Geodetic System 1984 (G1762)"],'
             'MEMBER["World Geodetic System 1984 (G2139)"],'
             'MEMBER["World Geodetic System 1984 (G2296)"],'
             'ELLIPSOID["WGS 84",6378137,298.257223563,LENGTHUNIT["metre",1]],'
             'ENSEMBLEACCURACY[2.0]],PRIMEM["Greenwich",0,'
             'ANGLEUNIT["degree",0.0174532925199433]],CS[ellipsoidal,2],'
             'AXIS["geodetic latitude (Lat)",north,ORDER[1],'
             'ANGLEUNIT["degree",0.0174532925199433]],'
             'AXIS["geodetic longitude (Lon)",east,ORDER[2],'
             'ANGLEUNIT["degree",0.0174532925199433]],'
             'USAGE[SCOPE["Horizontal component of 3D system."],AREA["World."],'
             'BBOX[-90,-180,90,180]],ID["EPSG",4326]]')


def edges_from_faces(face_nodes_mat, fv=-999):
    """Build unique undirected edge list + edge_x/y midpoints from face_nodes (1-based)."""
    edge_set = {}
    for face in face_nodes_mat:
        mask = face != fv
        verts = face[mask]
        for k in range(len(verts)):
            a, b = verts[k], verts[(k + 1) % len(verts)]
            key = (min(a, b), max(a, b))
            edge_set[key] = None
    edges = np.array(sorted(edge_set.keys()), dtype=np.int32)
    return edges


def main():
    if not SRC.exists():
        raise SystemExit(f'src missing: {SRC}')

    src = nc.Dataset(SRC, 'r')
    nx = np.asarray(src.variables['mesh2d_node_x'][:], dtype=np.float64)
    ny = np.asarray(src.variables['mesh2d_node_y'][:], dtype=np.float64)
    nz = np.asarray(src.variables['mesh2d_node_z'][:], dtype=np.float64)
    fn = np.asarray(src.variables['mesh2d_face_nodes'][:], dtype=np.int32)
    fv = int(src.variables['mesh2d_face_nodes']._FillValue)
    src.close()

    n_unique = (fn != fv).sum(axis=1)
    keep = n_unique <= 4
    n_drop_big = (~keep).sum()

    # Also drop faces with near-collinear vertices (angle > 178°) — these are
    # degenerate quads that the user's manual stitch left behind (1 known: face 49487).
    # FM rejects them with "network is not orthogonal" because circumcenter -> infinity.
    bad_geom = np.zeros(fn.shape[0], dtype=bool)
    for i in range(fn.shape[0]):
        if not keep[i]:
            continue
        ids = fn[i]
        mask = ids != fv
        pts = np.array([(nx[ids[k] - 1], ny[ids[k] - 1]) for k in range(mask.sum())])
        for k in range(len(pts)):
            p1 = pts[(k - 1) % len(pts)]
            p2 = pts[k]
            p3 = pts[(k + 1) % len(pts)]
            v1 = p1 - p2
            v2 = p3 - p2
            nrm1 = np.linalg.norm(v1)
            nrm2 = np.linalg.norm(v2)
            if nrm1 < 1e-10 or nrm2 < 1e-10:
                bad_geom[i] = True
                break
            cos = np.clip(np.dot(v1, v2) / (nrm1 * nrm2), -1, 1)
            if np.degrees(np.arccos(cos)) > 178:
                bad_geom[i] = True
                break
    keep = keep & (~bad_geom)
    n_drop_geom = bad_geom.sum()

    print(f'src: {len(nx)} nodes, {fn.shape[0]} faces')
    print(f'  faces with >4 nodes (drop): {n_drop_big}')
    print(f'  faces with collinear vertices (drop): {n_drop_geom}')
    fn = fn[keep]
    fn_mat = np.where(fn != fv, fn, -999)[:, :4]
    n_faces = fn_mat.shape[0]
    print(f'  retained faces: {n_faces}')

    # Edges derived from face_nodes (dedup)
    edges = edges_from_faces(fn_mat)
    n_edges = edges.shape[0]
    print(f'  unique edges (from faces): {n_edges}')

    # Centroids
    fx = np.zeros(n_faces, dtype=np.float64)
    fy = np.zeros(n_faces, dtype=np.float64)
    face_z = np.zeros(n_faces, dtype=np.float64)
    for i in range(n_faces):
        ids = fn_mat[i]
        mask = ids != -999
        idx = ids[mask] - 1
        fx[i] = nx[idx].mean()
        fy[i] = ny[idx].mean()
        face_z[i] = nz[idx].mean()

    # Edge midpoints
    ex = (nx[edges[:, 0] - 1] + nx[edges[:, 1] - 1]) * 0.5
    ey = (ny[edges[:, 0] - 1] + ny[edges[:, 1] - 1]) * 0.5

    print(f'  z range: nodes {nz.min():.2f}..{nz.max():.2f}, faces {face_z.min():.2f}..{face_z.max():.2f}')

    DST_MASTER.parent.mkdir(parents=True, exist_ok=True)
    if DST_MASTER.exists():
        bak = DST_MASTER.with_suffix('.nc.bak_pre_user_edits2')
        if not bak.exists():
            shutil.copy2(DST_MASTER, bak)

    with nc.Dataset(DST_MASTER, 'w', format='NETCDF3_CLASSIC') as ds:
        ds.Conventions = 'CF-1.8 UGRID-1.0 Deltares-0.10'

        ds.createDimension('mesh2d_nNodes', len(nx))
        ds.createDimension('mesh2d_nFaces', n_faces)
        ds.createDimension('mesh2d_nMax_face_nodes', 4)
        ds.createDimension('mesh2d_nEdges', n_edges)
        ds.createDimension('two', 2)

        # CRS variable (matches working v05 wgs84 spec)
        wgs = ds.createVariable('wgs84', 'i4', ())
        wgs.crs_wkt = WGS84_WKT
        wgs.semi_major_axis = np.float64(6378137.0)
        wgs.semi_minor_axis = np.float64(6356752.314245179)
        wgs.inverse_flattening = np.float64(298.257223563)
        wgs.reference_ellipsoid_name = 'WGS 84'
        wgs.longitude_of_prime_meridian = np.float64(0.0)
        wgs.prime_meridian_name = 'Greenwich'
        wgs.geographic_crs_name = 'WGS 84'
        wgs.horizontal_datum_name = 'World Geodetic System 1984 ensemble'
        wgs.grid_mapping_name = 'latitude_longitude'
        wgs.spatial_ref = WGS84_WKT
        wgs.setncattr('name', 'WGS 84')
        wgs.epsg = np.int32(4326)

        # mesh2d topology (matches working bak exactly)
        mesh_var = ds.createVariable('mesh2d', 'i4', ())
        mesh_var.cf_role = 'mesh_topology'
        mesh_var.long_name = 'Topology data of 2D mesh'
        mesh_var.topology_dimension = np.int32(2)
        mesh_var.node_dimension = 'mesh2d_nNodes'
        mesh_var.edge_dimension = 'mesh2d_nEdges'
        mesh_var.face_dimension = 'mesh2d_nFaces'
        mesh_var.max_face_nodes_dimension = 'mesh2d_nMax_face_nodes'
        mesh_var.edge_node_connectivity = 'mesh2d_edge_nodes'
        mesh_var.face_node_connectivity = 'mesh2d_face_nodes'
        mesh_var.node_coordinates = 'mesh2d_node_x mesh2d_node_y mesh2d_node_z'
        mesh_var.setncattr('name', 'mesh2d')
        mesh_var.face_coordinates = 'mesh2d_face_x mesh2d_face_y'
        mesh_var.edge_coordinates = 'mesh2d_edge_x mesh2d_edge_y'

        # node_x: _FillValue=nan, standard_name + grid_mapping ONLY
        nxv = ds.createVariable('mesh2d_node_x', 'f8', ('mesh2d_nNodes',), fill_value=np.nan)
        nxv.standard_name = 'longitude'
        nxv.grid_mapping = 'wgs84'
        nxv[:] = nx

        nyv = ds.createVariable('mesh2d_node_y', 'f8', ('mesh2d_nNodes',), fill_value=np.nan)
        nyv.standard_name = 'latitude'
        nyv.grid_mapping = 'wgs84'
        nyv[:] = ny

        # node_z: NO grid_mapping, NO _FillValue (working bak doesn't have it)
        nzv = ds.createVariable('mesh2d_node_z', 'f8', ('mesh2d_nNodes',))
        nzv.standard_name = 'altitude'
        nzv.long_name = 'z-coordinate of mesh nodes (bedlevel)'
        nzv.units = 'm'
        nzv.mesh = 'mesh2d'
        nzv.location = 'node'
        nzv.coordinates = 'mesh2d_node_x mesh2d_node_y'
        nzv[:] = nz

        env = ds.createVariable('mesh2d_edge_nodes', 'i4', ('mesh2d_nEdges', 'two'),
                                fill_value=np.int32(-999))
        env.cf_role = 'edge_node_connectivity'
        env.start_index = np.int32(1)
        env.grid_mapping = 'wgs84'
        env[:] = edges

        fnv = ds.createVariable('mesh2d_face_nodes', 'i4',
                                ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'),
                                fill_value=np.int32(-999))
        fnv.cf_role = 'face_node_connectivity'
        fnv.start_index = np.int32(1)
        fnv.grid_mapping = 'wgs84'
        fnv[:] = fn_mat

        # face_x/y/edge_x/y: characteristic coords with standard_name+long_name+units only
        fxv = ds.createVariable('mesh2d_face_x', 'f8', ('mesh2d_nFaces',))
        fxv.standard_name = 'longitude'
        fxv.long_name = 'Characteristic longitude of mesh face'
        fxv.units = 'degrees_east'
        fxv[:] = fx

        fyv = ds.createVariable('mesh2d_face_y', 'f8', ('mesh2d_nFaces',))
        fyv.standard_name = 'latitude'
        fyv.long_name = 'Characteristic latitude of mesh face'
        fyv.units = 'degrees_north'
        fyv[:] = fy

        exv = ds.createVariable('mesh2d_edge_x', 'f8', ('mesh2d_nEdges',))
        exv.standard_name = 'longitude'
        exv.long_name = 'Characteristic longitude of mesh edge'
        exv.units = 'degrees_east'
        exv[:] = ex

        eyv = ds.createVariable('mesh2d_edge_y', 'f8', ('mesh2d_nEdges',))
        eyv.standard_name = 'latitude'
        eyv.long_name = 'Characteristic latitude of mesh edge'
        eyv.units = 'degrees_north'
        eyv[:] = ey

        fzv = ds.createVariable('mesh2d_face_z', 'f8', ('mesh2d_nFaces',))
        fzv.standard_name = 'altitude'
        fzv.long_name = 'z-coordinate of mesh faces'
        fzv.units = 'm'
        fzv.mesh = 'mesh2d'
        fzv.location = 'face'
        fzv.coordinates = 'mesh2d_face_x mesh2d_face_y'
        fzv.grid_mapping = 'wgs84'
        fzv[:] = face_z

    print(f'\nwrote {DST_MASTER}')

    DST_MODEL.parent.mkdir(parents=True, exist_ok=True)
    if DST_MODEL.exists():
        bak = DST_MODEL.with_suffix('.nc.bak_pre_user_edits2')
        if not bak.exists():
            shutil.copy2(DST_MODEL, bak)
    shutil.copy2(DST_MASTER, DST_MODEL)
    print(f'synced {DST_MODEL}')


if __name__ == '__main__':
    main()
