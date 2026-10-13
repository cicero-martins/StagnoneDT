"""Screening of the effect of the 2026 bathymetry on the v04 family of models.

Every member of the Paper 1 ensemble runs on the v04 mesh
(Stagnone_dxy01_15m_net.nc, bed level at face centres), so the bed-level
change that the 2026 raster would impose is evaluated once on that mesh. The
screening is geometric and involves no model run. It gives, for the lagoon
interior, the quantities through which a depth change reaches the results.

  volume and mean depth    tidal prism to volume ratio, flushing time
  sqrt(h) ratio            long-wave celerity, phase of the lagoon response
  h^(5/3) ratio            unit-width Manning conveyance at equal slope
  hv / h                   canopy submergence, hv = 0.40 m as in the [veg] setup
  faces shallower than 0.3 m   the population prone to the salinity blow-up
  wet and dry mismatch     faces that change class between the two surfaces

The lagoon interior is the set of faces flagged in lagoon_tracer_init.xyz.
Depth is taken below z = 0 of each surface, and differences are 2026 minus
v04 in elevation, positive where the 2026 surface is shallower.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer
from scipy.spatial import cKDTree

from compare_bathy_levigata_2006 import (C_NEW, C_OLD, DIV, EPSG_2006, INK, OUT, WET_FRAC_MIN,
                                          load_2006, load_new, sample_new)

ROOT = Path(__file__).resolve().parents[1]
V04 = ROOT / 'model/dflowfm_v04'
NET = V04 / 'Stagnone_dxy01_15m_net.nc'
TRACER = V04 / 'lagoon_tracer_init.xyz'
OBS = V04 / 'Stagnone_dxy01_15m_obs.xyn'

HV = 0.40           # canopy height of the [veg] setup (m)
H_MIN = 0.05        # depth floor for the ratios (m)
H_SHALLOW = 0.30    # threshold of the blow-up-prone population (m)
TO_UTM = Transformer.from_crs(4326, 32633, always_xy=True)


def face_areas(ds, nx, ny):
    """Planar area of each face by the shoelace formula, in UTM 33N."""
    fn = ds.mesh2d_face_nodes.values
    start = int(ds.mesh2d_face_nodes.attrs.get('start_index', 1))
    ok = np.isfinite(fn) & (fn >= start)
    idx = np.where(ok, fn - start, 0).astype(int)
    x = np.where(ok, nx[idx], np.nan)
    y = np.where(ok, ny[idx], np.nan)
    # close each polygon on its own first node, skipping the padding
    n = ok.sum(axis=1)
    area = np.zeros(len(fn))
    for k in range(fn.shape[1]):
        k2 = np.where(k + 1 < n, k + 1, 0)
        use = k < n
        x2 = x[np.arange(len(fn)), k2]
        y2 = y[np.arange(len(fn)), k2]
        area += np.where(use, x[:, k] * y2 - x2 * y[:, k], 0.0)
    return 0.5 * np.abs(area)


def wq(v, w, q):
    """Area-weighted quantiles."""
    o = np.argsort(v)
    c = np.cumsum(w[o]) / w.sum()
    return np.interp(q, c, v[o])


def main():
    pd.set_option('display.width', 200)
    pd.set_option('display.float_format', lambda v: f'{v:.3f}')
    z_new, wet_new, valid_new, tf, bnd = load_new()

    ds = xr.open_dataset(NET)
    nx, ny = TO_UTM.transform(ds.mesh2d_node_x.values, ds.mesh2d_node_y.values)
    fx, fy = TO_UTM.transform(ds.mesh2d_face_x.values, ds.mesh2d_face_y.values)
    fz = ds.mesh2d_face_z.values
    area = face_areas(ds, nx, ny)

    tr = pd.read_csv(TRACER, sep=r'\s+', header=None, names=['lon', 'lat', 'c'])
    tx, ty = TO_UTM.transform(tr.lon.values, tr.lat.values)
    dist, j = cKDTree(np.c_[tx, ty]).query(np.c_[fx, fy])
    lagoon = (tr.c.values[j] > 0.5) & (dist < 50.0)

    new_f, wfrac, inside = sample_new(z_new, wet_new, valid_new, tf, fx, fy)
    wet_new_f = inside & (wfrac >= WET_FRAC_MIN)
    wet_v04 = fz < 0

    L = lagoon & inside
    print('[lagoon interior] %d faces, %.2f km2, median face size %.0f m' % (
        L.sum(), area[L].sum() * 1e-6, np.sqrt(np.median(area[L]))))
    cls = pd.DataFrame([
        ('wet in both', (L & wet_v04 & wet_new_f)),
        ('wet in v04, land in 2026', (L & wet_v04 & ~wet_new_f)),
        ('land in v04, wet in 2026', (L & ~wet_v04 & wet_new_f)),
    ], columns=['class', 'mask'])
    cls['faces'] = cls['mask'].map(np.sum)
    cls['km2'] = cls['mask'].map(lambda m: area[m].sum() * 1e-6)
    print(cls[['class', 'faces', 'km2']].to_string(index=False))

    B = L & wet_v04 & wet_new_f
    h0, h1, a = -fz[B], -new_f[B], area[B]
    dz = new_f[B] - fz[B]
    v0, v1 = (h0 * a).sum(), (h1 * a).sum()
    print('\n[volume below z=0, faces wet in both] v04 %.2f Mm3, 2026 %.2f Mm3 (%+.1f %%)' % (v0 * 1e-6, v1 * 1e-6, 100 * (v1 / v0 - 1)))
    print('[area-weighted mean depth] v04 %.3f m, 2026 %.3f m' % (v0 / a.sum(), v1 / a.sum()))
    print('[2026 minus v04] bias %.3f m, rmse %.3f m, p05 %.3f, p95 %.3f' % (
        np.average(dz, weights=a), np.sqrt(np.average(dz ** 2, weights=a)), *wq(dz, a, [0.05, 0.95])))

    h0c, h1c = np.maximum(h0, H_MIN), np.maximum(h1, H_MIN)
    q = [0.05, 0.25, 0.5, 0.75, 0.95]
    ratios = pd.DataFrame({
        'quantile (area-weighted)': q,
        'depth ratio h26/h04': wq(h1c / h0c, a, q),
        'celerity ratio sqrt': wq(np.sqrt(h1c / h0c), a, q),
        'conveyance ratio ^(5/3)': wq((h1c / h0c) ** (5 / 3), a, q),
    })
    print('\n[local ratios, faces wet in both]')
    print(ratios.to_string(index=False))
    rel = np.abs(h1c / h0c - 1)
    for thr in (0.10, 0.25, 0.50):
        print('  area with |relative depth change| > %2.0f %%: %.1f %%' % (100 * thr, 100 * a[rel > thr].sum() / a.sum()))
    # bulk celerity over the basin: travel time scales with the mean of h^-1/2
    print('  basin-mean 1/sqrt(g h) ratio (2026 / v04): %.3f' % (
        np.average(h1c ** -0.5, weights=a) / np.average(h0c ** -0.5, weights=a)))

    print('\n[faces shallower than %.2f m] v04 %d (%.1f %% of area), 2026 %d (%.1f %%)' % (
        H_SHALLOW, (h0 < H_SHALLOW).sum(), 100 * a[h0 < H_SHALLOW].sum() / a.sum(),
        (h1 < H_SHALLOW).sum(), 100 * a[h1 < H_SHALLOW].sum() / a.sum()))
    print('[canopy submergence hv/h, hv = %.2f m] median v04 %.3f, 2026 %.3f; area with hv/h > 0.5: v04 %.1f %%, 2026 %.1f %%' % (
        HV, wq(HV / h0c, a, 0.5), wq(HV / h1c, a, 0.5),
        100 * a[HV / h0c > 0.5].sum() / a.sum(), 100 * a[HV / h1c > 0.5].sum() / a.sum()))

    # ---- observation stations ----------------------------------------------
    obs = pd.read_csv(OBS, sep=r'\s+', header=None, names=['lon', 'lat', 'name'])
    ox, oy = TO_UTM.transform(obs.lon.values, obs.lat.values)
    _, k = cKDTree(np.c_[fx, fy]).query(np.c_[ox, oy])
    o_new, o_w, o_in = sample_new(z_new, wet_new, valid_new, tf, ox, oy)
    obs['depth_v04'] = -fz[k]
    obs['depth_2026_at_face'] = -new_f[k]
    obs['depth_2026_at_point'] = -o_new
    obs['delta_m'] = obs.depth_v04 - obs.depth_2026_at_face
    obs = obs[o_in]
    print('\n[stations inside the raster] delta is 2026 minus v04 in elevation')
    print(obs[['name', 'depth_v04', 'depth_2026_at_face', 'depth_2026_at_point', 'delta_m']].to_string(index=False))
    obs.to_csv(OUT / 'impact_v04_stations.csv', index=False)

    # ---- inlet sections -----------------------------------------------------
    # Row or column of the 10 m raster through each inlet station, limited to
    # the contiguous wet run that contains it.
    xs06, ys06, z06, wet06 = load_2006()
    X6, Y6 = np.meshgrid(xs06, ys06)
    X6, Y6 = Transformer.from_crs(EPSG_2006, 32633, always_xy=True).transform(X6, Y6)
    t06 = cKDTree(np.c_[X6[wet06], Y6[wet06]])
    tface = cKDTree(np.c_[fx, fy])
    rows = []
    def wet_run(line, p):
        if not line[p]:
            return None
        i0 = p
        while i0 > 0 and line[i0 - 1]:
            i0 -= 1
        i1 = p
        while i1 < line.size - 1 and line[i1 + 1]:
            i1 += 1
        return np.arange(i0, i1 + 1)

    # The northern station lies seaward of the throat, so the section is the
    # narrowest east-west wet run through its easting within SCAN cells.
    for name, axis, scan in [('BocaNord', 'EW', 150), ('BocaSud', 'NS', 0)]:
        s = obs[obs.name == name].iloc[0]
        sx, sy = TO_UTM.transform(s.lon, s.lat)
        col0 = int((sx - tf.c) / tf.a)
        row0 = int((sy - tf.f) / tf.e)
        best = None
        for off in range(-scan, scan + 1):
            row, col = (row0 + off, col0) if axis == 'EW' else (row0, col0 + off)
            run = wet_run(wet_new[row, :], col) if axis == 'EW' else wet_run(wet_new[:, col], row)
            if run is not None and (best is None or run.size < best[0].size):
                best = (run, row, col)
        ii, row, col = best
        if axis == 'EW':
            px = tf.c + (ii + 0.5) * tf.a
            py = np.full(ii.size, tf.f + (row + 0.5) * tf.e)
            zn = z_new[row, ii]
        else:
            px = np.full(ii.size, tf.c + (col + 0.5) * tf.a)
            py = tf.f + (ii + 0.5) * tf.e
            zn = z_new[ii, col]
        d6, k6 = t06.query(np.c_[px, py])
        z6 = np.where(d6 < 30, z06[wet06][k6], 0.0)
        _, kf = tface.query(np.c_[px, py])
        zf = np.minimum(fz[kf], 0.0)
        w = abs(tf.a)
        rows.append({'section': f'{name} ({axis})', 'x_km': px.mean() / 1e3, 'y_km': py.mean() / 1e3, 'width_m': ii.size * w,
                     'area_2026_m2': -zn.sum() * w, 'area_2006_m2': -z6.sum() * w, 'area_v04_m2': -zf.sum() * w,
                     'max_depth_2026': -zn.min(), 'max_depth_2006': -z6.min(), 'max_depth_v04': -zf.min()})
    sec = pd.DataFrame(rows)
    sec['area_2026_over_v04'] = sec.area_2026_m2 / sec.area_v04_m2
    print('\n[inlet sections through the inlet stations, width defined on the 2026 raster]')
    print(sec.to_string(index=False))
    sec.to_csv(OUT / 'impact_v04_inlet_sections.csv', index=False)

    # ---- figure -------------------------------------------------------------
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': '#999999', 'axes.labelcolor': INK,
                         'xtick.color': INK, 'ytick.color': INK, 'axes.titlesize': 10})
    km = lambda v, p: f'{v / 1000:.0f}'
    fig, axs = plt.subplots(1, 3, figsize=(14, 6.5), constrained_layout=True,
                            gridspec_kw={'width_ratios': [1, 1, 1.25]})
    for ax, val, lab, lim in [
        (axs[0], dz, 'Bed level change (m), positive where 2026 is shallower', 0.5),
        (axs[1], 100 * (h1c / h0c - 1), 'Depth change relative to v04 (%)', 50),
    ]:
        sc = ax.scatter(fx[B], fy[B], c=val, s=5, cmap=DIV if ax is axs[0] else DIV.reversed(),
                        vmin=-lim, vmax=lim, linewidths=0)
        ax.scatter(ox[o_in], oy[o_in], s=28, facecolors='none', edgecolors=INK, linewidths=1)
        for n_, x_, y_ in zip(obs.name, ox[o_in], oy[o_in]):
            ax.annotate(n_, (x_, y_), xytext=(5, 4), textcoords='offset points', fontsize=7, color=INK)
        ax.set_facecolor('#f2f0eb'); ax.set_aspect('equal')
        ax.set_xlim(fx[B].min() - 400, fx[B].max() + 400); ax.set_ylim(fy[B].min() - 400, fy[B].max() + 400)
        ax.xaxis.set_major_formatter(km); ax.yaxis.set_major_formatter(km)
        ax.set_xlabel('Easting UTM 33N (km)')
        fig.colorbar(sc, ax=ax, location='bottom', extend='both', shrink=0.9, label=lab)
    axs[0].set_ylabel('Northing UTM 33N (km)')
    axs[0].set_title('2026 minus v04 on lagoon faces')
    axs[1].set_title('Relative depth change (blue deeper, red shallower)')
    ax = axs[2]
    o0, o1 = np.argsort(h0), np.argsort(h1)
    ax.plot(h0[o0], np.cumsum(a[o0]) * 1e-6, color=C_OLD, lw=2, label='v04 mesh')
    ax.plot(h1[o1], np.cumsum(a[o1]) * 1e-6, color=C_NEW, lw=2, label='2026 on the v04 mesh')
    ax.axvline(H_SHALLOW, color='#999999', lw=0.8, ls='--')
    ax.axvline(HV, color='#999999', lw=0.8, ls=':')
    ax.text(H_SHALLOW, 0.5, ' 0.30 m', fontsize=7, color=INK, rotation=90, va='bottom', ha='right')
    ax.text(HV, 0.5, ' canopy height', fontsize=7, color=INK, rotation=90, va='bottom', ha='left')
    ax.set_xlim(0, 3); ax.set_ylim(0, None)
    ax.set_xlabel('Depth (m)'); ax.set_ylabel('Lagoon area shallower than depth (km$^2$)')
    ax.set_title('Hypsometry of the lagoon interior'); ax.legend(frameon=False)
    ax.grid(color='#e5e5e5', lw=0.6); ax.set_axisbelow(True)
    for s_ in ('top', 'right'):
        ax.spines[s_].set_visible(False)
    fig.savefig(OUT / 'fig4_impact_v04_lagoon.png', dpi=170)
    print('\n[done]', OUT / 'fig4_impact_v04_lagoon.png')


if __name__ == '__main__':
    main()
