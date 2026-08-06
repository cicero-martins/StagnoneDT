"""Is the bed change under distributed roughness different in KIND from the bed
change under uniform roughness?

The drifter ensemble showed an interaction: neither morphodynamics nor
distributed roughness improves Lagrangian transport on its own, but together
they do. The magnitudes of bed change are nearly identical between the two
morphodynamic members (median -0.024 m for bl against -0.020 m for vr), so if
the interaction is real it has to live in the spatial pattern rather than in
how much sediment moves.

This script tests that directly:

  (a) bed level change with uniform roughness (bl)
  (b) bed level change with distributed roughness (vr)
  (c) the difference between them
  plus two quantitative summaries printed to stdout:
      - concentration: what share of the total |dz| sits in the busiest 5% of
        cells. Higher means the change is focused rather than spread out.
      - inside against outside the seagrass canopy, which is where the
        mechanism predicts a difference if canopy drag suppresses erosion.

Bed change is a DIVERGING quantity around zero, so it gets a diverging map
(cmocean balance) with symmetric limits and a neutral midpoint, never a
sequential or rainbow ramp. Limits are clipped at the 99th percentile of |dz|
because a single cell in the vr field reaches +67 m and would otherwise set the
scale for everything.

Canopy mask comes from roughness_satellite.xyz, where Manning 0.020 is bare bed
and the higher classes are vegetated. That file is the same RF classification
the trachytopes were built from, used here only as a diagnostic mask.

Output: figures/dmorph_pattern_bl_vs_vr.{png,pdf}
"""
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree

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

try:
    import cmocean
    DIV = cmocean.cm.balance
except ImportError:
    DIV = plt.get_cmap('RdBu_r')

BBOX = dict(lon=(12.418, 12.492), lat=(37.815, 37.914))
ASPECT = 1.0 / np.cos(np.radians(37.87))


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


def concentration(dz, frac=0.05):
    """Share of total |dz| held by the busiest `frac` of cells."""
    a = np.abs(dz[np.isfinite(dz)])
    if a.sum() == 0:
        return np.nan
    k = max(1, int(round(frac * len(a))))
    return np.sort(a)[::-1][:k].sum() / a.sum()


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    zb = np.load(PROC / 'dmorph_delta_bl_server.npz')
    zv = np.load(PROC / 'dmorph_delta_vr.npz')
    assert np.allclose(zb['face_x'], zv['face_x']), 'face order differs'
    fx, fy = zb['face_x'], zb['face_y']
    dz_bl, dz_vr = zb['delta_bl'], zv['delta_bl']

    inbox = ((fx >= BBOX['lon'][0]) & (fx <= BBOX['lon'][1]) &
             (fy >= BBOX['lat'][0]) & (fy <= BBOX['lat'][1]))
    print(f'{inbox.sum()} faces inside the lagoon frame')

    # canopy mask, nearest roughness sample within 60 m
    rough = np.loadtxt(MODEL / 'roughness_satellite.xyz')
    tree = cKDTree(rough[:, :2])
    dist, idx = tree.query(np.column_stack([fx, fy]))
    veg = (rough[idx, 2] > 0.021) & (dist < 60 / 111000.0 / np.cos(np.radians(37.87)))
    print(f'{veg[inbox].sum()} of {inbox.sum()} lagoon faces classed as canopy')

    print('\n=== concentration of |dz| in the busiest 5% of lagoon cells ===')
    for lab, dz in [('uniform roughness (bl)', dz_bl), ('distributed (vr)', dz_vr)]:
        print(f'  {lab:24s} {concentration(dz[inbox]) * 100:5.1f}%')

    print('\n=== mean dz inside vs outside canopy, lagoon only (m) ===')
    print(f"{'member':24s} {'canopy':>9s} {'bare':>9s} {'ratio':>7s}")
    for lab, dz in [('uniform roughness (bl)', dz_bl), ('distributed (vr)', dz_vr)]:
        a = np.abs(dz[inbox & veg]).mean()
        b = np.abs(dz[inbox & ~veg]).mean()
        print(f'  {lab:22s} {a:9.4f} {b:9.4f} {a / b:7.2f}')

    lim = np.nanpercentile(np.abs(np.concatenate([dz_bl[inbox], dz_vr[inbox]])), 99)
    lim = float(np.round(lim, 2))
    print(f'\nColour limits: +/- {lim} m (99th percentile of |dz|)')

    polys = parse_ldb(MODEL / 'sicily2.ldb') + parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')

    fig, axes = plt.subplots(1, 3, figsize=(10.4, 5.6), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    fields = [('(a) Uniform roughness', dz_bl, lim),
              ('(b) Distributed roughness', dz_vr, lim),
              ('(c) Difference (b $-$ a)', dz_vr - dz_bl, lim)]

    for ax, (title, dz, vlim) in zip(axes, fields):
        for poly in polys:
            ax.fill(poly[:, 0], poly[:, 1], facecolor=LAND, edgecolor=LAND_EDGE,
                    lw=0.4, zorder=1)
        sc = ax.scatter(fx[inbox], fy[inbox], c=np.clip(dz[inbox], -vlim, vlim),
                        s=1.6, cmap=DIV, vmin=-vlim, vmax=vlim, zorder=2,
                        rasterized=True, linewidths=0)
        ax.set_xlim(*BBOX['lon'])
        ax.set_ylim(*BBOX['lat'])
        ax.set_aspect(ASPECT)
        ax.set_title(title, loc='left', fontsize=9.5, color=INK, pad=6)
        ax.tick_params(colors=MUTED, labelsize=7)
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(30)
            lbl.set_ha('right')
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color('#c9c7c1')

    for ax in axes[1:]:
        ax.set_yticklabels([])

    cb = fig.colorbar(sc, ax=axes, orientation='horizontal', fraction=0.045,
                      pad=0.12, aspect=45, extend='both')
    cb.set_label('Bed level change over nine days (m); '
                 'negative is erosion', fontsize=8.5, color=MUTED)
    cb.ax.tick_params(labelsize=7.5, colors=MUTED)
    cb.outline.set_edgecolor(LAND_EDGE)

    for ext in ('png', 'pdf'):
        p = FIG / f'dmorph_pattern_bl_vs_vr.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
