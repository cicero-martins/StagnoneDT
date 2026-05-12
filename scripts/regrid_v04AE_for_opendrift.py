"""
Regrid v04AE surface currents (full 9-day Jul 1-10 with AE-only blend +
D-Morph active + 8 MPI + ComInterval=3600s SWAN) onto a rectilinear lat/lon
grid for OpenDrift.

Identical structure to regrid_v04rAE_for_opendrift.py, except:
  - reads from model/dflowfm_v04AE/DFM_OUTPUT_*
  - time slice clipped to the drifter campaign window: Jul 7 -> Jul 10
    (the deploys are all on Jul 8; +/-1 day buffer for OpenDrift readers)
  - output: data/processed/v04AE_surface_current.nc

Compared with v04rAE:
  - same AE-only wind blend
  - full spinup from Jul 1 (vs Jul 8 restart in v04rAE)
  - D-Morph ran for 7 days before drifter window (bathy has evolved)
  - mapInterval likely 1800s (vs 600s in v04rAE) — coarser temporal sampling

Run:
    python scripts/regrid_v04AE_for_opendrift.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import dfm_tools as dfmt
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
V04AE = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
OUT = ROOT / 'data' / 'processed' / 'v04AE_surface_current.nc'

# Target grid (rectilinear, covers full FM domain with ~200 m cells)
LON_MIN, LON_MAX = 12.00, 12.55
LAT_MIN, LAT_MAX = 37.70, 38.05
DX = 0.002
DY = 0.002

# Slice around the drifter campaign (deploys are all on Jul 8 between 07:00-12:00)
T_MIN = '2025-07-07T00:00:00'
T_MAX = '2025-07-10T00:00:00'

LAND_BL_THRESH = -0.05
KDIST_DEG = 0.003


def main():
    map_pattern = str(V04AE / 'Stagnone_dxy01_15m_0*_map.nc')
    print(f'Opening partitioned map.nc: {map_pattern}')
    ds = dfmt.open_partitioned_dataset(map_pattern)
    print(f'  Partitions merged. ucx dims: {dict(ds["mesh2d_ucx"].sizes)}')

    lay_dim = 'mesh2d_nLayers'
    if lay_dim not in ds['mesh2d_ucx'].dims:
        lay_dim = [d for d in ds['mesh2d_ucx'].dims if 'layer' in d.lower() or 'lay' in d.lower()][0]
        print(f'  Using layer dim: {lay_dim}')
    ucx = ds['mesh2d_ucx'].isel({lay_dim: -1})
    ucy = ds['mesh2d_ucy'].isel({lay_dim: -1})
    print(f'Surface ucx full: time {ucx.time.values[0]} .. {ucx.time.values[-1]}')

    ucx = ucx.sel(time=slice(T_MIN, T_MAX))
    ucy = ucy.sel(time=slice(T_MIN, T_MAX))
    times = pd.to_datetime(ucx.time.values)
    print(f'Subset time:  {times[0]} .. {times[-1]} ({len(times)} snapshots)')

    fx = np.asarray(ds.grid.face_x)
    fy = np.asarray(ds.grid.face_y)
    # NOTE: mesh2d_flowelem_bl is the static bedlevel. With D-Morph active the
    # bed has changed, but for the land mask we use the static value because
    # the OpenDrift target grid is fixed and we want a consistent mask.
    bl = np.asarray(ds['mesh2d_flowelem_bl'].values).flatten()
    water_mask = bl < LAND_BL_THRESH
    fx_w = fx[water_mask]
    fy_w = fy[water_mask]
    print(f'Source faces water (bl<{LAND_BL_THRESH} m): {water_mask.sum()} / {len(fx)}')

    lons = np.arange(LON_MIN, LON_MAX + DX/2, DX)
    lats = np.arange(LAT_MIN, LAT_MAX + DY/2, DY)
    LON, LAT = np.meshgrid(lons, lats)
    print(f'Target grid: {len(lons)} x {len(lats)} = {len(lons)*len(lats)} cells')

    tree_w = cKDTree(np.column_stack([fx_w, fy_w]))
    dists_w, _ = tree_w.query(np.column_stack([LON.ravel(), LAT.ravel()]))
    mask_far = dists_w > KDIST_DEG
    print(f'Target cells with valid water source: {(~mask_far).sum()} / {len(dists_w)}')

    ntime = len(times)
    u_out = np.full((ntime, len(lats), len(lons)), np.nan, dtype=np.float32)
    v_out = np.full((ntime, len(lats), len(lons)), np.nan, dtype=np.float32)
    tgt_pts = np.column_stack([LON.ravel(), LAT.ravel()])

    for it in range(ntime):
        u_face = ucx.isel(time=it).values[water_mask]
        v_face = ucy.isel(time=it).values[water_mask]
        u_flat = griddata(np.column_stack([fx_w, fy_w]), u_face, tgt_pts, method='linear')
        v_flat = griddata(np.column_stack([fx_w, fy_w]), v_face, tgt_pts, method='linear')
        u_flat[mask_far] = np.nan
        v_flat[mask_far] = np.nan
        u_out[it] = u_flat.reshape(LON.shape)
        v_out[it] = v_flat.reshape(LON.shape)
        if (it + 1) % 25 == 0 or it == ntime - 1:
            print(f'  [{it+1:3d}/{ntime}] {times[it]}  '
                  f'u_abs_max={np.nanmax(np.abs(u_flat)):.3f} m/s')

    # Same AE-only blended wind used by v04AE FM forcing.
    print('\nAdding wind (u10, v10) from AE-only blend (consistent with v04AE FM forcing)...')
    wind_u_path = ROOT / 'model' / 'dflowfm_v04AE' / 'wind_blendedAE_u10n_20250701to20250710.nc'
    wind_v_path = ROOT / 'model' / 'dflowfm_v04AE' / 'wind_blendedAE_v10n_20250701to20250710.nc'
    ds_u = xr.open_dataset(wind_u_path)
    ds_v = xr.open_dataset(wind_v_path)
    u10 = ds_u['u10n'].interp(time=times, latitude=lats, longitude=lons, method='linear').values.astype(np.float32)
    v10 = ds_v['v10n'].interp(time=times, latitude=lats, longitude=lons, method='linear').values.astype(np.float32)
    print(f'  u10 range: {np.nanmin(u10):.2f} .. {np.nanmax(u10):.2f} m/s')
    print(f'  v10 range: {np.nanmin(v10):.2f} .. {np.nanmax(v10):.2f} m/s')

    ds_out = xr.Dataset(
        {
            'x_sea_water_velocity': (('time', 'lat', 'lon'), u_out, {
                'standard_name': 'x_sea_water_velocity', 'units': 'm s-1',
                'long_name': 'Eastward surface current'}),
            'y_sea_water_velocity': (('time', 'lat', 'lon'), v_out, {
                'standard_name': 'y_sea_water_velocity', 'units': 'm s-1',
                'long_name': 'Northward surface current'}),
            'x_wind': (('time', 'lat', 'lon'), u10, {
                'standard_name': 'x_wind', 'units': 'm s-1',
                'long_name': 'Eastward wind at 10 m'}),
            'y_wind': (('time', 'lat', 'lon'), v10, {
                'standard_name': 'y_wind', 'units': 'm s-1',
                'long_name': 'Northward wind at 10 m'}),
        },
        coords={
            'time': ('time', times),
            'lat': ('lat', lats, {'standard_name': 'latitude', 'units': 'degrees_north'}),
            'lon': ('lon', lons, {'standard_name': 'longitude', 'units': 'degrees_east'}),
        },
        attrs={
            'Conventions': 'CF-1.8',
            'source': 'Regridded from Stagnone v04AE (8 MPI, full 9d Jul 1-10, AE-only blend, D-Morph ON, ComInterval=3600s SWAN) + AE blended wind',
            'description': 'Surface currents + 10-m wind, rectilinear grid for OpenDrift, Jul 7-10 2025',
        },
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    comp = {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}
    encoding = {v: comp for v in ['x_sea_water_velocity', 'y_sea_water_velocity', 'x_wind', 'y_wind']}
    ds_out.to_netcdf(OUT, encoding=encoding)
    print(f'\nWrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
