"""WL comparison plot: failed iter (Jul 7-9 partial) vs nodm full vs in-situ obs.

3 panels (BocaNord, BocaSud, AltaVilaEst). Shows where the iter diverges from
nodm — diagnostic for the cell 13162 blowup pattern.

Output: figures/iter_d2025-07-10_failed_wl_vs_nodm.png
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

ITER_HIS = PROC / 'iter_d2025-07-10_his_attempt6.nc'
NODM_HIS = ROOT / 'model' / 'dflowfm_v04AE_nodm' / 'DFM_OUTPUT_Stagnone_dxy01_15m' / 'Stagnone_dxy01_15m_0000_his.nc'

STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst']


def sname(ds, name):
    sn = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
          for s in ds.station_name.values]
    return sn.index(name)


def load_wl(ds, station):
    i = sname(ds, station)
    dim = 'stations' if 'stations' in ds['waterlevel'].dims else 'station'
    s = ds['waterlevel'].isel({dim: i}).to_pandas()
    s.index = pd.to_datetime(s.index)
    return s


def load_obs(station):
    name_map = {'AltaVilaEst': 'Altavila'}
    name = name_map.get(station, station)
    for cand in [PROC / f'wl_{station}_10min_UTC.csv',
                 PROC / f'wl_{name}Est_10min_UTC.csv',
                 PROC / f'wl_{name}_10min_UTC.csv']:
        if cand.exists():
            df = pd.read_csv(cand, parse_dates=['datetime_utc'])
            return df.set_index('datetime_utc')['wl_m']
    return None


ds_iter = xr.open_dataset(ITER_HIS)
ds_nodm = xr.open_dataset(NODM_HIS)
print(f'Iter:  {ds_iter.time.values[0]} -> {ds_iter.time.values[-1]} (n={len(ds_iter.time)})')
print(f'Nodm:  {ds_nodm.time.values[0]} -> {ds_nodm.time.values[-1]} (n={len(ds_nodm.time)})')

iter_start = pd.Timestamp(str(ds_iter.time.values[0]))
iter_end = pd.Timestamp(str(ds_iter.time.values[-1]))

fig, axes = plt.subplots(len(STATIONS), 1, figsize=(14, 9), sharex=True)
for ax, st in zip(axes, STATIONS):
    wl_iter = load_wl(ds_iter, st)
    wl_nodm = load_wl(ds_nodm, st)
    obs = load_obs(st)

    # nodm: only show window matching iter (for fair comparison) + a bit before
    nodm_show_start = iter_start - pd.Timedelta('12h')
    wl_nodm_w = wl_nodm.loc[nodm_show_start:iter_end + pd.Timedelta('12h')]

    if obs is not None:
        obs_w = obs.loc[nodm_show_start:iter_end + pd.Timedelta('12h')]
        ax.plot(obs_w.index, obs_w.values, color='black', lw=0.8, label='in-situ obs')

    ax.plot(wl_nodm_w.index, wl_nodm_w.values, color='tab:blue', lw=1.0, alpha=0.85,
            label='v04AE_nodm (cold-start 9d)')
    ax.plot(wl_iter.index, wl_iter.values, color='tab:red', lw=1.2,
            label=f'iter attempt 6 (rst Jul 7 -> crashed Jul 9 00:00)')

    # Mark restart + crash
    ax.axvline(iter_start, color='green', ls=':', alpha=0.7, label='restart')
    ax.axvline(iter_end, color='red', ls='--', alpha=0.7, label='crash')

    # Crash region (cell 13162 blew up — but it's offshore, no station here)
    ax.set_ylabel('WL [m]')
    ax.set_title(f'{st}')
    ax.grid(alpha=0.3)
    if ax is axes[0]:
        ax.legend(loc='upper right', fontsize=8, ncol=2)

axes[-1].set_xlabel('time (UTC)')
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %Hh'))
plt.suptitle('WL at observation stations: iter attempt 6 (failed) vs v04AE_nodm vs obs',
             y=1.005, fontsize=11)
plt.tight_layout()
out = FIG / 'iter_d2025-07-10_failed_wl_vs_nodm.png'
plt.savefig(out, dpi=140, bbox_inches='tight')
print(f'Saved {out}')

# Quick numeric diff
print('\n=== Diff iter vs nodm (within iter window) ===')
for st in STATIONS:
    wl_iter = load_wl(ds_iter, st)
    wl_nodm = load_wl(ds_nodm, st)
    common = wl_iter.index.intersection(wl_nodm.index)
    if len(common) > 5:
        d = wl_iter.loc[common] - wl_nodm.loc[common]
        print(f'  {st:18}  n={len(common):4d}  mean_diff={d.mean():+.4f}  '
              f'max|diff|={d.abs().max():.4f}  '
              f'final t={common[-1]}  final diff={d.iloc[-1]:+.4f}')
