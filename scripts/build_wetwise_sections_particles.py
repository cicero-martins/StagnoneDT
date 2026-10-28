"""Particle variant of the perspective view of the velocity sections.

Same scene as build_wetwise_sections_view.py (surface plane above vertical
curtains, in perspective, under the same vertical exaggeration), with the
arrows replaced by animated particle trails.  Each particle stays in the plane
it was released in.  On the surface plane it is advected by the surface-layer
velocity; on a curtain it is advected by the along-section component and by
the vertical one, in sigma coordinates so that it never leaves the water
column.  The component across a section cannot move a particle confined to
it, and remains carried by the colour of the curtain.  The field is
interpolated linearly in time between the stored instants, and in space
bilinearly on the surface grid and on the (sample, layer) grid of each
section.

Usage
    python build_wetwise_sections_particles.py --cache <dir holding sections.nc>
        [--start ...] [--stop ...] [--member ...] [--vmax ...] [--smax ...]

Writes particles.html next to sections.nc, leaving index.html untouched.
"""
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_wetwise_sections_view import (  # noqa: E402
    H_DRY, build_payload, open_cache, parser, write_page)


def ri(a, scale):
    """Nested list of integers in units of 1/scale, NaN as null."""
    a = np.asarray(a, float) * scale
    if a.ndim == 1:
        return [None if not np.isfinite(x) else int(round(x)) for x in a]
    return [ri(x, 1) for x in a]


def add_particle_fields(ds, payload):
    """Full-resolution fields for the advection, beside the arrow subsets.

    Stored as integers to keep the page small: surface velocity in mm/s,
    surface elevation in cm, along-section velocity in 0.1 mm/s and vertical
    velocity in um/s.
    """
    # only the grid cells wet at some instant are stored, as flat lists
    u, v, z = (ds[k].values.reshape(ds.sizes['time'], -1)
               for k in ('surf_ucx', 'surf_ucy', 'surf_s1'))
    wet = np.flatnonzero(np.isfinite(u).any(0))
    payload['surface']['wet'] = wet.tolist()
    payload['surface']['gu'] = [ri(f[wet], 1e3) for f in u]
    payload['surface']['gv'] = [ri(f[wet], 1e3) for f in v]
    payload['surface']['gz'] = [ri(f[wet], 1e2) for f in z]
    for name, sec in payload['sections'].items():
        dry = ~((ds[f'{name}_s1'] - ds[f'{name}_bl']).values > H_DRY)
        ut = ds[f'{name}_ut'].values.copy()
        w = ds[f'{name}_w'].values.copy()
        ut[dry] = np.nan
        w[dry] = np.nan
        sec['ut'] = [ri(f.T, 1e4) for f in ut]
        sec['w'] = [ri(f.T, 1e6) for f in w]
    dt = np.diff(ds.time.values).astype('timedelta64[s]').astype(float)
    payload['dt_frame'] = float(np.median(dt))


def main():
    args = parser().parse_args()
    ds = open_cache(args)
    payload = build_payload(ds, args)
    add_particle_fields(ds, payload)
    write_page(payload, TEMPLATE, Path(args.cache) / 'particles.html',
               args.title)


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
#ctl { display:flex; gap:12px; align-items:center; padding:8px 16px 12px;
  border-top:1px solid var(--line); font-size:13px; flex-wrap:wrap; }
#ctl input[type=range] { flex:1; min-width:160px; }
button, select { font:inherit; padding:4px 12px; border:1px solid var(--line);
  background:transparent; color:var(--ink); border-radius:6px; cursor:pointer; }
select { padding:3px 6px; background:var(--bg); }
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
  <nav><a href="index.html">Arrow view</a><a href="../../index.html">&larr; WetWise portal</a></nav>
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
  <label>Flow speed-up <select id="speed">
    <option value="3600">1 h per s</option>
    <option value="7200" selected>2 h per s</option>
    <option value="14400">4 h per s</option>
  </select></label>
</div>
</div>
<script>
const D = __DATA__;
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const INK = dark ? '#ececec' : '#1b1b1b', MUTED = dark ? '#a0a0a0' : '#6b6b6b';
const BG = dark ? '#16171a' : '#ffffff';
const COAST = dark ? '#8a8a8a' : '#7a7a7a';
const VMAX = D.scale.vmax, SMAX = D.scale.smax;
const DIV = [[0,'#2f5f98'],[0.25,'#8fb3d9'],[0.5,'#efefef'],[0.75,'#e3a08b'],[1,'#b2413a']];
const TRAILSCALE = [[0, BG], [1, INK]];
document.getElementById('sub').textContent =
  `${D.member} · surface plane coloured by surface speed, curtains by the velocity normal to each section ` +
  `(positive to the left of the section direction) · particles move within their own plane, by the surface-layer ` +
  `velocity on the surface and by the along-section and vertical velocity on the curtains · vertical exaggeration about ${D.exag}×`;

// ---------------------------------------------------------------- sampling
// Fields are linear in time between stored instants i0 and i1 (weight al).
const lerpT = (a, b, al) => a === null ? b : b === null ? a : a + (b - a) * al;
const S = D.surface, SDX = S.x[1] - S.x[0], SDY = S.y[1] - S.y[0], NX = S.x.length;
// surface fields hold only the wet cells; CELL maps a grid cell to its slot
const CELL = new Int32Array(NX * S.y.length).fill(-1);
S.wet.forEach((idx, n) => { CELL[idx] = n; });
function surfAt(F, i0, i1, al, x, y) {
  const fx = (x - S.x[0]) / SDX, fy = (y - S.y[0]) / SDY;
  const c = Math.floor(fx), q = Math.floor(fy);
  if (c < 0 || q < 0 || c >= S.x.length - 1 || q >= S.y.length - 1) return null;
  const tx = fx - c, ty = fy - q;
  let sw = 0, sv = 0;
  const corner = (rr, cc, wt) => {
    const n = CELL[rr * NX + cc];
    if (n < 0) return;
    const v = lerpT(F[i0][n], F[i1][n], al);
    if (v !== null) { sw += wt; sv += wt * v; }
  };
  corner(q, c, (1 - tx) * (1 - ty)); corner(q, c + 1, tx * (1 - ty));
  corner(q + 1, c, (1 - tx) * ty); corner(q + 1, c + 1, tx * ty);
  return sw > 0.3 ? sv / sw : null;
}
// along a section: p is the fractional sample index, row a row of F[i]
function rowAt(F, i0, i1, al, row, p) {
  const j = Math.floor(p), t = p - j;
  const a = lerpT(F[i0][row][j], F[i1][row][j], al);
  const b = lerpT(F[i0][row][j + 1], F[i1][row][j + 1], al);
  if (a === null || b === null) return null;
  return a + (b - a) * t;
}
// layer centres sit at sigma = (k + 1/2) / nk
function layerAt(F, i0, i1, al, p, sig, nk) {
  const ks = Math.max(0, Math.min(nk - 1.000001, sig * nk - 0.5));
  const k = Math.floor(ks), t = ks - k;
  const a = rowAt(F, i0, i1, al, k, p);
  const b = rowAt(F, i0, i1, al, Math.min(k + 1, nk - 1), p);
  if (a === null || b === null) return null;
  return a + (b - a) * t;
}
const lin = (arr, p) => { const j = Math.floor(p), t = p - j;
  return arr[j] + (arr[Math.min(j + 1, arr.length - 1)] - arr[j]) * t; };

// ---------------------------------------------------------------- particles
const TRAIL = 16, TICK = 50;           // positions kept per trail, ms per step
const SECS = Object.keys(D.sections);
const P = [];                          // {kind, sec, x, y, s, sig, age, life, hx, hy, hz}
function wetSurfaceCells(i) {
  const out = [];
  S.gu[i].forEach((v, n) => { if (v !== null) out.push([Math.floor(S.wet[n] / NX), S.wet[n] % NX]); });
  return out;
}
function wetSamples(name, i) {
  const z = D.sections[name].z[i], nk = z.length - 2, out = [];
  for (let p = 0; p < z[0].length - 1; p++)
    if (z[0][p] !== null && z[nk + 1][p] !== null && z[0][p + 1] !== null) out.push(p);
  return out;
}
let WET = null;
function refreshWet(i) {
  WET = {surface: wetSurfaceCells(i)};
  for (const n of SECS) WET[n] = wetSamples(n, i);
}
function spawn(pt) {
  pt.age = 0; pt.life = 40 + Math.floor(Math.random() * 80);
  pt.hx = []; pt.hy = []; pt.hz = [];
  if (pt.kind === 'surface') {
    const [q, c] = WET.surface[Math.floor(Math.random() * WET.surface.length)];
    pt.x = S.x[c] + (Math.random() - 0.5) * SDX; pt.y = S.y[q] + (Math.random() - 0.5) * SDY;
  } else {
    const w = WET[pt.sec];
    pt.s = w[Math.floor(Math.random() * w.length)] + Math.random();
    pt.sig = 0.05 + 0.9 * Math.random();
  }
}
function initParticles(i) {
  refreshWet(i);
  P.length = 0;
  const nsurf = Math.min(900, WET.surface.length);
  for (let k = 0; k < nsurf; k++) P.push({kind:'surface'});
  for (const n of SECS) {
    const ns = Math.round(1.3 * WET[n].length);
    for (let k = 0; k < ns; k++) P.push({kind:'section', sec:n});
  }
  for (const pt of P) { spawn(pt); pt.age = Math.floor(Math.random() * pt.life); }
}

// one step of dt model seconds in the field at fractional frame tc
function step(pt, tc, dt) {
  const i0 = Math.floor(tc), i1 = Math.min(i0 + 1, D.times.length - 1), al = tc - i0;
  if (++pt.age > pt.life) { spawn(pt); return; }
  let X, Y, Z;
  if (pt.kind === 'surface') {
    const u = surfAt(S.gu, i0, i1, al, pt.x, pt.y), v = surfAt(S.gv, i0, i1, al, pt.x, pt.y);
    if (u === null || v === null) { spawn(pt); return; }
    pt.x += u * dt / 1e6; pt.y += v * dt / 1e6;          // mm/s to km
    const zs = surfAt(S.gz, i0, i1, al, pt.x, pt.y);
    if (zs === null) { spawn(pt); return; }
    X = pt.x; Y = pt.y; Z = zs / 100 + 0.01;
  } else {
    const s = D.sections[pt.sec], nk = s.ut[0].length, ds = (s.dist[1] - s.dist[0]) * 1000;
    if (pt.s < 0 || pt.s >= s.x.length - 1) { spawn(pt); return; }
    const ut = layerAt(s.ut, i0, i1, al, pt.s, pt.sig, nk);
    const w = layerAt(s.w, i0, i1, al, pt.s, pt.sig, nk);
    const bed = rowAt(s.z, i0, i1, al, 0, pt.s), top = rowAt(s.z, i0, i1, al, nk + 1, pt.s);
    if (ut === null || w === null || bed === null || top === null || top - bed < 0.05) { spawn(pt); return; }
    pt.s += ut / 1e4 * dt / ds;                          // 0.1 mm/s to m/s
    pt.sig = Math.max(0.02, Math.min(0.98, pt.sig + w / 1e6 * dt / (top - bed)));   // um/s
    if (pt.s < 0 || pt.s >= s.x.length - 1) { spawn(pt); return; }
    X = lin(s.x, pt.s); Y = lin(s.y, pt.s); Z = bed + pt.sig * (top - bed);
  }
  pt.hx.push(X); pt.hy.push(Y); pt.hz.push(Z);
  if (pt.hx.length > TRAIL) { pt.hx.shift(); pt.hy.shift(); pt.hz.shift(); }
}

// trails as one line trace per plane kind, fading from the background colour
function trailTrace(kind) {
  const x = [], y = [], z = [], c = [];
  for (const pt of P) {
    if (pt.kind !== kind || pt.hx.length < 2) continue;
    if (kind === 'surface' ? !ON.surface : !ON[pt.sec]) continue;
    const n = pt.hx.length;
    for (let j = 0; j < n; j++) { x.push(pt.hx[j]); y.push(pt.hy[j]); z.push(pt.hz[j]); c.push(j / (n - 1)); }
    x.push(null); y.push(null); z.push(null); c.push(0);
  }
  return {x, y, z, c};
}
function particleTraces() {
  return ['surface', 'section'].map(kind => {
    const t = trailTrace(kind);
    return {type:'scatter3d', mode:'lines', x:t.x, y:t.y, z:t.z,
      line:{color:t.c, colorscale:TRAILSCALE, cmin:0, cmax:1, width:kind === 'surface' ? 3 : 2.5},
      hoverinfo:'skip', showlegend:false};
  });
}

// ---------------------------------------------------------------- scene
const SECTION_LABEL = {ns_axis:'N–S section', ew_centre:'E–W section'};
const ON = {surface:true, coast:true};
for (const name of SECS) ON[name] = true;

// particle traces come first, so that their indices stay 0 and 1 whatever
// the layer selection
function traces(i) {
  const out = particleTraces();
  const M = D.mesh;
  if (ON.surface) out.push({type:'mesh3d', x:M.x, y:M.y, z:M.z[i], i:M.i, j:M.j, k:M.k,
    intensity:M.speed[i], intensitymode:'cell',
    cmin:0, cmax:SMAX, colorscale:'Viridis', opacity:0.45, showscale:true,
    colorbar:{title:{text:'surface |u| (m/s)', side:'right'}, len:0.42, y:0.78, thickness:12,
              tickfont:{color:INK}, titlefont:{color:INK}},
    hoverinfo:'skip', flatshading:true, lighting:{ambient:1, diffuse:0, specular:0}});
  let first = true;
  for (const [name, s] of Object.entries(D.sections)) {
    if (!ON[name]) continue;
    const nk = s.z[i].length;
    const xs = Array.from({length:nk}, () => s.x), ys = Array.from({length:nk}, () => s.y);
    out.push({type:'surface', x:xs, y:ys, z:s.z[i], surfacecolor:s.un[i],
      cmin:-VMAX, cmax:VMAX, colorscale:DIV, showscale:first, opacity:0.85,
      colorbar:{title:{text:'normal velocity (m/s)', side:'right'}, len:0.42, y:0.26, thickness:12,
                tickfont:{color:INK}, titlefont:{color:INK}},
      hovertemplate:`${SECTION_LABEL[name] || name}<br>z %{z:.2f} m<br>uₙ %{surfacecolor:.3f} m/s<extra></extra>`,
      lighting:{ambient:1, diffuse:0, specular:0}});
    out.push({type:'scatter3d', mode:'lines', x:s.x, y:s.y, z:s.bl[i],
      line:{color:INK, width:3}, hoverinfo:'skip', showlegend:false});
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
let busy = false, shown = -1;
function show(i) {
  busy = true; shown = i;
  tl.textContent = D.times[i] + ' UTC';
  return Plotly.react(el, traces(i), layout, {responsive:true, displaylogo:false})
    .then(() => { busy = false; });
}

// Preset cameras, in the normalised scene box (x east, y north, z up).
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
const LAYERS = [['surface', 'Surface'], ...SECS.map(n => [n, SECTION_LABEL[n] || n]),
  ['coast', 'Coast and labels']];
for (const [key, text] of LAYERS) {
  const lab = document.createElement('label'), cb = document.createElement('input');
  cb.type = 'checkbox'; cb.checked = ON[key];
  cb.addEventListener('change', () => { ON[key] = cb.checked; show(shown); });
  lab.append(cb, text);
  lbox.appendChild(lab);
}

// ---------------------------------------------------------------- clock
// Particles keep moving in the frozen field while paused; Play also advances
// the field in time.  A full redraw happens only when the stored instant
// changes, otherwise only the two trail traces are restyled.
let tc = D.start, playing = false;
const speed = document.getElementById('speed');
document.getElementById('play').addEventListener('click', e => {
  playing = !playing; e.target.textContent = playing ? 'Pause' : 'Play';
});
sl.addEventListener('input', () => { tc = +sl.value; show(+sl.value); });
function tick() {
  if (busy) return;
  const dt = +speed.value * TICK / 1000;
  if (playing) {
    tc += dt / D.dt_frame;
    if (tc >= D.times.length - 1) tc = 0;
  }
  for (const pt of P) step(pt, tc, dt);
  const i = Math.floor(tc);
  if (i !== shown) { sl.value = i; refreshWet(i); show(i); return; }
  const a = trailTrace('surface'), b = trailTrace('section');
  busy = true;
  Plotly.restyle(el, {x:[a.x, b.x], y:[a.y, b.y], z:[a.z, b.z], 'line.color':[a.c, b.c]}, [0, 1])
    .then(() => { busy = false; });
}
initParticles(D.start);
sl.value = D.start;
show(D.start).then(() => {
  el.on('plotly_relayout', ev => { if (ev['scene.camera']) layout.scene.camera = ev['scene.camera']; });
  setInterval(tick, TICK);
});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    main()
