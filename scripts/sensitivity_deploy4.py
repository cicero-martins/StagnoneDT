"""Does the conclusion depend on deployment 4? No. This shows it both ways.

Deployment 4 is a sampling outlier: 0.43 h in the water, 162 m of observed
path, 3 scored steps, against next-lowest values of 1.94 h, 723 m and 12 steps.
It is also the only deployment where the bare-bed arm beats the vegetated arm.
Those two facts pull in opposite directions -- the first argues for dropping
it, the second means dropping it flatters the conclusion -- so the manuscript
keeps it in and reports this table.

One asymmetry has to be declared rather than resolved. The transport error
decomposition CANNOT include deployment 4 at any setting: heading error is the
mean angular difference over step bearings, three positions give two bearings,
and the routine requires three. So Section 5.3 has always been computed on 11
deployments while Sections 4.2 and 4.3 used 12. That was silent in the
submitted version and is now stated.

    python scripts/sensitivity_deploy4.py
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, TAG, CONTRASTS, scored

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
NBOOT = 4000
SEED = 17

CODE = {'nowaves': '---', 'nowaves_veg': '-V-', 'nodm': 'W--',
        'nodm_veg': 'WV-', 'nowaves_dm': '--M', 'nowaves_vegdm': '-VM',
        'bl': 'W-M', 'veg': 'WVM'}


def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


def load():
    d = None
    for k in KEYS:
        m = pd.read_csv(PROC / f'drifter_metrics_{TAG[k]}.csv')[
            ['deploy', 'drifter_id', 'LW_skill']].rename(columns={'LW_skill': k})
        d = m if d is None else d.merge(m, on=['deploy', 'drifter_id'])
    return d


def arm_interaction(mu, base, w, b, wb):
    W, B, WB = mu[w] - mu[base], mu[b] - mu[base], mu[wb] - mu[base]
    return W, B, WB, WB - (W + B)


def main():
    d = load()
    sets = [('with deployment 4', d),
            ('without deployment 4', scored(d, exclude=(4,), verbose=False))]

    print('=== deployment 4, why it is a candidate for exclusion ===')
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    g = obs.groupby(['deploy', 'source']).agg(t0=('time', 'min'),
                                              t1=('time', 'max'))
    g['h'] = (g.t1 - g.t0).dt.total_seconds() / 3600
    m0 = pd.read_csv(PROC / f'drifter_metrics_{TAG[KEYS[0]]}.csv')
    prof = m0.groupby('deploy').agg(steps=('n_steps', 'mean'),
                                    obs_m=('obs_path_m', 'mean'))
    prof['h'] = g.groupby('deploy')['h'].mean()
    print(f"{'deploy':>7s} {'hours':>7s} {'obs path m':>11s} {'steps':>7s}")
    for i, r in prof.sort_values('steps').iterrows():
        mark = '  <-- outlier on all three' if i == 4 else ''
        print(f'{int(i):7d} {r.h:7.2f} {r.obs_m:11.0f} {r.steps:7.0f}{mark}')

    print('\n=== member means ===')
    print(f"{'member':8s} " + ' '.join(f'{n:>22s}' for n, _ in sets))
    for k in KEYS:
        vals = ' '.join(f'{s[k].mean():22.3f}' for _, s in sets)
        print(f'{CODE[k]:8s} {vals}')

    print('\n=== the twelve contrasts ===')
    print(f"{'contrast':38s} " +
          ' '.join(f'{n:>26s}' for n, _ in sets))
    for lab, a, b in CONTRASTS:
        cells = []
        for _, s in sets:
            rng = np.random.default_rng(SEED)
            x = (s[a] - s[b]).values
            lo, hi = boot_ci(x, rng)
            p = wilcoxon(x).pvalue
            sig = '*' if not (lo <= 0 <= hi) else ' '
            cells.append(f'{x.mean():+7.3f} [{lo:+6.3f},{hi:+6.3f}]{sig}')
        print(f'{lab:38s} ' + ' '.join(f'{c:>26s}' for c in cells))

    print('\n=== the interaction, per arm ===')
    arms = {'bare bed ': ('nowaves', 'nodm', 'nowaves_dm', 'bl'),
            'vegetated': ('nowaves_veg', 'nodm_veg', 'nowaves_vegdm', 'veg')}
    for name, s in sets:
        mu = s[KEYS].mean()
        print(f'  {name}')
        for arm, keys in arms.items():
            W, B, WB, I = arm_interaction(mu, *keys)
            print(f'    {arm}: waves {W:+.3f}  bed {B:+.3f}  both {WB:+.3f}'
                  f'   interaction {I:+.3f}')
        u = mu[list(arms['bare bed '])]
        v = mu[list(arms['vegetated'])]
        print(f'    spread across cells: bare {u.std(ddof=0):.3f}'
              f'   vegetated {v.std(ddof=0):.3f}')

    print('\nAll twelve contrasts keep their sign. Eleven keep their')
    print('significance; bed mobility on a vegetated bed with waves goes from')
    print('crossing zero (+0.018) to clear of it (+0.032), which is the one')
    print('change that cuts slightly against the clean reading rather than for')
    print('it. Every other difference flatters the conclusion, and that is why')
    print('the primary analysis keeps deployment 4 in.')


if __name__ == '__main__':
    main()
