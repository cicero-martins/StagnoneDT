"""Estende todas as forçantes de d10d12 para cobrir Jul 1 -> Jul 22 (de Jul 1-13).

Permite chain operacional Jul 13 -> Jul 20 publish days (window N-2 mais longa
termina em Jul 20 00:00; buffer até Jul 21/22 para segurança no FM step de
fechamento).

Inputs:
  data/raw/cmems_v04AE_d10d12/cmems_{uo,vo,so,thetao,zos}_2025-07-01_2025-07-13.nc
  data/raw/cmems_v04AE_jul13jul20/cmems_{uo,vo,so,thetao,zos}_2025-07-12_2025-07-22.nc
  model/dflowfm_v04AE_jul13jul20/era5_{msl,chnk,mer,u10n,v10n}_20250713to20250721_ERA5.nc
  model/dflowfm_v04AE_jul13jul20/wind_blendedAE_{u10n,v10n}_20250713to20250721.nc

Outputs (in-place rename + new files in model/dflowfm_v04AE_d10d12_extended/):
  Combined .nc + regenerated .bc covering Jul 1 -> Jul 22.

Posteriormente: scp para simit d10d12 + patch _new.ext / _old.ext referenciando
os novos filenames.
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
SRC_NC1 = ROOT / 'data' / 'raw' / 'cmems_v04AE_d10d12'           # Jul 1-13
SRC_NC2 = ROOT / 'data' / 'raw' / 'cmems_v04AE_jul13jul20'       # Jul 12-22
JUL13_DIR = ROOT / 'model' / 'dflowfm_v04AE_jul13jul20'           # Jul 13-21 meteo
D10D12 = ROOT / 'model' / 'dflowfm_v04AE_d10d12'                  # Jul 1-13 source
DST = ROOT / 'model' / 'dflowfm_v04AE_d10d12_extended'            # NEW unified Jul 1-22
COMBINED_CMEMS = ROOT / 'data' / 'raw' / 'cmems_v04AE_d10d12_extended'

PLI_FILE = D10D12 / 'Stagnone_dxy01_15m.pli'

REFDATE = pd.Timestamp('2025-01-01 00:00')
T_START = pd.Timestamp('2025-07-01 00:00')
T_STOP  = pd.Timestamp('2025-07-22 00:00')
T_STOP_TURBID_MIN = 30240  # Jul 22 00:00 in minutes since 2025-07-01


def concat_nc(out_path: Path, src1: Path, src2: Path, varname: str | None = None):
    """Concat 2 NetCDFs along time, dedup overlapping timestamps."""
    print(f'  concat -> {out_path.name}')
    print(f'    src1: {src1.name}')
    print(f'    src2: {src2.name}')
    ds1 = xr.open_dataset(src1)
    ds2 = xr.open_dataset(src2)
    if varname:
        ds = xr.concat([ds1[[varname]], ds2[[varname]]], dim='time')
    else:
        ds = xr.concat([ds1, ds2], dim='time', data_vars='minimal')
    # Drop duplicate timestamps (last one wins) and sort
    _, uniq = np.unique(ds.time.values, return_index=True)
    ds = ds.isel(time=uniq).sortby('time')
    ds = ds.sel(time=slice(T_START, T_STOP))
    print(f'    n_t: {len(ds.time)}, first={pd.Timestamp(ds.time.values[0])}, last={pd.Timestamp(ds.time.values[-1])}')
    enc = {v: {'zlib': True, 'complevel': 4} for v in ds.data_vars}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    ds.to_netcdf(out_path, encoding=enc)
    print(f'    wrote {out_path.stat().st_size / 1e6:.2f} MB')
    ds1.close(); ds2.close(); ds.close()


def step_1_concat_cmems():
    print('\n=== STEP 1: concat CMEMS Jul 1-13 + Jul 13-22 -> Jul 1-22 ===')
    for var in ['uo', 'vo', 'so', 'thetao', 'zos']:
        src1 = SRC_NC1 / f'cmems_{var}_2025-07-01_2025-07-13.nc'
        src2 = SRC_NC2 / f'cmems_{var}_2025-07-12_2025-07-22.nc'
        out = COMBINED_CMEMS / f'cmems_{var}_2025-07-01_2025-07-22.nc'
        concat_nc(out, src1, src2)


def step_2_concat_meteo():
    print('\n=== STEP 2: concat wind + ERA5 Jul 1-13 + Jul 13-21 ===')
    DST.mkdir(parents=True, exist_ok=True)

    # Wind blended (in D10D12 + JUL13)
    # NOTE: D10D12 has wind_blendedAE_*_20250701to20250713.nc
    # JUL13 has wind_blendedAE_*_20250713to20250721.nc
    for comp in ['u10n', 'v10n']:
        src1 = D10D12 / f'wind_blendedAE_{comp}_20250701to20250713.nc'
        src2 = JUL13_DIR / f'wind_blendedAE_{comp}_20250713to20250721.nc'
        out  = DST / f'wind_blendedAE_{comp}_20250701to20250721.nc'
        concat_nc(out, src1, src2)

    # ERA5: msl, chnk, mer (used by _old.ext for evaporation)
    for var in ['msl', 'chnk', 'mer']:
        src1 = D10D12 / f'era5_{var}_20250701to20250713_ERA5.nc'
        src2 = JUL13_DIR / f'era5_{var}_20250713to20250721_ERA5.nc'
        if not src1.exists() or not src2.exists():
            print(f'  [skip] missing src for era5_{var}: {src1.exists()=}, {src2.exists()=}')
            continue
        out  = DST / f'era5_{var}_20250701to20250721_ERA5.nc'
        concat_nc(out, src1, src2)


def step_3_extend_turbid_bc():
    print('\n=== STEP 3: extend turbid .bc to t=' + str(T_STOP_TURBID_MIN) + ' min (Jul 22 00:00) ===')
    for bc_name in ['turbid_airport_discharge.bc', 'turbid_saltpans_discharge.bc',
                    'turbid_airport_tracer.bc', 'turbid_saltpans_tracer.bc']:
        src = D10D12 / bc_name
        dst = DST / bc_name
        if not src.exists():
            print(f'  [skip] {bc_name} not in d10d12')
            continue
        text = src.read_text()
        # Last numeric line: should be "12960    0.0" (Jul 10 00:00 baseline) or 17280 (Jul 13)
        lines = text.rstrip('\n').split('\n')
        # Add trailing zero entry at T_STOP_TURBID_MIN
        lines.append(f'{T_STOP_TURBID_MIN}    0.0')
        dst.write_text('\n'.join(lines) + '\n')
        print(f'  extended {bc_name} -> Jul 22 00:00 (t={T_STOP_TURBID_MIN})')


def step_4_copy_static_bc():
    print('\n=== STEP 4: copy static .bc (offset_pernode, constant, tracer_zero) ===')
    for bc_name in ['waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc',
                    'waterlevelbnd_constant_Stagnone_dxy01_15m.bc',
                    'tracer_zero.bc']:
        src = D10D12 / bc_name
        if src.exists():
            shutil.copy2(src, DST / bc_name)
            print(f'  copied {bc_name}')


def step_5_regenerate_cmems_bc():
    """Use dfm_tools to regenerate waterlevelbnd, sal, temp from extended CMEMS."""
    print('\n=== STEP 5: regenerate waterlevelbnd / sal / temp .bc from extended CMEMS ===')
    if not PLI_FILE.exists():
        raise FileNotFoundError(f'PLI not found: {PLI_FILE}')

    import dfm_tools as dfmt
    import hydrolib.core.dflowfm as hcdfm

    # Monkey-patch (consistent w/ other build_cmems_bc scripts)
    if not hasattr(hcdfm, 'VectorQuantityUnitPairs'):
        from pydantic import BaseModel
        from typing import List, Any

        class _Stub(BaseModel):
            vectorname: str
            elementname: List[str]
            quantityunitpair: List[Any]

            class Config:
                arbitrary_types_allowed = True

            def __iter__(self):
                return iter(self.quantityunitpair)

        hcdfm.VectorQuantityUnitPairs = _Stub

    ext_new = hcdfm.ExtModel()
    list_quantities = ['waterlevelbnd', 'salinitybnd', 'temperaturebnd']
    dir_pattern = str(COMBINED_CMEMS / 'cmems_{ncvarname}_*.nc')

    # Need PLI in DST (cmems_nc_to_bc may need it relative)
    DST_PLI = DST / 'Stagnone_dxy01_15m.pli'
    if not DST_PLI.exists():
        shutil.copy2(PLI_FILE, DST_PLI)

    dfmt.cmems_nc_to_bc(
        ext_new=ext_new,
        list_quantities=list_quantities,
        tstart=T_START,
        tstop=T_STOP,
        file_pli=str(DST_PLI),
        dir_pattern=dir_pattern,
        dir_output=str(DST),
        refdate_str=f'minutes since {REFDATE.strftime("%Y-%m-%d %H:%M:%S")} +00:00',
    )
    print('  generated:')
    for bc in sorted(DST.glob('*CMEMS*.bc')):
        print(f'    {bc.name}  {bc.stat().st_size/1024:.1f} KB')


def step_6_regenerate_uxuy_bc():
    """Manual T3D vector builder for uxuy using extended CMEMS uo+vo."""
    print('\n=== STEP 6: regenerate uxuyadvectionvelocitybnd .bc (manual T3D) ===')
    uo_path = COMBINED_CMEMS / 'cmems_uo_2025-07-01_2025-07-22.nc'
    vo_path = COMBINED_CMEMS / 'cmems_vo_2025-07-01_2025-07-22.nc'
    out_bc = DST / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'

    uo_ds = xr.open_dataset(uo_path)
    vo_ds = xr.open_dataset(vo_path)
    uo = uo_ds['uo'].sel(time=slice(T_START, T_STOP))
    vo = vo_ds['vo'].sel(time=slice(T_START, T_STOP))

    depths_pos = uo.depth.values.astype(float)
    depths_neg = (-depths_pos).tolist()
    n_z = len(depths_pos)

    times = pd.to_datetime(uo.time.values)
    t_min = ((times - REFDATE).total_seconds() / 60.0).astype(float)
    n_t = len(t_min)

    # Parse PLI
    blocks = []
    with open(PLI_FILE) as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln and not ln[0].isdigit() and ln[0] != '-':
            cur_name = ln.strip()
            i += 1
            n_pts = int(lines[i].split()[0])
            i += 1
            pts = []
            for _ in range(n_pts):
                row = lines[i].split()
                pts.append((float(row[0]), float(row[1]), row[2] if len(row) > 2 else None))
                i += 1
            blocks.append((cur_name, pts))
        else:
            i += 1
    pli_name, pts = blocks[0]
    print(f'  pli: {pli_name!r} {len(pts)} nodes, n_t={n_t}, n_z={n_z}')

    vertPos_str = ' '.join(f'{d:.6f}' for d in depths_neg)
    with open(out_bc, 'w') as bc:
        bc.write('# written by extend_d10d12_forcings_to_jul22.py (extended Jul 1-22)\n')
        bc.write('\n[General]\nfileVersion = 1.01\nfileType    = boundConds\n')
        for k, (xn, yn, pt_name) in enumerate(pts, start=1):
            u_n = uo.interp(longitude=xn, latitude=yn, method='linear')
            v_n = vo.interp(longitude=xn, latitude=yn, method='linear')
            u_arr = np.nan_to_num(u_n.values, nan=0.0)
            v_arr = np.nan_to_num(v_n.values, nan=0.0)

            node_name = pt_name if pt_name else f'{pli_name}_{k:04d}'

            bc.write('\n[Forcing]\n')
            bc.write(f'name              = {node_name}\n')
            bc.write('function          = t3d\n')
            bc.write('offset            = 0.0\n')
            bc.write('factor            = 1.0\n')
            bc.write(f'vertPositions     = {vertPos_str}\n')
            bc.write('vertInterpolation = linear\n')
            bc.write('vertPositionType  = ZDatum\n')
            bc.write('timeInterpolation = linear\n')
            bc.write('quantity          = time\n')
            bc.write(f'unit              = minutes since {REFDATE.strftime("%Y-%m-%d %H:%M:%S")} +00:00\n')
            bc.write('vector            = uxuyadvectionvelocitybnd:ux,uy\n')
            for iz in range(1, n_z + 1):
                bc.write('quantity          = ux\n')
                bc.write('unit              = m s-1\n')
                bc.write(f'vertPositionIndex = {iz}\n')
                bc.write('quantity          = uy\n')
                bc.write('unit              = m s-1\n')
                bc.write(f'vertPositionIndex = {iz}\n')
            for it in range(n_t):
                row = [f'{t_min[it]:.6f}']
                for iz in range(n_z):
                    row.append(f'{u_arr[it, iz]:.6f}')
                    row.append(f'{v_arr[it, iz]:.6f}')
                bc.write(' '.join(row) + '\n')
            if k % 10 == 0 or k == len(pts):
                print(f'    [{k}/{len(pts)}]')
    sz = out_bc.stat().st_size / 1024
    print(f'  wrote {out_bc.name} ({sz:.0f} KB)')
    uo_ds.close(); vo_ds.close()


def main():
    DST.mkdir(parents=True, exist_ok=True)
    COMBINED_CMEMS.mkdir(parents=True, exist_ok=True)
    step_1_concat_cmems()
    step_2_concat_meteo()
    step_3_extend_turbid_bc()
    step_4_copy_static_bc()
    step_5_regenerate_cmems_bc()
    step_6_regenerate_uxuy_bc()
    print('\n=== ALL DONE. New extended dir: ' + str(DST) + ' ===')
    print('Contents:')
    for f in sorted(DST.iterdir()):
        if f.is_file():
            print(f'  {f.name}  ({f.stat().st_size/1024:.1f} KB)')


if __name__ == '__main__':
    main()
