"""What the seagrass classes do to the flow.

A caution the figure is built around. Comparing classes WITHIN one configuration
does not isolate the canopy, because the classes sit in different parts of the
basin at different depths. The bare configurations prove it: with no canopy at
all, their Posidonia cells are still slower at the bed than their sand cells, by
a ratio near 0.86. That difference is geography, not canopy drag. The canopy
effect becomes visible when the SAME class is compared BETWEEN configurations,
which is what panel (b) does.

(a) Bed and surface speed by class. The four members of each arm are collapsed
    into a mean and a band, because sixteen individual lines cannot be told
    apart and the within-arm spread is the only thing they carried. Colour is
    the canopy treatment throughout the manuscript, so it is the canopy
    treatment here too, and the two depths are separated by marker and dash.
(c) The canopy effect on bed speed, class by class, averaged over the four cells
    of the design.

Wave orbital velocity used to be panel (c) and is now reported in the text only.
The canopy enters the momentum equation of the flow and not the roughness field
passed to the wave model, so what the panel showed was a second-order feedback
through the current field: changes under 2.5% whose largest value fell on sand,
which carries no canopy. That is a null result and it reads more honestly as a
sentence than as a plot with an axis stretched to hold it.

Output: figures/class_speed_uorb.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, FACTORS

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
C_BARE = '#eb6834'     # bare bed, uniform roughness
C_VEG = '#4a3aa7'      # seagrass canopy

CLASSES = ['sand', 'Cymodocea', 'Posidonia', 'rock']
ORDER = list(KEYS)
BARE = [k for k in KEYS if FACTORS[k]['roughness'] != 'vegetated']
VEG = [k for k in KEYS if FACTORS[k]['roughness'] == 'vegetated']
# the four canopy contrasts, treated minus its own bare control
PAIRS = [('nowaves_veg', 'nowaves'), ('nodm_veg', 'nodm'),
         ('nowaves_vegdm', 'nowaves_dm'), ('veg', 'bl')]


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#c9c7c1')


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    d = pd.read_csv(PROC / 'class_speed_uorb.csv')

    def piv(metric):
        p = d[d.metric == metric].pivot(index='member', columns='klass',
                                        values='value')
        return p.reindex(ORDER)[CLASSES]

    bed, surf, orb = piv('bed_speed'), piv('surface_speed'), piv('uorb_mean')

    fig = plt.figure(figsize=(10.4, 4.6), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    # The two depths get their own axes rather than sharing one with a dashed
    # line. Two lines needed a colour AND a dash to identify, which was one
    # encoding too many, and the vegetated bed band spans 0.0003 to 0.0016 m/s
    # against an axis of 0.10, so on a shared scale it is thinner than its own
    # line and reads as a missing band rather than as a narrow one.
    gs = fig.add_gridspec(2, 2, width_ratios=[1.3, 1.0], height_ratios=[1, 1],
                          hspace=0.30, wspace=0.26,
                          left=0.085, right=0.985, top=0.90, bottom=0.20)
    x = np.arange(len(CLASSES))

    for row, (tbl, mk, name) in enumerate(((surf, 's', 'Surface layer'),
                                           (bed, 'o', 'Bed layer'))):
        ax = fig.add_subplot(gs[row, 0])
        for keys, col in ((BARE, C_BARE), (VEG, C_VEG)):
            v = tbl.loc[keys]
            ax.fill_between(x, v.min(), v.max(), color=col, alpha=0.20, lw=0,
                            zorder=2)
            ax.plot(x, v.mean(), '-', color=col, marker=mk, ms=5.5, lw=2.0,
                    mec='white', mew=1.0, zorder=4)
        ax.set_xlim(-0.3, len(CLASSES) - 0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(CLASSES if row else [], fontsize=9.5)
        ax.set_ylabel('m s$^{-1}$', fontsize=9.5, color=MUTED)
        ax.set_title(f'({"ab"[row]}) {name}', loc='left', fontsize=10.5,
                     color=INK, pad=6)
        style(ax)
        if row == 1:
            ax.legend(handles=[
                Line2D([], [], color=C_BARE, lw=2.4, marker='o', ms=5.5,
                       mec='white', label='Bare'),
                Line2D([], [], color=C_VEG, lw=2.4, marker='o', ms=5.5,
                       mec='white', label='Canopy'),
                Patch(facecolor=MUTED, alpha=0.26,
                      label='range over the four configurations')],
                fontsize=9, frameon=False, loc='upper center',
                bbox_to_anchor=(0.5, -0.22), ncol=3, columnspacing=1.6)

    # (c) canopy effect on bed speed, averaged over the four cells
    ax = fig.add_subplot(gs[:, 1])
    rel = pd.DataFrame({c: [100 * (bed.loc[a, c] / bed.loc[b, c] - 1)
                            for a, b in PAIRS] for c in CLASSES})
    ys = np.arange(len(CLASSES))[::-1]
    for y, c in zip(ys, CLASSES):
        m, lo, hi = rel[c].mean(), rel[c].min(), rel[c].max()
        ax.plot([lo, hi], [y, y], '-', color=C_VEG, lw=6, alpha=0.28,
                zorder=3, solid_capstyle='round')
        ax.plot([0, m], [y, y], '-', color=C_VEG, lw=3.0, zorder=4,
                solid_capstyle='round')
        ax.plot([m], [y], 'o', ms=9, mfc=C_VEG, mec='white', mew=1.4, zorder=5)
        ax.text(lo - 2.5, y, f'{m:+.0f}%', fontsize=9.5, color=INK,
                va='center', ha='right')
    ax.axvline(0, color=INK, lw=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels(CLASSES, fontsize=9.5)
    ax.set_xlim(rel.min().min() - 16, 4)
    ax.set_ylim(-0.6, len(CLASSES) - 0.4)
    ax.set_xlabel('Change in bed speed (%)', fontsize=10, color=MUTED)
    ax.set_title('(c) Canopy effect on bed speed', loc='left', fontsize=10.5,
                 color=INK, pad=8)
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'class_speed_uorb.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)

    print('\n=== Posidonia/sand bed-speed ratio by configuration ===')
    for m in ORDER:
        print(f'  {m:15s} {bed.loc[m, "Posidonia"] / bed.loc[m, "sand"]:.3f}')
    print('\n=== canopy effect on bed speed, mean over the four cells ===')
    for c in CLASSES:
        print(f'  {c:11s} {rel[c].mean():+6.1f}%  '
              f'(range {rel[c].min():+.1f} to {rel[c].max():+.1f})')
    print('\n=== canopy effect on orbital velocity, the two wave-coupled cells ===')
    for c in CLASSES:
        a = 100 * (orb.loc['nodm_veg', c] / orb.loc['nodm', c] - 1)
        b = 100 * (orb.loc['veg', c] / orb.loc['bl', c] - 1)
        print(f'  {c:11s} fixed bed {a:+5.1f}%   mobile bed {b:+5.1f}%')


if __name__ == '__main__':
    main()
