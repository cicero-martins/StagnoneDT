"""Figure: observed against simulated drifter trajectories, four deployments.

Section 5 argues that bed mobility corrects how far the particles travel and
distributed roughness corrects which way they go. That argument is currently
carried by three summary numbers per member. This figure shows the tracks the
numbers came from, so a reader can see the two failure modes rather than infer
them.

Three members are drawn, chosen to isolate the two steps of the argument:

  waves          fixed bed, uniform roughness  -- travels too short a distance
  waves + morph. mobile bed, uniform roughness -- right distance, wrong heading
  full           mobile bed, distributed rough -- right distance, right heading

The four fixed-bed members are indistinguishable from one another (path ratio
0.77 to 0.80, heading error 15.8 to 16.2 deg), so drawing one of them stands in
for all four and keeps four lines per panel instead of seven.

Deployments 1, 2, 3 and 10 are shown. They span the duration range (2.4 to
7.2 h) and include the case that makes the direction argument visible: in
deployment 10 the mobile-bed uniform member ends FARTHER from the observed
endpoint than the fixed-bed member (1808 m against 1218 m) despite recovering
the path length, which is the signature of a magnitude fix without a direction
fix.

One drifter per panel, the median-skill drifter of that deployment under the
full member, so the panel is representative rather than selected.

Every track is clipped to the interval its drifter was actually in the water.
OpenDrift advects to the end of the forcing, so an unclipped simulated track
runs 12 to 41 h against 0.5 to 7.2 h of observation and invents a runaway that
is not part of any scored comparison.

Output: figures/drifter_trajectories.{png,pdf}
"""
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

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
LAND = '#efece6'
LAND_EDGE = '#c9c7c1'

# Same categorical trio as Figure 1, already validated all-pairs for CVD
# separation. Assigned in fixed order, never cycled.
MEMBERS = [('v04AE_nodm', 'Waves (fixed bed)', '#eb6834'),
           ('v04AE', 'Waves + morph.', '#1baf7a'),
           ('v04AE_vr', 'Full', '#4a3aa7')]

DEPLOYS = [1, 2, 3, 10]
PAD_FRAC = 0.16


def parse_ldb(path):
    """Delft3D land-boundary file to a list of (N, 2) arrays."""
    polys, cur = [], []
    for ln in Path(path).read_text().splitlines():
        s = ln.strip()
        if not s or s.startswith('*'):
            continue
        parts = s.split()
        try:
            x, y = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            if len(cur) > 1:
                polys.append(np.array(cur))
            cur = []
            continue
        if not np.isfinite(x) or not np.isfinite(y) or abs(x) > 1e10:
            if len(cur) > 1:
                polys.append(np.array(cur))
            cur = []
            continue
        cur.append((x, y))
    if len(cur) > 1:
        polys.append(np.array(cur))
    return polys


def split_long_segments(polys, max_m=1500.0):
    """Break land boundaries at implausibly long straight jumps.

    sicily2.ldb carries a few segments that run for kilometres in a straight
    line, which are domain-edge closures rather than coastline. At the zoom
    these panels use they draw as grey diagonals across open water.
    """
    out = []
    for p in polys:
        d = hav(p[:-1, 0], p[:-1, 1], p[1:, 0], p[1:, 1])
        cut = np.flatnonzero(d > max_m) + 1
        for seg in np.split(p, cut):
            if len(seg) > 1:
                out.append(seg)
    return out


def hav(lo1, la1, lo2, la2):
    R = 6371000.0
    p1, p2 = np.radians(la1), np.radians(la2)
    dp, dl = np.radians(la2 - la1), np.radians(lo2 - lo1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def pick_drifter(met, dep):
    """The median-skill drifter of a deployment, under the full member."""
    s = met[met['deploy'] == dep].sort_values('LW_skill')
    return s.iloc[len(s) // 2]['drifter_id']


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    sims = {k: pd.read_csv(PROC / f'drifter_sim_{k}.csv', parse_dates=['time'])
            for k, _, _ in MEMBERS}
    mets = {k: pd.read_csv(PROC / f'drifter_metrics_{k}.csv')
            for k, _, _ in MEMBERS}

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)

    fig, axes = plt.subplots(2, 2, figsize=(9.4, 9.0), dpi=300)
    fig.patch.set_facecolor(SURFACE)

    for ax, dep in zip(axes.ravel(), DEPLOYS):
        did = pick_drifter(mets['v04AE_vr'], dep)
        o = obs[(obs['deploy'] == dep) & (obs['source'] == did)].sort_values('time')
        t0, t1 = o['time'].min(), o['time'].max()
        hours = (t1 - t0).total_seconds() / 3600

        xs, ys = [o['lon'].values], [o['lat'].values]
        drawn = []
        for key, lab, col in MEMBERS:
            s = sims[key]
            s = s[(s['deploy'] == dep) & (s['drifter_id'] == did) &
                  (s['time'] >= t0) & (s['time'] <= t1)].sort_values('time')
            if len(s) < 2:
                continue
            drawn.append((key, lab, col, s))
            xs.append(s['lon'].values)
            ys.append(s['lat'].values)

        lo = np.concatenate(xs)
        la = np.concatenate(ys)
        cx, cy = (lo.min() + lo.max()) / 2, (la.min() + la.max()) / 2
        aspect = 1.0 / np.cos(np.radians(cy))
        half = max((lo.max() - lo.min()) / 2, (la.max() - la.min()) * aspect / 2)
        half *= 1 + PAD_FRAC
        ax.set_xlim(cx - half, cx + half)
        ax.set_ylim(cy - half / aspect, cy + half / aspect)

        # fill() closes the path, which draws a straight edge across the panel
        # for any land boundary that is an open polyline rather than a loop.
        # Fill without an edge, then stroke the open path separately.
        for p in land:
            ax.fill(p[:, 0], p[:, 1], color=LAND, ec='none', zorder=1)
        for p in coast:
            ax.plot(p[:, 0], p[:, 1], '-', color=LAND_EDGE, lw=0.5, zorder=2)

        # observed last-but-one in z so the simulated ends stay readable on top
        ax.plot(o['lon'], o['lat'], '-', color=INK, lw=2.6, zorder=6,
                solid_capstyle='round')
        ax.plot(o['lon'].iloc[0], o['lat'].iloc[0], 'o', ms=8, mfc='white',
                mec=INK, mew=2.0, zorder=8)
        ax.plot(o['lon'].iloc[-1], o['lat'].iloc[-1], 's', ms=8, mfc=INK,
                mec='white', mew=1.4, zorder=8)

        for key, lab, col, s in drawn:
            ax.plot(s['lon'], s['lat'], '-', color=col, lw=2.0, zorder=5,
                    alpha=0.95, solid_capstyle='round')
            ax.plot(s['lon'].iloc[-1], s['lat'].iloc[-1], 's', ms=7, mfc=col,
                    mec='white', mew=1.4, zorder=7)

        # scale bar, 500 m
        span_m = hav(cx - half, cy, cx + half, cy)
        frac = 500.0 / span_m
        x0 = cx - half * 0.88
        y0 = cy - half / aspect * 0.86
        ax.plot([x0, x0 + frac * 2 * half], [y0, y0], '-', color=INK, lw=2.2,
                zorder=9, solid_capstyle='butt')
        ax.text(x0 + frac * half, y0, '500 m', fontsize=7.5, color=INK,
                ha='center', va='bottom', zorder=9)

        ax.set_title(f'Deployment {dep}   ({hours:.1f} h)', loc='left',
                     fontsize=10, color=INK, pad=6)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_facecolor(SURFACE)
        for sp in ax.spines.values():
            sp.set_color(GRID)

    handles = [Line2D([], [], color=INK, lw=2.6, label='Observed')]
    handles += [Line2D([], [], color=c, lw=2.0, label=l) for _, l, c in MEMBERS]
    handles += [Line2D([], [], ls='none', marker='o', mfc='white', mec=INK,
                       mew=2.0, ms=8, label='Release'),
                Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white',
                       mew=1.4, ms=8, label='End of scored window')]
    fig.legend(handles=handles, loc='lower center', ncol=3, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.005))

    fig.tight_layout(rect=(0, 0.075, 1, 1))
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_trajectories.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
