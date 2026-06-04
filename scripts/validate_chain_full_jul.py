"""Validate and plot full Jul 07-20 continuation chain (12 runs).

Inputs: data/processed/continuation_validation_jun04/*_his.nc
Outputs:
  data/processed/continuation_validation_jun04/metrics.csv
  figures/validation_chain_2026-06-04.png   (skill evolution + time series)
  figures/validation_chain_skill_2026-06-04.png  (bar chart per station)

Run window derivation:
  d2025-07-10_his.nc       -> N-3 baseline: Jul 07 -> Jul 10
  d2025-07-NN_nK_his.nc    -> N-K: (Jul NN - K days) -> Jul NN
"""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.cm as cm

ROOT = Path(__file__).resolve().parent.parent
VAL_DIR = ROOT / 'data' / 'processed' / 'continuation_validation_jun04'
FIG_DIR = ROOT / 'figures'
INSITU = {
    'AltaVilaEst': ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'AE_wl_UTC.csv',
    'BocaNord':    ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BN_wl_UTC.csv',
    'BocaSud':     ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BS_wl_UTC.csv',
}
MARETTIMO_MOD_CSV = VAL_DIR / 'marettimo_wl_chain_jul25.csv'
MARETTIMO_OBS_CSV = ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'
SPINUP_H = 12


def derive_window(stem: str):
    """Return (t0, t1, publish_date, label) from his.nc stem."""
    if stem == 'd2025-07-10':
        t0, t1 = pd.Timestamp('2025-07-07'), pd.Timestamp('2025-07-10')
        return t0, t1, t1, 'N-3 nodm (Jul07-10)'
    m = re.match(r'd(\d{4}-\d{2}-\d{2})_n(\d+)$', stem)
    if m:
        publish = pd.Timestamp(m.group(1))
        k = int(m.group(2))
        t0 = publish - pd.Timedelta(days=k)
        return t0, publish, publish, f'N-{k} chain ({t0.strftime("%d")}-{publish.strftime("%b%d")})'
    raise ValueError(f'Cannot parse stem: {stem}')


def station_names(ds):
    out = []
    for s in ds.station_name.values:
        if isinstance(s, (np.ndarray, list)):
            out.append(b''.join([c if isinstance(c, bytes) else c.encode() for c in s]).decode().strip())
        else:
            out.append(str(s).replace("b'", "").replace("'", "").strip())
    return out


def load_obs(stn):
    df = pd.read_csv(INSITU[stn])
    tcol = next(c for c in df.columns if 'time' in c.lower())
    wlcol = next(c for c in df.columns if c.lower() in ('h_m', 'wl', 'wl_m', 'waterlevel', 'h')
                 or 'level' in c.lower())
    df[tcol] = pd.to_datetime(df[tcol])
    return df.set_index(tcol)[wlcol]


def detide(s, win_steps=25 * 6):
    return s - s.rolling(win_steps, center=True, min_periods=1).mean()


def compute_metrics(mod_raw, obs_raw, t_start, t_end):
    m10 = mod_raw.resample('10min').mean().dropna()[t_start:t_end]
    o10 = obs_raw.resample('10min').mean().dropna()[t_start:t_end]
    common = m10.index.intersection(o10.index)
    if len(common) < 30:
        return None
    m, o = m10.loc[common], o10.loc[common]
    bias = (m - o).mean()
    rmse = np.sqrt(((m - o) ** 2).mean())
    ma, oa = detide(m), detide(o)
    return {
        'bias_mm': bias * 1000,
        'rmse_mm': rmse * 1000,
        'corr_raw': m.corr(o),
        'rmse_anom_mm': np.sqrt(((ma - oa) ** 2).mean()) * 1000,
        'corr_anom': ma.corr(oa),
        'n_steps': len(common),
    }


def collect_all_runs():
    files = sorted(VAL_DIR.glob('*_his.nc'))
    runs = []
    for f in files:
        stem = f.stem.replace('_his', '')
        try:
            t0, t1, pub, label = derive_window(stem)
        except ValueError:
            continue
        runs.append({'file': f, 'stem': stem, 't0': t0, 't1': t1, 'pub': pub, 'label': label})
    return runs


def load_marettimo_mod():
    """Load model Marettimo WL from pre-extracted CSV (one row per run×time)."""
    if not MARETTIMO_MOD_CSV.exists():
        return None
    df = pd.read_csv(MARETTIMO_MOD_CSV)
    df['time'] = pd.to_datetime(df['time'])
    return df


def load_marettimo_obs():
    df = pd.read_csv(MARETTIMO_OBS_CSV)
    tcol = next(c for c in df.columns if 'time' in c.lower())
    df[tcol] = pd.to_datetime(df[tcol])
    return df.set_index(tcol)['wl_m']


def build_metrics(runs, obs_cache):
    rows = []
    mar_mod = load_marettimo_mod()
    mar_obs = load_marettimo_obs() if MARETTIMO_OBS_CSV.exists() else None

    for r in runs:
        t_val_start = r['t0'] + pd.Timedelta(hours=SPINUP_H)

        # --- his.nc stations (AE/BN/BS) ---
        ds = xr.open_dataset(r['file'])
        names = station_names(ds)
        for stn, obs_raw in obs_cache.items():
            if stn not in names:
                continue
            idx = names.index(stn)
            mod_raw = ds.waterlevel.isel(station=idx).to_pandas()
            mod_raw.index = pd.DatetimeIndex(mod_raw.index)
            m = compute_metrics(mod_raw, obs_raw, t_val_start, r['t1'])
            if m is None:
                print(f'  SKIP {r["stem"]} {stn}: insufficient overlap')
                continue
            rows.append({'run': r['stem'], 'label': r['label'],
                         'pub_date': r['pub'].date(), 'station': stn, **m})
        ds.close()

        # --- Marettimo from pre-extracted CSV ---
        if mar_mod is not None and mar_obs is not None:
            sub = mar_mod[mar_mod['run'] == r['stem']].set_index('time')['wl_m']
            if len(sub) == 0:
                continue
            m = compute_metrics(sub, mar_obs, t_val_start, r['t1'])
            if m is None:
                print(f'  SKIP {r["stem"]} Marettimo: insufficient overlap')
                continue
            rows.append({'run': r['stem'], 'label': r['label'],
                         'pub_date': r['pub'].date(), 'station': 'Marettimo', **m})

    return pd.DataFrame(rows)


def plot_skill_evolution(df, fname):
    """Line plots: corr_anom and bias vs publish date, one line per station."""
    stations = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'Marettimo']
    colors = {'BocaNord': '#1f77b4', 'BocaSud': '#2ca02c', 'AltaVilaEst': '#d62728', 'Marettimo': '#8c564b'}

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    metrics = ['corr_anom', 'rmse_anom_mm', 'bias_mm']
    ylabels = ['Anomaly correlation', 'Anomaly RMSE (mm)', 'Bias (mm)']
    ylims = [(0, 1.0), (0, None), (None, None)]

    for ax, metric, ylabel, ylim in zip(axes, metrics, ylabels, ylims):
        for stn in stations:
            sub = df[df['station'] == stn].sort_values('pub_date')
            ax.plot(pd.to_datetime(sub['pub_date']), sub[metric],
                    marker='o', ms=5, lw=1.4, color=colors[stn], label=stn)
            for _, row in sub.iterrows():
                ax.annotate(f"{row[metric]:.2f}" if metric == 'corr_anom' else f"{row[metric]:.0f}",
                            xy=(pd.Timestamp(row['pub_date']), row[metric]),
                            xytext=(0, 6), textcoords='offset points',
                            ha='center', fontsize=6.5, color=colors[stn])
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='gray', lw=0.5)
        if ylim[0] is not None or ylim[1] is not None:
            lo, hi = ax.get_ylim()
            ax.set_ylim(ylim[0] if ylim[0] is not None else lo,
                        ylim[1] if ylim[1] is not None else hi)
        if metric == 'corr_anom':
            ax.set_ylim(0, 1.0)
        ax.legend(loc='lower left', fontsize=8)

    axes[-1].xaxis.set_major_locator(mdates.DayLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))
    axes[-1].set_xlabel('Publish date (UTC)')
    fig.suptitle('Skill evolution — operational chain Jul 2025 (N-2 sliding window)\n'
                 '(metrics computed after 12h spinup drop)', fontsize=11, y=0.99)
    fig.tight_layout()
    fig.savefig(fname, dpi=130, bbox_inches='tight')
    print(f'Saved: {fname}  ({fname.stat().st_size / 1024:.0f} KB)')
    plt.close(fig)


def plot_time_series(runs, obs_cache, df, fname):
    """Time series: obs + model chain, 4 panels (BN/BS/AE/Marettimo)."""
    stations = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'Marettimo']
    plot_t0 = pd.Timestamp('2025-07-07')
    plot_t1 = pd.Timestamp('2025-07-20')

    # Pre-load Marettimo data
    mar_mod = load_marettimo_mod()
    mar_obs = load_marettimo_obs() if MARETTIMO_OBS_CSV.exists() else None

    # Color gradient over time (sequential colormap)
    n_runs = len(runs)
    cmap = cm.get_cmap('plasma', n_runs)
    run_colors = {r['stem']: cmap(i) for i, r in enumerate(runs)}

    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    for ax, stn in zip(axes, stations):
        # Observations
        if stn == 'Marettimo':
            if mar_obs is not None:
                obs_p = mar_obs[plot_t0:plot_t1]
                ax.plot(obs_p.index, obs_p.values, color='black', lw=0.7, alpha=0.55,
                        label='In-situ (JRC TAD 658)', zorder=3)
        else:
            obs = obs_cache[stn][plot_t0:plot_t1]
            ax.plot(obs.index, obs.values, color='black', lw=0.7, alpha=0.55,
                    label='In-situ', zorder=3)

        # Model runs
        for r in runs:
            t_spinup_end = r['t0'] + pd.Timedelta(hours=SPINUP_H)
            col = run_colors[r['stem']]
            if stn == 'Marettimo':
                if mar_mod is None:
                    continue
                sub = mar_mod[mar_mod['run'] == r['stem']].set_index('time')['wl_m']
                if len(sub) == 0:
                    continue
                ax.plot(sub[r['t0']:t_spinup_end].index,
                        sub[r['t0']:t_spinup_end].values,
                        color=col, alpha=0.15, lw=1.0, zorder=4)
                ax.plot(sub[t_spinup_end:r['t1']].index,
                        sub[t_spinup_end:r['t1']].values,
                        color=col, alpha=0.95, lw=1.6, zorder=5, label=r['label'])
            else:
                nc = r['file']
                ds = xr.open_dataset(nc)
                names = station_names(ds)
                if stn not in names:
                    ds.close(); continue
                idx = names.index(stn)
                mod = ds.waterlevel.isel(station=idx).to_pandas()
                mod.index = pd.DatetimeIndex(mod.index)
                ax.plot(mod[r['t0']:t_spinup_end].index,
                        mod[r['t0']:t_spinup_end].values,
                        color=col, alpha=0.15, lw=1.0, zorder=4)
                ax.plot(mod[t_spinup_end:r['t1']].index,
                        mod[t_spinup_end:r['t1']].values,
                        color=col, alpha=0.95, lw=1.6, zorder=5, label=r['label'])
                ds.close()

        ax.set_title(stn, loc='left', fontsize=11, fontweight='bold')
        ax.set_ylabel('WL (m)')
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='gray', lw=0.5)

    # Restart marks
    for ax in axes:
        for pub_d in pd.date_range('2025-07-10', '2025-07-20', freq='D'):
            ax.axvline(pub_d, color='steelblue', lw=0.4, linestyle='--', alpha=0.4)

    axes[0].legend(ncol=4, loc='lower left', fontsize=7, framealpha=0.9)
    axes[-1].xaxis.set_major_locator(mdates.DayLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))
    axes[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    axes[-1].set_xlim(plot_t0, plot_t1)
    axes[-1].set_xlabel('Time (UTC)')
    fig.suptitle('Operational chain Jul 2025 — full time series\n'
                 '(plasma gradient: blue=Jul10 → yellow=Jul20; blue dashed lines = publish dates)',
                 fontsize=11, y=0.99)
    fig.tight_layout()
    fig.savefig(fname, dpi=130, bbox_inches='tight')
    print(f'Saved: {fname}  ({fname.stat().st_size / 1024:.0f} KB)')
    plt.close(fig)


def main():
    runs = collect_all_runs()
    print(f'Found {len(runs)} runs in {VAL_DIR}')
    for r in runs:
        print(f'  {r["stem"]:30s}  {r["t0"].date()} -> {r["t1"].date()}  [{r["label"]}]')

    obs_cache = {stn: load_obs(stn) for stn in INSITU}

    print('\nComputing metrics...')
    df = build_metrics(runs, obs_cache)
    if df.empty:
        print('ERROR: no metrics computed. Check station names and insitu CSV paths.')
        return

    out_csv = VAL_DIR / 'metrics.csv'
    df.to_csv(out_csv, index=False, float_format='%.4f')
    print(f'\nCSV: {out_csv}')
    print('\n=== Summary (corr_anom per run × station) ===')
    pivot = df.pivot_table(index='run', columns='station', values='corr_anom', aggfunc='mean')
    pivot.index = [i.replace('d2025-07-', '') for i in pivot.index]
    print(pivot.round(3).to_string())

    print('\n=== Bias (mm) per run × station ===')
    pivot_b = df.pivot_table(index='run', columns='station', values='bias_mm', aggfunc='mean')
    pivot_b.index = [i.replace('d2025-07-', '') for i in pivot_b.index]
    print(pivot_b.round(1).to_string())

    FIG_DIR.mkdir(exist_ok=True)
    plot_skill_evolution(df, FIG_DIR / 'validation_chain_2026-06-04.png')
    plot_time_series(runs, obs_cache, df, FIG_DIR / 'validation_chain_timeseries_2026-06-04.png')


if __name__ == '__main__':
    main()
