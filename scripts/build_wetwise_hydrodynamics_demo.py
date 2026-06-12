"""Build the WetWise Hydrodynamics tab demo (standalone HTML).

Reads v04AE partitioned map.nc + his.nc, regrids to a regular lat/lon grid
covering the Stagnone lagoon, and produces a self-contained Plotly HTML bundle
with 3 tabs (WL / Velocity / Hwav), a sync time slider, and per-station
sparklines (BocaNord, BocaSud, AltaVilaEst).

Usage:
    python scripts/build_wetwise_hydrodynamics_demo.py

Outputs:
    outputs/wetwise_tab/demo_hydrodynamics/demo_data.nc   (pre-gridded cache)
    outputs/wetwise_tab/demo_hydrodynamics/index.html     (standalone HTML)

The data-preparation step is cached: if demo_data.nc already exists it is
re-used without re-reading the 8 × 100 MB map.nc files.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import xarray as xr

ROOT   = Path(__file__).resolve().parents[1]
V04AE  = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
INSITU = ROOT / 'data' / 'processed' / 'insitu_2025-26'
OUT_DIR = ROOT / 'outputs' / 'wetwise_tab' / 'demo_hydrodynamics'
CACHE   = OUT_DIR / 'demo_data.nc'
HTML    = OUT_DIR / 'index.html'

# Regular grid covering the lagoon proper
LAG_LON = (12.40, 12.52)
LAG_LAT = (37.82, 37.96)
DX = DY = 0.003          # ~300 m

# Temporal subsampling: every 4 hours (map interval is 1800 s = 0.5 h)
T_STEP = 8               # every 8th output step → every 4 h

VARS = ['mesh2d_s1', 'mesh2d_ucx', 'mesh2d_ucy', 'mesh2d_hwav']

STATIONS = {
    'BocaNord':    {'csv_wl': 'BN_wl_UTC.csv',    'lon': 12.4245, 'lat': 37.9008},
    'BocaSud':     {'csv_wl': 'BS_wl_UTC.csv',     'lon': 12.4356, 'lat': 37.8312},
    'AltaVilaEst': {'csv_wl': 'AE_wl_UTC.csv',     'lon': 12.4782, 'lat': 37.8660},
}

# ── Step 1: Prepare regridded data ────────────────────────────────────────────

def prepare_data():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        print(f'Cache found: {CACHE} — skipping regrid step')
        return

    print('Opening partitioned map.nc ...')
    import dfm_tools as dfmt
    from scipy.interpolate import griddata

    pat = str(V04AE / 'Stagnone_dxy01_15m_0*_map.nc')
    ds = dfmt.open_partitioned_dataset(pat)
    print(f'  Variables: {list(ds.data_vars)[:8]} ...')

    # Cell-centre coordinates
    cx = ds['mesh2d_face_x'].values
    cy = ds['mesh2d_face_y'].values
    print(f'  Face count: {cx.shape[0]}')

    # Regular grid
    lon_vec = np.arange(LAG_LON[0], LAG_LON[1], DX)
    lat_vec = np.arange(LAG_LAT[0], LAG_LAT[1], DY)
    lon2, lat2 = np.meshgrid(lon_vec, lat_vec)
    points = np.column_stack([cx, cy])

    # Mask to lagoon extent (restrict interpolation source)
    lag_mask = ((cx >= LAG_LON[0] - 0.05) & (cx <= LAG_LON[1] + 0.05) &
                (cy >= LAG_LAT[0] - 0.05) & (cy <= LAG_LAT[1] + 0.05))

    # Layer selection: surface for velocity, s1/hwav are 2D
    def get_surface(da):
        for dim in da.dims:
            if 'layer' in dim.lower() or 'nlay' in dim.lower():
                return da.isel({dim: -1})
        return da

    # Time subsampling
    n_times = ds.dims.get('time', 0)
    t_idx = list(range(0, n_times, T_STEP))
    print(f'  Time steps available: {n_times}, selected: {len(t_idx)} (every {T_STEP})')

    times = ds['time'].values[t_idx]

    grids = {v: [] for v in VARS}

    for i, ti in enumerate(t_idx):
        if i % 12 == 0:
            print(f'  Regridding timestep {i}/{len(t_idx)}...')
        for vn in VARS:
            if vn not in ds:
                grids[vn].append(np.full(lon2.shape, np.nan))
                continue
            da = get_surface(ds[vn].isel(time=ti))
            vals = da.values.astype(np.float32)
            # Land/dry: replace fill values
            vals[np.abs(vals) > 1e9] = np.nan
            vals_lag = vals[lag_mask]
            pts_lag  = points[lag_mask]
            gi = griddata(pts_lag, vals_lag, (lon2, lat2),
                          method='linear', fill_value=np.nan)
            grids[vn].append(gi.astype(np.float32))

    # Stack to arrays shape (time, lat, lon)
    ds_out = xr.Dataset(
        {vn: xr.DataArray(
            np.stack(grids[vn], axis=0),
            dims=['time', 'lat', 'lon'],
            attrs={'units': 'm'})
         for vn in VARS},
        coords={
            'time': times,
            'lat': lat_vec,
            'lon': lon_vec,
        }
    )
    ds_out.to_netcdf(CACHE)
    print(f'  Cache saved: {CACHE}  ({CACHE.stat().st_size//1024} kB)')


# ── Step 2: Load station obs ──────────────────────────────────────────────────

def load_stations():
    SIM_T0 = pd.Timestamp('2025-07-01')
    SIM_T1 = pd.Timestamp('2025-07-10')
    result = {}
    for name, info in STATIONS.items():
        fp = INSITU / info['csv_wl']
        if not fp.exists():
            result[name] = None
            continue
        df = pd.read_csv(fp, parse_dates=['time'], index_col='time')
        df = df.sort_index().loc[SIM_T0:SIM_T1]
        if df.empty:
            result[name] = None
            continue
        # Find WL column (handles h_m, wl, waterlevel, level, etc.)
        wl_cols = [c for c in df.columns if any(k in c.lower() for k in
                   ('wl', 'waterlevel', 'water_level', 'h_m', 'level'))]
        col = wl_cols[0] if wl_cols else df.columns[0]
        result[name] = df[col].resample('1h').mean().dropna()
    return result


# ── Step 3: Build HTML ────────────────────────────────────────────────────────

def build_html():
    print('Loading regridded cache ...')
    ds = xr.open_dataset(CACHE)
    times_raw = ds['time'].values
    times_pd  = pd.DatetimeIndex(times_raw)
    lon  = ds['lon'].values
    lat  = ds['lat'].values
    n_t  = len(times_pd)

    # Build time labels
    t_labels = [str(t)[:16].replace('T', ' ') for t in times_pd]

    # Extract arrays (time, lat, lon) → list of 2D arrays
    def to_list2d(arr_3d):
        out = []
        for i in range(arr_3d.shape[0]):
            sl = arr_3d[i]
            sl[np.isnan(sl)] = None  # JSON null
            out.append(sl.tolist())
        return out

    s1_data    = to_list2d(ds['mesh2d_s1'].values)
    ucx_data   = to_list2d(ds['mesh2d_ucx'].values)
    ucy_data   = to_list2d(ds['mesh2d_ucy'].values)
    hwav_data  = to_list2d(ds['mesh2d_hwav'].values) if 'mesh2d_hwav' in ds else [
        [[None]*len(lon)]*len(lat)]*n_t

    # Velocity magnitude
    umag_data = []
    for i in range(n_t):
        ucx_i = np.array(ds['mesh2d_ucx'].values[i], dtype=np.float32)
        ucy_i = np.array(ds['mesh2d_ucy'].values[i], dtype=np.float32)
        mag = np.sqrt(ucx_i**2 + ucy_i**2)
        mag[np.isnan(mag)] = None
        umag_data.append(mag.tolist())

    # Station data
    sta_obs = load_stations()
    sta_json = {}
    for name, series in sta_obs.items():
        if series is not None:
            sta_json[name] = {
                't': [str(i)[:16].replace('T', ' ') for i in series.index],
                'wl': series.values.round(4).tolist()
            }
        else:
            sta_json[name] = None

    # Model time series at nearest grid cell for each station
    sta_model = {}
    for name, info in STATIONS.items():
        ilon = int(np.argmin(np.abs(lon - info['lon'])))
        ilat = int(np.argmin(np.abs(lat - info['lat'])))
        wl_model = []
        for i in range(n_t):
            v = ds['mesh2d_s1'].values[i, ilat, ilon]
            wl_model.append(float(v) if not np.isnan(v) else None)
        sta_model[name] = {'t': t_labels, 'wl': wl_model}

    ds.close()

    print('Building HTML ...')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WetWise — Stagnone Hydrodynamics</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; color: #222; }}
  header {{ background: #1F497D; color: white; padding: 12px 24px; display: flex;
            align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.4em; }}
  header span {{ font-size: 0.9em; opacity: 0.75; }}
  .container {{ max-width: 1300px; margin: 0 auto; padding: 16px; }}
  .tabs {{ display: flex; gap: 0; border-bottom: 2px solid #1F497D; margin-bottom: 12px; }}
  .tab-btn {{ padding: 8px 24px; cursor: pointer; background: #e7f0fb; border: none;
              font-size: 0.95em; font-weight: 600; color: #1F497D; border-radius: 4px 4px 0 0; }}
  .tab-btn.active {{ background: #1F497D; color: white; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .slider-row {{ margin: 10px 0; display: flex; align-items: center; gap: 12px; }}
  .slider-row label {{ font-size: 0.85em; color: #555; white-space: nowrap; }}
  #time-slider {{ flex: 1; accent-color: #1F497D; }}
  #time-label {{ font-size: 0.85em; color: #1F497D; font-weight: 600; min-width: 140px; }}
  .play-btn {{ padding: 4px 14px; background: #2E74B5; color: white; border: none;
               border-radius: 4px; cursor: pointer; font-size: 0.9em; }}
  .play-btn:hover {{ background: #1F497D; }}
  .map-div {{ width: 100%; height: 480px; }}
  .section-title {{ font-size: 1.0em; font-weight: 700; color: #1F497D;
                    margin: 20px 0 8px; padding-left: 4px; }}
  .station-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
                   gap: 16px; margin-bottom: 20px; }}
  .station-card {{ background: white; border-radius: 8px; padding: 12px;
                   box-shadow: 0 1px 4px rgba(0,0,0,0.12); }}
  .station-card h3 {{ font-size: 0.92em; color: #1F497D; margin-bottom: 6px; }}
  .sparkline-div {{ height: 60px; }}
  .main-chart-div {{ height: 200px; margin-top: 6px; }}
  footer {{ text-align: center; font-size: 0.75em; color: #888;
            padding: 12px; border-top: 1px solid #ddd; margin-top: 24px; }}
</style>
</head>
<body>
<header>
  <h1>WetWise — Stagnone di Marsala</h1>
  <span>Hydrodynamics Dashboard | v04AE | Jul 1–10 2025</span>
</header>
<div class="container">

  <!-- Spatial Fields -->
  <div class="section-title">Spatial Fields</div>
  <div class="tabs" id="field-tabs">
    <button class="tab-btn active" onclick="switchTab('wl')">Water Level</button>
    <button class="tab-btn" onclick="switchTab('vel')">Surface Velocity</button>
    <button class="tab-btn" onclick="switchTab('hwav')">Wave Height (Hwav)</button>
  </div>

  <div class="slider-row">
    <button class="play-btn" id="play-btn" onclick="togglePlay()">▶ Play</button>
    <label>Time:</label>
    <input type="range" id="time-slider" min="0" max="{n_t-1}" value="0"
           oninput="onSlider(this.value)">
    <span id="time-label">{t_labels[0]}</span>
  </div>

  <div id="tab-wl"  class="tab-content active">
    <div id="map-wl"  class="map-div"></div>
  </div>
  <div id="tab-vel" class="tab-content">
    <div id="map-vel" class="map-div"></div>
  </div>
  <div id="tab-hwav" class="tab-content">
    <div id="map-hwav" class="map-div"></div>
  </div>

  <!-- Per-station section -->
  <div class="section-title">Station Time Series (model vs obs)</div>
  <div class="station-grid" id="station-grid"></div>

</div>
<footer>
  WetWise Digital Twin · Stagnone di Marsala · Delft3D FM 3D + SWAN · UNIPA PhD project 2026
</footer>

<script>
// ── data ──────────────────────────────────────────────────────────────────────
const TIMES  = {json.dumps(t_labels)};
const LONS   = {json.dumps(lon.tolist())};
const LATS   = {json.dumps(lat.tolist())};
const S1     = {json.dumps(s1_data)};
const UCX    = {json.dumps(ucx_data)};
const UCY    = {json.dumps(ucy_data)};
const HWAV   = {json.dumps(hwav_data)};
const UMAG   = {json.dumps(umag_data)};
const STA_OBS   = {json.dumps(sta_json)};
const STA_MODEL = {json.dumps(sta_model)};
const STA_INFO  = {json.dumps({n: STATIONS[n] for n in STATIONS})};

// ── state ─────────────────────────────────────────────────────────────────────
let currentT = 0;
let playing   = false;
let playTimer = null;
let activeTab = 'wl';

// ── colorscales ───────────────────────────────────────────────────────────────
const CS_WL   = 'RdBu';
const CS_VEL  = 'Plasma';
const CS_HWAV = 'Greens';

const LAY = {{
  margin: {{l:10, r:10, t:10, b:10}},
  paper_bgcolor: '#f5f7fa',
  plot_bgcolor:  '#ddeeff',
  xaxis: {{title:'Longitude (°E)', fixedrange:false}},
  yaxis: {{title:'Latitude (°N)',  fixedrange:false, scaleanchor:'x'}},
  coloraxis: {{colorbar: {{thickness:14, len:0.8, x:1.01}}}},
}};

function makeHeatmap(z, cs, title_z) {{
  return [{{
    type: 'heatmap', z: z,
    x: LONS, y: LATS,
    colorscale: cs,
    coloraxis: 'coloraxis',
    showscale: true,
    hoverongaps: false,
    hovertemplate: 'lon: %{{x:.4f}}<br>lat: %{{y:.4f}}<br>' + title_z + ': %{{z:.3f}}<extra></extra>',
    zsmooth: 'best',
  }}];
}}

function makeVelScatter(ucx_t, ucy_t, umag_t) {{
  const lons = [], lats = [], us = [], vs = [], mags = [], txt = [];
  const step = 3;  // every 3rd cell for quiver readability
  for (let j = 0; j < LATS.length; j += step) {{
    for (let i = 0; i < LONS.length; i += step) {{
      const u = ucx_t[j][i], v = ucy_t[j][i], m = umag_t[j][i];
      if (u == null || m == null || m < 0.005) continue;
      lons.push(LONS[i]); lats.push(LATS[j]);
      us.push(u); vs.push(v); mags.push(m);
      txt.push(`u: ${{u.toFixed(3)}} m/s<br>v: ${{v.toFixed(3)}} m/s<br>|U|: ${{m.toFixed(3)}} m/s`);
    }}
  }}
  // Scale for display
  const scale = 0.002;
  const traces = [];
  for (let k = 0; k < lons.length; k++) {{
    traces.push({{
      type: 'scatter', mode: 'lines',
      x: [lons[k], lons[k] + us[k]*scale],
      y: [lats[k], lats[k] + vs[k]*scale],
      line: {{color: velColor(mags[k]), width: 1.5}},
      showlegend: false, hoverinfo: 'skip',
    }});
  }}
  // Scatter dots at base
  traces.push({{
    type: 'scatter', mode: 'markers',
    x: lons, y: lats,
    marker: {{
      color: mags, colorscale: CS_VEL,
      size: 5, cmin: 0, cmax: 0.5,
      colorbar: {{title: '|U| (m/s)', thickness:14, len:0.8, x:1.01}},
      showscale: true,
    }},
    text: txt, hovertemplate: '%{{text}}<extra></extra>',
    showlegend: false,
  }});
  return traces;
}}

function velColor(mag) {{
  const t = Math.min(mag / 0.5, 1);
  const r = Math.round(t * 200);
  const g = Math.round((1-t) * 150);
  const b = Math.round(200 * (1-t));
  return `rgb(${{r}},${{g}},${{b}})`;
}}

// ── init ──────────────────────────────────────────────────────────────────────
function initMaps() {{
  const lay_wl = {{...LAY, title: '', coloraxis: {{...LAY.coloraxis,
    colorbar: {{...LAY.coloraxis.colorbar, title:'WL (m)'}},
    colorscale: CS_WL,
  }}}};
  Plotly.newPlot('map-wl',  makeHeatmap(S1[0], CS_WL, 'WL'), lay_wl, {{responsive:true}});
  Plotly.newPlot('map-vel', makeVelScatter(UCX[0], UCY[0], UMAG[0]),
    {{...LAY, title:''}}, {{responsive:true}});
  const lay_hw = {{...LAY, coloraxis: {{...LAY.coloraxis,
    colorbar: {{...LAY.coloraxis.colorbar, title:'Hwav (m)'}},
    colorscale: CS_HWAV, cmin:0, cmax:1.5,
  }}}};
  Plotly.newPlot('map-hwav', makeHeatmap(HWAV[0], CS_HWAV, 'Hwav'), lay_hw, {{responsive:true}});
}}

function updateMaps(t) {{
  Plotly.restyle('map-wl',  {{z: [S1[t]]}},   [0]);
  if (activeTab === 'vel') {{
    Plotly.react('map-vel', makeVelScatter(UCX[t], UCY[t], UMAG[t]), {{...LAY, title:''}});
  }}
  Plotly.restyle('map-hwav', {{z: [HWAV[t]]}}, [0]);
}}

function switchTab(tab) {{
  activeTab = tab;
  document.querySelectorAll('.tab-btn').forEach((b, i) => {{
    b.classList.toggle('active', ['wl','vel','hwav'][i] === tab);
  }});
  ['wl','vel','hwav'].forEach(t => {{
    document.getElementById('tab-'+t).classList.toggle('active', t === tab);
  }});
  if (tab === 'vel') updateMaps(currentT);
}}

function onSlider(val) {{
  currentT = parseInt(val);
  document.getElementById('time-label').textContent = TIMES[currentT];
  updateMaps(currentT);
  updateStationCharts(currentT);
}}

function togglePlay() {{
  playing = !playing;
  document.getElementById('play-btn').textContent = playing ? '⏸ Pause' : '▶ Play';
  if (playing) {{
    playTimer = setInterval(() => {{
      currentT = (currentT + 1) % TIMES.length;
      document.getElementById('time-slider').value = currentT;
      document.getElementById('time-label').textContent = TIMES[currentT];
      updateMaps(currentT);
      updateStationCharts(currentT);
    }}, 300);
  }} else {{
    clearInterval(playTimer);
  }}
}}

// ── station charts ────────────────────────────────────────────────────────────
function buildStationCards() {{
  const grid = document.getElementById('station-grid');
  Object.keys(STA_INFO).forEach(name => {{
    const card = document.createElement('div');
    card.className = 'station-card';
    card.innerHTML = `<h3>${{name}}</h3>
      <div class="sparkline-div" id="spark-${{name}}"></div>
      <div class="main-chart-div" id="chart-${{name}}"></div>`;
    grid.appendChild(card);

    // Sparkline: hourly obs resampled to 1pt/hr
    const obs = STA_OBS[name];
    const mod = STA_MODEL[name];
    if (obs) {{
      Plotly.newPlot('spark-'+name, [{{
        x: obs.t, y: obs.wl,
        type: 'scatter', mode: 'lines',
        line: {{color: '#555', width: 1.2}},
        showlegend: false,
        hovertemplate: '%{{x}}<br>Obs: %{{y:.3f}} m<extra></extra>',
      }}], {{
        margin: {{l:0,r:0,t:0,b:0}},
        xaxis: {{visible:false}}, yaxis: {{visible:false}},
        paper_bgcolor:'transparent', plot_bgcolor:'transparent',
        showlegend:false,
      }}, {{staticPlot:false, responsive:true}});
    }}

    // Main chart: obs + model on current day
    drawMainChart(name, 0);
  }});
}}

function drawMainChart(name, tIdx) {{
  const tStr = TIMES[tIdx].split(' ')[0];  // current day
  const obs = STA_OBS[name];
  const mod = STA_MODEL[name];
  const traces = [];
  if (obs) {{
    const mask = obs.t.map(t => t.startsWith(tStr));
    const ox = obs.t.filter((_, i) => mask[i]);
    const oy = obs.wl.filter((_, i) => mask[i]);
    if (ox.length) traces.push({{
      x: ox, y: oy, name: 'Observed',
      type: 'scatter', mode: 'lines+markers',
      line: {{color: '#1F497D', width: 2}},
      marker: {{size: 4}},
    }});
  }}
  if (mod) {{
    const mask = mod.t.map(t => t.startsWith(tStr));
    const mx = mod.t.filter((_, i) => mask[i]);
    const my = mod.wl.filter((_, i) => mask[i]);
    if (mx.length) traces.push({{
      x: mx, y: my, name: 'Model v04AE',
      type: 'scatter', mode: 'lines',
      line: {{color: '#C55A11', width: 2, dash: 'dot'}},
    }});
  }}
  if (!traces.length) return;
  Plotly.react('chart-'+name, traces, {{
    margin: {{l:40,r:10,t:6,b:30}},
    xaxis: {{title:''}},
    yaxis: {{title:'WL (m)', nticks:4}},
    legend: {{orientation:'h', x:0, y:1.12, font:{{size:10}}}},
    paper_bgcolor:'transparent', plot_bgcolor:'#f5f7fa',
    showlegend: true, height: 200,
  }}, {{responsive:true}});
}}

function updateStationCharts(tIdx) {{
  Object.keys(STA_INFO).forEach(name => drawMainChart(name, tIdx));
}}

// ── start ─────────────────────────────────────────────────────────────────────
initMaps();
buildStationCards();
</script>
</body>
</html>"""

    HTML.parent.mkdir(parents=True, exist_ok=True)
    HTML.write_text(html, encoding='utf-8')
    print(f'HTML saved: {HTML}  ({HTML.stat().st_size//1024} kB)')


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    prepare_data()
    build_html()
    print('Done.')
