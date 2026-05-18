"""
Build wind_blendedAE_{u10n,v10n}_20250701to20250713.nc for v04AE continuation
Jul 10 -> Jul 12 run, using the NEW AE in-situ data from dati_2025-26.

Differs from prepare_v04rAE_ae_only_blend.py by:
  - Reads AE u10/v10 directly from data/processed/insitu_2025-26/AE_wind_UTC.csv
    (no speed/dir -> uv conversion needed; xlsx already had components)
  - Window Jul 1-13 (12 days) instead of Jul 1-10 (9d)
  - Source ERA5: model/dflowfm_v04AE_d10d12/wind_era5raw_*_20250701to20250713.nc

Same radius-blend geometry:
  - Inside 3 km of lagoon centre: AE value only
  - Beyond 8 km: ERA5 only
  - Linear taper in between
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import RegularGridInterpolator

ROOT = Path(__file__).resolve().parents[1]
DST = ROOT / 'model' / 'dflowfm_v04AE_d10d12'
DST.mkdir(parents=True, exist_ok=True)

# Same blend params as v04rAE
LAGOON_CENTER = (12.462, 37.867)
INNER_RADIUS_KM = 3.0
OUTER_RADIUS_KM = 8.0
DX_OUT = 0.005   # ~500 m fine grid
DY_OUT = 0.005
AE_LON, AE_LAT = 12.447, 37.890


def dist_km(lon1, lat1, lon2, lat2):
    dx = (lon1 - lon2) * 111 * np.cos(np.radians((lat1 + lat2) / 2))
    dy = (lat1 - lat2) * 111
    return np.hypot(dx, dy)


def main():
    era5_u_path = DST / 'wind_era5raw_u10n_20250701to20250713.nc'
    era5_v_path = DST / 'wind_era5raw_v10n_20250701to20250713.nc'
    for p in (era5_u_path, era5_v_path):
        if not p.exists():
            raise FileNotFoundError(
                f'ERA5 raw not found at {p}. '
                'Run scripts/download_era5_v04AE_d10d12.py first.')

    ds_eu = xr.open_dataset(era5_u_path)
    ds_ev = xr.open_dataset(era5_v_path)
    era5_lat = ds_eu.latitude.values
    era5_lon = ds_eu.longitude.values
    times = pd.to_datetime(ds_eu.time.values)
    print(f'ERA5 raw: {len(times)} hourly times, grid {len(era5_lat)}x{len(era5_lon)}')
    print(f'   {times[0]} -> {times[-1]}')

    # AE station (new in-situ data, already in UTC, u10/v10 components)
    ae_csv = ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'AE_wind_UTC.csv'
    ae = pd.read_csv(ae_csv, index_col=0, parse_dates=True)
    print(f'AE in-situ: {len(ae)} 10-min samples, {ae.index.min()} -> {ae.index.max()}')

    # Resample 10-min -> hourly (mean), align with ERA5 times
    ae_h = ae[['u10', 'v10']].resample('1h').mean()
    ae_h = ae_h.reindex(times, method='nearest', tolerance=pd.Timedelta('30min'))
    valid = ae_h.notna().all(axis=1).sum()
    print(f'AE aligned to ERA5 hourly: {valid}/{len(ae_h)} valid points')

    # Output fine grid (covers full ERA5 domain)
    lat_min, lat_max = era5_lat.min(), era5_lat.max()
    lon_min, lon_max = era5_lon.min(), era5_lon.max()
    lat_out = np.arange(lat_min, lat_max + DY_OUT / 2, DY_OUT)
    lon_out = np.arange(lon_min, lon_max + DX_OUT / 2, DX_OUT)
    LON2, LAT2 = np.meshgrid(lon_out, lat_out)
    print(f'Fine output grid: {len(lat_out)} x {len(lon_out)}')

    # Blend weight w(distance from lagoon centre)
    d = dist_km(LON2, LAT2, *LAGOON_CENTER)
    w = np.where(d <= INNER_RADIUS_KM, 1.0,
        np.where(d >= OUTER_RADIUS_KM, 0.0,
                 (OUTER_RADIUS_KM - d) / (OUTER_RADIUS_KM - INNER_RADIUS_KM)))
    print(f'Blend weights: {(w == 1).sum()} full-AE cells, '
          f'{(w == 0).sum()} full-ERA5 cells, '
          f'{((w > 0) & (w < 1)).sum()} transition cells')

    # ERA5 latitude orientation (descending typical -> flip for RGI)
    if era5_lat[0] > era5_lat[-1]:
        era5_lat_asc = era5_lat[::-1]
        flip_lat = True
    else:
        era5_lat_asc = era5_lat
        flip_lat = False

    u_out = np.full((len(times), len(lat_out), len(lon_out)), np.nan, dtype=np.float32)
    v_out = np.full((len(times), len(lat_out), len(lon_out)), np.nan, dtype=np.float32)

    for it in range(len(times)):
        e5_u = ds_eu.u10n.isel(time=it).values
        e5_v = ds_ev.v10n.isel(time=it).values
        if flip_lat:
            e5_u = e5_u[::-1]
            e5_v = e5_v[::-1]
        interp_u = RegularGridInterpolator(
            (era5_lat_asc, era5_lon), e5_u,
            bounds_error=False, fill_value=None)
        interp_v = RegularGridInterpolator(
            (era5_lat_asc, era5_lon), e5_v,
            bounds_error=False, fill_value=None)
        pts = np.column_stack([LAT2.ravel(), LON2.ravel()])
        e5_u_fine = interp_u(pts).reshape(LAT2.shape)
        e5_v_fine = interp_v(pts).reshape(LAT2.shape)

        ae_u_now = ae_h.iloc[it]['u10']
        ae_v_now = ae_h.iloc[it]['v10']
        if np.isnan(ae_u_now):
            # If AE missing this hour, fall back to ERA5 everywhere
            u_out[it] = e5_u_fine
            v_out[it] = e5_v_fine
            continue
        u_out[it] = (1 - w) * e5_u_fine + w * ae_u_now
        v_out[it] = (1 - w) * e5_v_fine + w * ae_v_now

        if (it + 1) % 24 == 0 or it == len(times) - 1:
            cl = len(lat_out) // 2
            cn = len(lon_out) // 2
            print(f'  [{it+1:3d}/{len(times)}] {times[it]} '
                  f'centre u/v = {u_out[it, cl, cn]:+.2f}/{v_out[it, cl, cn]:+.2f} m/s')

    # Write CF NetCDF
    def save(name, data, var, std_name, long_name):
        ds = xr.Dataset(
            {var: (('time', 'latitude', 'longitude'), data, {
                'standard_name': std_name, 'units': 'm s-1', 'long_name': long_name,
            })},
            coords={
                'time': ('time', times),
                'latitude': ('latitude', lat_out,
                             {'units': 'degrees_north', 'standard_name': 'latitude'}),
                'longitude': ('longitude', lon_out,
                              {'units': 'degrees_east', 'standard_name': 'longitude'}),
            },
            attrs={
                'Conventions': 'CF-1.8',
                'source': (f'AE-only blend of ERA5 raw + AE in-situ (dati_2025-26), '
                           f'IDW radius {INNER_RADIUS_KM}-{OUTER_RADIUS_KM} km'),
                'history': 'Created by scripts/prepare_v04AE_d10d12_ae_blend.py',
            },
        )
        out = DST / name
        enc = {var: {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}}
        ds.to_netcdf(out, encoding=enc)
        print(f'Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)')

    save('wind_blendedAE_u10n_20250701to20250713.nc', u_out, 'u10n',
         'eastward_wind', '10 m eastward wind, AE-only blend (Jul 1-13 2025)')
    save('wind_blendedAE_v10n_20250701to20250713.nc', v_out, 'v10n',
         'northward_wind', '10 m northward wind, AE-only blend (Jul 1-13 2025)')


if __name__ == '__main__':
    main()
