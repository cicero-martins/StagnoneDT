"""Compare WL at the 3 lagoon stations between v03 (HDF5 wave bug -> waves
effectively stuck = wave-coupling-OFF) and v04 (waves working).

Both runs cover Jul 1-10 2025 9-day window. v03 only saved one partition
(his.nc has all stations regardless), v04 has 8 partitions. Both have
BocaNord, BocaSud, AltaVilaEst as obs points.

Output: figures/v03_vs_v04_wl_compare.png + metrics CSV.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import netCDF4 as nc
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V03_HIS = PROJECT_ROOT / 'model' / 'dflowfm_v03' / 'output' / 'Stagnone_dxy01_15m_0000_his.nc'
V04_HIS_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
V04_HIS = sorted(V04_HIS_DIR.glob('Stagnone_dxy01_15m_000?_his.nc'))
FIG = PROJECT_ROOT / 'figures'

OBS_FILES = {
    'BocaNord': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'boundaries_BN.csv',
    'BocaSud': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'boundaries_BS.csv',
    'AltaVilaEst': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'boundaries_AE.csv',
}

T_MIN = pd.Timestamp('2025-07-02 00:00')  # post-spinup
T_MAX = pd.Timestamp('2025-07-10 00:00')


def _decode_names(arr):
    return [b.tobytes().decode('utf-8', errors='replace').rstrip('\x00').strip() for b in arr]


def _read_his(fn) -> tuple[pd.DatetimeIndex, dict[str, np.ndarray]]:
    ds = nc.Dataset(fn)
    names = _decode_names(ds.variables['station_name'][:])
    t = ds.variables['time']
    times = pd.to_datetime(nc.num2date(t[:], t.units, only_use_cftime_datetimes=False))
    wl = ds.variables['waterlevel']
    out = {}
    for i, name in enumerate(names):
        out[name] = np.asarray(wl[:, i])
    ds.close()
    return times, out


def _load_v04_his(stations: list[str]) -> dict[str, pd.Series]:
    """Concatenate from 8 partitions, picking first non-NaN value per (station, t)."""
    series = {s: None for s in stations}
    for fn in V04_HIS:
        times, out = _read_his(fn)
        for s in stations:
            if s in out:
                arr = out[s]
                arr = np.where((arr > -10) & (arr < 10), arr, np.nan)
                cur = pd.Series(arr, index=times)
                if series[s] is None:
                    series[s] = cur
                else:
                    series[s] = series[s].combine_first(cur)
    return {s: v.dropna() for s, v in series.items() if v is not None}


def _load_obs(sname: str) -> pd.Series:
    p = OBS_FILES[sname]
    df = pd.read_csv(p, encoding='utf-8-sig')
    tcol = df.columns[0]; vcol = df.columns[1]
    df['t_local'] = pd.to_datetime(df[tcol], dayfirst=False, errors='coerce')
    df = df.dropna(subset=['t_local'])
    df['t'] = df['t_local'] - pd.Timedelta(hours=1)  # CET solare -> UTC
    df[vcol] = pd.to_numeric(df[vcol], errors='coerce')
    return df.set_index('t')[vcol].dropna().loc[T_MIN:T_MAX]


def _metrics(mod: pd.Series, obs: pd.Series) -> dict:
    obs_r = obs.reindex(mod.index, method='nearest', tolerance=pd.Timedelta('30min'))
    al = pd.concat([mod.rename('mod'), obs_r.rename('obs')], axis=1).dropna()
    if len(al) < 10:
        return {}
    diff = al['mod'] - al['obs']
    bias = float(diff.mean()); rmse = float(np.sqrt((diff ** 2).mean()))
    corr = float(al['mod'].corr(al['obs']))
    ma = al['mod'] - al['mod'].mean(); oa = al['obs'] - al['obs'].mean()
    rmse_anom = float(np.sqrt(((ma - oa) ** 2).mean()))
    return {'n': len(al), 'rmse_raw': rmse, 'bias': bias, 'corr_raw': corr,
            'rmse_anom': rmse_anom, 'std_mod': float(al['mod'].std()),
            'std_obs': float(al['obs'].std()),
            'std_ratio': float(al['mod'].std() / al['obs'].std())}


def main() -> int:
    stations = ['BocaNord', 'BocaSud', 'AltaVilaEst']

    # v03 (single his.nc)
    v03_times, v03_wl = _read_his(V03_HIS)
    v03_series = {}
    for s in stations:
        if s in v03_wl:
            arr = v03_wl[s]
            arr = np.where((arr > -10) & (arr < 10), arr, np.nan)
            v03_series[s] = pd.Series(arr, index=v03_times).dropna().loc[T_MIN:T_MAX]
    print(f'v03 stations loaded: {list(v03_series.keys())}')

    # v04 (8 his.nc)
    v04_series = _load_v04_his(stations)
    v04_series = {s: v.loc[T_MIN:T_MAX] for s, v in v04_series.items()}
    print(f'v04 stations loaded: {list(v04_series.keys())}')

    # Plot
    fig, axes = plt.subplots(len(stations), 2, figsize=(16, 9), sharex=True)
    rows = []
    for row, sname in enumerate(stations):
        ax_raw = axes[row, 0]
        ax_anom = axes[row, 1]
        obs = _load_obs(sname)
        v03 = v03_series.get(sname)
        v04 = v04_series.get(sname)

        # RAW
        ax_raw.plot(obs.index, obs.values, color='#3a7bd5', lw=0.7, alpha=0.7, label='obs')
        if v03 is not None:
            ax_raw.plot(v03.index, v03.values, color='#888888', lw=0.9, alpha=0.85,
                        label='v03 (no functional waves)')
            m03 = _metrics(v03, obs)
        else:
            m03 = {}
        if v04 is not None:
            ax_raw.plot(v04.index, v04.values, color='#d96b0d', lw=0.9, alpha=0.85,
                        label='v04 (waves working)')
            m04 = _metrics(v04, obs)
        else:
            m04 = {}
        ax_raw.set_title(
            f'{sname} | v03 RMSE={m03.get("rmse_raw", float("nan")):.3f} bias={m03.get("bias", float("nan")):+.3f}'
            f' | v04 RMSE={m04.get("rmse_raw", float("nan")):.3f} bias={m04.get("bias", float("nan")):+.3f}',
            fontsize=9,
        )
        ax_raw.set_ylabel('WL [m]')
        ax_raw.grid(alpha=0.3)
        ax_raw.legend(loc='upper left', fontsize=8)

        # ANOMALY (mean-removed in window)
        if v03 is not None:
            v03a = v03 - v03.mean()
            ax_anom.plot(v03a.index, v03a.values, color='#888888', lw=0.9, alpha=0.85,
                         label='v03 anomaly')
        obs_a = obs - obs.mean()
        ax_anom.plot(obs_a.index, obs_a.values, color='#3a7bd5', lw=0.7, alpha=0.7,
                     label='obs anomaly')
        if v04 is not None:
            v04a = v04 - v04.mean()
            ax_anom.plot(v04a.index, v04a.values, color='#d96b0d', lw=0.9, alpha=0.85,
                         label='v04 anomaly')
        ax_anom.axhline(0, color='gray', lw=0.5)
        ax_anom.set_title(
            f'{sname} anomaly | v03 RMSE_anom={m03.get("rmse_anom", float("nan")):.3f} '
            f'r={m03.get("corr_raw", float("nan")):.2f} std_ratio={m03.get("std_ratio", float("nan")):.2f}'
            f' | v04 RMSE_anom={m04.get("rmse_anom", float("nan")):.3f} '
            f'r={m04.get("corr_raw", float("nan")):.2f} std_ratio={m04.get("std_ratio", float("nan")):.2f}',
            fontsize=9,
        )
        ax_anom.set_ylabel('WL anomaly [m]')
        ax_anom.grid(alpha=0.3)
        ax_anom.legend(loc='upper left', fontsize=8)

        for tag, m in [('v03', m03), ('v04', m04)]:
            if m:
                rows.append({'station': sname, 'version': tag, **m})

    for row in range(len(stations)):
        for col in range(2):
            axes[row, col].set_xlim(T_MIN, T_MAX)
    for col in range(2):
        axes[-1, col].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.suptitle('v03 (HDF5 bug -> wave coupling stuck) vs v04 (waves working) — '
                 'Jul 2-10 2025 (post-spinup)', fontsize=12)
    fig.tight_layout()
    out_fig = FIG / 'v03_vs_v04_wl_compare.png'
    fig.savefig(out_fig, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'saved {out_fig}')

    df = pd.DataFrame(rows)
    if len(df):
        df_pivot = df.pivot(index='station', columns='version',
                            values=['rmse_raw', 'bias', 'rmse_anom', 'corr_raw', 'std_ratio'])
        print()
        print(df_pivot.to_string(float_format=lambda x: f'{x:+.4f}'))
        out_csv = PROJECT_ROOT / 'data' / 'processed' / 'compare_v03_vs_v04_wl.csv'
        df.to_csv(out_csv, index=False)
        print(f'saved {out_csv}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
