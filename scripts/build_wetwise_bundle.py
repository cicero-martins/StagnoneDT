"""Wetwise tab bundle v2 — interactive Plotly tabs replacing MP4 animations.

Generates a self-contained HTML bundle for a given publish day:
  outputs/wetwise_tab/d<YYYY-MM-DD>/
  ├── index.html              entry point with tabbed UI
  ├── manifest.json           timestamp + asset list
  └── data/
      └── validation_metrics.json

The publish window is the last 24h of the model run. Per spec
[wetwise_tab_v2_spec memory]:
  - 3 tabs: WL (full-width, first), Velocity (colored quiver), Hwav (greens)
  - WL chart + spatial map sync via single slider (move together in time)
  - Per-station section with sparkline (last 7d, 1pt/hour, clickable to navigate days)
  - Drop salinity tab

Usage:
    python scripts/build_wetwise_bundle.py --model-out <DFM_OUTPUT> --publish-day 2025-07-09

For testing with v04AE_nodm:
    python scripts/build_wetwise_bundle.py \\
        --model-out model/dflowfm_v04AE_nodm/DFM_OUTPUT_Stagnone_dxy01_15m \\
        --publish-day 2025-07-09 \\
        --output-dir outputs/wetwise_tab_v2_test
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import xarray as xr
import dfm_tools as dfmt
from scipy.interpolate import griddata
from scipy.spatial import cKDTree
import plotly.graph_objects as go
import plotly.io as pio


# ---------- regrid helpers ----------

LON_MIN_LAGOON, LON_MAX_LAGOON = 12.40, 12.50
LAT_MIN_LAGOON, LAT_MAX_LAGOON = 37.79, 37.92
LON_MIN_FULL,   LON_MAX_FULL   = 11.95, 12.55
LAT_MIN_FULL,   LAT_MAX_FULL   = 37.70, 38.10

DX_LAGOON = 0.0008  # ~88 m
DY_LAGOON = 0.0008
DX_FULL = 0.004     # ~440 m
DY_FULL = 0.004

LAND_BL_THRESH = -0.05
KDIST_DEG = 0.005


def build_target_grid(lon_min, lon_max, lat_min, lat_max, dx, dy):
    """Return (lons, lats, LON_mesh, LAT_mesh)."""
    lons = np.arange(lon_min, lon_max + dx / 2, dx)
    lats = np.arange(lat_min, lat_max + dy / 2, dy)
    LON, LAT = np.meshgrid(lons, lats)
    return lons, lats, LON, LAT


def regrid_field(field_face, fx_w, fy_w, water_mask, LON, LAT, mask_far):
    """Interpolate a (face,) field to (lat, lon) grid via griddata."""
    pts = np.column_stack([fx_w, fy_w])
    vals = field_face[water_mask]
    tgt = np.column_stack([LON.ravel(), LAT.ravel()])
    out_flat = griddata(pts, vals, tgt, method='linear')
    out_flat[mask_far] = np.nan
    return out_flat.reshape(LON.shape)


def open_partitioned(map_pattern):
    ds = dfmt.open_partitioned_dataset(map_pattern)
    fx = np.asarray(ds.grid.face_x)
    fy = np.asarray(ds.grid.face_y)
    bl = np.asarray(ds['mesh2d_flowelem_bl'].values).flatten()
    water_mask = bl < LAND_BL_THRESH
    fx_w, fy_w = fx[water_mask], fy[water_mask]
    return ds, fx_w, fy_w, water_mask


def precompute_mask_far(fx_w, fy_w, LON, LAT, kdist_deg=KDIST_DEG):
    tree = cKDTree(np.column_stack([fx_w, fy_w]))
    dists, _ = tree.query(np.column_stack([LON.ravel(), LAT.ravel()]))
    return dists > kdist_deg


# ---------- WL tab ----------

def build_wl_tab(ds, fx_w, fy_w, water_mask, times, station_data, publish_start, publish_stop):
    """Build WL tab: top line chart (3 stations) + bottom heatmap, synced via slider.

    Returns: plotly.graph_objects.Figure (with subplots + frames).
    """
    # Lagoon-focused grid for WL
    lons, lats, LON, LAT = build_target_grid(
        LON_MIN_LAGOON, LON_MAX_LAGOON, LAT_MIN_LAGOON, LAT_MAX_LAGOON,
        DX_LAGOON, DY_LAGOON)
    mask_far = precompute_mask_far(fx_w, fy_w, LON, LAT)

    # Subset time to publish window
    t_idx = np.where((times >= publish_start) & (times <= publish_stop))[0]
    sel_times = times[t_idx]
    print(f'  WL tab: {len(sel_times)} frames, grid {LON.shape}')

    # Precompute heatmaps per frame
    wl_da = ds['mesh2d_s1']  # waterlevel
    frames_data = []
    for ti in t_idx:
        s1 = np.asarray(wl_da.isel(time=ti).values)
        wl_grid = regrid_field(s1, fx_w, fy_w, water_mask, LON, LAT, mask_far)
        frames_data.append(wl_grid)
    frames_data = np.stack(frames_data, axis=0)

    # Make figure with 2 vertical subplots
    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.30, 0.70],
        vertical_spacing=0.08,
        subplot_titles=('Water level @ stations (full window)',
                        'Water level — spatial field (lagoon zoom)'),
    )

    # Top row: line traces for each in-situ station (model)
    station_colors = {'BocaNord': '#1f77b4', 'BocaSud': '#2ca02c', 'AltaVilaEst': '#d62728'}
    for st_name, ts in station_data.items():
        color = station_colors.get(st_name, '#888')
        fig.add_trace(go.Scatter(
            x=ts.index, y=ts.values, mode='lines',
            name=st_name, line=dict(color=color, width=1.5),
            hovertemplate=f'<b>{st_name}</b><br>%{{x}}<br>%{{y:.3f}} m<extra></extra>',
        ), row=1, col=1)

    # Static current-time indicator (vertical line, will be updated per frame)
    # Initialize at first publish time
    t_initial = sel_times[0]
    fig.add_trace(go.Scatter(
        x=[t_initial, t_initial], y=[-1, 1], mode='lines',
        name='current', line=dict(color='black', width=2, dash='dot'),
        showlegend=False, hoverinfo='skip',
    ), row=1, col=1)

    # Bottom row: heatmap of WL spatial (initial frame)
    fig.add_trace(go.Heatmap(
        z=frames_data[0], x=lons, y=lats,
        colorscale='RdBu_r', zmid=0, zmin=-0.6, zmax=0.6,
        colorbar=dict(title='WL [m]', len=0.55, y=0.30),
        hovertemplate='lon=%{x:.4f}<br>lat=%{y:.4f}<br>WL=%{z:.3f} m<extra></extra>',
    ), row=2, col=1)

    # Build frames: each frame updates the vertical line + heatmap z
    frames = []
    n_stations = len(station_data)
    vline_idx = n_stations  # trace index of vertical line
    heatmap_idx = n_stations + 1  # trace index of heatmap
    for k, ti in enumerate(t_idx):
        t = pd.Timestamp(sel_times[k])
        frames.append(go.Frame(
            name=str(t),
            data=[
                go.Scatter(x=[t, t], y=[-1, 1]),  # vline update
                go.Heatmap(z=frames_data[k]),     # heatmap update
            ],
            traces=[vline_idx, heatmap_idx],
        ))
    fig.frames = frames

    # Slider
    slider_steps = []
    for k in range(len(t_idx)):
        t = pd.Timestamp(sel_times[k])
        slider_steps.append(dict(
            method='animate',
            label=t.strftime('%m-%d %H:%M'),
            args=[[str(t)], dict(mode='immediate', frame=dict(duration=200, redraw=True),
                                  transition=dict(duration=150))],
        ))
    fig.update_layout(
        sliders=[dict(
            active=0,
            currentvalue=dict(prefix='Time: ', visible=True, xanchor='center'),
            steps=slider_steps,
            pad=dict(t=50),
        )],
        updatemenus=[dict(
            type='buttons', direction='left',
            buttons=[
                dict(label='▶ Play', method='animate',
                     args=[None, dict(frame=dict(duration=300, redraw=True),
                                       fromcurrent=True, transition=dict(duration=200))]),
                dict(label='⏸ Pause', method='animate',
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                         mode='immediate', transition=dict(duration=0))]),
            ],
            x=0.05, y=-0.05, xanchor='right', yanchor='top',
        )],
        height=720, width=900,
        margin=dict(l=50, r=20, t=60, b=120),
        title=f'Stagnone WL — publish window {publish_start.strftime("%Y-%m-%d %H:%M")} -> {publish_stop.strftime("%H:%M")} UTC',
    )
    fig.update_xaxes(title='time (UTC)', row=1, col=1)
    fig.update_yaxes(title='WL [m]', row=1, col=1)
    fig.update_xaxes(title='lon (°E)', row=2, col=1)
    fig.update_yaxes(title='lat (°N)', row=2, col=1, scaleanchor='x', scaleratio=1.27)  # aspect-correct near 38°N
    return fig


# ---------- Velocity tab ----------

def build_velocity_tab(ds, fx_w, fy_w, water_mask, times, publish_start, publish_stop):
    """Velocity quiver colored by magnitude. Plotly doesn't have native quiver
    in subplots/frames, so we use Scatter with arrow markers approximating it.
    Approach: subsample mesh to a 30x25 regular grid, draw line segments at each
    grid point with magnitude as color.
    """
    # Reduced-res grid for clear quiver
    lons = np.linspace(LON_MIN_LAGOON, LON_MAX_LAGOON, 36)
    lats = np.linspace(LAT_MIN_LAGOON, LAT_MAX_LAGOON, 28)
    LON, LAT = np.meshgrid(lons, lats)
    mask_far = precompute_mask_far(fx_w, fy_w, LON, LAT)

    t_idx = np.where((times >= publish_start) & (times <= publish_stop))[0]
    sel_times = times[t_idx]
    print(f'  Velocity tab: {len(sel_times)} frames, quiver grid {LON.shape}')

    # Surface layer top
    lay_dim = 'mesh2d_nLayers'
    if lay_dim not in ds['mesh2d_ucx'].dims:
        lay_dim = [d for d in ds['mesh2d_ucx'].dims if 'layer' in d.lower()][0]
    ucx_da = ds['mesh2d_ucx'].isel({lay_dim: -1})
    ucy_da = ds['mesh2d_ucy'].isel({lay_dim: -1})

    # Precompute per-frame: u, v, mag at each grid point
    u_frames, v_frames, mag_frames = [], [], []
    for ti in t_idx:
        u_face = np.asarray(ucx_da.isel(time=ti).values)
        v_face = np.asarray(ucy_da.isel(time=ti).values)
        u_grid = regrid_field(u_face, fx_w, fy_w, water_mask, LON, LAT, mask_far)
        v_grid = regrid_field(v_face, fx_w, fy_w, water_mask, LON, LAT, mask_far)
        mag = np.sqrt(u_grid ** 2 + v_grid ** 2)
        u_frames.append(u_grid); v_frames.append(v_grid); mag_frames.append(mag)
    u_frames = np.stack(u_frames); v_frames = np.stack(v_frames); mag_frames = np.stack(mag_frames)

    # Quiver via arrow markers: one marker per grid point, oriented by atan2(v,u)
    # Plotly supports marker.symbol='arrow' with marker.angle (degrees, 0=north, CW)
    def quiver_points(u, v, mag):
        flat_u = u.ravel(); flat_v = v.ravel(); flat_mag = mag.ravel()
        flat_lon = LON.ravel(); flat_lat = LAT.ravel()
        valid = ~(np.isnan(flat_u) | np.isnan(flat_v))
        # angle: 0 = north (up), CW positive — vector (u,v) East/North coordinates
        # Plotly arrow points "north" when angle=0; to make it point in (u,v) direction:
        # angle = atan2(u, v) in degrees (so positive v -> 0 north, positive u -> 90 east)
        angle = np.degrees(np.arctan2(flat_u[valid], flat_v[valid]))
        return flat_lon[valid], flat_lat[valid], flat_mag[valid], angle

    xs0, ys0, ms0, ang0 = quiver_points(u_frames[0], v_frames[0], mag_frames[0])
    vmax = float(np.nanpercentile(mag_frames, 95))

    fig = go.Figure(data=[go.Scatter(
        x=xs0, y=ys0, mode='markers',
        marker=dict(
            symbol='arrow', size=14, angle=ang0,
            color=ms0, colorscale='Viridis', cmin=0, cmax=vmax,
            line=dict(width=0),
            colorbar=dict(title='|U| [m/s]', len=0.85, y=0.5),
        ),
        hovertemplate='|U|=%{marker.color:.3f} m/s<extra></extra>',
        name='velocity', showlegend=False,
    )])

    # Frames — update positions + angles + colors
    frames = []
    for k, ti in enumerate(t_idx):
        t = pd.Timestamp(sel_times[k])
        xs, ys, ms, ang = quiver_points(u_frames[k], v_frames[k], mag_frames[k])
        frames.append(go.Frame(
            name=str(t),
            data=[go.Scatter(x=xs, y=ys, marker=dict(color=ms, angle=ang))],
            traces=[0],
        ))
    fig.frames = frames

    slider_steps = []
    for k in range(len(t_idx)):
        t = pd.Timestamp(sel_times[k])
        slider_steps.append(dict(
            method='animate', label=t.strftime('%m-%d %H:%M'),
            args=[[str(t)], dict(mode='immediate', frame=dict(duration=200, redraw=True),
                                  transition=dict(duration=150))],
        ))

    fig.update_layout(
        sliders=[dict(
            active=0, currentvalue=dict(prefix='Time: ', visible=True, xanchor='center'),
            steps=slider_steps, pad=dict(t=50),
        )],
        updatemenus=[dict(
            type='buttons', direction='left',
            buttons=[
                dict(label='▶ Play', method='animate',
                     args=[None, dict(frame=dict(duration=300, redraw=True),
                                       fromcurrent=True, transition=dict(duration=200))]),
                dict(label='⏸ Pause', method='animate',
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                         mode='immediate', transition=dict(duration=0))]),
            ],
            x=0.05, y=-0.05, xanchor='right', yanchor='top',
        )],
        height=700, width=900,
        margin=dict(l=50, r=20, t=60, b=120),
        title=f'Surface velocity — publish window {publish_start.strftime("%Y-%m-%d %H:%M")} -> {publish_stop.strftime("%H:%M")} UTC',
        xaxis=dict(title='lon (°E)', range=[LON_MIN_LAGOON, LON_MAX_LAGOON]),
        yaxis=dict(title='lat (°N)', range=[LAT_MIN_LAGOON, LAT_MAX_LAGOON],
                   scaleanchor='x', scaleratio=1.27),
    )
    return fig


# ---------- Hwav tab ----------

def build_hwav_tab(ds, fx_w, fy_w, water_mask, times, publish_start, publish_stop):
    """Hwav heatmap, greens colormap, lagoon zoom."""
    lons, lats, LON, LAT = build_target_grid(
        LON_MIN_LAGOON, LON_MAX_LAGOON, LAT_MIN_LAGOON, LAT_MAX_LAGOON,
        DX_LAGOON, DY_LAGOON)
    mask_far = precompute_mask_far(fx_w, fy_w, LON, LAT)

    t_idx = np.where((times >= publish_start) & (times <= publish_stop))[0]
    sel_times = times[t_idx]
    print(f'  Hwav tab: {len(sel_times)} frames, grid {LON.shape}')

    if 'mesh2d_hwav' not in ds:
        print('  WARN: mesh2d_hwav not in dataset, skipping')
        return None

    hwav_da = ds['mesh2d_hwav']
    frames_data = []
    for ti in t_idx:
        h = np.asarray(hwav_da.isel(time=ti).values)
        hw_grid = regrid_field(h, fx_w, fy_w, water_mask, LON, LAT, mask_far)
        frames_data.append(hw_grid)
    frames_data = np.stack(frames_data, axis=0)

    vmax = float(np.nanpercentile(frames_data, 98))

    fig = go.Figure(data=[go.Heatmap(
        z=frames_data[0], x=lons, y=lats,
        colorscale='Greens', zmin=0, zmax=vmax,
        colorbar=dict(title='H_rms [m]', len=0.85, y=0.5),
        hovertemplate='lon=%{x:.4f}<br>lat=%{y:.4f}<br>H_rms=%{z:.3f} m<extra></extra>',
    )])

    frames = []
    for k, ti in enumerate(t_idx):
        t = pd.Timestamp(sel_times[k])
        frames.append(go.Frame(
            name=str(t),
            data=[go.Heatmap(z=frames_data[k])],
            traces=[0],
        ))
    fig.frames = frames

    slider_steps = []
    for k in range(len(t_idx)):
        t = pd.Timestamp(sel_times[k])
        slider_steps.append(dict(
            method='animate', label=t.strftime('%m-%d %H:%M'),
            args=[[str(t)], dict(mode='immediate', frame=dict(duration=200, redraw=True),
                                  transition=dict(duration=150))],
        ))

    fig.update_layout(
        sliders=[dict(
            active=0, currentvalue=dict(prefix='Time: ', visible=True, xanchor='center'),
            steps=slider_steps, pad=dict(t=50),
        )],
        updatemenus=[dict(
            type='buttons', direction='left',
            buttons=[
                dict(label='▶ Play', method='animate',
                     args=[None, dict(frame=dict(duration=300, redraw=True),
                                       fromcurrent=True, transition=dict(duration=200))]),
                dict(label='⏸ Pause', method='animate',
                     args=[[None], dict(frame=dict(duration=0, redraw=False),
                                         mode='immediate', transition=dict(duration=0))]),
            ],
            x=0.05, y=-0.05, xanchor='right', yanchor='top',
        )],
        height=700, width=900,
        margin=dict(l=50, r=20, t=60, b=120),
        title=f'Significant wave height (H_rms) — {publish_start.strftime("%Y-%m-%d %H:%M")} -> {publish_stop.strftime("%H:%M")} UTC',
        xaxis=dict(title='lon (°E)'),
        yaxis=dict(title='lat (°N)', scaleanchor='x', scaleratio=1.27),
    )
    return fig


# ---------- Per-station section ----------

def build_station_card(st_name, ts_full_7d, publish_start, publish_stop):
    """Two Plotly figures per station:
    - sparkline: 7d at ~1pt/hour, publish day highlighted
    - main: publish day at native 10-min resolution
    Returns (sparkline_html_div, main_html_div) — partial HTML to embed.
    """
    # Sparkline: resample to hourly for compactness
    sparkline = ts_full_7d.resample('1h').mean()
    inside = (sparkline.index >= publish_start) & (sparkline.index <= publish_stop)
    spark = go.Figure()
    # Background grey trace
    spark.add_trace(go.Scatter(
        x=sparkline.index, y=sparkline.values, mode='lines',
        line=dict(color='#888', width=1.0),
        showlegend=False, hovertemplate='%{x}<br>%{y:.3f} m<extra></extra>',
    ))
    # Highlight publish day
    spark.add_trace(go.Scatter(
        x=sparkline.index[inside], y=sparkline.values[inside], mode='lines',
        line=dict(color='#d62728', width=2.5),
        showlegend=False, hovertemplate='%{x}<br>%{y:.3f} m<extra></extra>',
    ))
    spark.update_layout(
        height=80, width=900,
        margin=dict(l=40, r=10, t=5, b=20),
        plot_bgcolor='white',
        xaxis=dict(showgrid=False, ticks='', showticklabels=True, tickformat='%m-%d'),
        yaxis=dict(showgrid=False, title='m', title_font=dict(size=10), tickfont=dict(size=9)),
        showlegend=False,
    )

    # Main: publish day, 10-min res
    main_ts = ts_full_7d.loc[publish_start:publish_stop]
    main = go.Figure()
    main.add_trace(go.Scatter(
        x=main_ts.index, y=main_ts.values, mode='lines',
        line=dict(color='#1f77b4', width=1.5),
        name=st_name, hovertemplate='%{x}<br>%{y:.3f} m<extra></extra>',
    ))
    main.update_layout(
        height=220, width=900,
        margin=dict(l=50, r=20, t=30, b=40),
        title=dict(text=f'{st_name} — Water level over publish day', x=0.5, font=dict(size=12)),
        xaxis=dict(title='time (UTC)'),
        yaxis=dict(title='WL [m]'),
        showlegend=False,
    )

    # Render to partial HTML (without <html>/<body>)
    spark_div = pio.to_html(spark, include_plotlyjs=False, full_html=False,
                             div_id=f'spark_{st_name.lower()}')
    main_div = pio.to_html(main, include_plotlyjs=False, full_html=False,
                            div_id=f'main_{st_name.lower()}')
    return spark_div, main_div


# ---------- Index.html assembler ----------

INDEX_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Stagnone Hydrodynamic Model — {publish_day}</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         margin: 0; padding: 20px; background: #f4f4f4; color: #222; }}
  h1 {{ font-size: 1.5em; margin-top: 0; }}
  .tabs {{ display: flex; gap: 2px; border-bottom: 3px solid #1f77b4; margin-bottom: 0; }}
  .tab-btn {{ padding: 10px 24px; background: #ddd; border: 0; cursor: pointer;
              font-size: 1em; color: #444; transition: background 0.2s; }}
  .tab-btn:hover {{ background: #ccc; }}
  .tab-btn.active {{ background: #1f77b4; color: white; }}
  .tab-content {{ display: none; background: white; padding: 4px; }}
  .tab-content.active {{ display: block; }}
  iframe {{ width: 100%; height: 780px; border: 0; }}
  .stations-section {{ margin-top: 30px; }}
  .stations-section h2 {{ font-size: 1.2em; border-bottom: 2px solid #ddd; padding-bottom: 6px; }}
  .station-card {{ background: white; padding: 10px 15px; margin: 10px 0; border-radius: 4px;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
  .station-card h3 {{ margin: 5px 0; font-size: 1.05em; color: #1f77b4; }}
  .sparkline {{ border-bottom: 1px solid #eee; margin-bottom: 5px; padding-bottom: 5px; }}
  footer {{ margin-top: 30px; font-size: 0.85em; color: #888; }}
</style>
</head>
<body>

<h1>Stagnone Hydrodynamic Model — publish day {publish_day}</h1>
<p style="color: #666;">Window: {window_start} → {window_stop} UTC · Generated {generated_at}</p>

<div class="tabs">
  <button class="tab-btn active" data-tab="wl">Water Level</button>
  <button class="tab-btn" data-tab="velocity">Surface Velocity</button>
  <button class="tab-btn" data-tab="hwav">Wave Height</button>
</div>

<div id="tab-wl" class="tab-content active">
  <iframe src="wl_tab.html" loading="lazy"></iframe>
</div>
<div id="tab-velocity" class="tab-content">
  <iframe src="velocity_tab.html" loading="lazy"></iframe>
</div>
<div id="tab-hwav" class="tab-content">
  <iframe src="hwav_tab.html" loading="lazy"></iframe>
</div>

<div class="stations-section">
  <h2>Per-station detail (publish day, sparkline = last 7 days)</h2>
  {station_cards}
</div>

<footer>
  Generated by build_wetwise_bundle.py · Stagnone Digital Twin · Source: {model_source}
</footer>

<script>
  document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    }});
  }});
</script>

</body>
</html>"""


def build_index_html(out_dir, publish_day, publish_start, publish_stop,
                     model_source, generated_at, station_data_7d):
    """Assemble index.html with tabs (iframes) + per-station section."""
    station_cards_html = []
    for st_name, ts_7d in station_data_7d.items():
        spark_div, main_div = build_station_card(st_name, ts_7d, publish_start, publish_stop)
        station_cards_html.append(f'''
        <div class="station-card">
          <h3>{st_name}</h3>
          <div class="sparkline">{spark_div}</div>
          <div class="main-chart">{main_div}</div>
        </div>''')

    html = INDEX_TEMPLATE.format(
        publish_day=publish_day,
        window_start=publish_start.strftime('%Y-%m-%d %H:%M'),
        window_stop=publish_stop.strftime('%Y-%m-%d %H:%M'),
        generated_at=generated_at,
        model_source=str(model_source),
        station_cards='\n'.join(station_cards_html),
    )
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    print(f'  Saved {out_dir / "index.html"}')


# ---------- main ----------

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-out', required=True, help='DFM_OUTPUT_*/ dir with partitioned map.nc')
    p.add_argument('--publish-day', required=True, help='YYYY-MM-DD; publish window = last 24h ending at this date 00:00')
    p.add_argument('--output-dir', default='outputs/wetwise_tab_v2_test', help='Bundle output dir base')
    args = p.parse_args()

    model_out = Path(args.model_out)
    publish_day = pd.Timestamp(args.publish_day)
    publish_stop = publish_day
    publish_start = publish_day - timedelta(hours=24)
    out_dir = Path(args.output_dir) / f'd{args.publish_day}'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'data').mkdir(exist_ok=True)

    print(f'Model out  : {model_out}')
    print(f'Publish    : {publish_start} -> {publish_stop}')
    print(f'Output     : {out_dir}')

    # Open partitioned map.nc
    map_pattern = str(model_out / 'Stagnone_dxy01_15m_0*_map.nc')
    print(f'Opening {map_pattern} ...')
    ds, fx_w, fy_w, water_mask = open_partitioned(map_pattern)
    times = pd.to_datetime(ds.time.values)

    # Read his.nc for station time series (full window — sparkline will use 7d)
    his = xr.open_dataset(model_out / 'Stagnone_dxy01_15m_0000_his.nc')
    sname_full = [s.decode().strip() if isinstance(s, bytes) else s.strip()
                  for s in his.station_name.values]
    STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst']
    station_data = {}
    full_window_start = publish_stop - timedelta(days=7)
    for st in STATIONS:
        if st not in sname_full:
            continue
        i = sname_full.index(st)
        dim = 'stations' if 'stations' in his.waterlevel.dims else 'station'
        s = his.waterlevel.isel({dim: i}).to_pandas()
        s.index = pd.to_datetime(s.index)
        s_window = s.loc[full_window_start:publish_stop]
        station_data[st] = s_window

    # ===== Tab 1: WL =====
    print('Building WL tab...')
    fig_wl = build_wl_tab(ds, fx_w, fy_w, water_mask, times,
                          station_data, publish_start, publish_stop)
    wl_html_path = out_dir / 'wl_tab.html'
    pio.write_html(fig_wl, str(wl_html_path), include_plotlyjs='cdn',
                   full_html=True, auto_play=False)
    print(f'  Saved {wl_html_path}')

    # ===== Tab 2: Velocity =====
    print('Building Velocity tab...')
    fig_vel = build_velocity_tab(ds, fx_w, fy_w, water_mask, times,
                                  publish_start, publish_stop)
    vel_html_path = out_dir / 'velocity_tab.html'
    pio.write_html(fig_vel, str(vel_html_path), include_plotlyjs='cdn',
                   full_html=True, auto_play=False)
    print(f'  Saved {vel_html_path}')

    # ===== Tab 3: Hwav =====
    print('Building Hwav tab...')
    fig_hwav = build_hwav_tab(ds, fx_w, fy_w, water_mask, times,
                               publish_start, publish_stop)
    tabs_built = ['wl', 'velocity']
    if fig_hwav is not None:
        hwav_html_path = out_dir / 'hwav_tab.html'
        pio.write_html(fig_hwav, str(hwav_html_path), include_plotlyjs='cdn',
                       full_html=True, auto_play=False)
        print(f'  Saved {hwav_html_path}')
        tabs_built.append('hwav')

    # ===== manifest =====
    generated_at = datetime.utcnow().isoformat() + 'Z'
    manifest = {
        'publish_day': args.publish_day,
        'publish_start': str(publish_start),
        'publish_stop': str(publish_stop),
        'model_source': str(model_out),
        'generated_at': generated_at,
        'tabs': tabs_built,
    }
    with open(out_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f'  Saved {out_dir / "manifest.json"}')

    # ===== index.html (tabs + per-station) =====
    print('Building index.html...')
    build_index_html(out_dir, args.publish_day, publish_start, publish_stop,
                     model_out, generated_at, station_data)

    print(f'\nDone. Open {out_dir / "index.html"} in a browser.')


if __name__ == '__main__':
    main()
