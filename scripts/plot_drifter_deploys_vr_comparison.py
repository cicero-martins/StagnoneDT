"""Per-deploy drifter trajectory comparison: bl / nodm / vr / nodm_vr.

Layout per deploy: 1 overview (full lagoon, all runs) + 4 zoomed panels (one per run).
Output: figures/vr_drifter_deploy_NN.png (NN = 01..12).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.gridspec as gridspec

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
MODEL_DIR = ROOT / 'model' / 'dflowfm_v04AE'

RUNS = {
    'v04AE':         ('bl  D-Morph ON,  VR OFF', '#2563eb'),
    'v04AE_nodm':    ('nodm D-Morph OFF, VR OFF', '#16a34a'),
    'v04AE_vr':      ('vr  D-Morph ON,  VR ON',  '#dc2626'),
    'v04AE_nodm_vr': ('nodm_vr D-Morph OFF, VR ON', '#ea580c'),
}

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
    sims = {}
    metrics = {}
    for run in RUNS:
        f_sim = PROC / f'drifter_sim_{run}.csv'
        f_met = PROC / f'drifter_metrics_{run}.csv'
        if f_sim.exists() and f_met.exists():
            sims[run] = pd.read_csv(f_sim, parse_dates=['time'])
            metrics[run] = pd.read_csv(f_met)
            print(f'{run}: {len(sims[run])} sim rows, {len(metrics[run])} metric rows')
        else:
            missing = [f for f in [f_sim, f_met] if not f.exists()]
            print(f'MISSING: {[m.name for m in missing]}')
    available_runs = list(sims.keys())

    landboundary = []
    for fn in ['sicily2.ldb', 'Stagnone_dxy01_15m.ldb']:
        path = MODEL_DIR / fn
        if path.exists():
            landboundary.extend(parse_ldb(path))
    poly_bboxes = np.array([[p[:, 0].min(), p[:, 0].max(),
                              p[:, 1].min(), p[:, 1].max()]
                             for p in landboundary]) if landboundary else np.empty((0, 4))

    land_mask_path = PROC / 'v04_land_mask_50m.nc'
    land_arr = land_lon = land_lat = None
    if land_mask_path.exists():
        land_ds = xr.open_dataset(land_mask_path)
        land_lon = land_ds.lon.values
        land_lat = land_ds.lat.values
        land_arr = land_ds.land.values

    def visible_polys(lon_min, lon_max, lat_min, lat_max):
        if poly_bboxes.shape[0] == 0:
            return []
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

    def plot_tracks_on_ax(ax, obs_dep, sim_dep, sources, run_color):
        cmap = plt.get_cmap('tab10')
        for i, src in enumerate(sources):
            color = cmap(i % 10)
            obs_g = obs_dep[obs_dep['source'] == src].sort_values('time')
            sim_g = sim_dep[sim_dep['drifter_id'] == src].sort_values('time') \
                if sim_dep is not None else pd.DataFrame()
            if obs_g.empty:
                continue
            t0, t1 = obs_g['time'].min(), obs_g['time'].max()
            sim_clip = sim_g[(sim_g['time'] >= t0) & (sim_g['time'] <= t1)] \
                if not sim_g.empty else pd.DataFrame()
            ax.plot(obs_g['lon'], obs_g['lat'], '-', color=color, alpha=0.9,
                    lw=1.1, zorder=4)
            if len(sim_clip):
                ax.plot(sim_clip['lon'], sim_clip['lat'], '--', color=run_color,
                        alpha=0.95, lw=1.1, zorder=5)
            ax.scatter(obs_g['lon'].iloc[0], obs_g['lat'].iloc[0], color=color,
                       s=55, marker='o', edgecolor='k', linewidth=0.5, zorder=6)
            ax.scatter(obs_g['lon'].iloc[-1], obs_g['lat'].iloc[-1], color=color,
                       s=40, marker='s', edgecolor='k', linewidth=0.4, zorder=6)
            if len(sim_clip):
                ax.scatter(sim_clip['lon'].iloc[-1], sim_clip['lat'].iloc[-1],
                           color=run_color, s=60, marker='X',
                           edgecolor='k', linewidth=0.4, zorder=7)

    deploys = sorted(obs['deploy'].unique())

    for dep in deploys:
        obs_dep = obs[obs['deploy'] == dep]
        if obs_dep.empty:
            continue
        sources = sorted(obs_dep['source'].unique())
        t0, t1 = obs_dep['time'].min(), obs_dep['time'].max()
        dur_h = (t1 - t0).total_seconds() / 3600.0

        # auto zoom extent (from obs + all sim)
        all_lons = obs_dep['lon'].copy()
        all_lats = obs_dep['lat'].copy()
        for run in available_runs:
            sd = sims[run][sims[run]['deploy'] == dep]
            if not sd.empty:
                all_lons = pd.concat([all_lons, sd['lon']])
                all_lats = pd.concat([all_lats, sd['lat']])
        lon_span = max(all_lons.max() - all_lons.min(), 0.002)
        lat_span = max(all_lats.max() - all_lats.min(), 0.002)
        zlon_min = all_lons.min() - lon_span * HALF_PAD
        zlon_max = all_lons.max() + lon_span * HALF_PAD
        zlat_min = all_lats.min() - lat_span * HALF_PAD
        zlat_max = all_lats.max() + lat_span * HALF_PAD

        # layout: left = overview, right = 2x2 grid of zooms
        fig = plt.figure(figsize=(18, 9))
        gs = gridspec.GridSpec(2, 3, figure=fig, width_ratios=[1.2, 1, 1],
                               hspace=0.35, wspace=0.12)
        ax_ov = fig.add_subplot(gs[:, 0])  # tall overview
        run_axes = [
            fig.add_subplot(gs[0, 1]),  # bl
            fig.add_subplot(gs[0, 2]),  # nodm
            fig.add_subplot(gs[1, 1]),  # vr
            fig.add_subplot(gs[1, 2]),  # nodm_vr
        ]

        # overview: all runs + obs
        ax_ov.set_xlim(*STAGNONE_BBOX['lon'])
        ax_ov.set_ylim(*STAGNONE_BBOX['lat'])
        draw_land(ax_ov)
        for run, ax_r in zip(available_runs, run_axes):
            label, col = RUNS[run]
            sd = sims[run][sims[run]['deploy'] == dep]
            for src in sources:
                sg = sd[sd['drifter_id'] == src].sort_values('time')
                og = obs_dep[obs_dep['source'] == src].sort_values('time')
                if og.empty:
                    continue
                t0s, t1s = og['time'].min(), og['time'].max()
                sc = sg[(sg['time'] >= t0s) & (sg['time'] <= t1s)]
                if len(sc):
                    ax_ov.plot(sc['lon'], sc['lat'], '-', color=col, alpha=0.6, lw=0.9, zorder=4)
                    ax_ov.scatter(sc['lon'].iloc[-1], sc['lat'].iloc[-1],
                                  color=col, s=45, marker='X', edgecolor='k',
                                  linewidth=0.3, zorder=6)
        # obs on overview
        for src in sources:
            og = obs_dep[obs_dep['source'] == src].sort_values('time')
            if og.empty:
                continue
            ax_ov.plot(og['lon'], og['lat'], 'k-', alpha=0.85, lw=1.1, zorder=7)
            ax_ov.scatter(og['lon'].iloc[0], og['lat'].iloc[0], color='k',
                          s=55, marker='o', edgecolor='k', linewidth=0.5, zorder=8)
            ax_ov.scatter(og['lon'].iloc[-1], og['lat'].iloc[-1], color='k',
                          s=40, marker='s', edgecolor='k', linewidth=0.4, zorder=8)
        ax_ov.set_aspect(ASPECT, adjustable='datalim')
        ax_ov.set_xlabel('Longitude', fontsize=8)
        ax_ov.set_ylabel('Latitude', fontsize=8)
        ax_ov.set_title(f'Deploy {dep} — all runs\n{t0.strftime("%Y-%m-%d %H:%M")} '
                        f'-> {t1.strftime("%H:%M")}  ({dur_h:.1f} h)', fontsize=9)
        ax_ov.grid(alpha=0.3)
        # overview legend
        ov_handles = [Line2D([0], [0], color='k', lw=1.1, label='observed')]
        for run in available_runs:
            lbl, col = RUNS[run]
            ov_handles.append(Line2D([0], [0], color=col, lw=0.9, label=lbl[:4]))
        ax_ov.legend(handles=ov_handles, fontsize=7, loc='lower right', framealpha=0.85)

        # per-run zoom panels
        for run, ax_r in zip(available_runs, run_axes):
            label, col = RUNS[run]
            sd = sims[run][sims[run]['deploy'] == dep]
            m_dep = metrics[run][metrics[run]['deploy'] == dep]
            lw_mean = m_dep['LW_skill'].mean() if len(m_dep) else float('nan')
            ep_mean = m_dep['endpoint_sep_m'].mean() if len(m_dep) else float('nan')

            ax_r.set_xlim(zlon_min, zlon_max)
            ax_r.set_ylim(zlat_min, zlat_max)
            draw_land(ax_r)
            plot_tracks_on_ax(ax_r, obs_dep, sd, sources, col)
            ax_r.set_aspect(ASPECT, adjustable='datalim')
            ax_r.set_xlabel('Lon', fontsize=7)
            ax_r.set_ylabel('Lat', fontsize=7)
            ax_r.tick_params(labelsize=6)
            ax_r.grid(alpha=0.3)
            short = label.split()[0]  # bl / nodm / vr / nodm_vr
            ax_r.set_title(f'{short}   LW={lw_mean:.2f}  EP={ep_mean:.0f} m',
                           fontsize=9, color=col, fontweight='bold')

        # shared type legend
        type_handles = [
            Line2D([0], [0], color='k', lw=1.1, linestyle='-', label='observed'),
            Line2D([0], [0], color='grey', lw=1.1, linestyle='--', label='simulated'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='grey',
                   markeredgecolor='k', markersize=6, label='release', linestyle=''),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='grey',
                   markeredgecolor='k', markersize=5, label='obs end', linestyle=''),
            Line2D([0], [0], marker='X', color='grey', markersize=6,
                   markeredgecolor='k', label='sim end', linestyle=''),
        ]
        fig.legend(handles=type_handles, loc='upper center', ncol=5, fontsize=8,
                   bbox_to_anchor=(0.62, 0.99), frameon=True)

        fig.suptitle(
            f'Deploy {dep} — drifter comparison  |  {len(sources)} drifter(s)  |  '
            f'{t0.strftime("%Y-%m-%d %H:%M")} -> {t1.strftime("%H:%M")}',
            fontsize=11, y=1.02
        )

        out = FIG / f'vr_drifter_deploy_{dep:02d}.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved {out.name}  D{dep}: '
              + '  '.join(f'{r.split("_", 1)[-1] if "_" in r else "bl"}=LW{metrics[r][metrics[r]["deploy"]==dep]["LW_skill"].mean():.2f}'
                          for r in available_runs))


if __name__ == '__main__':
    main()
