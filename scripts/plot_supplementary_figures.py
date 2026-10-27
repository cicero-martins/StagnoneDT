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
from matplotlib.colors import BoundaryNorm
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
BOCCA_NORD = dict(lon=(12.443, 12.470), lat=(37.896, 37.914))
LAGOON_CENTRE = (12.462, 37.867)          # centre of the wind blend, as in prepare_v04rAE_ae_only_blend.py
AE_STATION = (12.447, 37.890)
CAMPAIGN = (pd.Timestamp('2025-07-08 06:00'), pd.Timestamp('2025-07-09 20:00'))
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


def aspect(ext):
    """Width over height of a geographic window drawn at true scale."""
    (x0, x1), (y0, y1) = ext['lon'], ext['lat']
    return (x1 - x0) * np.cos(np.deg2rad((y0 + y1) / 2)) / (y1 - y0)


def zoom_box(ax, ext, color=INK):
    (x0, x1), (y0, y1) = ext['lon'], ext['lat']
    ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color=color, lw=1.4)


def fig_s1():
    polys, fx, fy = faces(NET)
    s = spacing(fx, fy)
    whole = dict(lon=(fx.min() - 0.01, fx.max() + 0.01), lat=(fy.min() - 0.01, fy.max() + 0.01))
    panels = ((whole, '(a) Whole domain', 0.1), (LAGOON, '(b) Lagoon and inlets', 0.1),
              (BOCCA_NORD, '(c) Bocca Nord', 0.5))
    ratios = [aspect(e) for e, _, _ in panels]
    fig = plt.figure(figsize=(16.5, 5.6))
    gs = fig.add_gridspec(1, 4, width_ratios=ratios + [0.05], wspace=0.3)
    bounds = [30, 45, 55, 65, 80, 100, 150, 250, 400, 600, 1000]
    norm = BoundaryNorm(bounds, 256)
    for k, (ext, title, lw) in enumerate(panels):
        ax = fig.add_subplot(gs[0, k])
        edge = '#1b1b1b' if k == 2 else 'face'
        pc = PolyCollection(polys, array=s, cmap='viridis', norm=norm, edgecolor=edge, lw=lw,
                            rasterized=True)
        ax.add_collection(pc)
        ax.set_xlim(*ext['lon']); ax.set_ylim(*ext['lat'])
        style(ax, grid=False)
        geo(ax)
        if k:
            ax.set_ylabel('')
        if k < 2:
            zoom_box(ax, panels[k + 1][0], color='#c0392b')
        ax.set_title(title, loc='left', fontsize=11, color=INK)
    cb = fig.colorbar(pc, cax=fig.add_subplot(gs[0, 3]), ticks=bounds, spacing='uniform')
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
        ax.add_collection(PolyCollection(polys, facecolor='#d9d7d2', edgecolor='#bdbab3', lw=0.15, rasterized=True))
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
    zos.index = zos.index.normalize()
    obs_d = obs.resample('1D').mean()
    obs_d.index = pd.DatetimeIndex(obs_d.index).normalize()
    # exact daily alignment, as in compute_marettimo_offset_anchor.py
    df = pd.concat([obs_d.rename('obs'), zos.rename('zos')], axis=1).dropna()
    delta = df['obs'] - df['zos']
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


def dist_km(lon, lat, lon0, lat0):
    return np.hypot((lon - lon0) * 111 * np.cos(np.radians((lat + lat0) / 2)), (lat - lat0) * 111)


def fig_s3_wind():
    era = ROOT / 'model' / 'dflowfm_v04rE5'
    u = xr.open_dataset(era / 'wind_era5raw_u10n_20250701to20250710.nc').u10n
    v = xr.open_dataset(era / 'wind_era5raw_v10n_20250701to20250710.nc').v10n
    pt = dict(longitude=LAGOON_CENTRE[0], latitude=LAGOON_CENTRE[1])
    eu = u.sortby('latitude').interp(**pt).to_pandas()
    ev = v.sortby('latitude').interp(**pt).to_pandas()
    ae = pd.read_csv(PROC / 'wind_AE_10min_UTC.csv', index_col=0, parse_dates=True)
    rad = np.radians(ae['dir_deg'])
    ae_h = pd.DataFrame({'u': -ae['speed_10m'] * np.sin(rad),
                         'v': -ae['speed_10m'] * np.cos(rad)}).resample('1h').mean()
    ae_h = ae_h.loc[eu.index[0]:eu.index[-1]]

    def spd_dir(uu, vv):
        return np.hypot(uu, vv), (np.degrees(np.arctan2(-uu, -vv)) + 360) % 360

    series = (('AltaVilaEst record, applied inside 3 km', *spd_dir(ae_h.u, ae_h.v), CANOPY),
              ('ERA5 at the lagoon centre, applied beyond 8 km', *spd_dir(eu, ev), BARE))

    polys, fx, fy = faces(NET)
    ext = dict(lon=(12.33, 12.59), lat=(37.77, 37.965))
    fig = plt.figure(figsize=(13.5, 5.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[aspect(ext) * 1.15, 1.9], wspace=0.22, hspace=0.12)
    ax = fig.add_subplot(gs[:, 0])
    ax.add_collection(PolyCollection(polys, facecolor='#e4e2dd', edgecolor='none', rasterized=True))
    lon = np.linspace(*ext['lon'], 400); lat = np.linspace(*ext['lat'], 300)
    LON, LAT = np.meshgrid(lon, lat)
    d = dist_km(LON, LAT, *LAGOON_CENTRE)
    w = np.clip((8 - d) / 5, 0, 1)
    pm = ax.pcolormesh(LON, LAT, np.ma.masked_equal(w, 0), cmap='Purples', vmin=0, vmax=1.25,
                       alpha=0.75, shading='auto', rasterized=True)
    ax.contour(LON, LAT, d, levels=[3, 8], colors=[CANOPY, MUTED], linewidths=1.4)
    ax.plot(*AE_STATION, marker='^', color=INK, ms=9, mec=SURFACE, mew=1.2, ls='none',
            label='AltaVilaEst station')
    ax.plot(*LAGOON_CENTRE, marker='+', color=INK, ms=11, mew=2, ls='none', label='Centre of the blend')
    ax.set_xlim(*ext['lon']); ax.set_ylim(*ext['lat'])
    style(ax, grid=False)
    geo(ax)
    ax.set_title('(a) Weight of the station record', loc='left', fontsize=11, color=INK)
    ax.legend(fontsize=8.5, loc='lower left', frameon=True, framealpha=0.95)
    cb = fig.colorbar(pm, ax=ax, shrink=0.7, pad=0.02, ticks=[0, 0.5, 1])
    cb.ax.set_ylim(0, 1)
    cb.ax.tick_params(colors=MUTED)

    axs = fig.add_subplot(gs[0, 1]); axd = fig.add_subplot(gs[1, 1], sharex=axs)
    for lab, sp, dr, col in series:
        axs.plot(sp.index, sp.values, color=col, lw=1.5, label=lab)
        axd.plot(dr.index, dr.values, 'o', color=col, ms=2.5, label=lab)
    for a in (axs, axd):
        a.axvspan(*CAMPAIGN, color='#efece6', zorder=0)
        style(a)
    axs.text(CAMPAIGN[0] + (CAMPAIGN[1] - CAMPAIGN[0]) / 2, axs.get_ylim()[1], 'drifter\ncampaign',
             ha='center', va='top', fontsize=8.5, color=MUTED)
    axs.set_ylabel('Speed at 10 m (m s$^{-1}$)', color=MUTED)
    axs.set_title('(b) Wind speed', loc='left', fontsize=11, color=INK)
    axs.tick_params(labelbottom=False)
    axs.legend(fontsize=8.5, frameon=False, loc='upper left')
    axd.set_ylim(0, 360); axd.set_yticks([0, 90, 180, 270, 360])
    axd.set_yticklabels(['N', 'E', 'S', 'W', 'N'])
    axd.set_ylabel('Direction from', color=MUTED)
    axd.set_title('(c) Wind direction', loc='left', fontsize=11, color=INK)
    axd.xaxis.set_major_formatter(mpl.dates.DateFormatter('%d %b'))
    save(fig, 'figS3_wind')


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
    fig = plt.figure(figsize=(12.8, 14.0))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.35, 0.95, 1], hspace=0.3, wspace=0.18)
    for k, (lev, lab) in enumerate((('L60', '60 m'), ('L30', '30 m'), ('L15', '15 m'))):
        polys, fx, fy = faces(QT / f'stagnone_qt_{lev}' / f'stagnone_qt_{lev}_net.nc')
        for row, ext, lw, title in ((0, LAGOON, 0.15, f'({"abc"[k]}) {lab} in the lagoon, {len(polys):,} faces'),
                                    (1, BOCCA_NORD, 0.4, f'({"def"[k]}) {lab}, Bocca Nord')):
            ax = fig.add_subplot(gs[row, k])
            ax.add_collection(PolyCollection(polys, facecolor='#f3f2ef', edgecolor='#5d5a55', lw=lw, rasterized=True))
            ax.set_xlim(*ext['lon']); ax.set_ylim(*ext['lat'])
            style(ax, grid=False)
            geo(ax)
            if row == 0:
                zoom_box(ax, BOCCA_NORD, color='#c0392b')
            if k:
                ax.set_ylabel(''); ax.tick_params(labelleft=False)
            ax.set_title(title, loc='left', fontsize=10, color=INK)
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

    ax = fig.add_subplot(gs[2, 0:2])
    panel(ax, [('30 m', 'v04AE_nowaves_qtL30_cfl05'), ('15 m', 'v04AE_nowaves_qtL15_cfl05'),
               ('present mesh', 'v04AE_nowaves_bed26_cfl05')], 'v04AE_nowaves_qtL60_cfl05',
          '(g) Horizontal resolution, uniform start, against the 60 m mesh')
    ax.set_ylabel('Paired change in Liu--Weisberg skill', color=MUTED)
    ax = fig.add_subplot(gs[2, 2])
    panel(ax, [('20 layers', 'v04AE_nowaves_v04bed_cfl05_L20_at5_ic3d')],
          'v04AE_nowaves_v04bed_cfl05_L10_at5_ic3d', '(h) 20 against 10 layers, stratified start')
    save(fig, 'figS6')


if __name__ == '__main__':
    fig_s1(); fig_s2(); fig_s3(); fig_s3_wind(); fig_s4(); fig_s6()
