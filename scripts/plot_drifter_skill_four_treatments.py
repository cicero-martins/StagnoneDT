"""Lagrangian skill across the closed factorial, under four roughness treatments.

Section 4.3 claims distributed roughness acts only where waves and a mobile bed
coexist. This is the figure that tests it, and it does not survive: under both
parameterisations that actually deliver a canopy, roughness helps in ALL FOUR
cells, and the full cell is the one that responds LEAST.

The four treatments are not four options. Two of them work and two do not, for
reasons established by measurement rather than preference:

  uniform        Manning 0.023 everywhere, the control
  Baptist 153    trachytopes, meadow applied. Works because 153 folds the
                 canopy into a single Chezy and needs no momentum sink.
  Baptist 154    trachytopes. Computes a canopy momentum sink that this build
                 never reads, so it delivers only its bed Chezy and makes the
                 meadow SMOOTHER than bare sand. Negative in all four cells.
  [veg]          FM's own vegetation module, where the sink does reach the
                 momentum equation. Every parameter from literature; nothing
                 fitted to any observation, drifters included.

Panel (b) carries the argument, so it gets the space: the roughness contrast is
each member minus the uniform control of its own cell, paired per drifter with
a 4000-resample bootstrap interval.

One asymmetry is marked rather than averaged away: in the waves + mobile bed
cell the 153 entry is the ORIGINAL member, whose .arl reached 5.5% of the
meadow, because 153 with the meadow correctly applied aborts in exactly that
configuration. There is no corrected 153 there to compare against.

    python scripts/plot_drifter_skill_four_treatments.py
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

NBOOT, SEED = 4000, 17
KEY = ['deploy', 'drifter_id']

# cell label, uniform control, 153, 154, [veg], and whether the 153 entry is
# the uncorrected original
CELLS = [
    ('no waves\nfixed bed', 'v04AE_nowaves', 'v04AE_nowaves_vr_arlfix',
     'v04AE_nowaves_vr_154', 'v04AE_veg_hv040', False),
    ('waves\nfixed bed', 'v04AE_nodm', 'v04AE_nodm_vr_arlfix',
     'v04AE_nodm_vr_154shore', 'v04AE_veg_waves', False),
    ('no waves\nmobile bed', 'v04AE_nowaves_dm', 'v04AE_nowaves_vrdm_arlfix',
     'v04AE_nowaves_vrdm_154', 'v04AE_veg_nowaves_dm', False),
    ('waves\nmobile bed', 'v04AE', 'v04AE_vr', 'v04AE_vr_154',
     'v04AE_veg_waves_dm', True),
]
# Validated all-pairs: worst CVD dE 21.3 (protan), normal-vision 25.3, every
# hue clear of the 3:1 contrast floor.
TREAT = [('Baptist 153', '#4a3aa7'), ('Baptist 154', '#eb6834'),
         ('[veg] module', '#0f9bd0')]
INK, MUTED, GRID, SURFACE = '#1c1c1c', '#6b6b6b', '#e2e1dd', '#ffffff'
REF = '#8c8c8c'


def lw(tag):
    return pd.read_csv(PROC / f'drifter_metrics_{tag}.csv')[KEY + ['LW_skill']]


def contrast(tag, ctrl, rng):
    j = lw(tag).merge(lw(ctrl), on=KEY, suffixes=('_t', '_c'))
    d = (j.LW_skill_t - j.LW_skill_c).values
    idx = rng.integers(0, len(d), size=(NBOOT, len(d)))
    lo, hi = np.percentile(d[idx].mean(axis=1), [2.5, 97.5])
    return d.mean(), lo, hi, int((d > 0).sum()), len(d)


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    rng = np.random.default_rng(SEED)

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(11.4, 4.5), dpi=300,
        gridspec_kw=dict(width_ratios=[1.0, 1.35], wspace=0.32))
    fig.patch.set_facecolor(SURFACE)
    ys = np.arange(len(CELLS))[::-1]
    off = {0: +0.22, 1: 0.0, 2: -0.22}

    for i, (lab, u, a, b, v, partial) in enumerate(CELLS):
        y = ys[i]
        axA.plot(lw(u).LW_skill.mean(), y, 'o', ms=8, mfc='none', mec=REF,
                 mew=1.6, zorder=3)
        for k, (tag, (tlab, col)) in enumerate(zip((a, b, v), TREAT)):
            axA.plot(lw(tag).LW_skill.mean(), y + off[k], 'o', ms=7, color=col,
                     mec='white', mew=0.8, zorder=4)
            m, lo, hi, npos, n = contrast(tag, u, rng)
            axB.plot([lo, hi], [y + off[k]] * 2, '-', color=col, lw=2.4,
                     solid_capstyle='round', alpha=0.55, zorder=3)
            axB.plot(m, y + off[k], 'o', ms=7, color=col, mec='white',
                     mew=0.8, zorder=4)
            if k == 0 and partial:
                axB.text(m, y + off[k] + 0.13, '†', fontsize=11, color=col,
                         ha='center', va='bottom', zorder=5)

    for ax, xlab, title in (
            (axA, 'Liu-Weisberg skill', '(a)  skill by cell'),
            (axB, 'skill minus the cell’s uniform control',
             '(b)  the roughness contrast, with 95% bootstrap interval')):
        ax.set_yticks(ys)
        ax.set_ylim(-0.55, len(CELLS) - 0.45)
        ax.set_xlabel(xlab, fontsize=9, color=MUTED)
        ax.set_title(title, loc='left', fontsize=10, color=INK, pad=8)
        ax.grid(True, axis='x', color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=8.5, colors=MUTED)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        for s in ('left', 'bottom'):
            ax.spines[s].set_color(GRID)
    axA.set_yticklabels([c[0] for c in CELLS], fontsize=8.5, color=INK)
    axB.set_yticklabels([])
    axB.axvline(0, color=INK, lw=1.0, zorder=2)

    h = [plt.Line2D([], [], ls='none', marker='o', ms=8, mfc='none', mec=REF,
                    mew=1.6, label='uniform roughness (control)')]
    h += [plt.Line2D([], [], ls='none', marker='o', ms=7, color=c, mec='white',
                     mew=0.8, label=l) for l, c in TREAT]
    fig.legend(handles=h, loc='lower center', ncol=4, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, -0.045))
    fig.text(0.5, -0.10,
             '†  in this cell the 153 entry is the ORIGINAL member, whose .arl '
             'reached 5.5% of the meadow: 153 with the meadow correctly '
             'applied aborts here, so no corrected 153 exists to compare '
             'against.', fontsize=7.5, color=MUTED, ha='center')
    fig.suptitle('Distributed roughness helps in every cell, and least where '
                 'the manuscript says it acts',
                 fontsize=11.5, color=INK, x=0.007, ha='left', y=1.02)

    fig.subplots_adjust(left=0.115, right=0.985, top=0.86, bottom=0.20)
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_skill_four_treatments.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'wrote {p}')
    plt.close(fig)

    print(f"\n{'cell':22s} {'uniform':>8s} " +
          ' '.join(f'{l:>13s}' for l, _ in TREAT))
    for lab, u, a, b, v, partial in CELLS:
        row = f"{lab.replace(chr(10), ' '):22s} {lw(u).LW_skill.mean():8.3f} "
        for tag in (a, b, v):
            m, lo, hi, npos, n = contrast(tag, u, rng)
            row += f'{lw(tag).LW_skill.mean():6.3f} ({m:+.3f})'
        print(row + ('   <- 153 nao corrigida' if partial else ''))


if __name__ == '__main__':
    main()
