"""Figures of docs/sentinel2_suspended_matter.md.

Reads the maps written by s2_suspended_matter_lagoon.py, the statistics in
data/processed/s2_tsm_july2025.csv and the surface silt of the model members
in data/processed/arm_surface_silt_s2.csv (surface_silt_at_s2_overpasses_simit.py).

Usage:  python figure_s2_suspended_matter.py
Writes: figures/s2_tsm_scenes_rgb.png, s2_tsm_processing.png, s2_tsm_maps.png,
        s2_tsm_model_comparison.png
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'figures'
M = np.load(ROOT / 'data' / 'raw' / 'satellite' / 's2_cogs_july2025' / 's2_tsm_maps.npz')
STATS = pd.read_csv(ROOT / 'data' / 'processed' / 's2_tsm_july2025.csv', parse_dates=['datetime'])
MODEL = pd.read_csv(ROOT / 'data' / 'processed' / 'arm_surface_silt_s2.csv', parse_dates=['overpass'])

w, s, e, n = M['extent']
X0, Y0 = w, s
EXT = [0, (e - w) / 1e3, 0, (n - s) / 1e3]   # km from the south-west corner of the window
lagoon = M['lagoon']
plt.rcParams.update({'font.size': 8, 'axes.titlesize': 8})


def label(i):
    return f"{M['times'][i][:10]}  {M['times'][i][11:]} UTC  {M['orbits'][i]}"


def frame(ax, km=True, xkm=None):
    ax.contour(np.flipud(lagoon), levels=[0.5], colors='k', linewidths=0.4, extent=EXT)
    ax.set_xticks([0, 2, 4, 6]); ax.set_yticks([0, 4, 8, 12])
    if not (km if xkm is None else xkm):
        ax.set_xticklabels([])
    if not km:
        ax.set_yticklabels([])


def grid(nsc, ncol=3):
    """Panels in rows of ncol, km labels on the left column and the bottom row only."""
    nrow = -(-nsc // ncol)
    fig, axs = plt.subplots(nrow, ncol, figsize=(2.3 * ncol, 3.9 * nrow), constrained_layout=True)
    axs = axs.ravel()
    for ax in axs[nsc:]:
        ax.set_visible(False)
    for i, ax in enumerate(axs[:nsc]):
        ax.set_xlabel('km' if i >= nsc - ncol else '')
        ax.set_ylabel('km' if i % ncol == 0 else '')
    return fig, axs[:nsc]


def rgb_image(i):
    rgb = np.moveaxis(M['rgb'][i], 0, -1)
    rgb = np.clip(np.nan_to_num(rgb) / 0.20, 0, 1) ** (1 / 1.6)
    return rgb


# 1. true colour of the scenes
nsc = len(M['ids'])
fig, axs = grid(nsc)
for i, ax in enumerate(axs):
    ax.imshow(rgb_image(i), extent=EXT, interpolation='nearest')
    frame(ax, km=(i % 3 == 0), xkm=(i >= nsc - 3))
    ax.set_title(f"{M['times'][i][5:10]}  {M['times'][i][11:]} {M['orbits'][i]}")
fig.savefig(FIG / 's2_tsm_scenes_rgb.png', dpi=200)
plt.close(fig)

# 2. processing of the two overpasses of 10 July
idx = [i for i, t in enumerate(M['times']) if t.startswith('2025-07-10')]
excl = ListedColormap(['#d9d9d9', '#e08214', '#2166ac'])
fig, axs = plt.subplots(len(idx), 5, figsize=(9.6, 3.9 * len(idx)), constrained_layout=True)
for r, i in enumerate(idx):
    red, swir = M['red'][i], M['swir'][i]
    rho_w = red - swir
    common = M['common_' + str(M['orbits'][i])]
    # 0 left out in another scene of the orbit, 1 left out in this scene, 2 used
    cls = np.where(common, 2, np.where(M['ok'][i], 0, 1)).astype(float)
    cls[~lagoon] = np.nan
    panels = [(red, 'B04, 665 nm', 'Greys_r', 0, 0.12),
              (swir, 'B11, 1610 nm', 'Greys_r', 0, 0.12),
              (rho_w, r'$\rho_w$ = B04 $-$ B11', 'Greys_r', 0, 0.06),
              (cls, 'lagoon pixels', excl, 0, 2),
              (np.where(common, M['tsm'][i], np.nan), 'T (mg/l)', 'YlOrBr', 0, 30)]
    for c, (a, title, cmap, lo, hi) in enumerate(panels):
        ax = axs[r, c]
        im = ax.imshow(a, extent=EXT, cmap=cmap, vmin=lo, vmax=hi, interpolation='nearest')
        frame(ax, km=(c == 0))
        ax.set_title(title if r == 0 else '')
        if c == 0:
            ax.set_ylabel(label(i) + '\nkm')
        if c != 3:
            fig.colorbar(im, ax=ax, shrink=0.6, location='bottom', pad=0.02)
        else:
            cb = fig.colorbar(im, ax=ax, shrink=0.6, location='bottom', pad=0.02, ticks=[1 / 3, 1, 5 / 3])
            cb.ax.set_xticklabels(['other\nscene', 'this\nscene', 'used'], fontsize=6)
fig.savefig(FIG / 's2_tsm_processing.png', dpi=200)
plt.close(fig)

# 3. suspended matter of every scene, lagoon pixels valid in the scene
fig, axs = grid(nsc)
for i, ax in enumerate(axs):
    own = lagoon & M['ok'][i]
    ax.imshow(rgb_image(i).mean(axis=-1), extent=EXT, cmap='Greys_r', vmin=0, vmax=1.4, interpolation='nearest')
    im = ax.imshow(np.where(own, M['tsm'][i], np.nan), extent=EXT, cmap='YlOrBr', vmin=0, vmax=30,
                   interpolation='nearest')
    frame(ax, km=(i % 3 == 0), xkm=(i >= nsc - 3))
    p50 = STATS.loc[STATS['id'] == M['ids'][i], 'tsm_own_p50'].iloc[0]
    ax.set_title(f"{M['times'][i][5:10]} {M['orbits'][i]}, p50 {p50:.1f} mg/l")
fig.colorbar(im, ax=axs, shrink=0.4, label='T (mg/l)')
fig.savefig(FIG / 's2_tsm_maps.png', dpi=200)
plt.close(fig)

# 4. satellite against the surface silt of the members
names = {'dflowfm_v04AE_dens_ic3d': ('bare, original parameters', '#999999', '--'),
         '_arm_wm_dep': ('bare, dep', '#E69F00', '-'),
         '_arm_wm_e2p3': ('bare, e2p3', '#56B4E9', '-'),
         '_veg_waves_dm_ic3d': ('canopy, original parameters', '#000000', '--'),
         '_arm_vwm_swandep': ('canopy in FM and SWAN, dep', '#D55E00', '-'),
         '_arm_vwm_e2p3': ('canopy in FM, e2p3', '#0072B2', '-'),
         '_arm_vwm_e2p3_swan': ('canopy in FM and SWAN, e2p3', '#009E73', '-')}
FLOOR = 0.1
fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.6), constrained_layout=True, sharey=True)
for ax, q in zip(axs, ('p50', 'p95')):
    for mem, (lab, col, ls) in names.items():
        d = MODEL[MODEL['member'] == mem].sort_values('overpass')
        if len(d):
            ax.plot(d['overpass'], np.maximum(d[q], FLOOR), ls, color=col, lw=1.5, marker='o', ms=4, label=lab)
    for orb, mk in (('R079', 's'), ('R122', 'D')):
        d = STATS[STATS['orbit'] == orb]
        ax.errorbar(d['datetime'], d[f'tsm_{q}'], fmt=mk, color='#cc79a7', mfc='white', mew=1.5, ms=7,
                    label=f'Sentinel-2, {orb}', zorder=5)
    ax.axvspan(pd.Timestamp('2025-07-07'), pd.Timestamp('2025-07-10'), color='#000000', alpha=0.06, lw=0)
    ax.set_yscale('log'); ax.set_ylim(FLOOR * 0.8, 2e4)
    ax.set_title(f'{q} over the lagoon (mg/l)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.grid(axis='y', color='#dddddd', lw=0.5)
axs[0].set_ylabel('suspended matter, surface (mg/l)')
axs[1].legend(loc='upper left', bbox_to_anchor=(1.02, 1), frameon=False)
fig.savefig(FIG / 's2_tsm_model_comparison.png', dpi=200)
plt.close(fig)
print('figures written')
