"""Where the wave-coupled fixed-bed member fails, and what the cells look like.

On Baptist formula 154 this member aborts on the velocity cap at
2025-07-04 18:00:58, twice, having looked healthy at the frame 58 seconds
earlier: domain maximum 2.90 m/s, p99 2.08. The abort message carries a cell
index that resolves to nothing usable -- the global flow-element numbering runs
to 25210 and the index reported was 25968, so it is not a cell index at all.

The cells were found instead by looking for anomalous acceleration between the
last ordinary frame and the emergency solution-state write that FM appends on
abort. That write lands in the map.nc of the reporting partition only, which is
why a naive read that truncates to the shortest partition drops it.

What the search returns is a cluster about 400 m across on the southwest shore
of Marettimo, 45 km from the lagoon, where cells of 0.7 m water depth sit
against neighbours 21 to 28 m deep. Water level there moves by 1.79 m in 58
seconds while the tide is falling by centimetres.

    python scripts/plot_nodm_vr_154_failure_region.py
"""
from pathlib import Path
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.environ.get('CLAUDE_SCRATCH', ROOT / 'data' / 'processed'))
NPZ = SCRATCH / 'failregion.npz'
OUT = ROOT / 'figures' / 'nodm_vr_154_failure_region.png'

# The accelerating cluster, from the frame-to-frame search described above.
CLUSTER = np.array([
    (12.0505, 37.9463), (12.0503, 37.9464), (12.0506, 37.9461),
    (12.0497, 37.9464), (12.0516, 37.9461), (12.0509, 37.9466),
])
LAGOON = (12.42, 12.50, 37.79, 37.92)
ARL_X = (12.3925, 12.4963)          # extent of the seagrass .arl
ARL_Y = (37.7971, 37.9752)

# Ink stays in text tokens; the marks carry identity. One sequential hue for
# depth, one status colour for the failing cells.
INK, MUTED, GRID = '#1c1c1c', '#6b6b6b', '#dcdcdc'
FAIL = '#c1121f'


def main():
    d = np.load(NPZ)
    x, y, bl, s1 = d['x'], d['y'], d['bl'], d['s1']
    # Partition 5 is kept separately and in full. It is the reporting rank, so
    # it alone carries the 38th frame, the emergency solution-state write 58 s
    # after the last ordinary one. Concatenating partitions and truncating to
    # the shortest silently drops exactly the frame the event is in.
    x5, y5, bl5, s15, u5, t5 = (d['x5'], d['y5'], d['bl5'],
                                d['s15'], d['u5'], d['t5'])
    depth = s1[-1] - bl

    fig = plt.figure(figsize=(14.5, 5.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.0, 1.0], wspace=0.42)

    # (a) the whole domain, to show the separation
    ax = fig.add_subplot(gs[0])
    sea = bl < 0
    # sqrt stretch: the domain runs to 700 m, so a linear ramp renders the whole
    # shelf as one flat tone and hides exactly the structure that matters here.
    ax.scatter(x[sea], y[sea], c=np.sqrt(-bl[sea]), s=1.4, cmap='Blues',
               vmin=0, vmax=np.sqrt(400), linewidths=0, rasterized=True)
    ax.scatter(x[~sea], y[~sea], c='#d9d2c5', s=1.4, linewidths=0, rasterized=True)
    ax.add_patch(plt.Rectangle((ARL_X[0], ARL_Y[0]), ARL_X[1] - ARL_X[0],
                               ARL_Y[1] - ARL_Y[0], fill=False, ec='#2a9d8f',
                               lw=1.4, zorder=5))
    ax.text(ARL_X[1] + 0.01, ARL_Y[0] + 0.02, 'seagrass\n.arl extent',
            color='#2a9d8f', fontsize=8, va='bottom')
    ax.scatter(*CLUSTER.mean(axis=0), s=90, marker='o', facecolor='none',
               edgecolor=FAIL, lw=2.0, zorder=6)
    ax.annotate('failing cells', CLUSTER.mean(axis=0),
                xytext=(12.02, 37.72), color=FAIL, fontsize=9,
                arrowprops=dict(arrowstyle='-', color=FAIL, lw=1.0))
    ax.set_title('(a)  45 km from the lagoon, outside the meadow',
                 fontsize=9.5, color=INK, loc='left')
    _frame(ax)

    # (b) the cluster, and the step it sits on
    ax = fig.add_subplot(gs[1])
    m = (np.abs(x - 12.0506) < 0.09) & (np.abs(y - 37.9463) < 0.07)
    sc = ax.scatter(x[m], y[m], c=bl[m], s=26, cmap='terrain',
                    norm=TwoSlopeNorm(vcenter=0, vmin=-60, vmax=15),
                    linewidths=0)
    ax.scatter(CLUSTER[:, 0], CLUSTER[:, 1], s=110, marker='o',
               facecolor='none', edgecolor=FAIL, lw=1.8, zorder=6)
    cb = plt.colorbar(sc, ax=ax, fraction=0.042, pad=0.14)
    cb.set_label('bed level (m)', fontsize=8, color=MUTED)
    cb.ax.tick_params(labelsize=7, colors=MUTED)
    ax.set_title('(b)  Marettimo shore:\n0.7 m cells against 25 m neighbours',
                 fontsize=9.5, color=INK, loc='left')
    _frame(ax)

    # (c) what actually happens, per cell, into the emergency frame
    ax = fig.add_subplot(gs[2])
    hours = (t5 - t5[0]) / 3600.0
    idx5 = [int(np.argmin(np.hypot(x5 - cx, y5 - cy))) for cx, cy in CLUSTER]
    jump = np.array([s15[-1, i] - s15[-2, i] for i in idx5])
    worst = int(np.argmax(np.abs(jump)))
    for j, i in enumerate(idx5):
        ax.plot(hours, s15[:, i], lw=1.0,
                color=FAIL if j == worst else MUTED,
                alpha=1.0 if j == worst else 0.45,
                zorder=5 if j == worst else 2)
    ax.set_xlabel('hours from 2025-07-04 00:00', fontsize=8, color=MUTED)
    ax.set_ylabel('water level (m)', fontsize=8, color=MUTED, labelpad=1)
    ax.set_title('(c)  water level in the six cells;\nthe last point is the '
                 'emergency write, 58 s on', fontsize=9.5, color=INK, loc='left')
    lo = min(s15[:, idx5].min(), -0.1) - 0.15
    hi = max(s15[:, idx5].max(), 0.5) + 0.15
    ax.set_ylim(lo, hi)
    ax.annotate(f'{jump[worst]:+.2f} m in {t5[-1] - t5[-2]:.0f} s',
                (hours[-1], s15[-1, idx5[worst]]),
                xytext=(hours[-1] * 0.42, lo + 0.30),
                color=FAIL, fontsize=8.5, ha='left',
                arrowprops=dict(arrowstyle='->', color=FAIL, lw=1.0))
    ax.axhline(0, color=GRID, lw=0.8, zorder=1)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(GRID)
    ax.tick_params(labelsize=7, colors=MUTED)
    ax.grid(True, color=GRID, lw=0.5, alpha=0.6)
    ax.set_axisbelow(True)

    fig.suptitle('nodm_vr on Baptist 154: where and how it aborts',
                 fontsize=11, color=INK, x=0.007, ha='left', y=0.985)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, bbox_inches='tight', facecolor='white')
    print(f'wrote {OUT}')

    # the numbers the figure is asserting, so they can be checked
    print('\ncluster cells (partition 5, into the emergency frame):')
    print(f"{'lon':>9} {'lat':>8} {'bl':>8} {'depth':>7} {'ds1':>9} {'|U|':>7}")
    for i in idx5:
        print(f'{x5[i]:9.4f} {y5[i]:8.4f} {bl5[i]:+8.2f} '
              f'{s15[-1, i] - bl5[i]:7.2f} {s15[-1, i] - s15[-2, i]:+9.4f} '
              f'{u5[-1, i]:7.3f}')
    print(f'  interval into the emergency frame: {t5[-1] - t5[-2]:.1f} s')
    near = np.hypot((x - 12.0506) * 88, (y - 37.9463) * 111) < 1.0
    print(f'\nwithin 1 km: {int(near.sum())} cells, bed level '
          f'{bl[near].min():.1f} to {bl[near].max():.1f} m')
    lag = ((x > LAGOON[0]) & (x < LAGOON[1]) & (y > LAGOON[2]) & (y < LAGOON[3]))
    print(f'lagoon mean water level, final three frames: '
          f'{np.round([np.nanmean(s1[k][lag]) for k in (-3, -2, -1)], 4)}')


def _frame(ax):
    ax.set_aspect(1 / np.cos(np.deg2rad(37.9)))
    ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    ax.yaxis.set_major_locator(plt.MaxNLocator(5))
    ax.tick_params(labelsize=7, colors=MUTED)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.set_xlabel('lon', fontsize=8, color=MUTED)
    ax.set_ylabel('lat', fontsize=8, color=MUTED)


if __name__ == '__main__':
    main()
