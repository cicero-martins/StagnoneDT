"""Drop face 49487 (180° collinear vertex artifact) from the user's
manual mesh in-place, preserving RGFGRID's edge ordering and edge_faces.

Approach:
  1. Load Stagnone_v05_manual_net.nc
  2. Drop row 49487 from mesh2d_face_nodes, mesh2d_face_x/y/x_bnd/y_bnd
  3. Update mesh2d_edge_faces: any reference to face 49487 -> 0 (boundary marker)
     AND any face index > 49487 decrement by 1 (since indices shift after deletion)
  4. Write CRS as wgs84 EPSG:4326 (replacing projected_coordinate_system EPSG:0)
  5. Save to model/dflowfm_v05/Stagnone_v05_net.nc
"""
from __future__ import annotations
from pathlib import Path
import shutil
import numpy as np
import netCDF4 as nc

SRC = Path('model/dflowfm_v05/Stagnone_v05_manual_net.nc')
DST = Path('model/dflowfm_v05/Stagnone_v05_net.nc')
DST_DATA = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
BAD_FACE_0BASED = 49487  # 0-based index of the face to drop


def main():
    with nc.Dataset(SRC, 'r') as src:
        # Copy everything except the modified vars
        fn = np.asarray(src.variables['mesh2d_face_nodes'][:], dtype=np.int32)
        ef = np.asarray(src.variables['mesh2d_edge_faces'][:], dtype=np.int32)
        fx = np.asarray(src.variables['mesh2d_face_x'][:], dtype=np.float64)
        fy = np.asarray(src.variables['mesh2d_face_y'][:], dtype=np.float64)
        fxb = np.asarray(src.variables['mesh2d_face_x_bnd'][:], dtype=np.float64)
        fyb = np.asarray(src.variables['mesh2d_face_y_bnd'][:], dtype=np.float64)
        en = np.asarray(src.variables['mesh2d_edge_nodes'][:], dtype=np.int32)
        ex = np.asarray(src.variables['mesh2d_edge_x'][:], dtype=np.float64)
        ey = np.asarray(src.variables['mesh2d_edge_y'][:], dtype=np.float64)
        nx = np.asarray(src.variables['mesh2d_node_x'][:], dtype=np.float64)
        ny = np.asarray(src.variables['mesh2d_node_y'][:], dtype=np.float64)
        nz = np.asarray(src.variables['mesh2d_node_z'][:], dtype=np.float64)

    print(f'Source: {fn.shape[0]} faces, {en.shape[0]} edges, {len(nx)} nodes')

    # Drop face row
    keep = np.ones(fn.shape[0], dtype=bool)
    keep[BAD_FACE_0BASED] = False
    fn2 = fn[keep]
    fx2 = fx[keep]
    fy2 = fy[keep]
    fxb2 = fxb[keep]
    fyb2 = fyb[keep]
    print(f'After drop: {fn2.shape[0]} faces')

    # Update edge_faces: face indices are 1-based; bad face has 1-based index 49488
    bad_1b = BAD_FACE_0BASED + 1
    # Replace any reference to bad face with 0 (FillValue for boundary)
    ef2 = ef.copy()
    ef2[ef2 == bad_1b] = 0
    # Decrement any face index > bad_1b by 1 (since face list shifted)
    mask = ef2 > bad_1b
    ef2[mask] -= 1

    # Sanity
    n_ref_bad = (ef == bad_1b).sum()
    n_above = (ef > bad_1b).sum()
    print(f'  edge_faces: {n_ref_bad} edges referenced bad face -> 0 (boundary)')
    print(f'  edge_faces: {n_above} indices > bad face -> decremented')

    n_faces = fn2.shape[0]
    n_nodes = len(nx)
    n_edges = en.shape[0]
    n_max = fn2.shape[1]

    DST.parent.mkdir(parents=True, exist_ok=True)
    if DST.exists():
        bak = DST.with_suffix('.nc.bak_pre_dropface')
        if not bak.exists():
            shutil.copy2(DST, bak)

    with nc.Dataset(SRC, 'r') as src, nc.Dataset(DST, 'w', format='NETCDF3_CLASSIC') as ds:
        # Conventions
        for k in src.ncattrs():
            ds.setncattr(k, src.getncattr(k))

        # Dimensions
        ds.createDimension('mesh2d_nNodes', n_nodes)
        ds.createDimension('mesh2d_nFaces', n_faces)
        ds.createDimension('mesh2d_nMax_face_nodes', n_max)
        ds.createDimension('mesh2d_nEdges', n_edges)
        ds.createDimension('Two', 2)

        # Replace CRS variable with WGS84 EPSG:4326
        WGS84_WKT = ('GEOGCRS["WGS 84",ENSEMBLE["World Geodetic System 1984 ensemble",'
                     'MEMBER["World Geodetic System 1984 (Transit)"],'
                     'ELLIPSOID["WGS 84",6378137,298.257223563,LENGTHUNIT["metre",1]]],'
                     'PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],'
                     'CS[ellipsoidal,2],AXIS["lat",north],AXIS["lon",east],ID["EPSG",4326]]')
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

        # mesh2d topology — replicate user's structure but update node_coordinates to include node_z
        src_mesh = src.variables['mesh2d']
        mesh_var = ds.createVariable('mesh2d', src_mesh.dtype, ())
        for k in src_mesh.ncattrs():
            mesh_var.setncattr(k, src_mesh.getncattr(k))
        mesh_var.node_coordinates = 'mesh2d_node_x mesh2d_node_y mesh2d_node_z'

        # Copy node_x, node_y but update CRS attr
        for nm, arr in [('mesh2d_node_x', nx), ('mesh2d_node_y', ny)]:
            sv = src.variables[nm]
            attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
            fv_ = sv.getncattr('_FillValue') if '_FillValue' in sv.ncattrs() else None
            if 'grid_mapping' in attrs:
                attrs['grid_mapping'] = 'wgs84'
            v = ds.createVariable(nm, sv.dtype, sv.dimensions, fill_value=fv_)
            v[:] = arr
            for k, val in attrs.items():
                v.setncattr(k, val)

        # node_z
        sv = src.variables['mesh2d_node_z']
        attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
        nz_var = ds.createVariable('mesh2d_node_z', sv.dtype, sv.dimensions)
        nz_var[:] = nz
        for k, val in attrs.items():
            nz_var.setncattr(k, val)

        # edge_nodes — copy directly (same edges, same ordering)
        sv = src.variables['mesh2d_edge_nodes']
        attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
        fv_ = sv.getncattr('_FillValue') if '_FillValue' in sv.ncattrs() else None
        if 'grid_mapping' in attrs:
            attrs['grid_mapping'] = 'wgs84'
        v = ds.createVariable('mesh2d_edge_nodes', sv.dtype, sv.dimensions, fill_value=fv_)
        v[:] = en
        for k, val in attrs.items():
            v.setncattr(k, val)

        # edge_faces (UPDATED)
        sv = src.variables['mesh2d_edge_faces']
        attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
        fv_ = sv.getncattr('_FillValue') if '_FillValue' in sv.ncattrs() else None
        v = ds.createVariable('mesh2d_edge_faces', sv.dtype, sv.dimensions, fill_value=fv_)
        v[:] = ef2
        for k, val in attrs.items():
            v.setncattr(k, val)

        # face_nodes (UPDATED)
        sv = src.variables['mesh2d_face_nodes']
        attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
        fv_ = sv.getncattr('_FillValue') if '_FillValue' in sv.ncattrs() else None
        if 'grid_mapping' in attrs:
            attrs['grid_mapping'] = 'wgs84'
        v = ds.createVariable('mesh2d_face_nodes', sv.dtype, sv.dimensions, fill_value=fv_)
        v[:] = fn2
        for k, val in attrs.items():
            v.setncattr(k, val)

        # face_x, face_y, face_x_bnd, face_y_bnd (UPDATED — dropped one row)
        for nm, arr in [('mesh2d_face_x', fx2), ('mesh2d_face_y', fy2),
                        ('mesh2d_face_x_bnd', fxb2), ('mesh2d_face_y_bnd', fyb2)]:
            sv = src.variables[nm]
            attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
            fv_ = sv.getncattr('_FillValue') if '_FillValue' in sv.ncattrs() else None
            v = ds.createVariable(nm, sv.dtype, sv.dimensions, fill_value=fv_)
            v[:] = arr
            for k, val in attrs.items():
                v.setncattr(k, val)

        # edge_x, edge_y (unchanged)
        for nm, arr in [('mesh2d_edge_x', ex), ('mesh2d_edge_y', ey)]:
            sv = src.variables[nm]
            attrs = {k: sv.getncattr(k) for k in sv.ncattrs() if k != '_FillValue'}
            fv_ = sv.getncattr('_FillValue') if '_FillValue' in sv.ncattrs() else None
            v = ds.createVariable(nm, sv.dtype, sv.dimensions, fill_value=fv_)
            v[:] = arr
            for k, val in attrs.items():
                v.setncattr(k, val)

    print(f'wrote {DST}')

    DST_DATA.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DST, DST_DATA)
    print(f'synced {DST_DATA}')


if __name__ == '__main__':
    main()
