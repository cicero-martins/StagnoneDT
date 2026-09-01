"""Figure: observed against simulated drifter trajectories, all twelve deployments.

The earlier version drew four deployments and three members, chosen to stage an
argument about bed mobility fixing distance and roughness fixing direction. That
argument no longer holds, and selecting four panels out of twelve invited the
reader to wonder about the eight that were left out. Every deployment is here.

Two configurations are drawn. They differ only in the canopy, W-M against WVM,
so the difference between the two coloured tracks in each panel is the canopy
and nothing else.

One drifter per panel, the median-skill drifter of that deployment under the
full configuration, so the panel is representative rather than selected.

Each track is clipped to the interval its drifter was in the water. OpenDrift
advects to the end of the forcing, so an unclipped simulated track runs on for
hours after the observed one stops. The clip keeps the bracketing sample at or
before the release: model output is on a ten-minute grid, and a drifter released
at 07:16 has its first in-window sample at 07:24, which drew the simulated line
starting ten minutes downstream of the release circle and looked like a seeding
error rather than a sampling one.

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

# The canopy treatment carries the colour, as everywhere else in the manuscript.
MEMBERS = [('v04AE', 'Bare (W-M)', '#eb6834'),
           ('v04AE_veg_waves_dm', 'Canopy (WVM)', '#4a3aa7')]
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


def hav(lo1, la1, lo2, la2):
    R = 6371000.0
    p1, p2 = np.radians(la1), np.radians(la2)
    dp, dl = np.radians(la2 - la1), np.radians(lo2 - lo1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


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


def pick_drifter(met, dep):
    """The median-skill drifter of a deployment, under the full member."""
    s = met[met['deploy'] == dep].sort_values('LW_skill')
    return s.iloc[len(s) // 2]['drifter_id']


def clip_track(sim, dep, did, t0, t1):
    """The simulated track over the observed window, starting at the release.

    Filtering on time >= t0 alone drops the sample that brackets the release
    when the drifter entered the water between two output steps, so the line
    would start one ten-minute step downstream of the release marker.
    """
    s = sim[(sim.deploy == dep) & (sim.drifter_id == did)].sort_values('time')
    s = s[s.time <= t1]
    before = s[s.time <= t0]
    start = before.time.max() if len(before) else s.time.min()
    return s[s.time >= start]


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    sims = {k: pd.read_csv(PROC / f'drifter_sim_{k}.csv', parse_dates=['time'])
            for k, _, _ in MEMBERS}
    full = pd.read_csv(PROC / f'drifter_metrics_{MEMBERS[-1][0]}.csv')
    deploys = sorted(full.deploy.unique())

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)

    fig, axes = plt.subplots(3, 4, figsize=(11.6, 8.8), dpi=300)
    fig.patch.set_facecolor(SURFACE)

    for ax, dep in zip(axes.ravel(), deploys):
        did = pick_drifter(full, dep)
        o = obs[(obs.deploy == dep) & (obs.source == did)].sort_values('time')
        t0, t1 = o.time.min(), o.time.max()
        tracks = {k: clip_track(sims[k], dep, did, t0, t1)
                  for k, _, _ in MEMBERS}

        xs = [o.lon.values] + [g.lon.values for g in tracks.values() if len(g) > 1]
        ys = [o.lat.values] + [g.lat.values for g in tracks.values() if len(g) > 1]
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
        for (k, _, col), z in zip(MEMBERS, (4, 5)):
            g = tracks[k]
            if len(g) < 2:
                continue
            ax.plot(g.lon, g.lat, '-', color=col, lw=2.0, zorder=z, alpha=0.95,
                    solid_capstyle='round')
            ax.plot(g.lon.iloc[-1], g.lat.iloc[-1], 's', ms=6, mfc=col,
                    mec='white', mew=1.2, zorder=z + 3)
        ax.plot(o.lon.iloc[0], o.lat.iloc[0], 'o', ms=7, mfc='white', mec=INK,
                mew=1.8, zorder=9)
        ax.plot(o.lon.iloc[-1], o.lat.iloc[-1], 's', ms=6.5, mfc=INK,
                mec='white', mew=1.2, zorder=9)

        # panel extents differ by an order of magnitude across deployments,
        # 0.4 h against 7.2 h, so a fixed bar runs off the short ones
        span = hav(cx - half, cy, cx + half, cy)
        bar = max([b for b in (50, 100, 200, 500, 1000) if b <= 0.40 * span],
                  default=50)
        fr = bar / span
        x0, y0 = cx - half * 0.90, cy + half / asp * 0.87
        ax.plot([x0, x0 + fr * 2 * half], [y0, y0], '-', color=INK, lw=1.8,
                zorder=9, solid_capstyle='butt')
        ax.text(x0 + fr * half, y0, f'{bar} m', fontsize=7, color=INK,
                ha='center', va='bottom', zorder=9)
        hrs = (t1 - t0).total_seconds() / 3600
        ax.set_title(f'Deployment {dep}   ({hrs:.1f} h)', loc='left',
                     fontsize=9.5, color=INK, pad=4)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_facecolor(SURFACE)
        for s_ in ax.spines.values():
            s_.set_color(GRID)

    h = [Line2D([], [], color=INK, lw=2.6, label='Observed')]
    h += [Line2D([], [], color=c, lw=2.0, label=l) for _, l, c in MEMBERS]
    h += [Line2D([], [], ls='none', marker='o', mfc='white', mec=INK, mew=1.8,
                 ms=7, label='Release'),
          Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white', mew=1.2,
                 ms=6.5, label='End of scored window')]
    fig.legend(handles=h, loc='lower center', ncol=5, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.012))
    fig.subplots_adjust(left=0.012, right=0.988, top=0.965, bottom=0.05,
                        wspace=0.06, hspace=0.16)
    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_trajectories.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'wrote {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
