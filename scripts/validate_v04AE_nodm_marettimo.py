"""Marettimo offshore WL validation for v04AE_nodm coupled 9-day run,
side-by-side with v04AE. Extends the in-situ validation
[validate_v04AE_nodm_wl.py] with offshore signal preservation.

Cell selection: v03d-compatible target (12.0753, 37.9747) with bl < -0.3 m
(memory marettimo_validation_cell — the literal nearest cell to the JRC TAD658
gauge falls in the lee of Marettimo and flat-lines).

Reports raw RMSE + bias + RMSE_anom + corr per CLAUDE.md validation philosophy.

Outputs:
  figures/v04AE_nodm_vs_v04AE_marettimo_validation.png
  data/processed/v04AE_nodm_marettimo_metrics.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd
import netCDF4 as nc
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
OBS_CSV = ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'
TARGET_LON, TARGET_LAT = 12.0753, 37.9747
BL_MAX, BL_MIN = -0.3, -50.0
SPINUP_DAYS = 1.0


def find_cell(out_dir):
    """Find cell closest to v03d anchor (12.0753, 37.9747) with bl<-0.3m."""
    best = None
    for p in range(8):
        fn = out_dir / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not fn.exists():
            continue
        ds = nc.Dataset(fn)
        fx = ds.variables['mesh2d_face_x'][:]
        fy = ds.variables['mesh2d_face_y'][:]
        bl = ds.variables['mesh2d_flowelem_bl'][:]
        d_km = np.sqrt((fx - TARGET_LON) ** 2 + (fy - TARGET_LAT) ** 2) * 111
        ok = (bl < BL_MAX) & (bl > BL_MIN)
        ds.close()
        if not ok.any():
            continue
        d_ok = np.where(ok, d_km, np.inf)
        idx = int(np.argmin(d_ok))
        cand = dict(d_km=float(d_ok[idx]), partition=p, idx=idx,
                    lon=float(fx[idx]), lat=float(fy[idx]),
                    bl=float(bl[idx]), file=fn)
        if best is None or cand['d_km'] < best['d_km']:
            best = cand
    return best


def extract_wl(cell):
    ds = nc.Dataset(cell['file'])
    t = ds.variables['time']
    times = pd.to_datetime(nc.num2date(t[:], t.units,
                                       only_use_cftime_datetimes=False))
    s1 = np.asarray(ds.variables['mesh2d_s1'][:, cell['idx']])
    ds.close()
    s1 = np.where((s1 > -10) & (s1 < 10), s1, np.nan)
    return pd.Series(s1, index=times).dropna()


def load_obs():
    df = pd.read_csv(OBS_CSV)
    df['t'] = pd.to_datetime(df['Time(UTC)'])
    return df.set_index('t')['wl_m'].dropna()


def metrics(o, s):
    valid = (~o.isna()) & (~s.isna())
    o, s = o[valid].values, s[valid].values
    if len(o) < 3:
        return dict(n=len(o), rmse=np.nan, bias=np.nan, rmse_anom=np.nan,
                    corr=np.nan, std_ratio=np.nan, willmott=np.nan)
    bias = (s - o).mean()
    rmse = np.sqrt(((s - o) ** 2).mean())
    o_a = o - o.mean(); s_a = s - s.mean()
    rmse_anom = np.sqrt(((s_a - o_a) ** 2).mean())
    corr = float(np.corrcoef(o_a, s_a)[0, 1]) if o_a.std() > 0 else np.nan
    o_mean = o.mean()
    denom = float(np.sum((np.abs(s - o_mean) + np.abs(o - o_mean)) ** 2))
    willmott = 1 - float(np.sum((s - o) ** 2)) / denom if denom > 0 else np.nan
    std_ratio = s.std() / o.std() if o.std() > 0 else np.nan
    return dict(n=len(o), rmse=rmse, bias=bias, rmse_anom=rmse_anom,
                corr=corr, std_ratio=std_ratio, willmott=willmott)


def main():
    obs = load_obs()
    print(f'obs Marettimo: {len(obs)} samples from {obs.index[0]} to {obs.index[-1]}')

    out_rows = []
    runs_data = {}
    for run, out_dir in RUNS.items():
        cell = find_cell(out_dir)
        if cell is None:
            print(f'WARN {run}: no Marettimo cell')
            continue
        print(f'\n{run} cell: part {cell["partition"]} idx {cell["idx"]} '
              f'({cell["lon"]:.4f}, {cell["lat"]:.4f}) bl={cell["bl"]:.2f}m '
              f'dist_to_anchor={cell["d_km"]:.2f}km')
        sim = extract_wl(cell)
        print(f'  sim WL: {len(sim)} samples, {sim.index[0]} -> {sim.index[-1]}')

        # Window: post-spinup
        t0_raw = sim.index.min()
        tF = sim.index.max()
        t0 = t0_raw + pd.Timedelta(days=SPINUP_DAYS)

        # Resample obs to sim grid
        obs_i = obs.reindex(sim.index, method='nearest',
                            tolerance=pd.Timedelta('15min'))

        runs_data[run] = dict(sim=sim, obs=obs_i, cell=cell, t0=t0, tF=tF)

        for win_label, t_start in [('post-spinup', t0), ('full', t0_raw)]:
            m = metrics(obs_i.loc[t_start:tF], sim.loc[t_start:tF])
            m.update(run=run, window=win_label,
                     cell_lon=cell['lon'], cell_lat=cell['lat'],
                     cell_bl=cell['bl'], dist_to_anchor_km=cell['d_km'])
            out_rows.append(m)

    df = pd.DataFrame(out_rows)[
        ['run', 'window', 'n', 'rmse', 'bias', 'rmse_anom', 'corr', 'willmott',
         'std_ratio', 'cell_lon', 'cell_lat', 'cell_bl', 'dist_to_anchor_km']]
    print('\n=== Metrics ===')
    print(df.to_string(index=False, float_format='%.4f'))

    csv = PROC / 'v04AE_nodm_marettimo_metrics.csv'
    df.to_csv(csv, index=False, float_format='%.4f')
    print(f'\nSaved {csv}')

    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(13, 6.5), sharex=True)
    colors = {'v04AE': 'tab:red', 'v04AE_nodm': 'tab:blue'}

    # Top: raw WL
    ax = axes[0]
    obs_plot = obs.loc[runs_data['v04AE']['sim'].index[0]:runs_data['v04AE']['sim'].index[-1]]
    ax.plot(obs_plot.index, obs_plot.values, color='black', lw=0.9, label='Marettimo obs')
    for run, d in runs_data.items():
        sim = d['sim']
        row = df.query('run == @run and window == "post-spinup"').iloc[0]
        ax.plot(sim.index, sim.values, color=colors[run], lw=0.9,
                label=f'{run}  RMSE={row["rmse"]:.3f} bias={row["bias"]:+.3f} '
                      f'corr={row["corr"]:.3f}')
        ax.axvline(d['t0'], color='gray', ls='--', alpha=0.6, lw=0.7)
    ax.set_ylabel('WL [m]')
    ax.set_title('Marettimo offshore — raw WL')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(alpha=0.3)

    # Bottom: anomaly (mean-removed)
    ax = axes[1]
    obs_anom_plot = obs_plot - obs_plot.mean()
    ax.plot(obs_anom_plot.index, obs_anom_plot.values, color='black', lw=0.9,
            label='Marettimo obs (anom)')
    for run, d in runs_data.items():
        sim = d['sim']
        sim_anom = sim - sim.mean()
        row = df.query('run == @run and window == "post-spinup"').iloc[0]
        ax.plot(sim_anom.index, sim_anom.values, color=colors[run], lw=0.9,
                label=f'{run}  RMSE_anom={row["rmse_anom"]:.3f}')
    ax.set_ylabel('WL anomaly [m]')
    ax.set_title('Marettimo offshore — anomaly (mean-removed)')
    ax.set_xlabel('date (UTC)')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(alpha=0.3)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))

    plt.suptitle('Marettimo offshore WL: v04AE (D-Morph on) vs v04AE_nodm '
                 '(D-Morph off) vs JRC TAD 658', y=1.005, fontsize=11)
    plt.tight_layout()
    out = FIG / 'v04AE_nodm_vs_v04AE_marettimo_validation.png'
    plt.savefig(out, dpi=140, bbox_inches='tight')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
