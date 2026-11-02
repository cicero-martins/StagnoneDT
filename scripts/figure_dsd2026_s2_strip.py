"""Three Sentinel-2 maps of suspended matter for the bed-mobility slide of the
Delft3D User Days deck.

The scenes are those of orbit R079 (no sun glint) before, at the start and at
the end of the drifter window, over the lagoon pixels valid in each scene, with
the median and the 95th percentile of the scene in the title. Reads the maps of
s2_suspended_matter_lagoon.py and the statistics in data/processed/s2_tsm_july2025.csv.

Usage:  python figure_dsd2026_s2_strip.py
Writes: docs/dsd2026/assets/s2_tsm_strip.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
M = np.load(ROOT / 'data' / 'raw' / 'satellite' / 's2_cogs_july2025' / 's2_tsm_maps.npz')
STATS = pd.read_csv(ROOT / 'data' / 'processed' / 's2_tsm_july2025.csv')
OUT = ROOT / 'docs' / 'dsd2026' / 'assets' / 's2_tsm_strip.png'
SCENES = [('2025-06-30', '30 June'), ('2025-07-07', '7 July'), ('2025-07-10', '10 July')]
NAVY, GREY = '#0D2137', '#334555'
CROP = (1.4, 6.4, 0.9, 12.4)   # km from the south-west corner of the window, the lagoon only

plt.rcParams.update({'font.family': 'Calibri', 'font.size': 9})
w, s, e, n = M['extent']
EXT = [0, (e - w) / 1e3, 0, (n - s) / 1e3]
lagoon = M['lagoon']

fig, axs = plt.subplots(1, 3, figsize=(5.23, 3.45), dpi=300, constrained_layout=True)
for ax, (day, lab) in zip(axs, SCENES):
    i = [k for k, t in enumerate(M['times']) if t.startswith(day) and M['orbits'][k] == 'R079'][0]
    rgb = np.clip(np.nan_to_num(np.moveaxis(M['rgb'][i], 0, -1)) / 0.20, 0, 1) ** (1 / 1.6)
    ax.imshow(rgb.mean(axis=-1), extent=EXT, cmap='Greys_r', vmin=0, vmax=1.4, interpolation='nearest')
    im = ax.imshow(np.where(lagoon & M['ok'][i], M['tsm'][i], np.nan), extent=EXT, cmap='YlOrBr',
                   vmin=0, vmax=30, interpolation='nearest')
    ax.contour(np.flipud(lagoon), levels=[0.5], colors=NAVY, linewidths=0.3, extent=EXT)
    ax.set_xlim(CROP[:2]); ax.set_ylim(CROP[2:])
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color('#C9D3DD')
    r = STATS.loc[STATS['id'] == M['ids'][i]].iloc[0]
    ax.set_title(f"{lab}\nmedian {r['tsm_own_p50']:.1f}, p95 {r['tsm_own_p95']:.0f}", color=GREY,
                 fontsize=8.5, linespacing=1.3)
cb = fig.colorbar(im, ax=axs, shrink=0.75, aspect=25, pad=0.02)
cb.set_label('mg/l', color=GREY)
cb.outline.set_visible(False)
cb.ax.tick_params(colors=GREY, labelsize=8)
fig.suptitle('Sentinel-2, suspended matter observed in the lagoon', color=NAVY, fontsize=10,
             fontweight='bold', x=0.02, ha='left')
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=300, facecolor='white')
print('->', OUT)
