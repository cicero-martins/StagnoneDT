"""Water level skill at BN, BS and AE for all five ensemble members.

Reports the raw RMSE, the bias and the anomaly RMSE together, because
RMSE^2 = bias^2 + RMSE_anom^2 and quoting either alone confounds a constant
reference-level offset with genuine error in phase and amplitude. Correlation
and the modelled-to-observed standard deviation ratio go with them.

The first simulated day is dropped as spin-up.

Source per member is not uniform. Four members read their own his.nc. Only
nodm_vr reads a CSV extracted on the server, because its output was never
copied back in full; that member is fixed-bed and was not rerun, so the CSV is
still current for it.

Two traps this encodes. A member directory can hold more than one his.nc, since
the current run writes to the directory root while an earlier run's copy may
remain under DFM_OUTPUT_*; the newest file wins, chosen by mtime. And vr was
previously read from a CSV because its local his.nc was truncated at 430 of
1297 steps, which is no longer the case after the 2026-08-06 rerun.

Output: data/processed/wl_metrics_ensemble.csv
"""
import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, MODELDIR

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model'

STATIONS = {'BocaNord': 'wl_BocaNord_10min_UTC.csv',
            'BocaSud': 'wl_BocaSud_10min_UTC.csv',
            'AltaVilaEst': 'wl_AltavilaEst_10min_UTC.csv'}

# The four mobile-bed members moved to the *_dens directories when DensIn=false
# closed the factorial; MODELDIR in _ensemble.py is the single source for that.
HIS = {k: MODELDIR[k] for k in KEYS if k != 'nodm_vr'}
CSV = {'nodm_vr': 'wl_nodm_vr.csv'}
ORDER = list(KEYS)

SPINUP_DAYS = 1.0


def from_his(d):
    # Newest wins. The member directories can hold more than one his.nc: the
    # current run writes to the directory root while an earlier run's copy may
    # still sit under DFM_OUTPUT_*. Picking by glob order silently scored a
    # superseded run.
    cands = (glob.glob(str(MODEL / d / '*_his.nc')) +
             glob.glob(str(MODEL / d / 'DFM_OUTPUT_*' / '*_his.nc')))
    cands = [c for c in cands if not c.endswith('.bak_unrestricted')]
    f = max(cands, key=os.path.getmtime)
    ds = xr.open_dataset(f)
    names = [b.tobytes().decode('utf-8', 'ignore').strip() if isinstance(b, bytes)
             else str(b).strip()
             for b in ds['station_name'].values]
    wl = ds['waterlevel'].values
    t = pd.to_datetime(ds.time.values)
    ds.close()
    out = pd.DataFrame({'time': t})
    for st in STATIONS:
        hit = [i for i, n in enumerate(names) if n.replace(' ', '') == st]
        if hit:
            out[st] = wl[:, hit[0]]
    return out


def load_member(key):
    if key in HIS:
        return from_his(HIS[key])
    df = pd.read_csv(PROC / CSV[key], parse_dates=['time'])
    return df


def metrics(mod, obs):
    ok = np.isfinite(mod) & np.isfinite(obs)
    m, o = mod[ok], obs[ok]
    if len(m) < 10:
        return dict(n=len(m))
    bias = float(np.mean(m - o))
    rmse = float(np.sqrt(np.mean((m - o) ** 2)))
    ma, oa = m - m.mean(), o - o.mean()
    return dict(n=int(len(m)), rmse_raw=rmse, bias=bias,
                rmse_anom=float(np.sqrt(np.mean((ma - oa) ** 2))),
                corr=float(np.corrcoef(m, o)[0, 1]),
                std_ratio=float(m.std() / o.std()))


def main():
    obs = {}
    for st, fn in STATIONS.items():
        d = pd.read_csv(PROC / fn)
        tc = [c for c in d.columns if 'time' in c.lower()][0]
        vc = [c for c in d.columns if c != tc][0]
        d = d[[tc, vc]].rename(columns={tc: 'time', vc: st})
        d['time'] = pd.to_datetime(d['time'])
        obs[st] = d.set_index('time')[st]
        print(f'obs {st:12s} n={len(d)}  {d["time"].min()} -> {d["time"].max()}')

    rows = []
    for key in ORDER:
        mod = load_member(key)
        t0 = mod['time'].min() + pd.Timedelta(days=SPINUP_DAYS)
        m = mod[mod['time'] >= t0].set_index('time')
        print(f'\n{key}: {len(m)} steps post-spinup, '
              f'{m.index.min()} -> {m.index.max()}')
        for st in STATIONS:
            if st not in m.columns:
                print(f'  {st}: absent from this member')
                continue
            o = obs[st].reindex(m.index, method='nearest',
                                tolerance=pd.Timedelta('10min'))
            r = metrics(m[st].values, o.values)
            r.update(member=key, station=st)
            rows.append(r)
            print(f"  {st:12s} RMSE {r.get('rmse_raw', np.nan):.3f}  "
                  f"bias {r.get('bias', np.nan):+.3f}  "
                  f"RMSE_anom {r.get('rmse_anom', np.nan):.3f}  "
                  f"corr {r.get('corr', np.nan):.2f}  "
                  f"std {r.get('std_ratio', np.nan):.2f}")

    df = pd.DataFrame(rows)
    out = PROC / 'wl_metrics_ensemble.csv'
    df.to_csv(out, index=False, float_format='%.4f')
    print(f'\nSaved {out}')

    print('\n=== anomaly RMSE (m), the dynamic-skill measure ===')
    piv = df.pivot(index='member', columns='station', values='rmse_anom')
    print(piv.reindex(ORDER).round(4).to_string())
    print('\n=== bias (m) ===')
    print(df.pivot(index='member', columns='station',
                   values='bias').reindex(ORDER).round(4).to_string())


if __name__ == '__main__':
    main()
