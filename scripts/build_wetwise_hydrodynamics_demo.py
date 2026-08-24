"""Build the WetWise Hydrodynamics portal from the regridded caches.

Consumes demo_coarse.nc / demo_fine.nc as written by regrid_wetwise_source.py
(which is the step that talks to the 37 GB of partitioned FM output, and which
normally runs on the compute server).  This script only turns those caches into
the browser payload, so it is cheap to re-run while iterating on the front end.

Payload
    data/meta.json                 times, grids, colour ranges, station series
    data/<grid>_<var>.u16          scalar fields, uint16 + scale/offset
    data/vel/<grid>_d<nn>.i16      velocity by calendar day, int16 mm/s
    data/land.geojson              land boundary, all four lagoon islands
    index.html

Run
    python scripts/build_wetwise_hydrodynamics_demo.py
    python -m http.server 8080 --directory outputs/wetwise_tab/demo_hydrodynamics
"""
from pathlib import Path
import collections
import json

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'outputs' / 'wetwise_tab' / 'demo_hydrodynamics'
DATA_DIR = OUT_DIR / 'data'
VEL_DIR = DATA_DIR / 'vel'
CACHE = {'coarse': OUT_DIR / 'demo_coarse.nc', 'fine': OUT_DIR / 'demo_fine.nc'}
LDB = ROOT / 'data' / 'processed' / 'sicily_v05_manualEdited.ldb'
INSITU = ROOT / 'data' / 'processed' / 'insitu_2025-26'
HTML = OUT_DIR / 'index.html'

SRC_LABEL = 'v04AE_vr_dens'
SRC_DESC = 'waves + variable roughness + mobile bed'

ZOOM_FINE = 12
FRAMES_PER_DAY = 48
U16_NAN = 65535
I16_NAN = -32768

# The fine grid overshoots the lagoon so the detail view has a margin, but that
# margin is open sea west of Isola Grande and it dominates the statistics: over
# the whole fine grid the p95 current is 0.61 m/s, while inside the lagoon it is
# 0.16.  Colour ranges and the particle anchor for the detail view are therefore
# derived over the lagoon proper, not over the whole grid.
LAGOON_STATS_BOX = (12.435, 12.490, 37.832, 37.903)   # lon0, lon1, lat0, lat1

STATIONS = {
    'BocaNord':    {'csv': 'BN_wl_UTC.csv', 'lon': 12.4245, 'lat': 37.9008},
    'BocaSud':     {'csv': 'BS_wl_UTC.csv', 'lon': 12.4356, 'lat': 37.8312},
    'AltaVilaEst': {'csv': 'AE_wl_UTC.csv', 'lon': 12.4782, 'lat': 37.8660},
}

def _cmap_stops(name, k=13):
    """Sample a real matplotlib / cmocean colormap instead of eyeballing hex."""
    import matplotlib
    import matplotlib.colors as mcolors
    import cmocean  # noqa: F401  (registers the cmo.* names)
    cm = matplotlib.colormaps[name]
    return [mcolors.to_hex(cm(x)) for x in np.linspace(0, 1, k)]


def build_cmaps():
    """The palette the front end offers, Copernicus-style names first.

    'wetwise-*' are the ramps validated with the dataviz skill's ordinal
    checker against this dark basemap (monotone lightness, adjacent dL >= 0.06,
    extreme step clearing 2:1 on the surface, single hue per arm).  The
    scientific colormaps below are perceptually uniform by construction.
    """
    return {
        'viridis': _cmap_stops('viridis'),
        'balance': _cmap_stops('cmo.balance'),
        'thermal': _cmap_stops('cmo.thermal'),
        'haline': _cmap_stops('cmo.haline'),
        'amp': _cmap_stops('cmo.amp'),
        'wetwise-div': ['#b8e2f7', '#74c2e8', '#3f9ad1', '#2f6f9e',
                        '#3a3f46',
                        '#a35a34', '#d1803f', '#e8a860', '#f7d3a0'],
        'wetwise-teal': ['#1a6b80', '#2a8ba1', '#45a9bd', '#79cdda', '#c2eef6'],
        'wetwise-amber': ['#8a5410', '#b8720f', '#d9911c',
                          '#e8ae3d', '#f3ca70', '#ffe9a8'],
    }


DEFAULT_CMAP = {'wl': 'viridis', 'hwav': 'balance', 'vel': 'wetwise-amber'}


# -- land boundary ----------------------------------------------------------

def _read_ldb(path):
    polys = collections.OrderedDict()
    cur, skip = None, 0
    for line in path.read_text(errors='ignore').splitlines():
        s = line.split()
        if not s:
            continue
        if s[0][0].isalpha():
            cur = s[0]
            polys[cur] = []
            skip = 1
            continue
        if skip:
            skip = 0
            continue
        try:
            x, y = float(s[0]), float(s[1])
        except ValueError:
            continue
        if cur and np.isfinite(x) and np.isfinite(y):
            polys[cur].append((x, y))
    return polys


def _rdp(pts, tol):
    """Ramer-Douglas-Peucker, iterative so long coastlines can't blow the stack."""
    pts = np.asarray(pts)
    if len(pts) < 3:
        return pts
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        a, b = pts[i0], pts[i1]
        seg = b - a
        L = np.hypot(*seg)
        chunk = pts[i0 + 1:i1]
        if L == 0:
            d = np.hypot(*(chunk - a).T)
        else:
            d = np.abs(np.cross(seg, chunk - a)) / L
        k = int(np.argmax(d))
        if d[k] > tol:
            idx = i0 + 1 + k
            keep[idx] = True
            stack.append((i0, idx))
            stack.append((idx, i1))
    return pts[keep]


def build_land_geojson():
    """GeoJSON of the land boundary.

    Only long coastlines get simplified.  The old build ran a single 0.0003 deg
    tolerance over everything, which is wider than Isola della Scuola is across
    (~83 m), so a blanket tolerance would erase the very island we are trying
    to restore.
    """
    polys = _read_ldb(LDB)
    feats = []
    for name, pts in polys.items():
        if len(pts) < 4:
            continue
        arr = np.asarray(pts)
        arr = _rdp(arr, 0.0003) if len(arr) > 1500 else arr
        if len(arr) < 4:
            continue
        ring = arr.tolist()
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        feats.append({'type': 'Feature',
                      'properties': {'name': name},
                      'geometry': {'type': 'Polygon', 'coordinates': [ring]}})
        print(f'  {name:22s} {len(pts):6d} -> {len(arr):6d} pts')
    return {'type': 'FeatureCollection', 'features': feats}


# -- payload ----------------------------------------------------------------

def write_scalar(ds, var, grid, vmax_hint=None):
    """uint16 with scale/offset; U16_NAN marks dry / outside the mesh."""
    a = ds[var].values.astype(np.float32)
    finite = np.isfinite(a)
    lo = float(np.nanmin(a)) if finite.any() else 0.0
    hi = float(np.nanmax(a)) if finite.any() else 1.0
    if hi <= lo:
        hi = lo + 1e-6
    scale = (hi - lo) / (U16_NAN - 1)
    q = np.full(a.shape, U16_NAN, np.uint16)
    q[finite] = np.round((a[finite] - lo) / scale).astype(np.uint16)

    path = DATA_DIR / f'{grid}_{var}.u16'
    path.write_bytes(q.tobytes())
    print(f'  {path.name:34s} {path.stat().st_size/1e6:7.1f} MB')
    return {'offset': lo, 'scale': scale, 'file': f'data/{path.name}'}


def write_velocity(ds, grid, n_days):
    """int16 mm/s per calendar day, rows already flipped north-first."""
    u = ds['mesh2d_ucx'].values.astype(np.float32)
    v = ds['mesh2d_ucy'].values.astype(np.float32)
    u = u[:, ::-1, :]
    v = v[:, ::-1, :]
    n_t = u.shape[0]
    for d in range(n_days):
        t0, t1 = d * FRAMES_PER_DAY, min((d + 1) * FRAMES_PER_DAY, n_t)
        if t0 >= n_t:
            break
        out = []
        for arr in (u[t0:t1], v[t0:t1]):
            q = np.full(arr.shape, I16_NAN, np.int16)
            ok = np.isfinite(arr)
            q[ok] = np.clip(np.round(arr[ok] * 1000), -32767, 32767).astype(np.int16)
            out.append(q)
        path = VEL_DIR / f'{grid}_d{d:02d}.i16'
        path.write_bytes(np.concatenate(out).tobytes())
    print(f'  vel/{grid}_d*.i16  {n_days} days, '
          f'{sum(p.stat().st_size for p in VEL_DIR.glob(f"{grid}_d*.i16"))/1e6:.1f} MB')


def frame_stats(a, cut):
    """Per-timestep p2 / p98 / mean over the focus area.

    The colour range normally comes from the pooled distribution over ALL
    times, but within any single frame the field occupies only a fraction of
    it -- in a 3 km window of the lagoon the tide moves the whole water body
    almost in phase, so the instantaneous spread is ~12% of the temporal one
    and 88% of the ramp goes unused.  These let the front end rescale to the
    frame, or show the departure from the frame mean.
    """
    sub = cut(a).reshape(a.shape[0], -1) if cut is not None else a.reshape(a.shape[0], -1)
    with np.errstate(all='ignore'):
        lo = np.nanpercentile(sub, 2, axis=1)
        hi = np.nanpercentile(sub, 98, axis=1)
        mn = np.nanmean(sub, axis=1)
    f = lambda v: [None if not np.isfinite(x) else round(float(x), 4) for x in v]
    return {'lo': f(lo), 'hi': f(hi), 'mean': f(mn)}


def load_station_obs():
    T0, T1 = pd.Timestamp('2025-07-01'), pd.Timestamp('2025-07-10')
    out = {}
    for name, info in STATIONS.items():
        fp = INSITU / info['csv']
        if not fp.exists():
            out[name] = None
            continue
        df = (pd.read_csv(fp, parse_dates=['time'], index_col='time')
                .sort_index().loc[T0:T1])
        if df.empty:
            out[name] = None
            continue
        cols = [c for c in df.columns
                if any(k in c.lower() for k in
                       ('wl', 'waterlevel', 'water_level', 'h_m', 'level'))]
        col = cols[0] if cols else df.columns[0]
        s = df[col].resample('30min').mean()
        out[name] = [None if not np.isfinite(x) else round(float(x), 3)
                     for x in s.values]
    return out


def station_model(dsf, dsc):
    """Sample the model at each station, preferring the fine grid."""
    out = {}
    for name, info in STATIONS.items():
        series = None
        for ds in (dsf, dsc):
            lons, lats = ds['lon'].values, ds['lat'].values
            if not (lons[0] <= info['lon'] <= lons[-1] and
                    lats[0] <= info['lat'] <= lats[-1]):
                continue
            i = int(np.abs(lons - info['lon']).argmin())
            j = int(np.abs(lats - info['lat']).argmin())
            col = ds['mesh2d_s1'].values[:, j, i]
            if np.isfinite(col).any():
                series = col
                break
        out[name] = (None if series is None else
                     [None if not np.isfinite(x) else round(float(x), 3)
                      for x in series])
    return out


def build():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VEL_DIR.mkdir(parents=True, exist_ok=True)

    ds = {g: xr.open_dataset(p) for g, p in CACHE.items()}
    times = pd.to_datetime(ds['coarse']['time'].values)
    n_t = len(times)
    n_days = int(np.ceil(n_t / FRAMES_PER_DAY))
    print(f'{n_t} timesteps, {n_days} days, source {SRC_LABEL}')

    meta = {
        'source': SRC_LABEL,
        'source_desc': SRC_DESC,
        'times': [t.strftime('%Y-%m-%d %H:%M') for t in times],
        'n_t': n_t,
        'n_days': n_days,
        'frames_per_day': FRAMES_PER_DAY,
        'u16_nan': U16_NAN,
        'i16_nan': I16_NAN,
        'zoom_fine': ZOOM_FINE,
        'cmaps': build_cmaps(),
        'default_cmap': DEFAULT_CMAP,
        'grids': {},
    }

    for g in ('coarse', 'fine'):
        d = ds[g]
        lons, lats = d['lon'].values, d['lat'].values
        print(f'[{g}] {lons.size}x{lats.size}')

        s1 = d['mesh2d_s1'].values
        hw = d['mesh2d_hwav'].values if 'mesh2d_hwav' in d else None
        spd = np.hypot(d['mesh2d_ucx'].values, d['mesh2d_ucy'].values)

        if g == 'fine':
            b = LAGOON_STATS_BOX
            si = (lons >= b[0]) & (lons <= b[1])
            sj = (lats >= b[2]) & (lats <= b[3])
            cut = lambda a: None if a is None else a[:, sj, :][:, :, si]
            print(f'[{g}] statistics over the lagoon box '
                  f'({int(si.sum())}x{int(sj.sum())} of {lons.size}x{lats.size})')
        else:
            cut = lambda a: a
        s1_s, hw_s, spd_s = cut(s1), cut(hw), cut(spd)

        def pct(a, q):
            a = a[np.isfinite(a)]
            return float(np.percentile(a, q)) if a.size else 1.0

        # Per-view defaults: the lagoon runs an order of magnitude slower than
        # the open sea, so one shared range leaves one of the two views flat.
        meta['grids'][g] = {
            'lon0': float(lons[0]), 'lat0': float(lats[0]),
            'lon1': float(lons[-1]), 'lat1': float(lats[-1]),
            'nx': int(lons.size), 'ny': int(lats.size),
            'dx': float(lons[1] - lons[0]), 'dy': float(lats[1] - lats[0]),
            'wl': write_scalar(d, 'mesh2d_s1', g),
            'hwav': write_scalar(d, 'mesh2d_hwav', g) if hw is not None else None,
            'range': {
                'wl': round(max(pct(np.abs(s1_s), 98), 0.05), 3),
                'hwav': round(max(pct(hw_s, 98), 0.05), 3) if hw is not None else 1.0,
                'vel': round(max(pct(spd_s, 95), 0.02), 3),
            },
            # Representative current for this view.  Particle motion is scaled
            # against this rather than against the p95 ceiling: the lagoon's
            # median is only ~7% of its p95, so anchoring on the ceiling leaves
            # ordinary currents sub-pixel and invisible.
            'vel_typ': round(max(pct(spd_s, 50), 0.005), 4),
            'frames': {
                'wl': frame_stats(s1, cut),
                'hwav': frame_stats(hw, cut) if hw is not None else None,
            },
            # Slider ceiling: the raw maximum is a rare spike, and anchoring
            # the travel to it leaves the useful band squeezed into the first
            # few percent of the slider.  Cap at 4x the default instead.
            'range_max': {
                'wl': round(min(pct(np.abs(s1_s), 100) * 1.05,
                                4 * max(pct(np.abs(s1_s), 98), 0.05)), 3),
                'hwav': round(min(pct(hw_s, 100) * 1.05,
                                  4 * max(pct(hw_s, 98), 0.05)), 3) if hw is not None else 2.0,
                'vel': round(min(pct(spd_s, 100) * 1.05,
                                 4 * max(pct(spd_s, 95), 0.02)), 3),
            },
        }
        write_velocity(d, g, n_days)

    print('Stations ...')
    meta['sta_obs'] = load_station_obs()
    meta['sta_model'] = station_model(ds['fine'], ds['coarse'])
    meta['sta_info'] = {k: {'lon': v['lon'], 'lat': v['lat']}
                        for k, v in STATIONS.items()}

    # Open on a lively instant rather than on t=0, which is the flat initial
    # condition: currents are still zero there and the lagoon is level, so the
    # portal looks broken before you touch the timeline.  Pick the frame with
    # the widest instantaneous water-level spread inside the lagoon, ignoring
    # the first and last quarter of the run.
    fr = meta['grids']['fine']['frames']['wl']
    spread = np.array([np.nan if (lo is None or hi is None) else hi - lo
                       for lo, hi in zip(fr['lo'], fr['hi'])])
    win = spread.copy()
    win[:n_t // 4] = np.nan
    win[3 * n_t // 4:] = np.nan
    meta['start_t'] = int(np.nanargmax(win))
    print(f"start_t = {meta['start_t']} ({meta['times'][meta['start_t']]}), "
          f"lagoon WL spread {spread[meta['start_t']]:.3f} m "
          f"vs {np.nanmedian(win):.3f} m median")

    (DATA_DIR / 'meta.json').write_text(json.dumps(meta), encoding='utf-8')
    print(f"  meta.json  {(DATA_DIR/'meta.json').stat().st_size/1e3:.0f} kB")

    print('Land boundary ...')
    gj = build_land_geojson()
    (DATA_DIR / 'land.geojson').write_text(json.dumps(gj), encoding='utf-8')
    print(f"  land.geojson  {(DATA_DIR/'land.geojson').stat().st_size/1e3:.0f} kB")

    HTML.write_text(PAGE.replace('__ZOOM_FINE__', str(ZOOM_FINE)), encoding='utf-8')
    print(f'  index.html  {HTML.stat().st_size/1e3:.0f} kB')

    for d in ds.values():
        d.close()
    total = sum(p.stat().st_size for p in DATA_DIR.rglob('*')) / 1e6
    print(f'\nPayload {total:.0f} MB -> {OUT_DIR}')


# -- front end --------------------------------------------------------------
# Plain string, substituted with .replace(); no f-string brace doubling.

PAGE = r"""<meta charset="utf-8">
<title>Stagnone Hydrodynamics</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet-velocity@2.1.0/dist/leaflet-velocity.min.css"/>
<script src="https://cdn.jsdelivr.net/npm/leaflet-velocity@2.1.0/dist/leaflet-velocity.min.js"></script>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
:root{
  --bg:#0d1117; --panel:#131a24; --line:#1f2937;
  --ink:#e6edf3; --ink2:#9aa7b4; --ink3:#6b7785; --accent:#58c8d9;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
  font:13px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
#app{display:flex;flex-direction:column;height:100%}
#main{flex:1;display:flex;min-height:0}
#panel{width:288px;flex:none;background:var(--panel);border-right:1px solid var(--line);
  overflow-y:auto;overflow-x:hidden}
#map-wrap{flex:1;position:relative;min-width:0}
#map{position:absolute;inset:0;background:var(--bg)}
.ph{padding:14px 16px 12px;border-bottom:1px solid var(--line)}
.ph h1{margin:0;font-size:15px;font-weight:600;letter-spacing:.2px}
.ph .sub{color:var(--ink2);font-size:11.5px;margin-top:3px}
.ph .src{color:var(--accent);font-size:11px;margin-top:6px;font-weight:500}
.ph-res{color:var(--ink3);font-size:11px;margin-top:8px}
#base-btn{margin-top:9px;border:1px solid var(--line);background:#0f1620;
  color:var(--ink2);border-radius:6px;font-size:10.5px;padding:4px 10px;
  cursor:pointer;font-family:inherit}
#base-btn:hover{color:var(--accent);border-color:var(--accent)}

/* Light theme: only the tokens change, so every rule above follows. */
body.light{
  --bg:#eef1f5; --panel:#ffffff; --line:#d8dde5;
  --ink:#16202c; --ink2:#4c5966; --ink3:#78848f; --accent:#0b7c8c;
}
body.light .eye,body.light #base-btn,body.light .expand,
body.light .rst,body.light .opts select,body.light #play-btn,
body.light #modal-x{background:#f3f5f8}
body.light .eye.on{background:#dff1f4}
body.light #modal{background:rgba(230,234,240,.86)}
.li{padding:12px 16px;border-bottom:1px solid var(--line)}
.li.disabled{opacity:.38}
.li-row1{display:flex;align-items:center;gap:9px}
.eye{width:24px;height:24px;flex:none;border:1px solid var(--line);border-radius:6px;
  background:#0f1620;color:var(--ink3);cursor:pointer;font-size:11px;line-height:1;padding:0}
.eye.on{background:#0e2b33;border-color:var(--accent);color:var(--accent)}
.li-name{font-weight:600;font-size:12.5px}
.li-meta{color:var(--ink3);font-size:10.5px;margin:5px 0 0 33px}
.cb-wrap{margin:9px 0 0 33px}
.cb{height:9px;border-radius:5px;border:1px solid var(--line)}
.cb-labels{display:flex;justify-content:space-between;color:var(--ink2);
  font-size:10px;margin-top:3px;font-variant-numeric:tabular-nums}
.scale{margin:9px 0 0 33px;display:flex;align-items:center;gap:8px}
.scale input{flex:1;min-width:0;accent-color:var(--accent);height:15px}
.scale .val{color:var(--ink2);font-size:10px;width:56px;text-align:right;
  font-variant-numeric:tabular-nums}
.scale .rst{border:1px solid var(--line);background:#0f1620;color:var(--ink3);
  border-radius:5px;font-size:9.5px;padding:2px 5px;cursor:pointer}
.scale .rst.dirty{color:var(--accent);border-color:var(--accent)}
.scale input:disabled{opacity:.35}
.opts{margin:8px 0 0 33px;display:flex;gap:6px}
.opts select{flex:1;min-width:0;background:#0f1620;color:var(--ink2);
  border:1px solid var(--line);border-radius:5px;font-size:10px;padding:3px 4px;
  font-family:inherit;cursor:pointer}
.vel-load{margin:6px 0 0 33px;color:var(--accent);font-size:10px}
.sta-toggle{width:100%;text-align:left;padding:11px 16px;background:none;border:0;
  border-bottom:1px solid var(--line);color:var(--ink);font-size:12px;cursor:pointer;
  font-weight:600;font-family:inherit}
.sc{padding:10px 12px;border-bottom:1px solid var(--line)}
.sc h4{margin:0 0 5px;font-size:11.5px;color:var(--ink2);font-weight:600;
  display:flex;align-items:center;justify-content:space-between}
.expand{border:1px solid var(--line);background:#0f1620;color:var(--ink3);
  border-radius:5px;font-size:11px;padding:1px 7px;cursor:pointer;line-height:1.4}
.expand:hover{color:var(--accent);border-color:var(--accent)}
#modal{display:none;position:fixed;inset:0;z-index:10000;
  background:rgba(4,7,12,.82);align-items:center;justify-content:center;padding:32px}
#modal-box{width:min(1000px,94vw);height:min(620px,84vh);background:var(--panel);
  border:1px solid var(--line);border-radius:11px;display:flex;flex-direction:column;
  overflow:hidden}
#modal-head{display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px;border-bottom:1px solid var(--line);font-weight:600;font-size:13px}
#modal-x{border:1px solid var(--line);background:#0f1620;color:var(--ink2);
  border-radius:6px;padding:4px 12px;cursor:pointer;font-size:12px;font-family:inherit}
#modal-plot{flex:1;min-height:0;padding:6px 10px 10px}
#tbar{flex:none;display:flex;align-items:center;gap:14px;padding:9px 16px;
  background:var(--panel);border-top:1px solid var(--line)}
#play-btn{border:1px solid var(--line);background:#0f1620;color:var(--ink);
  border-radius:7px;padding:6px 14px;cursor:pointer;font-size:12px;font-family:inherit}
#tlabel{font-variant-numeric:tabular-nums;color:var(--ink2);min-width:132px;font-size:12px}
#tslider{flex:1;accent-color:var(--accent)}
#loader{position:fixed;inset:0;background:var(--bg);z-index:9999;display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:11px}
.ld-sub{color:var(--ink2);font-size:12px}
.ld-bar-wrap{width:260px;height:3px;background:var(--line);border-radius:2px;overflow:hidden}
.ld-bar{height:100%;background:var(--accent);transition:width .25s}
.note{padding:11px 16px;color:var(--ink3);font-size:10px;line-height:1.5}
.leaflet-container{background:var(--bg)}
#vel-readout{position:absolute;left:10px;bottom:10px;z-index:1000;
  background:var(--panel);border:1px solid var(--line);border-radius:7px;
  padding:5px 11px;font-size:11.5px;color:var(--ink);pointer-events:none;
  font-variant-numeric:tabular-nums;box-shadow:0 2px 10px rgba(0,0,0,.28)}
#vel-readout .ro-g{color:var(--ink3);font-size:10px;margin-left:5px}
</style>

<div id="loader">
  <div style="font-size:15px;font-weight:600">Stagnone Hydrodynamics</div>
  <div id="ld-status" class="ld-sub">Initialising...</div>
  <div class="ld-bar-wrap"><div class="ld-bar" id="ld-bar" style="width:2%"></div></div>
</div>

<div id="app">
  <div id="main">
    <div id="panel">
      <div class="ph">
        <h1>WetWise Hydrodynamics</h1>
        <div class="sub">Stagnone di Marsala Digital Twin</div>
        <div class="src" id="src-badge">-</div>
        <div class="ph-res" id="res-badge">Coarse view</div>
        <button id="base-btn" onclick="toggleBasemap()">light basemap</button>
      </div>
      <div id="layer-list"></div>
      <button class="sta-toggle" onclick="toggleSta()">Station time series</button>
      <div id="sta-sec"></div>
      <div id="modal" onclick="closeSta(event)">
        <div id="modal-box">
          <div id="modal-head"><span id="modal-title"></span>
            <button id="modal-x" onclick="closeSta()">close</button></div>
          <div id="modal-plot"></div>
        </div>
      </div>
      <div class="note" id="foot-note"></div>
    </div>
    <div id="map-wrap"><div id="map"></div>
      <div id="vel-readout" style="display:none"></div>
    </div>
  </div>
  <div id="tbar">
    <button id="play-btn" onclick="togglePlay()">Play</button>
    <span id="tlabel">-</span>
    <input type="range" id="tslider" min="0" max="0" value="0" oninput="seek(+this.value)">
  </div>
</div>

<script>
const ZOOM_FINE = __ZOOM_FINE__;
let META=null, TIMES=[], N_DAYS=0, U16_NAN=65535, I16_NAN=-32768;
let map=null, LAYERS=null, currentT=0, activeGrid='coarse';
let playing=false, playTimer=null, staBuilt=false;
const G={};                     // grid -> {meta, wl:{raw,..}, hwav:{...}}
const velCache={coarse:{}, fine:{}};
let velLoaded=0;

const setLoad=(p,t)=>{document.getElementById('ld-bar').style.width=p+'%';
  if(t)document.getElementById('ld-status').textContent=t;};

async function fetchJSON(u){const r=await fetch(u);if(!r.ok)throw new Error(u+' '+r.status);return r.json();}
async function fetchBuf(u){const r=await fetch(u);if(!r.ok)throw new Error(u+' '+r.status);return r.arrayBuffer();}

/* ---- colour ------------------------------------------------------------ */
const hexRgb=h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];

function ramp(stops,vmin,vmax,fadeLow){
  const cs=stops.map(hexRgb), n=cs.length;
  return v=>{
    let t=(v-vmin)/(vmax-vmin);
    t=t<0?0:t>1?1:t;
    const x=t*(n-1), k=Math.min(Math.floor(x),n-2), f=x-k;
    const a=cs[k], b=cs[k+1];
    // Fade the bottom of a sequential ramp so a near-zero field reads as the
    // basemap rather than as a flat wash of the ramp's darkest step.
    let al=210;
    if(fadeLow) al=Math.round(30+180*Math.min(t*3.2,1));
    return [Math.round(a[0]+f*(b[0]-a[0])),
            Math.round(a[1]+f*(b[1]-a[1])),
            Math.round(a[2]+f*(b[2]-a[2])), al];
  };
}
const cssRamp=stops=>'linear-gradient(to right,'+stops.join(',')+')';

/* ---- scalar field layer ------------------------------------------------
   One overlay per grid, both alive at once.  The coarse overlay is the base
   and never leaves the map, so zooming into the lagoon no longer blanks the
   offshore; the fine overlay just paints on top of it.                     */
class FieldLayer{
  constructor(key,cmap,fadeLow){
    this.key=key; this.cmap=cmap; this.fadeLow=fadeLow;
    this.on=false; this.ov={}; this.vmax=1; this.vmin=0; this.auto=true;
    /* Range mode. 'view' holds one range across the whole run, so colours are
       comparable between frames.  But the tide lifts the lagoon almost in
       phase: inside a 3 km window the instantaneous spread is only ~12% of the
       range pooled over time, so 88% of the ramp goes unused and every frame
       looks flat.  'frame' rescales to each instant, 'anom' shows the
       departure from that instant's spatial mean -- both trade cross-time
       comparability for actually seeing the gradient.  'frame' is the default
       precisely because the pooled range leaves 12-19% of the ramp in use. */
    this.mode='frame';
  }
  stops(){return META.cmaps[this.cmap]||META.cmaps.viridis;}
  setCmap(name){this.cmap=name;this.render(currentT);}
  setMode(m){this.mode=m;if(m==='anom')this.applyAnomDefault();this.render(currentT);}
  frames(){const f=G[activeGrid].meta.frames;return f?f[this.key]:null;}
  applyAnomDefault(){
    // Half the median instantaneous spread is a sane starting amplitude.
    const fr=this.frames();
    if(!fr)return;
    const sp=[];
    for(let i=0;i<fr.lo.length;i+=7)
      if(fr.lo[i]!==null&&fr.hi[i]!==null)sp.push(fr.hi[i]-fr.lo[i]);
    if(!sp.length)return;
    sp.sort((a,b)=>a-b);
    this.vmax=Math.max(sp[Math.floor(sp.length/2)]/2,1e-4);
    this.vmin=-this.vmax;
  }
  effRange(t){
    if(this.mode==='frame'){
      const fr=this.frames();
      if(fr&&fr.lo[t]!==null&&fr.hi[t]!==null&&fr.hi[t]>fr.lo[t])
        return [fr.lo[t],fr.hi[t],0];
    }
    if(this.mode==='anom'){
      const fr=this.frames();
      const m=(fr&&fr.mean[t]!==null)?fr.mean[t]:0;
      return [-this.vmax,this.vmax,m];
    }
    return [this.vmin,this.vmax,0];
  }
  _bounds(g){return [[g.lat0,g.lon0],[g.lat1,g.lon1]];}
  _mk(grid){
    const g=G[grid].meta;
    const ov=L.imageOverlay('',this._bounds(g),
      {opacity:1,interactive:false,className:'fld',
       zIndex: grid==='coarse'?200:210});
    return ov;
  }
  show(){
    if(this.on)return;
    this.on=true; this._ensure(); this._sync(); this.render(currentT);
  }
  _ensure(){   // fine data arrives after the map is live, so attach on demand
    if(!this.on)return;
    for(const grid of ['coarse','fine']){
      if(!G[grid]||!G[grid][this.key])continue;
      if(!this.ov[grid]){this.ov[grid]=this._mk(grid);this.ov[grid].addTo(map);}
    }
  }
  hide(){
    // Drop the references too, not just the map membership: _ensure() only
    // builds an overlay when the slot is empty, so keeping a detached object
    // here meant a hidden layer could never be shown again.
    for(const k in this.ov)if(this.ov[k])this.ov[k].remove();
    this.ov={};
    this.on=false;
  }
  _sync(){    // fine overlay only carries pixels while it is the active view
    if(!this.ov.fine)return;
    this.ov.fine.setOpacity(activeGrid==='fine'?1:0);
  }
  setRange(vmax){
    this.vmax=vmax;
    this.vmin=(this.key==='wl')?-vmax:0;
    this.render(currentT);
  }
  applyAuto(){
    if(this.mode==='anom'){this.applyAnomDefault();return;}
    if(this.mode==='frame')return;      // range comes from the frame itself
    if(!this.auto)return;
    const r=G[activeGrid].meta.range[this.key];
    this.setRange(r);
    return r;
  }
  render(t){
    if(!this.on)return;
    this._ensure(); this._sync();
    const [vmin,vmax,off]=this.effRange(t);
    const cf=ramp(this.stops(),vmin,vmax,this.fadeLow&&this.mode==='view');
    for(const grid of ['coarse','fine']){
      const gd=G[grid]&&G[grid][this.key];
      if(!gd||!this.ov[grid])continue;
      if(grid==='fine'&&activeGrid!=='fine')continue;
      const g=G[grid].meta, nx=g.nx, ny=g.ny, base=t*nx*ny;
      const cv=document.createElement('canvas');
      cv.width=nx; cv.height=ny;
      const ctx=cv.getContext('2d'), img=ctx.createImageData(nx,ny);
      for(let j=0;j<ny;j++){
        const r=ny-1-j, ro=base+r*nx, jo=j*nx;
        for(let i=0;i<nx;i++){
          const q=gd.raw[ro+i], idx=(jo+i)*4;
          if(q===U16_NAN){img.data[idx+3]=0;continue;}
          const c=cf(gd.offset+q*gd.scale-off);
          img.data[idx]=c[0];img.data[idx+1]=c[1];img.data[idx+2]=c[2];img.data[idx+3]=c[3];
        }
      }
      ctx.putImageData(img,0,0);
      this.ov[grid].setUrl(cv.toDataURL('image/png'));
    }
    syncScaleUI();
  }
}

/* ---- velocity ----------------------------------------------------------
   The layer is built once and kept.  Frames go in through the windy object
   followed by _startWindy(), which rebuilds the field but does NOT clear the
   canvas -- so the particle trails survive and the layer keeps animating
   while the timeline plays, instead of blinking out on every step.        */
// Px a REPRESENTATIVE current advances per frame (see vel_typ in meta).
// Single knob: raise for longer, faster streaks; lower for shorter ones.
const TARGET_PX = 3.4;

class VelLayer{
  /* Two leaflet-velocity layers, mirroring the two field overlays.  The coarse
     one is always on so the offshore keeps its currents at lagoon zoom; the
     fine one adds lagoon detail on top.  A leaflet-velocity layer carries one
     regular grid, so they cannot be merged -- instead the coarse frame is
     punched out over the fine grid's footprint, otherwise both would draw
     particles there and the lagoon would animate at double density. */
  constructor(){this.lyrs={};this.on=false;this.vmax=1;this.auto=true;}
  /* leaflet-velocity turns our velocityScale into screen motion as
        px_per_frame = v * VELOCITY_SCALE * mapArea^0.4 * px_per_degree
     (lv 2.1.0 lines 809/826).  mapArea is the visible extent in DEGREES
     squared, so it collapses as you zoom in: in the lagoon it drops to
     ~0.005 deg^2, and a real 0.04 m/s current ends up moving a particle
     0.7 px per frame -- a dot that never draws a trail.  maxVelocity cannot
     rescue it, because that option only feeds the colour scale (line 866).
     So solve the relation for velocityScale and re-apply it whenever the
     range or the view changes. */
  _velScale(){
    if(!map)return 0.012;
    const b=map.getBounds();
    const area=Math.abs((b.getSouth()-b.getNorth())*(b.getWest()-b.getEast()));
    const c=map.getCenter();
    const p0=map.latLngToContainerPoint([c.lat,c.lng]);
    const p1=map.latLngToContainerPoint([c.lat,c.lng+0.01]);
    const pxDeg=Math.abs(p1.x-p0.x)/0.01;
    const dpr=Math.pow(window.devicePixelRatio||1,1/3)||1;
    const gm=G[activeGrid].meta;
    // Anchor on the view's representative current, shifted by how far the user
    // has pulled the range below its default -- so narrowing the range really
    // does amplify the motion instead of only recolouring it.
    const ref=Math.max(gm.vel_typ*(this.vmax/gm.range.vel),1e-4);
    const denom=ref*pxDeg*Math.pow(Math.max(area,1e-9),0.4)*dpr;
    return Math.min(Math.max(TARGET_PX/denom,1e-5),4);
  }
  refreshScale(){
    const o={velocityScale:this._velScale()};
    for(const k in this.lyrs)this.lyrs[k].setOptions(o);
  }
  _frame(grid,t,hole){
    const g=G[grid].meta;
    const day=Math.floor(t/META.frames_per_day), ft=t%META.frames_per_day;
    const raw=velCache[grid][day];
    if(!raw)return null;
    const n=g.nx*g.ny, nf=raw.length/(2*n);
    if(ft>=nf)return null;
    const uo=ft*n, vo=nf*n+ft*n;
    const u=new Array(n), v=new Array(n);
    for(let k=0;k<n;k++){
      const a=raw[uo+k], b=raw[vo+k];
      u[k]=a===I16_NAN?null:a/1000;
      v[k]=b===I16_NAN?null:b/1000;
    }
    if(hole){   // rows run north-first, matching how the payload was written
      for(let j=0;j<g.ny;j++){
        const lat=g.lat1-j*g.dy;
        if(lat<hole.lat0||lat>hole.lat1)continue;
        for(let i=0;i<g.nx;i++){
          const lon=g.lon0+i*g.dx;
          if(lon<hole.lon0||lon>hole.lon1)continue;
          const k=j*g.nx+i;
          u[k]=null; v[k]=null;
        }
      }
    }
    const hdr={la1:g.lat1,lo1:g.lon0,la2:g.lat0,lo2:g.lon1,
               dx:g.dx,dy:g.dy,nx:g.nx,ny:g.ny,parameterUnit:'m.s-1'};
    return [{header:{...hdr,parameterCategory:2,parameterNumber:2},data:u},
            {header:{...hdr,parameterCategory:2,parameterNumber:3},data:v}];
  }
  show(){
    if(this.on)return;
    this.on=true;
    this.render(currentT);   // layers are built by the first frame that exists
  }
  _build(grid,f){
    this.lyrs[grid]=L.velocityLayer({
      // The built-in readout is off on both layers: it reads the layer's own
      // grid, and the coarse grid is punched out over the lagoon, so it
      // reported "No data" exactly where the fine layer was drawing.  The
      // readout below samples whichever grid is authoritative under the cursor.
      displayValues:false,
      data:f,maxVelocity:this.vmax,velocityScale:this._velScale(),
      colorScale:META.cmaps[META.default_cmap.vel],
      lineWidth:2.4,particleAge:90,frameRate:22,
      particleMultiplier:1/220,
      paneName:'velPane',   // above the painted fields, below the coastline
    }).addTo(map);
  }
  _drop(grid){
    if(this.lyrs[grid]){map.removeLayer(this.lyrs[grid]);delete this.lyrs[grid];}
  }
  hide(){for(const k in this.lyrs)this._drop(k);this.on=false;}
  setRange(vmax){
    this.vmax=vmax;
    // Range drives colour AND particle motion, so lowering it to read the
    // lagoon actually makes the currents legible instead of only recolouring.
    const o={maxVelocity:vmax,velocityScale:this._velScale()};
    for(const k in this.lyrs)this.lyrs[k].setOptions(o);
  }
  applyAuto(){
    if(!this.auto)return;
    const r=G[activeGrid].meta.range.vel;
    this.setRange(r);
    return r;
  }
  render(t){
    if(!this.on)return;
    const fg=G.fine&&G.fine.meta;
    const useFine=(activeGrid==='fine')&&fg&&velCache.fine[Math.floor(t/META.frames_per_day)];
    // Punch the fine footprint out of the coarse frame only while the fine
    // layer is actually drawing there.
    const hole=useFine?{lon0:fg.lon0,lon1:fg.lon1,lat0:fg.lat0,lat1:fg.lat1}:null;

    for(const grid of ['coarse','fine']){
      if(grid==='fine'&&!useFine){this._drop('fine');continue;}
      const f=this._frame(grid,t,grid==='coarse'?hole:null);
      if(!f){this._drop(grid);continue;}
      const lyr=this.lyrs[grid];
      if(!lyr){this._build(grid,f);continue;}
      const w=lyr._windy;
      if(w&&lyr._startWindy){
        lyr.options.data=f;
        w.setData(f);
        lyr._startWindy();         // keeps trails; setData() would wipe them
      }else{
        lyr.setData(f);
      }
    }
  }
}

/* ---- current readout ---------------------------------------------------
   Samples the finest grid that actually covers the cursor, so the lagoon
   reports its own 45 m value rather than the 270 m one -- and reports at all,
   which the layer-bound readout could not once the coarse frame was punched
   out beneath the fine layer.                                              */
function sampleVel(lon,lat,t){
  const day=Math.floor(t/META.frames_per_day), ft=t%META.frames_per_day;
  for(const grid of ['fine','coarse']){
    const gm=G[grid]&&G[grid].meta;
    if(!gm)continue;
    if(lon<gm.lon0||lon>gm.lon1||lat<gm.lat0||lat>gm.lat1)continue;
    const raw=velCache[grid][day];
    if(!raw)continue;
    const n=gm.nx*gm.ny, nf=raw.length/(2*n);
    if(ft>=nf)continue;
    const i=Math.round((lon-gm.lon0)/gm.dx);
    const j=Math.round((gm.lat1-lat)/gm.dy);          // rows are north-first
    if(i<0||i>=gm.nx||j<0||j>=gm.ny)continue;
    const k=j*gm.nx+i;
    const a=raw[ft*n+k], b=raw[nf*n+ft*n+k];
    if(a===I16_NAN||b===I16_NAN)continue;
    return {u:a/1000, v:b/1000, grid};
  }
  return null;
}

// Same maths as leaflet-velocity's bearingCCW, so the numbers stay comparable
// with what the built-in control used to print.
function bearingCCW(u,v){
  const vv=v>0?-v:Math.abs(v);
  const abs=Math.hypot(u,vv);
  if(!abs)return 0;
  return Math.atan2(u/abs,vv/abs)*180/Math.PI+180;
}

function updateReadout(e){
  const el=document.getElementById('vel-readout');
  if(!el)return;
  if(!e){el.style.display='none';return;}
  const s=sampleVel(e.latlng.lng,e.latlng.lat,currentT);
  if(!s){el.style.display='none';return;}
  el.style.display='';
  el.innerHTML='<b>Current</b> '+bearingCCW(s.u,s.v).toFixed(1)+'&deg;'
    +' &middot; '+Math.hypot(s.u,s.v).toFixed(3)+' m/s'
    +' <span class="ro-g">'+(s.grid==='fine'?'45 m':'270 m')+'</span>';
}

/* ---- load -------------------------------------------------------------- */
async function loadScalar(grid,key){
  const info=META.grids[grid][key];
  if(!info)return null;
  const buf=await fetchBuf(info.file);
  return {raw:new Uint16Array(buf),offset:info.offset,scale:info.scale};
}

async function loadAll(){
  setLoad(4,'Metadata...');
  META=await fetchJSON('data/meta.json');
  TIMES=META.times; N_DAYS=META.n_days;
  U16_NAN=META.u16_nan; I16_NAN=META.i16_nan;
  // t=0 is the flat initial condition -- no currents, level lagoon.  Open on
  // the liveliest instant instead (picked at build time).
  currentT=Math.min(META.start_t||0,TIMES.length-1);

  G.coarse={meta:META.grids.coarse};
  G.fine={meta:META.grids.fine};

  setLoad(14,'Water level...');
  G.coarse.wl=await loadScalar('coarse','wl');
  setLoad(34,'Wave height...');
  G.coarse.hwav=await loadScalar('coarse','hwav');

  setLoad(58,'Land boundary...');
  let land=null;
  try{land=await fetchJSON('data/land.geojson');}catch(e){console.warn('no land.geojson');}

  setLoad(74,'Map...');
  initMap(land);
  setLoad(100,'Ready');
  setTimeout(()=>document.getElementById('loader').style.display='none',180);

  // Lagoon detail and the velocity days stream in behind the live map.
  loadFine();
  loadVel();
}

async function loadFine(){
  try{
    G.fine.wl=await loadScalar('fine','wl');
    G.fine.hwav=await loadScalar('fine','hwav');
    if(activeGrid==='fine'&&LAYERS)
      Object.values(LAYERS).forEach(l=>l.render&&l.render(currentT));
  }catch(e){console.warn('fine',e);}
}

async function loadVel(){
  // Fetch the opening day first, otherwise the map sits there currentless
  // until the sequential load happens to reach it.
  const first=Math.floor(currentT/META.frames_per_day);
  const order=[first];
  for(let d=0;d<N_DAYS;d++)if(d!==first)order.push(d);
  for(const d of order){
    for(const grid of ['coarse','fine']){
      try{
        const b=await fetchBuf('data/vel/'+grid+'_d'+String(d).padStart(2,'0')+'.i16');
        velCache[grid][d]=new Int16Array(b);
      }catch(e){}
    }
    velLoaded++;
    badgeVel();
    if(LAYERS&&LAYERS.vel.on&&Math.floor(currentT/META.frames_per_day)===d)
      LAYERS.vel.render(currentT);
  }
}
function badgeVel(){
  const el=document.getElementById('vel-load-badge');
  if(!el)return;
  if(velLoaded>=N_DAYS){el.style.display='none';}
  else el.textContent='loading currents '+velLoaded+'/'+N_DAYS+' days';
}

/* ---- map --------------------------------------------------------------- */
const BASEMAPS={
  dark:{tiles:'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        land:{fillColor:'#0a0f18',fillOpacity:.95,color:'#28323f',weight:.6}},
  light:{tiles:'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
         land:{fillColor:'#e6e2da',fillOpacity:.95,color:'#a8a49b',weight:.6}},
};
let baseTheme='dark', tileLyr=null, landLyr=null, landGJ=null;

function applyBasemap(name){
  baseTheme=name;
  const b=BASEMAPS[name];
  if(tileLyr)map.removeLayer(tileLyr);
  tileLyr=L.tileLayer(b.tiles,{attribution:'&copy; OSM &copy; CARTO',
    subdomains:'abcd',maxZoom:19}).addTo(map);
  if(landLyr)map.removeLayer(landLyr);
  if(landGJ)landLyr=L.geoJSON(landGJ,{pane:'landPane',style:b.land}).addTo(map);
  document.body.className=(name==='light')?'light':'';
  const btn=document.getElementById('base-btn');
  if(btn)btn.textContent=(name==='dark')?'light basemap':'dark basemap';
}
function toggleBasemap(){
  applyBasemap(baseTheme==='dark'?'light':'dark');
  if(staBuilt)Object.keys(META.sta_info).forEach(n=>drawSta(n,currentT));
  if(modalSta)drawStaBig(modalSta,currentT);
}

function initMap(land){
  landGJ=land;
  // Quarter-level zoom so there are usable steps between the far-out views,
  // instead of one integer jump from the whole domain to half of it.
  map=L.map('map',{zoomControl:true,preferCanvas:true,
                   zoomSnap:0.25,zoomDelta:0.5});

  // Open framed on the model domain, and never let the view leave it: outside
  // the domain there is no data at all, only black.  getBoundsZoom(b,true)
  // returns the zoom at which the bounds COVER the viewport rather than fit
  // inside it, so no empty margin is visible at the opening view.
  const g=META.grids.coarse;
  const dom=L.latLngBounds([[g.lat0,g.lon0],[g.lat1,g.lon1]]);
  map.setView(dom.getCenter(),map.getBoundsZoom(dom,true));
  map.setMinZoom(map.getBoundsZoom(dom,true));
  map.setMaxBounds(dom.pad(0.02));

  // Panes first: applyBasemap draws the coastline into landPane.  Field
  // overlays stay in overlayPane (400); particles get their own pane above
  // them so the painted water level cannot wash them out, and the coastline
  // sits on top of both.
  map.createPane('velPane');
  map.getPane('velPane').style.zIndex=430;
  map.getPane('velPane').style.pointerEvents='none';
  map.createPane('landPane');
  map.getPane('landPane').style.zIndex=450;
  map.getPane('landPane').style.pointerEvents='none';

  applyBasemap(baseTheme);

  LAYERS={
    wl:  new FieldLayer('wl',  META.default_cmap.wl,  false),
    hwav:new FieldLayer('hwav',META.default_cmap.hwav,true),
    vel: new VelLayer(),
  };
  LAYERS.wl.vmax=META.grids.coarse.range.wl;
  LAYERS.wl.vmin=-LAYERS.wl.vmax;
  LAYERS.hwav.vmax=META.grids.coarse.range.hwav;
  LAYERS.vel.vmax=META.grids.coarse.range.vel;

  LAYERS.wl.show();
  LAYERS.vel.show();

  map.on('zoomend',()=>{
    const need=map.getZoom()>=ZOOM_FINE?'fine':'coarse';
    if(need===activeGrid)return;
    activeGrid=need;
    document.getElementById('res-badge').textContent=
      need==='fine'?'Lagoon detail - '+META.grids.fine.nx+'x'+META.grids.fine.ny+' cells'
                   :'Coarse view - zoom in for lagoon detail';
    for(const k in LAYERS){
      const l=LAYERS[k];
      if(l._sync)l._sync();
      l.applyAuto();
      if(l.render)l.render(currentT);
    }
    syncScaleUI();
  });
  // mapArea feeds the particle scaling, so it has to be re-derived after any
  // pan or zoom, not only when the coarse/fine grid flips.
  map.on('moveend',()=>{if(LAYERS&&LAYERS.vel)LAYERS.vel.refreshScale();});
  map.on('mousemove',updateReadout);
  map.on('mouseout',()=>updateReadout(null));

  buildPanel();
  toggleSta();          // stations visible from the start, as in the old build
  const sl=document.getElementById('tslider');
  sl.max=TIMES.length-1;
  sl.value=currentT;
  document.getElementById('tlabel').textContent=TIMES[currentT];
  document.getElementById('src-badge').textContent=META.source+' - '+META.source_desc;
  document.getElementById('res-badge').textContent='Coarse view - zoom in for lagoon detail';
  document.getElementById('foot-note').textContent=
    'Fields regridded from the FM mesh with an exact point-in-face mask, so the '
    +'island holes (including Isola della Scuola) and the offshore coverage are '
    +'the mesh’s own. Colour ranges follow the view and can be overridden below each layer.';
}

/* ---- panel ------------------------------------------------------------- */
const eyeOn={wl:true,vel:true,hwav:false};
const DEFS=[
  {key:'wl',  label:'Water Level',      unit:'m',   sym:true},
  {key:'vel', label:'Surface Velocity', unit:'m/s', sym:false},
  {key:'hwav',label:'Wave Height',      unit:'m',   sym:false},
];

function buildPanel(){
  const el=document.getElementById('layer-list');
  el.innerHTML='';
  DEFS.forEach(d=>{
    const on=eyeOn[d.key];
    const l=LAYERS[d.key];
    const stops=l.stops?l.stops():META.cmaps[META.default_cmap[d.key]];
    el.insertAdjacentHTML('beforeend',
      '<div class="li">'
      +'<div class="li-row1">'
      +'<button class="eye'+(on?' on':'')+'" id="eye-'+d.key+'" onclick="toggleLayer(\''+d.key+'\')">&#9679;</button>'
      +'<span class="li-name">'+d.label+'</span></div>'
      +'<div class="li-meta">'+META.source+' &middot; surface &middot; 30 min</div>'
      +(d.key==='vel'?'<div class="vel-load" id="vel-load-badge"></div>':'')
      +'<div class="cb-wrap"><div class="cb" id="cb-'+d.key+'" style="background:'+cssRamp(stops)+'"></div>'
      +'<div class="cb-labels"><span id="cb-min-'+d.key+'"></span>'
      +'<span id="cb-max-'+d.key+'"></span></div></div>'
      +'<div class="scale">'
      +'<input type="range" id="sc-'+d.key+'" min="1" max="1000" value="500" '
      +'oninput="onScale(\''+d.key+'\',+this.value)">'
      +'<span class="val" id="scv-'+d.key+'"></span>'
      +'<button class="rst" id="rst-'+d.key+'" onclick="resetScale(\''+d.key+'\')">auto</button>'
      +'</div>'
      +(d.key==='vel'?'':
        '<div class="opts">'
        +'<select id="cm-'+d.key+'" onchange="onCmap(\''+d.key+'\',this.value)">'
        +Object.keys(META.cmaps).map(n=>'<option value="'+n+'">'+n+'</option>').join('')
        +'</select>'
        +'<select id="md-'+d.key+'" onchange="onMode(\''+d.key+'\',this.value)" '
        +'title="view: one range for the whole run. frame: rescale to each instant. anom: departure from the frame mean.">'
        +'<option value="frame">range: per frame</option>'
        +'<option value="view">range: whole run</option>'
        +'<option value="anom">range: anomaly</option>'
        +'</select></div>')
      +'</div>');
  });
  DEFS.forEach(d=>{
    if(d.key==='vel')return;
    const cs=document.getElementById('cm-'+d.key);
    if(cs)cs.value=LAYERS[d.key].cmap;
    const ms=document.getElementById('md-'+d.key);
    if(ms)ms.value=LAYERS[d.key].mode;
  });
  el.insertAdjacentHTML('beforeend',
    '<div class="li disabled"><div class="li-row1">'
    +'<button class="eye">&#9679;</button><span class="li-name">Turbidity</span></div>'
    +'<div class="li-meta">not available in this run</div></div>');
  syncScaleUI();
}

// Slider position <-> value, quadratic so the low end (where the lagoon lives)
// gets most of the travel.
const scMax=k=>G[activeGrid].meta.range_max[k];
// Floor at 1.5% of the ceiling: below that the range stops meaning anything
// (the old floor bottomed out at 0.001 m/s, which just saturated the ramp).
function posToVal(k,p){const m=scMax(k),f=p/1000;return Math.max(m*f*f,m*0.015);}
function valToPos(k,v){return Math.round(1000*Math.sqrt(Math.min(v/scMax(k),1)));}

function onScale(key,pos){
  const l=LAYERS[key];
  l.auto=false;
  l.setRange(posToVal(key,pos));
  syncScaleUI();
}
function resetScale(key){
  const l=LAYERS[key];
  l.auto=true;
  l.applyAuto();
  syncScaleUI();
}
function onCmap(key,name){
  const l=LAYERS[key];
  l.setCmap(name);
  const cb=document.getElementById('cb-'+key);
  if(cb)cb.style.background=cssRamp(l.stops());
}
function onMode(key,m){
  LAYERS[key].setMode(m);
  syncScaleUI();
}
function fmt(v,u){return (Math.abs(v)<1?v.toFixed(3):v.toFixed(2))+' '+u;}

function syncScaleUI(){
  DEFS.forEach(d=>{
    const l=LAYERS[d.key];
    const [vmin,vmax]=l.effRange?l.effRange(currentT):[0,l.vmax];
    const sl=document.getElementById('sc-'+d.key);
    // Leave the slider alone while it has focus, or dragging fights the redraw.
    if(sl&&document.activeElement!==sl)sl.value=valToPos(d.key,l.vmax);
    if(sl)sl.disabled=(l.mode==='frame');
    const sv=document.getElementById('scv-'+d.key);
    if(sv)sv.textContent=(l.mode==='frame')?'per frame':fmt(l.vmax,d.unit);
    const mn=document.getElementById('cb-min-'+d.key);
    const mx=document.getElementById('cb-max-'+d.key);
    if(mn)mn.textContent=fmt(vmin,'').trim();
    if(mx)mx.textContent=fmt(vmax,d.unit);
    const rb=document.getElementById('rst-'+d.key);
    if(rb)rb.classList.toggle('dirty',!l.auto&&l.mode==='view');
  });
}

function toggleLayer(key){
  const l=LAYERS[key];
  if(!l)return;
  if(l.on){l.hide();eyeOn[key]=false;}
  else{l.show();l.render&&l.render(currentT);eyeOn[key]=true;}
  document.getElementById('eye-'+key).classList.toggle('on',eyeOn[key]);
}

/* ---- timeline ---------------------------------------------------------- */
function seek(v){
  currentT=+v;
  document.getElementById('tlabel').textContent=TIMES[currentT]||'-';
  if(LAYERS)for(const k in LAYERS)LAYERS[k].render&&LAYERS[k].render(currentT);
  if(staBuilt)updateSta(currentT);
}
function togglePlay(){
  playing=!playing;
  document.getElementById('play-btn').textContent=playing?'Pause':'Play';
  if(playing){
    playTimer=setInterval(()=>{
      currentT=(currentT+1)%TIMES.length;
      document.getElementById('tslider').value=currentT;
      seek(currentT);
    },320);
  }else clearInterval(playTimer);
}

/* ---- stations ---------------------------------------------------------- */
function toggleSta(){
  const sec=document.getElementById('sta-sec');
  if(staBuilt){sec.style.display=sec.style.display==='none'?'':'none';return;}
  staBuilt=true;
  Object.keys(META.sta_info).forEach(n=>{
    sec.insertAdjacentHTML('beforeend',
      '<div class="sc"><h4>'+n
      +'<button class="expand" onclick="openSta(\''+n+'\')" title="open large">&#9974;</button>'
      +'</h4><div id="sp-'+n+'" style="height:118px"></div></div>');
  });
  Object.keys(META.sta_info).forEach(n=>drawSta(n,currentT));
}

/* ---- enlarged station chart -------------------------------------------- */
let modalSta=null;
function openSta(name){
  modalSta=name;
  document.getElementById('modal-title').textContent=name+' - water level';
  document.getElementById('modal').style.display='flex';
  drawStaBig(name,currentT);
}
function closeSta(ev){
  if(ev&&ev.target&&ev.target.id!=='modal'&&ev.target.id!=='modal-x')return;
  document.getElementById('modal').style.display='none';
  modalSta=null;
}
// Plotly gets no CSS, so the theme has to be handed to it explicitly.
function plotTheme(){
  return (baseTheme==='light')
    ? {tick:'#4c5966',grid:'#d8dde5',ink:'#16202c',cursor:'#16202c'}
    : {tick:'#6b7785',grid:'#1f2937',ink:'#9aa7b4',cursor:'#e6edf3'};
}
function staTraces(name){
  const obs=META.sta_obs[name], mod=META.sta_model[name], tr=[];
  if(obs)tr.push({x:TIMES,y:obs,type:'scatter',mode:'lines',name:'Observed',
                  line:{color:'#58c8d9',width:1.7}});
  if(mod)tr.push({x:TIMES,y:mod,type:'scatter',mode:'lines',name:'Model',
                  line:{color:'#e8a860',width:1.7,dash:'dot'}});
  return tr;
}
function drawStaBig(name,t){
  const th=plotTheme();
  const ax={color:th.ink,gridcolor:th.grid,zerolinecolor:th.grid,
            tickfont:{size:11},showgrid:true};
  Plotly.react('modal-plot',staTraces(name),{
    margin:{l:56,r:18,t:10,b:44},paper_bgcolor:'rgba(0,0,0,0)',
    plot_bgcolor:'rgba(0,0,0,0)',font:{color:th.ink,size:11},
    showlegend:true,legend:{orientation:'h',y:1.1},
    xaxis:ax,yaxis:{...ax,title:{text:'water level (m)',font:{size:11}}},
    shapes:[{type:'line',x0:TIMES[t],x1:TIMES[t],y0:0,y1:1,yref:'paper',
             line:{color:th.cursor,width:1.2,dash:'dot'}}],
  },{displayModeBar:true,responsive:true,
     modeBarButtonsToRemove:['lasso2d','select2d']});
}
function drawSta(name,t){
  const th=plotTheme();
  const ax={color:th.tick,gridcolor:th.grid,zerolinecolor:th.grid,
            tickfont:{size:9},showgrid:true};
  Plotly.react('sp-'+name,staTraces(name),{
    margin:{l:34,r:8,t:4,b:24},paper_bgcolor:'rgba(0,0,0,0)',
    plot_bgcolor:'rgba(0,0,0,0)',font:{color:th.ink,size:9},
    showlegend:true,legend:{orientation:'h',y:1.3,font:{size:9}},
    xaxis:ax,yaxis:{...ax,title:{text:'m',font:{size:9}}},
    shapes:[{type:'line',x0:TIMES[t],x1:TIMES[t],y0:0,y1:1,yref:'paper',
             line:{color:th.cursor,width:1,dash:'dot'}}],
  },{displayModeBar:false,responsive:true});
}
// Moving the cursor is a relayout, not a redraw: a full Plotly.react on three
// charts every 320 ms was enough to stutter the animation.
function updateSta(t){
  Object.keys(META.sta_info).forEach(n=>{
    const el=document.getElementById('sp-'+n);
    if(!el||!el.data)return;
    Plotly.relayout(el,{'shapes[0].x0':TIMES[t],'shapes[0].x1':TIMES[t]});
  });
  if(modalSta){
    const el=document.getElementById('modal-plot');
    if(el&&el.data)Plotly.relayout(el,{'shapes[0].x0':TIMES[t],'shapes[0].x1':TIMES[t]});
  }
}

loadAll().catch(e=>{
  document.getElementById('ld-status').textContent='Failed: '+e.message;
  console.error(e);
});
</script>
"""


def write_html():
    HTML.write_text(PAGE.replace('__ZOOM_FINE__', str(ZOOM_FINE)), encoding='utf-8')
    print(f'index.html  {HTML.stat().st_size/1e3:.0f} kB')


if __name__ == '__main__':
    import sys
    if '--html-only' in sys.argv:
        write_html()          # front-end iteration without rewriting 147 MB
    else:
        build()
