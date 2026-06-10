"""
WL validation for v04AE_vr (Baptist variable roughness) vs v04AE baseline.

Same methodology as validate_v04AE_wl.py:
  - Stations: BocaNord, BocaSud, AltaVilaEst (his.nc direct)
  - Post-spinup window: T_start + 1d -> T_end
  - Metrics: RMSE, bias, RMSE_anom, corr, std_ratio

Outputs:
  figures/v04AE_vr_wl_validation.png   -- 3-panel obs+VR+baseline
  data/processed/v04AE_vr_wl_metrics.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT   = Path(__file__).resolve().parents[1]
PROC   = ROOT / 'data' / 'processed'
FIG    = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

VR_DIR = ROOT / 'model' / 'dflowfm_v04AE_vr' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
BL_DIR = ROOT / 'model' / 'dflowfm_v04AE'    / 'DFM_OUTPUT_Stagnone_dxy01_15m'

STATIONS   = ['BocaNord', 'BocaSud', 'AltaVilaEst']
SPINUP_DAYS = 1.0


def load_sim_wl(out_dir: Path, station: str) -> pd.Series | None:
    for p in range(8):
        f = out_dir / f'Stagnone_dxy01_15m_{p:04d}_his.nc'
        if not f.exists():
            continue
        ds = xr.open_dataset(f)
        if 'station_name' not in ds:
            continue
        names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
                 for s in ds.station_name.values]
        if station not in names:
            continue
        i = names.index(station)
        dim = 'stations' if 'stations' in ds.waterlevel.dims else 'station'
        wl = ds.waterlevel.isel({dim: i}).to_pandas()
        wl.index = pd.to_datetime(wl.index)
        return wl
    return None


def load_obs(station: str) -> pd.Series | None:
    name_alt = {'AltaVilaEst': 'Altavila'}.get(station, station)
    for cand in [
        PROC / f'wl_{station}_10min_UTC.csv',
        PROC / f'wl_{name_alt}Est_10min_UTC.csv',
        PROC / f'wl_{name_alt}_10min_UTC.csv',
        PROC / f'insitu_2025-26' / f'{station}_wl.csv',
    ]:
        if cand.exists():
            df = pd.read_csv(cand, parse_dates=[0])
            df.columns = df.columns.str.strip()
            time_col = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()][0]
            wl_col   = [c for c in df.columns if 'wl' in c.lower() or 'level' in c.lower()
                        or 'water' in c.lower()][0]
            s = df.set_index(time_col)[wl_col]
            s.index = pd.to_datetime(s.index)
            s.name = station
            return s
    return None


def stats(obs: pd.Series, sim: pd.Series) -> dict:
    valid = (~obs.isna()) & (~sim.isna())
    o, s = obs[valid].values, sim[valid].values
    if len(o) < 3:
        return dict(n=len(o), rmse=np.nan, bias=np.nan, rmse_anom=np.nan,
                    corr=np.nan, std_ratio=np.nan)
    bias      = (s - o).mean()
    rmse      = np.sqrt(((s - o) ** 2).mean())
    o_a       = o - o.mean()
    s_a       = s - s.mean()
    rmse_anom = np.sqrt(((s_a - o_a) ** 2).mean())
    corr      = np.corrcoef(o_a, s_a)[0, 1] if o_a.std() > 0 else np.nan
    std_ratio = s.std() / o.std() if o.std() > 0 else np.nan
    return dict(n=len(o), rmse=rmse, bias=bias, rmse_anom=rmse_anom,
                corr=corr, std_ratio=std_ratio)


def main():
    # ── load data ────────────────────────────────────────────────────────────
    data = {}   # station -> (obs, sim_vr, sim_bl)
    for st in STATIONS:
        sim_vr = load_sim_wl(VR_DIR, st)
        sim_bl = load_sim_wl(BL_DIR, st)
        obs    = load_obs(st)
        if sim_vr is None:
            print(f'WARN  {st}: his.nc not found in {VR_DIR}')
            continue
        if obs is None:
            print(f'WARN  {st}: obs CSV not found')
            continue
        data[st] = (obs, sim_vr, sim_bl)

    if not data:
        print('ERROR: no data loaded'); return

    # ── common time window ────────────────────────────────────────────────────
    t0_raw = max(s.index.min() for _, s, _ in data.values())
    tF     = min(s.index.max() for _, s, _ in data.values())
    t0     = t0_raw + pd.Timedelta(days=SPINUP_DAYS)
    print(f'Sim window:        {t0_raw} -> {tF}')
    print(f'Validation window: {t0} -> {tF}  (drop first {SPINUP_DAYS} d spinup)\n')

    # ── metrics ───────────────────────────────────────────────────────────────
    rows = []
    for st, (obs, sim_vr, sim_bl) in data.items():
        obs_i  = obs.reindex(sim_vr.index, method='nearest',
                             tolerance=pd.Timedelta('15min'))
        obs_w  = obs_i.loc[t0:tF]
        vr_w   = sim_vr.loc[t0:tF]

        m_vr = stats(obs_w, vr_w)
        m_vr.update(station=st, run='v04AE_vr')
        rows.append(m_vr)

        if sim_bl is not None:
            bl_w = sim_bl.loc[t0:tF]
            m_bl = stats(obs_w, bl_w)
            m_bl.update(station=st, run='v04AE')
            rows.append(m_bl)

        delta = f'  DELTA_bias={(m_vr["bias"] - rows[-1]["bias"]):+.4f}  DELTA_RMSE={(m_vr["rmse"] - rows[-1]["rmse"]):+.4f}' \
                if sim_bl is not None and len(rows) >= 2 else ''
        print(f'{st}  [VR]  RMSE={m_vr["rmse"]:.4f}  bias={m_vr["bias"]:+.4f}  '
              f'RMSE_anom={m_vr["rmse_anom"]:.4f}  corr={m_vr["corr"]:.3f}{delta}')

    df_m = pd.DataFrame(rows)[['station', 'run', 'n', 'rmse', 'bias',
                                'rmse_anom', 'corr', 'std_ratio']]
    csv = PROC / 'v04AE_vr_wl_metrics.csv'
    df_m.to_csv(csv, index=False, float_format='%.4f')
    print(f'\nSaved {csv}')

    # ── plot ──────────────────────────────────────────────────────────────────
    n_st = len(data)
    fig, axes = plt.subplots(n_st, 1, figsize=(14, 3.2 * n_st), sharex=True)
    if n_st == 1:
        axes = [axes]

    for ax, (st, (obs, sim_vr, sim_bl)) in zip(axes, data.items()):
        obs_i = obs.reindex(sim_vr.index, method='nearest',
                            tolerance=pd.Timedelta('15min'))
        ax.plot(obs_i.index, obs_i.values, color='tab:gray', lw=1.0,
                label='obs', zorder=3)
        if sim_bl is not None:
            ax.plot(sim_bl.index, sim_bl.values, color='tab:blue', lw=0.9,
                    alpha=0.7, label='v04AE (no VR)', zorder=2)
        ax.plot(sim_vr.index, sim_vr.values, color='tab:orange', lw=1.0,
                label='v04AE_vr (Baptist VR)', zorder=4)
        ax.axvline(t0, color='black', ls='--', lw=0.8, alpha=0.5,
                   label=f'spinup +{SPINUP_DAYS}d')

        row_vr = df_m.query('station == @st and run == "v04AE_vr"')
        row_bl = df_m.query('station == @st and run == "v04AE"')
        title  = f'{st}  [VR]  RMSE={row_vr["rmse"].iloc[0]:.3f} m  ' \
                 f'bias={row_vr["bias"].iloc[0]:+.3f} m  ' \
                 f'RMSE_anom={row_vr["rmse_anom"].iloc[0]:.3f} m  ' \
                 f'corr={row_vr["corr"].iloc[0]:.3f}'
        if not row_bl.empty:
            title += (f'   ||  [BL] RMSE={row_bl["rmse"].iloc[0]:.3f}  '
                      f'corr={row_bl["corr"].iloc[0]:.3f}')
        ax.set_title(title, fontsize=9)
        ax.set_ylabel('WL [m]')
        ax.grid(alpha=0.3)
        ax.legend(loc='upper right', fontsize=8)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
    axes[-1].set_xlabel('date (UTC)')
    plt.tight_layout()
    out = FIG / 'v04AE_vr_wl_validation.png'
    plt.savefig(out, dpi=140, bbox_inches='tight')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
