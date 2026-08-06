"""Figure 1 (Paper 1): the Stagnone di Marsala study area, three panels.

(a) The full modelled domain: western Sicily, the Egadi archipelago
    (Marettimo, Levanzo, Favignana) and the shelf, with the Marettimo tide
    gauge used for offshore validation and a box giving the extent of (b).
(b) The lagoon in detail: model bathymetry, the two inlets, the four islands,
    the in-situ station network and the drifter release positions.
(c) A small locator over panel (a), placing the domain within Italy.

Colour decisions follow the project data-viz rules:
  - Depth is a MAGNITUDE, so it gets a sequential ramp running light shallow to
    dark deep. The ramp is cmocean 'deep', which is multi-hue but perceptually
    uniform: what the "never a rainbow" rule actually forbids is non-monotonic
    lightness, which manufactures banding that the data does not contain. jet
    and turbo were both measured and fail that test; cmocean deep, viridis and
    cividis pass. Panels (a) and (b) span very different depth ranges and
    therefore carry one colourbar each.
  - Station classes are IDENTITY, so they get categorical hues assigned in
    fixed order and validated all-pairs (a map is a scatter-like form, where
    the validated cap is three slots): orange #eb6834, aqua #1baf7a,
    violet #4a3aa7. Verified with the palette validator, worst all-pairs CVD
    dE 9.2 and normal-vision dE 27.6, both clear.
  - Blue is deliberately absent from the markers because the bathymetry ramp
    owns that hue.
  - Identity is never colour alone: each class also has its own marker shape,
    and the aqua class carries a direct label (the validator flags aqua below
    3:1 contrast on a light surface, which the label relieves).

Land in panel (a) comes from the mesh itself: the Egadi islands are inside the
domain and carry positive bed levels, so cells with z > 0 are painted as land.
sicily2.ldb only starts at 12.424 E and does not reach the archipelago.

Island naming: Mozia is confirmed by Mozia.pli in the model directory. The
sicily2.ldb blocks carry opaque names (F001-F005), so the remaining three are
identified geographically: F003 is the elongated western barrier (Isola
Grande), F002 sits north of Mozia (Santa Maria) and the small LandBoundary01
block sits south of it (Scuola). Worth a second pair of eyes before submission.

Output: manuscript/figures/study_area_stagnone.{png,pdf}
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, Normalize, PowerNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.tri import Triangulation

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'model' / 'dflowfm_v04AE_vr'
PROC = ROOT / 'data' / 'processed'
GEO = PROC / 'geo' / 'mediterranean_context.geojson'
OUT = ROOT / 'manuscript' / 'figures'
OUT.mkdir(parents=True, exist_ok=True)

# --- palette -----------------------------------------------------------------
SURFACE = '#ffffff'
LAND = '#e7e6e1'
LAND_EDGE = '#b9b7ae'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
BOX = '#c0392b'

C_WL = '#eb6834'      # categorical slot: water-level stations
C_MET = '#1baf7a'     # categorical slot: meteorological station
C_DRIFT = '#4a3aa7'   # categorical slot: drifter releases

# cmocean 'deep' is the oceanographic standard for bathymetry. It is multi-hue
# (pale green through teal and blue to deep navy) but its lightness is
# monotonic, so it does not manufacture the false boundaries that jet and turbo
# produce. Both were checked and are non-monotonic in lightness; neither is used.
try:
    import cmocean
    DEPTH_CMAP = cmocean.cm.deep
except ImportError:                      # keep the figure buildable without it
    DEPTH_CMAP = plt.get_cmap('YlGnBu')

LAGOON_MAX = 3.5      # m, panel (b): the lagoon range
DOMAIN_MAX = 730.0    # m, panel (a): full range; median is 7 m, so the ramp is
DOMAIN_GAMMA = 0.5    # power-normalised to keep resolution on the shelf

# --- geography ---------------------------------------------------------------
DOMAIN = dict(lon=(11.950, 12.570), lat=(37.690, 38.072))
BBOX = dict(lon=(12.418, 12.492), lat=(37.810, 37.914))
ASPECT = 1.0 / np.cos(np.radians(37.87))

STATIONS_WL = {          # from Stagnone_dxy01_15m_obs.xyn
    'BN': (12.457240, 37.905274),
    'AE': (12.451652, 37.891785),
    'BS': (12.449667, 37.842221),
}
STATION_MET = {'Mulino': (12.482, 37.868)}   # scripts/diagnose_d7_station_blame.py
MARETTIMO = (12.0753, 37.9747)               # offshore validation location

DOMAIN_LABELS = {        # text position -> anchor
    'Marettimo': ((12.010, 37.918), (12.062, 37.960)),
    'Levanzo': ((12.268, 38.040), (12.336, 38.014)),
    'Favignana': ((12.216, 37.898), (12.320, 37.925)),
    'Trapani': ((12.512, 38.040), (12.494, 38.020)),
}

ISLANDS = {
    'Isola Grande': ((12.4370, 37.8700), (12.4400, 37.8700)),
    'Santa Maria': ((12.4655, 37.8860), (12.4600, 37.8835)),
    'Mozia': ((12.4695, 37.8672), (12.4680, 37.8672)),
    'Scuola': ((12.4520, 37.8600), (12.4567, 37.8628)),
}
INLETS = {
    'Bocca Nord': ((12.4655, 37.9010), (12.4570, 37.9045)),
    'Bocca Sud': ((12.4300, 37.8390), (12.4455, 37.8400)),
}


def parse_ldb(path):
    """Delft3D land-boundary file to a list of (N, 2) arrays."""
    polys = []
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith('*')]
    i = 0
    while i < len(lines):
        i += 1                       # block name
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


def load_mesh():
    ds = xr.open_dataset(MODEL / 'Stagnone_dxy01_15m_net.nc')
    x = ds.mesh2d_node_x.values
    y = ds.mesh2d_node_y.values
    z = ds.mesh2d_node_z.values
    faces = ds.mesh2d_face_nodes.values
    ds.close()
    tris = []
    for f in faces:
        idx = [int(v) - 1 for v in f if np.isfinite(v) and v > 0]
        if len(idx) >= 3:
            tris.append(idx[:3])
            if len(idx) == 4:
                tris.append([idx[0], idx[2], idx[3]])
    return x, y, z, np.asarray(tris)


def draw_bathy(ax, x, y, z, tris, norm):
    """Sequential depth ramp over every wet cell, under the given norm."""
    depth_raw = np.where(z < 0, -z, np.nan)
    tri_wet = np.all((~np.isnan(depth_raw))[tris], axis=1)
    tri = Triangulation(x, y, tris)
    tri.set_mask(~tri_wet)
    return ax.tripcolor(tri, np.nan_to_num(depth_raw, nan=0.0), cmap=DEPTH_CMAP,
                        norm=norm, shading='gouraud', zorder=2, rasterized=True)


def leader(ax, txt, tpos, apos, **kw):
    if not np.allclose(tpos, apos):
        ax.plot([tpos[0], apos[0]], [tpos[1], apos[1]], '-', color=MUTED,
                lw=0.7, zorder=6)
    ax.text(*tpos, txt, zorder=7, **kw)


def scale_bar(ax, length_km, fx=0.045, fy=0.032, fs=7.5):
    lon0, lon1 = ax.get_xlim()
    lat0, lat1 = ax.get_ylim()
    deg = length_km / (111.0 * np.cos(np.radians(np.mean([lat0, lat1]))))
    x0 = lon0 + fx * (lon1 - lon0)
    y0 = lat0 + fy * (lat1 - lat0)
    ax.plot([x0, x0 + deg], [y0, y0], '-', color=INK, lw=2.2, zorder=8,
            solid_capstyle='butt')
    ax.text(x0 + deg / 2, y0 + 0.012 * (lat1 - lat0), f'{length_km:.0f} km',
            ha='center', va='bottom', fontsize=fs, color=INK, zorder=8)


def north_arrow(ax, fx=0.072, fy=0.072):
    lon0, lon1 = ax.get_xlim()
    lat0, lat1 = ax.get_ylim()
    x = lon0 + fx * (lon1 - lon0)
    y = lat0 + fy * (lat1 - lat0)
    ax.annotate('', xy=(x, y + 0.055 * (lat1 - lat0)), xytext=(x, y),
                arrowprops=dict(arrowstyle='-|>', color=INK, lw=1.4), zorder=8)
    ax.text(x, y + 0.065 * (lat1 - lat0), 'N', ha='center', va='bottom',
            fontsize=8.5, color=INK, fontweight='bold', zorder=8)


def style(ax):
    ax.set_aspect(ASPECT)
    ax.tick_params(colors=MUTED, labelsize=7.5)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color(LAND_EDGE)


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    x, y, z, tris = load_mesh()
    lag_polys = parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')
    sic_polys = parse_ldb(MODEL / 'sicily2.ldb')
    releases = pd.read_csv(PROC / 'drifter_releases_Jul2025.csv', parse_dates=['t0'])
    print(f'Mesh {len(x)} nodes / {len(tris)} triangles | '
          f'{len(releases)} releases over {releases["deploy"].nunique()} deploys')

    fig = plt.figure(figsize=(9.8, 6.4), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.25, 1.0], wspace=0.06)
    ax_d = fig.add_subplot(gs[0, 0])
    ax_l = fig.add_subplot(gs[0, 1])
    for a in (ax_d, ax_l):
        a.set_facecolor(SURFACE)

    # ---------------- panel (a): full model domain --------------------------
    tpc_d = draw_bathy(ax_d, x, y, z, tris,
                       PowerNorm(gamma=DOMAIN_GAMMA, vmin=0, vmax=DOMAIN_MAX))
    # Land from the mesh: the Egadi islands lie inside the domain and are not
    # in sicily2.ldb, which begins at 12.424 E.
    dryland = Triangulation(x, y, tris)
    dryland.set_mask(~np.all((z >= 0)[tris], axis=1))
    ax_d.tripcolor(dryland, np.ones_like(x), cmap=ListedColormap([LAND]),
                   shading='gouraud', zorder=3, rasterized=True)
    ax_d.tricontour(Triangulation(x, y, tris), (z >= 0).astype(float),
                    levels=[0.5], colors=[LAND_EDGE], linewidths=0.5, zorder=4)
    for poly in sic_polys:
        ax_d.fill(poly[:, 0], poly[:, 1], facecolor=LAND, edgecolor=LAND_EDGE,
                  lw=0.4, zorder=4)

    ax_d.scatter(*MARETTIMO, marker='s', s=52, facecolor=INK, edgecolor='white',
                 linewidths=1.0, zorder=8)
    for name, (tpos, apos) in DOMAIN_LABELS.items():
        leader(ax_d, name, tpos, apos, fontsize=7.5, style='italic', color=INK,
               ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.16', fc=SURFACE, ec='none',
                         alpha=0.75))

    ax_d.add_patch(Rectangle((BBOX['lon'][0], BBOX['lat'][0]),
                             np.diff(BBOX['lon'])[0], np.diff(BBOX['lat'])[0],
                             facecolor='none', edgecolor=BOX, lw=1.5, zorder=9))
    ax_d.text(BBOX['lon'][1] + 0.010, np.mean(BBOX['lat']), '(b)', color=BOX,
              fontsize=9, fontweight='bold', ha='left', va='center', zorder=9)

    ax_d.set_xlim(*DOMAIN['lon'])
    ax_d.set_ylim(*DOMAIN['lat'])
    style(ax_d)
    ax_d.set_xlabel('Longitude ($^{\\circ}$E)', color=MUTED, fontsize=8.5)
    ax_d.set_ylabel('Latitude ($^{\\circ}$N)', color=MUTED, fontsize=8.5)
    scale_bar(ax_d, 20, fx=0.400, fy=0.040)
    north_arrow(ax_d, fx=0.055, fy=0.845)
    ax_d.set_title('(a) Model domain', loc='left', fontsize=10, color=INK, pad=6)

    cb_d = fig.colorbar(tpc_d, ax=ax_d, orientation='horizontal', fraction=0.05,
                        pad=0.11, aspect=34,
                        ticks=[0, 10, 50, 100, 200, 400, 730])
    cb_d.set_label('Depth (m)', fontsize=8, color=MUTED)
    cb_d.ax.tick_params(labelsize=7, colors=MUTED)
    cb_d.outline.set_edgecolor(LAND_EDGE)

    # ---------------- panel (c): Italy locator, over panel (a) --------------
    axi = ax_d.inset_axes([0.022, 0.035, 0.315, 0.355])
    axi.set_facecolor('#dce6ee')
    gj = json.load(open(GEO, encoding='utf-8'))

    def draw_geom(g):
        """Fill Polygon and MultiPolygon rings; skip anything else.

        The GeometryCollection features mix in LineStrings, whose coordinates
        are one nesting level shallower and would be iterated as floats.
        """
        t = g.get('type')
        if t == 'GeometryCollection':
            for sub in g.get('geometries', []):
                draw_geom(sub)
            return
        if t == 'Polygon':
            polys = [g['coordinates']]
        elif t == 'MultiPolygon':
            polys = g['coordinates']
        else:
            return
        for poly in polys:
            for ring in poly:
                a = np.asarray(ring, dtype=float)
                if a.ndim == 2 and a.shape[0] > 2:
                    axi.fill(a[:, 0], a[:, 1], facecolor=LAND,
                             edgecolor=LAND_EDGE, lw=0.25, zorder=2)
    for feat in gj['features']:
        draw_geom(feat['geometry'])
    axi.add_patch(Rectangle((DOMAIN['lon'][0] - 0.45, DOMAIN['lat'][0] - 0.45),
                            np.diff(DOMAIN['lon'])[0] + 0.9,
                            np.diff(DOMAIN['lat'])[0] + 0.9,
                            facecolor='none', edgecolor=BOX, lw=1.3, zorder=6))
    axi.set_xlim(5.8, 19.2)
    axi.set_ylim(35.6, 47.4)
    axi.set_aspect(1.0 / np.cos(np.radians(41.5)))
    axi.set_xticks([])
    axi.set_yticks([])
    for sp in axi.spines.values():
        sp.set_edgecolor('#7a7a7a')
        sp.set_linewidth(0.9)
    axi.set_title('(c)', loc='left', fontsize=8, color=INK, pad=2)

    # ---------------- panel (b): the lagoon ---------------------------------
    tpc_l = draw_bathy(ax_l, x, y, z, tris, Normalize(vmin=0, vmax=LAGOON_MAX))
    for poly in sic_polys + lag_polys:
        ax_l.fill(poly[:, 0], poly[:, 1], facecolor=LAND, edgecolor=LAND_EDGE,
                  lw=0.5, zorder=3)

    for name, (tpos, apos) in ISLANDS.items():
        leader(ax_l, name, tpos, apos, fontsize=7, style='italic', color=INK,
               ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.14', fc=SURFACE, ec='none',
                         alpha=0.75))
    for name, (tpos, apos) in INLETS.items():
        leader(ax_l, name, tpos, apos, fontsize=7.5, color=INK, ha='center',
               va='center', fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.16', fc=SURFACE, ec='none',
                         alpha=0.8))

    ax_l.scatter(releases['lon0'], releases['lat0'], marker='D', s=22,
                 facecolor=C_DRIFT, edgecolor='white', linewidths=0.6, zorder=5)

    WL_OFF = {'BN': (-0.0050, 0.0012, 'right'),
              'AE': (-0.0048, 0.0014, 'right'),
              'BS': (0.0048, 0.0012, 'left')}
    for name, (sx, sy) in STATIONS_WL.items():
        dx, dy, ha = WL_OFF[name]
        ax_l.scatter(sx, sy, marker='o', s=90, facecolor=C_WL, edgecolor='white',
                     linewidths=1.3, zorder=8)
        ax_l.text(sx + dx, sy + dy, name, fontsize=8.5, fontweight='bold',
                  color=INK, ha=ha, va='center', zorder=9,
                  bbox=dict(boxstyle='round,pad=0.13', fc=SURFACE, ec='none',
                            alpha=0.8))
    for name, (sx, sy) in STATION_MET.items():
        ax_l.scatter(sx, sy, marker='^', s=105, facecolor=C_MET,
                     edgecolor='white', linewidths=1.3, zorder=8)
        ax_l.text(sx, sy - 0.0030, name, fontsize=8.5, fontweight='bold',
                  color=INK, ha='center', va='top', zorder=9,
                  bbox=dict(boxstyle='round,pad=0.13', fc=SURFACE, ec='none',
                            alpha=0.8))

    ax_l.set_xlim(*BBOX['lon'])
    ax_l.set_ylim(*BBOX['lat'])
    style(ax_l)
    ax_l.set_xlabel('Longitude ($^{\\circ}$E)', color=MUTED, fontsize=8.5)
    ax_l.yaxis.set_label_position('right')
    ax_l.yaxis.tick_right()
    ax_l.set_ylabel('Latitude ($^{\\circ}$N)', color=MUTED, fontsize=8.5)
    scale_bar(ax_l, 2, fx=0.055, fy=0.028, fs=7)
    ax_l.set_title('(b) Stagnone di Marsala', loc='left', fontsize=10,
                   color=INK, pad=6)
    for sp in ax_l.spines.values():
        sp.set_visible(True)
        sp.set_edgecolor(BOX)
        sp.set_linewidth(1.3)

    cb_l = fig.colorbar(tpc_l, ax=ax_l, orientation='horizontal', fraction=0.05,
                        pad=0.11, extend='max', aspect=15)
    cb_l.set_label('Depth (m)', fontsize=8, color=MUTED)
    cb_l.ax.tick_params(labelsize=7, colors=MUTED)
    cb_l.outline.set_edgecolor(LAND_EDGE)

    handles = [
        Line2D([0], [0], marker='o', ls='', mfc=C_WL, mec='white', ms=8,
               label='Water level station'),
        Line2D([0], [0], marker='^', ls='', mfc=C_MET, mec='white', ms=8,
               label='Meteorological station'),
        Line2D([0], [0], marker='D', ls='', mfc=C_DRIFT, mec='white', ms=5.5,
               label='Drifter release'),
        Line2D([0], [0], marker='s', ls='', mfc=INK, mec='white', ms=7,
               label='Marettimo tide gauge'),
    ]
    fig.legend(handles=handles, loc='lower center', ncol=4, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, 0.0))

    for ext in ('png', 'pdf'):
        p = OUT / f'study_area_stagnone.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
