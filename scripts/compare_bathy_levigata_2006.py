"""Comparison of the 2026 smoothed lagoon bathymetry with the 2006 survey.

Inputs
------
BATHY_STAGNONE_LEVIGATA_SIGMA30M.tif
    10 m raster in EPSG:32633, elevation negative downward, land coded as
    exactly zero. The file metadata declare a normalized Gaussian filter
    (sigma = 3 cells = 30 m, radius 9 cells) with a coastal taper over 2 to 9
    cells, applied to BATHY_STAGNONE_CORRETTA.tif, and state that the surface
    was not validated against survey points.
bat_stagnone_20m_2006.xyz
    20 m gridded survey of 2006 in UTM zone 33N, depth positive downward,
    land coded as zero. The file carries no CRS. Its coordinates are on the
    ED50 datum (EPSG:23033), since the translation that minimises the misfit
    to the 2026 raster over cells shallower than 3 m, (-55, -195) m, matches
    the ED50 to WGS84 shift at this site, (-66, -187) m, within one 20 m
    cell. bat20m_stgnlg_Adjusted.xyz, the lagoon source of the v05
    topobathymetry, is this survey resampled at 3 m on the same coordinates.
Stagnone_dxy01_15m_net.nc
    v04 mesh, bed level at face centres (bedLevType = 1), WGS84.

Sign convention of every difference is new minus reference in elevation, so
a positive value means the 2026 surface is shallower.

The 2026 raster is sampled at the reference points by bilinear interpolation
weighted by the wet fraction, which keeps the land zeros out of the average.
The 2006 grid is also compared after the same normalized Gaussian (sigma =
30 m), which separates the effect of the smoothing from the change in the
underlying surface.

Outputs go to outputs/bathy_levigata_2026-10/ as three figures and three CSV
tables.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

ROOT = Path(__file__).resolve().parents[1]
NEW_TIF = ROOT / 'data/raw/bathymetry/BATHY_STAGNONE_LEVIGATA_SIGMA30M.tif'
XYZ_2006 = ROOT / 'oldModel/bat_stagnone_20m_2006.xyz'
NET_V04 = ROOT / 'model/dflowfm_v04/Stagnone_dxy01_15m_net.nc'
OUT = ROOT / 'outputs/bathy_levigata_2026-10'

EPSG_2006 = 23033       # ED50 / UTM 33N, see the module docstring
SIGMA_M = 30.0          # filter declared in the raster metadata
WET_FRAC_MIN = 0.5      # a sampled point is wet when half its support is wet
DEPTH_EDGES = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0]
COAST_EDGES = [0.0, 40.0, 100.0, 200.0, 400.0, 5000.0]

# Diverging map with a neutral grey midpoint, blue for deeper and red for shallower.
DIV = LinearSegmentedColormap.from_list(
    'deeper_shallower', ['#1f4e8c', '#7fa8d6', '#d9d9d9', '#e0937a', '#a8321d'])
INK = '#333333'
C_NEW, C_OLD = '#1f4e8c', '#c2571a'


def load_new():
    with rasterio.open(NEW_TIF) as src:
        z = src.read(1).astype('float64')
        valid = z != src.nodata
        wet = valid & (z < 0)
        return z, wet, valid, src.transform, src.bounds


def sample_new(z, wet, valid, transform, x, y):
    """Wet-fraction-weighted bilinear sample of the 2026 raster at (x, y)."""
    col = (np.asarray(x) - transform.c) / transform.a - 0.5
    row = (np.asarray(y) - transform.f) / transform.e - 0.5
    crd = np.vstack([row.ravel(), col.ravel()])
    num = map_coordinates(np.where(wet, z, 0.0), crd, order=1, cval=0.0)
    w = map_coordinates(wet.astype('float64'), crd, order=1, cval=0.0)
    v = map_coordinates(valid.astype('float64'), crd, order=1, cval=0.0)
    out = np.full(w.shape, np.nan)
    ok = w >= WET_FRAC_MIN
    out[ok] = num[ok] / w[ok]
    shp = np.shape(x)
    return out.reshape(shp), w.reshape(shp), (v > 0.99).reshape(shp)


def load_2006():
    d = pd.read_csv(XYZ_2006, sep=r'\s+', header=None, names=['x', 'y', 'z'])
    xs = np.sort(d.x.unique())
    ys = np.sort(d.y.unique())[::-1]
    assert len(d) == xs.size * ys.size, '2006 file is not a full regular grid'
    grid = (d.pivot(index='y', columns='x', values='z')
             .reindex(index=ys, columns=xs).to_numpy())
    wet = grid > 0
    return xs, ys, np.where(wet, -grid, np.nan), wet


def masked_gaussian(z, wet, sigma_cells):
    """Normalized Gaussian restricted to wet cells."""
    num = gaussian_filter(np.where(wet, z, 0.0), sigma_cells, mode='constant')
    den = gaussian_filter(wet.astype('float64'), sigma_cells, mode='constant')
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(wet, num / den, np.nan)


def stats(diff, ref=None, new=None):
    d = diff[np.isfinite(diff)]
    if d.size == 0:
        return dict(n=0)
    out = dict(n=d.size, bias=d.mean(), median=np.median(d), std=d.std(),
               rmse=np.sqrt((d ** 2).mean()), mae=np.abs(d).mean(),
               p05=np.percentile(d, 5), p95=np.percentile(d, 95))
    if ref is not None:
        m = np.isfinite(diff)
        out['r'] = np.corrcoef(ref[m], new[m])[0, 1]
    return out


def class_table(diff, by, edges, label):
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (by >= lo) & (by < hi)
        rows.append({label: f'{lo:g}-{hi:g}', **stats(diff[m])})
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option('display.width', 200)
    pd.set_option('display.float_format', lambda v: f'{v:.3f}')

    z_new, wet_new, valid_new, tf, bnd = load_new()
    xs, ys, z06, wet06 = load_2006()
    dx06 = float(xs[1] - xs[0])
    X, Y = np.meshgrid(xs, ys)
    cell = dx06 * dx06

    print('[extent] 2026 raster  x %.0f-%.0f  y %.0f-%.0f' % (bnd.left, bnd.right, bnd.bottom, bnd.top))
    print('[extent] 2006 survey  x %.0f-%.0f  y %.0f-%.0f (coordinates as stored)' % (xs.min(), xs.max(), ys.min(), ys.max()))
    print('[2026] wet %.2f km2, land(zero) %.2f km2, nodata %d cells' % (
        wet_new.sum() * 1e-4, (valid_new & ~wet_new).sum() * 1e-4, (~valid_new).sum()))

    # ---- horizontal datum of the 2006 file ----------------------------------
    z06_s = masked_gaussian(z06, wet06, SIGMA_M / dx06)
    Xe, Ye = Transformer.from_crs(EPSG_2006, 32633, always_xy=True).transform(X, Y)
    sx, sy = float((Xe - X).mean()), float((Ye - Y).mean())
    print('\n[datum] EPSG:%d to EPSG:32633 moves the 2006 grid by %.1f m E, %.1f m N' % (EPSG_2006, sx, sy))
    rows = []
    for label, xx, yy in [('read as EPSG:32633', X, Y), (f'read as EPSG:{EPSG_2006}', Xe, Ye)]:
        n_, w_, in_ = sample_new(z_new, wet_new, valid_new, tf, xx, yy)
        wn_ = in_ & (w_ >= WET_FRAC_MIN)
        b_ = wn_ & wet06
        rows.append({'georeference of 2006': label, 'mask_mismatch_km2': (in_ & (wn_ != wet06)).sum() * cell * 1e-6,
                     **stats(np.where(b_, n_ - z06, np.nan), z06, n_)})
    t_datum = pd.DataFrame(rows)
    print(t_datum.to_string(index=False))
    t_datum.to_csv(OUT / 'diff_by_georeference.csv', index=False)

    # ---- 2026 sampled on the 2006 grid, 2006 read in its own datum ---------
    X, Y = Xe, Ye
    new06, wfrac, inside = sample_new(z_new, wet_new, valid_new, tf, X, Y)
    wet_new06 = inside & (wfrac >= WET_FRAC_MIN)
    both = inside & wet06 & wet_new06
    diff_raw = np.where(both, new06 - z06, np.nan)
    diff_s = np.where(both, new06 - z06_s, np.nan)

    print('\n[common domain] %.2f km2 of the 2006 grid lies inside the 2026 raster' % (inside.sum() * cell * 1e-6))
    area = pd.DataFrame([
        ('wet in both', both.sum()),
        ('wet 2026, land 2006', (inside & wet_new06 & ~wet06).sum()),
        ('land 2026, wet 2006', (inside & ~wet_new06 & wet06).sum()),
        ('land in both', (inside & ~wet_new06 & ~wet06).sum()),
    ], columns=['class', 'cells'])
    area['km2'] = area.cells * cell * 1e-6
    print(area.to_string(index=False))
    area.to_csv(OUT / 'area_classes.csv', index=False)

    overall = pd.DataFrame([
        {'reference': '2006 as surveyed (20 m)', **stats(diff_raw, z06, new06)},
        {'reference': '2006 after sigma=30 m', **stats(diff_s, z06_s, new06)},
    ])
    print('\n[2026 minus 2006, wet in both] metres')
    print(overall.to_string(index=False))

    depth06 = np.where(both, -z06, np.nan)
    t_depth = class_table(diff_raw, depth06, DEPTH_EDGES, 'depth_2006_m')
    t_depth['bias_vs_smoothed'] = class_table(diff_s, depth06, DEPTH_EDGES, 'd')['bias']
    t_depth['rmse_vs_smoothed'] = class_table(diff_s, depth06, DEPTH_EDGES, 'd')['rmse']
    print('\n[by 2006 depth class]')
    print(t_depth.to_string(index=False))
    t_depth.to_csv(OUT / 'diff_by_depth_class.csv', index=False)

    dist = distance_transform_edt(wet06) * dx06
    t_coast = class_table(diff_raw, np.where(both, dist, np.nan), COAST_EDGES, 'dist_to_2006_shore_m')
    t_coast['bias_vs_smoothed'] = class_table(diff_s, np.where(both, dist, np.nan), COAST_EDGES, 'd')['bias']
    print('\n[by distance to the 2006 shoreline]')
    print(t_coast.to_string(index=False))
    t_coast.to_csv(OUT / 'diff_by_shore_distance.csv', index=False)

    vol06 = -np.nansum(np.where(inside & wet06, z06, 0.0)) * cell
    vol26 = -np.nansum(np.where(wet_new06, new06, 0.0)) * cell
    print('\n[volume below z=0, common domain] 2006 %.2f Mm3, 2026 %.2f Mm3 (%+.1f %%)' % (
        vol06 * 1e-6, vol26 * 1e-6, 100 * (vol26 / vol06 - 1)))
    shallow = both & (depth06 < 3.0)
    print('[cells shallower than 3 m in 2006] mean depth 2006 %.3f m, 2026 %.3f m' % (
        -np.nanmean(z06[shallow]), -np.nanmean(new06[shallow])))

    # ---- 2026 sampled on the v04 mesh faces --------------------------------
    ds = xr.open_dataset(NET_V04)
    fx, fy = Transformer.from_crs(4326, 32633, always_xy=True).transform(
        ds.mesh2d_face_x.values, ds.mesh2d_face_y.values)
    fz = ds.mesh2d_face_z.values
    new_f, wf, in_f = sample_new(z_new, wet_new, valid_new, tf, fx, fy)
    wet_f = in_f & (fz < 0) & np.isfinite(new_f)
    diff_f = np.where(wet_f, new_f - fz, np.nan)
    in06 = (fx >= X.min()) & (fx <= X.max()) & (fy >= Y.min()) & (fy <= Y.max())
    mesh = pd.DataFrame([
        {'faces': 'inside 2026 raster, wet in both', **stats(diff_f, fz, new_f)},
        {'faces': '  within the 2006 footprint', **stats(np.where(in06, diff_f, np.nan))},
        {'faces': '  outside the 2006 footprint', **stats(np.where(~in06, diff_f, np.nan))},
        {'faces': '  v04 depth < 3 m', **stats(np.where(fz > -3, diff_f, np.nan))},
    ])
    print('\n[2026 minus v04 face bed level] metres; %d faces inside the raster, %d wet in v04, %d land in v04 and wet in 2026, %d wet in v04 and land in 2026' % (
        in_f.sum(), (in_f & (fz < 0)).sum(), (in_f & (fz >= 0) & (wf >= WET_FRAC_MIN)).sum(),
        (in_f & (fz < 0) & (wf < WET_FRAC_MIN)).sum()))
    print(mesh.to_string(index=False))
    pd.concat([overall.rename(columns={'reference': 'case'}),
               mesh.rename(columns={'faces': 'case'})]).to_csv(OUT / 'diff_overall.csv', index=False)

    # ---- figures -----------------------------------------------------------
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': '#999999', 'axes.labelcolor': INK,
                         'xtick.color': INK, 'ytick.color': INK, 'axes.titlesize': 10})
    ext06 = [xs.min() - dx06 / 2 + sx, xs.max() + dx06 / 2 + sx,
             ys.min() - dx06 / 2 + sy, ys.max() + dx06 / 2 + sy]
    km = lambda v, p: f'{v / 1000:.0f}'

    fig, axs = plt.subplots(1, 3, figsize=(13, 7.5), sharex=True, sharey=True, constrained_layout=True)
    extn = [bnd.left, bnd.right, bnd.bottom, bnd.top]
    im0 = axs[0].imshow(np.where(wet_new, z_new, np.nan), extent=extn, cmap='Blues_r', vmin=-6, vmax=0)
    axs[0].set_title('2026 smoothed surface (10 m)')
    axs[1].imshow(z06, extent=ext06, cmap='Blues_r', vmin=-6, vmax=0)
    axs[1].set_title('2006 survey (20 m)')
    im2 = axs[2].imshow(diff_raw, extent=ext06, cmap=DIV, vmin=-0.6, vmax=0.6)
    axs[2].set_title('2026 minus 2006')
    for ax in axs:
        ax.set_facecolor('#f2f0eb')
        ax.set_xlim(extn[0], extn[1]); ax.set_ylim(extn[2], extn[3])
        ax.set_aspect('equal')
        ax.xaxis.set_major_formatter(km); ax.yaxis.set_major_formatter(km)
        ax.set_xlabel('Easting UTM 33N (km)')
    axs[0].set_ylabel('Northing UTM 33N (km)')
    fig.colorbar(im0, ax=axs[:2], shrink=0.6, extend='min', label='Bed elevation (m)', location='bottom')
    fig.colorbar(im2, ax=axs[2], shrink=0.9, extend='both', location='bottom',
                 label='Elevation difference (m), positive where 2026 is shallower')
    fig.savefig(OUT / 'fig1_maps.png', dpi=170)
    plt.close(fig)

    fig, axs = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    ax = axs[0, 0]
    bins = np.linspace(-1.5, 1.5, 121)
    ax.hist(diff_raw[np.isfinite(diff_raw)], bins=bins, histtype='step', lw=2, color=C_OLD, label='2006 as surveyed')
    ax.hist(diff_s[np.isfinite(diff_s)], bins=bins, histtype='step', lw=2, color=C_NEW, label='2006 after sigma = 30 m')
    ax.axvline(0, color='#999999', lw=0.8)
    ax.set_xlabel('2026 minus 2006 (m)'); ax.set_ylabel('Cells (20 m)')
    ax.set_title('Distribution of the elevation difference'); ax.legend(frameon=False, title='Reference')

    ax = axs[0, 1]
    m = both & (depth06 < 6)
    hb = ax.hexbin(-z06[m], -new06[m], gridsize=90, bins='log', cmap='Blues', mincnt=1, extent=(0, 6, 0, 6))
    ax.plot([0, 6], [0, 6], color=INK, lw=1)
    ax.set_xlabel('Depth 2006 (m)'); ax.set_ylabel('Depth 2026 (m)')
    ax.set_title('Depth against depth, cells shallower than 6 m'); ax.set_aspect('equal')
    fig.colorbar(hb, ax=ax, label='Cells per bin')

    ax = axs[1, 0]
    xpos = np.arange(len(t_depth))
    ax.bar(xpos - 0.2, t_depth['bias'], 0.38, color=C_OLD, label='2006 as surveyed')
    ax.bar(xpos + 0.2, t_depth['bias_vs_smoothed'], 0.38, color=C_NEW, label='2006 after sigma = 30 m')
    ax.axhline(0, color='#999999', lw=0.8)
    ax.set_xticks(xpos); ax.set_xticklabels(t_depth['depth_2006_m'])
    ax.set_xlabel('Depth class in 2006 (m)'); ax.set_ylabel('Mean of 2026 minus 2006 (m)')
    ax.set_title('Mean difference by depth class'); ax.legend(frameon=False, title='Reference')

    ax = axs[1, 1]
    d06 = np.sort(-z06[inside & wet06]); d26 = np.sort(-new06[wet_new06])
    ax.plot(d06, np.arange(1, d06.size + 1) * cell * 1e-6, color=C_OLD, lw=2, label='2006')
    ax.plot(d26, np.arange(1, d26.size + 1) * cell * 1e-6, color=C_NEW, lw=2, label='2026')
    ax.set_xlim(0, 5); ax.set_ylim(0, None)
    ax.set_xlabel('Depth (m)'); ax.set_ylabel('Area shallower than depth (km$^2$)')
    ax.set_title('Hypsometry on the common domain'); ax.legend(frameon=False)
    for ax in axs.ravel():
        ax.grid(color='#e5e5e5', lw=0.6); ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
    fig.savefig(OUT / 'fig2_statistics.png', dpi=170)
    plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 7), constrained_layout=True,
                            gridspec_kw={'width_ratios': [1, 1.1]})
    ax = axs[0]
    sc = ax.scatter(fx[wet_f], fy[wet_f], c=diff_f[wet_f], s=3, cmap=DIV, vmin=-1, vmax=1, linewidths=0)
    ax.set_facecolor('#f2f0eb'); ax.set_aspect('equal')
    ax.set_xlim(extn[0], extn[1]); ax.set_ylim(extn[2], extn[3])
    ax.xaxis.set_major_formatter(km); ax.yaxis.set_major_formatter(km)
    ax.set_xlabel('Easting UTM 33N (km)'); ax.set_ylabel('Northing UTM 33N (km)')
    ax.set_title('2026 minus v04 bed level at mesh faces')
    fig.colorbar(sc, ax=ax, shrink=0.8, extend='both', location='bottom',
                 label='Elevation difference (m), positive where 2026 is shallower')
    ax = axs[1]
    bins = np.linspace(-3, 3, 121)
    ax.hist(diff_f[wet_f & in06], bins=bins, histtype='step', lw=2, color=C_NEW, label='Within the 2006 footprint')
    ax.hist(diff_f[wet_f & ~in06], bins=bins, histtype='step', lw=2, color=C_OLD, label='Outside the 2006 footprint')
    ax.axvline(0, color='#999999', lw=0.8)
    ax.set_xlabel('2026 minus v04 (m)'); ax.set_ylabel('Mesh faces')
    ax.set_title('Distribution over v04 faces'); ax.legend(frameon=False, title='Faces')
    ax.grid(color='#e5e5e5', lw=0.6); ax.set_axisbelow(True)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    fig.savefig(OUT / 'fig3_v04_mesh.png', dpi=170)
    plt.close(fig)
    print('\n[done] figures and tables in', OUT)


if __name__ == '__main__':
    main()
