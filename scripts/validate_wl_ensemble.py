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
from _ensemble import KEYS, MODELDIR, TAG

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model'

STATIONS = {'BocaNord': 'wl_BocaNord_10min_UTC.csv',
            'BocaSud': 'wl_BocaSud_10min_UTC.csv',
            'AltaVilaEst': 'wl_AltavilaEst_10min_UTC.csv'}

# The four mobile-bed members moved to the *_dens directories when DensIn=false
# closed the factorial; MODELDIR in _ensemble.py is the single source for that.
HIS = {k: MODELDIR[k] for k in KEYS}
ORDER = list(KEYS)

# The vegetated members were built and run on the server, and their map.nc set
# is 40 GB, so only the his.nc came back. They resolve from this cache instead
# of from a model directory that does not exist on this machine.
HIS_CACHE = PROC / 'veg_his'

SPINUP_DAYS = 1.0

# Every member is scored on the SAME interval. The uniform members are nine-day
# runs and the vegetated ones are three-day restart segments, so letting each
# use its own post-spinup span would compare an eight-day record against a
# two-day one and attribute the difference to the member. The window is the
# intersection after each member drops its own spin-up day, computed rather
# than written down, and printed with the table.
COMMON_WINDOW = True


def from_his(d, key=None):
    if key is not None:
        cached = HIS_CACHE / f'{TAG[key]}_his.nc'
        if cached.exists():
            return read_his(str(cached))
    return read_his(pick_his(d))


def pick_his(d):
    # Newest wins. The member directories can hold more than one his.nc: the
    # current run writes to the directory root while an earlier run's copy may
    # still sit under DFM_OUTPUT_*. Picking by glob order silently scored a
    # superseded run.
    cands = (glob.glob(str(MODEL / d / '*_his.nc')) +
             glob.glob(str(MODEL / d / 'DFM_OUTPUT_*' / '*_his.nc')))
    cands = [c for c in cands if not c.endswith('.bak_unrestricted')]
    if not cands:
        raise FileNotFoundError(f'no his.nc under {MODEL / d}')
    return max(cands, key=os.path.getmtime)


def read_his(f):
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
    return from_his(HIS[key], key=key)


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

    loaded = {k: load_member(k) for k in ORDER}
    starts = {k: v['time'].min() + pd.Timedelta(days=SPINUP_DAYS)
              for k, v in loaded.items()}
    ends = {k: v['time'].max() for k, v in loaded.items()}
    w0, w1 = max(starts.values()), min(ends.values())
    if COMMON_WINDOW:
        print(f'\ncommon scoring window {w0} -> {w1}')
        for k in ORDER:
            print(f'  {k:15s} own post-spinup span '
                  f'{starts[k]} -> {ends[k]}')

    rows = []
    for key in ORDER:
        mod = loaded[key]
        t0 = w0 if COMMON_WINDOW else starts[key]
        t1 = w1 if COMMON_WINDOW else ends[key]
        m = mod[(mod['time'] >= t0) & (mod['time'] <= t1)].set_index('time')
        print(f'\n{key}: {len(m)} steps scored, '
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
