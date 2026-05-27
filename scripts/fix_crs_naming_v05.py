"""Rename CRS variable 'mesh2d_crs' -> 'wgs84' and reattach grid_mapping
attribute on bedlevel vars, to match v04AE convention.

The v04AE net.nc has:
  - CRS variable named 'wgs84' (int32 scalar with EPSG/proj4 attrs)
  - mesh2d_face_z, mesh2d_node_z carry grid_mapping='wgs84'

xugrid (used by build_mesh_v05.py) writes the CRS as 'mesh2d_crs' and FM
2026 may not resolve that pointer reliably. This script rewrites each
9 net.nc files (master + 8 partitioned) so that:
  - the CRS variable is renamed 'mesh2d_crs' -> 'wgs84'
  - every variable that had grid_mapping='mesh2d_crs' now has 'wgs84'
  - mesh2d_face_z gains grid_mapping='wgs84' (lost in regen_face_z_from_nodes_v05.py)
"""
from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4 as nc

MASTER = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
MODEL_DIR = Path('model/dflowfm_v05')


def patch_file(path: Path):
    print(f'\n=== {path.name} ===')
    bak = path.with_suffix('.nc.bak_pre_crs_rename')
    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix('.nc.tmp_crs')
    if tmp.exists():
        tmp.unlink()

    src = nc.Dataset(path, 'r')
    dst = nc.Dataset(tmp, 'w', format='NETCDF3_CLASSIC')

    # dims
    for n, d in src.dimensions.items():
        dst.createDimension(n, len(d) if not d.isunlimited() else None)
    # global attrs
    for k in src.ncattrs():
        dst.setncattr(k, src.getncattr(k))
    # vars: rename mesh2d_crs -> wgs84, others copied verbatim
    for name, var in src.variables.items():
        new_name = 'wgs84' if name == 'mesh2d_crs' else name
        attrs = {k: var.getncattr(k) for k in var.ncattrs()}
        fv = attrs.pop('_FillValue', None)
        nv = dst.createVariable(new_name, var.dtype, var.dimensions, fill_value=fv)
        if var.ndim == 0:
            nv.assignValue(var[...])
        else:
            nv[:] = var[:]
        for k, v in attrs.items():
            # update any reference to old CRS name
            if isinstance(v, str) and v == 'mesh2d_crs':
                v = 'wgs84'
            nv.setncattr(k, v)
    # face_z: ensure grid_mapping is set
    if 'mesh2d_face_z' in dst.variables:
        if 'grid_mapping' not in dst.variables['mesh2d_face_z'].ncattrs():
            dst.variables['mesh2d_face_z'].grid_mapping = 'wgs84'
            print('  added grid_mapping=wgs84 to mesh2d_face_z')

    src.close()
    dst.close()
    path.unlink()
    tmp.rename(path)

    # verify
    chk = nc.Dataset(path, 'r')
    has_wgs84 = 'wgs84' in chk.variables
    has_meshcrs = 'mesh2d_crs' in chk.variables
    fz_gm = chk.variables['mesh2d_face_z'].grid_mapping if 'grid_mapping' in chk.variables['mesh2d_face_z'].ncattrs() else '-'
    nz_gm = chk.variables['mesh2d_node_z'].grid_mapping if 'grid_mapping' in chk.variables['mesh2d_node_z'].ncattrs() else '-'
    print(f'  vars: wgs84 present={has_wgs84}, mesh2d_crs absent={not has_meshcrs}')
    print(f'  face_z.grid_mapping = {fz_gm}')
    print(f'  node_z.grid_mapping = {nz_gm}')
    chk.close()


def main():
    if not MASTER.exists():
        raise SystemExit(f'{MASTER} not found')
    patch_file(MASTER)
    shutil.copy2(MASTER, MODEL_DIR / 'Stagnone_v05_net.nc')
    print(f'\nSynced master -> {MODEL_DIR / "Stagnone_v05_net.nc"}')
    for p in sorted(MODEL_DIR.glob('Stagnone_v05_000*_net.nc')):
        patch_file(p)


if __name__ == '__main__':
    main()
