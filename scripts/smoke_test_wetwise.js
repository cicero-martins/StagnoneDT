/*
 * Headless smoke test for the WetWise portal page.
 *
 * `node --check` only parses; it cannot see a stale reference like
 * META.stops[...] after the payload key was renamed to META.cmaps, which is
 * exactly the class of bug that reaches the browser as
 * "Cannot read properties of undefined".  This stubs just enough of the DOM,
 * Leaflet, leaflet-velocity and Plotly to actually run loadAll() against the
 * real files on disk, then drives a few interactions.
 *
 *   node scripts/smoke_test_wetwise.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const DIR = path.join(ROOT, 'outputs', 'wetwise_tab', 'demo_hydrodynamics');
const HTML = path.join(DIR, 'index.html');

const errors = [];
const els = new Map();

function makeEl(id) {
  return {
    id, textContent: '', innerHTML: '', value: '0', disabled: false, data: null,
    style: {},          // real object: assertions read back what the page set
    classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
    insertAdjacentHTML() {}, addEventListener() {}, appendChild() {},
    getContext: () => ({
      createImageData: (nx, ny) => ({ data: new Uint8ClampedArray(nx * ny * 4) }),
      putImageData() {}, clearRect() {},
    }),
    toDataURL: () => 'data:image/png;base64,AA==',
  };
}
const getEl = id => { if (!els.has(id)) els.set(id, makeEl(id)); return els.get(id); };

const pt = (lat, lng) => ({ x: (lng + 180) * 3000, y: (90 - lat) * 3000 });
let zoom = 11;

const layerStub = () => ({
  addTo() { return this; }, remove() {}, removeFrom() {},
  setUrl() {}, setBounds() {}, setOpacity() {}, setStyle() {},
});

// Image overlays are tracked so the test can assert a hidden field layer really
// comes back on the map -- hiding used to detach the overlay while keeping the
// reference, which left the layer impossible to re-show.
const overlays = [];
const trackedOverlay = () => {
  const o = {
    attached: false, painted: 0,
    addTo() { this.attached = true; return this; },
    remove() { this.attached = false; },
    setUrl() { this.painted++; }, setBounds() {}, setOpacity(v) { this.opacity = v; },
  };
  overlays.push(o);
  return o;
};
const attachedCount = () => overlays.filter(o => o.attached).length;

// Velocity layers are tracked too: offshore currents must survive the zoom to
// lagoon detail, which needs a coarse layer alive alongside the fine one.
const velLayers = [];
const liveVel = () => velLayers.filter(l => l.attached && !l.removed).length;

// `let map` inside the page is a lexical binding, so it never lands on the vm
// global -- capture the instance here instead to drive zoom/pan events.
let mapInstance = null;

const L = {
  map: () => (mapInstance = {
    getBounds: () => ({
      getSouth: () => 37.80, getNorth: () => 37.95,
      getWest: () => 12.35, getEast: () => 12.55,
      _southWest: { lat: 37.80, lng: 12.35 }, _northEast: { lat: 37.95, lng: 12.55 },
    }),
    getCenter: () => ({ lat: 37.87, lng: 12.44 }),
    getSize: () => ({ x: 1100, y: 750 }),
    getZoom: () => zoom,
    latLngToContainerPoint: a => pt(a[0] !== undefined ? a[0] : a.lat,
                                   a[1] !== undefined ? a[1] : a.lng),
    createPane() {}, getPane: () => ({ style: {} }),
    on(ev, fn) { (this._h = this._h || {})[ev] = fn; },
    fire(ev) { if (this._h && this._h[ev]) this._h[ev](); },
    removeLayer(l) { if (l) l.removed = true; }, addLayer() {},
    setView() { return this; }, setMinZoom() { return this; },
    setMaxBounds() { return this; }, getBoundsZoom: () => 10.5,
  }),
  latLngBounds: c => ({
    getCenter: () => ({ lat: (c[0][0] + c[1][0]) / 2, lng: (c[0][1] + c[1][1]) / 2 }),
    pad() { return this; },
  }),
  tileLayer: () => layerStub(),
  imageOverlay: () => trackedOverlay(),
  geoJSON: () => layerStub(),
  latLng: (a, b) => ({ lat: a, lng: b }),
  velocityLayer: o => {
    const l = {
      options: o || {}, _windy: { setData() {} }, _startWindy() {},
      attached: false,
      addTo() { this.attached = true; return this; },
      setData() {}, setOptions() {},
    };
    velLayers.push(l);
    return l;
  },
};

const Plotly = { react() {}, relayout() {}, newPlot() {} };

// --url <base> runs the page against a published deployment instead of the
// local files, which is the only way to prove a visitor's browser can load it
// (object keys, public policy and content types all have to be right).
const REMOTE = (() => {
  const i = process.argv.indexOf('--url');
  return i > -1 ? process.argv[i + 1].replace(/\/(index\.html)?$/, '') : null;
})();

async function fakeFetch(url) {
  const rel = url.split('?')[0];
  if (REMOTE) {
    const r = await fetch(REMOTE + '/' + rel);
    if (!r.ok) return { ok: false, status: r.status };
    const buf = Buffer.from(await r.arrayBuffer());
    return {
      ok: true, status: r.status,
      json: async () => JSON.parse(buf.toString('utf8')),
      arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
    };
  }
  const p = path.join(DIR, rel);
  if (!fs.existsSync(p)) return { ok: false, status: 404 };
  const buf = fs.readFileSync(p);
  return {
    ok: true, status: 200,
    json: async () => JSON.parse(buf.toString('utf8')),
    arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
  };
}

const sandbox = {
  console, setTimeout, clearTimeout, setInterval, clearInterval,
  fetch: fakeFetch, L, Plotly, Math, JSON, Object, Array, Number, String,
  Uint16Array, Int16Array, Float32Array, Uint8ClampedArray, Promise, Error,
  isNaN, parseInt, parseFloat, Date,
  window: { devicePixelRatio: 1 },
  document: { getElementById: getEl, createElement: () => makeEl('canvas'),
              activeElement: null, body: makeEl('body') },
};
sandbox.globalThis = sandbox;

async function loadHtml() {
  if (!REMOTE) return fs.readFileSync(HTML, 'utf8');
  const r = await fetch(REMOTE + '/index.html');
  if (!r.ok) throw new Error('index.html -> HTTP ' + r.status);
  return r.text();
}

(async () => {
const html = await loadHtml();
const code = html.match(/<script>([\s\S]*?)<\/script>/g).pop()
                 .replace(/^<script>/, '').replace(/<\/script>$/, '');

vm.createContext(sandbox);
try {
  vm.runInContext(code, sandbox, { filename: 'portal.js' });
} catch (e) {
  errors.push('eval: ' + e.message);
}

setTimeout(() => {
  const status = getEl('ld-status').textContent;
  if (/^Failed/.test(status)) errors.push('loadAll: ' + status);

  const drive = (label, fn) => { try { fn(); } catch (e) { errors.push(label + ': ' + e.message); } };

  drive('seek', () => sandbox.seek(200));
  drive('toggleLayer hwav', () => sandbox.toggleLayer('hwav'));
  drive('onCmap wl->balance', () => sandbox.onCmap('wl', 'balance'));
  drive('onCmap hwav->viridis', () => sandbox.onCmap('hwav', 'viridis'));
  drive('onMode wl->frame', () => sandbox.onMode('wl', 'frame'));
  drive('onMode wl->anom', () => sandbox.onMode('wl', 'anom'));
  drive('onMode wl->view', () => sandbox.onMode('wl', 'view'));
  drive('onScale vel', () => sandbox.onScale('vel', 300));
  drive('resetScale vel', () => sandbox.resetScale('vel'));
  drive('zoom to fine', () => { zoom = 14; mapInstance.fire('zoomend'); });
  drive('seek at fine', () => sandbox.seek(210));
  drive('offshore currents survive the zoom', () => {
    const n = liveVel();
    if (n < 2) throw new Error('expected coarse + fine velocity layers, got ' + n);
  });
  drive('moveend', () => mapInstance.fire('moveend'));
  drive('toggleSta', () => sandbox.toggleSta());
  drive('openSta BocaNord', () => sandbox.openSta('BocaNord'));
  drive('seek with modal open', () => sandbox.seek(215));
  drive('closeSta', () => sandbox.closeSta());
  drive('basemap -> light', () => sandbox.toggleBasemap());
  drive('seek on light', () => sandbox.seek(218));
  drive('basemap -> dark', () => sandbox.toggleBasemap());
  drive('zoom back to coarse', () => { zoom = 10; mapInstance.fire('zoomend'); });
  // Regression: the readout used to read the coarse layer's own grid, which is
  // punched out under the fine layer, so it said "No data" over the lagoon --
  // the one place the user most wants a number.
  drive('readout over the lagoon', () => {
    zoom = 14; mapInstance.fire('zoomend');
    sandbox.updateReadout({ latlng: { lat: 37.870, lng: 12.460 } });
    const el = getEl('vel-readout');
    if (el.style.display === 'none') throw new Error('hidden over the lagoon');
    if (!/m\/s/.test(el.innerHTML)) throw new Error('empty: ' + el.innerHTML);
    if (!/45 m/.test(el.innerHTML)) throw new Error('not sampling the fine grid: ' + el.innerHTML);
  });
  drive('readout offshore', () => {
    sandbox.updateReadout({ latlng: { lat: 37.95, lng: 12.05 } });
    const el = getEl('vel-readout');
    if (el.style.display === 'none') throw new Error('hidden offshore');
    if (!/270 m/.test(el.innerHTML)) throw new Error('not sampling the coarse grid: ' + el.innerHTML);
  });
  drive('readout off-domain', () => {
    sandbox.updateReadout({ latlng: { lat: 40.0, lng: 10.0 } });
    if (getEl('vel-readout').style.display !== 'none') throw new Error('should be hidden outside the domain');
  });

  drive('fine velocity layer released', () => {
    zoom = 10; mapInstance.fire('zoomend');   // self-contained: earlier cases zoom around
    sandbox.seek(212);
    const n = liveVel();
    if (n !== 1) throw new Error('expected the coarse layer alone, got ' + n);
  });
  drive('toggleLayer vel off', () => sandbox.toggleLayer('vel'));
  drive('toggleLayer vel on', () => sandbox.toggleLayer('vel'));

  // Regression: hiding a field layer and showing it again must put pixels back.
  for (const key of ['wl', 'hwav']) {
    drive('hide/show ' + key, () => {
      sandbox.toggleLayer(key);                       // off
      if (attachedCount() === 0 && key === 'wl') { /* fine, wl may be alone */ }
      const before = attachedCount();
      sandbox.toggleLayer(key);                       // back on
      const after = attachedCount();
      if (after <= before) {
        throw new Error(key + ' did not re-attach (attached ' + before + ' -> ' + after + ')');
      }
      const paintedBefore = overlays.reduce((s, o) => s + o.painted, 0);
      sandbox.seek(220);
      const paintedAfter = overlays.reduce((s, o) => s + o.painted, 0);
      if (paintedAfter <= paintedBefore) throw new Error(key + ' re-shown but never repainted');
    });
  }

  if (errors.length) {
    console.error('\nFAIL (' + errors.length + ')');
    errors.forEach(e => console.error('  - ' + e));
    process.exit(1);
  }
  const meta = JSON.parse(fs.readFileSync(path.join(DIR, 'data', 'meta.json'), 'utf8'));
  console.log('\nPASS (' + (REMOTE || 'local files') + ')'
    + '  status=' + JSON.stringify(status)
    + '  source=' + meta.source
    + '  grids=' + Object.entries(meta.grids)
        .map(([k, v]) => k + ' ' + v.nx + 'x' + v.ny).join(', ')
    + '  cmaps=' + Object.keys(meta.cmaps).length);
}, REMOTE ? 40000 : 2500);
})().catch(e => { console.error('FAIL: ' + e.message); process.exit(1); });
