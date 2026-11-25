"""Process attribution on the fixed bed, the two-factor design of Paper 1.

The design is a 2x2 in wave coupling and canopy, plus the wave-coupled
vegetated member rerun with the canopy also in the wave model (WVs). Each
single-factor contrast is the mean over the 35 drifters of the per-drifter
difference in skill between two members that differ in one factor, with its
95% percentile bootstrap interval (4000 resamples of the 35 differences).
Pairing by drifter removes the difficulty common to all members, which is
what lets a contrast of 0.02 clear zero where the member intervals overlap.

The three-panel figure of the earlier draft duplicated Table 3 in its
interaction plot, and the contrasts are now a table in Section 4.2. What
remains as a figure is the canopy contrast by deployment, in Section S6.

    STAGNONE_ENSEMBLE=ic3d STAGNONE_BED=fixed python scripts/plot_attribution_2x2.py

Output: data/processed/attribution_2x2<SUFFIX>.csv and
figures/<FIGSUB>/canopy_contrast_by_deployment.{png,pdf}.
"""
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import TAG, SUFFIX, FIGSUB, BED, scored

assert BED == 'fixed', 'the 2x2 figure needs STAGNONE_BED=fixed'

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures' / FIGSUB
FIG.mkdir(parents=True, exist_ok=True)

# The wave-coupled vegetated member with the canopy also in the wave model,
# a segment from the same restart as nodm_veg (dwaves_vegetation_iveg_wrapper).
SWAN_TAG = 'arm_vwf_swan'
CODE2 = dict(nowaves='--', nowaves_veg='-V', nodm='W-', nodm_veg='WV', swan='WVs')

SURFACE, INK, MUTED, GRID = '#ffffff', '#1b1b1b', '#6b6b6b', '#e8e7e4'
C_BARE, C_VEG, C_VEG_LIGHT = '#eb6834', '#4a3aa7', '#9b8fd9'
NBOOT, SEED = 4000, 17

# (label, treated, control), treated minus control
CONTRASTS = [
    ('Canopy, no waves',                 'nowaves_veg', 'nowaves'),
    ('Canopy, waves',                    'nodm_veg',    'nodm'),
    ('Canopy, waves, canopy in SWAN',    'swan',        'nodm'),
    ('Waves, bare',                      'nodm',        'nowaves'),
    ('Waves, canopy',                    'nodm_veg',    'nowaves_veg'),
    ('Waves, canopy in SWAN',            'swan',        'nowaves_veg'),
    ('Canopy in SWAN, waves and canopy', 'swan',        'nodm_veg'),
]


def boot_ci(v, rng, n=NBOOT):
    """95% percentile interval of the mean, resampling the values given."""
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


def style(ax, grid='both'):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, axis=grid, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9.5)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'):
        ax.spines[sp].set_color('#c9c7c1')


def load():
    tags = dict(TAG, swan=SWAN_TAG)
    d = None
    for key, tag in tags.items():
        m = pd.read_csv(PROC / f'drifter_metrics_{tag}.csv')[
            ['deploy', 'drifter_id', 'LW_skill']].rename(columns={'LW_skill': key})
        d = m if d is None else d.merge(m, on=['deploy', 'drifter_id'])
    return scored(d).reset_index(drop=True)


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    rng = np.random.default_rng(SEED)
    d = load()
    print(f'{len(d)} drifters, {d["deploy"].nunique()} deployments')

    # The earlier figure drew the member intervals before the contrasts. The
    # same draws are consumed here so that the contrast intervals keep the
    # values the manuscript reports.
    for k in ('nowaves', 'nowaves_veg', 'nodm', 'nodm_veg', 'swan'):
        boot_ci(d[k], rng)

    # The contrast table of Section 4.2, one row per single-factor contrast.
    rows = []
    for lab, a, b in CONTRASTS:
        x = (d[a] - d[b]).values
        m = x.mean(); lo, hi = boot_ci(x, rng)
        rows.append(dict(contrast=lab, code=f'{CODE2[a]} minus {CODE2[b]}',
                         treated=a, control=b, mean=m, lo=lo, hi=hi,
                         n_better=int((x > 0).sum()), n_worse=int((x < 0).sum()),
                         clear_of_zero=not (lo <= 0 <= hi)))
        print(f'{CODE2[a]:>4s} - {CODE2[b]:<4s} {m:+.3f} [{lo:+.3f}, {hi:+.3f}] '
              f'{int((x > 0).sum())}/{len(x)} better')
    pd.DataFrame(rows).to_csv(PROC / f'attribution_2x2{SUFFIX}.csv', index=False,
                              float_format='%.4f')

    # Supplementary figure: the canopy contrast deployment by deployment.
    fig, ax = plt.subplots(figsize=(10.5, 3.6), dpi=300)
    deps = sorted(d['deploy'].unique())
    for lab, a, b, col, off in (('-V minus --', 'nowaves_veg', 'nowaves', C_VEG_LIGHT, -0.19),
                                ('WV minus W-', 'nodm_veg', 'nodm', C_VEG, 0.19)):
        v = [(d.loc[d.deploy == dp, a] - d.loc[d.deploy == dp, b]).mean() for dp in deps]
        ax.bar(np.arange(len(deps)) + off, v, width=0.36, color=col, edgecolor='white',
               lw=0.6, label=lab, zorder=3)
    n = d.groupby('deploy').size()
    ax.axhline(0, color=INK, lw=1.0, zorder=4)
    ax.set_xticks(range(len(deps)))
    ax.set_xticklabels([f'{int(dp)}\n({n[dp]})' for dp in deps], fontsize=8.8)
    ax.set_xlabel('Deployment (drifters)', fontsize=10, color=MUTED)
    ax.set_ylabel('Mean difference in\nLiu–Weisberg skill', fontsize=10, color=MUTED)
    ax.legend(fontsize=9, frameon=False, loc='upper right', ncol=2)
    style(ax, grid='y')
    for ext in ('png', 'pdf'):
        p = FIG / f'canopy_contrast_by_deployment.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
