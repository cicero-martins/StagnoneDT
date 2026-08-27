"""Trajectories under the two Baptist formulations, side by side.

The paired statistics say the two formulations disagree in sign about what
distributed roughness does to Lagrangian skill: on 153 with the meadow actually
applied the roughness contrast is +0.16 to +0.21, on 154 it is -0.06 to -0.02.
The summary numbers do not say what the tracks are doing differently. This does.

What to look for. Mean path ratio, simulated over observed, is 0.91 on 153 and
0.71 on 154, against 0.78 for uniform roughness. So the expectation is that the
purple track reaches roughly as far as the black one and the orange track falls
short of both. Heading is the second axis, and it is not summarised by either
number.

Rows are members, columns are deployments, and the extent of a column is shared
across its rows so the rows can be read against one another without rescaling.
One drifter per column, the median-skill drifter of that deployment under the
full member, the same choice the manuscript figure makes.

The four deployments are the manuscript's, and they are not a fair sample of
this particular comparison. Taken over all twelve, that median rule reproduces
the ensemble mean almost exactly (0.479 against 0.474, 0.418 against 0.412,
0.596 against 0.608). Taken over these four it does not, because deployments 1
and 3 hold every one of the eleven zero-skill cases and nothing else holds any.
Two of the four track columns therefore show a failure that occurs in 5 of 35
drifters. The last column carries the whole distribution for that reason: the
tracks show what the failure looks like, the strip shows how often it happens.

Two labels that are not interchangeable, and the figure marks the difference:

  '153, meadow applied' is the _arlfix re-run, the .arl written to 9 decimals.
  '153, meadow at 5.5%' is the member as it stands in the manuscript, where the
  6-decimal .arl missed FM's 1 cm matching tolerance on 94% of the links.

The waves + mobile-bed member has only the second, because on 153 with the
corrected meadow it aborts. Its comparison is therefore against a different
control than the other rows, and the row label says so.

Every track is clipped to the interval its drifter was in the water. OpenDrift
advects to the end of the forcing, which for these deployments is 12 to 41 h
against 0.5 to 7.2 h observed, so an unclipped track invents a runaway that is
part of no scored comparison.

Output: figures/drifter_tracks_153_vs_154.{png,pdf}
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
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
LAND = '#efece6'
LAND_EDGE = '#c9c7c1'

# Two of the manuscript trio, re-validated as a pair: worst adjacent CVD dE
# 29.5 (protan), normal-vision 37.6, both clear of the 3:1 contrast floor.
C153, C154 = '#4a3aa7', '#eb6834'

# row label, 153-variant tag, 154 tag, 153 caveat
ROWS = [
    ('No waves, fixed bed',   'v04AE_nowaves_vr_arlfix',   'v04AE_nowaves_vr_154',   'applied'),
    ('Waves, fixed bed',      'v04AE_nodm_vr_arlfix',      'v04AE_nodm_vr_154shore', 'applied'),
    ('No waves, mobile bed',  'v04AE_nowaves_vrdm_arlfix', 'v04AE_nowaves_vrdm_154', 'applied'),
    ('Waves, mobile bed',     'v04AE_vr',                  'v04AE_vr_154',           'partial'),
]
# The one member whose 154 run carries the Marettimo rocky-shore treatment.
SHORE_TAG = 'v04AE_nodm_vr_154shore'
DEPLOYS = [1, 2, 3, 10]
PAD_FRAC = 0.16


def track(sim, dep, did, t0, t1):
    s = sim[(sim['deploy'] == dep) & (sim['drifter_id'] == did) &
            (sim['time'] >= t0) & (sim['time'] <= t1)]
    return s.sort_values('time')


def skill(met, dep, did):
    r = met[(met['deploy'] == dep) & (met['drifter_id'] == did)]
    return float(r['LW_skill'].iloc[0]) if len(r) else np.nan


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])

    rows, missing = [], []
    for label, t153, t154, kind in ROWS:
        f153, f154 = PROC / f'drifter_sim_{t153}.csv', PROC / f'drifter_sim_{t154}.csv'
        if not (f153.exists() and f154.exists()):
            missing.append(label)
            continue
        rows.append(dict(
            label=label, kind=kind, tag154=t154,
            s153=pd.read_csv(f153, parse_dates=['time']),
            s154=pd.read_csv(f154, parse_dates=['time']),
            m153=pd.read_csv(PROC / f'drifter_metrics_{t153}.csv'),
            m154=pd.read_csv(PROC / f'drifter_metrics_{t154}.csv')))
    if missing:
        print('not drawn (no OpenDrift output yet): ' + ', '.join(missing))
    if not rows:
        print('nothing to draw')
        return

    ref = pd.read_csv(PROC / 'drifter_metrics_v04AE_vr.csv')
    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)

    # One drifter per column, and one extent per column: the rows are only
    # comparable to each other if the panel does not rescale under them.
    cols = {}
    for dep in DEPLOYS:
        did = pick_drifter(ref, dep)
        o = obs[(obs['deploy'] == dep) &
                (obs['source'] == did)].sort_values('time')
        t0, t1 = o['time'].min(), o['time'].max()
        xs, ys = [o['lon'].values], [o['lat'].values]
        for r in rows:
            for k in ('s153', 's154'):
                s = track(r[k], dep, did, t0, t1)
                if len(s) > 1:
                    xs.append(s['lon'].values)
                    ys.append(s['lat'].values)
        lo, la = np.concatenate(xs), np.concatenate(ys)
        cx, cy = (lo.min() + lo.max()) / 2, (la.min() + la.max()) / 2
        aspect = 1.0 / np.cos(np.radians(cy))
        half = max((lo.max() - lo.min()) / 2,
                   (la.max() - la.min()) * aspect / 2) * (1 + PAD_FRAC)
        cols[dep] = dict(did=did, o=o, t0=t0, t1=t1, cx=cx, cy=cy,
                         aspect=aspect, half=half,
                         hours=(t1 - t0).total_seconds() / 3600)

    nr, nc = len(rows), len(DEPLOYS)
    # A narrow spacer column keeps the strip's axis label off the last map
    # panel; a uniform wspace would have to open every gap to fix one.
    fig = plt.figure(figsize=(2.55 * nc + 3.4, 2.75 * nr), dpi=300)
    gs = fig.add_gridspec(nr, nc + 2, width_ratios=[1] * nc + [0.16, 1.30],
                          wspace=0.10, hspace=0.14)
    axes = [[fig.add_subplot(gs[i, j]) for j in range(nc)] for i in range(nr)]
    strips = [fig.add_subplot(gs[i, nc + 1]) for i in range(nr)]
    fig.patch.set_facecolor(SURFACE)

    for i, r in enumerate(rows):
        for j, dep in enumerate(DEPLOYS):
            ax, c = axes[i][j], cols[dep]
            ax.set_xlim(c['cx'] - c['half'], c['cx'] + c['half'])
            ax.set_ylim(c['cy'] - c['half'] / c['aspect'],
                        c['cy'] + c['half'] / c['aspect'])

            # fill() closes the path, so an open coastline polyline would draw
            # a straight edge across the panel: fill without an edge, stroke
            # the open path separately.
            for p in land:
                ax.fill(p[:, 0], p[:, 1], color=LAND, ec='none', zorder=1)
            for p in coast:
                ax.plot(p[:, 0], p[:, 1], '-', color=LAND_EDGE, lw=0.5, zorder=2)

            o = c['o']
            ax.plot(o['lon'], o['lat'], '-', color=INK, lw=2.6, zorder=6,
                    solid_capstyle='round')
            ax.plot(o['lon'].iloc[0], o['lat'].iloc[0], 'o', ms=7, mfc='white',
                    mec=INK, mew=1.8, zorder=9)
            ax.plot(o['lon'].iloc[-1], o['lat'].iloc[-1], 's', ms=7, mfc=INK,
                    mec='white', mew=1.3, zorder=9)

            txt = []
            for key, mkey, col in (('s153', 'm153', C153),
                                   ('s154', 'm154', C154)):
                s = track(r[key], dep, c['did'], c['t0'], c['t1'])
                if len(s) < 2:
                    txt.append('  --  ')
                    continue
                ax.plot(s['lon'], s['lat'], '-', color=col, lw=1.9, zorder=5,
                        alpha=0.95, solid_capstyle='round')
                ax.plot(s['lon'].iloc[-1], s['lat'].iloc[-1], 's', ms=6.5,
                        mfc=col, mec='white', mew=1.3, zorder=8)
                txt.append(f'{skill(r[mkey], dep, c["did"]):.2f}')

            # Values wear text ink; the colored square beside each carries the
            # identity, so the number is never color-alone.
            ax.text(0.035, 0.055, 'LW', transform=ax.transAxes, fontsize=7,
                    color=MUTED, ha='left', va='bottom')
            for k, (v, col) in enumerate(zip(txt, (C153, C154))):
                ax.plot(0.135 + 0.20 * k, 0.083, 's', ms=4.5, color=col,
                        transform=ax.transAxes, clip_on=False, zorder=10)
                ax.text(0.175 + 0.20 * k, 0.055, v, transform=ax.transAxes,
                        fontsize=7.5, color=INK, ha='left', va='bottom')

            if i == 0:
                span_m = hav(c['cx'] - c['half'], c['cy'],
                             c['cx'] + c['half'], c['cy'])
                frac = 500.0 / span_m
                x0 = c['cx'] - c['half'] * 0.90
                y0 = c['cy'] + c['half'] / c['aspect'] * 0.86
                ax.plot([x0, x0 + frac * 2 * c['half']], [y0, y0], '-',
                        color=INK, lw=2.0, zorder=9, solid_capstyle='butt')
                ax.text(x0 + frac * c['half'], y0, '500 m', fontsize=7,
                        color=INK, ha='center', va='bottom', zorder=9)
                ax.set_title(f"Deployment {dep}   ({c['hours']:.1f} h)",
                             loc='left', fontsize=9.5, color=INK, pad=5)
            if j == 0:
                mark = ''
                if r['kind'] == 'partial':
                    mark = ' †'
                if r['tag154'] == SHORE_TAG:
                    mark += ' ‡'
                ax.set_ylabel(r['label'].replace(', ', ',\n') + mark,
                              fontsize=9.5, color=INK, labelpad=8)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_facecolor(SURFACE)
            for sp in ax.spines.values():
                sp.set_color(GRID)

        # The distribution the four track panels were drawn from. Every drifter,
        # every deployment, paired: a grey segment joins the same drifter under
        # the two formulations, so a downward segment is a drifter the 154 run
        # scores worse.
        ax = strips[i]
        alldeps = sorted(r['m154']['deploy'].unique())
        for d in DEPLOYS:
            ax.axvspan(d - 0.42, d + 0.42, color='#f4f2ee', zorder=0)
        j153 = r['m153'].merge(r['m154'], on=['deploy', 'drifter_id'],
                               suffixes=('_a', '_b'))
        for _, row in j153.iterrows():
            ax.plot([row.deploy - 0.13, row.deploy + 0.13],
                    [row.LW_skill_a, row.LW_skill_b], '-', color=GRID, lw=0.9,
                    zorder=2)
        ax.plot(j153.deploy - 0.13, j153.LW_skill_a, 'o', ms=4.2, mfc=C153,
                mec='white', mew=0.7, ls='none', zorder=4)
        ax.plot(j153.deploy + 0.13, j153.LW_skill_b, 'o', ms=4.2, mfc=C154,
                mec='white', mew=0.7, ls='none', zorder=4)
        for v, col in ((j153.LW_skill_a.mean(), C153),
                       (j153.LW_skill_b.mean(), C154)):
            ax.axhline(v, color=col, lw=1.1, ls=(0, (4, 3)), alpha=0.85,
                       zorder=3)
            ax.text(12.75, v, f'{v:.2f}', fontsize=7.5, color=col, va='center',
                    ha='left')
        ax.set_xlim(0.4, 12.6)
        ax.set_ylim(-0.06, 1.02)
        ax.set_xticks(alldeps)
        ax.set_xticklabels([str(d) for d in alldeps], fontsize=7, color=MUTED)
        ax.tick_params(axis='y', labelsize=7, colors=MUTED)
        ax.grid(True, axis='y', color=GRID, lw=0.5, alpha=0.7)
        ax.set_axisbelow(True)
        ax.set_ylabel('Liu-Weisberg skill', fontsize=8, color=MUTED)
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
        for sp in ('left', 'bottom'):
            ax.spines[sp].set_color(GRID)
        if i == 0:
            ax.set_title('All 35 drifters, paired\n(shaded = the four drawn '
                         'at left)', loc='left', fontsize=9.5, color=INK, pad=5)
        if i == len(rows) - 1:
            ax.set_xlabel('deployment', fontsize=8, color=MUTED)

    handles = [
        Line2D([], [], color=INK, lw=2.6, label='Observed'),
        Line2D([], [], color=C153, lw=1.9, label='Baptist 153, meadow applied'),
        Line2D([], [], color=C154, lw=1.9, label='Baptist 154, meadow applied'),
        Line2D([], [], ls='none', marker='o', mfc='white', mec=INK, mew=1.8,
               ms=7, label='Release'),
        Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white', mew=1.3,
               ms=7, label='End of scored window')]
    fig.legend(handles=handles, loc='lower left', ncol=5, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.055, 0.028))
    notes = []
    if any(r['kind'] == 'partial' for r in rows):
        notes.append('†  this member has no 153 run with the meadow applied '
                     '— that configuration aborts, so its 153 line is the '
                     'manuscript member, meadow at 5.5%')
    if any(r['tag154'] == SHORE_TAG for r in rows):
        notes.append('‡  its 154 run carries a rocky-shore Manning of 0.05 at '
                     'Marettimo, 45 km away, without which it does not '
                     'integrate; the other members do not')
    if notes:
        fig.text(0.055, 0.004, '\n'.join(notes), fontsize=7.5, color=MUTED,
                 ha='left', va='bottom')
    fig.suptitle('Distributed roughness under the two Baptist formulations: '
                 'the same meadow, applied two ways',
                 fontsize=12, color=INK, x=0.008, ha='left', y=0.995)

    # gridspec already sets the spacing; tight_layout would fight it and warns.
    fig.subplots_adjust(left=0.055, right=0.965, top=0.905,
                        bottom=0.125 if notes else 0.09)
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_tracks_153_vs_154.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)

    print(f"\n{'row':22s} {'deploy':>7s} {'LW 153':>7s} {'LW 154':>7s} "
          f"{'path 153':>9s} {'path 154':>9s}")
    for r in rows:
        for dep in DEPLOYS:
            did = cols[dep]['did']
            a = r['m153'][(r['m153'].deploy == dep) & (r['m153'].drifter_id == did)]
            b = r['m154'][(r['m154'].deploy == dep) & (r['m154'].drifter_id == did)]
            if not len(a) or not len(b):
                continue
            print(f"{r['label']:22s} {dep:7d} {a.LW_skill.iloc[0]:7.3f} "
                  f"{b.LW_skill.iloc[0]:7.3f} {a.path_ratio.iloc[0]:9.2f} "
                  f"{b.path_ratio.iloc[0]:9.2f}")


if __name__ == '__main__':
    main()
