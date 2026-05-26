"""Fix v05 net.nc for Delft3D-QuickPlot compatibility.

dfm_tools/xugrid writes mesh2d_face_nodes as int64 (modern netCDF4); the legacy
MATLAB QuickPlot only handles int32 in the connectivity tables and raises
'Integers can only be combined with integers of the same class' at
private/netcdffil > qp_netcdf_ugrid_get_xy line 3351.

Additionally, the mesh2d variable produced by xugrid is missing the optional
face_coordinates/edge_coordinates attributes that QuickPlot looks up.

This script rewrites Stagnone_v05_net.nc so that:
  - mesh2d_face_nodes  : int64 -> int32
  - mesh2d_edge_nodes  : already int32 (kept)
  - start_index/_FillValue attrs: dtype-matched to the array
  - mesh2d.face_coordinates = "mesh2d_face_x mesh2d_face_y"
  - mesh2d.edge_coordinates = "mesh2d_edge_x mesh2d_edge_y"

Backup written to Stagnone_v05_net.nc.bak before edit.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4 as nc
import numpy as np

MESH = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
BAK = MESH.with_suffix('.nc.bak')


def main():
    if not MESH.exists():
        raise SystemExit(f'{MESH} not found')

    if not BAK.exists():
        shutil.copy(MESH, BAK)
        print(f'Backup -> {BAK}')

    # Read everything we need, then write fresh file (in-place rewrite is hard
    # with dtype changes; safer to dup with corrected schema).
    src = nc.Dataset(BAK, 'r')

    tmp = MESH.with_suffix('.nc.new')
    if tmp.exists():
        tmp.unlink()
    dst = nc.Dataset(tmp, 'w', format='NETCDF3_CLASSIC')

    # copy dims
    for name, dim in src.dimensions.items():
        dst.createDimension(name, len(dim) if not dim.isunlimited() else None)

    # copy global attrs
    for k in src.ncattrs():
        dst.setncattr(k, src.getncattr(k))

    int_conn_vars = {'mesh2d_face_nodes', 'mesh2d_edge_nodes', 'mesh2d_edge_faces',
                     'mesh2d_face_edges', 'mesh2d_face_links'}
    int_fillvalue_int32 = np.int32(-999)

    for name, var in src.variables.items():
        kwargs = {'zlib': False}  # NETCDF3_CLASSIC doesn't support compression
        # Force connectivity vars to int32
        if name in int_conn_vars or var.dtype == np.int64:
            new_dtype = 'i4'
        else:
            new_dtype = var.dtype

        # Copy without the _FillValue first
        fill = None
        attrs = {k: var.getncattr(k) for k in var.ncattrs()}
        if '_FillValue' in attrs:
            fill = attrs.pop('_FillValue')

        nv = dst.createVariable(name, new_dtype, var.dimensions,
                                 fill_value=(int_fillvalue_int32 if (name in int_conn_vars and fill is not None)
                                             else (np.array(fill, dtype=new_dtype) if fill is not None else None)))
        # write data, casting if needed
        data = var[:]
        if new_dtype == 'i4' and data.dtype != np.int32:
            # remap -999 fill -> int32; clamp anything else to int32 range
            data = np.where(data < -2**31 + 1, -999, data).astype(np.int32)
        nv[:] = data

        for k, v in attrs.items():
            # ensure start_index has same dtype as the var
            if k == 'start_index' and name in int_conn_vars:
                nv.setncattr(k, np.int32(v))
            else:
                nv.setncattr(k, v)

    # Fix mesh2d attributes
    if 'mesh2d' in dst.variables:
        m = dst.variables['mesh2d']
        if 'face_coordinates' not in m.ncattrs():
            m.face_coordinates = 'mesh2d_face_x mesh2d_face_y'
        if 'edge_coordinates' not in m.ncattrs() and 'mesh2d_edge_x' in src.variables:
            m.edge_coordinates = 'mesh2d_edge_x mesh2d_edge_y'

    src.close()
    dst.close()

    MESH.unlink()
    tmp.rename(MESH)
    print(f'Wrote {MESH} (NETCDF3_CLASSIC, int32 connectivity)')

    # quick verification
    ds = nc.Dataset(MESH)
    for vname in ('mesh2d_face_nodes', 'mesh2d_edge_nodes'):
        v = ds.variables[vname]
        si = v.start_index
        fv = v._FillValue if '_FillValue' in v.ncattrs() else None
        print(f'  {vname}: dtype={v.dtype} start_index={si} ({type(si).__name__}) _FillValue={fv}')
    if 'mesh2d' in ds.variables:
        m = ds.variables['mesh2d']
        print(f'  mesh2d.face_coordinates = {m.face_coordinates}')
        if 'edge_coordinates' in m.ncattrs():
            print(f'  mesh2d.edge_coordinates = {m.edge_coordinates}')
    ds.close()


if __name__ == '__main__':
    main()
