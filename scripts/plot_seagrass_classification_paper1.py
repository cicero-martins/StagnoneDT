"""Figure: the seagrass map, from imagery to the classes the model actually uses.

Section 3.4 describes the roughness field in words. It is one of the two
treatments the paper attributes an effect to, so it is worth showing. The point
of the figure is the transfer, not the remote sensing: panel (c) is what D-Flow
FM reads, which is not the classified raster but the trachytope link file built
from it with a 20 m search radius, area-weighted where a link straddles more
than one class.

  (a) PlanetScope SuperDove August 2023 median composite, true colour
  (b) the random-forest classification, water only
  (c) the dominant trachytope class per flow link, from the .arl actually used

The six RF classes collapse to the four trachytope classes as in
build_trachytope_arl.py: Cymodocea and Cymodocea+Caulerpa to one canopy class,
the three Posidonia classes to the other, unvegetated to sand, reef plateau to
rock. Land is masked out of (b) because the classifier was trained on submerged
targets and its labels over land carry no meaning.

Output: figures/seagrass_classification.{png,pdf}
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model' / 'dflowfm_v04AE_vr'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

CLASS_TIF = PROC / 'planet2023_rf_v3' / 'classified_seagrass_aug2023_v3.tif'
COMP_TIF = PROC / 'planet2023_rf' / 'composite_aug2023.tif'
ARL = MODEL / 'stagnone_trachytopes_v3.arl'
LDB = ROOT / 'model' / 'dflowfm_v04AE' / 'Stagnone_dxy01_15m.ldb'

# lagoon window, WGS84. The eastern edge must clear the mainland shoreline:
# cropping at 12.478 cut the eastern margin of the lagoon out of the frame.
BBOX = (12.424, 37.812, 12.489, 37.914)
LON_TICKS = [12.44, 12.46, 12.48]
LAT_TICKS = [37.83, 37.85, 37.87, 37.89, 37.91]

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
LANDC = '#efece6'
LAND_EDGE = '#c9c7c1'

# Four substrate classes, sequential within the two canopy types so the
# ordering sand -> Cymodocea -> Posidonia reads as increasing canopy, with rock
# held apart as a non-vegetated hard substrate.
CLASSES = [(1, 'Bare sand', '#e3d3a8'),
           (2, '\\emph{Cymodocea}', '#7fc9a0'),
           (3, '\\emph{Posidonia}', '#1b7a52'),
           (4, 'Rock', '#9d9a94')]
LABELS = ['Bare sand', 'Cymodocea nodosa', 'Posidonia oceanica', 'Rock']
COLORS = [c for _, _, c in CLASSES]

# RF v3 class -> trachytope class, as in build_trachytope_arl.py
RF_TO_TRT = {0: 1, 1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 7: 4}


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


def read_window(path, bands):
    """Read a WGS84 bbox out of a UTM raster, returning array + WGS84 extent."""
    with rasterio.open(path) as src:
        l, b, r, t = transform_bounds('EPSG:4326', src.crs, *BBOX)
        win = from_bounds(l, b, r, t, src.transform)
        a = src.read(bands, window=win)
        wl, wb, wr, wt = rasterio.windows.bounds(win, src.transform)
        ext = transform_bounds(src.crs, 'EPSG:4326', wl, wb, wr, wt)
    return a, (ext[0], ext[2], ext[1], ext[3])


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    rgb, ext = read_window(COMP_TIF, [6, 4, 2])  # SuperDove red, green, blue
    rgb = rgb.astype(float)
    lo, hi = np.nanpercentile(rgb, [2, 98])
    rgb = np.clip((rgb - lo) / (hi - lo), 0, 1).transpose(1, 2, 0)

    cls, ext_c = read_window(CLASS_TIF, [1])
    cls = cls[0]
    trt = np.full(cls.shape, np.nan)
    for rf, t in RF_TO_TRT.items():
        trt[cls == rf] = t

    arl = np.loadtxt(ARL, comments='#')
    lon, lat, tno, frac = arl[:, 0], arl[:, 1], arl[:, 3], arl[:, 4]
    sel = ((lon >= BBOX[0]) & (lon <= BBOX[2]) &
           (lat >= BBOX[1]) & (lat <= BBOX[3]))
    lon, lat, tno, frac = lon[sel], lat[sel], tno[sel], frac[sel]
    # a link may carry several classes; keep the one with the largest fraction
    order = np.lexsort((frac, lat, lon))
    lon, lat, tno = lon[order], lat[order], tno[order]
    keep = np.ones(len(lon), bool)
    keep[:-1] = (lon[:-1] != lon[1:]) | (lat[:-1] != lat[1:])

    land = parse_ldb(LDB)
    cmap = ListedColormap(COLORS)
    norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], cmap.N)

    fig, axes = plt.subplots(1, 3, figsize=(9.2, 7.6), dpi=300)
    fig.patch.set_facecolor(SURFACE)

    axes[0].imshow(rgb, extent=ext, origin='upper')
    axes[1].imshow(trt, extent=ext_c, origin='upper', cmap=cmap, norm=norm,
                   interpolation='nearest')
    axes[2].scatter(lon[keep], lat[keep], c=tno[keep], cmap=cmap, norm=norm,
                    s=3.2, marker='s', linewidths=0)

    for p in land:
        axes[1].fill(p[:, 0], p[:, 1], color=LANDC, ec='none', zorder=3)
        axes[2].fill(p[:, 0], p[:, 1], color=LANDC, ec=LAND_EDGE, lw=0.4,
                     zorder=0)

    titles = ['(a) PlanetScope, Aug 2023',
              '(b) Random-forest classification',
              '(c) Trachytope class per link']
    for i, (ax, t) in enumerate(zip(axes, titles)):
        ax.set_xlim(BBOX[0], BBOX[2])
        ax.set_ylim(BBOX[1], BBOX[3])
        ax.set_aspect(1.0 / np.cos(np.radians(37.86)))
        ax.set_title(t, loc='left', fontsize=9.5, color=INK, pad=6)
        ax.set_xticks(LON_TICKS)
        ax.set_xticklabels([f'{v:.2f}$^\\circ$E' for v in LON_TICKS],
                           fontsize=7.5)
        ax.set_yticks(LAT_TICKS)
        ax.set_yticklabels([f'{v:.2f}$^\\circ$N' for v in LAT_TICKS]
                           if i == 0 else [], fontsize=7.5)
        ax.tick_params(colors=MUTED, length=3, width=0.6)
        ax.grid(color='#ffffff', lw=0.4, alpha=0.45, zorder=4)
        ax.set_axisbelow(False)
        ax.set_facecolor(SURFACE)
        for sp in ax.spines.values():
            sp.set_color(LAND_EDGE)

    # one scale bar, on panel (a); all three panels share the extent
    ax = axes[0]
    km = 2.0
    dlon = km * 1000.0 / (111320.0 * np.cos(np.radians(37.86)))
    x0 = BBOX[0] + 0.055 * (BBOX[2] - BBOX[0])
    y0 = BBOX[1] + 0.035 * (BBOX[3] - BBOX[1])
    ax.plot([x0, x0 + dlon], [y0, y0], '-', color='white', lw=3.2, zorder=9,
            solid_capstyle='butt')
    ax.text(x0 + dlon / 2, y0 + 0.0016, f'{km:.0f} km', fontsize=7.5,
            color='white', ha='center', va='bottom', zorder=9)

    handles = [Patch(fc=c, ec='none', label=l) for c, l in zip(COLORS, LABELS)]
    fig.legend(handles=handles, loc='lower center', ncol=4, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, 0.005))

    fig.tight_layout(rect=(0, 0.045, 1, 1))
    for e in ('png', 'pdf'):
        p = FIG / f'seagrass_classification.{e}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)

    n = keep.sum()
    print(f'\n{n} links in the lagoon window')
    for t, lab in zip([1, 2, 3, 4], LABELS):
        k = (tno[keep] == t).sum()
        print(f'  {lab:22s} {k:6d}  {100 * k / n:5.1f}%')


if __name__ == '__main__':
    main()
