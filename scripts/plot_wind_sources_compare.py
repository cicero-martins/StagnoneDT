"""
Compare the 3 wind sources used in the Stagnone modelling -
AE, Mulino (in-situ stations) and ERA5 raw at the lagoon centre - over the
forcing window Jul 1-10 2025.

Outputs:
  figures/wind_sources_rose.png       3-panel wind rose (from-direction)
  figures/wind_sources_direction.png  direction time series (TO compass)
  figures/wind_sources_speed.png      speed time series

Direction convention follows the in-situ CSVs (`dir_deg` = FROM, 0 N, 90 E).
The time series uses TO direction (where the wind blows toward) since that
is what drives drifters.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')   # non-interactive backend - avoids plt.show() hangs
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'

T0 = pd.Timestamp('2025-07-01 00:00:00')
T1 = pd.Timestamp('2025-07-10 00:00:00')
CAMPAIGN_T0 = pd.Timestamp('2025-07-08 06:00:00')
CAMPAIGN_T1 = pd.Timestamp('2025-07-09 20:00:00')
LAGOON_CENTER = (12.462, 37.867)


def from_to_uv(speed, dir_from_deg):
    """FROM-convention dir + speed -> u, v (eastward, northward)."""
    rad = np.radians(dir_from_deg)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def uv_to_dir_to(u, v):
    return np.degrees(np.arctan2(u, v)) % 360


# Load AE + Mulino, resample hourly
ae = pd.read_csv(PROC / 'wind_AE_10min_UTC.csv', index_col=0, parse_dates=True)
mul = pd.read_csv(PROC / 'wind_Mulino_10min_UTC.csv', index_col=0, parse_dates=True)
ae = ae.loc[T0:T1, ['dir_deg', 'speed_10m']]
mul = mul.loc[T0:T1, ['dir_deg', 'speed_10m']]
ae['u'], ae['v'] = from_to_uv(ae.speed_10m, ae.dir_deg)
mul['u'], mul['v'] = from_to_uv(mul.speed_10m, mul.dir_deg)
ae_h = ae.resample('1h').mean()
mul_h = mul.resample('1h').mean()
# Recompute dir_from after hourly mean (vector mean is more correct than scalar mean of dir)
ae_h['dir_from'] = (np.degrees(np.arctan2(-ae_h.u, -ae_h.v))) % 360
mul_h['dir_from'] = (np.degrees(np.arctan2(-mul_h.u, -mul_h.v))) % 360
ae_h['speed'] = np.hypot(ae_h.u, ae_h.v)
mul_h['speed'] = np.hypot(mul_h.u, mul_h.v)

# ERA5 raw at lagoon centre
ds_eu = xr.open_dataset(ROOT / 'model' / 'dflowfm_v04rE5' / 'wind_era5raw_u10n_20250701to20250710.nc')
ds_ev = xr.open_dataset(ROOT / 'model' / 'dflowfm_v04rE5' / 'wind_era5raw_v10n_20250701to20250710.nc')
e5_u = ds_eu.u10n.sel(time=slice(T0, T1)).interp(latitude=LAGOON_CENTER[1], longitude=LAGOON_CENTER[0]).to_pandas()
e5_v = ds_ev.v10n.sel(time=slice(T0, T1)).interp(latitude=LAGOON_CENTER[1], longitude=LAGOON_CENTER[0]).to_pandas()
e5_h = pd.DataFrame({'u': e5_u, 'v': e5_v})
e5_h['speed'] = np.hypot(e5_h.u, e5_h.v)
e5_h['dir_from'] = (np.degrees(np.arctan2(-e5_h.u, -e5_h.v))) % 360

print(f'AE hourly: {ae_h.index[0]} -> {ae_h.index[-1]}, n={len(ae_h)}')
print(f'Mulino   : {mul_h.index[0]} -> {mul_h.index[-1]}, n={len(mul_h)}')
print(f'ERA5 @ lagoon centre: {e5_h.index[0]} -> {e5_h.index[-1]}, n={len(e5_h)}')


# ------------- 1) Wind rose (3 panels) -------------
def windrose(ax, speed, dir_from, title, n_dir=16, speed_bins=(0, 2, 4, 6, 8, 12)):
    """Polar wind rose. Bars per dir bin, stacked by speed bin."""
    s = pd.Series(speed).dropna().values
    d = pd.Series(dir_from).dropna().values
    valid = (~np.isnan(s)) & (~np.isnan(d))
    s, d = s[valid], d[valid]

    bin_size = 360 / n_dir
    dir_centres = np.arange(0, 360, bin_size)
    # Shift directions so 0 (N) is centred in its bin
    d_shifted = (d + bin_size/2) % 360
    dir_bins = np.floor(d_shifted / bin_size).astype(int)

    cmap = plt.get_cmap('viridis')
    colours = cmap(np.linspace(0.15, 0.95, len(speed_bins) - 1))

    bottom = np.zeros(n_dir)
    for k in range(len(speed_bins) - 1):
        lo, hi = speed_bins[k], speed_bins[k+1]
        in_bin = (s >= lo) & (s < hi if k < len(speed_bins) - 2 else s >= lo)
        counts = np.zeros(n_dir)
        for j in range(n_dir):
            counts[j] = ((dir_bins == j) & in_bin).sum()
        freq = 100 * counts / len(s) if len(s) else counts
        theta = np.radians(dir_centres)
        label = f'{lo}-{hi} m/s' if k < len(speed_bins) - 2 else f'>={lo} m/s'
        ax.bar(theta, freq, width=np.radians(bin_size) * 0.95,
               bottom=bottom, color=colours[k], edgecolor='white', linewidth=0.4,
               label=label)
        bottom += freq

    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_xticks(np.radians(np.arange(0, 360, 45)))
    ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'], fontsize=9)
    ax.set_title(title, fontsize=11, pad=14)
    ax.tick_params(labelsize=8)
    ax.grid(alpha=0.3)
    return colours


fig, axes = plt.subplots(1, 3, figsize=(16, 6.5), subplot_kw={'projection': 'polar'})
spd_bins = (0, 2, 4, 6, 8, 100)
colours = windrose(axes[0], ae_h.speed, ae_h.dir_from, f'AE station\n(lagoon NW, n={ae_h.dropna().shape[0]} h)', speed_bins=spd_bins)
windrose(axes[1], mul_h.speed, mul_h.dir_from, f'Mulino station\n(lagoon E shore, n={mul_h.dropna().shape[0]} h)', speed_bins=spd_bins)
windrose(axes[2], e5_h.speed, e5_h.dir_from, f'ERA5 raw @ lagoon centre\n(n={e5_h.dropna().shape[0]} h)', speed_bins=spd_bins)

# Shared legend at bottom
labels = [f'{spd_bins[k]}-{spd_bins[k+1]} m/s' if k < len(spd_bins)-2 else f'>={spd_bins[k]} m/s'
          for k in range(len(spd_bins) - 1)]
handles = [plt.Rectangle((0, 0), 1, 1, color=colours[k]) for k in range(len(colours))]
fig.legend(handles, labels, loc='lower center', ncol=len(labels), fontsize=9,
           bbox_to_anchor=(0.5, 0.01), frameon=True, title='wind speed (FROM-direction)')
fig.suptitle(f'Wind rose - 3 sources used in v04 forcing, {T0:%Y-%m-%d} to {T1:%Y-%m-%d}\n'
             '(rings = % of hours; FROM-convention)', fontsize=12, y=0.99)
plt.tight_layout(rect=[0, 0.05, 1, 0.96])
out = FIG / 'wind_sources_rose.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved {out}')


# ------------- 2) Direction time series -------------
ae_dir_to = uv_to_dir_to(ae_h.u, ae_h.v)
mul_dir_to = uv_to_dir_to(mul_h.u, mul_h.v)
e5_dir_to = uv_to_dir_to(e5_h.u, e5_h.v)

fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(ae_h.index, ae_dir_to, '-', color='deepskyblue', lw=1.2, label='AE', alpha=0.9)
ax.plot(mul_h.index, mul_dir_to, '-', color='steelblue', lw=1.2, label='Mulino', alpha=0.9)
ax.plot(e5_h.index, e5_dir_to, 'o-', color='darkgreen', lw=1.4, label='ERA5 raw @ lagoon centre',
        markersize=3, alpha=0.9)
ax.axvspan(CAMPAIGN_T0, CAMPAIGN_T1, alpha=0.18, color='gold', label='drifter campaign 8-9 Jul')
ax.set_ylim(0, 360)
ax.set_yticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
ax.set_yticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N'])
ax.set_ylabel('Wind direction TO (compass)')
ax.set_xlabel('UTC time')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
ax.xaxis.set_major_locator(mdates.AutoDateLocator())
plt.setp(ax.get_xticklabels(), rotation=30, ha='right')
ax.legend(fontsize=9, loc='upper left', ncol=2, framealpha=0.9)
ax.grid(alpha=0.3)
ax.set_title(f'Wind direction TO - 3 sources, hourly, {T0:%Y-%m-%d} to {T1:%Y-%m-%d}')
plt.tight_layout()
out = FIG / 'wind_sources_direction.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved {out}')


# ------------- 3) Speed time series -------------
fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(ae_h.index, ae_h.speed, '-', color='deepskyblue', lw=1.4, label='AE', alpha=0.9)
ax.plot(mul_h.index, mul_h.speed, '-', color='steelblue', lw=1.4, label='Mulino', alpha=0.9)
ax.plot(e5_h.index, e5_h.speed, 'o-', color='darkgreen', lw=1.4, label='ERA5 raw @ lagoon centre',
        markersize=3, alpha=0.9)
ax.axvspan(CAMPAIGN_T0, CAMPAIGN_T1, alpha=0.18, color='gold', label='drifter campaign 8-9 Jul')
ax.set_ylabel('Wind speed (m/s)')
ax.set_xlabel('UTC time')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
ax.xaxis.set_major_locator(mdates.AutoDateLocator())
plt.setp(ax.get_xticklabels(), rotation=30, ha='right')
ax.legend(fontsize=9, loc='upper right', ncol=2, framealpha=0.9)
ax.grid(alpha=0.3)
ax.set_title(f'Wind speed - 3 sources, hourly, {T0:%Y-%m-%d} to {T1:%Y-%m-%d}')
plt.tight_layout()
out = FIG / 'wind_sources_speed.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved {out}')

# Summary stats table
print('\n=== Summary stats over Jul 1-10 (hourly) ===')
for label, df in [('AE', ae_h), ('Mulino', mul_h), ('ERA5_centre', e5_h)]:
    spd = df.speed.dropna()
    print(f'  {label:12s}: speed mean={spd.mean():.2f} max={spd.max():.2f} '
          f'p95={spd.quantile(0.95):.2f} m/s')
