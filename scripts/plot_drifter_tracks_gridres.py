"""Figure: the same drifters advected on three regrid resolutions.

The target grid handed to OpenDrift is 0.002 degrees, about 222 m, a value that
came from the first regrid script in April 2026 and was never justified. The FM
mesh inside the lagoon has a median nearest-neighbour spacing of 61 m, so that
grid smooths the drift field by roughly a factor of 3.6 before any particle is
released. Refining it to 111 m costs 0.011 of Liu-Weisberg skill, and refining
again to 56 m costs nothing further: the penalty saturates exactly where the
grid passes below the resolution of the mesh feeding it.

This shows what that looks like as trajectories. The three tracks coincide over
most of every panel, which is the result rather than a failure of the drawing,
so they are stroked from widest to narrowest in resolution order. Where they
agree the reader sees one thin line inside a wider halo; where they part, three
lines.

One drifter per panel, the median-skill drifter of that deployment on the
reference grid, the same convention as drifter_trajectories.py. Choosing the
drifter that diverges most would have staged the effect rather than reported it.

Hue carries identity because three near-coincident lines have to be told apart
at a glance; stroke width carries the ordering. Palette validated for CVD
separation, worst adjacent pair dE 22.4 under deuteranopia.

Output: figures/drifter_tracks_gridres.{png,pdf}
"""
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model' / 'dflowfm_v04AE'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_drifter_trajectories_paper1 import (parse_ldb, hav,
                                              split_long_segments, clip_track,
                                              pick_drifter)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
LAND = '#efece6'
LAND_EDGE = '#c9c7c1'

# Coarse to fine, with the stroke width falling in the same order, so a
# coincident stretch reads as three concentric bands rather than one line. The
# steps are wide enough that the middle band survives: at 3.2/2.0/1.1 the 111 m
# track showed as a 0.45 pt sliver and looked as though it had not been drawn.
GRIDS = [('v04AE_nodm', '222 m', '#eb6834', 4.6),
         ('v04AE_nodm_dx001', '111 m', '#4a3aa7', 2.9),
         ('v04AE_nodm_dx0005', '56 m', '#0d9488', 1.3)]
REF = GRIDS[0][0]
PAD_FRAC = 0.16


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    sims = {k: pd.read_csv(PROC / f'drifter_sim_{k}.csv', parse_dates=['time'])
            for k, _, _, _ in GRIDS}
    met = {k: pd.read_csv(PROC / f'drifter_metrics_{k}.csv')
           for k, _, _, _ in GRIDS}
    deploys = sorted(met[REF].deploy.unique())

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)

    fig, axes = plt.subplots(3, 4, figsize=(11.6, 9.2), dpi=300)
    fig.patch.set_facecolor(SURFACE)

    for ax, dep in zip(axes.ravel(), deploys):
        did = pick_drifter(met[REF], dep)
        o = obs[(obs.deploy == dep) & (obs.source == did)].sort_values('time')
        t0, t1 = o.time.min(), o.time.max()
        tracks = {k: clip_track(sims[k], dep, did, t0, t1)
                  for k, _, _, _ in GRIDS}

        xs = [o.lon.values] + [g.lon.values for g in tracks.values()
                               if len(g) > 1]
        ys = [o.lat.values] + [g.lat.values for g in tracks.values()
                               if len(g) > 1]
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

        ax.plot(o.lon, o.lat, '-', color=INK, lw=2.4, zorder=8,
                solid_capstyle='round')
        for z, (k, _, col, lw) in enumerate(GRIDS):
            g = tracks[k]
            if len(g) < 2:
                continue
            ax.plot(g.lon, g.lat, '-', color=col, lw=lw, zorder=4 + z,
                    solid_capstyle='round')
        ax.plot(o.lon.iloc[0], o.lat.iloc[0], 'o', ms=7, mfc='white', mec=INK,
                mew=1.8, zorder=9)
        ax.plot(o.lon.iloc[-1], o.lat.iloc[-1], 's', ms=6.5, mfc=INK,
                mec='white', mew=1.2, zorder=9)

        span = hav(cx - half, cy, cx + half, cy)
        bar = max([b for b in (50, 100, 200, 500, 1000) if b <= 0.40 * span],
                  default=50)
        fr = bar / span
        x0, y0 = cx - half * 0.90, cy + half / asp * 0.87
        ax.plot([x0, x0 + fr * 2 * half], [y0, y0], '-', color=INK, lw=1.8,
                zorder=9, solid_capstyle='butt')
        ax.text(x0 + fr * half, y0, f'{bar} m', fontsize=7, color=INK,
                ha='center', va='bottom', zorder=9)

        # the three skills, directly labelled in their own colours, so the
        # panel carries its own numbers instead of sending the reader to a table
        hrs = (t1 - t0).total_seconds() / 3600
        ax.set_title(f'Deployment {dep}   ({hrs:.1f} h)', loc='left',
                     fontsize=9.5, color=INK, pad=4)
        for i, (k, _, col, _) in enumerate(GRIDS):
            r = met[k][(met[k].deploy == dep) & (met[k].drifter_id == did)]
            if not len(r):
                continue
            ax.text(0.985, 0.03 + 0.075 * (len(GRIDS) - 1 - i),
                    f'{r.iloc[0]["LW_skill"]:.3f}', transform=ax.transAxes,
                    fontsize=8, color=col, ha='right', va='bottom',
                    fontweight='bold')

        ax.set_xticks([]); ax.set_yticks([])
        ax.set_facecolor(SURFACE)
        for s_ in ax.spines.values():
            s_.set_color(GRID)

    h = [Line2D([], [], color=INK, lw=2.4, label='Observed')]
    h += [Line2D([], [], color=c, lw=lw, label=f'Regrid {lab}')
          for _, lab, c, lw in GRIDS]
    h += [Line2D([], [], ls='none', marker='o', mfc='white', mec=INK, mew=1.8,
                 ms=7, label='Release'),
          Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white',
                 mew=1.2, ms=6.5, label='End of scored window')]
    fig.legend(handles=h, loc='lower center', ncol=6, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.012))
    fig.subplots_adjust(left=0.012, right=0.988, top=0.965, bottom=0.055,
                        wspace=0.06, hspace=0.16)
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_tracks_gridres.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'wrote {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
