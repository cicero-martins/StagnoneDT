"""
WL skill comparison v03d (no D-Morph) vs v04AE (with D-Morph), same 9-day window.

Caveat: this is NOT a clean isolation of D-Morph effect — v04AE also has:
  - per-node Marettimo-anchored BC offset (v03d uses simpler BC)
  - AE-only wind blend (v03d uses an earlier blend or no blend)
  - Trapani port mesh patch (v04 added)
But for WL skill the dominant control is BC + wind; D-Morph could only affect
WL through bedlevel evolution changing tidal propagation. The point of this
comparison is therefore: 'do v04AE additions (including the noisy D-Morph)
hurt or help WL skill vs the v03d baseline?'

Stations: BocaNord, BocaSud, AltaVilaEst (his.nc direct).
Window: post-spinup (drop first sim-day).

Outputs:
  figs/wl_compare_v03d_v04AE.png
  data/processed/wl_compare_v03d_v04AE.csv
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

V03D_OUT = ROOT / 'model' / 'dflowfm_v03d' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
V04AE_OUT = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'

STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst']
SPINUP_DAYS = 1.0

RUNS = {'v03d (no D-Morph)': V03D_OUT, 'v04AE (D-Morph on)': V04AE_OUT}


def load_sim_wl(out_dir, station):
    for p in range(8):
        f = out_dir / f'Stagnone_dxy01_15m_{p:04d}_his.nc'
        if not f.exists():
            continue
        ds = xr.open_dataset(f)
        names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
                 for s in ds.station_name.values]
        if station not in names:
            continue
        i = names.index(station)
        wl = ds.waterlevel.isel(stations=i).to_pandas() if 'stations' in ds.waterlevel.dims \
             else ds.waterlevel.isel(station=i).to_pandas()
        wl.index = pd.to_datetime(wl.index)
        return wl
    return None


def load_obs(station):
    candidates = [PROC / f'wl_{station}_10min_UTC.csv',
                  PROC / f'wl_{station[:-3]}Est_10min_UTC.csv',
                  PROC / f'wl_{station.replace("AltaVila", "Altavila")}_10min_UTC.csv']
    for c in candidates:
        if c.exists():
            df = pd.read_csv(c, parse_dates=['datetime_utc'])
            return df.set_index('datetime_utc')['wl_m']
    return None


def stats(o, s):
    valid = (~o.isna()) & (~s.isna())
    o, s = o[valid].values, s[valid].values
    if len(o) < 3:
        return dict(n=len(o), rmse=np.nan, bias=np.nan, rmse_anom=np.nan,
                    corr=np.nan, std_ratio=np.nan)
    bias = (s - o).mean()
    rmse = np.sqrt(((s - o) ** 2).mean())
    o_a, s_a = o - o.mean(), s - s.mean()
    rmse_anom = np.sqrt(((s_a - o_a) ** 2).mean())
    corr = np.corrcoef(o_a, s_a)[0, 1] if o_a.std() > 0 else np.nan
    std_ratio = s.std() / o.std() if o.std() > 0 else np.nan
    return dict(n=len(o), rmse=rmse, bias=bias, rmse_anom=rmse_anom,
                corr=corr, std_ratio=std_ratio)


# ---- collect series per (run, station)
data = {}
for run, out_dir in RUNS.items():
    data[run] = {}
    for st in STATIONS:
        sim = load_sim_wl(out_dir, st)
        if sim is None:
            print(f'WARN {run}/{st}: missing sim')
        data[run][st] = sim

obs_by_st = {st: load_obs(st) for st in STATIONS}
for st, ob in obs_by_st.items():
    if ob is None:
        print(f'WARN: obs missing for {st}')

# common window from any run that has data
t_starts, t_ends = [], []
for run in RUNS:
    for st in STATIONS:
        s = data[run][st]
        if s is not None:
            t_starts.append(s.index.min())
            t_ends.append(s.index.max())
t0_raw = max(t_starts)
tF = min(t_ends)
t0 = t0_raw + pd.Timedelta(days=SPINUP_DAYS)
print(f'Common window:     {t0_raw} -> {tF}')
print(f'Validation window: {t0} -> {tF}\n')

rows = []
for run in RUNS:
    for st in STATIONS:
        sim = data[run][st]
        ob = obs_by_st.get(st)
        if sim is None or ob is None:
            continue
        ob_i = ob.reindex(sim.index, method='nearest', tolerance=pd.Timedelta('15min'))
        m = stats(ob_i.loc[t0:tF], sim.loc[t0:tF])
        m['run'] = run; m['station'] = st
        rows.append(m)
df = pd.DataFrame(rows)[['run', 'station', 'n', 'rmse', 'bias',
                          'rmse_anom', 'corr', 'std_ratio']]
csv = PROC / 'wl_compare_v03d_v04AE.csv'
df.to_csv(csv, index=False, float_format='%.4f')
print('Per-run / station metrics (post-spinup):')
print(df.to_string(index=False))
print(f'\nSaved {csv}')

# delta table
delta_rows = []
piv_rmse = df.pivot(index='station', columns='run', values='rmse')
piv_bias = df.pivot(index='station', columns='run', values='bias')
piv_anom = df.pivot(index='station', columns='run', values='rmse_anom')
piv_corr = df.pivot(index='station', columns='run', values='corr')
print('\nDelta v04AE - v03d:')
for st in STATIONS:
    d_rmse = piv_rmse.loc[st, 'v04AE (D-Morph on)'] - piv_rmse.loc[st, 'v03d (no D-Morph)']
    d_bias = piv_bias.loc[st, 'v04AE (D-Morph on)'] - piv_bias.loc[st, 'v03d (no D-Morph)']
    d_anom = piv_anom.loc[st, 'v04AE (D-Morph on)'] - piv_anom.loc[st, 'v03d (no D-Morph)']
    d_corr = piv_corr.loc[st, 'v04AE (D-Morph on)'] - piv_corr.loc[st, 'v03d (no D-Morph)']
    print(f'  {st}:  dRMSE={d_rmse:+.4f}  dbias={d_bias:+.4f}  '
          f'dRMSE_anom={d_anom:+.4f}  dcorr={d_corr:+.3f}')

# plot
fig, axes = plt.subplots(len(STATIONS), 1, figsize=(13, 3.2 * len(STATIONS)),
                         sharex=True)
for ax, st in zip(axes, STATIONS):
    ob = obs_by_st.get(st)
    if ob is not None:
        ax.plot(ob.index, ob.values, color='black', lw=1.0, alpha=0.8,
                label='obs')
    for run, color in [('v03d (no D-Morph)', 'tab:blue'),
                       ('v04AE (D-Morph on)', 'tab:red')]:
        sim = data[run][st]
        if sim is not None:
            ax.plot(sim.index, sim.values, color=color, lw=1.0,
                    alpha=0.85, label=run)
    ax.axvline(t0, color='gray', ls='--', alpha=0.6, lw=0.8,
               label=f'spinup +{SPINUP_DAYS}d')
    # add metrics for both in title
    title_bits = [st]
    sub = df[df.station == st]
    for run, short in [('v03d (no D-Morph)', 'v03d'),
                       ('v04AE (D-Morph on)', 'v04AE')]:
        r = sub[sub.run == run]
        if not r.empty:
            r = r.iloc[0]
            title_bits.append(f'{short}: RMSE={r["rmse"]:.3f} '
                              f'bias={r["bias"]:+.3f} '
                              f'anom={r["rmse_anom"]:.3f} '
                              f'corr={r["corr"]:.3f}')
    ax.set_title('  |  '.join(title_bits), fontsize=10)
    ax.set_ylabel('WL [m]')
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right', fontsize=8)

axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
axes[-1].set_xlabel('date')
plt.tight_layout()
out_png = FIG / 'wl_compare_v03d_v04AE.png'
plt.savefig(out_png, dpi=140, bbox_inches='tight')
print(f'\nSaved {out_png}')
