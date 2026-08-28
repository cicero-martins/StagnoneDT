"""Every deployment, in the cell that carries the complete physics.

This exists to answer a specific worry: that the waves + mobile bed cell
performs worse. It does not. Its uniform control is the BEST of the four
(0.624 against 0.469 to 0.539) and its vegetated member sits in the pack
(0.711 against 0.693 to 0.735). What is smaller there is the roughness
CONTRAST, and the reason is measurable.

In the uniform arm each process alone hurts -- waves -0.035, mobile bed -0.071
with 0 of 35 drifters improving -- yet together they help, +0.084. Additive
would predict -0.106, so the interaction term is +0.190. In the vegetated arm
the same term is +0.028. The synergy exists only when the meadow is missing,
which is what compensating errors look like: without a canopy the bed is too
smooth, and waves plus a mobile bed reproduce by another route part of the flow
structure the meadow would have produced. Put the meadow in and the
compensation has nothing left to do.

So the small contrast is not the vegetation failing here. It is the control
being unusually good for the wrong reason.

All twelve deployments, one panel each, showing the median-skill drifter of the
deployment. The number under each panel is the deployment mean over its three
drifters, which is what the ensemble statistics use -- the drawn track is one
member of it, not a summary.

    python scripts/plot_drifter_tracks_full_physics_all12.py
"""
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_drifter_trajectories_paper1 import (parse_ldb, split_long_segments,
                                              hav, pick_drifter)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model' / 'dflowfm_v04AE'
FIG = ROOT / 'figures'

SURFACE, INK, MUTED, GRID = '#ffffff', '#1b1b1b', '#6b6b6b', '#e8e7e4'
LAND, LAND_EDGE, REF = '#efece6', '#c9c7c1', '#8c8c8c'
CVEG = '#0f9bd0'
UNIF, VEG = 'v04AE', 'v04AE_veg_waves_dm'
PAD_FRAC = 0.16


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    su = pd.read_csv(PROC / f'drifter_sim_{UNIF}.csv', parse_dates=['time'])
    sv = pd.read_csv(PROC / f'drifter_sim_{VEG}.csv', parse_dates=['time'])
    mu = pd.read_csv(PROC / f'drifter_metrics_{UNIF}.csv')
    mv = pd.read_csv(PROC / f'drifter_metrics_{VEG}.csv')

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)
    deploys = sorted(mu.deploy.unique())

    fig, axes = plt.subplots(3, 4, figsize=(11.6, 8.6), dpi=300)
    fig.patch.set_facecolor(SURFACE)

    for ax, dep in zip(axes.ravel(), deploys):
        did = pick_drifter(mv, dep)
        o = obs[(obs.deploy == dep) & (obs.source == did)].sort_values('time')
        t0, t1 = o.time.min(), o.time.max()

        def clip(s):
            g = s[(s.deploy == dep) & (s.drifter_id == did) &
                  (s.time >= t0) & (s.time <= t1)]
            return g.sort_values('time')

        gu, gv = clip(su), clip(sv)
        xs = [o.lon.values] + [g.lon.values for g in (gu, gv) if len(g) > 1]
        ys = [o.lat.values] + [g.lat.values for g in (gu, gv) if len(g) > 1]
        lo, la = np.concatenate(xs), np.concatenate(ys)
        cx, cy = (lo.min() + lo.max()) / 2, (la.min() + la.max()) / 2
        asp = 1.0 / np.cos(np.radians(cy))
        half = max((lo.max() - lo.min()) / 2,
                   (la.max() - la.min()) * asp / 2) * (1 + PAD_FRAC)
        ax.set_xlim(cx - half, cx + half)
        ax.set_ylim(cy - half / asp, cy + half / asp)

        for p in land:
            ax.fill(p[:, 0], p[:, 1], color=LAND, ec='none', zorder=1)
        for p in coast:
            ax.plot(p[:, 0], p[:, 1], '-', color=LAND_EDGE, lw=0.5, zorder=2)

        ax.plot(o.lon, o.lat, '-', color=INK, lw=2.6, zorder=6,
                solid_capstyle='round')
        ax.plot(o.lon.iloc[0], o.lat.iloc[0], 'o', ms=6.5, mfc='white',
                mec=INK, mew=1.7, zorder=9)
        ax.plot(o.lon.iloc[-1], o.lat.iloc[-1], 's', ms=6.5, mfc=INK,
                mec='white', mew=1.2, zorder=9)
        for g, col, z in ((gu, REF, 4), (gv, CVEG, 5)):
            if len(g) < 2:
                continue
            ax.plot(g.lon, g.lat, '-', color=col, lw=2.0, zorder=z, alpha=0.95,
                    solid_capstyle='round')
            ax.plot(g.lon.iloc[-1], g.lat.iloc[-1], 's', ms=6, mfc=col,
                    mec='white', mew=1.2, zorder=z + 3)

        du = mu[mu.deploy == dep].LW_skill.mean()
        dv = mv[mv.deploy == dep].LW_skill.mean()
        # Panel extents differ by an order of magnitude across deployments --
        # 0.4 h against 7.2 h -- so a fixed 500 m bar runs off the short ones.
        # Pick the largest round length that fits in 40% of the panel.
        span = hav(cx - half, cy, cx + half, cy)
        bar = max([b for b in (50, 100, 200, 500, 1000) if b <= 0.40 * span],
                  default=50)
        fr = bar / span
        x0, y0 = cx - half * 0.90, cy + half / asp * 0.87
        ax.plot([x0, x0 + fr * 2 * half], [y0, y0], '-', color=INK, lw=1.8,
                zorder=9, solid_capstyle='butt')
        ax.text(x0 + fr * half, y0, f'{bar} m', fontsize=6.5, color=INK,
                ha='center', va='bottom', zorder=9)
        hrs = (t1 - t0).total_seconds() / 3600
        ax.set_title(f'Deployment {dep}   ({hrs:.1f} h)', loc='left',
                     fontsize=9, color=INK, pad=4)
        # deployment mean over its three drifters, not the drawn track
        ax.text(0.035, 0.055, 'deployment mean LW', transform=ax.transAxes,
                fontsize=6.5, color=MUTED, ha='left', va='bottom')
        ax.plot(0.055, 0.155, 's', ms=4.5, color=REF, transform=ax.transAxes,
                clip_on=False, zorder=10)
        ax.text(0.095, 0.125, f'{du:.2f}', transform=ax.transAxes,
                fontsize=7.5, color=INK, ha='left', va='bottom')
        ax.plot(0.265, 0.155, 's', ms=4.5, color=CVEG, transform=ax.transAxes,
                clip_on=False, zorder=10)
        ax.text(0.305, 0.125, f'{dv:.2f}', transform=ax.transAxes,
                fontsize=7.5, color=INK, ha='left', va='bottom')
        ax.text(0.985, 0.125, f'{dv - du:+.2f}', transform=ax.transAxes,
                fontsize=7.5, ha='right', va='bottom',
                color=CVEG if dv >= du else '#b3341f')
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_facecolor(SURFACE)
        for s_ in ax.spines.values():
            s_.set_color(GRID)

    h = [Line2D([], [], color=INK, lw=2.6, label='Observed'),
         Line2D([], [], color=REF, lw=2.0, label='Uniform roughness (control)'),
         Line2D([], [], color=CVEG, lw=2.0, label='[veg] module, literature only'),
         Line2D([], [], ls='none', marker='o', mfc='white', mec=INK, mew=1.7,
                ms=6.5, label='Release'),
         Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white', mew=1.2,
                ms=6.5, label='End of scored window')]
    fig.legend(handles=h, loc='lower center', ncol=5, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, -0.014))
    fig.suptitle('Waves and mobile bed, all twelve deployments: the meadow '
                 'improves eleven of them',
                 fontsize=12, color=INK, x=0.008, ha='left', y=0.997)
    fig.subplots_adjust(left=0.012, right=0.988, top=0.93, bottom=0.055,
                        wspace=0.06, hspace=0.18)
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_tracks_full_physics_all12.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'wrote {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
