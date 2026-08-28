"""Trajectories under the two parameterisations that actually deliver a canopy.

Baptist 154 is left out on purpose. Its canopy momentum sink is computed and
never read by this build, so it models the meadow smoother than bare sand and
scores below the uniform control in all four cells; its tracks are in
plot_drifter_tracks_153_vs_154.py and the story there is told. What is worth
looking at is where the two WORKING routes agree and where they part.

They agree more than the skill numbers suggest. Against the uniform control the
contrast is +0.16 to +0.21 for 153 and +0.19 to +0.26 for [veg], and paired
against each other the difference is +0.032, -0.020, +0.066 and +0.006 across
the four cells -- small next to the effect both measure. The claim the figure
supports is convergence, not a winner.

Rows are the factorial's four cells, columns are deployments, and the extent of
a column is shared across its rows so the rows can be read against one another.
One drifter per column, the median-skill drifter of that deployment under the
full member, the manuscript's choice.

Deployments 1 and 3 hold every zero-skill case the 154 arm produced, so those
columns are where the treatments separate most; 2 and 10 are typical. That is
an unbalanced sample of the ensemble by design, and the skill figure carries
the balanced version.

    python scripts/plot_drifter_tracks_153_vs_veg.py
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
LAND, LAND_EDGE = '#efece6', '#c9c7c1'
C153, CVEG = '#4a3aa7', '#0f9bd0'

# cell, 153 tag, [veg] tag, 153 is the uncorrected original
ROWS = [('No waves, fixed bed', 'v04AE_nowaves_vr_arlfix', 'v04AE_veg_hv040', False),
        ('Waves, fixed bed', 'v04AE_nodm_vr_arlfix', 'v04AE_veg_waves', False),
        ('No waves, mobile bed', 'v04AE_nowaves_vrdm_arlfix', 'v04AE_veg_nowaves_dm', False),
        ('Waves, mobile bed', 'v04AE_vr', 'v04AE_veg_waves_dm', True)]
DEPLOYS = [1, 2, 3, 10]
PAD_FRAC = 0.16


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    rows = []
    for lab, t153, tveg, partial in ROWS:
        f = [PROC / f'drifter_sim_{t}.csv' for t in (t153, tveg)]
        if not all(x.exists() for x in f):
            print(f'skip {lab}: falta {[x.name for x in f if not x.exists()]}')
            continue
        rows.append(dict(
            lab=lab, partial=partial,
            s153=pd.read_csv(f[0], parse_dates=['time']),
            sveg=pd.read_csv(f[1], parse_dates=['time']),
            m153=pd.read_csv(PROC / f'drifter_metrics_{t153}.csv'),
            mveg=pd.read_csv(PROC / f'drifter_metrics_{tveg}.csv')))

    ref = pd.read_csv(PROC / 'drifter_metrics_v04AE_vr.csv')
    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)

    cols = {}
    for dep in DEPLOYS:
        did = pick_drifter(ref, dep)
        o = obs[(obs.deploy == dep) & (obs.source == did)].sort_values('time')
        t0, t1 = o.time.min(), o.time.max()
        xs, ys = [o.lon.values], [o.lat.values]
        for r in rows:
            for k in ('s153', 'sveg'):
                s = r[k]
                s = s[(s.deploy == dep) & (s.drifter_id == did) &
                      (s.time >= t0) & (s.time <= t1)]
                if len(s) > 1:
                    xs.append(s.lon.values)
                    ys.append(s.lat.values)
        lo, la = np.concatenate(xs), np.concatenate(ys)
        cx, cy = (lo.min() + lo.max()) / 2, (la.min() + la.max()) / 2
        asp = 1.0 / np.cos(np.radians(cy))
        half = max((lo.max() - lo.min()) / 2,
                   (la.max() - la.min()) * asp / 2) * (1 + PAD_FRAC)
        cols[dep] = dict(did=did, o=o, t0=t0, t1=t1, cx=cx, cy=cy, asp=asp,
                         half=half, h=(t1 - t0).total_seconds() / 3600)

    nr, nc = len(rows), len(DEPLOYS)
    fig, axes = plt.subplots(nr, nc, figsize=(2.55 * nc, 2.7 * nr), dpi=300,
                             squeeze=False)
    fig.patch.set_facecolor(SURFACE)

    for i, r in enumerate(rows):
        for j, dep in enumerate(DEPLOYS):
            ax, c = axes[i][j], cols[dep]
            ax.set_xlim(c['cx'] - c['half'], c['cx'] + c['half'])
            ax.set_ylim(c['cy'] - c['half'] / c['asp'],
                        c['cy'] + c['half'] / c['asp'])
            for p in land:
                ax.fill(p[:, 0], p[:, 1], color=LAND, ec='none', zorder=1)
            for p in coast:
                ax.plot(p[:, 0], p[:, 1], '-', color=LAND_EDGE, lw=0.5, zorder=2)

            o = c['o']
            ax.plot(o.lon, o.lat, '-', color=INK, lw=2.6, zorder=6,
                    solid_capstyle='round')
            ax.plot(o.lon.iloc[0], o.lat.iloc[0], 'o', ms=7, mfc='white',
                    mec=INK, mew=1.8, zorder=9)
            ax.plot(o.lon.iloc[-1], o.lat.iloc[-1], 's', ms=7, mfc=INK,
                    mec='white', mew=1.3, zorder=9)

            txt = []
            for key, mk, col in (('s153', 'm153', C153), ('sveg', 'mveg', CVEG)):
                s = r[key]
                s = s[(s.deploy == dep) & (s.drifter_id == c['did']) &
                      (s.time >= c['t0']) & (s.time <= c['t1'])].sort_values('time')
                if len(s) < 2:
                    txt.append(' -- ')
                    continue
                ax.plot(s.lon, s.lat, '-', color=col, lw=1.9, zorder=5,
                        alpha=0.95, solid_capstyle='round')
                ax.plot(s.lon.iloc[-1], s.lat.iloc[-1], 's', ms=6.5, mfc=col,
                        mec='white', mew=1.3, zorder=8)
                q = r[mk][(r[mk].deploy == dep) & (r[mk].drifter_id == c['did'])]
                txt.append(f'{q.LW_skill.iloc[0]:.2f}' if len(q) else ' -- ')

            ax.text(0.035, 0.055, 'LW', transform=ax.transAxes, fontsize=7,
                    color=MUTED, ha='left', va='bottom')
            for k, (val, col) in enumerate(zip(txt, (C153, CVEG))):
                ax.plot(0.135 + 0.20 * k, 0.083, 's', ms=4.5, color=col,
                        transform=ax.transAxes, clip_on=False, zorder=10)
                ax.text(0.175 + 0.20 * k, 0.055, val, transform=ax.transAxes,
                        fontsize=7.5, color=INK, ha='left', va='bottom')

            if i == 0:
                span = hav(c['cx'] - c['half'], c['cy'],
                           c['cx'] + c['half'], c['cy'])
                fr = 500.0 / span
                x0 = c['cx'] - c['half'] * 0.90
                y0 = c['cy'] + c['half'] / c['asp'] * 0.86
                ax.plot([x0, x0 + fr * 2 * c['half']], [y0, y0], '-', color=INK,
                        lw=2.0, zorder=9, solid_capstyle='butt')
                ax.text(x0 + fr * c['half'], y0, '500 m', fontsize=7, color=INK,
                        ha='center', va='bottom', zorder=9)
                ax.set_title(f"Deployment {dep}   ({c['h']:.1f} h)", loc='left',
                             fontsize=9.5, color=INK, pad=5)
            if j == 0:
                ax.set_ylabel(r['lab'].replace(', ', ',\n') +
                              (' †' if r['partial'] else ''),
                              fontsize=9.5, color=INK, labelpad=8)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_facecolor(SURFACE)
            for s_ in ax.spines.values():
                s_.set_color(GRID)

    h = [Line2D([], [], color=INK, lw=2.6, label='Observed'),
         Line2D([], [], color=C153, lw=1.9, label='Baptist 153, meadow applied'),
         Line2D([], [], color=CVEG, lw=1.9, label='[veg] module, literature only'),
         Line2D([], [], ls='none', marker='o', mfc='white', mec=INK, mew=1.8,
                ms=7, label='Release'),
         Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white', mew=1.3,
                ms=7, label='End of scored window')]
    fig.legend(handles=h, loc='lower left', ncol=5, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.045, 0.026))
    if any(r['partial'] for r in rows):
        fig.text(0.045, 0.004,
                 '†  this row\'s 153 is the ORIGINAL member (.arl reaching 5.5% '
                 'of the meadow): 153 with the meadow applied aborts in this '
                 'configuration.', fontsize=7.5, color=MUTED, ha='left')
    fig.suptitle('Two routes to a canopy, and how far apart they actually are',
                 fontsize=12, color=INK, x=0.008, ha='left', y=0.995)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.925, bottom=0.085,
                        wspace=0.06, hspace=0.10)
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_tracks_153_vs_veg.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'wrote {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
