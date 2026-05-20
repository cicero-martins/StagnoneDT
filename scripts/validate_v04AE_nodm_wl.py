"""WL validation for v04AE_nodm coupled 9-day run, side-by-side with v04AE.

Computes RMSE/bias/RMSE_anom/corr at BocaNord, BocaSud, AltaVilaEst for both
runs against the in-situ 10-min UTC obs, with the same post-spinup window
(drop first 1 day) per CLAUDE.md validation philosophy.

Outputs:
  figures/v04AE_nodm_vs_v04AE_wl_validation.png
  data/processed/v04AE_nodm_wl_metrics.csv
  data/processed/wl_compare_v04AE_v04AE_nodm.csv
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
FIG.mkdir(parents=True, exist_ok=True)

RUNS = {
    'v04AE':      ROOT / 'model' / 'dflowfm_v04AE'      / 'DFM_OUTPUT_Stagnone_dxy01_15m',
    'v04AE_nodm': ROOT / 'model' / 'dflowfm_v04AE_nodm' / 'DFM_OUTPUT_Stagnone_dxy01_15m',
}
STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst']
SPINUP_DAYS = 1.0


def load_sim_wl(out_dir, station):
    for p in range(8):
        f = out_dir / f'Stagnone_dxy01_15m_{p:04d}_his.nc'
        if not f.exists():
            continue
        ds = xr.open_dataset(f)
        names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
                 for s in ds.station_name.values]
        if station not in names:
            ds.close()
            continue
        i = names.index(station)
        dim = 'stations' if 'stations' in ds.waterlevel.dims else 'station'
        wl = ds.waterlevel.isel({dim: i}).to_pandas()
        wl.index = pd.to_datetime(wl.index)
        ds.close()
        return wl
    return None


def load_obs(station):
    name_map = {'AltaVilaEst': 'Altavila'}
    name = name_map.get(station, station)
    candidates = [
        PROC / f'wl_{station}_10min_UTC.csv',
        PROC / f'wl_{name}Est_10min_UTC.csv',
        PROC / f'wl_{name}_10min_UTC.csv',
    ]
    for c in candidates:
        if c.exists():
            df = pd.read_csv(c, parse_dates=['datetime_utc'])
            df = df.rename(columns={'datetime_utc': 'time', 'wl_m': 'wl'})
            return df.set_index('time')['wl']
    return None


def metrics(o, s):
    valid = (~o.isna()) & (~s.isna())
    o, s = o[valid].values, s[valid].values
    if len(o) < 3:
        return dict(n=len(o), rmse=np.nan, bias=np.nan, rmse_anom=np.nan,
                    corr=np.nan, std_ratio=np.nan)
    bias = (s - o).mean()
    rmse = np.sqrt(((s - o) ** 2).mean())
    o_a = o - o.mean(); s_a = s - s.mean()
    rmse_anom = np.sqrt(((s_a - o_a) ** 2).mean())
    corr = float(np.corrcoef(o_a, s_a)[0, 1]) if o_a.std() > 0 else np.nan
    std_ratio = s.std() / o.std() if o.std() > 0 else np.nan
    return dict(n=len(o), rmse=rmse, bias=bias, rmse_anom=rmse_anom,
                corr=corr, std_ratio=std_ratio)


def main():
    # Load obs + sim for each run+station
    pairs = {}  # (run, station) -> (sim, obs_resampled_to_sim_grid)
    for run, out_dir in RUNS.items():
        for st in STATIONS:
            sim = load_sim_wl(out_dir, st)
            obs = load_obs(st)
            if sim is None or obs is None:
                print(f'WARN  {run} {st}:  sim={sim is None}  obs={obs is None}')
                continue
            obs_i = obs.reindex(sim.index, method='nearest',
                                tolerance=pd.Timedelta('15min'))
            pairs[(run, st)] = (sim, obs_i)

    # Common window across both runs (assume same sim period)
    starts = [s.index.min() for (s, _) in pairs.values()]
    ends = [s.index.max() for (s, _) in pairs.values()]
    t0_raw = max(starts); tF = min(ends)
    t0 = t0_raw + pd.Timedelta(days=SPINUP_DAYS)
    print(f'Sim window:        {t0_raw} -> {tF}')
    print(f'Validation window: {t0} -> {tF} (drop first {SPINUP_DAYS} day spinup)\n')

    # Metrics table
    rows = []
    for (run, st), (sim, obs) in pairs.items():
        for label, t_start in [('post-spinup', t0), ('full', t0_raw)]:
            m = metrics(obs.loc[t_start:tF], sim.loc[t_start:tF])
            m.update(run=run, station=st, window=label)
            rows.append(m)
    df = pd.DataFrame(rows)[['run', 'station', 'window', 'n', 'rmse', 'bias',
                              'rmse_anom', 'corr', 'std_ratio']]

    # Print post-spinup compact view
    print('=== Post-spinup metrics ===')
    print(df[df.window == 'post-spinup'].drop(columns=['window']).to_string(
        index=False, float_format='%.4f'))

    # Save full metrics
    metrics_csv = PROC / 'v04AE_nodm_wl_metrics.csv'
    df.to_csv(metrics_csv, index=False, float_format='%.4f')

    # Compact comparison table
    pivot = df[df.window == 'post-spinup'].pivot(
        index='station', columns='run',
        values=['rmse', 'bias', 'rmse_anom', 'corr'])
    pivot['delta_rmse'] = pivot[('rmse', 'v04AE_nodm')] - pivot[('rmse', 'v04AE')]
    pivot['delta_corr'] = pivot[('corr', 'v04AE_nodm')] - pivot[('corr', 'v04AE')]
    cmp_csv = PROC / 'wl_compare_v04AE_v04AE_nodm.csv'
    pivot.to_csv(cmp_csv, float_format='%.4f')
    print(f'\nSaved {metrics_csv}')
    print(f'Saved {cmp_csv}')
    print('\n=== nodm - v04AE deltas (post-spinup) ===')
    print(pivot[['delta_rmse', 'delta_corr']].to_string(float_format='%+.4f'))

    # Plot: 3 panels (one per station), obs + v04AE + v04AE_nodm
    fig, axes = plt.subplots(len(STATIONS), 1, figsize=(13, 3 * len(STATIONS)),
                              sharex=True)
    colors = {'v04AE': 'tab:red', 'v04AE_nodm': 'tab:blue'}
    for ax, st in zip(axes, STATIONS):
        obs_plotted = False
        for run in RUNS:
            key = (run, st)
            if key not in pairs:
                continue
            sim, obs = pairs[key]
            if not obs_plotted:
                ax.plot(obs.index, obs.values, color='black', lw=0.9, label='obs')
                obs_plotted = True
            row = df.query('run == @run and station == @st and window == "post-spinup"').iloc[0]
            label = (f'{run}  RMSE={row["rmse"]:.3f}  bias={row["bias"]:+.3f}  '
                     f'RMSEa={row["rmse_anom"]:.3f}  corr={row["corr"]:.3f}')
            ax.plot(sim.index, sim.values, color=colors[run], lw=0.9,
                    label=label)
        ax.axvline(t0, color='gray', ls='--', alpha=0.6, lw=0.8)
        ax.set_title(st)
        ax.set_ylabel('WL [m]')
        ax.grid(alpha=0.3)
        ax.legend(loc='upper right', fontsize=7)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
    axes[-1].set_xlabel('date (UTC)')
    plt.suptitle('Stagnone WL — v04AE (D-Morph on) vs v04AE_nodm (D-Morph off) vs obs',
                 y=1.005, fontsize=11)
    plt.tight_layout()
    fig_path = FIG / 'v04AE_nodm_vs_v04AE_wl_validation.png'
    plt.savefig(fig_path, dpi=140, bbox_inches='tight')
    print(f'Saved {fig_path}')


if __name__ == '__main__':
    main()
