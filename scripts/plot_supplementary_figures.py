"""Figures of the Supplementary Material of Paper 1.

S1 mesh resolution, S2 SWAN grids over the flow mesh, S3 Marettimo boundary
offset, S4 initial temperature and salinity profiles, S6 mesh family and layer
test. Every input is local; S5, the mobile-bed state, needs the map files on
the server and is drawn by a separate script. The style follows the figures of
the main text: white surface, recessive grid, the canopy treatment in purple
and the bare one in orange, and one-hue scales for magnitudes.

Output: figures/supplementary/figS<n>.{png,pdf}
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.collections import PolyCollection
from matplotlib.colors import LogNorm
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures' / 'supplementary'
FIG.mkdir(parents=True, exist_ok=True)
NET = ROOT / 'model' / 'dflowfm_v04AE_nowaves' / 'Stagnone_dxy01_15m_net.nc'
SWAN = ROOT / 'model' / 'dflowfm_v04AE' / 'wave'
QT = PROC / 'mesh_quadtree_family'

SURFACE, INK, MUTED, GRID = '#ffffff', '#1b1b1b', '#6b6b6b', '#e8e7e4'
BARE, CANOPY = '#eb6834', '#4a3aa7'
LAGOON = dict(lon=(12.405, 12.495), lat=(37.795, 37.925))
mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})


def style(ax, grid=True):
    ax.set_facecolor(SURFACE)
    if grid:
        ax.grid(color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'):
        ax.spines[sp].set_color('#c9c7c1')


def geo(ax):
    lat0 = np.deg2rad(np.mean(ax.get_ylim()))
    ax.set_aspect(1 / np.cos(lat0))
    ax.set_xlabel('Longitude ($^\\circ$E)', color=MUTED)
    ax.set_ylabel('Latitude ($^\\circ$N)', color=MUTED)


def save(fig, name):
    for ext in ('png', 'pdf'):
        fig.savefig(FIG / f'{name}.{ext}', dpi=300, bbox_inches='tight', facecolor=SURFACE)
    plt.close(fig)
    print('saved', FIG / f'{name}.png')


def faces(path):
    ds = xr.open_dataset(path)
    xb, yb = ds.mesh2d_face_x_bnd.values, ds.mesh2d_face_y_bnd.values
    polys = [np.column_stack([x[np.isfinite(x)], y[np.isfinite(y)]]) for x, y in zip(xb, yb)]
    fx, fy = ds.mesh2d_face_x.values, ds.mesh2d_face_y.values
    ds.close()
    return polys, fx, fy


def spacing(fx, fy):
    lat0 = np.deg2rad(np.mean(fy))
    xy = np.column_stack([fx * 111320 * np.cos(lat0), fy * 110540])
    d, _ = cKDTree(xy).query(xy, k=2)
    return d[:, 1]


def fig_s1():
    polys, fx, fy = faces(NET)
    s = spacing(fx, fy)
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.6), gridspec_kw={'width_ratios': [1.6, 1]})
    norm = LogNorm(vmin=30, vmax=1000)
    for ax, ext, title in ((axes[0], None, '(a) Whole domain'), (axes[1], LAGOON, '(b) Lagoon and inlets')):
        pc = PolyCollection(polys, array=s, cmap='Blues_r', norm=norm, edgecolor='face', lw=0.1)
        ax.add_collection(pc)
        if ext:
            ax.set_xlim(*ext['lon']); ax.set_ylim(*ext['lat'])
        else:
            ax.set_xlim(fx.min() - 0.01, fx.max() + 0.01); ax.set_ylim(fy.min() - 0.01, fy.max() + 0.01)
        style(ax, grid=False)
        geo(ax)
        ax.set_title(title, loc='left', fontsize=11, color=INK)
    cb = fig.colorbar(pc, ax=axes, shrink=0.8, pad=0.02)
    cb.set_ticks([30, 60, 100, 300, 1000])
    cb.set_ticklabels(['30', '60', '100', '300', '1000'])
    cb.set_label('Distance to the nearest cell centre (m)', color=MUTED)
    cb.ax.tick_params(colors=MUTED)
    save(fig, 'figS1')


def read_grd(path):
    lines = path.read_text().splitlines()
    nx, ny = map(int, lines[1].split())
    vals = []
    for ln in lines[3:]:
        ln = ln.replace('ETA=', ' ')
        parts = ln.split()
        if ln.strip() and not ln.startswith('  ') and len(parts) > 0 and parts[0].isdigit() and 'e' not in parts[0]:
            parts = parts[1:]
        vals.extend(float(v) for v in parts if 'e' in v or '.' in v)
    a = np.array(vals)
    assert a.size == 2 * nx * ny, (path, a.size, nx, ny)
    return a[:nx * ny].reshape(ny, nx), a[nx * ny:].reshape(ny, nx)


def outline(x, y):
    xs = np.concatenate([x[0, :], x[:, -1], x[-1, ::-1], x[::-1, 0]])
    ys = np.concatenate([y[0, :], y[:, -1], y[-1, ::-1], y[::-1, 0]])
    return xs, ys


def fig_s2():
    polys, fx, fy = faces(NET)
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.6), gridspec_kw={'width_ratios': [1.6, 1]})
    grids = [('Outer grid, 69 x 54 at about 800 m', SWAN / 'swan_grid_outer.grd', MUTED, (4, 1)),
             ('Inner grid, 121 x 221 at about 90 by 110 m', SWAN / 'swan_grid.grd', CANOPY, (10, 1))]
    for k, (ax, ext, title) in enumerate(((axes[0], None, '(a) Whole domain'),
                                          (axes[1], LAGOON, '(b) Lagoon and inlets, every inner grid line'))):
        ax.add_collection(PolyCollection(polys, facecolor='#d9d7d2', edgecolor='#bdbab3', lw=0.15))
        for lab, path, col, steps in grids:
            step = steps[k]
            x, y = read_grd(path)
            x = np.where(x == 0, np.nan, x); y = np.where(y == 0, np.nan, y)
            for j in range(0, x.shape[0], step):
                ax.plot(x[j], y[j], color=col, lw=0.4, alpha=0.6)
            for i in range(0, x.shape[1], step):
                ax.plot(x[:, i], y[:, i], color=col, lw=0.4, alpha=0.6)
            ox, oy = outline(x, y)
            ax.plot(ox, oy, color=col, lw=2, label=lab)
        if ext:
            ax.set_xlim(*ext['lon']); ax.set_ylim(*ext['lat'])
        else:
            ax.set_xlim(fx.min() - 0.03, fx.max() + 0.03); ax.set_ylim(fy.min() - 0.03, fy.max() + 0.03)
        style(ax, grid=False)
        geo(ax)
        ax.set_title(title, loc='left', fontsize=11, color=INK)
    axes[0].legend(loc='lower left', fontsize=9, frameon=True, framealpha=0.95)
    save(fig, 'figS2')


def fig_s3():
    obs = pd.read_csv(ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv')
    obs = obs.set_index(pd.to_datetime(obs['Time(UTC)']))['wl_m'].sort_index()
    ds = xr.open_dataset(ROOT / 'data' / 'raw' / 'cmems' / 'zos_marettimo_anchor' /
                         'cmems_zos_marettimo_2025-01-01_2026-01-20.nc')
    if 'longitude' in ds.coords:
        ds = ds.rename({'longitude': 'lon', 'latitude': 'lat'})
    zos = ds['zos'].sel(lon=12.0766, lat=37.9662, method='nearest').to_pandas()
    zos.index = pd.DatetimeIndex(zos.index)
    obs_d = obs.resample('1D').mean()
    delta = pd.Series(obs_d.reindex(zos.index.normalize(), method='nearest').values - zos.values,
                      index=zos.index.normalize()).dropna()
    monthly = delta.resample('1ME').mean()
    anchor = float(delta.mean())
    print(f'S3: {len(delta)} days, anchor {anchor:+.3f} m, monthly {monthly.min():+.3f} to {monthly.max():+.3f}')
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(delta.index, delta.values, color='#9b9893', lw=0.9, label='Daily difference')
    ax.plot(monthly.index - pd.Timedelta(days=15), monthly.values, 'o-', color=INK, ms=7, lw=2,
            mec=SURFACE, mew=1.2, label='Monthly mean', zorder=4)
    ax.axhline(anchor, color=CANOPY, lw=2, ls='--', label=f'Anchor, {anchor:+.3f} m')
    ax.axhspan(anchor - 0.07, anchor + 0.07, color=CANOPY, alpha=0.08, lw=0)
    ax.axvspan(pd.Timestamp('2025-07-01'), pd.Timestamp('2025-07-10'), color='#efece6', zorder=0)
    ax.text(pd.Timestamp('2025-07-05'), ax.get_ylim()[1], 'simulated\nwindow', ha='center', va='top',
            fontsize=8.5, color=MUTED)
    ax.set_ylabel('Gauge minus CMEMS sea surface height (m)', color=MUTED)
    style(ax)
    ax.legend(fontsize=9, frameon=False, loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3)
    save(fig, 'figS3')


def read_pli(path):
    a = np.loadtxt(path, skiprows=2)
    return a[:, 0], a[:, 1]


def fig_s4():
    zt, t = read_pli(PROC / 'ic3d' / 'ic3d_temperature_profile.pli')
    zs, s = read_pli(PROC / 'ic3d' / 'ic3d_salinity_profile.pli')
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 5.4), sharey=True)
    for ax, z, v, uni, lab, title in ((axes[0], zt, t, 24.0, 'Temperature ($^\\circ$C)', '(a) Temperature'),
                                      (axes[1], zs, s, 37.5, 'Salinity', '(b) Salinity')):
        ax.plot(v, z, color=INK, lw=2, marker='o', ms=4, label='Stratified start (CMEMS profile)')
        ax.axvline(uni, color=BARE, lw=2, ls='--', label='Uniform start')
        ax.set_xlabel(lab, color=MUTED)
        ax.set_title(title, loc='left', fontsize=11, color=INK)
        style(ax)
    axes[0].set_ylim(-700, 5)
    axes[0].set_ylabel('Elevation (m)', color=MUTED)
    axes[0].legend(fontsize=9, frameon=False, loc='lower right')
    save(fig, 'figS4')


def mean_se(tag):
    x = pd.read_csv(PROC / f'drifter_metrics_{tag}.csv').LW_skill
    return x.mean(), x.std(ddof=1) / np.sqrt(len(x))


def fig_s6():
    fig = plt.figure(figsize=(12.8, 9.0))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.35, 1], hspace=0.32, wspace=0.18)
    for k, (lev, lab) in enumerate((('L60', '60 m'), ('L30', '30 m'), ('L15', '15 m'))):
        ax = fig.add_subplot(gs[0, k])
        polys, fx, fy = faces(QT / f'stagnone_qt_{lev}' / f'stagnone_qt_{lev}_net.nc')
        ax.add_collection(PolyCollection(polys, facecolor='#f3f2ef', edgecolor='#5d5a55', lw=0.15))
        ax.set_xlim(*LAGOON['lon']); ax.set_ylim(*LAGOON['lat'])
        style(ax, grid=False)
        geo(ax)
        if k:
            ax.set_ylabel(''); ax.tick_params(labelleft=False)
        ax.set_title(f'({"abc"[k]}) {lab} in the lagoon, {len(polys):,} faces', loc='left',
                     fontsize=10, color=INK)
    def paired(a, b):
        da = pd.read_csv(PROC / f'drifter_metrics_{a}.csv').set_index(['deploy', 'drifter_id']).LW_skill
        db = pd.read_csv(PROC / f'drifter_metrics_{b}.csv').set_index(['deploy', 'drifter_id']).LW_skill
        x = (da - db).dropna()
        return x.mean(), x.std(ddof=1) / np.sqrt(len(x))

    def panel(ax, rows, ref, title):
        for i, (lab, tag) in enumerate(rows):
            m, se = paired(tag, ref)
            ax.errorbar(i, m, yerr=se, fmt='o', color=INK, ms=8, capsize=4, lw=1.6, mec=SURFACE, mew=1.2)
        ax.axhline(0, color=INK, lw=1.0)
        ax.set_xticks(range(len(rows)))
        ax.set_xticklabels([r[0] for r in rows])
        ax.set_xlim(-0.5, len(rows) - 0.5)
        ax.set_ylim(-0.02, 0.02)
        ax.set_title(title, loc='left', fontsize=10, color=INK)
        style(ax)

    ax = fig.add_subplot(gs[1, 0:2])
    panel(ax, [('30 m', 'v04AE_nowaves_qtL30_cfl05'), ('15 m', 'v04AE_nowaves_qtL15_cfl05'),
               ('present mesh', 'v04AE_nowaves_bed26_cfl05')], 'v04AE_nowaves_qtL60_cfl05',
          '(d) Horizontal resolution, uniform start, against the 60 m mesh')
    ax.set_ylabel('Paired change in Liu--Weisberg skill', color=MUTED)
    ax = fig.add_subplot(gs[1, 2])
    panel(ax, [('20 layers', 'v04AE_nowaves_v04bed_cfl05_L20_at5_ic3d')],
          'v04AE_nowaves_v04bed_cfl05_L10_at5_ic3d', '(e) 20 against 10 layers, stratified start')
    save(fig, 'figS6')


if __name__ == '__main__':
    fig_s1(); fig_s2(); fig_s3(); fig_s4(); fig_s6()
