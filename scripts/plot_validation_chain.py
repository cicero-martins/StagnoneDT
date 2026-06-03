"""Plot WL validation chain: 4 runs vs in-situ AE/BN/BS.

3 stacked panels (one per station). Each panel:
  - In-situ obs (thick black)
  - 4 model runs overlaid (distinct colors)
  - Spinup window shaded (first 12h of each run)
  - Vertical lines at chain restart events
Annotated with corr_anom per run.

Output: figures/validation_chain_2026-06-03.png
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent.parent
VAL_DIR = ROOT / 'data' / 'processed' / 'continuation_validation'
FIG = ROOT / 'figures' / 'validation_chain_2026-06-03.png'

INSITU = {
    'AltaVilaEst': ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'AE_wl_UTC.csv',
    'BocaNord':    ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BN_wl_UTC.csv',
    'BocaSud':     ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BS_wl_UTC.csv',
}

RUNS = [
    {'label': 'N-3 nodm (Jul 7-10)',     'file': 'd2025-07-10_his.nc',    't0': '2025-07-07', 't1': '2025-07-10', 'color': '#1f77b4'},
    {'label': 'N-2 nodm (Jul 8-10)',     'file': 'd2025-07-10_n2_his.nc', 't0': '2025-07-08', 't1': '2025-07-10', 'color': '#2ca02c'},
    {'label': 'N-2 chain (Jul 9-11)',    'file': 'd2025-07-11_n2_his.nc', 't0': '2025-07-09', 't1': '2025-07-11', 'color': '#d62728'},
    {'label': 'N-2 chain (Jul 10-12)',   'file': 'd2025-07-12_n2_his.nc', 't0': '2025-07-10', 't1': '2025-07-12', 'color': '#9467bd'},
]

SPINUP_H = 12  # excluded from metrics + shaded in plot


def detide(s, win_steps=25 * 6):
    return s - s.rolling(win_steps, center=True, min_periods=1).mean()


def station_names(ds):
    arr = ds.station_name.values
    out = []
    for s in arr:
        if isinstance(s, (np.ndarray, list)):
            out.append(b''.join([c if isinstance(c, bytes) else c.encode() for c in s]).decode().strip())
        else:
            out.append(str(s).replace("b'", "").replace("'", "").strip())
    return out


def load_obs(stn):
    df = pd.read_csv(INSITU[stn])
    tcol = [c for c in df.columns if 'time' in c.lower()][0]
    wlcol = [c for c in df.columns if c.lower() in ('h_m', 'wl', 'wl_m', 'waterlevel', 'h') or 'level' in c.lower()][0]
    df[tcol] = pd.to_datetime(df[tcol])
    s = df.set_index(tcol)[wlcol]
    return s


def metrics_for_run(mod, obs, t_start, t_end):
    """mod, obs are 10-min resampled inside [t_start, t_end]."""
    m10 = mod.resample('10min').mean().dropna()[t_start:t_end]
    o10 = obs.resample('10min').mean().dropna()[t_start:t_end]
    common = m10.index.intersection(o10.index)
    if len(common) < 30:
        return None
    m = m10.loc[common]
    o = o10.loc[common]
    rmse = np.sqrt(((m - o) ** 2).mean())
    bias = (m - o).mean()
    ma = detide(m); oa = detide(o)
    corr_anom = ma.corr(oa)
    rmse_anom = np.sqrt(((ma - oa) ** 2).mean())
    return {'corr_anom': corr_anom, 'rmse_anom_mm': rmse_anom * 1000, 'bias_mm': bias * 1000, 'n': len(common)}


def main():
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)

    plot_t0 = pd.Timestamp('2025-07-07 00:00')
    plot_t1 = pd.Timestamp('2025-07-12 12:00')

    for ax, stn in zip(axes, ['BocaNord', 'BocaSud', 'AltaVilaEst']):
        obs = load_obs(stn)
        obs_p = obs[plot_t0:plot_t1]
        ax.plot(obs_p.index, obs_p.values, color='black', lw=1.6, label='Observação (in-situ, 10-min)')

        legend_entries = []
        for run in RUNS:
            nc = VAL_DIR / run['file']
            if not nc.exists():
                continue
            ds = xr.open_dataset(nc)
            names = station_names(ds)
            if stn not in names:
                ds.close(); continue
            idx = names.index(stn)
            mod = ds.waterlevel.isel(station=idx).to_pandas()
            mod.index = pd.DatetimeIndex(mod.index)
            t0 = pd.Timestamp(run['t0'])
            t1 = pd.Timestamp(run['t1'])

            # Plot spinup transparent + post-spinup solid
            t_spinup_end = t0 + pd.Timedelta(hours=SPINUP_H)
            m_spin = mod[t0:t_spinup_end]
            m_post = mod[t_spinup_end:t1]
            ax.plot(m_spin.index, m_spin.values, color=run['color'], alpha=0.25, lw=1.0)
            ax.plot(m_post.index, m_post.values, color=run['color'], alpha=0.95, lw=1.2)

            # Metrics on post-spinup window
            metrics = metrics_for_run(mod, obs, t_spinup_end, t1)
            mtxt = ''
            if metrics:
                mtxt = f"r_anom={metrics['corr_anom']:+.2f}, RMSE_an={metrics['rmse_anom_mm']:+.0f}mm, bias={metrics['bias_mm']:+.0f}mm"
            legend_entries.append((run['color'], run['label'], mtxt))
            ds.close()

        # Custom legend
        handles = [plt.Line2D([0], [0], color='black', lw=1.6, label='Observação')]
        for color, lab, mtxt in legend_entries:
            handles.append(plt.Line2D([0], [0], color=color, lw=1.5, label=f'{lab}  ·  {mtxt}'))
        ax.legend(handles=handles, loc='lower left', fontsize=8, framealpha=0.9)

        ax.set_title(stn, loc='left', fontsize=11, fontweight='bold')
        ax.set_ylabel('WL (m)')
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='gray', lw=0.5)

    # Marks de restart dos chain iters (rst dates = N-2)
    for ax in axes:
        for rst in [pd.Timestamp('2025-07-08'), pd.Timestamp('2025-07-09'), pd.Timestamp('2025-07-10')]:
            ax.axvline(rst, color='gray', lw=0.4, linestyle=':', alpha=0.5)

    axes[-1].set_xlabel('Time (UTC)')
    axes[-1].xaxis.set_major_locator(mdates.DayLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    axes[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    axes[-1].set_xlim(plot_t0, plot_t1)

    fig.suptitle('Validação chain operacional Jul 2025 — 4 runs vs in-situ\n'
                 '(faded = spinup 12h descartado dos metrics; linhas verticais = restart events)',
                 fontsize=11, y=0.99)
    fig.tight_layout()
    fig.savefig(FIG, dpi=130, bbox_inches='tight')
    print(f'Saved: {FIG}')
    print(f'  size: {FIG.stat().st_size / 1024:.0f} KB')

    # === Segundo painel: skill bars (cleaner overview) ===
    df = pd.read_csv(VAL_DIR / 'metrics.csv')
    stations_order = ['BocaNord', 'BocaSud', 'AltaVilaEst']
    runs_order = ['d2025-07-10', 'd2025-07-10_n2', 'd2025-07-11_n2', 'd2025-07-12_n2']
    run_labels = {'d2025-07-10': 'N-3 nodm', 'd2025-07-10_n2': 'N-2 nodm',
                  'd2025-07-11_n2': 'N-2 chain J11', 'd2025-07-12_n2': 'N-2 chain J12'}
    colors = {'d2025-07-10': '#1f77b4', 'd2025-07-10_n2': '#2ca02c',
              'd2025-07-11_n2': '#d62728', 'd2025-07-12_n2': '#9467bd'}

    fig2, axs = plt.subplots(1, 3, figsize=(13, 4.5))
    for ax, metric, title, ylabel in zip(
        axs,
        ['corr_anom', 'rmse_anom_mm', 'bias_mm'],
        ['Correlação (anomalia, tide-free)', 'RMSE anomalia (mm)', 'Bias (mm)'],
        ['corr_anom', 'RMSE_anom (mm)', 'Bias (mm)'],
    ):
        x_pos = np.arange(len(stations_order))
        bar_w = 0.20
        for i, run in enumerate(runs_order):
            sub = df[df['run'] == run].set_index('station').reindex(stations_order)
            vals = sub[metric].values
            ax.bar(x_pos + (i - 1.5) * bar_w, vals, bar_w,
                   label=run_labels[run], color=colors[run], alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(stations_order, rotation=15, ha='right', fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(True, axis='y', alpha=0.3)
        ax.axhline(0, color='black', lw=0.5)
        if metric == 'corr_anom':
            ax.set_ylim(0, 1.0)
        ax.tick_params(axis='y', labelsize=8)

    axs[0].legend(loc='lower right', fontsize=8, framealpha=0.95)
    fig2.suptitle('Skill metrics por estação × run (drop spinup 12h)', fontsize=11, y=1.0)
    fig2.tight_layout()
    FIG2 = FIG.parent / 'validation_chain_skill_2026-06-03.png'
    fig2.savefig(FIG2, dpi=130, bbox_inches='tight')
    print(f'Saved: {FIG2}')
    print(f'  size: {FIG2.stat().st_size / 1024:.0f} KB')


if __name__ == '__main__':
    main()
