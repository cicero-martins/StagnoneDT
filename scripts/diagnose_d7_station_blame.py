"""
Pinpoint which in-situ station is responsible for the blended-wind direction
bias at D7. Mulino is ~0.93 km from D7 release, AE is ~3.1 km. With IDW(p=2)
inside inner_radius=3 km, the blended wind at D7 ~= 92% Mulino + 8% AE
(ERA5 contribution = 0 inside inner radius).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'

T0 = pd.Timestamp('2025-07-08 17:00:00')
T1 = pd.Timestamp('2025-07-08 19:00:00')
D7_LON = 12.4778
D7_LAT = 37.8757

STATIONS = {
    'AE':     {'lon': 12.447, 'lat': 37.890},
    'Mulino': {'lon': 12.482, 'lat': 37.868},
}
LAGOON_CENTER = (12.462, 37.867)
INNER_RADIUS_KM = 3.0
OUTER_RADIUS_KM = 8.0


def dir_speed_to_uv(speed, direction_deg_from):
    rad = np.radians(direction_deg_from)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def uv_to_speed_dir(u, v):
    speed = np.hypot(u, v)
    dir_to = np.degrees(np.arctan2(u, v)) % 360
    return speed, dir_to


def dist_km(lon1, lat1, lon2, lat2):
    dx = (lon1 - lon2) * 111 * np.cos(np.radians((lat1 + lat2) / 2))
    dy = (lat1 - lat2) * 111
    return np.hypot(dx, dy)


# Station distances and IDW weights at D7
d_d7_to_ae = dist_km(D7_LON, D7_LAT, STATIONS['AE']['lon'], STATIONS['AE']['lat'])
d_d7_to_mul = dist_km(D7_LON, D7_LAT, STATIONS['Mulino']['lon'], STATIONS['Mulino']['lat'])
d_d7_to_center = dist_km(D7_LON, D7_LAT, LAGOON_CENTER[0], LAGOON_CENTER[1])
print(f'D7 release at ({D7_LON}, {D7_LAT})')
print(f'  Distance to AE     : {d_d7_to_ae:.2f} km')
print(f'  Distance to Mulino : {d_d7_to_mul:.2f} km')
print(f'  Distance to lagoon center: {d_d7_to_center:.2f} km')
print(f'  Inner-radius rule  : {d_d7_to_center:.2f} < {INNER_RADIUS_KM} -> w_IDW = 1.00 (full IDW, NO ERA5)')

inv_sq_ae = 1.0 / d_d7_to_ae ** 2
inv_sq_mul = 1.0 / d_d7_to_mul ** 2
total = inv_sq_ae + inv_sq_mul
w_ae = inv_sq_ae / total
w_mul = inv_sq_mul / total
print(f'  IDW(p=2) weights @ D7: Mulino = {w_mul:.3f}, AE = {w_ae:.3f}')


# Station data during D7 window
ae = pd.read_csv(PROC / 'wind_AE_10min_UTC.csv', index_col=0, parse_dates=True)
mul = pd.read_csv(PROC / 'wind_Mulino_10min_UTC.csv', index_col=0, parse_dates=True)
ae_d7 = ae.loc[T0:T1]
mul_d7 = mul.loc[T0:T1]

ae_u, ae_v = dir_speed_to_uv(ae_d7.speed_10m.values, ae_d7.dir_deg.values)
mul_u, mul_v = dir_speed_to_uv(mul_d7.speed_10m.values, mul_d7.dir_deg.values)

ae_mean_u, ae_mean_v = ae_u.mean(), ae_v.mean()
mul_mean_u, mul_mean_v = mul_u.mean(), mul_v.mean()
ae_spd, ae_dir_to = uv_to_speed_dir(ae_mean_u, ae_mean_v)
mul_spd, mul_dir_to = uv_to_speed_dir(mul_mean_u, mul_mean_v)
print(f'\nAE     mean during D7: u={ae_mean_u:.2f}, v={ae_mean_v:.2f} m/s -> speed {ae_spd:.2f}, TO {ae_dir_to:.0f} deg')
print(f'Mulino mean during D7: u={mul_mean_u:.2f}, v={mul_mean_v:.2f} m/s -> speed {mul_spd:.2f}, TO {mul_dir_to:.0f} deg')


# ERA5 raw at D7 release
era5_u_path = ROOT / 'model' / 'dflowfm_v04r' / 'era5_u10n_20250701to20250710_ERA5.nc'
era5_v_path = ROOT / 'model' / 'dflowfm_v04r' / 'era5_v10n_20250701to20250710_ERA5.nc'
ds_eu = xr.open_dataset(era5_u_path)
ds_ev = xr.open_dataset(era5_v_path)
sub_eu = ds_eu.u10n.sel(time=slice(T0, T1)).interp(latitude=D7_LAT, longitude=D7_LON)
sub_ev = ds_ev.v10n.sel(time=slice(T0, T1)).interp(latitude=D7_LAT, longitude=D7_LON)
era5_mean_u, era5_mean_v = float(sub_eu.values.mean()), float(sub_ev.values.mean())
era5_spd, era5_dir_to = uv_to_speed_dir(era5_mean_u, era5_mean_v)
print(f'ERA5 raw @ D7        : u={era5_mean_u:.2f}, v={era5_mean_v:.2f} m/s -> speed {era5_spd:.2f}, TO {era5_dir_to:.0f} deg')


# IDW prediction at D7 (no ERA5 because inside inner radius)
idw_u = w_mul * mul_mean_u + w_ae * ae_mean_u
idw_v = w_mul * mul_mean_v + w_ae * ae_mean_v
idw_spd, idw_dir_to = uv_to_speed_dir(idw_u, idw_v)
print(f'\nIDW(0.92*Mulino + 0.08*AE): u={idw_u:.2f}, v={idw_v:.2f} -> speed {idw_spd:.2f}, TO {idw_dir_to:.0f} deg')

# Read blended at D7 (from regridded v04r as ground truth of what FM saw)
ds_uc = xr.open_dataset(PROC / 'v04r_surface_current.nc')
sub = ds_uc.sel(time=slice(T0, T1))
ix = int(np.argmin(np.abs(ds_uc.lon.values - D7_LON)))
iy = int(np.argmin(np.abs(ds_uc.lat.values - D7_LAT)))
blend_u = float(sub['x_wind'].isel(lat=iy, lon=ix).mean().values)
blend_v = float(sub['y_wind'].isel(lat=iy, lon=ix).mean().values)
blend_spd, blend_dir_to = uv_to_speed_dir(blend_u, blend_v)
print(f'Blended wind @ D7 (regrid): u={blend_u:.2f}, v={blend_v:.2f} -> speed {blend_spd:.2f}, TO {blend_dir_to:.0f} deg')


# Observed drifter mean drift
tracks = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
d7 = tracks[tracks['deploy'] == 7].sort_values(['source', 'time']).reset_index(drop=True)
us, vs = [], []
for src, g in d7.groupby('source'):
    g = g.sort_values('time').reset_index(drop=True)
    dt_s = g['time'].diff().dt.total_seconds().values
    cos_lat = np.cos(np.radians(g['lat'].mean()))
    us.extend((g['lon'].diff().values * 111000 * cos_lat / dt_s).tolist())
    vs.extend((g['lat'].diff().values * 111000 / dt_s).tolist())
obs_mean_u = np.nanmean(us)
obs_mean_v = np.nanmean(vs)
obs_spd, obs_dir_to = uv_to_speed_dir(obs_mean_u, obs_mean_v)
print(f'\nObs D7 drift mean: u={obs_mean_u:.3f}, v={obs_mean_v:.3f} -> speed {obs_spd:.3f}, TO {obs_dir_to:.0f} deg')


# === Plot the smoking gun map ===
fig, (ax_map, ax_wind_ts) = plt.subplots(1, 2, figsize=(15, 8))

# Lagoon outline + station markers
# Use the v04 land mask we already have
land_ds = xr.open_dataset(PROC / 'v04_land_mask_50m.nc')
ax_map.pcolormesh(land_ds.lon, land_ds.lat,
                  np.where(land_ds.land == 1, 1.0, np.nan),
                  cmap='Greys', vmin=0, vmax=2, alpha=0.4, zorder=0)

# Lagoon center, inner/outer radius circles
theta = np.linspace(0, 2 * np.pi, 200)
for r, label, ls in [(INNER_RADIUS_KM, '3 km inner (full IDW)', '--'),
                      (OUTER_RADIUS_KM, '8 km outer (full ERA5)', ':')]:
    dlat = r / 111
    dlon = r / (111 * np.cos(np.radians(LAGOON_CENTER[1])))
    ax_map.plot(LAGOON_CENTER[0] + dlon * np.cos(theta),
                LAGOON_CENTER[1] + dlat * np.sin(theta),
                ls, color='dimgrey', lw=1, label=label, alpha=0.7)
ax_map.scatter(*LAGOON_CENTER, marker='+', color='dimgrey', s=120, label='lagoon centre')

# Stations + their wind vectors (mean over D7 window)
def draw_arrow(ax, lon0, lat0, u, v, color, label, arrow_scale=0.0008, lw=2.5):
    dx = u * arrow_scale
    dy = v * arrow_scale
    ax.annotate('', xy=(lon0 + dx, lat0 + dy), xytext=(lon0, lat0),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw), zorder=6)
    ax.text(lon0 + dx, lat0 + dy, f' {label}', color=color, fontsize=9, va='center', zorder=7)

ax_map.scatter(STATIONS['AE']['lon'], STATIONS['AE']['lat'], marker='^', s=180,
               color='deepskyblue', edgecolor='k', linewidth=1.0, label='AE station', zorder=5)
draw_arrow(ax_map, STATIONS['AE']['lon'], STATIONS['AE']['lat'], ae_mean_u, ae_mean_v,
           'deepskyblue', f'AE {ae_spd:.1f} m/s\nTO {ae_dir_to:.0f} deg')

ax_map.scatter(STATIONS['Mulino']['lon'], STATIONS['Mulino']['lat'], marker='^', s=180,
               color='steelblue', edgecolor='k', linewidth=1.0, label='Mulino station', zorder=5)
draw_arrow(ax_map, STATIONS['Mulino']['lon'], STATIONS['Mulino']['lat'], mul_mean_u, mul_mean_v,
           'steelblue', f'Mulino {mul_spd:.1f} m/s\nTO {mul_dir_to:.0f} deg', lw=3.0)

# D7 release: ERA5 raw + obs drift + blended wind
ax_map.scatter(D7_LON, D7_LAT, marker='o', s=200, color='red', edgecolor='k', linewidth=1.0,
               label='D7 release', zorder=5)
draw_arrow(ax_map, D7_LON, D7_LAT, era5_mean_u, era5_mean_v,
           'darkgreen', f'ERA5 raw {era5_spd:.1f} m/s\nTO {era5_dir_to:.0f} deg')
draw_arrow(ax_map, D7_LON, D7_LAT, blend_u, blend_v,
           'darkorange', f'Blended {blend_spd:.1f} m/s\nTO {blend_dir_to:.0f} deg', lw=3.0)
# Obs drift scaled (it's tiny vs wind magnitudes)
draw_arrow(ax_map, D7_LON, D7_LAT, obs_mean_u * 50, obs_mean_v * 50,
           'black', f'obs drift x50: {obs_spd*100:.1f} cm/s\nTO {obs_dir_to:.0f} deg', lw=2.5)

ax_map.set_xlim(12.40, 12.50)
ax_map.set_ylim(37.83, 37.92)
ax_map.set_aspect(1 / np.cos(np.radians(37.87)))
ax_map.set_xlabel('Longitude (deg E)')
ax_map.set_ylabel('Latitude (deg N)')
ax_map.set_title(f'D7 release {T0:%H:%M}-{T1:%H:%M} UTC: in-situ stations vs ERA5 vs blended\n'
                 f'Mulino is {d_d7_to_mul:.1f} km from D7 -> IDW weight {w_mul*100:.0f}% (dominates blend)',
                 fontsize=11)
ax_map.legend(fontsize=8, loc='lower left')
ax_map.grid(alpha=0.3)


# === Wind direction time series during the day ===
import matplotlib.dates as mdates
T_DAY_S = pd.Timestamp('2025-07-08 06:00:00')
T_DAY_E = pd.Timestamp('2025-07-08 22:00:00')

ae_day = ae.loc[T_DAY_S:T_DAY_E]
mul_day = mul.loc[T_DAY_S:T_DAY_E]
ae_u_day, ae_v_day = dir_speed_to_uv(ae_day.speed_10m.values, ae_day.dir_deg.values)
mul_u_day, mul_v_day = dir_speed_to_uv(mul_day.speed_10m.values, mul_day.dir_deg.values)
era5_u_day = ds_eu.u10n.sel(time=slice(T_DAY_S, T_DAY_E)).interp(latitude=D7_LAT, longitude=D7_LON)
era5_v_day = ds_ev.v10n.sel(time=slice(T_DAY_S, T_DAY_E)).interp(latitude=D7_LAT, longitude=D7_LON)
ae_dir_to_day = (np.degrees(np.arctan2(ae_u_day, ae_v_day)) % 360)
mul_dir_to_day = (np.degrees(np.arctan2(mul_u_day, mul_v_day)) % 360)
era5_dir_to_day = (np.degrees(np.arctan2(era5_u_day.values, era5_v_day.values)) % 360)

ax_wind_ts.plot(ae_day.index, ae_dir_to_day, '-', color='deepskyblue', label='AE', lw=1.4)
ax_wind_ts.plot(mul_day.index, mul_dir_to_day, '-', color='steelblue', label='Mulino', lw=1.4)
ax_wind_ts.plot(pd.to_datetime(era5_u_day.time.values), era5_dir_to_day, 'o-',
                color='darkgreen', label='ERA5 raw @ D7', markersize=5, lw=1.5)
ax_wind_ts.axvspan(T0, T1, alpha=0.18, color='gold', label='D7 obs window')
ax_wind_ts.axhline(obs_dir_to, color='black', ls='--', lw=1.0, alpha=0.7,
                   label=f'obs drift dir TO ({obs_dir_to:.0f} deg)')
ax_wind_ts.set_ylim(0, 360)
ax_wind_ts.set_yticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
ax_wind_ts.set_yticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N'])
ax_wind_ts.set_ylabel('Wind direction TO (compass)')
ax_wind_ts.set_xlabel('UTC time')
ax_wind_ts.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax_wind_ts.legend(fontsize=8, loc='lower left')
ax_wind_ts.grid(alpha=0.3)
ax_wind_ts.set_title('Wind direction time series at D7 location, 2025-07-08')

fig.suptitle(f'D7 wind blame: Mulino (0.93 km, 92% IDW weight) reads NW->SE while ERA5 raw + obs drift agree on E\n'
             f'Result: blended pulled {blend_dir_to - era5_dir_to:.0f} deg toward S vs ERA5 raw',
             fontsize=12, y=1.00)
plt.tight_layout()
out = FIG / 'diag_d7_station_blame.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f'\nSaved {out}')
