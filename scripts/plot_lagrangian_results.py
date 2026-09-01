"""The three Lagrangian metrics Section 4.2 reports, one panel each.

This used to carry a wave-contrast panel and a transport-rate panel. The wave
contrast duplicated a panel of the attribution figure and put waves in the
subject position of a section whose result is the canopy, and the transport rate
said in a lollipop what the path ratio says per drifter. Both are gone.

What is here instead is the trajectory error split the way Section 4.2 states
it: how far the particles went, how well they held their heading, and the skill
score that combines the two. All three on the same eight categories and the same
colour convention as the rest of the manuscript, so the reader compares them by
looking down a column.

Every panel shows one point per drifter, not a summary, because the spread
within a configuration is comparable to the difference between configurations
in the bare arm and much smaller in the vegetated one, which is itself a result.

Output: figures/lagrangian_results.{png,pdf}
"""
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, TAG, FACTORS, scored

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE, INK, MUTED, GRID = '#ffffff', '#1b1b1b', '#6b6b6b', '#e8e7e4'
C_BARE, C_VEG = '#eb6834', '#4a3aa7'

CODE = {'nowaves': '---', 'nowaves_veg': '-V-', 'nodm': 'W--',
        'nodm_veg': 'WV-', 'nowaves_dm': '--M', 'nowaves_vegdm': '-VM',
        'bl': 'W-M', 'veg': 'WVM'}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, axis='y', zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9.5)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'):
        ax.spines[sp].set_color('#c9c7c1')


def strip(ax, vals, rng, ref=None):
    """One point per drifter, with the mean drawn as a bar."""
    for i, k in enumerate(KEYS):
        v = np.asarray(vals[k], float)
        v = v[np.isfinite(v)]
        col = C_VEG if FACTORS[k]['roughness'] == 'vegetated' else C_BARE
        ax.scatter(i + rng.uniform(-0.19, 0.19, len(v)), v, s=13, color=col,
                   alpha=0.45, linewidths=0, zorder=3)
        ax.plot([i - 0.32, i + 0.32], [v.mean()] * 2, '-', color=col, lw=2.8,
                zorder=5, solid_capstyle='round')
    if ref is not None:
        ax.axhline(ref, color=INK, lw=1.0, ls='--', zorder=2)
    ax.set_xticks(range(len(KEYS)))
    ax.set_xticklabels([CODE[k] for k in KEYS], fontsize=9.5,
                       family='DejaVu Sans Mono')
    ax.set_xlim(-0.6, len(KEYS) - 0.4)
    style(ax)


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    rng = np.random.default_rng(17)

    met = {k: scored(pd.read_csv(PROC / f'drifter_metrics_{TAG[k]}.csv'),
                     verbose=(k == KEYS[0])) for k in KEYS}
    dec = pd.read_csv(PROC / 'transport_error_decomposition.csv')
    dec = {k: g for k, g in dec.groupby('member')}

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 4.3), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.055, right=0.99, top=0.88, bottom=0.20,
                        wspace=0.22)

    strip(axes[0], {k: met[k].LW_skill.values for k in KEYS}, rng)
    axes[0].set_ylabel('Liu--Weisberg skill', fontsize=10, color=MUTED)
    axes[0].set_title(f'(a) Skill, {len(met[KEYS[0]])} drifters', loc='left',
                      fontsize=11, color=INK, pad=8)

    strip(axes[1], {k: dec[k].speed_ratio.values for k in KEYS}, rng, ref=1.0)
    axes[1].set_ylabel('Simulated / observed path length', fontsize=10,
                       color=MUTED)
    axes[1].set_title('(b) Distance travelled', loc='left', fontsize=11,
                      color=INK, pad=8)

    strip(axes[2], {k: dec[k].heading_err_deg.values for k in KEYS}, rng)
    axes[2].set_ylabel('Mean heading error (degrees)', fontsize=10, color=MUTED)
    axes[2].set_title('(c) Direction held', loc='left', fontsize=11, color=INK,
                      pad=8)

    fig.text(0.055, 0.035, 'W wave coupling    V seagrass canopy    '
             'M mobile bed        orange, bare        purple, canopy',
             fontsize=9, color=MUTED, ha='left')

    for ext in ('png', 'pdf'):
        p = FIG / f'lagrangian_results.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)

    print(f"\n{'member':8s} {'LW':>7s} {'path':>7s} {'heading':>8s}")
    for k in KEYS:
        print(f'{CODE[k]:8s} {met[k].LW_skill.mean():7.3f} '
              f'{dec[k].speed_ratio.mean():7.2f} '
              f'{dec[k].heading_err_deg.mean():7.1f}d')


if __name__ == '__main__':
    main()
