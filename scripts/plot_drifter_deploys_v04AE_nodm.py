"""Per-deploy drifter figures for v04AE_nodm (full 9d, AE-only blend, D-Morph OFF).

Mirror of plot_drifter_deploys_v04AE.py with VARIANT toggled.
Output: figures/v04AE_nodm_drifter_deploy_NN.png (NN = 01..12).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
MODEL_DIR = ROOT / 'model' / 'dflowfm_v04AE'  # land boundaries identical, reuse

VARIANT = 'v04AE_nodm'
TITLE_TAG = 'v04AE_nodm, full 9d Jul 1-10, AE-only blend, D-Morph OFF'

STAGNONE_BBOX = dict(lon=(12.420, 12.490), lat=(37.800, 37.9105))
ASPECT_LAT = 37.87
ASPECT = 1.0 / np.cos(np.radians(ASPECT_LAT))
HALF_PAD = (1.0 / np.sqrt(0.75) - 1) / 2


def parse_ldb(path):
    polylines = []
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith('*')]
    i = 0
    while i < len(lines):
        i += 1
        if i >= len(lines):
            break
        npts = int(lines[i].split()[0])
        i += 1
        coords = np.array([list(map(float, lines[i+k].split()[:2])) for k in range(npts)])
        polylines.append(coords)
        i += npts
    return polylines


def main():
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    sim = pd.read_csv(PROC / f'drifter_sim_{VARIANT}.csv', parse_dates=['time'])
    metrics = pd.read_csv(PROC / f'drifter_metrics_{VARIANT}.csv')
    print(f'Obs: {len(obs)} rows; Sim: {len(sim)} rows; Metrics: {len(metrics)} rows')

    landboundary = []
    for fn in ['sicily2.ldb', 'Stagnone_dxy01_15m.ldb']:
        path = MODEL_DIR / fn
        if path.exists():
            landboundary.extend(parse_ldb(path))
    poly_bboxes = np.array([[p[:, 0].min(), p[:, 0].max(),
                              p[:, 1].min(), p[:, 1].max()]
                             for p in landboundary])

    land_mask_path = PROC / 'v04_land_mask_50m.nc'
    land_arr = land_lon = land_lat = None
    if land_mask_path.exists():
        land_ds = xr.open_dataset(land_mask_path)
        land_lon = land_ds.lon.values
        land_lat = land_ds.lat.values
        land_arr = land_ds.land.values

    def visible_polys(lon_min, lon_max, lat_min, lat_max):
        keep = (poly_bboxes[:, 1] >= lon_min) & (poly_bboxes[:, 0] <= lon_max) & \
               (poly_bboxes[:, 3] >= lat_min) & (poly_bboxes[:, 2] <= lat_max)
        return np.where(keep)[0]

    def draw_land(ax):
        lon_min, lon_max = ax.get_xlim()
        lat_min, lat_max = ax.get_ylim()
        if land_arr is not None:
            ix = (land_lon >= lon_min) & (land_lon <= lon_max)
            iy = (land_lat >= lat_min) & (land_lat <= lat_max)
            sub = land_arr[np.ix_(iy, ix)]
            if sub.size > 0:
                ax.pcolormesh(land_lon[ix], land_lat[iy],
                              np.where(sub == 1, 1.0, np.nan),
                              cmap='Greys', vmin=0, vmax=2.0, shading='auto',
                              zorder=0, rasterized=True, alpha=0.55)
        for idx in visible_polys(lon_min, lon_max, lat_min, lat_max):
            poly = landboundary[idx]
            ax.fill(poly[:, 0], poly[:, 1], color='lightgrey', alpha=0.7, zorder=1)
            ax.plot(poly[:, 0], poly[:, 1], '-', color='dimgrey', lw=0.35, zorder=2)

    def plot_tracks(ax, obs_dep, sim_dep, sources):
        cmap = plt.get_cmap('tab10')
        for i, src in enumerate(sources):
            color = cmap(i % 10)
            obs_g = obs_dep[obs_dep['source'] == src].sort_values('time')
            sim_g = sim_dep[sim_dep['drifter_id'] == src].sort_values('time')
            if obs_g.empty:
                continue
            t0, t1 = obs_g['time'].min(), obs_g['time'].max()
            sim_clip = sim_g[(sim_g['time'] >= t0) & (sim_g['time'] <= t1)]
            ax.plot(obs_g['lon'], obs_g['lat'], '-', color=color, alpha=0.9,
                    lw=1.1, label=str(src), zorder=4)
            if len(sim_clip):
                ax.plot(sim_clip['lon'], sim_clip['lat'], '--', color=color,
                        alpha=0.95, lw=1.1, zorder=4)
            ax.scatter(obs_g['lon'].iloc[0], obs_g['lat'].iloc[0], color=color,
                       s=60, marker='o', edgecolor='k', linewidth=0.5, zorder=6)
            ax.scatter(obs_g['lon'].iloc[-1], obs_g['lat'].iloc[-1], color=color,
                       s=46, marker='s', edgecolor='k', linewidth=0.4, zorder=6)
            if len(sim_clip):
                ax.scatter(sim_clip['lon'].iloc[-1], sim_clip['lat'].iloc[-1],
                           color=color, s=67, marker='X',
                           edgecolor='k', linewidth=0.4, zorder=6)

    LEGEND_TYPE = [
        Line2D([0], [0], color='black', lw=1.1, linestyle='-', label='observed'),
        Line2D([0], [0], color='black', lw=1.1, linestyle='--',
               label=f'simulated ({VARIANT})'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgrey',
               markeredgecolor='k', markersize=6, label='release', linestyle=''),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='lightgrey',
               markeredgecolor='k', markersize=5, label='obs end', linestyle=''),
        Line2D([0], [0], marker='X', color='w', markerfacecolor='lightgrey',
               markeredgecolor='k', markersize=6, label='sim end @ obs t_end',
               linestyle=''),
    ]

    for dep in sorted(sim['deploy'].unique()):
        obs_dep = obs[obs['deploy'] == dep]
        sim_dep = sim[sim['deploy'] == dep]
        if obs_dep.empty:
            continue
        sources = sorted(obs_dep['source'].unique())
        t0, t1 = obs_dep['time'].min(), obs_dep['time'].max()
        dur_h = (t1 - t0).total_seconds() / 3600.0

        m_dep = metrics[metrics['deploy'] == dep]
        lw_mean = m_dep['LW_skill'].mean()
        ep_mean = m_dep['endpoint_sep_m'].mean()

        fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=(13, 6))
        fig.subplots_adjust(left=0.05, right=0.99, top=0.84, bottom=0.10, wspace=0.04)

        ax_full.set_xlim(*STAGNONE_BBOX['lon'])
        ax_full.set_ylim(*STAGNONE_BBOX['lat'])
        draw_land(ax_full)
        plot_tracks(ax_full, obs_dep, sim_dep, sources)
        ax_full.set_aspect(ASPECT, adjustable='datalim')
        ax_full.set_title('Stagnone overview', fontsize=11)
        ax_full.set_xlabel('Longitude (deg E)')
        ax_full.set_ylabel('Latitude (deg N)')
        ax_full.grid(alpha=0.3)
        ax_full.legend(loc='best', fontsize=7, title='drifter', framealpha=0.85)

        all_lons = pd.concat([obs_dep['lon'], sim_dep['lon']]) if not sim_dep.empty else obs_dep['lon']
        all_lats = pd.concat([obs_dep['lat'], sim_dep['lat']]) if not sim_dep.empty else obs_dep['lat']
        lon_span = max(all_lons.max() - all_lons.min(), 0.001)
        lat_span = max(all_lats.max() - all_lats.min(), 0.001)
        zlon_min = all_lons.min() - lon_span * HALF_PAD
        zlon_max = all_lons.max() + lon_span * HALF_PAD
        zlat_min = all_lats.min() - lat_span * HALF_PAD
        zlat_max = all_lats.max() + lat_span * HALF_PAD
        ax_zoom.set_xlim(zlon_min, zlon_max)
        ax_zoom.set_ylim(zlat_min, zlat_max)
        draw_land(ax_zoom)
        plot_tracks(ax_zoom, obs_dep, sim_dep, sources)
        ax_zoom.set_aspect(ASPECT, adjustable='datalim')
        width_km = (zlon_max - zlon_min) * 111 * np.cos(np.radians(ASPECT_LAT))
        height_km = (zlat_max - zlat_min) * 111
        ax_zoom.set_title(f'Track zoom ({width_km:.2f} x {height_km:.2f} km)',
                          fontsize=11)
        ax_zoom.set_xlabel('Longitude (deg E)')
        ax_zoom.set_ylabel('Latitude (deg N)')
        ax_zoom.grid(alpha=0.3)
        ax_zoom.legend(loc='best', fontsize=7, title='drifter', framealpha=0.85)

        fig.suptitle(
            f'Deploy {dep} ({TITLE_TAG})  |  {len(sources)} drifter(s)  |  '
            f'obs {dur_h:.1f} h  |  mean LW skill={lw_mean:.2f}, mean EP={ep_mean:.0f} m  |  '
            f'{t0.strftime("%Y-%m-%d %H:%M")} -> {t1.strftime("%H:%M")}',
            fontsize=11, y=0.97
        )
        fig.legend(handles=LEGEND_TYPE, loc='upper center', ncol=5, fontsize=8.5,
                   bbox_to_anchor=(0.5, 0.93), frameon=True)
        out = FIG / f'{VARIANT}_drifter_deploy_{dep:02d}.png'
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved {out.name}  LW={lw_mean:.2f}  EP={ep_mean:.0f} m')


if __name__ == '__main__':
    main()
