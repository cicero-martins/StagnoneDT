"""Vertical profile of mean current speed inside the lagoon, by ensemble member.

Answers two separate questions with one figure.

For RQ1: how much vertical structure does a sub-metre basin actually carry?
Restricted to the lagoon interior (4043 wet faces, inlets excluded) over the
drifter window, surface speed is 1.9 to 4.5 times bed speed depending on the
member. Even the weakest case is a factor near two, which is the quantitative
argument for running this basin in 3D rather than depth-averaged.

For the attribution thread: the bed treatment, not the roughness treatment,
dominates the vertical structure. The three fixed-bed members sit on top of one
another at a shear ratio near 2. Both morphodynamic members roughly double it,
by nearly halving the near-bed speed rather than by speeding up the surface.
Distributed roughness on top of that lowers the surface speed, which is what
canopy drag should do.

What it does NOT do is explain the drifter transport gap. vr's lagoon-mean
surface speed (0.078 m/s) is no higher than nodm's (0.080), yet vr's particles
travel at 0.142 m/s against nodm's 0.121. Whatever the drifters are responding
to, it is not the basin-mean surface speed.

Colour encodes the bed treatment and line style the roughness treatment, which
keeps five members on two validated hues and makes the factorial readable.

Input:  data/processed/layer_profile_lagoon.csv
        (produced by scripts/extract_layer_profile_lagoon.py, run on the server)
Output: figures/layer_profile_lagoon.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, LABEL

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
C_FIXED = '#eb6834'    # fixed bed
C_MORPH = '#4a3aa7'    # active morphodynamics

STYLE = {                       # member -> (colour, linestyle, label)
    'nowaves':      (C_FIXED, ':',  'no waves, uniform, fixed'),
    'nowaves_vr':   (C_FIXED, '--', 'no waves, distributed, fixed'),
    'nowaves_dm':   (C_FIXED, '-',  'no waves, uniform, mobile'),
    'nowaves_vrdm': (C_FIXED, '-.', 'no waves, distributed, mobile'),
    'nodm':         (C_MORPH, ':',  'waves, uniform, fixed'),
    'nodm_vr':      (C_MORPH, '--', 'waves, distributed, fixed'),
    'bl':           (C_MORPH, '-',  'waves, uniform, mobile'),
    'vr':           (C_MORPH, '-.', 'waves, distributed, mobile'),
}
ORDER = list(KEYS)


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    df = pd.read_csv(PROC / 'layer_profile_lagoon.csv')
    nfaces = int(df['n_faces'].iloc[0])

    print(f'Lagoon interior: {nfaces} wet faces')
    print(f"{'member':10s} {'bed':>8s} {'surface':>9s} {'shear':>7s}")
    shear = {}
    for k in ORDER:
        g = df[df['member'] == k].sort_values('layer')
        bed, surf = g['mean_speed'].iloc[0], g['mean_speed'].iloc[-1]
        shear[k] = surf / bed
        print(f'{k:10s} {bed:8.4f} {surf:9.4f} {shear[k]:7.2f}')

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.6), dpi=300,
                             gridspec_kw=dict(width_ratios=[1.5, 1.0],
                                              wspace=0.32))
    fig.patch.set_facecolor(SURFACE)

    ax = axes[0]
    for k in ORDER:
        g = df[df['member'] == k].sort_values('layer')
        colour, ls, lab = STYLE[k]
        ax.plot(g['mean_speed'], g['layer'], ls, color=colour, lw=2.0,
                marker='o', ms=4, mfc=colour, mec='white', mew=0.8, zorder=3)
    ax.set_xlabel('Mean speed (m s$^{-1}$)', fontsize=8.5, color=MUTED)
    ax.set_ylabel('Sigma layer', fontsize=8.5, color=MUTED)
    ax.set_yticks(range(10))
    ax.text(-0.14, 0.02, 'bed', transform=ax.transAxes, fontsize=8,
            color=MUTED, rotation=90, va='bottom')
    ax.text(-0.14, 0.98, 'surface', transform=ax.transAxes, fontsize=8,
            color=MUTED, rotation=90, va='top')
    ax.set_title('(a) Vertical profile, lagoon interior', loc='left',
                 fontsize=9.5, color=INK, pad=7)
    style(ax)

    handles = [Line2D([0], [0], color=STYLE[k][0], ls=STYLE[k][1], lw=2.0,
                      label=STYLE[k][2]) for k in ORDER]
    ax.legend(handles=handles, fontsize=7.5, frameon=False, loc='lower right',
              title='bed, roughness', title_fontsize=7.5)

    ax2 = axes[1]
    ys = np.arange(len(ORDER))[::-1]
    for y, k in zip(ys, ORDER):
        colour = STYLE[k][0]
        ax2.plot([1, shear[k]], [y, y], '-', color=colour, lw=3.0, alpha=0.85,
                 zorder=3, solid_capstyle='round')
        ax2.plot([shear[k]], [y], 'o', ms=8, mfc=colour, mec='white', mew=1.2,
                 zorder=4)
        ax2.text(shear[k] + 0.10, y, f'{shear[k]:.1f}x', fontsize=8,
                 color=INK, va='center', ha='left')
    ax2.axvline(1, color=INK, lw=1.0, zorder=2)
    ax2.set_yticks(ys)
    ax2.set_yticklabels(ORDER, fontsize=8.5)
    ax2.set_xlim(0.8, max(shear.values()) * 1.20)
    ax2.set_ylim(-0.6, len(ORDER) - 0.4)
    ax2.set_xlabel('Surface speed / bed speed', fontsize=8.5, color=MUTED)
    ax2.set_title('(b) Vertical shear', loc='left', fontsize=9.5, color=INK,
                  pad=7)
    style(ax2)

    for ext in ('png', 'pdf'):
        p = FIG / f'layer_profile_lagoon.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#c9c7c1')


if __name__ == '__main__':
    main()
