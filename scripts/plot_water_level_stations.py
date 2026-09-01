"""Water level, and where it can tell the configurations apart.

Section 4.1 makes a claim that a table of numbers states but does not show: the
eight configurations are indistinguishable at the two gauges near the inlets and
separate cleanly at the one inside the vegetated basin. This figure is the
evidence for it.

Anomalies rather than raw levels, because the raw record is dominated by a
positive bias that every member shares. That bias is a datum and boundary-offset
property and it is not what distinguishes the configurations, so plotting it
would use most of the vertical axis on the part of the signal that carries no
information about the question.

(a) The AltaVilaEst record over the scored window, observed against the two
    arms. Each arm is drawn as its mean and the envelope of its four
    configurations, which is the honest way to show that the separation is
    between arms and not within them.
(b) Anomaly RMSE at all three stations for all eight configurations. The two
    outer gauges interleave, the inner one does not.

    python scripts/plot_water_level_stations.py
"""
from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import KEYS, FACTORS
from validate_wl_ensemble import load_member, STATIONS, PROC

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE, INK, MUTED, GRID = '#ffffff', '#1b1b1b', '#6b6b6b', '#e8e7e4'
C_BARE, C_VEG = '#eb6834', '#4a3aa7'

W0, W1 = pd.Timestamp('2025-07-08'), pd.Timestamp('2025-07-10')
BARE = [k for k in KEYS if FACTORS[k]['roughness'] != 'vegetated']
VEG = [k for k in KEYS if FACTORS[k]['roughness'] == 'vegetated']
SHOW = 'AltaVilaEst'
CODE = {'nowaves': '---', 'nowaves_veg': '-V-', 'nodm': 'W--',
        'nodm_veg': 'WV-', 'nowaves_dm': '--M', 'nowaves_vegdm': '-VM',
        'bl': 'W-M', 'veg': 'WVM'}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'):
        ax.spines[sp].set_color('#c9c7c1')


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})

    obs = {}
    for st, fn in STATIONS.items():
        d = pd.read_csv(PROC / fn)
        tc = [c for c in d.columns if 'time' in c.lower()][0]
        vc = [c for c in d.columns if c != tc][0]
        d = d[[tc, vc]].rename(columns={tc: 'time', vc: st})
        d['time'] = pd.to_datetime(d['time'])
        obs[st] = d.set_index('time')[st]

    mod = {k: load_member(k).set_index('time') for k in KEYS}
    grid = mod[KEYS[0]].loc[W0:W1].index

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), dpi=300,
                             gridspec_kw=dict(width_ratios=[1.55, 1.0],
                                              wspace=0.24))
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.89, bottom=0.24)

    # (a) the inner station, observed against the two arms
    ax = axes[0]
    o = obs[SHOW].reindex(grid, method='nearest',
                          tolerance=pd.Timedelta('10min'))
    ax.plot(grid, (o - o.mean()).values, '-', color=INK, lw=2.4, zorder=6)
    for keys, col in ((BARE, C_BARE), (VEG, C_VEG)):
        v = np.array([(mod[k].loc[grid, SHOW]
                       - mod[k].loc[grid, SHOW].mean()).values for k in keys])
        ax.fill_between(grid, v.min(axis=0), v.max(axis=0), color=col,
                        alpha=0.30, lw=0, zorder=3)
        ax.plot(grid, v.mean(axis=0), '-', color=col, lw=1.8, zorder=4)
    ax.set_ylabel('Water level anomaly (m)', fontsize=10, color=MUTED)
    ax.set_title(f'(a) {SHOW}, the station inside the vegetated basin',
                 loc='left', fontsize=11, color=INK, pad=8)
    ax.xaxis.set_major_formatter(mpl.dates.DateFormatter('%d %b\n%H:%M'))
    ax.legend(handles=[
        Line2D([], [], color=INK, lw=2.4, label='Observed'),
        Line2D([], [], color=C_BARE, lw=2.2, label='Bare'),
        Line2D([], [], color=C_VEG, lw=2.2, label='Canopy'),
        Patch(facecolor=MUTED, alpha=0.32,
              label='range over the four configurations')],
        fontsize=9, frameon=False, loc='upper center',
        bbox_to_anchor=(0.5, -0.16), ncol=4, columnspacing=1.6)
    style(ax)

    # (b) anomaly RMSE, every station, every configuration
    ax = axes[1]
    sts = ['BocaSud', 'BocaNord', 'AltaVilaEst']
    for i, st in enumerate(sts):
        ob = obs[st].reindex(grid, method='nearest',
                             tolerance=pd.Timedelta('10min'))
        for k in KEYS:
            m = mod[k].loc[grid, st]
            ok = np.isfinite(m.values) & np.isfinite(ob.values)
            a = m.values[ok] - m.values[ok].mean()
            b = ob.values[ok] - ob.values[ok].mean()
            r = float(np.sqrt(np.mean((a - b) ** 2))) * 1000
            col = C_VEG if FACTORS[k]['roughness'] == 'vegetated' else C_BARE
            ax.plot(r, i, 'o', ms=8, mfc=col, mec='white', mew=1.3, zorder=4)
    ax.set_yticks(range(len(sts)))
    ax.set_yticklabels(sts, fontsize=9.5)
    ax.set_ylim(-0.6, len(sts) - 0.4)
    ax.set_xlim(0, 55)
    ax.set_xlabel('Anomaly RMSE (mm)', fontsize=10, color=MUTED)
    ax.set_title('(b) Anomaly RMSE, all eight configurations', loc='left',
                 fontsize=11, color=INK, pad=8)
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'water_level_stations.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
