"""Where the no-wave mobile-bed runs run away, and how many cells are involved.

Both members abort on maxVelocity at bit-identical model time on two independent
attempts, so the failure is deterministic. The abort message names 'cell index
14285', but that index resolves to two very different cells depending on the
numbering convention assumed, so this does not trust it. It asks the crashed
output directly which cells are fast in the last saved steps before the abort,
and compares them against the completed wave-coupled run at the same cells.

Map output is written every 1800 s, so the last saved step is up to half an hour
before the abort and shows the runaway building rather than its peak.

Panels:
  (a) where the fast cells are, over the whole domain
  (b) depth against peak speed, crashed against completed
  (c) the excess over the completed run, by depth band

Output: figures/crash_diagnosis.{png,pdf}
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

LAGOON = dict(lon=(12.418, 12.492), lat=(37.815, 37.914))
SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
LANDC = '#efece6'
LAND_EDGE = '#c9c7c1'
C_VRDM = '#4a3aa7'
C_DM = '#eb6834'
C_OK = '#9a9892'


def parse_ldb(path):
    polys, cur = [], []
    for ln in Path(path).read_text().splitlines():
        s = ln.strip()
        if not s or s.startswith('*'):
            continue
        try:
            x, y = float(s.split()[0]), float(s.split()[1])
        except (ValueError, IndexError):
            if len(cur) > 1:
                polys.append(np.array(cur))
            cur = []
            continue
        cur.append((x, y))
    if len(cur) > 1:
        polys.append(np.array(cur))
    return polys


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    vrdm = pd.read_csv(PROC / 'runaway_vrdm.csv').drop_duplicates('globalnr')
    dm = pd.read_csv(PROC / 'runaway_dm.csv').drop_duplicates('globalnr')
    ok = pd.read_csv(PROC / 'runaway_vr_completed.csv').drop_duplicates('globalnr')

    m = vrdm.merge(ok[['globalnr', 'ucmag']], on='globalnr',
                   suffixes=('', '_ok'))
    m = m.merge(dm[['globalnr', 'ucmag']], on='globalnr', suffixes=('', '_dm'))
    m['excess'] = m.ucmag - m.ucmag_ok
    m['in_lagoon'] = (m.lon.between(*LAGOON['lon']) &
                      m.lat.between(*LAGOON['lat']))

    top = m.nlargest(150, 'ucmag')
    print(f'top 150 cells of the crashed vrdm run:')
    print(f'  inside the lagoon: {int(top.in_lagoon.sum())}')
    print(f'  median depth: {top.depth.median():.1f} m   '
          f'range {top.depth.min():.1f} to {top.depth.max():.1f} m')
    print(f'  cells above datum (bl > 0): {int((top.bl > 0).sum())}')
    print(f'\nlagoon-only peak speed: crashed {m[m.in_lagoon].ucmag.max():.2f}, '
          f'completed {m[m.in_lagoon].ucmag_ok.max():.2f} m/s')
    print(f'offshore peak speed:    crashed {m[~m.in_lagoon].ucmag.max():.2f}, '
          f'completed {m[~m.in_lagoon].ucmag_ok.max():.2f} m/s')

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')

    fig = plt.figure(figsize=(11.2, 4.9), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 1.0, 1.0], wspace=0.30)
    ax0, ax1, ax2 = (fig.add_subplot(gs[0]), fig.add_subplot(gs[1]),
                     fig.add_subplot(gs[2]))

    for p in land:
        ax0.fill(p[:, 0], p[:, 1], color=LANDC, ec=LAND_EDGE, lw=0.4, zorder=1)
    q = m[m.ucmag > 1.5]
    sc = ax0.scatter(q.lon, q.lat, c=q.ucmag, s=16, cmap='inferno_r',
                     vmin=1.5, vmax=2.9, linewidths=0, zorder=4)
    ax0.add_patch(plt.Rectangle(
        (LAGOON['lon'][0], LAGOON['lat'][0]), np.diff(LAGOON['lon'])[0],
        np.diff(LAGOON['lat'])[0], fill=False, ec=INK, lw=1.0, ls=':', zorder=5))
    ax0.annotate('lagoon', (LAGOON['lon'][1], LAGOON['lat'][1]),
                 textcoords='offset points', xytext=(4, 3), fontsize=8,
                 color=INK)
    cb = fig.colorbar(sc, ax=ax0, fraction=0.035, pad=0.02)
    cb.set_label('Peak speed (m s$^{-1}$)', fontsize=8, color=MUTED)
    cb.ax.tick_params(colors=MUTED, labelsize=7.5)
    # sicily2.ldb runs well outside the model domain, so the limits must be set
    # explicitly or the panel autoscales to the land file instead of the mesh
    ax0.set_xlim(m.lon.min() - 0.01, m.lon.max() + 0.01)
    ax0.set_ylim(m.lat.min() - 0.01, m.lat.max() + 0.01)
    ax0.set_aspect(1.0 / np.cos(np.radians(37.9)))
    ax0.set_title('(a) Cells above 1.5 m s$^{-1}$ before the abort', loc='left',
                  fontsize=9.5, color=INK, pad=6)

    ax1.scatter(ok.depth, ok.ucmag, s=5, c=C_OK, linewidths=0, alpha=0.35,
                zorder=2)
    ax1.scatter(m.depth, m.ucmag, s=5, c=C_VRDM, linewidths=0, alpha=0.45,
                zorder=3)
    ax1.set_xscale('symlog', linthresh=1)
    ax1.set_xlabel('Water depth (m)', fontsize=8.5, color=MUTED)
    ax1.set_ylabel('Peak speed (m s$^{-1}$)', fontsize=8.5, color=MUTED)
    ax1.set_title('(b) Speed against depth', loc='left', fontsize=9.5,
                  color=INK, pad=6)

    bands = [(0, 1), (1, 5), (5, 20), (20, 100), (100, 1e6)]
    labs = ['<1', '1-5', '5-20', '20-100', '>100']
    xs = np.arange(len(bands))
    for off, (col, series, lab) in enumerate(
            [(C_DM, m.ucmag_dm, 'no waves + morph.'),
             (C_VRDM, m.ucmag, 'no waves + rough. + morph.')]):
        vals = [series[(m.depth > lo) & (m.depth <= hi)].quantile(0.999)
                - m.ucmag_ok[(m.depth > lo) & (m.depth <= hi)].quantile(0.999)
                for lo, hi in bands]
        ax2.bar(xs + (off - 0.5) * 0.36, vals, width=0.34, color=col,
                label=lab, zorder=3)
    ax2.axhline(0, color=INK, lw=1.0, zorder=4)
    ax2.set_xticks(xs)
    ax2.set_xticklabels(labs, fontsize=8)
    ax2.set_xlabel('Water depth (m)', fontsize=8.5, color=MUTED)
    ax2.set_ylabel('Excess over the completed run (m s$^{-1}$)', fontsize=8.5,
                   color=MUTED)
    ax2.set_title('(c) Where the excess speed sits', loc='left', fontsize=9.5,
                  color=INK, pad=6)
    ax2.legend(frameon=False, fontsize=7.5, loc='upper left')

    for ax in (ax0, ax1, ax2):
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, lw=0.5, zorder=0)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=7.5)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color(LAND_EDGE)

    handles = [Line2D([], [], ls='none', marker='o', mfc=C_VRDM, mec='none',
                      ms=6, label='Crashed run, last saved step'),
               Line2D([], [], ls='none', marker='o', mfc=C_OK, mec='none',
                      ms=6, label='Completed wave-coupled run, same step')]
    ax1.legend(handles=handles, frameon=False, fontsize=7.5, loc='upper left')

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    for e in ('png', 'pdf'):
        p = FIG / f'crash_diagnosis.{e}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
