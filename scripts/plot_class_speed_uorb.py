"""What the roughness classes do to the flow and to the waves.

A caution the figure is built around. Comparing classes WITHIN one member does
not isolate the roughness treatment, because the classes sit in different parts
of the basin at different depths. The uniform-roughness members prove it: with
no roughness distinction at all, their Posidonia cells are still slower at the
bed than their sand cells, by a ratio near 0.86. That difference is geography,
not vegetation drag. The roughness effect only becomes visible when the SAME
class is compared BETWEEN members, which is what panels (b) and (c) do.

(a) Bed and surface speed by class, all members, to show the baseline
    geographic pattern and how the bed treatment reshapes it.
(b) The roughness effect on bed speed, fixed bed, as the change from uniform to
    distributed within each class.
(c) The same for wave orbital velocity, where the effect is much larger and
    ordered exactly as canopy attenuation predicts.

Output: figures/class_speed_uorb.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, LABEL as LBL

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
C_BED = '#eb6834'
C_SURF = '#4a3aa7'
C_ORB = '#1baf7a'

CLASSES = ['sand', 'Cymodocea', 'Posidonia', 'rock']
ORDER = list(KEYS)
LABEL = {k: LBL[k].replace(chr(10), ' ') for k in KEYS}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#c9c7c1')


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    d = pd.read_csv(PROC / 'class_speed_uorb.csv')

    def piv(metric):
        p = d[d.metric == metric].pivot(index='member', columns='klass',
                                        values='value')
        return p.reindex(ORDER)[CLASSES]

    bed, surf = piv('bed_speed'), piv('surface_speed')
    orb = piv('uorb_mean')

    fig = plt.figure(figsize=(11.0, 4.2), dpi=300)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 1.0, 1.0], wspace=0.32,
                          left=0.06, right=0.98, top=0.86, bottom=0.20)
    fig.patch.set_facecolor(SURFACE)

    # (a) bed and surface speed by class, per member
    ax = fig.add_subplot(gs[0, 0])
    x = np.arange(len(CLASSES))
    # No horizontal offset: members sit on the same class positions and are
    # separated by opacity, so the class grouping stays legible.
    for m in ORDER:
        vr = m == 'vr'
        ax.plot(x, surf.loc[m], 's-', color=C_SURF, ms=5 if vr else 3.5,
                lw=2.0 if vr else 1.0, alpha=1.0 if vr else 0.38,
                zorder=5 if vr else 3)
        ax.plot(x, bed.loc[m], 'o-', color=C_BED, ms=5 if vr else 3.5,
                lw=2.0 if vr else 1.0, alpha=1.0 if vr else 0.38,
                zorder=5 if vr else 3)
    ax.set_xlim(-0.35, len(CLASSES) - 0.65)
    ax.set_xticks(x)
    ax.set_xticklabels(CLASSES, fontsize=8)
    ax.set_ylabel('Mean speed (m s$^{-1}$)', fontsize=8.5, color=MUTED)
    ax.set_title('(a) Speed by class, every member', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    ax.legend(handles=[
        Line2D([0], [0], marker='s', color=C_SURF, ms=5, lw=1.2, label='surface'),
        Line2D([0], [0], marker='o', color=C_BED, ms=5, lw=1.2, label='bed'),
        Line2D([0], [0], color='none', label='opaque = full member')],
        fontsize=8, frameon=False, loc='upper center',
        bbox_to_anchor=(0.5, -0.13), ncol=3, columnspacing=1.6)
    style(ax)

    # (b) roughness effect on bed speed, fixed bed
    ax = fig.add_subplot(gs[0, 1])
    rel = 100 * (bed.loc['nodm_vr'] / bed.loc['nodm'] - 1)
    ys = np.arange(len(CLASSES))[::-1]
    for y, c in zip(ys, CLASSES):
        ax.plot([0, rel[c]], [y, y], '-', color=C_BED, lw=3.0, zorder=3,
                solid_capstyle='round')
        ax.plot([rel[c]], [y], 'o', ms=8, mfc=C_BED, mec='white', mew=1.2,
                zorder=4)
        ax.text(rel[c] - 0.15, y, f'{rel[c]:+.1f}%', fontsize=7.5, color=INK,
                va='center', ha='right')
    ax.axvline(0, color=INK, lw=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels(CLASSES, fontsize=8)
    ax.set_xlim(rel.min() * 1.65, 0.8)
    ax.set_ylim(-0.6, len(CLASSES) - 0.4)
    ax.set_xlabel('Change in bed speed (%)', fontsize=8.5, color=MUTED)
    ax.set_title('(b) Roughness effect, fixed bed', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    style(ax)

    # (c) roughness effect on orbital velocity
    ax = fig.add_subplot(gs[0, 2])
    relo = 100 * (orb.loc['nodm_vr'] / orb.loc['nodm'] - 1)
    for y, c in zip(ys, CLASSES):
        ax.plot([0, relo[c]], [y, y], '-', color=C_ORB, lw=3.0, zorder=3,
                solid_capstyle='round')
        ax.plot([relo[c]], [y], 'o', ms=8, mfc=C_ORB, mec='white', mew=1.2,
                zorder=4)
        ax.text(relo[c] - 0.5, y, f'{relo[c]:+.1f}%', fontsize=7.5, color=INK,
                va='center', ha='right')
    ax.axvline(0, color=INK, lw=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels(CLASSES, fontsize=8)
    ax.set_xlim(relo.min() * 1.55, 2.0)
    ax.set_ylim(-0.6, len(CLASSES) - 0.4)
    ax.set_xlabel('Change in orbital velocity (%)', fontsize=8.5, color=MUTED)
    ax.set_title('(c) Roughness effect on waves', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'class_speed_uorb.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)

    print('\n=== Posidonia/sand bed-speed ratio by member ===')
    for m in ORDER:
        print(f'  {LABEL[m]:14s} {bed.loc[m, "Posidonia"] / bed.loc[m, "sand"]:.3f}')
    print('\n=== roughness effect, fixed bed (nodm_vr vs nodm) ===')
    for c in CLASSES:
        print(f'  {c:11s} bed {rel[c]:+5.1f}%   u_orb {relo[c]:+5.1f}%')


if __name__ == '__main__':
    main()
