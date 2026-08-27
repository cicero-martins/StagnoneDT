"""Does fixing the .arl precision change the water level skill?

The trachytope area file was written with 6 decimals while FM matches each
record to a net link within 1 cm, so every variable-roughness member of the
factorial ran with roughly 5.5% of the seagrass map instead of all of it
(scripts/build_trachytope_arl.py, and check_trachytope_coverage.py for the
measurement). Three of the four were rerun as *_arlfix clones with the
corrected file; this pairs each against its original.

The comparison is the one that decides what Paper 1 has to say: if the skill
is unchanged, the roughness field was never doing the work the text credits it
with, and that is a finding rather than a bug. If it moves, the numbers in
Sections 4 and 5 move with it.

Same conventions as validate_wl_ensemble.py: raw RMSE, bias and anomaly RMSE
reported together because RMSE^2 = bias^2 + RMSE_anom^2, and the first
simulated day dropped as spin-up.

    python scripts/compare_wl_arlfix.py
"""
import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model'

STATIONS = {'BocaNord': 'wl_BocaNord_10min_UTC.csv',
            'BocaSud': 'wl_BocaSud_10min_UTC.csv',
            'AltaVilaEst': 'wl_AltavilaEst_10min_UTC.csv'}

# Three variants per member, which is the decomposition that matters:
#
#   original  the runs behind the Paper 1 figures: 6-decimal .arl, so about
#             5.5% of the meadow applied, on Baptist formula 153
#   arlfix    .arl corrected to 9 decimals, still on 153 -- isolates the bug fix
#   f154      .arl corrected AND Baptist 154, which keeps the canopy drag out of
#             the bed Chezy instead of folding it in -- isolates the formulation
#
# nodm_vr's original output was never copied back in full, so it reads the CSV
# extracted on the server; that member is fixed-bed and was not otherwise
# rerun, so the CSV is still current.
#
# Missing entries are skipped rather than fatal: the 154 runs land one at a
# time, and this is meant to be re-run as they do.
VARIANTS = {
    'nowaves_vr':   {'original': 'dflowfm_v04AE_nowaves_vr',
                     'arlfix':   'dflowfm_v04AE_nowaves_vr_arlfix',
                     'f154':     'dflowfm_v04AE_nowaves_vr_154'},
    'nodm_vr':      {'original': 'csv:wl_nodm_vr.csv',
                     'arlfix':   'dflowfm_v04AE_nodm_vr_arlfix',
                     'f154':     'dflowfm_v04AE_nodm_vr_154'},
    'nowaves_vrdm': {'original': 'dflowfm_v04AE_nowaves_vrdm_dens',
                     'arlfix':   'dflowfm_v04AE_nowaves_vrdm_dens_arlfix',
                     'f154':     'dflowfm_v04AE_nowaves_vrdm_dens_154'},
    # 'vr' (waves + roughness + mobile bed) has no arlfix: on 153 it aborts on
    # MinTimestepBreak at 45 simulated minutes. 154 is the first configuration
    # in which this cell of the factorial runs at all.
    'vr':           {'original': 'dflowfm_v04AE_vr_dens',
                     'f154':     'dflowfm_v04AE_vr_dens_154'},
}
ORDER = ['original', 'arlfix', 'f154']

SPINUP_DAYS = 1.0


def from_his(d):
    # Newest wins: a member directory can hold the run's his.nc at its root and
    # an earlier copy under DFM_OUTPUT_*.
    cands = (glob.glob(str(MODEL / d / '*_his.nc')) +
             glob.glob(str(MODEL / d / 'DFM_OUTPUT_*' / '*_his.nc')))
    cands = [c for c in cands if not c.endswith('.bak_unrestricted')]
    if not cands:
        return None
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


def load(src):
    if src.startswith('csv:'):
        return pd.read_csv(PROC / src[4:], parse_dates=['time'])
    return from_his(src)


def metrics(mod, obs):
    ok = np.isfinite(mod) & np.isfinite(obs)
    m, o = mod[ok], obs[ok]
    if len(m) < 10:
        return dict(n=len(m))
    bias = float(np.mean(m - o))
    ma, oa = m - m.mean(), o - o.mean()
    return dict(n=int(len(m)),
                rmse_raw=float(np.sqrt(np.mean((m - o) ** 2))),
                bias=bias,
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

    rows = []
    for key, srcs in VARIANTS.items():
        for variant in ORDER:
            src = srcs.get(variant)
            if src is None:
                continue
            mod = load(src)
            if mod is None:
                print(f'{key}/{variant}: no his.nc yet under {src}')
                continue
            t0 = mod['time'].min() + pd.Timedelta(days=SPINUP_DAYS)
            m = mod[mod['time'] >= t0].set_index('time')
            for st in STATIONS:
                if st not in m.columns:
                    continue
                o = obs[st].reindex(m.index, method='nearest',
                                    tolerance=pd.Timedelta('10min'))
                r = metrics(m[st].values, o.values)
                r.update(member=key, variant=variant, station=st)
                rows.append(r)

    df = pd.DataFrame(rows)
    out = PROC / 'wl_metrics_arlfix.csv'
    df.to_csv(out, index=False, float_format='%.4f')

    def deltas(piv, a, b, label):
        print(f'  delta ({a} - {b}):')
        any_row = False
        for k in VARIANTS:
            if (k, a) in piv.index and (k, b) in piv.index:
                d = piv.loc[(k, a)] - piv.loc[(k, b)]
                print('   ', f'{k:14s}',
                      '  '.join(f'{s}={v:+.4f}' for s, v in d.items()))
                any_row = True
        if not any_row:
            print('    (nothing to compare yet)')

    for col, unit in (('rmse_anom', 'anomaly RMSE, the dynamic-skill measure'),
                      ('bias', 'bias'),
                      ('rmse_raw', 'raw RMSE'),
                      ('corr', 'correlation'),
                      ('std_ratio', 'modelled/observed std')):
        print(f'\n=== {col} -- {unit} ===')
        piv = df.pivot_table(index=['member', 'variant'], columns='station',
                             values=col)
        piv = piv.reindex(columns=list(STATIONS))
        # keep the variants in run order rather than alphabetical
        piv = piv.reindex([(k, v) for k in VARIANTS for v in ORDER
                           if (k, v) in piv.index])
        print(piv.round(4).to_string())
        deltas(piv, 'arlfix', 'original', col)      # what the bug fix did
        deltas(piv, 'f154', 'arlfix', col)          # what the formulation did

    print(f'\nSaved {out}')


if __name__ == '__main__':
    main()
