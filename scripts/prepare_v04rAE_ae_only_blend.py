"""
Generate AE-only blended wind for v04rAE (sensitivity test #2):
- ERA5 bilinear-interpolated to a fine 0.005 deg (~500 m) grid
- "IDW" of just AE station (collapses to AE value at every fine cell)
- Radius blend: full IDW inside 3 km of lagoon centre, full ERA5 outside 8 km,
  linear in between. Identical structure to the original blended files,
  but Mulino is dropped per the optimal-weights diagnostic
  (data/processed/diag_implied_wind_per_deploy.csv showed AE 0.63 / ERA5 0.34
  / Mulino 0.03).

Output: model/dflowfm_v04rAE/wind_blendedAE_{u10n,v10n}_20250701to20250710.nc
        (same dims/format as wind_blended_*.nc so .ext refers to it the same way)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import RegularGridInterpolator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'model' / 'dflowfm_v04rE5'   # source for ERA5 + station data + restart files
DST = ROOT / 'model' / 'dflowfm_v04rAE'   # destination model dir
DST.mkdir(parents=True, exist_ok=True)

PROC = ROOT / 'data' / 'processed'

# Match notebook 03 settings
LAGOON_CENTER = (12.462, 37.867)
INNER_RADIUS_KM = 3.0
OUTER_RADIUS_KM = 8.0
DX_OUT = 0.005   # ~500 m
DY_OUT = 0.005
AE_LON, AE_LAT = 12.447, 37.890


def from_to_uv(speed, dir_from_deg):
    rad = np.radians(dir_from_deg)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def dist_km(lon1, lat1, lon2, lat2):
    dx = (lon1 - lon2) * 111 * np.cos(np.radians((lat1 + lat2) / 2))
    dy = (lat1 - lat2) * 111
    return np.hypot(dx, dy)


# ---- Load ERA5 raw (the clean version we already prepared for v04rE5) ----
era5_u_path = SRC / 'wind_era5raw_u10n_20250701to20250710.nc'
era5_v_path = SRC / 'wind_era5raw_v10n_20250701to20250710.nc'
ds_eu = xr.open_dataset(era5_u_path)
ds_ev = xr.open_dataset(era5_v_path)
era5_lat = ds_eu.latitude.values
era5_lon = ds_eu.longitude.values
times = pd.to_datetime(ds_eu.time.values)
print(f'ERA5 raw: {len(times)} times, grid {len(era5_lat)}x{len(era5_lon)}')

# ---- AE station ----
ae = pd.read_csv(PROC / 'wind_AE_10min_UTC.csv', index_col=0, parse_dates=True)
ae['u'], ae['v'] = from_to_uv(ae['speed_10m'], ae['dir_deg'])
# Hourly to align with ERA5
ae_h = ae[['u', 'v']].resample('1h').mean()
ae_h = ae_h.reindex(times, method='nearest', tolerance=pd.Timedelta('30min'))
print(f'AE hourly aligned: {ae_h.notna().sum().sum()} / {2*len(ae_h)} valid')

# ---- Output fine grid ----
lat_min, lat_max = era5_lat.min(), era5_lat.max()
lon_min, lon_max = era5_lon.min(), era5_lon.max()
lat_out = np.arange(lat_min, lat_max + DY_OUT/2, DY_OUT)
lon_out = np.arange(lon_min, lon_max + DX_OUT/2, DX_OUT)
LON2, LAT2 = np.meshgrid(lon_out, lat_out)
print(f'Fine output grid: {len(lat_out)} x {len(lon_out)}')

# ---- Blend weight w(dist) ----
d_to_centre = dist_km(LON2, LAT2, *LAGOON_CENTER)
w = np.where(d_to_centre <= INNER_RADIUS_KM, 1.0,
             np.where(d_to_centre >= OUTER_RADIUS_KM, 0.0,
                      (OUTER_RADIUS_KM - d_to_centre) / (OUTER_RADIUS_KM - INNER_RADIUS_KM)))
print(f'Blend weight: {(w == 1).sum()} cells full IDW, {(w == 0).sum()} cells full ERA5, '
      f'{((w > 0) & (w < 1)).sum()} cells transition')


# ---- Per-time blend ----
# ERA5 latitudes are typically descending; we need ascending for RGI
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
    interp_u = RegularGridInterpolator((era5_lat_asc, era5_lon), e5_u,
                                        bounds_error=False, fill_value=None)
    interp_v = RegularGridInterpolator((era5_lat_asc, era5_lon), e5_v,
                                        bounds_error=False, fill_value=None)
    pts = np.column_stack([LAT2.ravel(), LON2.ravel()])
    e5_u_fine = interp_u(pts).reshape(LAT2.shape)
    e5_v_fine = interp_v(pts).reshape(LAT2.shape)

    # AE-only: at every fine cell, the IDW value with one station = AE value
    ae_u_now = ae_h.iloc[it]['u']
    ae_v_now = ae_h.iloc[it]['v']
    if np.isnan(ae_u_now):
        # If AE missing for this hour, fall back to ERA5 everywhere
        u_out[it] = e5_u_fine
        v_out[it] = e5_v_fine
        continue
    idw_u_fine = np.full_like(e5_u_fine, ae_u_now)
    idw_v_fine = np.full_like(e5_v_fine, ae_v_now)

    u_out[it] = (1 - w) * e5_u_fine + w * idw_u_fine
    v_out[it] = (1 - w) * e5_v_fine + w * idw_v_fine

    if (it + 1) % 50 == 0 or it == len(times) - 1:
        print(f'  [{it+1:3d}/{len(times)}] {times[it]}  centre u/v = '
              f'{u_out[it, len(lat_out)//2, len(lon_out)//2]:+.2f}/'
              f'{v_out[it, len(lat_out)//2, len(lon_out)//2]:+.2f} m/s')


# ---- Write CF-compliant NetCDF (matching original blended file structure) ----
def save(name, data, var, std_name, long_name):
    ds = xr.Dataset(
        {var: (('time', 'latitude', 'longitude'), data, {
            'standard_name': std_name, 'units': 'm s-1', 'long_name': long_name,
        })},
        coords={
            'time': ('time', times),
            'latitude': ('latitude', lat_out, {'units': 'degrees_north', 'standard_name': 'latitude'}),
            'longitude': ('longitude', lon_out, {'units': 'degrees_east', 'standard_name': 'longitude'}),
        },
        attrs={
            'Conventions': 'CF-1.8',
            'source': f'AE-only blend (no Mulino) of ERA5 raw + AE station, IDW radius {INNER_RADIUS_KM}-{OUTER_RADIUS_KM} km',
        },
    )
    out = DST / name
    enc = {var: {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}}
    ds.to_netcdf(out, encoding=enc)
    print(f'Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)')


save('wind_blendedAE_u10n_20250701to20250710.nc', u_out, 'u10n', 'eastward_wind', '10 m eastward wind, AE-only blend')
save('wind_blendedAE_v10n_20250701to20250710.nc', v_out, 'v10n', 'northward_wind', '10 m northward wind, AE-only blend')
