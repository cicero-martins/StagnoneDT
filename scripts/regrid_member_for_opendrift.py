"""Regrid any ensemble member's surface currents for OpenDrift.

Replaces the family of near-identical regrid_v04*_for_opendrift.py scripts with
one parameterised version. Uses a manual partition loop with plain xarray, not
dfm_tools, because dfm_tools is absent from simit-server where the map.nc sets
live and where this has to run.

Usage:
    python regrid_member_for_opendrift.py <model_dir_name> <output_tag>
    python regrid_member_for_opendrift.py dflowfm_v04AE v04AE
    python regrid_member_for_opendrift.py dflowfm_v04AE v04AE_dx001 --dx 0.001

The target grid is 0.002 degrees, about 222 m. That value came from the first
regrid script in April 2026 and has never been justified anywhere: no memory, no
document, no commit message. It is a real coarsening, the FM mesh inside the
lagoon having a median nearest-neighbour spacing of 61 m, so OpenDrift sees a
field smoothed by roughly a factor of 3.6 in each direction. --dx exists to test
whether that matters. The temporal analogue was tested in May 2026 and did not
(see memory v04r_outcome_mapinterval_not_bottleneck); the spatial one had not
been.

The wind fields are identical across the v04AE family, so the AE-only blend is
always read from dflowfm_v04AE.

Surface layer is the LAST sigma layer. Verified physically rather than assumed:
mean speed rises monotonically from index 0 to index 9, which is bed friction
below and wind-driven flow above.
"""
import argparse
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
MODEL = ROOT / 'model'
WIND_DIR = MODEL / 'dflowfm_v04AE'

LON_MIN, LON_MAX = 12.00, 12.55
LAT_MIN, LAT_MAX = 37.70, 38.05
DX, DY = 0.002, 0.002
T_MIN, T_MAX = '2025-07-07T00:00:00', '2025-07-10T00:00:00'
LAND_BL_THRESH = -0.05
KDIST_DEG = 0.003
NPART = 8


def build_grid(dx, dy):
    """The regular target grid, as (lons, lats, LON, LAT, tgt).

    The half-step added to the stop keeps the last row and column: arange
    excludes its stop, and with a step of 0.002 whether the maximum survives
    otherwise comes down to floating-point luck rather than intent.
    """
    lons = np.arange(LON_MIN, LON_MAX + dx / 2, dx)
    lats = np.arange(LAT_MIN, LAT_MAX + dy / 2, dy)
    LON, LAT = np.meshgrid(lons, lats)
    return lons, lats, LON, LAT, np.column_stack([LON.ravel(), LAT.ravel()])


def load_partitions(out_dir):
    fx, fy, bl, ucx, ucy, times = [], [], [], [], [], None
    for p in range(NPART):
        f = out_dir / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not f.exists():
            print(f'  partition {p}: MISSING')
            continue
        ds = xr.open_dataset(f)
        lay = [d for d in ds['mesh2d_ucx'].dims if 'lay' in d.lower()]
        u = ds['mesh2d_ucx'].isel({lay[0]: -1}) if lay else ds['mesh2d_ucx']
        v = ds['mesh2d_ucy'].isel({lay[0]: -1}) if lay else ds['mesh2d_ucy']
        u = u.sel(time=slice(T_MIN, T_MAX))
        v = v.sel(time=slice(T_MIN, T_MAX))
        if times is None:
            times = pd.to_datetime(u.time.values)
        fx.append(ds['mesh2d_face_x'].values)
        fy.append(ds['mesh2d_face_y'].values)
        bl.append(ds['mesh2d_flowelem_bl'].values)
        ucx.append(u.values)
        ucy.append(v.values)
        ds.close()
    return (np.concatenate(fx), np.concatenate(fy), np.concatenate(bl),
            np.concatenate(ucx, axis=1), np.concatenate(ucy, axis=1), times)


def main(model_dir, tag, dx=DX, dy=None):
    dy = dx if dy is None else dy
    lons, lats, LON, _, tgt = build_grid(dx, dy)
    out_dir = MODEL / model_dir / 'DFM_OUTPUT_Stagnone_dxy01_15m'
    print(f'=== {tag}  ({model_dir}) ===')
    print(f'  grid {dx} deg (~{dx * 111000:.0f} m), '
          f'{len(lons)} x {len(lats)} = {len(tgt)} cells')
    fx, fy, bl, ucx, ucy, times = load_partitions(out_dir)
    print(f'  {len(fx)} faces, {len(times)} steps, {times[0]} .. {times[-1]}')

    water = bl < LAND_BL_THRESH
    src = np.column_stack([fx[water], fy[water]])
    dist, _ = cKDTree(src).query(tgt)
    far = dist > KDIST_DEG
    print(f'  water faces {water.sum()} / {len(fx)}; '
          f'target cells with source {(~far).sum()} / {len(dist)}')

    n = len(times)
    u_out = np.full((n, len(lats), len(lons)), np.nan, dtype=np.float32)
    v_out = np.full_like(u_out, np.nan)
    for it in range(n):
        uf = griddata(src, ucx[it][water], tgt, method='linear')
        vf = griddata(src, ucy[it][water], tgt, method='linear')
        uf[far] = np.nan
        vf[far] = np.nan
        u_out[it] = uf.reshape(LON.shape)
        v_out[it] = vf.reshape(LON.shape)
        if (it + 1) % 40 == 0 or it == n - 1:
            print(f'  [{it+1}/{n}] {times[it]}')

    wu = xr.open_dataset(WIND_DIR / 'wind_blendedAE_u10n_20250701to20250710.nc')
    wv = xr.open_dataset(WIND_DIR / 'wind_blendedAE_v10n_20250701to20250710.nc')
    u10 = wu['u10n'].interp(time=times, latitude=lats,
                            longitude=lons).values.astype(np.float32)
    v10 = wv['v10n'].interp(time=times, latitude=lats,
                            longitude=lons).values.astype(np.float32)
    wu.close()
    wv.close()

    ds_out = xr.Dataset(
        {'x_sea_water_velocity': (('time', 'lat', 'lon'), u_out,
                                  {'standard_name': 'x_sea_water_velocity',
                                   'units': 'm s-1'}),
         'y_sea_water_velocity': (('time', 'lat', 'lon'), v_out,
                                  {'standard_name': 'y_sea_water_velocity',
                                   'units': 'm s-1'}),
         'x_wind': (('time', 'lat', 'lon'), u10,
                    {'standard_name': 'x_wind', 'units': 'm s-1'}),
         'y_wind': (('time', 'lat', 'lon'), v10,
                    {'standard_name': 'y_wind', 'units': 'm s-1'})},
        coords={'time': times, 'lat': lats, 'lon': lons},
        attrs={'Conventions': 'CF-1.8',
               'source': f'Regridded from {model_dir}, surface sigma layer, '
                         f'plus AE blended wind',
               'grid_resolution_deg': dx})
    ds_out['time'].attrs.update({'standard_name': 'time'})
    ds_out['lat'].attrs.update({'standard_name': 'latitude',
                                'units': 'degrees_north'})
    ds_out['lon'].attrs.update({'standard_name': 'longitude',
                                'units': 'degrees_east'})
    PROC.mkdir(parents=True, exist_ok=True)
    out = PROC / f'{tag}_surface_current.nc'
    comp = {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}
    ds_out.to_netcdf(out, encoding={v: comp for v in ds_out.data_vars})
    print(f'  -> {out} ({out.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('model_dir')
    ap.add_argument('tag')
    ap.add_argument('--dx', type=float, default=DX,
                    help=f'target grid spacing in degrees (default {DX})')
    a = ap.parse_args()
    main(a.model_dir, a.tag, a.dx)
