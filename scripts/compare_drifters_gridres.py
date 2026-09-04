"""Does the regrid resolution change the Lagrangian skill?

The target grid handed to OpenDrift is 0.002 degrees, about 222 m. That value
came from the first regrid script in April 2026 and has never been justified:
no memory, no document, no commit message. It is a real coarsening, the FM mesh
inside the lagoon having a median nearest-neighbour spacing of 61 m, so the
drift field is smoothed by roughly a factor of 3.6 in each direction before any
particle is released.

The temporal analogue was tested in May 2026 and turned out not to matter, the
mean skill moving -0.008 when mapInterval went from 1800 to 600 s. The spatial
one had not been tested, and it is far cheaper: no model run, only a
reinterpolation of the same map.nc.

Same drifters, same windage, same OpenDrift configuration, same member. The only
difference is the grid the currents were interpolated onto, so the comparison is
paired per drifter and read the same way as attribution_stats.py: 4000
resamples, seed 17, Wilcoxon on the paired differences.

A caveat worth holding while reading the result. The intuition that finer is
better already failed once here: in the temporal test deployment 1 got worse,
0.59 to 0.36, blamed on interpolation noise in a calm interior. Coarsening can
act as a filter against sub-grid noise the drifters never felt.

    python scripts/compare_drifters_gridres.py <coarse_tag> <fine_tag>
    python scripts/compare_drifters_gridres.py v04AE_nodm v04AE_nodm_dx001
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
sys.path.insert(0, str(Path(__file__).resolve().parent))

NBOOT = 4000
SEED = 17


def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


def load(tag):
    f = PROC / f'drifter_metrics_{tag}.csv'
    if not f.exists():
        sys.exit(f'missing {f}')
    return pd.read_csv(f)


def main(coarse, fine):
    a, b = load(coarse), load(fine)
    key = ['deploy', 'drifter_id']
    d = a.merge(b, on=key, suffixes=('_c', '_f'))
    print(f'=== {coarse}  vs  {fine} ===')
    print(f'  {len(d)} drifters common to both, '
          f'{d["deploy"].nunique()} deploys\n')

    rng = np.random.default_rng(SEED)
    print(f"{'metrica':16s} {'grosso':>9s} {'fino':>9s} {'delta':>9s} "
          f"{'CI95':>19s} {'p':>8s}")
    print('-' * 76)
    for lab, col, fmt in [('LW skill', 'LW_skill', '9.3f'),
                          ('endpoint m', 'endpoint_sep_m', '9.0f'),
                          ('path ratio', 'path_ratio', '9.3f'),
                          ('n_steps', 'n_steps', '9.1f')]:
        x = (d[f'{col}_f'] - d[f'{col}_c']).dropna()
        lo, hi = boot_ci(x, rng)
        p = wilcoxon(x).pvalue if x.std() > 0 else np.nan
        sig = '*' if not (lo <= 0 <= hi) else ' '
        print(f'{lab:16s} {d[f"{col}_c"].mean():{fmt}} '
              f'{d[f"{col}_f"].mean():{fmt}} {x.mean():{fmt}} '
              f'[{lo:+8.3f},{hi:+8.3f}] {p:8.4f}{sig}')
    print('\n* = intervalo bootstrap fora do zero')

    print('\n=== por deploy, LW skill ===')
    print(f"{'dep':>4s} {'grosso':>8s} {'fino':>8s} {'delta':>8s}")
    print('-' * 32)
    for dep, g in d.groupby('deploy'):
        c, f = g['LW_skill_c'].mean(), g['LW_skill_f'].mean()
        print(f'{int(dep):4d} {c:8.3f} {f:8.3f} {f - c:+8.3f}')

    x = d['LW_skill_f'] - d['LW_skill_c']
    print(f'\n  {(x > 0).sum()} de {len(x)} drifters melhoram com a grade fina')

    out = PROC / f'gridres_{coarse}_vs_{fine}.csv'
    d.to_csv(out, index=False, float_format='%.4f')
    print(f'\nSaved {out}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('coarse_tag')
    ap.add_argument('fine_tag')
    a = ap.parse_args()
    main(a.coarse_tag, a.fine_tag)
