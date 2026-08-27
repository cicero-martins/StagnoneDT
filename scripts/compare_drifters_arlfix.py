"""What the corrected roughness field does to the Lagrangian skill.

Section 4.3 of the manuscript reads three of the four roughness contrasts as
null (+0.009, +0.001, +0.004) and the fourth, on a mobile bed with waves, as
large (+0.081), and concludes that distributed roughness acts only when waves
and a mobile bed are both present. Every one of those four members ran with
about 5.5% of the seagrass map applied, because the .arl was written to 6
decimals against a 1 cm matching tolerance. Three near-null contrasts are
exactly what a roughness field that was never applied would produce, so the
conclusion cannot stand on them as they are.

This recomputes the comparison from the corrected re-runs. Two questions, kept
separate:

  1. Paired, within member: does the same member score differently once its
     roughness field is actually applied?
  2. The contrast itself: distributed minus uniform, with the corrected VR
     member. The uniform members carry no trachytopes at all and are therefore
     unaffected by the fix, so their original metrics stand as the control.

Bootstrap and pairing follow attribution_stats.py: paired per drifter, 4000
resamples, seed 17, Wilcoxon on the paired differences.

The fourth cell, waves with a mobile bed, is absent until v04AE_vr_dens_arlfix
finishes; it is the one that carries the manuscript's claim, so nothing here
settles Section 4.3 on its own.

    python scripts/compare_drifters_arlfix.py
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import TAG

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
NBOOT = 4000
SEED = 17

# VR member key -> (its arlfix tag, the uniform-roughness control key)
PAIRS = [
    ('nowaves_vr',   'v04AE_nowaves_vr_arlfix',   'nowaves'),
    ('nodm_vr',      'v04AE_nodm_vr_arlfix',      'nodm'),
    ('nowaves_vrdm', 'v04AE_nowaves_vrdm_arlfix', 'nowaves_dm'),
]
KEYCOLS = ['deploy', 'drifter_id']


def load(tag):
    f = PROC / f'drifter_metrics_{tag}.csv'
    if not f.exists():
        return None
    return pd.read_csv(f)[KEYCOLS + ['LW_skill', 'endpoint_sep_m', 'path_ratio']]


def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


def report(label, x, rng):
    m = float(np.mean(x))
    lo, hi = boot_ci(x, rng)
    p = wilcoxon(x).pvalue if np.any(np.asarray(x) != 0) else np.nan
    neg, pos = int((x < 0).sum()), int((x > 0).sum())
    sig = '*' if not (lo <= 0 <= hi) else ' '
    print(f'{label:44s} {m:+7.3f} [{lo:+6.3f},{hi:+6.3f}] {p:8.4f}{sig} '
          f'{neg:3d}/{pos:<3d}')
    return dict(label=label, mean=m, lo=lo, hi=hi, p=p, n_neg=neg, n_pos=pos,
                clear_of_zero=not (lo <= 0 <= hi))


def main():
    rng = np.random.default_rng(SEED)
    rows = []

    print('=== member means: original vs corrected roughness ===')
    print(f"{'member':16s} {'LW old':>7s} {'LW new':>7s} {'dLW':>7s} "
          f"{'EP old':>7s} {'EP new':>7s} {'path old':>9s} {'path new':>9s}")
    have = {}
    for key, newtag, _ in PAIRS:
        old, new = load(TAG[key]), load(newtag)
        if new is None:
            print(f'{key:16s} (no metrics yet for {newtag})')
            continue
        j = old.merge(new, on=KEYCOLS, suffixes=('_old', '_new'))
        have[key] = j
        print(f'{key:16s} {j.LW_skill_old.mean():7.3f} {j.LW_skill_new.mean():7.3f} '
              f'{j.LW_skill_new.mean()-j.LW_skill_old.mean():+7.3f} '
              f'{j.endpoint_sep_m_old.mean():7.0f} {j.endpoint_sep_m_new.mean():7.0f} '
              f'{j.path_ratio_old.mean():9.2f} {j.path_ratio_new.mean():9.2f}')

    if not have:
        print('\nnothing to compare yet')
        return

    print(f"\n=== 1. paired within member (corrected - original) ===")
    print(f"{'':44s} {'dLW':>7s} {'CI95':>15s} {'p':>8s} {'neg/pos':>7s}")
    print('-' * 88)
    for key, _, _ in PAIRS:
        if key in have:
            j = have[key]
            rows.append(report(f'{key}: corrected - original',
                               (j.LW_skill_new - j.LW_skill_old).values, rng))

    print(f"\n=== 2. the roughness contrast (distributed - uniform) ===")
    print(f"{'':44s} {'dLW':>7s} {'CI95':>15s} {'p':>8s} {'neg/pos':>7s}")
    print('-' * 88)
    for key, _, ctrl in PAIRS:
        c = load(TAG[ctrl])
        for variant, col in (('as published', 'LW_skill_old'),
                             ('corrected', 'LW_skill_new')):
            if key not in have:
                continue
            j = have[key].merge(c, on=KEYCOLS)
            rows.append(report(f'{key} vs {ctrl} [{variant}]',
                               (j[col] - j.LW_skill).values, rng))

    print('\n* = bootstrap interval clear of zero')
    out = PROC / 'drifter_contrasts_arlfix.csv'
    pd.DataFrame(rows).to_csv(out, index=False, float_format='%.4f')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
