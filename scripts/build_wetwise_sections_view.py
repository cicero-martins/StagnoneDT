"""Build the perspective view of the velocity sections for the WetWise portal.

Consumes sections.nc as written by extract_velocity_sections.py and writes a
standalone page with a Plotly 3D scene, in perspective projection, in which
the surface-layer currents are drawn as arrows on a plane at the free surface
and the vertical sections hang below it as curtains coloured by the velocity
normal to each section.  Arrows on the curtains carry the along-section and
vertical components, both under the same vertical exaggeration as the
geometry, so that their inclination is the inclination of the flow in the
exaggerated scene.

Usage
    python build_wetwise_sections_view.py --cache <dir holding sections.nc>
        [--start 2025-07-08T06:00] [--stop 2025-07-09T20:00] [--title ...]
"""
from pathlib import Path
import argparse
import json
import sys

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_wetwise_hydrodynamics_demo import LDB, _read_ldb  # noqa: E402

R_EARTH = 6371000.0
H_DRY = 0.05            # m, water depth below which a section sample is dry
SURF_ARROW_STRIDE = 4   # every fourth surface grid point (~350 m)
SEC_ARROW_STRIDE = 10   # every tenth section sample (250 m)
SEC_ARROW_LAYERS = (1, 4, 8)
SCENE_Z = 0.30          # height of the scene box relative to its N-S extent

LABELS = [(12.4572, 37.9080, 'Bocca Nord'), (12.4470, 37.8420, 'Bocca Sud'),
          (12.4660, 37.8790, 'Mozia'), (12.4600, 37.8200, 'southern basin'),
          (12.4810, 37.8620, 'E-W section')]


def km(lon, lat, lon0, lat0, latc):
    """Local equirectangular kilometres from (lon0, lat0), scaled at latc."""
    k = np.pi / 180 * R_EARTH / 1000
    return (np.asarray(lon) - lon0) * k * np.cos(np.radians(latc)), \
        (np.asarray(lat) - lat0) * k


def r(a, nd=3):
    """Rounded nested list with NaN as null, for a compact JSON payload."""
    a = np.round(np.asarray(a, float), nd)
    return [None if not np.isfinite(x) else float(x) for x in a.ravel()] \
        if a.ndim == 1 else [r(x, nd) for x in a]


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--start', default='2025-07-08T06:00')
    ap.add_argument('--stop', default='2025-07-09T20:00')
    ap.add_argument('--title', default='Stagnone, vertical sections')
    ap.add_argument('--member', default=None,
                    help='label of the run shown, defaults to the source dir')
    ap.add_argument('--vmax', type=float, default=None,
                    help='curtain colour range (m/s), default 98th percentile of |u_n|')
    ap.add_argument('--smax', type=float, default=None,
                    help='surface colour range (m/s), default 98th percentile')
    ap.add_argument('--uref', type=float, default=None,
                    help='section arrow saturation speed (m/s), default 90th percentile')
    return ap


def open_cache(args):
    return xr.open_dataset(Path(args.cache) / 'sections.nc').sel(
        time=slice(args.start, args.stop))


def build_payload(ds, args):
    """Scene payload shared by the arrow view and the particle view."""
    sections = [k[:-len('_dist')] for k in ds.coords if k.endswith('_dist')]

    lon0, lat0 = float(ds.slon[0]), float(ds.slat[0])
    latc = float(ds.slat.mean())

    payload = {'times': [str(t)[:16].replace('T', ' ') for t in ds.time.values],
               'member': args.member or ds.attrs.get('source', ''),
               'sections': {}}

    # surface plane
    X, Y = km(*np.meshgrid(ds.slon.values, ds.slat.values), lon0, lat0, latc)
    # the grid arrives wet only inside the lagoon faces, so the open sea west
    # of Isola Grande, faster by a factor of three, does not enter the scales
    u, v, s1 = ds.surf_ucx.values, ds.surf_ucy.values, ds.surf_s1.values
    st = SURF_ARROW_STRIDE
    sub = (slice(None), slice(None, None, st), slice(None, None, st))
    xa, ya = X[::st, ::st].ravel(), Y[::st, ::st].ravel()
    ua, va = u[sub].reshape(len(ds.time), -1), v[sub].reshape(len(ds.time), -1)
    za = s1[sub].reshape(len(ds.time), -1)
    keep = np.isfinite(ua).any(0)
    # the plane itself is drawn on the triangular lagoon faces of the mesh,
    # with the node elevation the mean of the faces around it
    nodes, tri = np.unique(np.round(np.c_[ds.lag_xb.values.ravel(),
                                          ds.lag_yb.values.ravel()], 7),
                           axis=0, return_inverse=True)
    tri = tri.reshape(-1, 3)
    nnode = len(nodes)
    cnt = np.bincount(tri.ravel(), minlength=nnode)
    fs1 = ds.lag_s1.values
    nz = np.stack([np.bincount(tri.ravel(), np.repeat(np.nan_to_num(f), 3),
                               minlength=nnode) / cnt for f in fs1])
    mx, my = km(nodes[:, 0], nodes[:, 1], lon0, lat0, latc)
    fspeed = np.nan_to_num(np.hypot(ds.lag_ucx.values, ds.lag_ucy.values))
    payload['mesh'] = {
        'x': r(mx), 'y': r(my), 'i': tri[:, 0].tolist(), 'j': tri[:, 1].tolist(),
        'k': tri[:, 2].tolist(), 'z': [r(f, 3) for f in nz],
        'speed': [r(f, 3) for f in fspeed]}
    payload['surface'] = {
        'x': r(X[0], 3), 'y': r(Y[:, 0], 3),
        'ax': r(xa[keep]), 'ay': r(ya[keep]),
        'az': [r(f[keep]) for f in za],
        'au': [r(f[keep] / 1000, 6) for f in ua],
        'av': [r(f[keep] / 1000, 6) for f in va],
    }

    for name in sections:
        lon, lat = ds[f'{name}_lon'].values, ds[f'{name}_lat'].values
        x, y = km(lon, lat, lon0, lat0, latc)
        h = (ds[f'{name}_s1'] - ds[f'{name}_bl']).values
        dry = ~(h > H_DRY)
        z = ds[f'{name}_z'].values
        un = ds[f'{name}_un'].values
        ut = ds[f'{name}_ut'].values
        w = ds[f'{name}_w'].values
        bl = ds[f'{name}_bl'].values
        for a in (z, un, ut, w):
            a[dry] = np.nan
        # the curtain spans bed to surface: bed row, layer centres, surface row
        zc = np.concatenate([np.where(dry, np.nan, bl)[..., None], z,
                             np.where(dry, np.nan, ds[f'{name}_s1'].values)[..., None]],
                            axis=-1)
        unc = np.concatenate([un[..., :1], un, un[..., -1:]], axis=-1)
        # tangent per sample, from the sample coordinates
        tx, ty = np.gradient(x), np.gradient(y)
        nrm = np.hypot(tx, ty)
        tx, ty = tx / nrm, ty / nrm
        i_ar = np.arange(0, len(x), SEC_ARROW_STRIDE)
        k_ar = np.array(SEC_ARROW_LAYERS)
        I, K = np.meshgrid(i_ar, k_ar, indexing='ij')
        I, K = I.ravel(), K.ravel()
        payload['sections'][name] = {
            'x': r(x), 'y': r(y), 'dist': r(ds[f'{name}_dist'].values / 1000),
            'z': [r(f.T) for f in zc], 'un': [r(f.T) for f in unc],
            'bl': [r(f) for f in np.where(dry, np.nan, bl)],
            'ax': r(x[I]), 'ay': r(y[I]),
            'az': [r(f[I, K]) for f in z],
            'au': [r(f[I, K] * tx[I] / 1000, 6) for f in ut],
            'av': [r(f[I, K] * ty[I] / 1000, 6) for f in ut],
            'aw': [r(f[I, K], 6) for f in w],
        }

    # land outline inside the scene
    xmin, xmax = float(X.min()), float(X.max())
    ymin, ymax = float(Y.min()), float(Y.max())
    coast = []
    for pts in _read_ldb(LDB).values():
        p = np.asarray(pts)
        if p.size == 0:
            continue
        cxk, cyk = km(p[:, 0], p[:, 1], lon0, lat0, latc)
        inside = (cxk >= xmin) & (cxk <= xmax) & (cyk >= ymin) & (cyk <= ymax)
        if inside.sum() < 2:
            continue
        cxk = np.where(inside, cxk, np.nan)
        cyk = np.where(inside, cyk, np.nan)
        coast.append([r(cxk), r(cyk)])
    payload['coast'] = coast
    payload['extent'] = [xmin, xmax, ymin, ymax]
    zmin = float(np.nanmin([np.nanmin(np.asarray(s['z'], float))
                            for s in payload['sections'].values()]))
    payload['zrange'] = [zmin - 0.1, 0.6]
    exag = SCENE_Z / (payload['zrange'][1] - payload['zrange'][0]) * \
        (ymax - ymin) * 1000
    payload['exag'] = round(exag, -1)
    payload['aspect'] = {'x': (xmax - xmin) / (ymax - ymin), 'y': 1, 'z': SCENE_Z}
    # open on the instant of largest surface-to-bed velocity difference,
    # averaged over all section samples
    shear = sum(np.nanmean(np.hypot(
        (ds[f'{n}_un'].isel(layer=-1) - ds[f'{n}_un'].isel(layer=0)).values,
        (ds[f'{n}_ut'].isel(layer=-1) - ds[f'{n}_ut'].isel(layer=0)).values), axis=1)
        for n in sections)
    payload['start'] = int(np.nanargmax(shear))
    # colour and arrow scales follow the run, since the canopy members flow
    # three to four times slower than the bare ones and a fixed range would
    # leave their curtains blank; fixed values allow pages to be compared
    un_all = np.concatenate([np.abs(ds[f'{n}_un'].values).ravel() for n in sections])
    sp_sec = np.concatenate([np.hypot(ds[f'{n}_un'], ds[f'{n}_ut']).values.ravel()
                             for n in sections])
    w_all = np.concatenate([np.abs(ds[f'{n}_w'].values).ravel() for n in sections])
    sp_surf = np.hypot(u, v)

    def nice(q):
        return round(float(np.ceil(float(q) * 100) / 100), 2)
    payload['scale'] = {
        'vmax': args.vmax or nice(np.nanpercentile(un_all, 98)),
        'smax': args.smax or nice(np.nanpercentile(sp_surf, 98)),
        'uref_surf': nice(np.nanpercentile(sp_surf, 90)),
        'uref_sec': args.uref or nice(np.nanpercentile(sp_sec, 90)),
        'wref': float(np.nanpercentile(w_all, 95)),
    }
    print('scales', payload['scale'])
    payload['labels'] = []
    for lon, lat, txt in LABELS:
        lx, ly = km(lon, lat, lon0, lat0, latc)
        payload['labels'].append([round(float(lx), 3), round(float(ly), 3), txt])
    return payload


# The payload goes in a JSON file beside the page and is fetched with a
# progress bar, since inline it made a 10-15 MB page that stayed blank while
# downloading.  The scene script waits as text until the data has arrived.
# Fetching needs http, so the pages are opened locally through
# serve_wetwise.py rather than as files.
LOADER = r"""<div id="ld" style="position:fixed;inset:0;z-index:20;display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:10px;
  background:var(--bg);color:var(--ink);font-size:13px">
  <div style="font-weight:600">Loading the sections</div>
  <div id="ld-t" style="color:var(--muted);font-size:12px">connecting ...</div>
  <div style="width:260px;height:4px;background:var(--line);border-radius:2px;overflow:hidden">
    <div id="ld-b" style="height:100%;width:2%;background:var(--ink);transition:width .2s"></div></div>
</div>
<script>
(() => {
  const bar = document.getElementById('ld-b'), txt = document.getElementById('ld-t');
  const fail = m => { txt.textContent = 'could not load the data (' + m + ')'; };
  const x = new XMLHttpRequest();
  x.open('GET', '__DATA_URL__');
  x.setRequestHeader('Cache-Control', 'no-cache');
  x.onprogress = e => {
    const mb = (e.loaded / 1e6).toFixed(1);
    txt.textContent = e.lengthComputable ? `${mb} of ${(e.total / 1e6).toFixed(1)} MB` : `${mb} MB`;
    if (e.lengthComputable) bar.style.width = Math.max(2, 100 * e.loaded / e.total) + '%';
  };
  x.onerror = () => fail('network error');
  x.onload = () => {
    if (x.status !== 200) return fail('HTTP ' + x.status);
    txt.textContent = 'building the scene ...'; bar.style.width = '100%';
    // let the message paint before the parse blocks the page
    setTimeout(() => {
      try { window.__D = JSON.parse(x.responseText); } catch (e) { return fail(e.message); }
      const s = document.createElement('script');
      s.textContent = document.getElementById('main-js').textContent;
      document.body.appendChild(s);
      document.getElementById('ld').remove();
    }, 30);
  };
  x.send();
})();
</script>
"""


def write_page(payload, template, out, title):
    data = out.with_name(out.stem + '_data.json')
    data.write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    html = template.replace('__TITLE__', title).replace(
        '<script>\nconst D = __DATA__;',
        LOADER.replace('__DATA_URL__', data.name) +
        '<script type="text/plain" id="main-js">\nconst D = window.__D;')
    if 'window.__D' not in html:
        raise SystemExit('template has no data hook')
    out.write_text(html, encoding='utf-8')
    print(f'wrote {out} and {data.name}  ({data.stat().st_size / 1e6:.1f} MB, '
          f'{len(payload["times"])} frames, vertical exaggeration '
          f'{payload["exag"]:.0f}x)')


def main():
    args = parser().parse_args()
    ds = open_cache(args)
    payload = build_payload(ds, args)
    write_page(payload, TEMPLATE, Path(args.cache) / 'index.html', args.title)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
:root { --bg:#ffffff; --ink:#1b1b1b; --muted:#6b6b6b; --line:#e3e2de; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16171a; --ink:#ececec; --muted:#a0a0a0; --line:#33343a; }
}
html, body { margin:0; height:100%; background:var(--bg); color:var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
#wrap { display:flex; flex-direction:column; height:100%; }
header { padding:10px 16px 6px; border-bottom:1px solid var(--line); }
header h1 { font-size:16px; margin:0 0 2px; font-weight:600; }
header nav { float:right; font-size:12px; }
header nav a { color:var(--ink); margin-left:14px; text-decoration:none;
  border:1px solid var(--line); border-radius:6px; padding:3px 10px; }
header nav a:hover { border-color:var(--ink); }
header p { font-size:12px; margin:0; color:var(--muted); }
#scene { flex:1; min-height:360px; }
#ctl { display:flex; gap:12px; align-items:center; padding:8px 16px 12px;
  border-top:1px solid var(--line); font-size:13px; flex-wrap:wrap; }
#ctl input[type=range] { flex:1; min-width:160px; }
button { font:inherit; padding:4px 12px; border:1px solid var(--line);
  background:transparent; color:var(--ink); border-radius:6px; cursor:pointer; }
#t { font-variant-numeric: tabular-nums; min-width:120px; }
#stage { flex:1; position:relative; min-height:360px; }
#scene { position:absolute; inset:0; }
#tools { position:absolute; top:8px; left:12px; z-index:5; display:flex;
  flex-direction:column; gap:6px; font-size:12px; }
#tools .row { display:flex; gap:4px; flex-wrap:wrap; align-items:center; }
#tools .lbl { color:var(--muted); min-width:44px; }
#tools button { padding:2px 8px; font-size:12px; background:var(--bg); }
#tools button.on { border-color:var(--ink); }
#tools label { display:flex; gap:4px; align-items:center; padding:2px 8px;
  border:1px solid var(--line); border-radius:6px; background:var(--bg); cursor:pointer; }
</style>
</head>
<body>
<div id="wrap">
<header>
  <nav><a href="particles.html">Particle view</a><a href="../../index.html">&larr; WetWise portal</a></nav>
  <h1>__TITLE__</h1>
  <p id="sub"></p>
</header>
<div id="stage">
  <div id="scene"></div>
  <div id="tools">
    <div class="row" id="views"><span class="lbl">View</span></div>
    <div class="row" id="layers"><span class="lbl">Layers</span></div>
  </div>
</div>
<div id="ctl">
  <button id="play">Play</button>
  <input id="slider" type="range" min="0" value="0">
  <span id="t"></span>
</div>
</div>
<script>
const D = __DATA__;
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const INK = dark ? '#ececec' : '#1b1b1b', MUTED = dark ? '#a0a0a0' : '#6b6b6b';
const ARROW = dark ? '#f2f2f2' : '#1b1b1b';
const COAST = dark ? '#8a8a8a' : '#7a7a7a';
const VMAX = D.scale.vmax, SMAX = D.scale.smax, DZMAX = 0.25, DZREF = 0.12;
const DIV = [[0,'#2f5f98'],[0.25,'#8fb3d9'],[0.5,'#efefef'],[0.75,'#e3a08b'],[1,'#b2413a']];
document.getElementById('sub').textContent =
  `${D.member} · surface plane coloured by surface speed, curtains by the velocity normal to each section ` +
  `(positive to the left of the section direction) · arrows saturate at ${D.scale.uref_sec} m/s in the sections ` +
  `and ${D.scale.uref_surf} m/s on the surface · vertical exaggeration about ${D.exag}×`;

// Arrows as line segments.  Horizontal length grows with the square root of
// speed up to lmax km at uref m/s and saturates there, so the inlet jets do
// not swamp the lagoon and the direction of the slow near-bed flow stays
// legible.  The vertical rise is proportional to w alone, DZREF m at the
// 95th percentile of |w| and capped at DZMAX, so a steep arrow marks strong
// vertical flow and not weak horizontal flow.  u and v arrive in km/s, w in m/s.
// The two barbs of each head are built in normalised scene space, where the
// box is the aspect ratio, so that they keep their shape under the
// exaggeration.  Surface arrows get barbs in the horizontal plane, section
// arrows in the vertical plane that contains the arrow.
const SC = () => {
  const a = D.aspect, e = D.extent, zr = D.zrange;
  return {f:[a.x / (e[1] - e[0]), a.y / (e[3] - e[2]), a.z / (zr[1] - zr[0])]};
};
function arrows(x, y, z, u, v, w, lmax, uref, width) {
  const f = SC().f, lx = [], ly = [], lz = [];
  for (let k = 0; k < x.length; k++) {
    if (u[k] === null || v[k] === null || z[k] === null) continue;
    const sp = Math.hypot(u[k], v[k]) * 1000;
    if (!(sp > 1e-4)) continue;
    const L = lmax * Math.min(Math.sqrt(sp / uref), 1);
    const ex = u[k] * 1000 / sp, ey = v[k] * 1000 / sp;
    const dz = w ? Math.max(-DZMAX, Math.min(DZMAX, (w[k] || 0) / D.scale.wref * DZREF)) : 0;
    const t = [x[k] + ex * L, y[k] + ey * L, z[k] + dz];
    lx.push(x[k], t[0], null); ly.push(y[k], t[1], null); lz.push(z[k], t[2], null);
    // direction in normalised space
    const d = [ex * L * f[0], ey * L * f[1], dz * f[2]];
    const n = Math.hypot(...d);
    if (n < 1e-6) continue;
    const dn = d.map(c => c / n);
    let p = w ? [-dn[0] * dn[2], -dn[1] * dn[2], dn[0] ** 2 + dn[1] ** 2]   // in vertical plane
              : [-dn[1], dn[0], 0];                                         // horizontal
    const pn = Math.hypot(...p) || 1;
    p = p.map(c => c / pn);
    const hl = Math.max(0.35 * n, 0.006);
    for (const sgn of [1, -1]) {
      const b = [0, 1, 2].map(j => (-dn[j] * hl + sgn * 0.5 * hl * p[j]) / f[j]);
      lx.push(t[0], t[0] + b[0], null); ly.push(t[1], t[1] + b[1], null);
      lz.push(t[2], t[2] + b[2], null);
    }
  }
  return [{type:'scatter3d', mode:'lines', x:lx, y:ly, z:lz, line:{color:ARROW, width},
           hoverinfo:'skip', showlegend:false}];
}

const SECTION_LABEL = {ns_axis:'N–S section', ew_centre:'E–W section'};
const ON = {surface:true, coast:true};
for (const name of Object.keys(D.sections)) ON[name] = true;

function traces(i) {
  const S = D.surface, out = [];
  const M = D.mesh;
  if (ON.surface) out.push({type:'mesh3d', x:M.x, y:M.y, z:M.z[i], i:M.i, j:M.j, k:M.k,
    intensity:M.speed[i], intensitymode:'cell',
    cmin:0, cmax:SMAX, colorscale:'Viridis', opacity:0.45, showscale:true,
    colorbar:{title:{text:'surface |u| (m/s)', side:'right'}, len:0.42, y:0.78, thickness:12,
              tickfont:{color:INK}, titlefont:{color:INK}},
    hoverinfo:'skip', flatshading:true, lighting:{ambient:1, diffuse:0, specular:0}});
  if (ON.surface) out.push(...arrows(S.ax, S.ay, S.az[i], S.au[i], S.av[i], null, 0.30, D.scale.uref_surf, 4));
  let first = true;
  for (const [name, s] of Object.entries(D.sections)) {
    if (!ON[name]) continue;
    const nk = s.z[i].length;
    const xs = Array.from({length:nk}, () => s.x), ys = Array.from({length:nk}, () => s.y);
    out.push({type:'surface', x:xs, y:ys, z:s.z[i], surfacecolor:s.un[i],
      cmin:-VMAX, cmax:VMAX, colorscale:DIV, showscale:first,
      colorbar:{title:{text:'normal velocity (m/s)', side:'right'}, len:0.42, y:0.26, thickness:12,
                tickfont:{color:INK}, titlefont:{color:INK}},
      hovertemplate:`${SECTION_LABEL[name] || name}<br>z %{z:.2f} m<br>uₙ %{surfacecolor:.3f} m/s<extra></extra>`,
      lighting:{ambient:1, diffuse:0, specular:0}});
    out.push({type:'scatter3d', mode:'lines', x:s.x, y:s.y, z:s.bl[i],
      line:{color:INK, width:3}, hoverinfo:'skip', showlegend:false});
    out.push(...arrows(s.ax, s.ay, s.az[i], s.au[i], s.av[i], s.aw[i], 0.22, D.scale.uref_sec, 3));
    first = false;
  }
  if (!ON.coast) return out;
  out.push({type:'scatter3d', mode:'text', x:D.labels.map(l => l[0]), y:D.labels.map(l => l[1]),
    z:D.labels.map(() => 0.45), text:D.labels.map(l => l[2]),
    textfont:{color:INK, size:12}, hoverinfo:'skip', showlegend:false});
  for (const [cx, cy] of D.coast) {
    out.push({type:'scatter3d', mode:'lines', x:cx, y:cy, z:cx.map(() => 0.15),
      line:{color:COAST, width:2}, hoverinfo:'skip', showlegend:false});
  }
  return out;
}
const ax = (t, rng) => ({title:{text:t, font:{color:MUTED, size:11}}, range:rng,
  color:MUTED, gridcolor:dark ? '#2a2b30' : '#ecebe7', zeroline:false,
  backgroundcolor:'rgba(0,0,0,0)', showbackground:false});
const layout = {
  paper_bgcolor:'rgba(0,0,0,0)', margin:{l:0, r:0, t:0, b:0}, showlegend:false,
  uirevision:'keep',
  scene:{xaxis:{...ax('', [D.extent[0], D.extent[1]]), showticklabels:false, showgrid:false},
         yaxis:{...ax('', [D.extent[2], D.extent[3]]), showticklabels:false, showgrid:false},
         zaxis:ax('z (m)', D.zrange),
         aspectmode:'manual', aspectratio:D.aspect,
         camera:{eye:{x:0.95, y:-0.40, z:0.45}, projection:{type:'perspective'}}}
};
const el = document.getElementById('scene');
const sl = document.getElementById('slider'), tl = document.getElementById('t');
sl.max = D.times.length - 1;
function show(i) { Plotly.react(el, traces(i), layout, {responsive:true, displaylogo:false});
  tl.textContent = D.times[i] + ' UTC'; }
sl.addEventListener('input', () => show(+sl.value));

// Preset cameras, in the normalised scene box (x east, y north, z up).  The
// camera the viewer rotates to is captured, so the next frame does not snap
// it back to the preset.
const UP = {x:0, y:0, z:1};
const VIEWS = [
  ['Initial', {eye:{x:0.95, y:-0.40, z:0.45}, up:UP}],
  ['NW', {eye:{x:-0.62, y:0.72, z:0.45}, up:UP}],
  ['NE', {eye:{x:0.62, y:0.72, z:0.45}, up:UP}],
  ['SW', {eye:{x:-0.62, y:-0.72, z:0.45}, up:UP}],
  ['SE', {eye:{x:0.62, y:-0.72, z:0.45}, up:UP}],
  ['East side', {eye:{x:1.10, y:0, z:0.08}, up:UP}],
  ['South side', {eye:{x:0, y:-1.20, z:0.08}, up:UP}],
  ['Top', {eye:{x:0, y:-0.001, z:1.45}, up:{x:0, y:1, z:0}}],
];
const vbox = document.getElementById('views');
for (const [name, cam] of VIEWS) {
  const b = document.createElement('button');
  b.textContent = name;
  b.addEventListener('click', () => {
    layout.scene.camera = {...cam, center:{x:0, y:0, z:0}, projection:{type:'perspective'}};
    Plotly.relayout(el, {'scene.camera': layout.scene.camera});
    vbox.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
  });
  vbox.appendChild(b);
}
el.addEventListener('mousedown', () =>
  vbox.querySelectorAll('button').forEach(x => x.classList.remove('on')));

const lbox = document.getElementById('layers');
const LAYERS = [['surface', 'Surface'],
  ...Object.keys(D.sections).map(n => [n, SECTION_LABEL[n] || n]),
  ['coast', 'Coast and labels']];
for (const [key, text] of LAYERS) {
  const lab = document.createElement('label'), cb = document.createElement('input');
  cb.type = 'checkbox'; cb.checked = ON[key];
  cb.addEventListener('change', () => { ON[key] = cb.checked; show(+sl.value); });
  lab.append(cb, text);
  lbox.appendChild(lab);
}
let timer = null;
document.getElementById('play').addEventListener('click', e => {
  if (timer) { clearInterval(timer); timer = null; e.target.textContent = 'Play'; return; }
  e.target.textContent = 'Pause';
  timer = setInterval(() => { sl.value = (+sl.value + 1) % D.times.length; show(+sl.value); }, 450);
});
sl.value = D.start; show(D.start);
el.on('plotly_relayout', ev => {
  if (ev['scene.camera']) layout.scene.camera = ev['scene.camera'];
});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    main()
