"""
Diagnose Deploy 7: simulated drifter went SW while observed went E (skill 0
in both v04 and v04r). The hypothesis is that the FM surface current and/or
the wind forcing drive the model SW, but the real drift was E - so we compare
the model's drivers (current + wind) with the empirical drift vector during
the 17:00-19:00 UTC Jul 8 obs window at lon ~12.478, lat ~37.876.

Outputs:
  figures/diag_d7_wind_current_vs_drift.png  - 4-panel figure:
    1. Map of D7 obs + v04r sim with wind/current arrows over the obs window
    2. Wind speed/direction time series (blended, ERA5 raw)
    3. FM surface current time series at D7 release area
    4. Empirical drifter velocity time series (from obs)
  data/processed/diag_d7_summary.csv         - numeric summary table
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'

# D7 observation window (UTC) and approximate release area
T0 = pd.Timestamp('2025-07-08 17:00:00')
T1 = pd.Timestamp('2025-07-08 19:00:00')
D7_LON = 12.4778
D7_LAT = 37.8757


def vec_speed_dir(u, v):
    """Wind vector u/v (eastward, northward) -> speed (m/s) and meteorological
    direction (deg, FROM where the wind blows, 0=N, 90=E)."""
    speed = np.hypot(u, v)
    # Direction TO which wind blows: atan2(u, v) (oceanographic)
    # Direction FROM which wind blows (meteo): atan2(-u, -v)
    dir_to = np.degrees(np.arctan2(u, v)) % 360
    dir_from = np.degrees(np.arctan2(-u, -v)) % 360
    return speed, dir_to, dir_from


# === 1. Drifter D7 observed tracks ===
tracks = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
d7 = tracks[tracks['deploy'] == 7].sort_values(['source', 'time']).reset_index(drop=True)
print(f'D7 obs rows: {len(d7)}, sources: {sorted(d7.source.unique())}')

# Sim track (v04r) for D7
sim = pd.read_csv(PROC / 'drifter_sim_v04r.csv', parse_dates=['time'])
d7_sim = sim[sim['deploy'] == 7].sort_values(['drifter_id', 'time']).reset_index(drop=True)
d7_sim = d7_sim[(d7_sim['time'] >= T0) & (d7_sim['time'] <= T1)]

# Empirical drifter velocity from consecutive obs points (per source, then mean)
d7_vel = []
for src, g in d7.groupby('source'):
    g = g.sort_values('time').reset_index(drop=True)
    dt_s = g['time'].diff().dt.total_seconds().values
    dlon = g['lon'].diff().values
    dlat = g['lat'].diff().values
    # m / s east, north
    cos_lat = np.cos(np.radians(g['lat'].mean()))
    u_obs = dlon * 111000 * cos_lat / dt_s
    v_obs = dlat * 111000 / dt_s
    g['u_obs_ms'] = u_obs
    g['v_obs_ms'] = v_obs
    d7_vel.append(g)
d7_vel = pd.concat(d7_vel, ignore_index=True)
mean_obs = d7_vel[['u_obs_ms', 'v_obs_ms']].mean()
spd_obs, dir_to_obs, dir_from_obs = vec_speed_dir(mean_obs['u_obs_ms'], mean_obs['v_obs_ms'])
print(f'\nObserved D7 mean drift: u={mean_obs["u_obs_ms"]:.3f} m/s, v={mean_obs["v_obs_ms"]:.3f} m/s')
print(f'  speed = {spd_obs:.3f} m/s; direction TO = {dir_to_obs:.0f} deg (0=N, 90=E)')


# === 2. Wind: blended (ERA5 + SiAM) and ERA5 raw at D7 release ===
def extract_wind_at(point, t0, t1, u_path, v_path, u_var, v_var):
    """Return (times, u, v) at the given point, time-sliced."""
    du = xr.open_dataset(u_path)
    dv = xr.open_dataset(v_path)
    sl = slice(t0, t1)
    sub_u = du[u_var].sel(time=sl).interp(latitude=point[1], longitude=point[0])
    sub_v = dv[v_var].sel(time=sl).interp(latitude=point[1], longitude=point[0])
    return pd.to_datetime(sub_u.time.values), sub_u.values.astype(float), sub_v.values.astype(float)


print('\n=== Blended wind (v04r) at D7 release ===')
t_b, u_b, v_b = extract_wind_at(
    (D7_LON, D7_LAT), T0, T1,
    ROOT / 'model' / 'dflowfm_v04r' / 'wind_blended_u10n_20250701to20250710.nc',
    ROOT / 'model' / 'dflowfm_v04r' / 'wind_blended_v10n_20250701to20250710.nc',
    'u10n', 'v10n',
)
spd_b, dirto_b, dirfrom_b = vec_speed_dir(u_b.mean(), v_b.mean())
print(f'  Blended wind mean: u={u_b.mean():.2f}, v={v_b.mean():.2f} m/s '
      f'(speed {spd_b:.2f}, TO {dirto_b:.0f} deg)')
print(f'  Time range: {t_b[0]} -> {t_b[-1]}, n={len(t_b)}')

print('\n=== ERA5 raw u10n/v10n at D7 release ===')
t_e, u_e, v_e = extract_wind_at(
    (D7_LON, D7_LAT), T0, T1,
    ROOT / 'model' / 'dflowfm_v04r' / 'era5_u10n_20250701to20250710_ERA5.nc',
    ROOT / 'model' / 'dflowfm_v04r' / 'era5_v10n_20250701to20250710_ERA5.nc',
    'u10n', 'v10n',
)
spd_e, dirto_e, dirfrom_e = vec_speed_dir(u_e.mean(), v_e.mean())
print(f'  ERA5 raw mean:     u={u_e.mean():.2f}, v={v_e.mean():.2f} m/s '
      f'(speed {spd_e:.2f}, TO {dirto_e:.0f} deg)')
print(f'  Time range: {t_e[0]} -> {t_e[-1]}, n={len(t_e)}')


# === 3. FM surface current at D7 release area ===
print('\n=== Regridded v04r surface current at D7 release ===')
ds_uc = xr.open_dataset(PROC / 'v04r_surface_current.nc')
sub = ds_uc.sel(time=slice(T0, T1))
ix = int(np.argmin(np.abs(ds_uc.lon.values - D7_LON)))
iy = int(np.argmin(np.abs(ds_uc.lat.values - D7_LAT)))
u_c = sub['x_sea_water_velocity'].isel(lat=iy, lon=ix).values.astype(float)
v_c = sub['y_sea_water_velocity'].isel(lat=iy, lon=ix).values.astype(float)
t_c = pd.to_datetime(sub.time.values)
spd_c, dirto_c, dirfrom_c = vec_speed_dir(np.nanmean(u_c), np.nanmean(v_c))
print(f'  Current mean: u={np.nanmean(u_c):.3f}, v={np.nanmean(v_c):.3f} m/s '
      f'(speed {spd_c:.3f}, TO {dirto_c:.0f} deg)')
print(f'  At grid cell lon={ds_uc.lon.values[ix]:.4f}, lat={ds_uc.lat.values[iy]:.4f}')

# Also compute the predicted drift (u_current + 0.02 * u_wind) to compare with obs
u_pred_fm = np.nanmean(u_c) + 0.02 * u_b.mean()
v_pred_fm = np.nanmean(v_c) + 0.02 * v_b.mean()
spd_pred, dirto_pred, _ = vec_speed_dir(u_pred_fm, v_pred_fm)
print(f'\n  Predicted drift (current + 2% blended wind): '
      f'u={u_pred_fm:.3f}, v={v_pred_fm:.3f} m/s '
      f'(speed {spd_pred:.3f}, TO {dirto_pred:.0f} deg)')
print(f'  Observed drift:                                 '
      f'u={mean_obs["u_obs_ms"]:.3f}, v={mean_obs["v_obs_ms"]:.3f} m/s '
      f'(speed {spd_obs:.3f}, TO {dir_to_obs:.0f} deg)')


# === 4. Plot 4-panel diagnostic ===
fig = plt.figure(figsize=(14, 10), constrained_layout=True)
gs = fig.add_gridspec(2, 2)
ax_map = fig.add_subplot(gs[0, 0])
ax_wind = fig.add_subplot(gs[0, 1])
ax_curr = fig.add_subplot(gs[1, 0])
ax_drift = fig.add_subplot(gs[1, 1])

# Panel 1: Map of D7 obs + sim (zoom)
cmap_d = plt.get_cmap('tab10')
for i, (src, g) in enumerate(d7.groupby('source')):
    color = cmap_d(i % 10)
    g = g.sort_values('time')
    ax_map.plot(g['lon'], g['lat'], '-', color=color, lw=1.5, label=f'obs {src}', zorder=4)
    ax_map.scatter(g['lon'].iloc[0], g['lat'].iloc[0], color=color, s=80, marker='o',
                   edgecolor='k', linewidth=0.7, zorder=5)
    ax_map.scatter(g['lon'].iloc[-1], g['lat'].iloc[-1], color=color, s=60, marker='s',
                   edgecolor='k', linewidth=0.6, zorder=5)
for i, (src, g) in enumerate(d7_sim.groupby('drifter_id')):
    color = cmap_d(i % 10)
    g = g.sort_values('time')
    ax_map.plot(g['lon'], g['lat'], '--', color=color, lw=1.5, alpha=0.9, zorder=3)
    if len(g):
        ax_map.scatter(g['lon'].iloc[-1], g['lat'].iloc[-1], color=color, s=80,
                       marker='X', edgecolor='k', linewidth=0.6, zorder=5)
# Mean wind & current arrows centered at the release point
arrow_scale = 0.0008  # deg per m/s for visualization
ax_map.annotate('', xy=(D7_LON + arrow_scale*u_b.mean(), D7_LAT + arrow_scale*v_b.mean()),
                xytext=(D7_LON, D7_LAT), arrowprops=dict(arrowstyle='->', color='steelblue', lw=2),
                zorder=6)
ax_map.text(D7_LON + arrow_scale*u_b.mean(), D7_LAT + arrow_scale*v_b.mean(),
            f' wind\n {spd_b:.1f} m/s', color='steelblue', fontsize=8, va='bottom')
ax_map.annotate('', xy=(D7_LON + 30*arrow_scale*np.nanmean(u_c),
                        D7_LAT + 30*arrow_scale*np.nanmean(v_c)),
                xytext=(D7_LON, D7_LAT), arrowprops=dict(arrowstyle='->', color='darkred', lw=2),
                zorder=6)
ax_map.text(D7_LON + 30*arrow_scale*np.nanmean(u_c),
            D7_LAT + 30*arrow_scale*np.nanmean(v_c),
            f' current\n {spd_c*100:.1f} cm/s', color='darkred', fontsize=8, va='top')
# Observed drift mean arrow
ax_map.annotate('', xy=(D7_LON + 30*arrow_scale*mean_obs['u_obs_ms'],
                        D7_LAT + 30*arrow_scale*mean_obs['v_obs_ms']),
                xytext=(D7_LON, D7_LAT), arrowprops=dict(arrowstyle='->', color='black', lw=2.5),
                zorder=7)
ax_map.text(D7_LON + 30*arrow_scale*mean_obs['u_obs_ms'],
            D7_LAT + 30*arrow_scale*mean_obs['v_obs_ms'],
            f' obs drift\n {spd_obs*100:.1f} cm/s', color='black', fontsize=9, va='center', fontweight='bold')
ax_map.set_aspect(1 / np.cos(np.radians(37.87)))
ax_map.set_title(f'D7 obs (solid) vs v04r sim (dashed) + mean wind/current\n{T0:%Y-%m-%d %H:%M} -> {T1:%H:%M} UTC')
ax_map.set_xlabel('Longitude (deg E)')
ax_map.set_ylabel('Latitude (deg N)')
ax_map.legend(fontsize=7, loc='upper left')
ax_map.grid(alpha=0.3)

# Panel 2: Wind time series - blended vs ERA5 raw
ax_wind.plot(t_b, u_b, '-', color='steelblue', label=r'blended $u_{10}$', lw=1.4)
ax_wind.plot(t_b, v_b, '-', color='navy', label=r'blended $v_{10}$', lw=1.4)
ax_wind.plot(t_e, u_e, '--', color='steelblue', alpha=0.6, label=r'ERA5 raw $u_{10}$', lw=1.0)
ax_wind.plot(t_e, v_e, '--', color='navy', alpha=0.6, label=r'ERA5 raw $v_{10}$', lw=1.0)
ax_wind.axhline(0, color='k', lw=0.5, alpha=0.5)
ax_wind.set_ylabel('Wind component (m/s)')
ax_wind.set_title(f'Wind at D7 release (lon={D7_LON}, lat={D7_LAT})')
ax_wind.legend(fontsize=8, loc='best')
ax_wind.grid(alpha=0.3)

# Panel 3: FM surface current time series at D7 grid cell
ax_curr.plot(t_c, u_c, '-', color='darkred', label='u (E)', lw=1.4)
ax_curr.plot(t_c, v_c, '-', color='darkorange', label='v (N)', lw=1.4)
ax_curr.axhline(0, color='k', lw=0.5, alpha=0.5)
ax_curr.set_ylabel('Surface current (m/s)')
ax_curr.set_title(f'FM v04r surface current at D7 cell')
ax_curr.legend(fontsize=8, loc='best')
ax_curr.grid(alpha=0.3)

# Panel 4: Observed drift vector vs predicted (current + 2% wind)
import matplotlib.dates as mdates
for ax in [ax_wind, ax_curr]:
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

# Bar / arrow comparison
labels = ['Obs drift', 'FM current\n@ D7', 'Blended wind\n× 2%', 'ERA5 raw\n× 2%', 'Pred drift\n(curr + 2%w_blnd)']
us = [mean_obs['u_obs_ms'], np.nanmean(u_c), 0.02 * u_b.mean(), 0.02 * u_e.mean(), u_pred_fm]
vs = [mean_obs['v_obs_ms'], np.nanmean(v_c), 0.02 * v_b.mean(), 0.02 * v_e.mean(), v_pred_fm]
colors = ['black', 'darkred', 'steelblue', 'lightblue', 'purple']
for i, (lab, uu, vv, col) in enumerate(zip(labels, us, vs, colors)):
    ax_drift.annotate('', xy=(uu, vv), xytext=(0, 0),
                      arrowprops=dict(arrowstyle='->', color=col, lw=2.0))
    ax_drift.text(uu, vv, f'  {lab}', fontsize=8, va='center', color=col)
amax = max(abs(min(us + vs)), abs(max(us + vs))) * 1.4
ax_drift.set_xlim(-amax, amax)
ax_drift.set_ylim(-amax, amax)
ax_drift.axhline(0, color='k', lw=0.4, alpha=0.5)
ax_drift.axvline(0, color='k', lw=0.4, alpha=0.5)
ax_drift.set_aspect('equal')
ax_drift.set_xlabel('u (eastward, m/s)')
ax_drift.set_ylabel('v (northward, m/s)')
ax_drift.set_title('Mean drift drivers (D7 window)\nobs vs current+wind components')
ax_drift.grid(alpha=0.3)

fig.suptitle('Diagnostic - Deploy 7 (skill 0 in v04 + v04r): why does the model push SW while obs goes E?', fontsize=12)
out = FIG / 'diag_d7_wind_current_vs_drift.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.show()
print(f'\nSaved {out}')

# === 5. Save numeric summary ===
summary = pd.DataFrame({
    'source': ['obs_drift', 'fm_current', 'blended_wind_x2pct', 'era5_raw_wind_x2pct', 'pred_drift_curr+blend2pct'],
    'u_ms': us,
    'v_ms': vs,
    'speed_ms': [np.hypot(u, v) for u, v in zip(us, vs)],
    'dir_to_deg': [np.degrees(np.arctan2(u, v)) % 360 for u, v in zip(us, vs)],
})
summary['compass_to'] = summary['dir_to_deg'].apply(
    lambda d: ['N','NE','E','SE','S','SW','W','NW'][int((d + 22.5) % 360 / 45)]
)
print('\n=== Summary table ===')
print(summary.round(3).to_string(index=False))
summary.to_csv(PROC / 'diag_d7_summary.csv', index=False)
print(f'Saved {PROC / "diag_d7_summary.csv"}')
