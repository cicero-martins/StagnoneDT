"""Build a self-contained demo HTML for the Stagnone operational chain Jul 2025.

Inputs (all local):
  data/processed/continuation_validation_jun04/*_his.nc  — 12 model runs
  data/processed/continuation_validation_jun04/marettimo_wl_chain_jul25.csv
  data/processed/continuation_validation_jun04/metrics.csv
  data/processed/insitu_2025-26/AE_wl_UTC.csv, BN_wl_UTC.csv, BS_wl_UTC.csv
  data/raw/insitu/marettimo_wl_2025_2026_10min.csv
  outputs/wetwise_tab_v2_test/d2025-07-09/*.html  — existing spatial tabs

Output:
  outputs/wetwise_demo_jul25/index.html

Tabs:
  1. Chain Time Series  — model vs obs, full Jul 07-20, 4 stations (Plotly)
  2. Skill Metrics      — corr_anom / bias evolution + summary table (Plotly)
  3. Spatial Fields     — iframe to existing Jul-09 WL/Velocity/Hwav tabs
"""
from __future__ import annotations
import re
import json
import shutil
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import xarray as xr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

ROOT = Path(__file__).resolve().parent.parent
VAL_DIR  = ROOT / 'data' / 'processed' / 'continuation_validation_jun04'
INSITU   = {
    'BocaNord':    ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BN_wl_UTC.csv',
    'BocaSud':     ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BS_wl_UTC.csv',
    'AltaVilaEst': ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'AE_wl_UTC.csv',
}
MAR_OBS  = ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'
MAR_MOD  = VAL_DIR / 'marettimo_wl_chain_jul25.csv'
METRICS  = VAL_DIR / 'metrics.csv'
SPATIAL_SRC = ROOT / 'outputs' / 'wetwise_tab_v2_test' / 'd2025-07-09'
OUT_DIR  = ROOT / 'outputs' / 'wetwise_demo_jul25'

SPINUP_H = 12
STATION_COLORS = {
    'BocaNord':    '#1f77b4',
    'BocaSud':     '#2ca02c',
    'AltaVilaEst': '#d62728',
    'Marettimo':   '#8c564b',
}


# ─────────────────────────── helpers ────────────────────────────────────────

def derive_window(stem: str):
    if stem == 'd2025-07-10':
        return pd.Timestamp('2025-07-07'), pd.Timestamp('2025-07-10')
    m = re.match(r'd(\d{4}-\d{2}-\d{2})_n(\d+)$', stem)
    if m:
        pub = pd.Timestamp(m.group(1))
        return pub - pd.Timedelta(days=int(m.group(2))), pub
    raise ValueError(stem)


def station_names_from_ds(ds):
    out = []
    for s in ds.station_name.values:
        if isinstance(s, (np.ndarray, list)):
            out.append(b''.join([c if isinstance(c, bytes) else c.encode()
                                  for c in s]).decode().strip())
        else:
            out.append(str(s).replace("b'", "").replace("'", "").strip())
    return out


def load_obs(path, tcol_hint=None):
    df = pd.read_csv(path)
    tcol = next(c for c in df.columns if 'time' in c.lower())
    wlcol = next(c for c in df.columns
                 if c.lower() in ('h_m', 'wl', 'wl_m', 'waterlevel', 'h')
                 or 'level' in c.lower())
    df[tcol] = pd.to_datetime(df[tcol])
    return df.set_index(tcol)[wlcol]


def collect_runs():
    runs = []
    for f in sorted(VAL_DIR.glob('*_his.nc')):
        stem = f.stem.replace('_his', '')
        try:
            t0, t1 = derive_window(stem)
        except ValueError:
            continue
        runs.append({'file': f, 'stem': stem, 't0': t0, 't1': t1})
    return runs


def build_stitched_composite(runs, stations_his, mar_mod_df, mar_obs_s):
    """
    For each N-2 run, take the window [t0+SPINUP_H, t1] as the model output.
    Returns dict station -> pd.Series (stitched, 10-min resampled).
    """
    model_segs = {s: [] for s in list(stations_his.keys()) + ['Marettimo']}

    for r in runs:
        t_start = r['t0'] + pd.Timedelta(hours=SPINUP_H)
        t_end   = r['t1']
        ds = xr.open_dataset(r['file'])
        names = station_names_from_ds(ds)
        for stn in stations_his:
            if stn not in names:
                ds.close(); continue
            idx = names.index(stn)
            mod = ds.waterlevel.isel(station=idx).to_pandas()
            mod.index = pd.DatetimeIndex(mod.index)
            seg = mod[t_start:t_end].resample('10min').mean().dropna()
            model_segs[stn].append(seg)
        ds.close()

        # Marettimo from pre-extracted CSV
        if mar_mod_df is not None:
            sub = mar_mod_df[mar_mod_df['run'] == r['stem']].set_index('time')['wl_m']
            seg = sub[t_start:t_end].resample('10min').mean().dropna()
            model_segs['Marettimo'].append(seg)

    stitched = {}
    for stn, segs in model_segs.items():
        if segs:
            stitched[stn] = pd.concat(segs).sort_index()
            stitched[stn] = stitched[stn][~stitched[stn].index.duplicated(keep='last')]
    return stitched


# ─────────────────────── Tab 1: Chain Time Series ───────────────────────────

def build_timeseries_tab(runs, obs_cache, mar_obs, mar_mod_df):
    stations_ordered = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'Marettimo']
    station_labels   = {
        'BocaNord': 'BocaNord (lagoon N inlet)',
        'BocaSud':  'BocaSud (lagoon S inlet)',
        'AltaVilaEst': 'AltaVilaEst (lagoon interior)',
        'Marettimo': 'Marettimo (offshore, JRC TAD 658)',
    }

    stitched = build_stitched_composite(runs, obs_cache, mar_mod_df, mar_obs)

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        subplot_titles=[station_labels[s] for s in stations_ordered],
                        vertical_spacing=0.07)

    plot_t0 = pd.Timestamp('2025-07-07')
    plot_t1 = pd.Timestamp('2025-07-20')

    for row, stn in enumerate(stations_ordered, start=1):
        col = STATION_COLORS[stn]

        # Obs
        if stn == 'Marettimo':
            obs_s = mar_obs[plot_t0:plot_t1].resample('10min').mean() if mar_obs is not None else None
        else:
            obs_s = obs_cache[stn][plot_t0:plot_t1].resample('10min').mean()

        if obs_s is not None:
            fig.add_trace(go.Scatter(
                x=obs_s.index, y=obs_s.values,
                mode='lines', name='In-situ obs',
                line=dict(color='rgba(0,0,0,0.45)', width=0.8),
                showlegend=(row == 1),
                legendgroup='obs',
                hovertemplate='%{x|%b-%d %H:%M}<br>obs: %{y:.3f} m<extra></extra>',
            ), row=row, col=1)

        # Model (stitched composite)
        if stn in stitched:
            mod_s = stitched[stn][plot_t0:plot_t1]
            fig.add_trace(go.Scatter(
                x=mod_s.index, y=mod_s.values,
                mode='lines', name='Model (chain)',
                line=dict(color=col, width=1.6),
                showlegend=(row == 1),
                legendgroup='model',
                hovertemplate='%{x|%b-%d %H:%M}<br>model: %{y:.3f} m<extra></extra>',
            ), row=row, col=1)

        fig.update_yaxes(title_text='WL (m)', row=row, col=1, title_font_size=11)

    # Publish-day vertical markers
    for pub_day in pd.date_range('2025-07-10', '2025-07-20', freq='D'):
        for row in range(1, 5):
            fig.add_vline(x=pub_day.timestamp() * 1000, line_width=0.6,
                          line_dash='dot', line_color='steelblue', opacity=0.5,
                          row=row, col=1)

    fig.update_layout(
        height=900,
        title=dict(text='Operational chain Jul 2025 — model vs in-situ (stitched N-2 composite, 12h spinup dropped)',
                   font_size=13),
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1),
        margin=dict(l=60, r=20, t=80, b=40),
        plot_bgcolor='white',
        paper_bgcolor='white',
    )
    fig.update_xaxes(showgrid=True, gridcolor='#eee', tickformat='%b-%d',
                     range=[plot_t0, plot_t1])
    fig.update_yaxes(showgrid=True, gridcolor='#eee', zeroline=True,
                     zerolinecolor='#bbb', zerolinewidth=1)

    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id='tab_timeseries')


# ─────────────────────── Tab 2: Skill Metrics ───────────────────────────────

def build_metrics_tab():
    df = pd.read_csv(METRICS)
    df['pub_date'] = pd.to_datetime(df['pub_date'])
    stations = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'Marettimo']

    # Subplot: 3 metrics × 1 column
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        subplot_titles=['Anomaly correlation (tide-removed)',
                        'Anomaly RMSE (mm)',
                        'Bias (mm)'],
        vertical_spacing=0.10,
    )
    metrics_cfg = [
        ('corr_anom',    1, dict(range=[0, 1.05])),
        ('rmse_anom_mm', 2, dict(rangemode='tozero')),
        ('bias_mm',      3, {}),
    ]
    for metric, row, yaxis_kwargs in metrics_cfg:
        for stn in stations:
            sub = df[df['station'] == stn].sort_values('pub_date')
            if sub.empty:
                continue
            col = STATION_COLORS[stn]
            fig.add_trace(go.Scatter(
                x=sub['pub_date'], y=sub[metric],
                mode='lines+markers',
                name=stn,
                line=dict(color=col, width=1.8),
                marker=dict(size=6),
                showlegend=(row == 1),
                legendgroup=stn,
                hovertemplate=f'<b>{stn}</b><br>%{{x|%b-%d}}<br>{metric}: %{{y:.3f}}<extra></extra>',
            ), row=row, col=1)
        fig.update_yaxes(title_text=metric.replace('_', ' '), row=row, col=1,
                         title_font_size=11, **yaxis_kwargs)
        if metric == 'bias_mm':
            fig.add_hline(y=0, line_width=0.8, line_color='gray', row=row, col=1)

    fig.update_layout(
        height=750,
        title=dict(text='Skill metrics — N-2 operational chain (12h spinup drop)',
                   font_size=13),
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=70, r=20, t=80, b=40),
        plot_bgcolor='white', paper_bgcolor='white',
    )
    fig.update_xaxes(showgrid=True, gridcolor='#eee', tickformat='%b-%d')
    fig.update_yaxes(showgrid=True, gridcolor='#eee')

    # Summary table
    pivot = df.pivot_table(index='pub_date', columns='station',
                           values='corr_anom', aggfunc='mean').round(3)
    pivot.index = pivot.index.strftime('%b-%d')
    tbl = go.Figure(go.Table(
        header=dict(
            values=['Publish date'] + list(pivot.columns),
            fill_color='#1f77b4', font_color='white', font_size=12,
            align='center', height=28,
        ),
        cells=dict(
            values=[pivot.index.tolist()] + [pivot[c].tolist() for c in pivot.columns],
            fill_color=[['#f7f7f7', 'white'] * (len(pivot) // 2 + 1)],
            font_size=11, align='center', height=24,
            format=[None] + ['.3f'] * len(pivot.columns),
        ),
    ))
    tbl.update_layout(
        height=420, margin=dict(l=10, r=10, t=30, b=10),
        title=dict(text='Anomaly correlation per station × publish date', font_size=12),
    )

    chart_html = pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id='skill_chart')
    table_html = pio.to_html(tbl, include_plotlyjs=False, full_html=False, div_id='skill_table')
    return chart_html + '\n' + table_html


# ─────────────────────── assemble HTML ──────────────────────────────────────

INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stagnone DT — Operational Demo Jul 2025</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #f4f6f8; color: #222; }}
  header {{ background: #1a3a5c; color: white; padding: 14px 24px; }}
  header h1 {{ margin: 0; font-size: 1.3em; font-weight: 600; }}
  header p  {{ margin: 4px 0 0; font-size: 0.85em; opacity: 0.8; }}
  .tab-bar {{ display: flex; gap: 2px; background: #1a3a5c; padding: 0 24px; }}
  .tab-btn {{ padding: 10px 22px; background: transparent; color: rgba(255,255,255,0.7);
              border: none; cursor: pointer; font-size: 0.95em; border-bottom: 3px solid transparent; }}
  .tab-btn:hover {{ color: white; }}
  .tab-btn.active {{ color: white; border-bottom: 3px solid #4fc3f7; font-weight: 600; }}
  .tab-pane {{ display: none; padding: 20px 24px; }}
  .tab-pane.active {{ display: block; }}
  .card {{ background: white; border-radius: 6px; padding: 16px; margin-bottom: 16px;
           box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .card h2 {{ margin: 0 0 10px; font-size: 1.05em; color: #1a3a5c; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
  .spatial-tabs {{ display: flex; gap: 6px; margin-bottom: 10px; }}
  .sp-btn {{ padding: 7px 18px; background: #e8edf2; border: none; border-radius: 4px;
             cursor: pointer; font-size: 0.9em; }}
  .sp-btn.active {{ background: #1a3a5c; color: white; }}
  .sp-frame {{ display: none; width: 100%; height: 680px; border: none; border-radius: 4px; }}
  .sp-frame.active {{ display: block; }}
  .meta-grid {{ display: flex; gap: 20px; flex-wrap: wrap; font-size: 0.85em; color: #555; }}
  .meta-grid div {{ background: #eef3f8; padding: 8px 14px; border-radius: 4px; }}
  .meta-grid strong {{ color: #1a3a5c; }}
</style>
</head>
<body>

<header>
  <h1>Stagnone di Marsala — Hydrodynamic Digital Twin</h1>
  <p>Delft3D FM 3D + SWAN · Operational chain Jul 2025 · Generated {generated_at}</p>
</header>

<div class="tab-bar">
  <button class="tab-btn active" onclick="showTab('timeseries', this)">Chain Time Series</button>
  <button class="tab-btn" onclick="showTab('skill', this)">Skill Metrics</button>
  <button class="tab-btn" onclick="showTab('spatial', this)">Spatial Fields</button>
</div>

<!-- ─── Tab 1: Time Series ─── -->
<div id="pane-timeseries" class="tab-pane active">
  <div class="card">
    <h2>Model vs in-situ — full operational chain (Jul 07–20, 2025)</h2>
    <div class="meta-grid" style="margin-bottom:12px;">
      <div><strong>Runs:</strong> 12 × N-2 sliding window</div>
      <div><strong>Strategy:</strong> restart N−2, run 48 h, drop first 12 h spinup</div>
      <div><strong>Stations:</strong> BocaNord · BocaSud · AltaVilaEst (lagoon) · Marettimo (offshore)</div>
    </div>
    {timeseries_div}
  </div>
</div>

<!-- ─── Tab 2: Skill Metrics ─── -->
<div id="pane-skill" class="tab-pane">
  <div class="card">
    <h2>Skill evolution across publish dates</h2>
    {metrics_div}
  </div>
</div>

<!-- ─── Tab 3: Spatial Fields ─── -->
<div id="pane-spatial" class="tab-pane">
  <div class="card">
    <h2>Spatial fields — example publish day: 2025-07-09</h2>
    <p style="font-size:0.85em;color:#666;margin:0 0 10px;">
      Interactive maps (zoom/pan/hover). Showing Jul 08–09 publish window.
      Full-resolution output available for each chain iteration.
    </p>
    <div class="spatial-tabs">
      <button class="sp-btn active" onclick="showSpatial('wl', this)">Water Level</button>
      <button class="sp-btn" onclick="showSpatial('velocity', this)">Surface Velocity</button>
      <button class="sp-btn" onclick="showSpatial('hwav', this)">Wave Height</button>
    </div>
    <iframe id="sp-wl"       class="sp-frame active" src="spatial/wl_tab.html"       loading="lazy"></iframe>
    <iframe id="sp-velocity" class="sp-frame"         src="spatial/velocity_tab.html" loading="lazy"></iframe>
    <iframe id="sp-hwav"     class="sp-frame"         src="spatial/hwav_tab.html"     loading="lazy"></iframe>
  </div>
</div>

<script>
function showTab(name, btn) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('pane-' + name).classList.add('active');
  btn.classList.add('active');
}}
function showSpatial(name, btn) {{
  document.querySelectorAll('.sp-frame').forEach(f => f.classList.remove('active'));
  document.querySelectorAll('.sp-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('sp-' + name).classList.add('active');
  btn.classList.add('active');
}}
</script>

</body>
</html>
"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sp_dir = OUT_DIR / 'spatial'
    sp_dir.mkdir(exist_ok=True)

    # Copy existing spatial tab HTMLs
    for fname in ('wl_tab.html', 'velocity_tab.html', 'hwav_tab.html'):
        src = SPATIAL_SRC / fname
        if src.exists():
            shutil.copy2(src, sp_dir / fname)
            print(f'  Copied {fname}')
        else:
            print(f'  WARNING: {src} not found — spatial tab will be empty')

    # Load observations
    obs_cache = {stn: load_obs(path) for stn, path in INSITU.items()}
    mar_obs   = load_obs(MAR_OBS) if MAR_OBS.exists() else None
    mar_mod_df = pd.read_csv(MAR_MOD) if MAR_MOD.exists() else None
    if mar_mod_df is not None:
        mar_mod_df['time'] = pd.to_datetime(mar_mod_df['time'])

    runs = collect_runs()
    print(f'Building timeseries tab ({len(runs)} runs) ...')
    ts_div = build_timeseries_tab(runs, obs_cache, mar_obs, mar_mod_df)

    print('Building skill metrics tab ...')
    metrics_div = build_metrics_tab()

    print('Assembling index.html ...')
    generated_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    html = INDEX_TEMPLATE.format(
        generated_at=generated_at,
        timeseries_div=ts_div,
        metrics_div=metrics_div,
    )
    out_html = OUT_DIR / 'index.html'
    out_html.write_text(html, encoding='utf-8')
    size_kb = out_html.stat().st_size / 1024
    print(f'\nSaved: {out_html}  ({size_kb:.0f} KB)')
    print(f'Open in browser: file:///{out_html.as_posix()}')


if __name__ == '__main__':
    main()
