"""Lagrangian skill across the three roughness treatments.

Section 4.3 of the manuscript reads three of the four roughness contrasts as
null (+0.009, +0.001, +0.004) and the fourth, waves on a mobile bed, as large
(+0.081), and concludes that distributed roughness acts only when waves and a
mobile bed are both present. All four of those members ran with roughly 5.5% of
the seagrass map applied, because the .arl was written to 6 decimals against a
1 cm matching tolerance. Three near-null contrasts are what a roughness field
that was never applied would produce, so that conclusion cannot stand on them.

Two corrections were made, and they are separable, so this keeps them separate:

    original  formula 153, .arl at 6 decimals -- the manuscript's members
    arlfix    formula 153, .arl at 9 decimals -- the meadow actually applied
    154       formula 154, .arl at 9 decimals -- canopy drag as a momentum
              sink instead of folded into a single representative Chezy

original -> arlfix is the bug. arlfix -> 154 is the formulation. Reporting the
jump from original to 154 alone would attribute both to whichever one the
reader has in mind.

The uniform-roughness controls carry no trachytopes at all, so neither
correction touches them and their original metrics stand throughout.

Two caveats that belong in any sentence written from this output:

  The waves + fixed-bed member on 154 is v04AE_nodm_vr_154shore, which carries
  a rocky-shore Manning of 0.05 on 2206 links at Marettimo, 45 km from the
  lagoon, without which it does not integrate. The other members do not carry
  it. It is invisible at the three tide gauges but mean lagoon speed differs by
  about 2.4%, and a trajectory integrates, so this member's Lagrangian numbers
  are not exchangeable with the other seven.

  The waves + mobile-bed member has no arlfix column: on 153 with the corrected
  meadow it aborts. That absence is a result, not a gap.

Bootstrap and pairing follow attribution_stats.py: paired per drifter, 4000
resamples, seed 17, Wilcoxon on the paired differences.

    python scripts/compare_drifters_154.py
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

# VR member key -> {variant: drifter tag}, plus its uniform-roughness control.
# A missing variant is skipped rather than faked; vr has no arlfix because that
# configuration aborts.
VARIANTS = ['original', 'arlfix', '154']
MEMBERS = {
    'nowaves_vr':   (dict(original='v04AE_nowaves_vr',
                          arlfix='v04AE_nowaves_vr_arlfix',
                          _154='v04AE_nowaves_vr_154'),        'nowaves'),
    'nodm_vr':      (dict(original='v04AE_nodm_vr',
                          arlfix='v04AE_nodm_vr_arlfix',
                          _154='v04AE_nodm_vr_154shore'),      'nodm'),
    'nowaves_vrdm': (dict(original='v04AE_nowaves_vrdm',
                          arlfix='v04AE_nowaves_vrdm_arlfix',
                          _154='v04AE_nowaves_vrdm_154'),      'nowaves_dm'),
    'vr':           (dict(original='v04AE_vr',
                          _154='v04AE_vr_154'),                'bl'),
}
SHORE_TREATED = {'nodm_vr'}
KEYCOLS = ['deploy', 'drifter_id']


def tag_of(member, variant):
    return MEMBERS[member][0].get('_154' if variant == '154' else variant)


def load(tag):
    if tag is None:
        return None
    f = PROC / f'drifter_metrics_{tag}.csv'
    if not f.exists():
        return None
    return pd.read_csv(f)[KEYCOLS + ['LW_skill', 'endpoint_sep_m', 'path_ratio']]


def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


def report(label, x, rng, rows, note=''):
    x = np.asarray(x, float)
    m = float(np.mean(x))
    lo, hi = boot_ci(x, rng)
    p = wilcoxon(x).pvalue if np.any(x != 0) else np.nan
    neg, pos = int((x < 0).sum()), int((x > 0).sum())
    sig = '*' if not (lo <= 0 <= hi) else ' '
    print(f'{label:46s} {m:+7.3f} [{lo:+6.3f},{hi:+6.3f}] {p:8.4f}{sig} '
          f'{neg:3d}/{pos:<3d} {note}')
    rows.append(dict(label=label, mean=m, lo=lo, hi=hi, p=p, n_neg=neg,
                     n_pos=pos, clear_of_zero=not (lo <= 0 <= hi), note=note))


def main():
    rng = np.random.default_rng(SEED)
    rows = []
    M = {m: {v: load(tag_of(m, v)) for v in VARIANTS} for m in MEMBERS}
    C = {m: load(TAG[ctrl]) for m, (_, ctrl) in MEMBERS.items()}

    missing = [(m, v) for m in MEMBERS for v in VARIANTS
               if M[m][v] is None and tag_of(m, v) is not None]
    if missing:
        print('not yet available: '
              + ', '.join(f'{m}/{v}' for m, v in missing) + '\n')

    print('=== member means by treatment ===')
    print(f"{'member':15s} {'variant':9s} {'LW':>7s} {'EP m':>7s} "
          f"{'path':>6s}   {'tag'}")
    for m in MEMBERS:
        for v in VARIANTS:
            d = M[m][v]
            if d is None:
                continue
            mark = ' (shore treated)' if v == '154' and m in SHORE_TREATED else ''
            print(f'{m:15s} {v:9s} {d.LW_skill.mean():7.3f} '
                  f'{d.endpoint_sep_m.mean():7.0f} {d.path_ratio.mean():6.2f}   '
                  f'{tag_of(m, v)}{mark}')
        d = C[m]
        print(f'{"":15s} {"control":9s} {d.LW_skill.mean():7.3f} '
              f'{d.endpoint_sep_m.mean():7.0f} {d.path_ratio.mean():6.2f}   '
              f'{TAG[MEMBERS[m][1]]}')

    hdr = f"{'':46s} {'dLW':>7s} {'CI95':>15s} {'p':>8s} {'neg/pos':>7s}"
    print(f'\n=== 1. what each correction moved, paired within member ===')
    print(hdr); print('-' * 95)
    for m in MEMBERS:
        for a, b in (('original', 'arlfix'), ('arlfix', '154'),
                     ('original', '154')):
            if M[m][a] is None or M[m][b] is None:
                continue
            j = M[m][a].merge(M[m][b], on=KEYCOLS, suffixes=('_a', '_b'))
            report(f'{m}: {b} - {a}', j.LW_skill_b - j.LW_skill_a, rng, rows)

    print(f'\n=== 2. the roughness contrast, distributed - uniform ===')
    print(hdr); print('-' * 95)
    for m in MEMBERS:
        for v in VARIANTS:
            if M[m][v] is None:
                continue
            j = M[m][v].merge(C[m], on=KEYCOLS, suffixes=('_t', '_c'))
            note = 'shore' if v == '154' and m in SHORE_TREATED else ''
            report(f'{m} vs {MEMBERS[m][1]} [{v}]',
                   j.LW_skill_t - j.LW_skill_c, rng, rows, note)

    # Deployments 1, 2 and 3 were released between 07:14 and 07:48 on 8 July,
    # inside 35 minutes of each other, so they sample one flow state rather
    # than three. Every zero-skill case in the 154 members lives there and
    # nowhere else. It is a hard window for the uniform members too, which is
    # why the contrast is the thing to re-measure without it, not the mean.
    print(f'\n=== 3. the same contrast without the 8 Jul morning window ===')
    print(hdr); print('-' * 95)
    for m in MEMBERS:
        for v in VARIANTS:
            if M[m][v] is None:
                continue
            j = M[m][v].merge(C[m], on=KEYCOLS, suffixes=('_t', '_c'))
            j = j[j.deploy > 3]
            report(f'{m} vs {MEMBERS[m][1]} [{v}], deploys 4-12',
                   j.LW_skill_t - j.LW_skill_c, rng, rows)

    print('\n* = bootstrap interval clear of zero')
    print('shore = carries the Marettimo rocky-shore treatment; not '
          'exchangeable with the untreated members')
    out = PROC / 'drifter_contrasts_154.csv'
    pd.DataFrame(rows).to_csv(out, index=False, float_format='%.4f')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
