"""Patch mesh2d_face_z to match v04AE convention so FM recognises bedlevel.

v04AE_nodm uses:
  mesh2d_face_z : float64, standard_name='altitude', long_name='z-coordinate of mesh faces'
v05 (interp_bathy_to_mesh_v05.py) wrote:
  mesh2d_face_z : float32, standard_name='sea_floor_depth_below_geoid'

FM 2026 ignores the v05 variant -> falls back to BedlevUni=+5m -> mesh runs
DRY (waterdepth=0 everywhere, water level=NaN).

This patcher rewrites mesh2d_face_z in-place: cast to float64 and update
standard_name + long_name. Applied to master + 8 partitioned files.
"""
from __future__ import annotations

from pathlib import Path

import netCDF4 as nc
import numpy as np

MASTER = Path('data/processed/mesh_v05/Stagnone_v05_net.nc')
MODEL_DIR = Path('model/dflowfm_v05')


def patch_face_z(path: Path):
    print(f'\n=== {path.name} ===')
    ds = nc.Dataset(path, 'r+')
    if 'mesh2d_face_z' not in ds.variables:
        print('  no mesh2d_face_z - skip')
        ds.close()
        return
    v = ds.variables['mesh2d_face_z']
    print(f'  before: dtype={v.dtype}, standard_name={v.getncattr("standard_name") if "standard_name" in v.ncattrs() else "-"}')
    if v.dtype == np.float32:
        # netCDF4 can't change dtype in-place; read, delete-recreate
        data = v[:].astype(np.float64)
        attrs = {k: v.getncattr(k) for k in v.ncattrs()}
        dims = v.dimensions
        fill = attrs.pop('_FillValue', None)
        # delete old; create new as float64
        ds.close()
        # reopen with explicit nc4 mode
        with nc.Dataset(path, 'r+') as ds2:
            # netCDF3_CLASSIC doesn't support variable deletion; instead create
            # tmp file. Use scratch approach.
            pass
        # fall back: read everything, rewrite file
        import shutil
        tmp = path.with_suffix('.nc.tmp')
        with nc.Dataset(path, 'r') as src, nc.Dataset(tmp, 'w', format='NETCDF3_CLASSIC') as dst:
            for n, d in src.dimensions.items():
                dst.createDimension(n, len(d) if not d.isunlimited() else None)
            for k in src.ncattrs():
                dst.setncattr(k, src.getncattr(k))
            for vn, vv in src.variables.items():
                attrs_src = {k: vv.getncattr(k) for k in vv.ncattrs()}
                fv = attrs_src.pop('_FillValue', None)
                new_dtype = 'f8' if vn == 'mesh2d_face_z' else vv.dtype
                if fv is not None:
                    fv_typed = np.array(fv, dtype=new_dtype)
                else:
                    fv_typed = None
                nv = dst.createVariable(vn, new_dtype, vv.dimensions, fill_value=fv_typed)
                if vn == 'mesh2d_face_z':
                    nv[:] = vv[:].astype(np.float64)
                    # FM-expected attributes
                    nv.standard_name = 'altitude'
                    nv.long_name = 'z-coordinate of mesh faces'
                    nv.units = 'm'
                    nv.mesh = 'mesh2d'
                    nv.location = 'face'
                else:
                    nv[:] = vv[:]
                    for k, v_val in attrs_src.items():
                        nv.setncattr(k, v_val)
        path.unlink()
        tmp.rename(path)
        # verify
        with nc.Dataset(path, 'r') as chk:
            fz = chk.variables['mesh2d_face_z']
            print(f'  after:  dtype={fz.dtype}, standard_name={fz.getncattr("standard_name")}, range=({fz[:].min():.1f}, {fz[:].max():.1f})')
    else:
        # already float64; just rewrite standard_name attr
        v.standard_name = 'altitude'
        v.long_name = 'z-coordinate of mesh faces'
        ds.close()
        with nc.Dataset(path, 'r') as chk:
            fz = chk.variables['mesh2d_face_z']
            print(f'  after:  dtype={fz.dtype}, standard_name={fz.getncattr("standard_name")} (attrs-only update)')


def main():
    if not MASTER.exists():
        raise SystemExit(f'{MASTER} not found')

    patch_face_z(MASTER)
    # sync to model dir master
    import shutil
    target = MODEL_DIR / 'Stagnone_v05_net.nc'
    if target.exists():
        shutil.copy2(MASTER, target)
        print(f'\nCopied master -> {target}')

    # patch each partitioned file
    for p in sorted(MODEL_DIR.glob('Stagnone_v05_000*_net.nc')):
        patch_face_z(p)


if __name__ == '__main__':
    main()
