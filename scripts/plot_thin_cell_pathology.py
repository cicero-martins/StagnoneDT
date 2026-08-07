"""Map the cells that share the pathology which aborts the no-wave mobile-bed runs.

Global cell 14285 trips maxVelocity in both no-wave mobile-bed members, at
bit-identical model time on two independent attempts. In the completed
wave-coupled vr member that cell is dry in 99% of output steps, mean depth
1.8 mm, yet reaches 0.56 m/s. This asks how many other cells look the same, so
a fix can be scoped to the whole set rather than to the cell that tripped first.

Pathology, as measured on the completed vr run: dry (h < epsHu = 0.01 m) in more
than 90% of output steps, and still reaching more than 0.30 m/s at some point.

The distinction that matters for the fix is bed level. A cell above the datum in
a basin whose tidal range is 0.25 m is land that occasionally takes a film of
water, and forcing it permanently dry removes nothing physical. A cell below the
datum inside the lagoon is a real intertidal flat, and drying it would change
the basin.

Output: figures/thin_cell_pathology.{png,pdf}
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

EPSHU = 0.01
DRY_FRAC = 0.90
FAST = 0.30
CRASH_CELL = 14285
LAGOON = dict(lon=(12.418, 12.492), lat=(37.815, 37.914))

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
LANDC = '#efece6'
LAND_EDGE = '#c9c7c1'
SUPRA = '#eb6834'   # above datum: safe to force dry
SUB = '#4a3aa7'     # below datum: real intertidal, do not touch
CRASH = '#111111'


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
    d = pd.read_csv(PROC / 'thin_cell_scan_vr.csv').drop_duplicates('globalnr')

    patho = d[(d.dryfrac > DRY_FRAC) & (d.ucmag_max > FAST)].copy()
    patho['supratidal'] = patho.bl > 0
    inlag = ((patho.lon.between(*LAGOON['lon'])) &
             (patho.lat.between(*LAGOON['lat'])))
    patho['in_lagoon'] = inlag

    print(f'{len(d)} cells total, {len(patho)} pathological')
    print(f'  above datum (bl > 0): {patho.supratidal.sum()}')
    print(f'  below datum:          {(~patho.supratidal).sum()}')
    print(f'  inside the lagoon:    {patho.in_lagoon.sum()}')
    print(f'  above datum AND outside the lagoon: '
          f'{(patho.supratidal & ~patho.in_lagoon).sum()}')
    c = d[d.globalnr == CRASH_CELL]
    if len(c):
        r = c.iloc[0]
        print(f'\ncrash cell {CRASH_CELL}: bl={r.bl:+.2f} dry={100*r.dryfrac:.0f}% '
              f'ucmax={r.ucmag_max:.2f} m/s')
        print(f'  cells with a HIGHER ucmax than the one that tripped: '
              f'{(patho.ucmag_max > r.ucmag_max).sum()}')

    land = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    land += parse_ldb(MODEL / 'sicily2.ldb')

    fig = plt.figure(figsize=(10.6, 7.4), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.15], wspace=0.28)
    ax0, ax1, ax2 = (fig.add_subplot(gs[0]), fig.add_subplot(gs[1]),
                     fig.add_subplot(gs[2]))

    for ax, box, title in [
            (ax0, (12.30, 37.83, 12.56, 38.02), '(a) Model domain'),
            (ax1, (12.415, 37.810, 12.500, 37.985), '(b) Lagoon and the strip to its north')]:
        for p in land:
            ax.fill(p[:, 0], p[:, 1], color=LANDC, ec=LAND_EDGE, lw=0.4, zorder=1)
        s = patho[patho.supratidal]
        ax.scatter(s.lon, s.lat, s=13, c=SUPRA, marker='o', linewidths=0,
                   zorder=4, alpha=0.9)
        s = patho[~patho.supratidal]
        ax.scatter(s.lon, s.lat, s=13, c=SUB, marker='o', linewidths=0,
                   zorder=4, alpha=0.9)
        if len(c):
            ax.plot(c.lon, c.lat, marker='*', ms=17, mfc=CRASH, mec='white',
                    mew=1.2, ls='none', zorder=6)
        ax.add_patch(plt.Rectangle(
            (LAGOON['lon'][0], LAGOON['lat'][0]),
            np.diff(LAGOON['lon'])[0], np.diff(LAGOON['lat'])[0],
            fill=False, ec=MUTED, lw=0.8, ls=':', zorder=3))
        ax.set_xlim(box[0], box[2])
        ax.set_ylim(box[1], box[3])
        ax.set_aspect(1.0 / np.cos(np.radians(37.9)))
        ax.set_title(title, loc='left', fontsize=9.5, color=INK, pad=6)
        ax.tick_params(colors=MUTED, labelsize=7.5)
        ax.grid(color=GRID, lw=0.5, zorder=0)
        ax.set_axisbelow(True)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color(LAND_EDGE)

    # (c) why bed level is the right split
    ax2.scatter(patho.bl, patho.ucmag_max, s=15,
                c=[SUPRA if b else SUB for b in patho.supratidal],
                linewidths=0, alpha=0.85, zorder=3)
    if len(c):
        ax2.plot(c.bl, c.ucmag_max, marker='*', ms=17, mfc=CRASH, mec='white',
                 mew=1.2, ls='none', zorder=5)
        ax2.annotate(f'cell {CRASH_CELL}', (float(c.bl.iloc[0]),
                     float(c.ucmag_max.iloc[0])), textcoords='offset points',
                     xytext=(9, 4), fontsize=8, color=INK)
    ax2.axvline(0, color=INK, ls='--', lw=1.1, zorder=2)
    ax2.set_xlabel('Bed level (m)', fontsize=8.5, color=MUTED)
    ax2.set_ylabel('Maximum speed reached (m s$^{-1}$)', fontsize=8.5,
                   color=MUTED)
    ax2.set_title('(c) Bed level against peak speed', loc='left',
                  fontsize=9.5, color=INK, pad=6)
    ax2.grid(color=GRID, lw=0.6, zorder=0)
    ax2.set_axisbelow(True)
    ax2.tick_params(colors=MUTED, labelsize=8)
    for sp in ['top', 'right']:
        ax2.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax2.spines[sp].set_color(LAND_EDGE)

    ns, nb = int(patho.supratidal.sum()), int((~patho.supratidal).sum())
    handles = [
        Line2D([], [], ls='none', marker='o', mfc=SUPRA, mec='none', ms=7,
               label=f'Above datum, {ns} cells'),
        Line2D([], [], ls='none', marker='o', mfc=SUB, mec='none', ms=7,
               label=f'Below datum, {nb} cells'),
        Line2D([], [], ls='none', marker='*', mfc=CRASH, mec='white', mew=1.0,
               ms=13, label=f'Cell {CRASH_CELL}, aborts both runs'),
        Line2D([], [], ls=':', color=MUTED, lw=1.0, label='Lagoon extent')]
    fig.legend(handles=handles, loc='lower center', ncol=4, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, 0.005))
    fig.suptitle('Cells dry in more than 90% of output steps that still reach '
                 '0.3 m s$^{-1}$, measured on the completed wave-coupled run',
                 fontsize=9.5, color=MUTED, y=0.985)
    fig.tight_layout(rect=(0, 0.055, 1, 0.96))
    for e in ('png', 'pdf'):
        p = FIG / f'thin_cell_pathology.{e}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
