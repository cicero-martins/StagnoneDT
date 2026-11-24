"""Process attribution on the fixed bed, the two-factor design of Paper 1.

The co-author found the earlier attribution figure unclear: twelve contrasts of
a three-factor design read as a column of intervals, with nothing showing what
was being contrasted. With the mobile-bed arm out of the paper the design is a
2x2 in wave coupling and canopy, plus the wave-coupled vegetated member rerun
with the canopy also in the wave model, and the figure is built around that.

(a) Mean skill of the four cells as an interaction plot, canopy on the axis,
    one line per wave treatment. The vertical gap is the canopy effect, the
    gap between lines the wave effect, parallel lines no interaction. The
    member with the canopy also in SWAN sits beside the wave-coupled canopy
    cell.
(b) Each single-factor contrast as the mean of the per-drifter paired
    differences, with its 95% percentile bootstrap interval (4000 resamples
    of the 35 differences). Filled markers clear zero.
(c) The canopy contrast deployment by deployment.

    STAGNONE_ENSEMBLE=ic3d STAGNONE_BED=fixed python scripts/plot_attribution_2x2.py

Output: figures/<FIGSUB>/ensemble_attribution.{png,pdf}, and the contrast
table in data/processed/attribution_2x2<SUFFIX>.csv.
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

    fig = plt.figure(figsize=(12.4, 8.2), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[0.85, 1.25], height_ratios=[1.15, 0.85],
                          hspace=0.48, wspace=0.62, left=0.07, right=0.985,
                          top=0.95, bottom=0.08)

    # (a) interaction plot
    ax = fig.add_subplot(gs[0, 0])
    for lab, keys, mk, ls, off in (('no wave coupling', ('nowaves', 'nowaves_veg'), 'o', ':', -0.04),
                                   ('wave coupling', ('nodm', 'nodm_veg'), 's', '--', 0.04)):
        m = np.array([d[k].mean() for k in keys])
        ci = np.array([boot_ci(d[k], rng) for k in keys])
        ax.plot(np.array([0, 1]) + off, m, ls, color=INK, lw=1.4, zorder=3)
        for i, k in enumerate(keys):
            col = C_VEG if i else C_BARE
            ax.errorbar(i + off, m[i], yerr=[[m[i] - ci[i, 0]], [ci[i, 1] - m[i]]],
                        fmt=mk, color=col, ms=9, mec='white', mew=1.2, capsize=4,
                        lw=1.6, zorder=4)
    ms_ = d['swan'].mean(); ci_ = boot_ci(d['swan'], rng)
    ax.errorbar(1.20, ms_, yerr=[[ms_ - ci_[0]], [ci_[1] - ms_]], fmt='s', color=C_VEG,
                mfc=SURFACE, ms=9, mew=1.8, capsize=4, lw=1.6, zorder=4)
    ax.text(1.20, ci_[0] - 0.006, 'canopy\nalso in\nSWAN', ha='center', va='top',
            fontsize=8.5, color=MUTED)
    ax.set_xticks([0, 1]); ax.set_xticklabels(['bare bed', 'canopy'], fontsize=10)
    ax.set_xlim(-0.35, 1.45)
    ax.set_ylabel('Mean Liu--Weisberg skill', fontsize=10, color=MUTED)
    ax.set_title('(a) Mean skill of the four configurations', loc='left', fontsize=11,
                 color=INK, pad=8)
    ax.legend(handles=[Line2D([], [], color=INK, ls=':', marker='o', mfc=MUTED, mec='white',
                              label='no wave coupling'),
                       Line2D([], [], color=INK, ls='--', marker='s', mfc=MUTED, mec='white',
                              label='wave coupling')],
              fontsize=9, frameon=False, loc='upper left')
    style(ax)

    # (b) paired contrasts
    ax = fig.add_subplot(gs[0, 1])
    rows = []
    ys = np.arange(len(CONTRASTS))[::-1]
    for y, (lab, a, b) in zip(ys, CONTRASTS):
        x = (d[a] - d[b]).values
        m = x.mean(); lo, hi = boot_ci(x, rng)
        clear = not (lo <= 0 <= hi)
        col = C_VEG if lab.startswith('Canopy,') else (INK if lab.startswith('Waves') else MUTED)
        ax.plot([lo, hi], [y, y], '-', color=col, lw=2.4, alpha=0.9 if clear else 0.45,
                solid_capstyle='round', zorder=3)
        ax.plot(m, y, 'o', ms=8.5, mfc=col if clear else SURFACE, mec=col, mew=1.6, zorder=4)
        ax.text(0.25, y, f'{m:+.3f}', va='center', ha='right', fontsize=8.8, color=INK)
        rows.append(dict(contrast=lab, treated=a, control=b, mean=m, lo=lo, hi=hi,
                         n_better=int((x > 0).sum()), n_worse=int((x < 0).sum()),
                         clear_of_zero=clear))
        print(f'{lab:36s} {m:+.3f} [{lo:+.3f}, {hi:+.3f}] {int((x > 0).sum())}/{len(x)} better')
    ax.axvline(0, color=INK, lw=1.0, zorder=2)
    for yy in (ys[2] - 0.5, ys[5] - 0.5):
        ax.axhline(yy, color='#c9c7c1', lw=0.9, zorder=1)
    ax.set_yticks(ys); ax.set_yticklabels([c[0] for c in CONTRASTS], fontsize=9.2)
    ax.set_xlim(-0.07, 0.26)
    ax.set_ylim(-0.6, len(CONTRASTS) - 0.4)
    ax.set_xlabel('Paired change in Liu--Weisberg skill, mean over 35 drifters',
                  fontsize=10, color=MUTED)
    ax.set_title('(b) Single-factor contrasts, 95% bootstrap interval', loc='left',
                 fontsize=11, color=INK, pad=8)
    style(ax, grid='x')
    pd.DataFrame(rows).to_csv(PROC / f'attribution_2x2{SUFFIX}.csv', index=False,
                              float_format='%.4f')

    # (c) canopy contrast by deployment
    ax = fig.add_subplot(gs[1, :])
    deps = sorted(d['deploy'].unique())
    for lab, a, b, col, off in (('no wave coupling', 'nowaves_veg', 'nowaves', C_VEG_LIGHT, -0.19),
                                ('wave coupling', 'nodm_veg', 'nodm', C_VEG, 0.19)):
        v = [(d.loc[d.deploy == dp, a] - d.loc[d.deploy == dp, b]).mean() for dp in deps]
        ax.bar(np.arange(len(deps)) + off, v, width=0.36, color=col, edgecolor='white',
               lw=0.6, label=lab, zorder=3)
    n = d.groupby('deploy').size()
    ax.axhline(0, color=INK, lw=1.0, zorder=4)
    ax.set_xticks(range(len(deps)))
    ax.set_xticklabels([f'{int(dp)}\n({n[dp]})' for dp in deps], fontsize=8.8)
    ax.set_xlabel('Deployment (drifters)', fontsize=10, color=MUTED)
    ax.set_ylabel('Change in skill\nfrom the canopy', fontsize=10, color=MUTED)
    ax.set_title('(c) Canopy contrast by deployment', loc='left', fontsize=11, color=INK, pad=8)
    ax.legend(fontsize=9, frameon=False, loc='upper right', ncol=2)
    style(ax, grid='y')

    for ext in ('png', 'pdf'):
        p = FIG / f'ensemble_attribution.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
