"""Split the trajectory error into a magnitude part and a direction part.

The six-member results suggest something the earlier five could not. Bed
mobility under uniform roughness recovers the observed path length (0.93
against 0.78 to 0.81 for the fixed-bed members) yet has the worst endpoint
separation of the ensemble (661 m). Adding distributed roughness to the same
mobile bed keeps the path length (0.97) and cuts the endpoint separation to
334 m. That pattern is what you would see if the two treatments fixed different
halves of the error.

This tests it directly. For each drifter, over the scored window:

  speed error     = simulated path length / observed path length
  direction error = mean angular difference between the simulated and observed
                    displacement direction, sampled per output step
  net displacement ratio = simulated net displacement / observed

A member can get the path length right and the displacement wrong only by
travelling the right distance in the wrong directions, so the three together
separate "how far" from "which way".

Output: data/processed/transport_error_decomposition.csv and
        figures/transport_error_decomposition.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import MEMBERS as ENS, KEYS, TAG, LABEL, CONTRASTS, MODELDIR

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
BASE = '#9a9892'
ACCENT = '#4a3aa7'

MEMBERS = [(k, TAG[k], LABEL[k]) for k in KEYS]


def hav(lo1, la1, lo2, la2):
    R = 6371000.0
    p1, p2 = np.radians(la1), np.radians(la2)
    dp, dl = np.radians(la2 - la1), np.radians(lo2 - lo1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def bearings(lon, lat):
    """Step-wise displacement direction, in radians, on a local tangent plane."""
    dx = np.diff(lon) * np.cos(np.radians(lat[:-1]))
    dy = np.diff(lat)
    keep = (np.abs(dx) + np.abs(dy)) > 0
    return np.arctan2(dy[keep], dx[keep]), keep


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])

    rows = []
    for key, tag, _ in MEMBERS:
        sim = pd.read_csv(PROC / f'drifter_sim_{tag}.csv', parse_dates=['time'])
        for (dp, did), s in sim.groupby(['deploy', 'drifter_id']):
            o = obs[(obs['deploy'] == dp) & (obs['source'] == did)].sort_values('time')
            if len(o) < 3:
                continue
            s = s[(s['time'] >= o['time'].min()) &
                  (s['time'] <= o['time'].max())].sort_values('time')
            if len(s) < 3:
                continue
            ot = o['time'].values.astype('datetime64[s]').astype(float)
            st = s['time'].values.astype('datetime64[s]').astype(float)
            olon = np.interp(st, ot, o['lon'].values)
            olat = np.interp(st, ot, o['lat'].values)
            slon, slat = s['lon'].values, s['lat'].values

            op = hav(olon[:-1], olat[:-1], olon[1:], olat[1:]).sum()
            sp = hav(slon[:-1], slat[:-1], slon[1:], slat[1:]).sum()
            od = hav(olon[0], olat[0], olon[-1], olat[-1])
            sd = hav(slon[0], slat[0], slon[-1], slat[-1])

            ob, ko = bearings(olon, olat)
            sb, ks = bearings(slon, slat)
            n = min(len(ob), len(sb))
            if n < 3:
                continue
            diff = np.abs(np.angle(np.exp(1j * (sb[:n] - ob[:n]))))

            rows.append({'member': key, 'deploy': dp, 'drifter_id': did,
                         'speed_ratio': sp / op if op > 0 else np.nan,
                         'disp_ratio': sd / od if od > 0 else np.nan,
                         'heading_err_deg': float(np.degrees(diff.mean()))})

    d = pd.DataFrame(rows)
    d.to_csv(PROC / 'transport_error_decomposition.csv', index=False,
             float_format='%.4f')

    g = d.groupby('member')
    print(f"{'member':12s} {'path ratio':>11s} {'disp ratio':>11s} {'heading err':>12s}")
    for k, _, _ in MEMBERS:
        s = g.get_group(k)
        print(f'{k:12s} {s.speed_ratio.mean():11.2f} {s.disp_ratio.mean():11.2f} '
              f'{s.heading_err_deg.mean():10.1f} deg')

    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.9), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    panels = [('speed_ratio', 'Path length, sim / obs', 1.0,
               '(a) How far the particles went'),
              ('disp_ratio', 'Net displacement, sim / obs', 1.0,
               '(b) How far they ended up'),
              ('heading_err_deg', 'Mean heading error (deg)', 0.0,
               '(c) Which way they went')]
    for ax, (col, xlab, ref, title) in zip(axes, panels):
        ys = np.arange(len(MEMBERS))[::-1]
        for y, (k, _, lab) in zip(ys, MEMBERS):
            v = g.get_group(k)[col].mean()
            c = ACCENT if k == 'vr' else BASE
            ax.plot([ref, v], [y, y], '-', color=c, lw=3.0, zorder=3,
                    solid_capstyle='round')
            ax.plot([v], [y], 'o', ms=8, mfc=c, mec='white', mew=1.2, zorder=4)
            ax.text(v, y + 0.32, f'{v:.2f}' if col != 'heading_err_deg'
                    else f'{v:.0f}', fontsize=7.5,
                    color=INK if k == 'vr' else MUTED, ha='center')
        if ref:
            ax.axvline(ref, color=INK, ls='--', lw=1.3, zorder=2)
        ax.set_yticks(ys)
        ax.set_yticklabels([m[2] for m in MEMBERS], fontsize=7.5)
        ax.set_xlabel(xlab, fontsize=8.5, color=MUTED)
        ax.set_title(title, loc='left', fontsize=9.5, color=INK, pad=7)
        ax.set_ylim(-0.6, len(MEMBERS) - 0.3)
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=8)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color('#c9c7c1')
    fig.tight_layout()
    for ext in ('png', 'pdf'):
        p = FIG / f'transport_error_decomposition.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
