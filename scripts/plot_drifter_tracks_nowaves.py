"""Observed against simulated drifter tracks, for the deploys that drive the
ensemble result and the ones that contradict it.

Panel (d) of the attribution figure showed that the morphodynamics-plus-
roughness gain is carried by part of the dataset rather than shared across it.
This figure asks what that looks like in the trajectories themselves: the two
deploys where the gain is largest and the two where it is most negative, each
with the observation and three model members drawn on the same axes.

What it shows is under-advection, not a directional error. In deploys 1 and 2
the fixed-bed members travel a fraction of the observed distance in roughly the
right direction. Mean path ratio is 0.75-0.81 for the four baseline members
against 0.96 for vr, and 31-34% of their drifters fall below 0.7 against 11%
for vr. Deploy 2 is the extreme case: the baseline members cover about one
sixth of the observed path.

CLIPPING IS NOT OPTIONAL HERE. OpenDrift advects every particle to the end of
the forcing, but the deployments lasted 0.5 to 7.2 hours against 12 to 41 hours
of simulation. An unclipped plot shows a spurious southward runaway that is
entirely post-recovery drift, and it invites exactly the wrong mechanistic
story. The scoring in drifter_validation_*.py already masks to the observed
window, so metrics were never affected, only the picture.

Members shown are the ones the argument turns on:
  nowaves  waves off, fixed bed, uniform roughness
  nodm     the same with wave coupling on, so nodm vs nowaves is the wave effect
  vr       wave coupling, distributed roughness and active morphodynamics,
           the best-scoring member

Observation is black; the three members take the validated all-pairs trio.

Output: figures/drifter_tracks_nowaves.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model' / 'dflowfm_v04AE_vr'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
LAND = '#e7e6e1'
LAND_EDGE = '#b9b7ae'
INK = '#1b1b1b'
MUTED = '#6b6b6b'

MEMBERS = [
    ('nowaves', 'v04AE_nowaves', 'no waves', '#eb6834'),
    ('nodm',    'v04AE_nodm',    'waves, fixed bed', '#1baf7a'),
    ('vr',      'v04AE_vr',      'waves + roughness + morph.', '#4a3aa7'),
]
ASPECT = 1.0 / np.cos(np.radians(37.87))
N_SHOW = 2      # best and worst deploys by the vr - nodm_vr contrast


def parse_ldb(path):
    polys = []
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith('*')]
    i = 0
    while i < len(lines):
        i += 1
        if i >= len(lines):
            break
        try:
            npts = int(lines[i].split()[0])
        except (ValueError, IndexError):
            break
        i += 1
        polys.append(np.array([list(map(float, lines[i + k].split()[:2]))
                               for k in range(npts)]))
        i += npts
    return polys


def pick_deploys():
    """Deploys with the largest positive and negative vr - nodm_vr difference."""
    a = pd.read_csv(PROC / 'drifter_metrics_v04AE_vr.csv')
    b = pd.read_csv(PROC / 'drifter_metrics_v04AE_nodm_vr.csv')
    m = a.merge(b, on=['deploy', 'drifter_id'], suffixes=('_vr', '_nodmvr'))
    m['d'] = m['LW_skill_vr'] - m['LW_skill_nodmvr']
    per = m.groupby('deploy')['d'].mean().sort_values()
    worst = list(per.index[:N_SHOW])
    best = list(per.index[-N_SHOW:][::-1])
    return best, worst, per


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    sims = {k: pd.read_csv(PROC / f'drifter_sim_{tag}.csv', parse_dates=['time'])
            for k, tag, _, _ in MEMBERS}
    polys = parse_ldb(MODEL / 'sicily2.ldb') + parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')

    best, worst, per = pick_deploys()
    order = best + worst
    print('Per-deploy mean (vr - nodm_vr):')
    for dp, v in per.items():
        tag = ' <- shown' if dp in order else ''
        print(f'  deploy {int(dp):2d}: {v:+.3f}{tag}')

    # One frame size for every panel, so the panels are the same shape and the
    # same scale. Per-panel auto-fitting makes tracks of very different length
    # look equally large, which is exactly the wrong impression here.
    need_lon = need_lat = 0.0
    for dp in order:
        xs = [obs.loc[obs['deploy'] == dp, 'lon']]
        ys = [obs.loc[obs['deploy'] == dp, 'lat']]
        for key, _, _, _ in MEMBERS:
            sd = sims[key]
            sd = sd[sd['deploy'] == dp]
            xs.append(sd['lon'])
            ys.append(sd['lat'])
        xs = pd.concat(xs)
        ys = pd.concat(ys)
        need_lon = max(need_lon, xs.max() - xs.min())
        need_lat = max(need_lat, ys.max() - ys.min())
    half_lon = 0.5 * need_lon * 1.18
    half_lat = 0.5 * need_lat * 1.18
    # keep the panel box consistent with the latitude aspect correction
    half_lon = max(half_lon, half_lat / ASPECT)
    half_lat = max(half_lat, half_lon * ASPECT * 0.62)
    print(f'Common frame: {2*half_lon:.4f} deg lon x {2*half_lat:.4f} deg lat')

    fig, axes = plt.subplots(1, len(order), figsize=(3.05 * len(order), 4.6),
                             dpi=300)
    fig.patch.set_facecolor(SURFACE)

    for ax, dp in zip(np.atleast_1d(axes), order):
        o = obs[obs['deploy'] == dp]
        cx = 0.5 * (o['lon'].min() + o['lon'].max())
        cy = 0.5 * (o['lat'].min() + o['lat'].max())

        for poly in polys:
            ax.fill(poly[:, 0], poly[:, 1], facecolor=LAND, edgecolor=LAND_EDGE,
                    lw=0.5, zorder=1)

        for src, g in o.groupby('source'):
            g = g.sort_values('time')
            ax.plot(g['lon'], g['lat'], '-', color=INK, lw=2.0, zorder=5,
                    solid_capstyle='round')
            ax.plot(g['lon'].iloc[0], g['lat'].iloc[0], marker='o', ms=5,
                    mfc='white', mec=INK, mew=1.4, zorder=7, ls='')
            ax.plot(g['lon'].iloc[-1], g['lat'].iloc[-1], marker='o', ms=5,
                    mfc=INK, mec='white', mew=1.0, zorder=7, ls='')

        for key, _, _, colour in MEMBERS:
            s = sims[key]
            s = s[s['deploy'] == dp]
            for src, g in s.groupby('drifter_id'):
                # Clip each simulated track to the window in which THAT drifter
                # was actually in the water. OpenDrift is run to the end of the
                # forcing for every particle, so an unclipped track carries 12
                # to 41 hours of drift past recovery and invents a divergence
                # the scoring never sees. The metrics already mask this way.
                og = o[o['source'] == src]
                if og.empty:
                    continue
                t0, t1 = og['time'].min(), og['time'].max()
                g = g[(g['time'] >= t0) & (g['time'] <= t1)].sort_values('time')
                if g.empty:
                    continue
                ax.plot(g['lon'], g['lat'], '-', color=colour, lw=1.5,
                        alpha=0.9, zorder=4)
                ax.plot(g['lon'].iloc[-1], g['lat'].iloc[-1], marker='o', ms=4,
                        mfc=colour, mec='white', mew=0.8, zorder=6, ls='')

        ax.set_xlim(cx - half_lon, cx + half_lon)
        ax.set_ylim(cy - half_lat, cy + half_lat)
        ax.set_aspect(ASPECT)
        ax.tick_params(colors=MUTED, labelsize=7)
        ax.ticklabel_format(useOffset=False, style='plain')
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(30)
            lbl.set_ha('right')
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color('#c9c7c1')
        d = per.loc[dp]
        kind = 'gain' if d > 0 else 'loss'
        ax.set_title(f'Deploy {int(dp)}\n$\\Delta$LW {d:+.2f} ({kind})',
                     fontsize=9, color=INK, pad=6, linespacing=1.25)

    handles = [Line2D([0], [0], color=INK, lw=2.2, label='Observed')]
    handles += [Line2D([0], [0], color=c, lw=1.8, label=lab)
                for _, _, lab, c in MEMBERS]
    handles += [Line2D([0], [0], marker='o', ls='', mfc='white', mec=INK,
                       mew=1.4, ms=6, label='Release'),
                Line2D([0], [0], marker='o', ls='', mfc=INK, mec='white',
                       ms=6, label='End of track')]
    fig.legend(handles=handles, loc='lower center', ncol=6, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.035))
    fig.suptitle('Observed and simulated drifter tracks, deploys with the '
                 'largest and smallest morphodynamics gain',
                 fontsize=10, color=INK, y=1.01)
    fig.tight_layout()

    for ext in ('png', 'pdf'):
        p = FIG / f'drifter_tracks_nowaves.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
