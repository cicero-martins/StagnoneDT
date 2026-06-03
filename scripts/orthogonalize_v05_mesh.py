"""Run meshkernel orthogonalization on Stagnone_v05_net.nc to fix the
~445 non-orthogonal edges in the v04AE/v05 stitch zone (lagoon Stagnone).

Strategy: mild settings -- few outer iterations (2), default inner -- to
nudge problematic nodes without disturbing the well-formed v05 offshore
quads or v04AE lagoon triangles in their interiors.

Preserves node_z by interpolating from the ORIGINAL node positions to
the new (slightly displaced) positions via nearest-neighbor (since the
displacement is < cell size, NN is sufficient).

Reads:   data/processed/mesh_v05/Stagnone_v05_net.nc
Writes:  data/processed/mesh_v05/Stagnone_v05_net.nc  (overwrites; backup created)
Syncs:   model/dflowfm_v05/Stagnone_v05_net.nc
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

NET = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
MODEL_NET = Path('model/dflowfm_v05/Stagnone_v05_net.nc')

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


def main():
    # Load original mesh + node_z
    with nc.Dataset(NET, 'r') as ds:
        nx0 = np.asarray(ds.variables['mesh2d_node_x'][:], dtype=np.float64)
        ny0 = np.asarray(ds.variables['mesh2d_node_y'][:], dtype=np.float64)
        nz0 = np.asarray(ds.variables['mesh2d_node_z'][:], dtype=np.float64)
        en = np.asarray(ds.variables['mesh2d_edge_nodes'][:], dtype=np.int32)
        fn = np.asarray(ds.variables['mesh2d_face_nodes'][:], dtype=np.int32)
        si = int(ds.variables['mesh2d_edge_nodes'].start_index)
    en_flat = (en - si).astype(np.int32).flatten()

    print(f'Loaded mesh: {len(nx0)} nodes, {fn.shape[0]} faces, {en.shape[0]} edges')

    mk = MeshKernel(projection=ProjectionType.SPHERICAL)
    mk.mesh2d_set(Mesh2d(node_x=nx0, node_y=ny0, edge_nodes=en_flat))

    # Check orthogonality before
    ortho_before = np.asarray(mk.mesh2d_get_orthogonality().values)
    bad_before = (np.abs(ortho_before) > 0.5).sum()
    print(f'Before: {bad_before} edges with abs(cos)>0.5')

    # Run orthogonalization (mild settings — 2 outer × default inner)
    op = OrthogonalizationParameters(
        outer_iterations=2,
        boundary_iterations=25,
        inner_iterations=25,
        orthogonalization_to_smoothing_factor=0.975,
        orthogonalization_to_smoothing_factor_at_boundary=1.0,
        areal_to_angle_smoothing_factor=1.0,
    )
    print('\nRunning mesh2d_compute_orthogonalization (mild)...')
    # signature: (project_to_land_boundary_option, orthogonalization_parameters, selecting_polygon, land_boundaries)
    mk.mesh2d_compute_orthogonalization(
        project_to_land_boundary_option=ProjectToLandBoundaryOption.DO_NOT_PROJECT_TO_LANDBOUNDARY,
        orthogonalization_parameters=op,
        selecting_polygon=GeometryList(),
        land_boundaries=GeometryList(),
    )
    info = mk.mesh2d_get()
    nx1 = np.asarray(info.node_x, dtype=np.float64)
    ny1 = np.asarray(info.node_y, dtype=np.float64)
    print(f'After: {len(nx1)} nodes (was {len(nx0)})')

    # Check orthogonality after
    ortho_after = np.asarray(mk.mesh2d_get_orthogonality().values)
    bad_after = (np.abs(ortho_after) > 0.5).sum()
    print(f'After: {bad_after} edges with abs(cos)>0.5  (was {bad_before})')

    # Preserve node_z via NN from original positions
    print('\nRe-interpolating node_z via nearest-neighbor from original positions...')
    tree = cKDTree(np.column_stack([nx0, ny0]))
    _, idx = tree.query(np.column_stack([nx1, ny1]), k=1)
    nz1 = nz0[idx]
    max_disp = np.sqrt(((nx1-nx0)**2 + (ny1-ny0)**2)).max() * 111000
    moved = np.sqrt(((nx1-nx0)**2 + (ny1-ny0)**2)) * 111000 > 0.1  # >10 cm
    print(f'  nodes displaced > 10 cm: {moved.sum()} ({moved.sum()/len(nx1)*100:.2f}%)')
    print(f'  max displacement: {max_disp:.1f} m')

    # Reuse the same face_nodes (orthogonalization moves nodes but preserves topology)
    n_faces = fn.shape[0]

    # Backup + write
    bak = NET.with_suffix('.nc.bak_pre_ortho')
    if not bak.exists():
        shutil.copy2(NET, bak)
        print(f'  backup: {bak.name}')

    # rebuild face_x/y centroids
    fx = np.zeros(n_faces, dtype=np.float64)
    fy = np.zeros(n_faces, dtype=np.float64)
    for i in range(n_faces):
        ids = fn[i]
        mask = ids != -999
        fx[i] = nx1[ids[mask] - 1].mean()
        fy[i] = ny1[ids[mask] - 1].mean()
    face_z = np.zeros(n_faces, dtype=np.float64)
    for i in range(n_faces):
        ids = fn[i]
        mask = ids != -999
        face_z[i] = nz1[ids[mask] - 1].mean()

    # Get new edge connectivity from meshkernel (orthogonalization may not change it, but safe)
    new_en = np.asarray(info.edge_nodes, dtype=np.int32).reshape(-1, 2) + 1  # back to start_index=1

    with nc.Dataset(NET, 'w', format='NETCDF3_CLASSIC') as ds:
        ds.Conventions = 'CF-1.8 UGRID-1.0 Deltares-0.10'
        ds.createDimension('mesh2d_nNodes', len(nx1))
        ds.createDimension('mesh2d_nFaces', n_faces)
        ds.createDimension('mesh2d_nMax_face_nodes', 4)
        ds.createDimension('mesh2d_nEdges', new_en.shape[0])
        ds.createDimension('two', 2)

        mesh_var = ds.createVariable('mesh2d', 'i4', ())
        mesh_var.cf_role = 'mesh_topology'
        mesh_var.long_name = 'Topology data of 2D mesh'
        mesh_var.topology_dimension = np.int32(2)
        mesh_var.node_coordinates = 'mesh2d_node_x mesh2d_node_y'
        mesh_var.node_dimension = 'mesh2d_nNodes'
        mesh_var.edge_node_connectivity = 'mesh2d_edge_nodes'
        mesh_var.edge_dimension = 'mesh2d_nEdges'
        mesh_var.face_node_connectivity = 'mesh2d_face_nodes'
        mesh_var.face_dimension = 'mesh2d_nFaces'
        mesh_var.max_face_nodes_dimension = 'mesh2d_nMax_face_nodes'

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

        for vn, data, attrs in [
            ('mesh2d_node_x', nx1, dict(units='degrees_east', standard_name='longitude', long_name='x-coordinate of mesh nodes', mesh='mesh2d', location='node', grid_mapping='wgs84')),
            ('mesh2d_node_y', ny1, dict(units='degrees_north', standard_name='latitude', long_name='y-coordinate of mesh nodes', mesh='mesh2d', location='node', grid_mapping='wgs84')),
            ('mesh2d_face_x', fx, dict(units='degrees_east', standard_name='longitude', mesh='mesh2d', location='face', grid_mapping='wgs84')),
            ('mesh2d_face_y', fy, dict(units='degrees_north', standard_name='latitude', mesh='mesh2d', location='face', grid_mapping='wgs84')),
        ]:
            v = ds.createVariable(vn, 'f8', ('mesh2d_nNodes' if 'node' in vn else 'mesh2d_nFaces',))
            v[:] = data
            for k, val in attrs.items():
                v.setncattr(k, val)

        nz_var = ds.createVariable('mesh2d_node_z', 'f8', ('mesh2d_nNodes',), fill_value=-999.0)
        nz_var.units = 'm'
        nz_var.positive = 'up'
        nz_var.standard_name = 'altitude'
        nz_var.long_name = 'z-coordinate of mesh nodes'
        nz_var.mesh = 'mesh2d'
        nz_var.location = 'node'
        nz_var.coordinates = 'mesh2d_node_x mesh2d_node_y'
        nz_var.grid_mapping = 'wgs84'
        nz_var[:] = nz1

        en_var = ds.createVariable('mesh2d_edge_nodes', 'i4', ('mesh2d_nEdges', 'two'), fill_value=np.int32(-999))
        en_var.cf_role = 'edge_node_connectivity'
        en_var.long_name = 'Mapping from every edge to the two nodes that it connects'
        en_var.start_index = np.int32(1)
        en_var.mesh = 'mesh2d'
        en_var.location = 'edge'
        en_var[:] = new_en

        fn_var = ds.createVariable('mesh2d_face_nodes', 'i4', ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'), fill_value=np.int32(-999))
        fn_var.cf_role = 'face_node_connectivity'
        fn_var.long_name = 'Vertex nodes of mesh faces (counterclockwise)'
        fn_var.start_index = np.int32(1)
        fn_var.mesh = 'mesh2d'
        fn_var.location = 'face'
        fn_var[:] = fn[:, :4]

        fz_var = ds.createVariable('mesh2d_face_z', 'f8', ('mesh2d_nFaces',))
        fz_var.units = 'm'
        fz_var.positive = 'up'
        fz_var.standard_name = 'altitude'
        fz_var.long_name = 'z-coordinate of mesh face centers'
        fz_var.mesh = 'mesh2d'
        fz_var.location = 'face'
        fz_var.coordinates = 'mesh2d_face_x mesh2d_face_y'
        fz_var.grid_mapping = 'wgs84'
        fz_var[:] = face_z

    print(f'\nwrote {NET}')
    shutil.copy2(NET, MODEL_NET)
    print(f'synced {MODEL_NET}')


if __name__ == '__main__':
    main()
