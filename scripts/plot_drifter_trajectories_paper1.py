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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import TAG, SUFFIX, FIGSUB, CODE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model' / 'dflowfm_v04AE'
FIG = ROOT / 'figures' / FIGSUB
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
LAND = '#efece6'
LAND_EDGE = '#c9c7c1'

# The canopy treatment carries the colour, as everywhere else in the manuscript.
# From the stratified start the mobile bed enters only as a sensitivity test,
# so the pair shown is the wave-coupled fixed-bed one.
if SUFFIX:
    MEMBERS = [(TAG['nodm'], f"Bare ({CODE['nodm']})", '#eb6834'),
               (TAG['nodm_veg'], f"Canopy ({CODE['nodm_veg']})", '#4a3aa7')]
else:
    MEMBERS = [('v04AE', 'Bare (W-M)', '#eb6834'),
               ('v04AE_veg_waves_dm', 'Canopy (WVM)', '#4a3aa7')]
# The supplementary version draws every member of the fixed-bed design and the
# member with the canopy also in SWAN, as (tag, label, colour, line style).
# Colour carries the canopy and line style the wave treatment, as in Figure 4.
MEMBERS_ALL = [
    (TAG.get('nowaves'), 'REF', '#eb6834', (0, (3, 1.6))),
    (TAG.get('nodm'), 'WAV', '#eb6834', '-'),
    (TAG.get('nowaves_veg'), 'VEG', '#4a3aa7', (0, (3, 1.6))),
    (TAG.get('nodm_veg'), 'WAV+VEG', '#4a3aa7', '-'),
    ('arm_vwf_swan', 'WAV+VEG$^{\\mathrm{s}}$', '#9b8fd9', (0, (1, 1.2))),
]
# The deployments of the body figure. 1 and 2 show the bare member falling
# short of the observed path, 5 a case in which the bare member ends nearer the
# observed endpoint, and 9 and 11 the southward drift that both members follow.
SELECTED = [1, 2, 5, 9, 11]
# One colour per selected deployment, shared by its release in the locator
# panel and in its own panel. The hues avoid the orange and purple of the
# members and the black of the observed track.
DEP_COLOR = {1: '#2a9d8f', 2: '#3a86ff', 5: '#e0b100', 9: '#d6458f', 11: '#6b8e23'}
PAD_FRAC = 0.16
# Deployment 1 ends against the eastern shore, which the tight panel cut off.
PAD_EXTRA = {1: 0.55}
# The locator panel: the central lagoon, where every release lies.
LOCATOR = dict(lon=(12.428, 12.497), lat=(37.838, 37.912))
# Label offsets in points. Releases 1, 5 and 6 lie within 150 m of one another,
# as do 3 and 10, so the labels are placed by hand rather than by a rule.
LABEL_AT = {1: (4, -10), 2: (9, -3), 3: (9, -4), 4: (-9, 0), 5: (-9, -4),
            6: (-9, 4), 7: (0, 9), 8: (-9, 0), 9: (-9, 0), 10: (-9, 5),
            11: (10, 5), 12: (0, 9)}


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


def locator(ax, obs, land, coast, deps=None):
    """Observed tracks in grey and releases numbered, for the deployments given."""
    if deps is not None:
        obs = obs[obs.deploy.isin(deps)]
    for p in land:
        ax.fill(p[:, 0], p[:, 1], color=LAND, ec='none', zorder=1)
    for p in coast:
        ax.plot(p[:, 0], p[:, 1], '-', color=LAND_EDGE, lw=0.6, zorder=2)
    for _, g in obs.groupby(['deploy', 'source']):
        g = g.sort_values('time')
        ax.plot(g.lon, g.lat, '-', color='#a9a6a0', lw=0.9, zorder=3)
    rel = obs.sort_values('time').groupby('deploy')[['lon', 'lat']].first()
    cy = rel.lat.mean()
    asp = 1.0 / np.cos(np.radians(cy))
    for dep, row in rel.iterrows():
        ax.plot(row.lon, row.lat, 'o', ms=7, mfc=DEP_COLOR.get(int(dep), 'white'),
                mec=INK, mew=1.2, zorder=6)
        ax.annotate(str(int(dep)), (row.lon, row.lat), xytext=LABEL_AT.get(int(dep), (9, 0)),
                    textcoords='offset points', fontsize=8.5, color=INK, ha='center',
                    va='center', zorder=7)
    ax.set_xlim(*LOCATOR['lon']); ax.set_ylim(*LOCATOR['lat'])
    ax.set_aspect(asp)
    # 1 km scale bar, bottom left
    km = 1000.0 / hav(12.45, cy, 12.46, cy) * 0.01
    x0, y0 = LOCATOR['lon'][0] + 0.004, LOCATOR['lat'][0] + 0.004
    ax.plot([x0, x0 + km], [y0, y0], '-', color=INK, lw=2.0, zorder=9, solid_capstyle='butt')
    ax.text(x0 + km / 2, y0 + 0.0008, '1 km', fontsize=8, ha='center', va='bottom', color=INK)
    ax.set_title('Releases', loc='left', fontsize=9.5, color=INK, pad=4)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor(SURFACE)
    ax.set_rasterization_zorder(3)
    for s_ in ax.spines.values():
        s_.set_color(GRID)


def draw_panel(ax, dep, did, obs, sims, members, land, coast, release='white'):
    """One deployment: the observed track of drifter did and the members given.

    members is a list of (tag, label, colour, line style).
    """
    o = obs[(obs.deploy == dep) & (obs.source == did)].sort_values('time')
    t0, t1 = o.time.min(), o.time.max()
    tracks = {m[0]: clip_track(sims[m[0]], dep, did, t0, t1) for m in members}

    xs = [o.lon.values] + [g.lon.values for g in tracks.values() if len(g) > 1]
    ys = [o.lat.values] + [g.lat.values for g in tracks.values() if len(g) > 1]
    lo, la = np.concatenate(xs), np.concatenate(ys)
    cx, cy = (lo.min() + lo.max()) / 2, (la.min() + la.max()) / 2
    asp = 1.0 / np.cos(np.radians(cy))
    half = max((lo.max() - lo.min()) / 2,
               (la.max() - la.min()) * asp / 2) * (1 + PAD_FRAC + PAD_EXTRA.get(dep, 0.0))
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half / asp, cy + half / asp)

    for p in land:
        ax.fill(p[:, 0], p[:, 1], color=LAND, ec='none', zorder=1)
    for p in coast:
        ax.plot(p[:, 0], p[:, 1], '-', color=LAND_EDGE, lw=0.5, zorder=2)

    ax.plot(o.lon, o.lat, '-', color=INK, lw=2.6, zorder=6, solid_capstyle='round')
    for z, (k, _, col, ls) in enumerate(members, start=4):
        g = tracks[k]
        if len(g) < 2:
            continue
        ax.plot(g.lon, g.lat, color=col, ls=ls, lw=2.0, zorder=z / 10 + 4,
                alpha=0.95, solid_capstyle='round')
        ax.plot(g.lon.iloc[-1], g.lat.iloc[-1], 's', ms=6, mfc=col,
                mec='white', mew=1.2, zorder=z / 10 + 7)
    ax.plot(o.lon.iloc[0], o.lat.iloc[0], 'o', ms=8, mfc=release, mec=INK,
            mew=1.6, zorder=9)
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
    # the unclipped Sicily coastline in every panel made the PDF 8 MB;
    # land and coast are rasterised, the tracks stay vector
    ax.set_rasterization_zorder(3)
    for s_ in ax.spines.values():
        s_.set_color(GRID)


def legend(fig, members, ncol, y, release='Release'):
    h = [Line2D([], [], color=INK, lw=2.6, label='Observed')]
    h += [Line2D([], [], color=c, ls=ls, lw=2.0, label=l) for _, l, c, ls in members]
    h += [Line2D([], [], ls='none', marker='o', mfc='white', mec=INK, mew=1.8,
                 ms=7, label=release),
          Line2D([], [], ls='none', marker='s', mfc=MUTED, mec='white', mew=1.2,
                 ms=6.5, label='End of scored window')]
    fig.legend(handles=h, loc='lower center', ncol=ncol, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, y))


def save(fig, name):
    for ext in ('png', 'pdf'):
        p = FIG / f'{name}.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'wrote {p}')
    plt.close(fig)


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    full = pd.read_csv(PROC / f'drifter_metrics_{MEMBERS[-1][0]}.csv')
    deploys = sorted(full.deploy.unique())

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')
    coast = split_long_segments(land)

    # Body figure: the five deployments of SELECTED and the wave-coupled pair
    # that differs only in the canopy, with a locator panel in the first cell.
    pair = [(k, l, c, '-') for k, l, c in MEMBERS]
    tags = {m[0] for m in pair}
    if SUFFIX:
        tags |= {m[0] for m in MEMBERS_ALL}
    sims = {k: pd.read_csv(PROC / f'drifter_sim_{k}.csv', parse_dates=['time'])
            for k in tags}

    fig, axes = plt.subplots(2, 3, figsize=(11.6, 8.4), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    locator(axes[0, 0], obs, land, coast, deps=SELECTED)
    for ax, dep in zip(axes.ravel()[1:], SELECTED):
        draw_panel(ax, dep, pick_drifter(full, dep), obs, sims, pair, land, coast,
                   release=DEP_COLOR[dep])
    legend(fig, pair, 5, -0.012, release='Release, coloured by deployment')
    fig.subplots_adjust(left=0.012, right=0.988, top=0.965, bottom=0.06,
                        wspace=0.06, hspace=0.14)
    save(fig, 'drifter_trajectories')

    if not SUFFIX:
        return
    # Supplementary figure: every deployment and every member. The drifter is
    # the same as in the body figure, the median-skill drifter under WV.
    fig, axes = plt.subplots(3, 4, figsize=(14.0, 11.2), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    for ax, dep in zip(axes.ravel(), deploys):
        draw_panel(ax, dep, pick_drifter(full, dep), obs, sims, MEMBERS_ALL,
                   land, coast)
    legend(fig, MEMBERS_ALL, 8, -0.008)
    fig.subplots_adjust(left=0.012, right=0.988, top=0.965, bottom=0.05,
                        wspace=0.06, hspace=0.14)
    save(fig, 'drifter_trajectories_all')


if __name__ == '__main__':
    main()
