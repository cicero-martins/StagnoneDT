"""Gauges and paired drifter skill of no-waves test runs against each other.

Each run is named by the tag of its drifter files,
data/processed/drifter_metrics_v04AE_nowaves_<tag>.csv, and of its history
file, data/processed/qt_family_his/<tag>_his.nc (partition 0 of the run,
which holds every station). Water level is compared with the gauges after
the first day, as bias, anomaly RMSE and correlation (RMSE^2 = bias^2 +
RMSE_anom^2). Drifter skill is the Liu-Weisberg score of
drifter_validation_member.py, compared drifter by drifter between
consecutive runs of the list, with the standard error of the paired mean.

Usage:
    python compare_nowaves_test_runs.py bed26_cfl05 qtL60_cfl05 qtL30_cfl05 qtL15_cfl05
    python compare_nowaves_test_runs.py v04bed_cfl05 v04bed_cfl05_L10_hmf v04bed_cfl05_L20_hmf
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_v04AE_nodm_wl import load_obs, metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HIS = ROOT / 'data/processed/qt_family_his/{}_his.nc'
DRIFT = ROOT / 'data/processed/drifter_metrics_v04AE_nowaves_{}.csv'
GAUGES = ('BocaNord', 'BocaSud', 'AltaVilaEst')


def gauges(run):
    ds = xr.open_dataset(str(HIS).format(run))
    names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip() for s in ds.station_name.values]
    wl = pd.DataFrame(ds.waterlevel.values, index=pd.to_datetime(ds.time.values), columns=names)
    wl = wl.loc[wl.index[0] + pd.Timedelta(days=1):]
    rows = []
    for st in GAUGES:
        o = load_obs(st).reindex(wl.index, method='nearest', tolerance=pd.Timedelta('15min'))
        m = metrics(o, wl[st])
        rows.append(dict(run=run, station=st, bias=m['bias'], rmse_anom=m['rmse_anom'], corr=m['corr']))
    return rows


def main(runs):
    pd.set_option('display.width', 220)
    t = pd.DataFrame([r for run in runs if Path(str(HIS).format(run)).exists() for r in gauges(run)])
    if len(t):
        p = t.pivot(index='station', columns='run')
        print('[water level at the gauges after the first day, m]')
        for v in ('bias', 'rmse_anom', 'corr'):
            print(v)
            print(p[v][[r for r in runs if r in p[v].columns]].round(4).to_string())
    d = {r: pd.read_csv(str(DRIFT).format(r)).set_index(['deploy', 'drifter_id']).LW_skill for r in runs}
    print('\n[Liu-Weisberg skill]')
    for r in runs:
        print(f'  {r:24s} {d[r].mean():.3f}')
    print('[paired differences, consecutive runs]')
    for a, b in zip(runs[:-1], runs[1:]):
        x = (d[b] - d[a]).dropna()
        print(f'  {b} - {a}: {x.mean():+.4f}, standard error {x.std(ddof=1) / np.sqrt(len(x)):.4f}, '
              f'improved {(x > 0).sum()}/{len(x)}')


if __name__ == '__main__':
    main(sys.argv[1:])
