"""Station response of the no-waves member to the 2026 lagoon bathymetry.

The pair is model/dflowfm_v04AE_nowaves_ctrl (v04 bed) and
model/dflowfm_v04AE_nowaves_bathy26 (2026 bed inside the lagoon), both run
on four partitions on the same host, so that the bed level is the only
difference. The first simulated day is dropped as spin-up.

Three comparisons are made from the history files.

  against the gauges    RMSE, bias, anomaly RMSE and correlation of water
                        level at BocaNord, BocaSud and AltaVilaEst for each
                        run, where RMSE^2 = bias^2 + RMSE_anom^2
  between the runs      rms difference, amplitude ratio and lag of water
                        level at every lagoon station, the lag being the
                        shift that maximises the cross-correlation on a
                        one-minute grid, positive when the 2026 bed responds
                        later
  currents and salt     mean surface speed, rms vector difference of the
                        surface current, and mean salinity of the last day
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from compare_bathy_levigata_2006 import C_NEW, C_OLD, INK, OUT
from validate_v04AE_nodm_wl import load_obs, metrics

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    'ctrl': ROOT / 'model/dflowfm_v04AE_nowaves_ctrl/DFM_OUTPUT_Stagnone_dxy01_15m',
    'bathy26': ROOT / 'model/dflowfm_v04AE_nowaves_bathy26/DFM_OUTPUT_Stagnone_dxy01_15m',
}
GAUGES = ['BocaNord', 'BocaSud', 'AltaVilaEst']
LAGOON = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'C1_Central', 'C2_NorthCenter', 'C3_SouthCenter']
SPINUP = pd.Timedelta(days=1)
MAX_LAG_MIN = 120


def load_his(out_dir):
    ds = xr.open_dataset(out_dir / 'Stagnone_dxy01_15m_0000_his.nc')
    names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip() for s in ds.station_name.values]
    dim = 'stations' if 'stations' in ds.waterlevel.dims else 'station'
    return ds.assign_coords({dim: names}).rename({dim: 'station'})


def lag_minutes(ref, test):
    """Shift of test relative to ref that maximises the correlation of anomalies."""
    idx = pd.date_range(ref.index[0], ref.index[-1], freq='1min')
    a = ref.reindex(ref.index.union(idx)).interpolate('time').reindex(idx).values
    b = test.reindex(test.index.union(idx)).interpolate('time').reindex(idx).values
    a, b = a - a.mean(), b - b.mean()
    best = (-np.inf, 0)
    for k in range(-MAX_LAG_MIN, MAX_LAG_MIN + 1):
        r = np.corrcoef(a[max(0, -k):len(a) - max(0, k)], b[max(0, k):len(b) - max(0, -k)])[0, 1]
        best = max(best, (r, k))
    return best[1], best[0]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option('display.width', 200)
    his = {k: load_his(p) for k, p in RUNS.items()}
    t_end = min(pd.Timestamp(h.time.values[-1]) for h in his.values())
    t0 = pd.Timestamp(his['ctrl'].time.values[0]) + SPINUP
    print(f'[window] {t0} to {t_end}')
    his = {k: h.sel(time=slice(t0, t_end)) for k, h in his.items()}
    wl = {k: h.waterlevel.to_pandas() for k, h in his.items()}

    # ---- against the gauges -------------------------------------------------
    rows = []
    for st in GAUGES:
        obs = load_obs(st)
        if obs is None:
            print(f'[gauge] no observations for {st}')
            continue
        for run in RUNS:
            sim = wl[run][st]
            o = obs.reindex(sim.index, method='nearest', tolerance=pd.Timedelta('15min'))
            rows.append({'station': st, 'run': run, **metrics(o, sim)})
    if rows:
        g = pd.DataFrame(rows)
        print('\n[water level against the gauges] metres')
        print(g.to_string(index=False, float_format='%.4f'))
        g.to_csv(OUT / 'pair_wl_gauges.csv', index=False, float_format='%.4f')

    # ---- between the runs ---------------------------------------------------
    rows = []
    for st in LAGOON:
        a, b = wl['ctrl'][st], wl['bathy26'][st]
        lag, r = lag_minutes(a, b)
        us = {k: h.x_velocity.sel(station=st).isel(laydim=-1).values for k, h in his.items()}
        vs = {k: h.y_velocity.sel(station=st).isel(laydim=-1).values for k, h in his.items()}
        sp = {k: np.hypot(us[k], vs[k]) for k in his}
        last = slice(t_end - pd.Timedelta(days=1), t_end)
        sal = {k: float(h.salinity.sel(station=st, time=last).mean()) for k, h in his.items()}
        rows.append({
            'station': st,
            'wl_mean_diff': (b - a).mean(), 'wl_rms_diff': np.sqrt(((b - a) ** 2).mean()),
            'wl_std_ctrl': a.std(), 'amp_ratio': b.std() / a.std(), 'lag_min': lag, 'r_at_lag': r,
            'speed_ctrl': np.nanmean(sp['ctrl']), 'speed_bathy26': np.nanmean(sp['bathy26']),
            'vec_rms_diff': np.sqrt(np.nanmean((us['bathy26'] - us['ctrl']) ** 2 + (vs['bathy26'] - vs['ctrl']) ** 2)),
            'sal_ctrl': sal['ctrl'], 'sal_bathy26': sal['bathy26'],
        })
    t = pd.DataFrame(rows)
    print('\n[bathy26 against ctrl] water level in m, surface current in m/s, depth-mean salinity of the last day')
    print(t.to_string(index=False, float_format='%.4f'))
    t.to_csv(OUT / 'pair_station_response.csv', index=False, float_format='%.4f')

    # ---- figure -------------------------------------------------------------
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': '#999999', 'axes.labelcolor': INK,
                         'xtick.color': INK, 'ytick.color': INK, 'axes.titlesize': 10})
    fig, axs = plt.subplots(len(GAUGES), 2, figsize=(13, 8), sharex=True, constrained_layout=True)
    for i, st in enumerate(GAUGES):
        ax = axs[i, 0]
        ax.plot(wl['ctrl'].index, wl['ctrl'][st], color=C_OLD, lw=1.6, label='v04 bed')
        ax.plot(wl['bathy26'].index, wl['bathy26'][st], color=C_NEW, lw=1.0, label='2026 bed')
        ax.set_ylabel('Water level (m)'); ax.set_title(st)
        ax = axs[i, 1]
        ax.plot(wl['ctrl'].index, 100 * (wl['bathy26'][st] - wl['ctrl'][st]), color=INK, lw=1.0)
        ax.axhline(0, color='#999999', lw=0.8)
        ax.set_ylabel('Difference (cm)'); ax.set_title(f'{st}, 2026 bed minus v04 bed')
    axs[0, 0].legend(frameon=False, ncol=2, loc='upper right')
    for ax in axs.ravel():
        ax.grid(color='#e5e5e5', lw=0.6); ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    fig.savefig(OUT / 'fig5_pair_water_level.png', dpi=170)
    print('\n[done]', OUT / 'fig5_pair_water_level.png')


if __name__ == '__main__':
    main()
