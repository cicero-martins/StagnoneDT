"""Build WetWise Hydrodynamics portal — external-file architecture.

Full 30-min temporal resolution (433 timesteps).  Multi-resolution pyramid:
  coarse: full domain ~0.008 deg   fine: lagoon only ~0.003 deg
Land boundary overlay parsed from sicily2.ldb (simplified GeoJSON).

Outputs — outputs/wetwise_tab/demo_hydrodynamics/
  index.html
  data/meta.json              times, grid params, colour ranges, station series
  data/coarse_s1.json         WL all frames (coarse)
  data/coarse_hwav.json       Hwav all frames (coarse)
  data/fine_s1.json           WL all frames (fine)
  data/fine_hwav.json         Hwav all frames (fine)
  data/vel/coarse_d{nn}.json  velocity per calendar-day (coarse)
  data/vel/fine_d{nn}.json    velocity per calendar-day (fine)
  data/land.geojson           simplified land boundary

Run portal:
  python -m http.server 8080 --directory outputs/wetwise_tab/demo_hydrodynamics
  open http://localhost:8080

Delete demo_coarse.nc / demo_fine.nc to force re-grid.
"""
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import xarray as xr

ROOT     = Path(__file__).resolve().parents[1]
V04AE    = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
INSITU   = ROOT / 'data' / 'processed' / 'insitu_2025-26'
LDB      = ROOT / 'model' / 'dflowfm_v04AE' / 'sicily2.ldb'
OUT_DIR  = ROOT / 'outputs' / 'wetwise_tab' / 'demo_hydrodynamics'
DATA_DIR = OUT_DIR / 'data'
CACHE_C  = OUT_DIR / 'demo_coarse.nc'
CACHE_F  = OUT_DIR / 'demo_fine.nc'
HTML     = OUT_DIR / 'index.html'

FULL_LON = (11.95, 12.57);  FULL_LAT = (37.68, 38.12);  DX_C = DY_C = 0.008
LAG_LON  = (12.36, 12.54);  LAG_LAT  = (37.78, 37.99);  DX_F = DY_F = 0.003
T_STEP          = 1      # every model output step (1800 s = 30 min)
VEL_MAX_FINE    = 0.2    # hardcoded lagoon velocity scale (m/s)
ZOOM_FINE       = 12     # Leaflet zoom threshold for fine grid
FRAMES_PER_DAY  = 48     # 48 × 30 min = 24 h
SENTINEL        = -9999  # NaN substitute in scalar JSON (checked in JS)

VARS = ['mesh2d_s1', 'mesh2d_ucx', 'mesh2d_ucy', 'mesh2d_hwav']

STATIONS = {
    'BocaNord':    {'csv_wl': 'BN_wl_UTC.csv',  'lon': 12.4245, 'lat': 37.9008},
    'BocaSud':     {'csv_wl': 'BS_wl_UTC.csv',   'lon': 12.4356, 'lat': 37.8312},
    'AltaVilaEst': {'csv_wl': 'AE_wl_UTC.csv',   'lon': 12.4782, 'lat': 37.8660},
}


# ── Fast interpolator ─────────────────────────────────────────────────────

class FastGridInterp:
    """Delaunay triangulation built once; re-uses barycentric coords per frame."""
    def __init__(self, pts, xi):
        from scipy.spatial import Delaunay
        tri = Delaunay(pts)
        si  = tri.find_simplex(xi)
        self._mask = si >= 0
        si_c = np.where(self._mask, si, 0)
        T    = tri.transform[si_c, :2, :]
        r    = xi - tri.transform[si_c, 2]
        b2   = np.einsum('mij,mj->mi', T, r)
        bary = np.c_[b2, 1 - b2.sum(1)].astype(np.float32)
        self._bary  = bary[self._mask]
        self._verts = tri.simplices[si_c][self._mask]
        self._size  = len(xi)

    def __call__(self, values):
        out = np.full(self._size, np.nan, np.float32)
        if self._mask.any():
            v = values[self._verts]
            out[self._mask] = (v * self._bary).sum(1)
        return out


# ── Step 1: Regrid ────────────────────────────────────────────────────────

def _cache_valid(path, expected_n_t):
    if not path.exists():
        return False
    try:
        ds = xr.open_dataset(path)
        ok = ds.sizes.get('time', 0) == expected_n_t
        ds.close()
        return ok
    except Exception:
        return False


def prepare_data():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import dfm_tools as dfmt
    from scipy.spatial import cKDTree

    print('Opening partitioned map.nc ...')
    ds = dfmt.open_partitioned_dataset(
        str(V04AE / 'Stagnone_dxy01_15m_0*_map.nc'))
    cx = ds['mesh2d_face_x'].values
    cy = ds['mesh2d_face_y'].values
    print(f'  Face count: {cx.shape[0]}')

    n_times = ds.sizes['time']
    t_idx   = list(range(0, n_times, T_STEP))
    times   = ds['time'].values[t_idx]
    n_t     = len(t_idx)
    print(f'  Timesteps selected: {n_t}  ({n_t*0.5:.1f} h = {n_t*0.5/24:.1f} days)')

    need_c = not _cache_valid(CACHE_C, n_t)
    need_f = not _cache_valid(CACHE_F, n_t)
    if not need_c and not need_f:
        print('Caches are up to date — skipping regrid')
        ds.close(); return

    def get_surface(da):
        for d in da.dims:
            if 'layer' in d.lower() or 'nlay' in d.lower():
                return da.isel({d: -1})
        return da

    configs = []
    if need_c: configs.append(('coarse', FULL_LON, FULL_LAT, DX_C, DY_C, CACHE_C))
    if need_f: configs.append(('fine',   LAG_LON,  LAG_LAT,  DX_F, DY_F, CACHE_F))

    for label, lons, lats, dx, dy, cache in configs:
        lon_vec = np.arange(lons[0], lons[1] + dx / 2, dx)
        lat_vec = np.arange(lats[0], lats[1] + dy / 2, dy)
        ny, nx  = len(lat_vec), len(lon_vec)
        lon2, lat2 = np.meshgrid(lon_vec, lat_vec)
        xi = np.column_stack([lon2.ravel(), lat2.ravel()])

        buf = 0.1
        dom = ((cx >= lons[0]-buf) & (cx <= lons[1]+buf) &
               (cy >= lats[0]-buf) & (cy <= lats[1]+buf))
        pts = np.column_stack([cx[dom], cy[dom]])

        tree = cKDTree(pts)
        dists, _ = tree.query(xi)
        far = dists > dx * 2.0

        print(f'  [{label}] {nx}×{ny} grid, {int(far.sum())} land cells'
              f' — building interpolator ...')
        interp = FastGridInterp(pts, xi)

        grids = {v: np.full((n_t, ny, nx), np.nan, np.float32) for v in VARS}

        for i, ti in enumerate(t_idx):
            if i % 50 == 0:
                print(f'    [{label}] frame {i}/{n_t} ...')
            for vn in VARS:
                if vn not in ds:
                    continue
                da   = get_surface(ds[vn].isel(time=ti))
                vals = da.values.astype(np.float32)
                vals[np.abs(vals) > 1e9] = np.nan
                gi = interp(vals[dom])
                gi[far] = np.nan
                grids[vn][i] = gi.reshape(ny, nx)

        ds_out = xr.Dataset(
            {vn: xr.DataArray(grids[vn], dims=['time', 'lat', 'lon'])
             for vn in VARS},
            coords={'time': times, 'lat': lat_vec, 'lon': lon_vec}
        )
        ds_out.to_netcdf(cache)
        print(f'    Saved {cache}  ({cache.stat().st_size // 1024} kB)')

    ds.close()


# ── Step 2: Station obs ───────────────────────────────────────────────────

def load_stations():
    T0, T1 = pd.Timestamp('2025-07-01'), pd.Timestamp('2025-07-10')
    result = {}
    for name, info in STATIONS.items():
        fp = INSITU / info['csv_wl']
        if not fp.exists():
            result[name] = None; continue
        df = pd.read_csv(fp, parse_dates=['time'], index_col='time').sort_index().loc[T0:T1]
        if df.empty:
            result[name] = None; continue
        wl_cols = [c for c in df.columns if any(k in c.lower()
                   for k in ('wl', 'waterlevel', 'water_level', 'h_m', 'level'))]
        col = wl_cols[0] if wl_cols else df.columns[0]
        result[name] = df[col].resample('30min').mean().dropna()
    return result


# ── Helpers ───────────────────────────────────────────────────────────────

def _arr_to_json(arr_3d, dp=2):
    """Convert float32 array to nested Python lists; NaN → SENTINEL."""
    a = np.round(arr_3d.astype(np.float64), dp)
    a[np.isnan(a)] = SENTINEL
    return a.tolist()


def _vel_day_json(ucx_3d, ucy_3d, t0, t1):
    """Return {'u': [...], 'v': [...]} with N→S-scanned flat arrays per frame."""
    u_frames, v_frames = [], []
    for ti in range(t0, t1):
        u_ns = np.flipud(ucx_3d[ti]).ravel()
        v_ns = np.flipud(ucy_3d[ti]).ravel()
        u_frames.append([None if math.isnan(float(x)) else round(float(x), 3) for x in u_ns])
        v_frames.append([None if math.isnan(float(x)) else round(float(x), 3) for x in v_ns])
    return {'u': u_frames, 'v': v_frames}


def _parse_ldb_geojson(path, tolerance=0.0003):
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    segments = []
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]

    i = 0
    while i < len(lines):
        if i + 1 < len(lines):
            parts = lines[i + 1].split()
            if len(parts) == 2:
                try:
                    n, nc = int(parts[0]), int(parts[1])
                    if nc == 2:
                        coords = []
                        for j in range(i + 2, i + 2 + n):
                            if j < len(lines):
                                xy = lines[j].split()
                                if len(xy) >= 2:
                                    coords.append((float(xy[0]), float(xy[1])))
                        if len(coords) >= 3:
                            segments.append(coords)
                        i += 2 + n
                        continue
                except (ValueError, IndexError):
                    pass
        i += 1

    features = []
    for seg in segments:
        coords = seg if seg[0] == seg[-1] else seg + [seg[0]]
        try:
            poly = Polygon(coords)
            poly = make_valid(poly)
            poly = poly.simplify(tolerance, preserve_topology=True)
            if poly and not poly.is_empty:
                features.append({
                    'type': 'Feature',
                    'geometry': poly.__geo_interface__,
                    'properties': {}
                })
        except Exception:
            pass

    return json.dumps({'type': 'FeatureCollection', 'features': features})


# ── Step 3: Write data files ──────────────────────────────────────────────

def build_data_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / 'vel').mkdir(exist_ok=True)

    print('Loading caches ...')
    ds_c = xr.open_dataset(CACHE_C)
    ds_f = xr.open_dataset(CACHE_F)

    times_pd = pd.DatetimeIndex(ds_c['time'].values)
    n_t      = len(times_pd)
    t_labels = [str(t)[:16].replace('T', ' ') for t in times_pd]
    n_days   = math.ceil(n_t / FRAMES_PER_DAY)

    lons_c, lats_c = ds_c['lon'].values, ds_c['lat'].values
    lons_f, lats_f = ds_f['lon'].values, ds_f['lat'].values

    # Color ranges from coarse domain
    s1_all  = ds_c['mesh2d_s1'].values
    wl_abs  = float(np.nanpercentile(np.abs(s1_all), 98))
    wl_vmin = round(-wl_abs, 3)
    wl_vmax = round(wl_abs, 3)

    hw_data    = ds_c['mesh2d_hwav'].values if 'mesh2d_hwav' in ds_c else None
    hwav_vmax  = round(float(np.nanpercentile(hw_data[~np.isnan(hw_data)], 98)), 2) \
                 if hw_data is not None else 1.0

    sp_c      = np.sqrt(ds_c['mesh2d_ucx'].values**2 + ds_c['mesh2d_ucy'].values**2)
    vel_max_c = round(float(np.nanpercentile(sp_c, 95)), 3)
    vel_max_f = VEL_MAX_FINE

    print(f'  WL [{wl_vmin},{wl_vmax}] m  Hwav max {hwav_vmax} m'
          f'  vel coarse={vel_max_c} fine={vel_max_f}')

    # Station data
    sta_obs = load_stations()
    sta_obs_json = {
        n: {'t': [str(i)[:16].replace('T', ' ') for i in s.index],
            'wl': s.values.round(4).tolist()}
           if s is not None else None
        for n, s in sta_obs.items()
    }
    sta_model_json = {}
    for name, info in STATIONS.items():
        ilon = int(np.argmin(np.abs(lons_c - info['lon'])))
        ilat = int(np.argmin(np.abs(lats_c - info['lat'])))
        wl = [None if math.isnan(v := float(ds_c['mesh2d_s1'].values[i, ilat, ilon]))
              else round(v, 4) for i in range(n_t)]
        sta_model_json[name] = {'t': t_labels, 'wl': wl}

    # meta.json
    meta = {
        'times': t_labels, 'n_t': n_t, 'n_days': n_days,
        'frames_per_day': FRAMES_PER_DAY, 'sentinel': SENTINEL,
        'coarse': {'lons': lons_c.round(6).tolist(), 'lats': lats_c.round(6).tolist(),
                   'nx': int(len(lons_c)), 'ny': int(len(lats_c)), 'vel_max': vel_max_c},
        'fine':   {'lons': lons_f.round(6).tolist(), 'lats': lats_f.round(6).tolist(),
                   'nx': int(len(lons_f)), 'ny': int(len(lats_f)), 'vel_max': vel_max_f},
        'wl_vmin': wl_vmin, 'wl_vmax': wl_vmax, 'hwav_vmax': hwav_vmax,
        'sta_info':  {n: {'lon': STATIONS[n]['lon'], 'lat': STATIONS[n]['lat']} for n in STATIONS},
        'sta_obs':   sta_obs_json,
        'sta_model': sta_model_json,
    }
    p = DATA_DIR / 'meta.json'
    p.write_text(json.dumps(meta), encoding='utf-8')
    print(f'  meta.json  ({p.stat().st_size // 1024} kB)')

    # Scalar field files
    for label, ds in [('coarse', ds_c), ('fine', ds_f)]:
        for vn, fname in [('mesh2d_s1', f'{label}_s1.json'),
                          ('mesh2d_hwav', f'{label}_hwav.json')]:
            arr = ds[vn].values if vn in ds else None
            if arr is None:
                n = len(ds['lat']) if label == 'coarse' else len(ds_f['lat'])
                m = len(ds['lon']) if label == 'coarse' else len(ds_f['lon'])
                frames = [[[SENTINEL]*m]*n] * n_t
            else:
                frames = _arr_to_json(arr, dp=2)
            p = DATA_DIR / fname
            p.write_text(json.dumps({'frames': frames, 'sentinel': SENTINEL}),
                         encoding='utf-8')
            print(f'  {fname}  ({p.stat().st_size // 1024} kB)')

    # Velocity day files
    for label, ds in [('coarse', ds_c), ('fine', ds_f)]:
        ucx = ds['mesh2d_ucx'].values
        ucy = ds['mesh2d_ucy'].values
        for day in range(n_days):
            t0 = day * FRAMES_PER_DAY
            t1 = min(t0 + FRAMES_PER_DAY, n_t)
            p = DATA_DIR / 'vel' / f'{label}_d{day:02d}.json'
            p.write_text(json.dumps(_vel_day_json(ucx, ucy, t0, t1)), encoding='utf-8')
        total_kb = sum((DATA_DIR/'vel'/f'{label}_d{d:02d}.json').stat().st_size
                       for d in range(n_days)) // 1024
        print(f'  vel/{label}_d*.json  ({n_days} files, {total_kb} kB total)')

    # Land boundary
    print('  Parsing land boundary ...')
    land_gj = _parse_ldb_geojson(LDB, tolerance=0.0003)
    p = DATA_DIR / 'land.geojson'
    p.write_text(land_gj, encoding='utf-8')
    print(f'  land.geojson  ({p.stat().st_size // 1024} kB)')

    ds_c.close()
    ds_f.close()


# ── Step 4: Build HTML ────────────────────────────────────────────────────

def build_html():
    print('Building HTML ...')

    wl_stops_js = json.dumps([
        [-0.5, '#2166ac'], [-0.2, '#92c5de'], [0.0, '#f7f7f7'],
        [0.2,  '#f4a582'], [0.5, '#ca0020'],
    ])
    hw_stops_js = json.dumps([
        [0.0, '#f7fcf5'], [0.25, '#74c476'], [0.65, '#238b45'], [1.0, '#00441b'],
    ])
    vel_colors_js = json.dumps([
        '#3288bd','#66c2a5','#abdda4','#e6f598','#fee08b','#fdae61','#f46d43','#d53e4f'
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WetWise — Stagnone Hydrodynamics</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet-velocity@2.1.0/dist/leaflet-velocity.min.css"/>
<script src="https://cdn.jsdelivr.net/npm/leaflet-velocity@2.1.0/dist/leaflet-velocity.min.js"></script>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;
           background:#0d1220;color:#dde4f0}}
#loader{{position:fixed;top:0;left:0;width:100%;height:100%;background:#0d1220;
         z-index:9999;display:flex;flex-direction:column;align-items:center;
         justify-content:center;gap:14px;transition:opacity .4s}}
#loader.done{{opacity:0;pointer-events:none}}
.ld-title{{font-size:1.3em;font-weight:700;color:#7bb3f0;letter-spacing:1px}}
.ld-sub{{font-size:.82em;color:#445}}
.ld-bar-wrap{{width:220px;height:4px;background:#1e3050;border-radius:2px}}
.ld-bar{{height:100%;background:#4a90d9;border-radius:2px;transition:width .3s}}
#app{{display:flex;flex-direction:column;height:100vh}}
#main{{display:flex;flex:1;overflow:hidden;min-height:0}}
#panel{{width:290px;background:rgba(8,12,26,.97);border-right:1px solid #1e3050;
        display:flex;flex-direction:column;overflow-y:auto;z-index:600;flex-shrink:0}}
.ph{{padding:14px 16px 10px;border-bottom:1px solid #1e3050}}
.ph-title{{font-size:1.05em;font-weight:700;color:#7bb3f0;letter-spacing:.5px}}
.ph-sub{{font-size:.72em;color:#556;margin-top:3px}}
.ph-run{{font-size:.72em;color:#4a7;margin-top:2px}}
.ph-res{{font-size:.68em;color:#4a90d9;margin-top:4px;font-weight:600}}
.li{{padding:10px 14px;border-bottom:1px solid #111d33;transition:background .15s}}
.li:hover{{background:rgba(30,60,100,.2)}}
.li-row1{{display:flex;align-items:center;gap:7px;margin-bottom:4px}}
.eye{{background:none;border:none;cursor:pointer;font-size:1.05em;padding:0;
      width:22px;color:#2a4a70;transition:color .15s}}
.eye.on{{color:#7bb3f0}}
.li-name{{font-size:.87em;font-weight:600;color:#b8ccec;flex:1}}
.li-meta{{font-size:.7em;color:#445;padding-left:29px;margin-bottom:4px}}
.vel-load{{font-size:.65em;color:#4a7;padding-left:29px;margin-top:-2px;margin-bottom:2px}}
.cb-wrap{{padding-left:29px}}
.cb{{height:6px;border-radius:2px}}
.cb-labels{{display:flex;justify-content:space-between;font-size:.67em;color:#557;margin-top:2px}}
.li.disabled .li-name{{color:#2a3a50}}
.li.disabled .eye{{color:#1a2a40;cursor:not-allowed}}
.sta-toggle{{padding:10px 14px;background:none;border:none;border-top:1px solid #1e3050;
             cursor:pointer;color:#7bb3f0;font-size:.8em;text-align:left;width:100%;
             transition:background .15s}}
.sta-toggle:hover{{background:rgba(30,60,100,.2)}}
#sta-sec{{display:none;padding:8px 10px 6px}}
.sc{{background:rgba(10,16,36,.8);border-radius:4px;padding:8px;margin-bottom:8px}}
.sc h4{{font-size:.77em;color:#7bb3f0;margin-bottom:4px}}
#map-wrap{{flex:1;position:relative;overflow:hidden}}
#map{{width:100%;height:100%}}
#tbar{{background:rgba(6,10,22,.97);border-top:1px solid #1e3050;
       padding:7px 16px;display:flex;align-items:center;gap:12px;z-index:600;flex-shrink:0}}
#play-btn{{background:#1d4080;color:#c8d8f0;border:none;border-radius:4px;
           padding:5px 14px;cursor:pointer;font-size:.84em;flex-shrink:0;transition:background .15s}}
#play-btn:hover{{background:#2a5cb0}}
#tlabel{{font-size:.83em;color:#7bb3f0;font-weight:600;white-space:nowrap;min-width:150px;flex-shrink:0}}
#tslider{{flex:1;accent-color:#4a90d9;cursor:pointer}}
</style>
</head>
<body>

<div id="loader">
  <div class="ld-title">WetWise</div>
  <div class="ld-sub">Stagnone di Marsala Digital Twin</div>
  <div id="ld-status" class="ld-sub">Initialising...</div>
  <div class="ld-bar-wrap"><div class="ld-bar" id="ld-bar" style="width:2%"></div></div>
</div>

<div id="app">
<div id="main">
  <div id="panel">
    <div class="ph">
      <div class="ph-title">WetWise</div>
      <div class="ph-sub">Stagnone di Marsala Digital Twin</div>
      <div class="ph-run">v04AE &nbsp;&#183;&nbsp; Jul 1&#8211;10 2025</div>
      <div class="ph-res" id="res-badge">&#9679; Coarse view (zoom &#8805; {ZOOM_FINE} for lagoon)</div>
    </div>
    <div id="layer-list"></div>
    <button class="sta-toggle" onclick="toggleSta()">&#9654; Station time series</button>
    <div id="sta-sec"></div>
  </div>
  <div id="map-wrap"><div id="map"></div></div>
</div>
<div id="tbar">
  <button id="play-btn" onclick="togglePlay()">&#9654; Play</button>
  <span id="tlabel">—</span>
  <input type="range" id="tslider" min="0" max="0" value="0" oninput="seek(+this.value)">
</div>
</div>

<script>
// ── constants ────────────────────────────────────────────────────────────────
const ZOOM_FINE      = {ZOOM_FINE};
const FRAMES_PER_DAY = {FRAMES_PER_DAY};
const WL_STOPS   = {wl_stops_js};
const HWAV_STOPS = {hw_stops_js};
const VEL_COLORS = {vel_colors_js};

// ── runtime state ────────────────────────────────────────────────────────────
let TIMES=[], GRIDS={{}}, SENTINEL=-9999;
let WL_VMIN, WL_VMAX, HWAV_VMAX;
let STA_OBS={{}}, STA_MODEL={{}}, STA_INFO={{}};
let velCache={{coarse:{{}},fine:{{}}}};
let velLoadProgress=0, N_DAYS=10;
let activeGrid='coarse', currentT=0;
let playing=false, playTimer=null, staBuilt=false;
let map, LAYERS;

// ── loading overlay ──────────────────────────────────────────────────────────
function setLoad(pct,msg){{
  document.getElementById('ld-bar').style.width=pct+'%';
  document.getElementById('ld-status').textContent=msg;
}}
function hideLoader(){{
  const l=document.getElementById('loader');
  l.classList.add('done');
  setTimeout(()=>l.style.display='none',500);
}}

// ── fetch helper ─────────────────────────────────────────────────────────────
async function fetchJSON(url){{
  const r=await fetch(url);
  if(!r.ok) throw new Error('fetch '+url+' → '+r.status);
  return r.json();
}}

// ── colour utils ─────────────────────────────────────────────────────────────
function hexRgb(h){{return[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]}}
function colorFunc(stops,vmin,vmax){{
  const vs=stops.map(s=>s[0]),cs=stops.map(s=>hexRgb(s[1]));
  return v=>{{
    if(v===null||v===undefined||v<=SENTINEL+1)return null;
    const nv=(v-vmin)/(vmax-vmin);
    const nvs=vs.map(x=>(x-vmin)/(vmax-vmin));
    if(nv<=nvs[0])return cs[0];
    for(let k=0;k<nvs.length-1;k++){{
      if(nv>=nvs[k]&&nv<=nvs[k+1]){{
        const t=(nv-nvs[k])/(nvs[k+1]-nvs[k]);
        return[0,1,2].map(c=>Math.round(cs[k][c]+t*(cs[k+1][c]-cs[k][c])));
      }}
    }}
    return cs[cs.length-1];
  }};
}}
function cmGrad(stops,vmin,vmax){{
  return stops.map(([v,c])=>`${{c}} ${{((v-vmin)/(vmax-vmin)*100).toFixed(1)}}%`).join(',');
}}

// ── FieldLayer ────────────────────────────────────────────────────────────────
class FieldLayer{{
  constructor(cfn){{this.cfn=cfn;this.ov=null;this.on=false;this._d=null;this._lo=null;this._la=null;}}
  _bounds(){{const lo=this._lo,la=this._la;return[[la[0],lo[0]],[la[la.length-1],lo[lo.length-1]]];}}
  setGrid(lo,la,d){{this._lo=lo;this._la=la;this._d=d;if(this.ov)this.ov.setBounds(this._bounds());}}
  show(m,lo,la,d){{
    this.setGrid(lo,la,d);
    if(!this.ov)this.ov=L.imageOverlay('',this._bounds(),{{opacity:.75,interactive:false,zIndex:200}});
    if(!this.on){{this.ov.addTo(m);this.on=true;}}
  }}
  hide(){{if(this.on&&this.ov){{this.ov.remove();this.on=false;}}}}
  update(t){{if(this.on&&this._d)this._render(t);}}
  _render(t){{
    const d=this._d[t],ny=this._la.length,nx=this._lo.length;
    const cv=document.createElement('canvas');cv.width=nx;cv.height=ny;
    const ctx=cv.getContext('2d'),img=ctx.createImageData(nx,ny);
    for(let j=0;j<ny;j++){{
      const r=ny-1-j;
      for(let i=0;i<nx;i++){{
        const v=d[r][i],idx=(j*nx+i)*4;
        if(v===null||v===undefined||v<=SENTINEL+1){{img.data[idx+3]=0;continue;}}
        const rgb=this.cfn(v);
        if(!rgb){{img.data[idx+3]=0;continue;}}
        img.data[idx]=rgb[0];img.data[idx+1]=rgb[1];img.data[idx+2]=rgb[2];img.data[idx+3]=200;
      }}
    }}
    ctx.putImageData(img,0,0);
    this.ov.setUrl(cv.toDataURL('image/png'));
  }}
}}

// ── VelLayer ──────────────────────────────────────────────────────────────────
class VelLayer{{
  constructor(){{this.lyr=null;this.map=null;this.on=false;}}
  show(m){{this.map=m;this.on=true;this.update(currentT);}}
  hide(){{this._rm();this.on=false;}}
  _rm(){{if(this.lyr){{if(this.map)this.map.removeLayer(this.lyr);this.lyr=null;}}}}
  update(t){{
    if(!this.on||!this.map)return;
    const g=activeGrid,day=Math.floor(t/FRAMES_PER_DAY),ft=t%FRAMES_PER_DAY;
    if(!velCache[g][day])return;
    const frames=velCache[g][day];
    if(!frames||!frames[ft])return;
    this._rm();
    this.lyr=L.velocityLayer({{
      displayValues:true,
      displayOptions:{{velocityType:'Current',position:'bottomleft',
                       emptyString:'No data',angleConvention:'bearingCCW',speedUnit:'m/s'}},
      data:frames[ft],maxVelocity:GRIDS[g].vel_max,
      velocityScale:0.012,colorScale:VEL_COLORS,lineWidth:2,particleAge:90,
    }}).addTo(this.map);
  }}
}}

// ── vel data helpers ─────────────────────────────────────────────────────────
function buildVelFrames(dayData,grid){{
  const la1=grid.lats[grid.lats.length-1],lo1=grid.lons[0];
  const la2=grid.lats[0],lo2=grid.lons[grid.lons.length-1];
  const dx=grid.lons[1]-grid.lons[0],dy=grid.lats[1]-grid.lats[0];
  const hdr={{la1,lo1,la2,lo2,dx,dy,nx:grid.nx,ny:grid.ny,parameterUnit:'m.s-1'}};
  return dayData.u.map((u,i)=>[
    {{header:{{...hdr,parameterCategory:2,parameterNumber:2}},data:u}},
    {{header:{{...hdr,parameterCategory:2,parameterNumber:3}},data:dayData.v[i]}},
  ]);
}}

function updateVelLoadBadge(){{
  const el=document.getElementById('vel-load-badge');
  if(!el)return;
  if(velLoadProgress>=N_DAYS){{el.textContent='';el.style.display='none';}}
  else el.textContent=`Loading velocity: ${{velLoadProgress}}/${{N_DAYS}} days...`;
}}

// ── main data load ────────────────────────────────────────────────────────────
async function loadAll(){{
  try{{
    setLoad(5,'Fetching metadata...');
    const meta=await fetchJSON('data/meta.json');
    TIMES=meta.times; N_DAYS=meta.n_days; SENTINEL=meta.sentinel;
    WL_VMIN=meta.wl_vmin; WL_VMAX=meta.wl_vmax; HWAV_VMAX=meta.hwav_vmax;
    STA_OBS=meta.sta_obs; STA_MODEL=meta.sta_model; STA_INFO=meta.sta_info;

    setLoad(15,'Loading Water Level...');
    const [cs1,fs1]=await Promise.all([
      fetchJSON('data/coarse_s1.json'),fetchJSON('data/fine_s1.json')
    ]);
    setLoad(40,'Loading Wave Height...');
    const [chw,fhw]=await Promise.all([
      fetchJSON('data/coarse_hwav.json'),fetchJSON('data/fine_hwav.json')
    ]);
    setLoad(75,'Initialising map...');

    GRIDS.coarse={{...meta.coarse,s1:cs1.frames,hwav:chw.frames}};
    GRIDS.fine  ={{...meta.fine,  s1:fs1.frames,hwav:fhw.frames}};

    let landGJ=null;
    try{{landGJ=await fetchJSON('data/land.geojson');}}catch(e){{console.warn('land.geojson not found');}}

    setLoad(90,'Rendering...');
    hideLoader();
    initMap(landGJ);

    loadVelBackground();
  }}catch(e){{
    document.getElementById('ld-status').textContent='Error: '+e.message;
    console.error(e);
  }}
}}

async function loadVelBackground(){{
  for(let day=0;day<N_DAYS;day++){{
    const dd=String(day).padStart(2,'0');
    try{{
      const [cd,fd]=await Promise.all([
        fetchJSON(`data/vel/coarse_d${{dd}}.json`),
        fetchJSON(`data/vel/fine_d${{dd}}.json`)
      ]);
      velCache.coarse[day]=buildVelFrames(cd,GRIDS.coarse);
      velCache.fine[day]  =buildVelFrames(fd,GRIDS.fine);
      velLoadProgress=day+1;
      updateVelLoadBadge();
      if(LAYERS&&LAYERS.vel&&LAYERS.vel.on){{
        if(Math.floor(currentT/FRAMES_PER_DAY)===day) LAYERS.vel.update(currentT);
      }}
    }}catch(e){{console.warn('vel day',dd,e);}}
  }}
}}

// ── map init ─────────────────────────────────────────────────────────────────
function initMap(landGJ){{
  map=L.map('map',{{center:[37.89,12.27],zoom:10,zoomControl:true,preferCanvas:true}});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
    attribution:'&copy;<a href="https://www.openstreetmap.org/copyright">OSM</a> &copy;<a href="https://carto.com">CARTO</a>',
    subdomains:'abcd',maxZoom:19,
  }}).addTo(map);

  // Colour functions
  const cfnWL  =colorFunc(WL_STOPS,  WL_VMIN, WL_VMAX);
  const cfnHwav=colorFunc(HWAV_STOPS, 0,      HWAV_VMAX);

  LAYERS={{
    wl:   new FieldLayer(cfnWL),
    hwav: new FieldLayer(cfnHwav),
    vel:  new VelLayer(),
  }};

  // Default visible layers
  const g=GRIDS[activeGrid];
  LAYERS.wl.show(map,g.lons,g.lats,g.s1);
  LAYERS.wl.update(0);
  LAYERS.vel.show(map);  // will render when vel cache populates

  // Land boundary pane (above field layers)
  map.createPane('landPane');
  map.getPane('landPane').style.zIndex='450';
  if(landGJ){{
    L.geoJSON(landGJ,{{
      pane:'landPane',
      style:{{fillColor:'#090e1c',fillOpacity:0.93,color:'#0d1525',weight:0.5}}
    }}).addTo(map);
  }}

  // Zoom grid switch
  map.on('zoomend',function(){{
    const needed=map.getZoom()>=ZOOM_FINE?'fine':'coarse';
    if(needed!==activeGrid){{
      activeGrid=needed;
      const g2=GRIDS[activeGrid];
      if(LAYERS.wl.on)  {{LAYERS.wl.setGrid(g2.lons,g2.lats,g2.s1);  LAYERS.wl.update(currentT);}}
      if(LAYERS.hwav.on){{LAYERS.hwav.setGrid(g2.lons,g2.lats,g2.hwav);LAYERS.hwav.update(currentT);}}
      if(LAYERS.vel.on) LAYERS.vel.update(currentT);
      document.getElementById('res-badge').textContent=
        activeGrid==='fine'
          ? '\\u25CF Lagoon detail (\\u00d70.003\\u00b0)'
          : '\\u25CF Coarse view (zoom \\u2265 {ZOOM_FINE} for lagoon)';
      updateVelCbLabel();
    }}
  }});

  buildPanel();

  // Timeline
  const sl=document.getElementById('tslider');
  sl.max=TIMES.length-1;
  document.getElementById('tlabel').textContent=TIMES[0];
}}

// ── panel ─────────────────────────────────────────────────────────────────────
const eyeOn={{wl:true,vel:true,hwav:false}};
function updateVelCbLabel(){{
  const el=document.getElementById('cb-vel-max');
  if(el)el.textContent=GRIDS[activeGrid].vel_max.toFixed(2)+' m/s';
}}

function buildPanel(){{
  const wlGrad=`linear-gradient(to right,${{cmGrad(WL_STOPS,WL_VMIN,WL_VMAX)}})`;
  const hwGrad=`linear-gradient(to right,${{cmGrad(HWAV_STOPS,0,HWAV_VMAX)}})`;
  const vcGrad=`linear-gradient(to right,${{VEL_COLORS.join(',')}})`;
  const defs=[
    {{key:'wl',  label:'Water Level',      meta:'Jul 2025 &middot; surface &middot; 30 min',
      cb:wlGrad,cmin:WL_VMIN.toFixed(2),cmax:WL_VMAX.toFixed(2)+' m',maxId:'',dis:false}},
    {{key:'vel', label:'Surface Velocity', meta:'Jul 2025 &middot; surface &middot; 30 min',
      cb:vcGrad,cmin:'0',cmax:'... m/s',maxId:'cb-vel-max',dis:false}},
    {{key:'hwav',label:'Wave Height',      meta:'Jul 2025 &middot; surface &middot; 30 min',
      cb:hwGrad,cmin:'0',cmax:HWAV_VMAX.toFixed(2)+' m',maxId:'',dis:false}},
    {{key:'turb',label:'Turbidity',        meta:'Not available this run',
      cb:'',cmin:'',cmax:'',maxId:'',dis:true}},
  ];
  const el=document.getElementById('layer-list');
  el.innerHTML='';
  defs.forEach(d=>{{
    const on=eyeOn[d.key]??false;
    el.insertAdjacentHTML('beforeend',`
<div class="li${{d.dis?' disabled':''}}">
  <div class="li-row1">
    <button class="eye${{on?' on':''}}" onclick="toggleLayer('${{d.key}}')" id="eye-${{d.key}}">&#128065;</button>
    <span class="li-name">${{d.label}}</span>
  </div>
  <div class="li-meta">${{d.meta}}</div>
  ${{d.key==='vel'?'<div class="vel-load" id="vel-load-badge"></div>':''}}
  ${{!d.dis&&d.cb?`<div class="cb-wrap">
    <div class="cb" style="background:${{d.cb}}"></div>
    <div class="cb-labels">
      <span>${{d.cmin}}</span>
      <span${{d.maxId?` id="${{d.maxId}}"`:''}}>${{d.cmax}}</span>
    </div>
  </div>`:''}}</div>`);
  }});
  updateVelCbLabel();
}}

function toggleLayer(key){{
  if(!LAYERS||!LAYERS[key])return;
  const lyr=LAYERS[key],g=GRIDS[activeGrid];
  if(lyr.on){{lyr.hide();eyeOn[key]=false;}}
  else{{
    if(key==='wl')   lyr.show(map,g.lons,g.lats,g.s1);
    else if(key==='hwav')lyr.show(map,g.lons,g.lats,g.hwav);
    else if(key==='vel') lyr.show(map);
    lyr.update(currentT);eyeOn[key]=true;
  }}
  const btn=document.getElementById('eye-'+key);
  if(btn)btn.classList.toggle('on',eyeOn[key]);
}}

// ── timeline ──────────────────────────────────────────────────────────────────
function seek(val){{
  currentT=+val;
  document.getElementById('tlabel').textContent=TIMES[currentT]||'—';
  if(LAYERS)Object.values(LAYERS).forEach(l=>l.update(currentT));
  if(staBuilt)updateStaCharts(currentT);
}}
function togglePlay(){{
  playing=!playing;
  document.getElementById('play-btn').textContent=playing?'&#9646;&#9646; Pause':'&#9654; Play';
  if(playing){{
    playTimer=setInterval(()=>{{
      currentT=(currentT+1)%TIMES.length;
      document.getElementById('tslider').value=currentT;
      seek(currentT);
    }},300);
  }}else clearInterval(playTimer);
}}

// ── station charts ────────────────────────────────────────────────────────────
function toggleSta(){{
  const sec=document.getElementById('sta-sec');
  const btn=document.querySelector('.sta-toggle');
  const open=sec.style.display==='block';
  sec.style.display=open?'none':'block';
  btn.textContent=(open?'&#9654;':'&#9660;')+' Station time series';
  if(!open&&!staBuilt){{buildStaCards();staBuilt=true;}}
}}
function buildStaCards(){{
  const sec=document.getElementById('sta-sec');sec.innerHTML='';
  Object.keys(STA_INFO).forEach(name=>{{
    sec.insertAdjacentHTML('beforeend',
      `<div class="sc"><h4>${{name}}</h4><div id="sc-${{name}}" style="height:120px"></div></div>`);
    drawStaChart(name,currentT);
  }});
}}
function drawStaChart(name,tIdx){{
  const tStr=TIMES[tIdx]?TIMES[tIdx].split(' ')[0]:'';
  const obs=STA_OBS[name],mod=STA_MODEL[name],traces=[];
  if(obs){{
    const mk=obs.t.map(t=>t.startsWith(tStr));
    traces.push({{x:obs.t.filter((_,i)=>mk[i]),y:obs.wl.filter((_,i)=>mk[i]),
      name:'Obs',type:'scatter',mode:'lines',line:{{color:'#7bb3f0',width:1.5}}}});
  }}
  if(mod){{
    const mk=mod.t.map(t=>t.startsWith(tStr));
    traces.push({{x:mod.t.filter((_,i)=>mk[i]),y:mod.wl.filter((_,i)=>mk[i]),
      name:'Model',type:'scatter',mode:'lines',line:{{color:'#f4a582',width:1.5,dash:'dot'}}}});
  }}
  if(!traces.length)return;
  Plotly.react('sc-'+name,traces,{{
    margin:{{l:30,r:4,t:2,b:26}},paper_bgcolor:'transparent',
    plot_bgcolor:'rgba(8,14,30,.6)',font:{{color:'#aac',size:9}},
    xaxis:{{tickfont:{{size:8}},color:'#aac',gridcolor:'#1a2a45'}},
    yaxis:{{title:'m',titlefont:{{size:8}},tickfont:{{size:8}},color:'#aac',
            gridcolor:'#1a2a45',nticks:3}},
    legend:{{orientation:'h',x:0,y:1.15,font:{{size:8}},bgcolor:'transparent'}},
    height:120,showlegend:true,
  }},{{responsive:true,displayModeBar:false}});
}}
function updateStaCharts(tIdx){{Object.keys(STA_INFO).forEach(n=>drawStaChart(n,tIdx));}}

window.addEventListener('load',loadAll);
</script>
</body>
</html>"""

    HTML.parent.mkdir(parents=True, exist_ok=True)
    HTML.write_text(html, encoding='utf-8')
    print(f'HTML saved: {HTML}  ({HTML.stat().st_size // 1024} kB)')


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    prepare_data()
    build_data_files()
    build_html()
    print('\nDone.')
    print(f'\nRun:  python -m http.server 8080 --directory {OUT_DIR}')
    print('Open: http://localhost:8080')
