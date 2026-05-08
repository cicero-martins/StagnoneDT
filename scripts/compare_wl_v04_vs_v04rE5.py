"""
WL validation comparison: v04 (blended wind) vs v04rE5 (ERA5 raw, no blend),
over the v04rE5 window Jul 8-9 2025 (~36h after a 1d spinup buffer).

Stations: AltaVilaEst, BocaNord, BocaSud (his.nc direct).
Marettimo from map.nc cell extraction at the v03d-compatible reference cell
(12.0753, 37.9747, bl < -0.3 m) per memory marettimo_validation_cell.

Reports raw RMSE + bias + anomaly RMSE + correlation per station for v04 and
v04rE5, plus the delta. Confirms whether using ERA5 raw broke WL or not.

Outputs:
  data/processed/wl_compare_v04_v04rE5.csv
  figures/wl_compare_v04_v04rE5.png
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
RAW_INSITU = ROOT / 'data' / 'raw' / 'insitu'

# Window: post-spinup of v04rE5. v04rE5 starts Jul 8 00:00 UTC, ends Jul 10.
# Drop first ~6h as spinup buffer; campaign was 8-9 anyway.
T0 = pd.Timestamp('2025-07-08 06:00:00')
T1 = pd.Timestamp('2025-07-09 23:00:00')

V04_HIS = ROOT / 'model' / 'dflowfm_v04' / 'DFM_OUTPUT_Stagnone_dxy01_15m' / 'Stagnone_dxy01_15m_0000_his.nc'
V04rE5_HIS = ROOT / 'model' / 'dflowfm_v04rE5' / 'DFM_OUTPUT_Stagnone_dxy01_15m' / 'Stagnone_dxy01_15m_0000_his.nc'

STATIONS_INTERIOR = ['AltaVilaEst', 'BocaNord', 'BocaSud']

def load_obs_wl(name):
    """Read observed water level CSV (assumed to live in data/raw/insitu/)."""
    candidates = [RAW_INSITU / f'boundaries_{name[:2]}.csv',
                  RAW_INSITU / f'boundaries_{name[:3]}.csv',
                  RAW_INSITU / f'boundaries_AE.csv' if name == 'AltaVilaEst' else None,
                  RAW_INSITU / f'boundaries_BN.csv' if name == 'BocaNord' else None,
                  RAW_INSITU / f'boundaries_BS.csv' if name == 'BocaSud' else None,
                 ]
    for p in candidates:
        if p and p.exists():
            return p
    return None


def stats(obs, sim):
    """Return raw RMSE, bias, anomaly RMSE, correlation, std ratio."""
    valid = (~obs.isna()) & (~sim.isna())
    o, s = obs[valid].values, sim[valid].values
    if len(o) < 3:
        return dict(rmse=np.nan, bias=np.nan, rmse_anom=np.nan, corr=np.nan, std_ratio=np.nan, n=len(o))
    bias = (s - o).mean()
    rmse = np.sqrt(((s - o) ** 2).mean())
    o_anom = o - o.mean()
    s_anom = s - s.mean()
    rmse_anom = np.sqrt(((s_anom - o_anom) ** 2).mean())
    corr = np.corrcoef(o_anom, s_anom)[0, 1]
    std_ratio = s.std() / o.std() if o.std() > 0 else np.nan
    return dict(rmse=rmse, bias=bias, rmse_anom=rmse_anom, corr=corr, std_ratio=std_ratio, n=len(o))


# Load his.nc for both runs
def load_wl_at_station(his_path, station_name):
    ds = xr.open_dataset(his_path)
    # station_name comes back as a byte string; decode + strip
    names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
             for s in ds.station_name.values]
    if station_name not in names:
        return None
    idx = names.index(station_name)
    wl = ds.waterlevel.isel(station=idx).to_pandas()
    wl.index = pd.to_datetime(wl.index)
    return wl.loc[T0:T1]


print(f'Loading v04 his.nc ({V04_HIS.name})...')
print(f'Loading v04rE5 his.nc ({V04rE5_HIS.name})...')

results = []
fig, axes = plt.subplots(len(STATIONS_INTERIOR), 1, figsize=(13, 9), sharex=True)
for ax, station in zip(axes, STATIONS_INTERIOR):
    wl_v04 = load_wl_at_station(V04_HIS, station)
    wl_v04rE5 = load_wl_at_station(V04rE5_HIS, station)
    if wl_v04 is None or wl_v04rE5 is None:
        ax.text(0.5, 0.5, f'{station}: missing', ha='center', va='center', transform=ax.transAxes)
        continue

    # Try to load obs from boundaries CSV if available
    obs_path = None
    short = {'AltaVilaEst': 'AE', 'BocaNord': 'BN', 'BocaSud': 'BS'}.get(station, station[:2])
    for cand in [RAW_INSITU / f'boundaries_{short}.csv']:
        if cand.exists():
            obs_path = cand
            break

    obs = None
    if obs_path:
        try:
            o = pd.read_csv(obs_path, encoding='utf-8-sig')
            # Header is "CET solare", "<Station> h (m)"
            time_col, wl_col = o.columns[0], o.columns[1]
            # Parse "M/D/YYYY h:mm" or "YYYY/M/D h:mm" robustly
            t = pd.to_datetime(o[time_col], errors='coerce', dayfirst=False)
            if t.isna().sum() > len(t) * 0.5:
                # Try yearfirst (BN/BS use YYYY/M/D)
                t = pd.to_datetime(o[time_col], errors='coerce', yearfirst=True)
            o = o.assign(_t=t - pd.Timedelta(hours=1))   # CET solare -> UTC
            o = o.dropna(subset=['_t', wl_col])
            o = o.set_index('_t').sort_index()
            o = o[~o.index.duplicated(keep='first')]
            obs = pd.to_numeric(o[wl_col], errors='coerce').loc[T0:T1]
            # Reindex to model 10-min grid via nearest
            obs = obs.reindex(wl_v04.index, method='nearest', tolerance=pd.Timedelta('5min'))
        except Exception as exc:
            print(f'  {station}: failed to load obs ({exc})')
            obs = None

    # Plot
    ax.plot(wl_v04.index, wl_v04.values, '-', color='steelblue', lw=1.0, alpha=0.9, label='v04 (blended wind)')
    ax.plot(wl_v04rE5.index, wl_v04rE5.values, '-', color='darkorange', lw=1.0, alpha=0.9, label='v04rE5 (ERA5 raw)')
    if obs is not None:
        ax.plot(obs.index, obs.values, '-', color='black', lw=0.8, alpha=0.9, label='obs')
    ax.set_ylabel(f'{station}\nWL (m)')
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc='upper right')

    s_v04 = stats(obs, wl_v04) if obs is not None else None
    s_v04rE5 = stats(obs, wl_v04rE5) if obs is not None else None
    # Also compare v04rE5 vs v04 directly (no obs)
    s_E5_vs_v04 = stats(wl_v04, wl_v04rE5)

    results.append({
        'station': station,
        **{f'v04_{k}': v for k, v in (s_v04 or {}).items()},
        **{f'v04rE5_{k}': v for k, v in (s_v04rE5 or {}).items()},
        **{f'E5_vs_v04_{k}': v for k, v in s_E5_vs_v04.items()},
    })

axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
plt.setp(axes[-1].get_xticklabels(), rotation=30, ha='right')
fig.suptitle(f'WL comparison v04 (blended wind) vs v04rE5 (ERA5 raw)\n'
             f'Jul 8-9 2025, post-spinup window {T0:%H:%M} -> {T1:%H:%M} UTC',
             fontsize=12, y=0.995)
plt.tight_layout()
out = FIG / 'wl_compare_v04_v04rE5.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved {out}')

df_r = pd.DataFrame(results)
df_r.to_csv(PROC / 'wl_compare_v04_v04rE5.csv', index=False)
print('\n=== Stats per station ===')
# Print v04 vs v04rE5 anomaly RMSE and correlation, plus delta
cols = ['station',
        'v04_rmse_anom', 'v04rE5_rmse_anom',
        'v04_corr', 'v04rE5_corr',
        'v04_bias', 'v04rE5_bias',
        'E5_vs_v04_rmse_anom', 'E5_vs_v04_corr']
print(df_r[cols].round(4).to_string(index=False))
