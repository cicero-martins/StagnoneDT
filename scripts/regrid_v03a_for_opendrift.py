"""
Regrid v03a surface currents (from 4 MPI partitions) onto a rectilinear
lat/lon grid, CF-compliant, ready for OpenDrift's reader_netCDF_CF_generic.

Inputs:
  - model/dflowfm_v03a/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0*_map.nc  (surface currents)
  - model/dflowfm_v03a/wind_blended_u10n_20250701to20250710.nc                       (blended wind u)
  - model/dflowfm_v03a/wind_blended_v10n_20250701to20250710.nc                       (blended wind v)
Output:
  - data/processed/v03a_surface_current.nc   (x_sea_water_velocity, y_sea_water_velocity, x_wind, y_wind)

~433 timesteps × regular grid ~0.001° (≈100 m) over lagoon+offshore bbox.
Result file is ~100-200 MB.

Run:
    python scripts/regrid_v03a_for_opendrift.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import dfm_tools as dfmt
from scipy.interpolate import griddata

ROOT = Path(r'F:/StagnoneDT')
V03A = ROOT / 'model' / 'dflowfm_v03a' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
OUT = ROOT / 'data' / 'processed' / 'v03a_surface_current.nc'

# Target grid (rectilinear, covers full FM domain with ~200 m cells)
LON_MIN, LON_MAX = 12.00, 12.55
LAT_MIN, LAT_MAX = 37.70, 38.05
DX = 0.002      # ~180 m at lat 37.87
DY = 0.002      # ~220 m

# Temporal subsampling (optional — huge NetCDF if we keep all 433 snapshots)
# Campaign is Jul 8-9 only, so focus there to keep the file small
T_MIN = '2025-07-07T12:00:00'
T_MAX = '2025-07-10T00:00:00'


def main():
    print(f'Opening partitioned map.nc...')
    ds = dfmt.open_partitioned_dataset(str(V03A / 'Stagnone_dxy01_15m_0*_map.nc'))

    # Surface slice (top sigma = last layer)
    lay_dim = 'mesh2d_nLayers'
    ucx = ds['mesh2d_ucx'].isel({lay_dim: -1})
    ucy = ds['mesh2d_ucy'].isel({lay_dim: -1})
    print(f'Surface ucx shape: {ucx.shape}  time range {ucx.time.values[0]} .. {ucx.time.values[-1]}')

    # Subset in time
    ucx = ucx.sel(time=slice(T_MIN, T_MAX))
    ucy = ucy.sel(time=slice(T_MIN, T_MAX))
    times = pd.to_datetime(ucx.time.values)
    print(f'Subset time: {times[0]} .. {times[-1]} ({len(times)} snapshots)')

    # Face coordinates
    fx = np.asarray(ds.grid.face_x)
    fy = np.asarray(ds.grid.face_y)
    print(f'Source faces: {len(fx)}')

    # Build target grid
    lons = np.arange(LON_MIN, LON_MAX + DX/2, DX)
    lats = np.arange(LAT_MIN, LAT_MAX + DY/2, DY)
    LON, LAT = np.meshgrid(lons, lats)
    print(f'Target grid: {len(lons)} x {len(lats)} = {len(lons)*len(lats)} cells')

    # Mask: cells inside the FM mesh convex hull (rough — drop points >2 km from any face)
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([fx, fy]))
    dists, _ = tree.query(np.column_stack([LON.ravel(), LAT.ravel()]))
    # Drop cells farther than ~500 m from any face (keep only where we have data)
    mask_far = dists > 0.005
    print(f'Target cells inside domain: {(~mask_far).sum()} / {len(dists)}')

    # Interpolate each timestep
    ntime = len(times)
    u_out = np.full((ntime, len(lats), len(lons)), np.nan, dtype=np.float32)
    v_out = np.full((ntime, len(lats), len(lons)), np.nan, dtype=np.float32)
    tgt_pts = np.column_stack([LON.ravel(), LAT.ravel()])

    for it in range(ntime):
        u_face = ucx.isel(time=it).values
        v_face = ucy.isel(time=it).values
        # linear interpolation; cells far from any face stay NaN (we set them explicitly too)
        u_flat = griddata(np.column_stack([fx, fy]), u_face, tgt_pts, method='linear')
        v_flat = griddata(np.column_stack([fx, fy]), v_face, tgt_pts, method='linear')
        u_flat[mask_far] = np.nan
        v_flat[mask_far] = np.nan
        u_out[it] = u_flat.reshape(LON.shape)
        v_out[it] = v_flat.reshape(LON.shape)
        if (it + 1) % 20 == 0 or it == ntime - 1:
            print(f'  [{it+1:3d}/{ntime}] {times[it]}  u_abs_max={np.nanmax(np.abs(u_flat)):.3f} m/s')

    # --- Add wind (u10, v10) from blended wind file, interpolated to same grid+time ---
    print('\nAdding wind (u10, v10) from blended wind file...')
    wind_u_path = ROOT / 'model' / 'dflowfm_v03a' / 'wind_blended_u10n_20250701to20250710.nc'
    wind_v_path = ROOT / 'model' / 'dflowfm_v03a' / 'wind_blended_v10n_20250701to20250710.nc'
    ds_u = xr.open_dataset(wind_u_path)
    ds_v = xr.open_dataset(wind_v_path)
    # Interpolate wind to the (time, lat, lon) grid — wind is already on a rectilinear grid,
    # so xarray's native interp suffices.
    u10 = ds_u['u10n'].interp(time=times, latitude=lats, longitude=lons, method='linear').values.astype(np.float32)
    v10 = ds_v['v10n'].interp(time=times, latitude=lats, longitude=lons, method='linear').values.astype(np.float32)
    print(f'  u10 range: {np.nanmin(u10):.2f} .. {np.nanmax(u10):.2f} m/s')
    print(f'  v10 range: {np.nanmin(v10):.2f} .. {np.nanmax(v10):.2f} m/s')

    # Write CF-compliant netCDF
    ds_out = xr.Dataset(
        {
            'x_sea_water_velocity': (('time', 'lat', 'lon'), u_out, {
                'standard_name': 'x_sea_water_velocity',
                'units': 'm s-1',
                'long_name': 'Eastward surface current',
            }),
            'y_sea_water_velocity': (('time', 'lat', 'lon'), v_out, {
                'standard_name': 'y_sea_water_velocity',
                'units': 'm s-1',
                'long_name': 'Northward surface current',
            }),
            'x_wind': (('time', 'lat', 'lon'), u10, {
                'standard_name': 'x_wind',
                'units': 'm s-1',
                'long_name': 'Eastward wind at 10 m',
            }),
            'y_wind': (('time', 'lat', 'lon'), v10, {
                'standard_name': 'y_wind',
                'units': 'm s-1',
                'long_name': 'Northward wind at 10 m',
            }),
        },
        coords={
            'time': ('time', times),
            'lat': ('lat', lats, {'standard_name': 'latitude', 'units': 'degrees_north'}),
            'lon': ('lon', lons, {'standard_name': 'longitude', 'units': 'degrees_east'}),
        },
        attrs={
            'Conventions': 'CF-1.8',
            'source': 'Regridded from Stagnone v03a (4 MPI partitions) + blended wind',
            'description': 'Surface currents + 10-m wind, rectilinear grid for OpenDrift',
        },
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    comp = {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}
    encoding = {v: comp for v in ['x_sea_water_velocity', 'y_sea_water_velocity', 'x_wind', 'y_wind']}
    ds_out.to_netcdf(OUT, encoding=encoding)
    print(f'\nWrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
