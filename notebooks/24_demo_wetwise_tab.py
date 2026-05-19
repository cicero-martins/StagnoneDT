# %% [markdown]
# # 24. Demo Wetwise Tab — Continuation v04AE_d10d12 (Jul 10-12 2025)
#
# Produces the visualization bundle for the wetwise mock-up "Hydrodynamic Model" tab.
# Inputs:
#   - `model/dflowfm_v04AE_d10d12/DFM_OUTPUT_Stagnone_dxy01_15m/` (1 his.nc + 8 map.nc)
#   - `data/processed/insitu_2025-26/{AE,BN,BS}_wl_UTC.csv` (in-situ WL for validation)
#
# Outputs to `outputs/wetwise_tab/`:
#   - `interactive/*.html` (Plotly fig_to_html, self-contained)
#   - `static/*.png` (matplotlib snapshots)
#   - `data/validation_metrics.json`
#   - `animations/*.mp4` (FuncAnimation → ffmpeg)
#
# This script uses `# %%` cell markers — run end-to-end with
# `python notebooks/24_demo_wetwise_tab.py` or cell-by-cell in VS Code.

# %% setup
from __future__ import annotations
from pathlib import Path
import json

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib

# Point matplotlib at the imageio-ffmpeg binary (handles Windows where ffmpeg is not on PATH)
import imageio_ffmpeg
matplotlib.rcParams['animation.ffmpeg_path'] = imageio_ffmpeg.get_ffmpeg_exe()

import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import plotly.graph_objects as go
import plotly.io as pio
import cmocean.cm as cmo  # oceanographic colormaps

import dfm_tools as dfmt

# Color palette
LAND_COLOR  = '#b8b8b8'   # neutral medium gray for filled LDB land polygons
COAST_COLOR = '#4a4a4a'   # darker gray for coastline outline
BG_COLOR    = '#f4f4f4'   # very light gray for plot background (was brown-tan, ugly)

# Standard oceanographic colormaps per quantity
# (cmocean: scientifically-designed for these specific variables)
CMAP_WL   = cmo.balance   # diverging blue-white-red, centered on 0 (sea surface anomaly)
CMAP_HRMS = cmo.amp       # sequential, designed for wave amplitudes
CMAP_SAL  = cmo.haline    # sequential, designed for salinity (cyan -> deep purple)
CMAP_TEM  = cmo.thermal   # sequential, temperatures
CMAP_BATHY = cmo.deep     # for bathymetry depths

# Equivalent plotly colorscales (manually approximated from cmocean if needed)
PLOTLY_WL   = 'RdBu_r'
PLOTLY_HRMS = 'Reds'
PLOTLY_SAL  = 'Viridis'

ROOT = Path(__file__).resolve().parent.parent if '__file__' in dir() else Path.cwd()
MODEL_OUT = ROOT / 'model' / 'dflowfm_v04AE_d10d12' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
INSITU    = ROOT / 'data' / 'processed' / 'insitu_2025-26'
BUNDLE    = ROOT / 'outputs' / 'wetwise_tab'
for sub in ('interactive', 'static', 'data', 'animations'):
    (BUNDLE / sub).mkdir(parents=True, exist_ok=True)

WINDOW = ('2025-07-10 00:00', '2025-07-12 00:00')
STATIONS = {'AE': 'AltaVilaEst', 'BN': 'BocaNord', 'BS': 'BocaSud'}
COLOR_OBS   = '#1f77b4'
COLOR_MODEL = '#d62728'

print(f'ROOT      = {ROOT}')
print(f'MODEL_OUT = {MODEL_OUT}')
print(f'BUNDLE    = {BUNDLE}')

# %% load his.nc — station time series
his = xr.open_dataset(MODEL_OUT / 'Stagnone_dxy01_15m_0000_his.nc')
station_names = [s.decode().strip() if isinstance(s, bytes) else s.strip()
                 for s in his.station_name.values]
station_idx = {n: i for i, n in enumerate(station_names)}
print(f'his.nc stations: {station_names}')
print(f'his.nc time: {his.time.values[0]} -> {his.time.values[-1]} ({len(his.time)} pts)')

# %% load in-situ CSVs
def load_insitu_wl(station_short, window):
    df = pd.read_csv(INSITU / f'{station_short}_wl_UTC.csv',
                     index_col=0, parse_dates=True)
    return df.loc[window[0]:window[1], 'h_m']

insitu_wl = {s: load_insitu_wl(s, WINDOW) for s in STATIONS}
for s, ts in insitu_wl.items():
    print(f'{s} in-situ: {len(ts)} samples, mean={ts.mean():+.4f}, std={ts.std():.4f} m')

# %% align model + insitu, compute metrics
def metrics(model_ts, obs_ts):
    """Returns dict with bias, RMSE, RMSE_anom, std ratio, correlation."""
    aligned = pd.DataFrame({'model': model_ts, 'obs': obs_ts}).dropna()
    if len(aligned) == 0:
        return None
    diff = aligned['model'] - aligned['obs']
    m_anom = aligned['model'] - aligned['model'].mean()
    o_anom = aligned['obs']   - aligned['obs'].mean()
    anom_diff = m_anom - o_anom
    return {
        'n_points'   : int(len(aligned)),
        'bias_m'     : float(diff.mean()),
        'rmse_m'     : float((diff**2).mean()**0.5),
        'rmse_anom_m': float((anom_diff**2).mean()**0.5),
        'std_model_m': float(aligned['model'].std()),
        'std_obs_m'  : float(aligned['obs'].std()),
        'corr'       : float(aligned.corr().iloc[0, 1]),
    }

# Build dict: station -> {'model': series, 'obs': series, 'metrics': dict}
station_data = {}
for short, full in STATIONS.items():
    sidx = station_idx[full]
    model_wl = his['waterlevel'].isel(station=sidx).to_pandas()
    obs_10min = insitu_wl[short].resample('10min').mean()
    m = metrics(model_wl, obs_10min)
    station_data[short] = dict(model=model_wl, obs=obs_10min, metrics=m, full_name=full)
    print(f'{short} ({full}): n={m["n_points"]:3d}  '
          f'bias={m["bias_m"]:+.4f} m  '
          f'RMSE={m["rmse_m"]:.4f} m  '
          f'RMSE_anom={m["rmse_anom_m"]:.4f} m  '
          f'corr={m["corr"]:.3f}')

# %% Plotly interactive: WL 3 stations stacked
fig = go.Figure()
panel_offsets = {'AE': 0.30, 'BN': 0.00, 'BS': -0.30}  # vertical offset per station

for short, info in station_data.items():
    off = panel_offsets[short]
    # in-situ (observation)
    fig.add_trace(go.Scatter(
        x=info['obs'].index, y=info['obs'].values + off,
        mode='lines', name=f'{short} obs',
        line=dict(color=COLOR_OBS, width=1.4),
        legendgroup=short, legendgrouptitle_text=short,
    ))
    # model
    fig.add_trace(go.Scatter(
        x=info['model'].index, y=info['model'].values + off,
        mode='lines', name=f'{short} model',
        line=dict(color=COLOR_MODEL, width=1.6, dash='dash'),
        legendgroup=short,
    ))
    # zero baseline of this panel (annotation only)
    fig.add_hline(y=off, line=dict(color='gray', width=0.5, dash='dot'),
                  annotation_text=f'{short} ({info["full_name"]}) baseline + {off:+.2f} m',
                  annotation_position='right')

fig.update_layout(
    title='Water Level — model vs in-situ (Jul 10-12 2025)',
    xaxis_title='Time (UTC)',
    yaxis_title='h (m) + offset per station for visual clarity',
    height=520, width=1100,
    template='plotly_white',
    legend=dict(groupclick='toggleitem'),
    margin=dict(l=60, r=180, t=60, b=50),
)

out_html = BUNDLE / 'interactive' / 'wl_3stations.html'
fig.write_html(out_html, include_plotlyjs='cdn', full_html=True)
print(f'wrote {out_html} ({out_html.stat().st_size/1024:.1f} KB)')

# (the old 3-panel static PNG was replaced by per-station PNGs further down)

# %% Save validation metrics JSON
metrics_json = {
    'run_id': 'v04AE_d10d12',
    'window_start': WINDOW[0],
    'window_end':   WINDOW[1],
    'reference_obs': 'data/processed/insitu_2025-26 (4 stations 2025-26 in-situ)',
    'stations': {
        short: {
            'full_name': info['full_name'],
            'his_index': int(station_idx[info['full_name']]),
            **info['metrics'],
        }
        for short, info in station_data.items()
    },
}
out_json = BUNDLE / 'data' / 'validation_metrics.json'
out_json.write_text(json.dumps(metrics_json, indent=2))
print(f'wrote {out_json} ({out_json.stat().st_size} B)')
print()
print(json.dumps(metrics_json, indent=2))

# %% Open map.nc partitioned (8 ranks merged)
uds = dfmt.open_partitioned_dataset(str(MODEL_OUT / 'Stagnone_dxy01_15m_0*_map.nc'))
print(f'map.nc time range: {uds.time.values[0]} -> {uds.time.values[-1]} ({len(uds.time)} pts)')
print(f'spatial dims: {dict(uds.sizes)}')

# %% Build grid + coastlines + regrid helper
import matplotlib.tri as mtri
from matplotlib.animation import FuncAnimation
from matplotlib.colors import TwoSlopeNorm
import matplotlib.colors as mcolors

V04AE_DIR = ROOT / 'model' / 'dflowfm_v04AE'

# face center coordinates from uds (xugrid via uds.grid)
face_x = uds.grid.face_coordinates[:, 0]
face_y = uds.grid.face_coordinates[:, 1]
print(f'n faces (cells): {len(face_x)}')
print(f'lon range: {face_x.min():.4f} -> {face_x.max():.4f}')
print(f'lat range: {face_y.min():.4f} -> {face_y.max():.4f}')

# Bounding boxes
LAGOON_BBOX = dict(lon_min=12.42, lon_max=12.49,
                   lat_min=37.83, lat_max=37.97)
DOMAIN_BBOX = dict(lon_min=float(face_x.min()) - 0.005, lon_max=float(face_x.max()) + 0.005,
                   lat_min=float(face_y.min()) - 0.005, lat_max=float(face_y.max()) + 0.005)

PLOTLY_TIME_STRIDE = 2   # subsample frames in Plotly animations

# Triangulation (used by interpolator below)
triang = mtri.Triangulation(face_x, face_y)

# Mask long-edge triangles: these span across mesh holes (dry land cells removed
# via illegalcells_dry.pol or coastline boundaries) and produce ghost values
# during linear interpolation. After masking, those areas become NaN -> drawn as
# LAND_COLOR via cmap.set_bad().
def _max_edge_len(triang):
    x, y = triang.x, triang.y
    tv = triang.triangles
    dxs = np.column_stack([x[tv[:, 0]] - x[tv[:, 1]],
                           x[tv[:, 1]] - x[tv[:, 2]],
                           x[tv[:, 2]] - x[tv[:, 0]]])
    dys = np.column_stack([y[tv[:, 0]] - y[tv[:, 1]],
                           y[tv[:, 1]] - y[tv[:, 2]],
                           y[tv[:, 2]] - y[tv[:, 0]]])
    return np.sqrt(dxs**2 + dys**2).max(axis=1)

edge_len = _max_edge_len(triang)
# Threshold: typical Stagnone face spacing is ~15 m at fine lagoon, ~400 m offshore.
# Increased to 5 km — only catches absurd cross-domain triangles. Real coastline
# is now shown by filled LDB polygons (set in draw_frame, not via tri mask).
LONG_EDGE_DEG = 0.05
tri_mask = edge_len > LONG_EDGE_DEG
triang.set_mask(tri_mask)
print(f'Triangulation built ({len(triang.triangles)} triangles); '
      f'masked {tri_mask.sum()} long-edge ({100*tri_mask.sum()/len(triang.triangles):.1f}%) '
      f'over threshold {LONG_EDGE_DEG} deg.')
print(f'edge stats: p50={np.median(edge_len):.5f}, p95={np.percentile(edge_len,95):.5f}, '
      f'max={edge_len.max():.4f} deg')

# %% Coastlines from .ldb
def load_ldb_polygons(path):
    """Parse Deltares .ldb (land boundary) file -> list of (xs, ys) arrays."""
    polys = []
    with open(path) as f:
        lines = [l.rstrip() for l in f]
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1; continue
        # header line: polygon name
        i += 1
        if i >= len(lines):
            break
        parts = lines[i].split()
        n = int(parts[0])
        i += 1
        xs, ys = [], []
        for j in range(n):
            xy = lines[i + j].split()
            xs.append(float(xy[0])); ys.append(float(xy[1]))
        i += n
        polys.append((np.array(xs), np.array(ys)))
    return polys

coast_polys_sicily = load_ldb_polygons(V04AE_DIR / 'sicily2.ldb')
coast_polys_stagnone = load_ldb_polygons(V04AE_DIR / 'Stagnone_dxy01_15m.ldb')
coast_polys = coast_polys_sicily + coast_polys_stagnone
# Filter to polygons that intersect our DOMAIN_BBOX (most of Sicily is outside)
def poly_in_bbox(xs, ys, bbox):
    return ((xs.max() >= bbox['lon_min']) and (xs.min() <= bbox['lon_max']) and
            (ys.max() >= bbox['lat_min']) and (ys.min() <= bbox['lat_max']))
coast_in_domain = [(x, y) for x, y in coast_polys if poly_in_bbox(x, y, DOMAIN_BBOX)]
print(f'coast polygons: sicily={len(coast_polys_sicily)}, '
      f'stagnone={len(coast_polys_stagnone)}, in domain bbox: {len(coast_in_domain)}')

# %% Helpers: make grid + regrid for any bbox
def make_grid(bbox, nx, ny):
    lon = np.linspace(bbox['lon_min'], bbox['lon_max'], nx)
    lat = np.linspace(bbox['lat_min'], bbox['lat_max'], ny)
    return lon, lat, *np.meshgrid(lon, lat)

def regrid_face_to(values_1d, LON2, LAT2):
    """LinearTriInterpolator: respects mesh topology, NaN outside mesh = land mask."""
    interp = mtri.LinearTriInterpolator(triang, values_1d)
    return interp(LON2, LAT2)

# Pre-compute grids for the two main views
LON_LAG, LAT_LAG, LON2_LAG, LAT2_LAG = make_grid(LAGOON_BBOX, 80, 120)
LON_DOM, LAT_DOM, LON2_DOM, LAT2_DOM = make_grid(DOMAIN_BBOX, 200, 140)
print(f'lagoon grid: {LON2_LAG.shape}, domain grid: {LON2_DOM.shape}')

# %% Helper: render MP4 animation via tricontourf (smooth continuous shades on
# the masked triangulation; no regridding, no patches, respects mesh holes)
def render_mp4_animation(var_da, out_path, title, bbox,
                         coast_polys=None,
                         cmap='viridis', vmin=None, vmax=None,
                         cbar_label='', center_zero=False,
                         figsize=(10, 7), stations=None, n_levels=24,
                         LON2=None, LAT2=None):  # LON2/LAT2 kept for backward compat (unused now)
    """var_da: xarray DataArray with dims (time, face_dim).
    bbox: dict with lon/lat bounds for axis limits.
    coast_polys: list of (xs, ys) tuples drawn as land mask overlay.
    stations: dict {short_name: (lon, lat)} marker points."""
    times = pd.to_datetime(var_da.time.values)
    n_t = len(times)

    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    ax.set_facecolor(LAND_COLOR)  # gray under any NaN/holes from pcolormesh

    # robust auto-range via 1/99 percentiles (resistant to outliers)
    if vmin is None or vmax is None:
        # xugrid often returns read-only views that break np.nanpercentile's internal
        # _lerp. Manual sort-based percentile is bulletproof.
        arr = np.array(var_da.values, copy=True).ravel()
        finite = np.sort(arr[np.isfinite(arr)])
        n = len(finite)
        p1 = float(finite[int(0.01 * n)])
        p99 = float(finite[int(0.99 * n)])
        if center_zero:
            absmax = max(abs(p1), abs(p99))
            vmin, vmax = -absmax, absmax
        else:
            if vmin is None: vmin = p1
            if vmax is None: vmax = p99

    norm = (TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
            if center_zero else mcolors.Normalize(vmin=vmin, vmax=vmax))

    # Accept either a matplotlib Colormap object or a name string
    if hasattr(cmap, '_segmentdata') or hasattr(cmap, 'colors'):
        cmap_obj = cmap.copy() if hasattr(cmap, 'copy') else cmap
    else:
        cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad(LAND_COLOR)

    levels = np.linspace(vmin, vmax, n_levels)

    # Per-frame dry-cell masking via mesh2d_waterdepth (if available)
    have_depth = 'mesh2d_waterdepth' in uds.data_vars
    DRY_DEPTH_M = 0.01  # cells with waterdepth < 1 cm treated as land for viz

    def draw_frame(frame_idx):
        """Clear axis and redraw entire frame — tricontourf is not naturally updatable."""
        ax.clear()
        ax.set_facecolor(BG_COLOR)
        vals = np.asarray(var_da.isel(time=frame_idx).values).astype(np.float32)

        # Build per-frame triangle mask: static long-edge + NaN + dry-cell
        bad_face = ~np.isfinite(vals)
        if have_depth:
            d = np.asarray(uds['mesh2d_waterdepth'].isel(time=frame_idx).values)
            bad_face = bad_face | (d < DRY_DEPTH_M) | ~np.isfinite(d)
        if bad_face.any():
            tris_bad = np.any(bad_face[triang.triangles], axis=1)
            triang.set_mask(tri_mask | tris_bad)
        else:
            triang.set_mask(tri_mask)

        # tricontourf cannot accept NaN at face values in unmasked triangles -> fill safe
        vals_safe = np.where(np.isfinite(vals), vals, vmin)
        vals_clip = np.clip(vals_safe, vmin, vmax)
        cs = ax.tricontourf(triang, vals_clip, levels=levels, cmap=cmap_obj, extend='both')

        # Restore static mask for next iter's combined mask computation
        triang.set_mask(tri_mask)

        # Fill LDB land polygons on top (zorder=10 so they cover any spurious values
        # inside islands / mainland)
        if coast_polys:
            for xs, ys in coast_polys:
                ax.fill(xs, ys, facecolor=LAND_COLOR, edgecolor=COAST_COLOR,
                        linewidth=0.5, zorder=10)
        # Station markers
        if stations:
            for s, (lon, lat) in stations.items():
                if lon is None or lat is None: continue
                if (bbox['lon_min'] <= lon <= bbox['lon_max'] and
                    bbox['lat_min'] <= lat <= bbox['lat_max']):
                    ax.plot(lon, lat, marker='o', mfc='red', mec='black', ms=7, mew=0.8)
                    ax.annotate(s, (lon, lat), xytext=(6, 6),
                                textcoords='offset points', fontsize=9, fontweight='bold',
                                bbox=dict(boxstyle='round,pad=0.15', fc='white', alpha=0.85))
        ax.set_xlim(bbox['lon_min'], bbox['lon_max'])
        ax.set_ylim(bbox['lat_min'], bbox['lat_max'])
        ax.set_aspect('equal')
        ax.set_xlabel('Longitude (°E)')
        ax.set_ylabel('Latitude (°N)')
        ax.set_title(f'{title}\n{times[frame_idx]:%Y-%m-%d %H:%M} UTC')
        return cs

    # Draw frame 0 to establish colorbar
    cs0 = draw_frame(0)
    fig.colorbar(cs0, ax=ax, label=cbar_label, shrink=0.85)

    def update(frame_idx):
        draw_frame(frame_idx)
        # don't return artists — full re-draw is the simpler/safer pattern
        return []

    anim = FuncAnimation(fig, update, frames=n_t, blit=False, interval=120)
    # Higher dpi + CRF for sharper MP4 (yuv420p kept for broad browser compat)
    writer = FFMpegWriter(fps=8, codec='h264',
                          extra_args=['-pix_fmt', 'yuv420p', '-crf', '18'])
    anim.save(str(out_path), writer=writer, dpi=160)
    plt.close(fig)
    print(f'wrote {out_path} ({out_path.stat().st_size/1024/1024:.2f} MB)')

# %% Read station coords from his.nc (geom_node_coord*)
station_coords = {}
sx = his.station_geom_node_coordx.values if hasattr(his, 'station_geom_node_coordx') else None
sy = his.station_geom_node_coordy.values if hasattr(his, 'station_geom_node_coordy') else None
for short, full in STATIONS.items():
    idx_s = station_idx[full]
    if sx is not None and idx_s < len(sx):
        station_coords[short] = (float(sx[idx_s]), float(sy[idx_s]))
    else:
        station_coords[short] = (None, None)
print('Station coords (from his.nc):')
for s, (x, y) in station_coords.items():
    print(f'  {s} ({STATIONS[s]}): lon={x:.5f}, lat={y:.5f}')

# %% Pre-compute WL spatial regridded for all frames (used by per-station HTML)
print('\nPre-regridding WL spatial frames (domain, lagoon, per-station)...')
times_full = pd.to_datetime(uds.time.values)
t_indices = list(range(0, len(times_full), PLOTLY_TIME_STRIDE))
print(f'  total times: {len(times_full)}, sampled to: {len(t_indices)} (stride={PLOTLY_TIME_STRIDE})')

# Pre-extract face values for WL once (avoid xarray re-isel overhead)
wl_da = uds['mesh2d_s1']
wl_face_arr = wl_da.values  # shape (time, faces)

# %% Helper: render per-station synced HTML (timeseries + heatmap + vline)
from plotly.subplots import make_subplots

def render_station_dashboard(short, full_name, station_data, station_lon, station_lat,
                             wl_face_arr, t_indices, times_full):
    """Build a per-station dashboard HTML with synchronized:
    - Left: WL time series (obs + model) with a moving vertical-line marker
    - Right: WL heatmap zoomed on the station, animated
    Slider + play/pause controls drive both panels."""
    # Zoom window: ±0.025 deg (~2.5 km) around the station
    half = 0.025
    bbox_st = dict(lon_min=station_lon - half, lon_max=station_lon + half,
                   lat_min=station_lat - half, lat_max=station_lat + half)
    lon_st, lat_st, LON2_st, LAT2_st = make_grid(bbox_st, 100, 100)

    # Pre-regrid WL at the station's window for each sampled timestep
    # Mask dry cells (waterdepth < DRY_DEPTH_M) before regrid to avoid bogus values
    have_depth_local = 'mesh2d_waterdepth' in uds.data_vars
    DRY_DEPTH_M_local = 0.01
    frames_Z = []
    for ti in t_indices:
        wl_faces = np.asarray(wl_face_arr[ti], dtype=np.float32).copy()
        if have_depth_local:
            d = np.asarray(uds['mesh2d_waterdepth'].isel(time=ti).values)
            wl_faces[d < DRY_DEPTH_M_local] = np.nan
        Z = regrid_face_to(wl_faces, LON2_st, LAT2_st).astype(np.float32)
        frames_Z.append(Z)

    # Fixed physical range for WL (overrides auto-range; consistent across stations)
    zmin, zmax = -0.5, 0.5

    frame_times = [times_full[i] for i in t_indices]
    info = station_data[short]
    m = info['metrics']

    # Build subplot figure
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.58, 0.42],
        horizontal_spacing=0.10,
        subplot_titles=[
            f'{short} WL — model vs in-situ (sync marker = video frame)',
            f'{short} WL field (±2.5 km zoom)',
        ],
    )

    # Trace 0: obs
    fig.add_trace(go.Scatter(
        x=info['obs'].index, y=info['obs'].values, mode='lines',
        name='in-situ', line=dict(color=COLOR_OBS, width=1.4),
    ), row=1, col=1)
    # Trace 1: model
    fig.add_trace(go.Scatter(
        x=info['model'].index, y=info['model'].values, mode='lines',
        name='model', line=dict(color=COLOR_MODEL, width=1.6, dash='dash'),
    ), row=1, col=1)
    # Trace 2: vline marker (initial frame)
    y_lo = min(info['obs'].min(), info['model'].min()) - 0.01
    y_hi = max(info['obs'].max(), info['model'].max()) + 0.01
    fig.add_trace(go.Scatter(
        x=[frame_times[0], frame_times[0]], y=[y_lo, y_hi],
        mode='lines', name='now',
        line=dict(color='black', width=1.8, dash='dot'),
        hoverinfo='skip', showlegend=False,
    ), row=1, col=1)
    # Trace 3: heatmap (initial frame) — use NaN-aware Heatmap with plot bgcolor as land
    fig.add_trace(go.Heatmap(
        z=frames_Z[0], x=lon_st, y=lat_st,
        colorscale=PLOTLY_WL, zmin=zmin, zmax=zmax,
        colorbar=dict(title='WL (m)', len=0.75, x=1.02),
        showscale=True, name='wl',
        hovertemplate='lon=%{x:.4f}<br>lat=%{y:.4f}<br>WL=%{z:.3f} m<extra></extra>',
    ), row=1, col=2)
    # Trace 4: LDB land polygons clipped to this station zoom (filled)
    coast_zoom = [(xs, ys) for xs, ys in coast_polys
                  if poly_in_bbox(xs, ys, bbox_st)]
    if coast_zoom:
        # Single Scatter with NaN-separated polygons -> renders as multiple filled regions
        coast_x, coast_y = [], []
        for xs, ys in coast_zoom:
            coast_x.extend(xs.tolist() + [None])
            coast_y.extend(ys.tolist() + [None])
        fig.add_trace(go.Scatter(
            x=coast_x, y=coast_y,
            fill='toself', fillcolor=LAND_COLOR,
            line=dict(color=COAST_COLOR, width=0.6),
            mode='lines', name='land',
            showlegend=False, hoverinfo='skip',
        ), row=1, col=2)

    # Trace 5: station marker
    fig.add_trace(go.Scatter(
        x=[station_lon], y=[station_lat], mode='markers+text',
        marker=dict(color='red', size=11, line=dict(color='black', width=1.2)),
        text=[short], textposition='top right',
        textfont=dict(size=12, color='black'),
        hoverinfo='text', hovertext=[full_name], showlegend=False,
    ), row=1, col=2)

    # Frames: update trace 2 (vline) + trace 3 (heatmap)
    frames = [
        go.Frame(
            data=[
                go.Scatter(x=[frame_times[i], frame_times[i]], y=[y_lo, y_hi],
                           mode='lines', line=dict(color='black', width=1.8, dash='dot')),
                go.Heatmap(z=frames_Z[i], x=lon_st, y=lat_st,
                           colorscale=PLOTLY_WL, zmin=zmin, zmax=zmax,
                           colorbar=dict(title='WL (m)', len=0.75, x=1.02)),
            ],
            traces=[2, 3],
            name=frame_times[i].strftime('%Y-%m-%d %H:%M'),
        )
        for i in range(len(t_indices))
    ]
    fig.update(frames=frames)

    # Layout: equal aspect on right, time axis on left, slider+buttons at bottom
    fig.update_yaxes(scaleanchor='x2', scaleratio=1, row=1, col=2)
    fig.update_xaxes(title_text='Time (UTC)', row=1, col=1)
    fig.update_yaxes(title_text='WL (m)', row=1, col=1)
    fig.update_xaxes(title_text='Longitude (°E)', row=1, col=2,
                     range=[bbox_st['lon_min'], bbox_st['lon_max']])
    fig.update_yaxes(title_text='Latitude (°N)', row=1, col=2,
                     range=[bbox_st['lat_min'], bbox_st['lat_max']])

    metric_txt = (
        f'<b>{short} ({full_name})</b> — '
        f'bias = {m["bias_m"]*1000:+.0f} mm  |  '
        f'RMSE = {m["rmse_m"]*1000:.0f} mm  |  '
        f'RMSE_anom = {m["rmse_anom_m"]*1000:.0f} mm  |  '
        f'corr = {m["corr"]:+.3f}  |  '
        f'n = {m["n_points"]}'
    )

    fig.update_layout(
        title=dict(text=metric_txt, x=0.01, xanchor='left',
                   font=dict(size=12)),
        height=560, width=1280,
        template='plotly_white',
        plot_bgcolor='white',  # white background; land shown via filled LDB polygons
        margin=dict(l=70, r=140, t=80, b=110),
        updatemenus=[dict(
            type='buttons', showactive=False, x=0.0, y=-0.16, direction='left',
            buttons=[
                # Slower frame (350ms) gives the browser time to redraw the heatmap
                # on each step (the previous 130ms was too fast — heatmap stayed blank
                # during play). transition.duration=0 means jumps not animated tweens.
                dict(label='Play', method='animate',
                     args=[None, dict(frame=dict(duration=350, redraw=True),
                                      transition=dict(duration=0),
                                      fromcurrent=True, mode='immediate')]),
                dict(label='Pause', method='animate',
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                        mode='immediate')]),
            ],
        )],
        sliders=[dict(
            active=0,
            currentvalue=dict(prefix='t = '),
            x=0.05, y=-0.08, len=0.92,
            steps=[dict(label=f.name, method='animate',
                        args=[[f.name], dict(mode='immediate',
                                             frame=dict(duration=0, redraw=True),
                                             transition=dict(duration=0))])
                   for f in frames],
        )],
    )

    out_html = BUNDLE / 'interactive' / f'station_{short}_wl_dashboard.html'
    # config: enable scrollZoom for the heatmap subplot, and Plotly handles the
    # rest (modeBar shows reset, zoom, pan icons).
    fig.write_html(out_html, include_plotlyjs='cdn', full_html=True,
                   config=dict(scrollZoom=True, displayModeBar=True,
                               modeBarButtonsToRemove=['lasso2d', 'select2d']))
    print(f'  wrote {out_html.name}  ({out_html.stat().st_size/1024:.1f} KB)')
    return out_html

# %% Per-station static PNG (graph + map snapshot side-by-side)
def render_station_static_png(short, full_name, station_data, station_lon, station_lat,
                              wl_face_arr, mid_t):
    """A static 2-panel PNG: WL timeseries (with stats title) + WL map snapshot at t_mid."""
    half = 0.025
    bbox_st = dict(lon_min=station_lon - half, lon_max=station_lon + half,
                   lat_min=station_lat - half, lat_max=station_lat + half)
    _, _, LON2_st, LAT2_st = make_grid(bbox_st, 100, 100)
    # mask dry cells before regrid
    wl_faces_mid = np.asarray(wl_face_arr[mid_t], dtype=np.float32).copy()
    if 'mesh2d_waterdepth' in uds.data_vars:
        d = np.asarray(uds['mesh2d_waterdepth'].isel(time=mid_t).values)
        wl_faces_mid[d < 0.01] = np.nan
    Z_mid = regrid_face_to(wl_faces_mid, LON2_st, LAT2_st)

    info = station_data[short]
    m = info['metrics']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={'width_ratios': [1.4, 1]})
    # Left: time series
    ax1.plot(info['obs'].index, info['obs'].values, color=COLOR_OBS,
             lw=1.4, label='in-situ')
    ax1.plot(info['model'].index, info['model'].values, color=COLOR_MODEL,
             lw=1.6, ls='--', label='model')
    ax1.axvline(times_full[mid_t], color='k', ls=':', lw=1.2, alpha=0.7)
    ax1.text(times_full[mid_t], ax1.get_ylim()[1]*0.95, ' map snapshot',
             fontsize=8, color='k')
    ax1.set_xlabel('Time (UTC)')
    ax1.set_ylabel('Water Level (m)')
    ax1.grid(alpha=0.3); ax1.legend(loc='upper right', fontsize=9)
    ax1.set_title(
        f'bias = {m["bias_m"]*1000:+.0f} mm  |  '
        f'RMSE = {m["rmse_m"]*1000:.0f} mm  |  '
        f'RMSE_anom = {m["rmse_anom_m"]*1000:.0f} mm  |  '
        f'corr = {m["corr"]:+.3f}  |  n = {m["n_points"]}',
        fontsize=10,
    )

    # Right: map snapshot at mid_t — light bg + WL pcolormesh + filled LDB on top
    cmap = CMAP_WL.copy() if hasattr(CMAP_WL, 'copy') else CMAP_WL
    cmap.set_bad(BG_COLOR)
    ax2.set_facecolor(BG_COLOR)
    # Fixed range to keep all per-station PNGs comparable
    im = ax2.pcolormesh(LON2_st, LAT2_st, Z_mid, cmap=cmap,
                        vmin=-0.5, vmax=0.5, shading='nearest')
    fig.colorbar(im, ax=ax2, label='WL (m)', shrink=0.85)
    # Filled LDB land polygons on top (cover spurious values inside islands)
    for xs, ys in coast_in_domain:
        if poly_in_bbox(xs, ys, bbox_st):
            ax2.fill(xs, ys, facecolor=LAND_COLOR, edgecolor=COAST_COLOR,
                     linewidth=0.5, zorder=10)
    ax2.plot(station_lon, station_lat, 'o', mfc='red', mec='black', ms=10, mew=1)
    ax2.annotate(short, (station_lon, station_lat), xytext=(8, 8),
                 textcoords='offset points', fontsize=11, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.85))
    ax2.set_xlim(bbox_st['lon_min'], bbox_st['lon_max'])
    ax2.set_ylim(bbox_st['lat_min'], bbox_st['lat_max'])
    ax2.set_aspect('equal')
    ax2.set_xlabel('Longitude (°E)'); ax2.set_ylabel('Latitude (°N)')
    ax2.set_title(f'WL field @ {times_full[mid_t]:%Y-%m-%d %H:%M} UTC')

    fig.suptitle(f'{short} ({full_name}) — v04AE_d10d12 Jul 10-12 2025', y=1.005)
    fig.tight_layout()
    out_png = BUNDLE / 'static' / f'station_{short}_wl_compare.png'
    fig.savefig(out_png, dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'  wrote {out_png.name}  ({out_png.stat().st_size/1024:.1f} KB)')

# %% Build per-station outputs (HTML + PNG x 3)
print('\nBuilding per-station dashboards + PNGs...')
mid_t_idx = len(times_full) // 2  # mid-window for static snapshot
for short, (lon_s, lat_s) in station_coords.items():
    if lon_s is None or lat_s is None:
        print(f'skip {short}: missing coords'); continue
    print(f'\n--- {short} ({STATIONS[short]}) ---')
    render_station_dashboard(short, STATIONS[short], station_data, lon_s, lat_s,
                             wl_face_arr, t_indices, times_full)
    render_station_static_png(short, STATIONS[short], station_data, lon_s, lat_s,
                              wl_face_arr, mid_t_idx)

# %% Full-domain MP4 animations (WL + Hrms + Salinity top-layer)
print('\nRendering full-domain MP4 animations (with coast + land mask + cmocean cmaps)...')
# WL — cmocean.balance, diverging, FIXED range -0.5 to +0.5 m
# (auto-range was picking up outliers from dry-cells; now we mask dry via waterdepth
#  and fix the colorbar to the physical tidal/storm-surge range typical of Stagnone)
render_mp4_animation(
    wl_da, BUNDLE / 'animations' / 'waterlevel.mp4',
    title='Water Level (s1) — v04AE_d10d12 (Jul 10-12)',
    LON2=LON2_DOM, LAT2=LAT2_DOM, bbox=DOMAIN_BBOX,
    coast_polys=coast_in_domain,
    cmap=CMAP_WL, vmin=-0.5, vmax=0.5, cbar_label='WL (m)',
    figsize=(10, 8),
    stations=station_coords,
)

# Hrms — cmocean.amp, sequential for wave amplitudes
render_mp4_animation(
    uds['mesh2d_hwav'], BUNDLE / 'animations' / 'hrms_waves.mp4',
    title='Wave Hrms — v04AE_d10d12',
    LON2=LON2_DOM, LAT2=LAT2_DOM, bbox=DOMAIN_BBOX,
    coast_polys=coast_in_domain,
    cmap=CMAP_HRMS, vmin=0, vmax=1.2, cbar_label='Hrms (m)',
    figsize=(10, 8),
    stations=station_coords,
)

# Salinity top-layer — cmocean.haline, standard for salinity
sa_var = uds['mesh2d_sa1']
layer_dims = [d for d in sa_var.dims if 'layer' in d.lower()]
sa_top = sa_var.isel({layer_dims[0]: -1}) if layer_dims else sa_var
render_mp4_animation(
    sa_top, BUNDLE / 'animations' / 'salinity_top.mp4',
    title='Salinity (top layer) — v04AE_d10d12',
    LON2=LON2_DOM, LAT2=LAT2_DOM, bbox=DOMAIN_BBOX,
    coast_polys=coast_in_domain,
    cmap=CMAP_SAL, vmin=37, vmax=46, cbar_label='Salinity (ppt)',
    figsize=(10, 8),
    stations=station_coords,
)

# %% Domain overview (bathy + stations + coast)
fig_dom, ax_dom = plt.subplots(figsize=(10, 8))
ax_dom.set_facecolor(BG_COLOR)
bl = uds['mesh2d_flowelem_bl'].values
# tricontourf directly on triangulation (no regrid needed)
_bl_finite = np.sort(bl[np.isfinite(bl)])
_n = len(_bl_finite)
bl_lo, bl_hi = float(_bl_finite[int(0.01 * _n)]), float(_bl_finite[int(0.99 * _n)])
levels_bl = np.linspace(bl_lo, bl_hi, 22)
bl_safe = np.where(np.isfinite(bl), bl, bl_lo)
cmap_bl = cmo.deep_r.copy()
cs_bl = ax_dom.tricontourf(triang, np.clip(bl_safe, bl_lo, bl_hi),
                            levels=levels_bl, cmap=cmap_bl, extend='both')
fig_dom.colorbar(cs_bl, ax=ax_dom, label='Bed level (m, +ve up)', shrink=0.85)
# Filled LDB land overlay
for xs, ys in coast_in_domain:
    ax_dom.fill(xs, ys, facecolor=LAND_COLOR, edgecolor=COAST_COLOR,
                linewidth=0.5, zorder=10)
for s, (lon, lat) in station_coords.items():
    ax_dom.plot(lon, lat, 'ko', markersize=9, markerfacecolor='red', markeredgewidth=1.5)
    ax_dom.annotate(s, (lon, lat), xytext=(8, 8), textcoords='offset points',
                    fontsize=11, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.85))
ax_dom.set_xlim(DOMAIN_BBOX['lon_min'], DOMAIN_BBOX['lon_max'])
ax_dom.set_ylim(DOMAIN_BBOX['lat_min'], DOMAIN_BBOX['lat_max'])
ax_dom.set_aspect('equal')
ax_dom.set_xlabel('Longitude (°E)')
ax_dom.set_ylabel('Latitude (°N)')
ax_dom.set_title('Stagnone domain — bathymetry + coast + obs stations')
fig_dom.tight_layout()
out_dom = BUNDLE / 'static' / 'domain_overview.png'
fig_dom.savefig(out_dom, dpi=130, bbox_inches='tight')
plt.close(fig_dom)
print(f'wrote {out_dom} ({out_dom.stat().st_size/1024:.1f} KB)')

# %% Done — bundle inventory
print(f'\nBundle at {BUNDLE}:')
for p in sorted(BUNDLE.rglob('*')):
    if p.is_file():
        size = p.stat().st_size
        unit = 'MB' if size > 1024*1024 else 'KB'
        v = size / (1024*1024) if unit == 'MB' else size / 1024
        print(f'  {p.relative_to(BUNDLE)}  ({v:.1f} {unit})')
