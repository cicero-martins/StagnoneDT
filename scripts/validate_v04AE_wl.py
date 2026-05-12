"""
WL validation for v04AE coupled 9-day run.

Stations (his.nc direct): BocaNord, BocaSud, AltaVilaEst.
Obs: data/processed/wl_<station>_10min_UTC.csv  (columns: datetime_utc, wl_m)

Per CLAUDE.md validation philosophy:
  - report raw RMSE + bias + RMSE_anom + corr  (RMSE^2 = bias^2 + RMSE_anom^2)
  - drop the first sim-day as spinup (T_MIN+1d -> T_MAX)
  - the bias tells about datum/offset error, RMSE_anom is the dynamic skill

Outputs:
  figs/v04AE_wl_validation.png
  data/processed/v04AE_wl_metrics.csv
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
OUT_DIR = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst']

# Sim window: Jul 1 -> Jul 10. Drop first day as spinup -> Jul 2 -> Jul 10.
SPINUP_DAYS = 1.0


def load_sim_wl(station):
    """Walk through partitions until the station is found in his.nc."""
    for p in range(8):
        f = OUT_DIR / f'Stagnone_dxy01_15m_{p:04d}_his.nc'
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
    """Map AltaVilaEst -> Altavila (csv has lowercase)."""
    name = {'AltaVilaEst': 'Altavila'}.get(station, station)
    candidates = [PROC / f'wl_{station}_10min_UTC.csv',
                  PROC / f'wl_{name}Est_10min_UTC.csv',
                  PROC / f'wl_{name}_10min_UTC.csv']
    for c in candidates:
        if c.exists():
            df = pd.read_csv(c, parse_dates=['datetime_utc'])
            df = df.rename(columns={'datetime_utc': 'time', 'wl_m': 'wl'})
            df = df.set_index('time')['wl']
            return df
    return None


def stats(o, s):
    valid = (~o.isna()) & (~s.isna())
    o, s = o[valid].values, s[valid].values
    if len(o) < 3:
        return dict(n=len(o), rmse=np.nan, bias=np.nan, rmse_anom=np.nan,
                    corr=np.nan, std_ratio=np.nan)
    bias = (s - o).mean()
    rmse = np.sqrt(((s - o) ** 2).mean())
    o_anom = o - o.mean()
    s_anom = s - s.mean()
    rmse_anom = np.sqrt(((s_anom - o_anom) ** 2).mean())
    corr = np.corrcoef(o_anom, s_anom)[0, 1] if o_anom.std() > 0 else np.nan
    std_ratio = s.std() / o.std() if o.std() > 0 else np.nan
    return dict(n=len(o), rmse=rmse, bias=bias, rmse_anom=rmse_anom,
                corr=corr, std_ratio=std_ratio)


def main():
    # collect per-station sim + obs
    pairs = {}
    for st in STATIONS:
        sim = load_sim_wl(st)
        obs = load_obs(st)
        if sim is None or obs is None:
            print(f'WARN {st}: sim={sim is None} obs={obs is None}')
            continue
        # interpolate obs onto sim timestamps (more robust than the reverse)
        obs_i = obs.reindex(sim.index, method='nearest', tolerance=pd.Timedelta('15min'))
        pairs[st] = (sim, obs_i)

    # determine common time window across all stations
    t_starts = [v[0].index.min() for v in pairs.values()]
    t_ends = [v[0].index.max() for v in pairs.values()]
    t0_raw = max(t_starts) if t_starts else None
    tF = min(t_ends) if t_ends else None
    t0 = t0_raw + pd.Timedelta(days=SPINUP_DAYS)
    print(f'Sim window:        {t0_raw} -> {tF}')
    print(f'Validation window: {t0} -> {tF} (drop first {SPINUP_DAYS} day spinup)\n')

    # compute metrics
    rows = []
    for st, (sim, obs) in pairs.items():
        sim_w = sim.loc[t0:tF]
        obs_w = obs.loc[t0:tF]
        m_raw = stats(obs.loc[t0_raw:tF], sim.loc[t0_raw:tF])
        m = stats(obs_w, sim_w)
        m['station'] = st
        m['window'] = 'post-spinup'
        m_raw['station'] = st
        m_raw['window'] = 'full'
        rows.append(m)
        rows.append(m_raw)
        print(f'{st}:  n={m["n"]}  '
              f'RMSE={m["rmse"]:.4f}  bias={m["bias"]:+.4f}  '
              f'RMSE_anom={m["rmse_anom"]:.4f}  '
              f'corr={m["corr"]:.3f}  std_s/std_o={m["std_ratio"]:.2f}')

    df = pd.DataFrame(rows)[['station', 'window', 'n', 'rmse', 'bias',
                              'rmse_anom', 'corr', 'std_ratio']]
    csv = PROC / 'v04AE_wl_metrics.csv'
    df.to_csv(csv, index=False, float_format='%.4f')
    print(f'\nSaved {csv}')

    # ---- plot
    fig, axes = plt.subplots(len(pairs), 1, figsize=(13, 3 * len(pairs)),
                             sharex=True)
    if len(pairs) == 1:
        axes = [axes]
    for ax, (st, (sim, obs)) in zip(axes, pairs.items()):
        ax.plot(obs.index, obs.values, color='tab:gray', lw=1.0, label='obs')
        ax.plot(sim.index, sim.values, color='tab:red', lw=1.0,
                label='v04AE coupled')
        ax.axvline(t0, color='black', ls='--', alpha=0.6, lw=0.8,
                   label=f'spinup cutoff (+{SPINUP_DAYS}d)')
        m_row = df.query('station == @st and window == "post-spinup"').iloc[0]
        ax.set_title(f'{st}  RMSE={m_row["rmse"]:.3f} m  '
                     f'bias={m_row["bias"]:+.3f} m  '
                     f'RMSE_anom={m_row["rmse_anom"]:.3f} m  '
                     f'corr={m_row["corr"]:.3f}')
        ax.set_ylabel('WL [m]')
        ax.grid(alpha=0.3)
        ax.legend(loc='upper right', fontsize=8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
    axes[-1].set_xlabel('date')
    plt.tight_layout()
    out = FIG / 'v04AE_wl_validation.png'
    plt.savefig(out, dpi=140, bbox_inches='tight')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
