"""Paired contrasts across the eight-member ensemble, with bootstrap intervals.

The waves x roughness x bed-mobility factorial closed on 2026-08-08, when
DensIn=false let the two no-wave mobile-bed cells run. Every factor now has four
single-factor contrasts, one per combination of the other two, so an effect can
be reported with the conditions under which it was measured rather than as a
single number from one axis.

Member and contrast definitions live in _ensemble.py.

Emits data/processed/attribution_contrasts.csv and prints the table.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, binomtest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import (MEMBERS as ENS, KEYS, TAG, LABEL, CONTRASTS,
                       MODELDIR, scored)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
NBOOT = 4000

MEMBERS = TAG


def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


def main():
    d = None
    for key, tag in MEMBERS.items():
        m = pd.read_csv(PROC / f'drifter_metrics_{tag}.csv')
        m = m[['deploy', 'drifter_id', 'LW_skill', 'endpoint_sep_m',
               'path_ratio']].rename(columns={
                   'LW_skill': f'LW_{key}', 'endpoint_sep_m': f'EP_{key}',
                   'path_ratio': f'PR_{key}'})
        d = m if d is None else d.merge(m, on=['deploy', 'drifter_id'])
    d = scored(d).reset_index(drop=True)
    print(f'{len(d)} drifters common to all {len(MEMBERS)} members, '
          f'{d["deploy"].nunique()} deploys\n')

    print(f"{'member':12s} {'LW':>6s} {'EP m':>6s} {'path':>6s}")
    for k in MEMBERS:
        print(f'{k:12s} {d[f"LW_{k}"].mean():6.3f} {d[f"EP_{k}"].mean():6.0f} '
              f'{d[f"PR_{k}"].mean():6.2f}')

    rng = np.random.default_rng(17)
    rows = []
    print(f"\n{'contrast':38s} {'dLW':>7s} {'CI95':>18s} {'p':>8s} {'neg/pos':>9s}")
    print('-' * 86)
    for lab, a, b in CONTRASTS:
        x = (d[f'LW_{a}'] - d[f'LW_{b}']).dropna()
        m = x.mean()
        lo, hi = boot_ci(x, rng)
        p = wilcoxon(x).pvalue
        neg, pos = int((x < 0).sum()), int((x > 0).sum())
        sig = '*' if not (lo <= 0 <= hi) else ' '
        print(f'{lab:38s} {m:+7.3f} [{lo:+6.3f},{hi:+6.3f}] {p:8.4f}{sig} '
              f'{neg:4d}/{pos:<4d}')
        rows.append({'contrast': lab, 'a': a, 'b': b, 'dLW': m, 'lo': lo,
                     'hi': hi, 'p': p, 'n_neg': neg, 'n_pos': pos,
                     'clear_of_zero': not (lo <= 0 <= hi)})
    print('\n* = bootstrap interval clear of zero')

    # the wave penalty, per deploy, both roughness treatments
    print('\n=== wave penalty by deploy ===')
    for lab, a, b in CONTRASTS[:4]:
        x = (d[f'LW_{a}'] - d[f'LW_{b}'])
        per = x.groupby(d['deploy']).mean()
        nd = int((per < 0).sum())
        bt = binomtest(int((x < 0).sum()), len(x), 0.5)
        print(f'  {lab:38s} {nd}/{len(per)} deploys worse, '
              f'{int((x < 0).sum())}/{len(x)} drifters worse (sign p={bt.pvalue:.4f})')

    pd.DataFrame(rows).to_csv(PROC / 'attribution_contrasts.csv', index=False,
                              float_format='%.4f')
    print(f'\nSaved {PROC / "attribution_contrasts.csv"}')


if __name__ == '__main__':
    main()
