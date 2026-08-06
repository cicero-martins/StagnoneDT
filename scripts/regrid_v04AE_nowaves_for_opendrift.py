"""Regrid v04AE_nowaves surface currents onto a rectilinear lat/lon grid for
OpenDrift.

Clone of the server-side regrid_vr_for_opendrift.py, which uses a manual
partition loop with plain xarray and scipy instead of dfm_tools. That matters
because dfm_tools is NOT installed on simit-server, in either the base
interpreter or the stagnone_extract conda env, and the 9-day map.nc output is
far too large to pull back to the laptop just to regrid it. Run this where the
output lives.

The wind fields are identical across the whole v04AE family (the members differ
only in wave coupling, morphodynamics, and roughness), so the AE-only blend is
read from the v04AE directory.

Usage, on simit-server:
    source ~/miniconda3/etc/profile.d/conda.sh && conda activate stagnone_extract
    python ~/StagnoneDT/scripts/regrid_v04AE_nowaves_for_opendrift.py

Output: data/processed/v04AE_nowaves_surface_current.nc
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

warnings.filterwarnings('ignore')

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
WIND_DIR = ROOT / 'model' / 'dflowfm_v04AE'
OUT_DIR = ROOT / 'model' / 'dflowfm_v04AE_nowaves' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
RUN_NAME = 'v04AE_nowaves'

LON_MIN, LON_MAX = 12.00, 12.55
LAT_MIN, LAT_MAX = 37.70, 38.05
DX, DY = 0.002, 0.002
T_MIN = '2025-07-07T00:00:00'
T_MAX = '2025-07-10T00:00:00'
LAND_BL_THRESH = -0.05
KDIST_DEG = 0.003
NPART = 8

lons = np.arange(LON_MIN, LON_MAX + DX / 2, DX)
lats = np.arange(LAT_MIN, LAT_MAX + DY / 2, DY)
LON, LAT = np.meshgrid(lons, lats)
tgt_pts = np.column_stack([LON.ravel(), LAT.ravel()])


def load_partitions(out_dir):
    """Concatenate surface-layer face data across all map.nc partitions."""
    all_fx, all_fy, all_bl, all_ucx, all_ucy = [], [], [], [], []
    times = None
    for p in range(NPART):
        f = out_dir / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not f.exists():
            print(f'  partition {p}: MISSING, skipped')
            continue
        ds = xr.open_dataset(f)
        lay = [d for d in ds['mesh2d_ucx'].dims if 'lay' in d.lower()]
        ucx = ds['mesh2d_ucx'].isel({lay[0]: -1}) if lay else ds['mesh2d_ucx']
        ucy = ds['mesh2d_ucy'].isel({lay[0]: -1}) if lay else ds['mesh2d_ucy']
        ucx = ucx.sel(time=slice(T_MIN, T_MAX))
        ucy = ucy.sel(time=slice(T_MIN, T_MAX))
        if times is None:
            times = pd.to_datetime(ucx.time.values)
        all_fx.append(ds['mesh2d_face_x'].values)
        all_fy.append(ds['mesh2d_face_y'].values)
        all_bl.append(ds['mesh2d_flowelem_bl'].values)
        all_ucx.append(ucx.values)
        all_ucy.append(ucy.values)
        ds.close()
    return (np.concatenate(all_fx), np.concatenate(all_fy),
            np.concatenate(all_bl), np.concatenate(all_ucx, axis=1),
            np.concatenate(all_ucy, axis=1), times)


def main():
    print(f'=== {RUN_NAME} ===')
    fx, fy, bl, ucx, ucy, times = load_partitions(OUT_DIR)
    print(f'Total: {len(fx)} faces, {len(times)} timesteps '
          f'({times[0]} .. {times[-1]})')

    water = bl < LAND_BL_THRESH
    fx_w, fy_w = fx[water], fy[water]
    print(f'Water faces (bl < {LAND_BL_THRESH} m): {water.sum()} / {len(fx)}')

    tree = cKDTree(np.column_stack([fx_w, fy_w]))
    dists, _ = tree.query(tgt_pts)
    mask_far = dists > KDIST_DEG
    print(f'Target cells with a valid water source: '
          f'{(~mask_far).sum()} / {len(dists)}')

    ntime = len(times)
    u_out = np.full((ntime, len(lats), len(lons)), np.nan, dtype=np.float32)
    v_out = np.full((ntime, len(lats), len(lons)), np.nan, dtype=np.float32)
    src = np.column_stack([fx_w, fy_w])
    for it in range(ntime):
        u_f = griddata(src, ucx[it][water], tgt_pts, method='linear')
        v_f = griddata(src, ucy[it][water], tgt_pts, method='linear')
        u_f[mask_far] = np.nan
        v_f[mask_far] = np.nan
        u_out[it] = u_f.reshape(LON.shape)
        v_out[it] = v_f.reshape(LON.shape)
        if (it + 1) % 20 == 0 or it == ntime - 1:
            print(f'  [{it+1}/{ntime}] {times[it]}  '
                  f'u_abs_max={np.nanmax(np.abs(u_f)):.3f} m/s')

    print('Adding wind (AE-only blend, shared across the v04AE family)...')
    wu = xr.open_dataset(WIND_DIR / 'wind_blendedAE_u10n_20250701to20250710.nc')
    wv = xr.open_dataset(WIND_DIR / 'wind_blendedAE_v10n_20250701to20250710.nc')
    u10 = wu['u10n'].interp(time=times, latitude=lats,
                            longitude=lons).values.astype(np.float32)
    v10 = wv['v10n'].interp(time=times, latitude=lats,
                            longitude=lons).values.astype(np.float32)
    wu.close()
    wv.close()

    ds_out = xr.Dataset(
        {
            'x_sea_water_velocity': (('time', 'lat', 'lon'), u_out, {
                'standard_name': 'x_sea_water_velocity', 'units': 'm s-1'}),
            'y_sea_water_velocity': (('time', 'lat', 'lon'), v_out, {
                'standard_name': 'y_sea_water_velocity', 'units': 'm s-1'}),
            'x_wind': (('time', 'lat', 'lon'), u10, {
                'standard_name': 'x_wind', 'units': 'm s-1'}),
            'y_wind': (('time', 'lat', 'lon'), v10, {
                'standard_name': 'y_wind', 'units': 'm s-1'}),
        },
        coords={'time': times, 'lat': lats, 'lon': lons},
        attrs={
            'Conventions': 'CF-1.8',
            'source': 'Regridded from Stagnone v04AE_nowaves (8 MPI, 9d Jul 1-10 2025, '
                      'AE-only blend, waves OFF, D-Morph OFF, uniform roughness, '
                      'Linux/IntelMPI simit-server) + AE blended wind',
            'description': 'Surface currents and 10-m wind on a rectilinear grid '
                           'for OpenDrift, Jul 7-10 2025. No-waves member of the '
                           'Paper 1 ensemble.',
        },
    )
    ds_out['time'].attrs.update({'standard_name': 'time', 'long_name': 'time'})
    ds_out['lat'].attrs.update({'standard_name': 'latitude',
                                'units': 'degrees_north'})
    ds_out['lon'].attrs.update({'standard_name': 'longitude',
                                'units': 'degrees_east'})

    PROC.mkdir(parents=True, exist_ok=True)
    out = PROC / f'{RUN_NAME}_surface_current.nc'
    comp = {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}
    ds_out.to_netcdf(out, encoding={v: comp for v in [
        'x_sea_water_velocity', 'y_sea_water_velocity', 'x_wind', 'y_wind']})
    print(f'-> {out} ({out.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
