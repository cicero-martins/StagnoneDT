"""Video of the particle view of the velocity sections, for a presentation.

The particle page (build_wetwise_sections_particles.py) is opened in headless
Edge with ?record, which stops its own clock and hides its controls.  The page
is then driven over the DevTools protocol one video frame at a time, each frame
advancing the particles by a fixed model time step, and every frame is captured
and encoded with ffmpeg.  Rendering speed therefore does not affect the timing
of the result.

The sequence follows SHOTS.  It opens on the top view with every layer on,
moves to the perspective view, isolates the north-south section, then the
east-west section with the camera closing in on it, and returns to the
perspective view with every layer on.

Usage
    python scripts/record_wetwise_sections_video.py --member WV-
        [--out docs/dsd2026/assets/sections_3d_WV-.mp4] [--fps 30]
        [--rate 3600] [--size 1920x1080] [--no-captions] [--frames-only]
"""
import argparse
import base64
import functools
import json
import shutil
import subprocess
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import imageio_ffmpeg
import websocket

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / 'outputs' / 'wetwise_tab'
EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
HTTP_PORT, CDP_PORT = 8131, 9333

# The page's presets aim above the box centre to leave room for its controls;
# the video has none, so the perspective view is centred on the box.
UP = {'x': 0, 'y': 0, 'z': 1}
ZOOM, CENTER = 0.68, {'x': 0, 'y': 0, 'z': 0.0}
TOP = {'eye': {'x': 0, 'y': -0.001, 'z': 1.25}, 'center': {'x': 0, 'y': 0, 'z': 0},
       'up': {'x': 0, 'y': 1, 'z': 0}}
PERSP = {'eye': {'x': 0.95 * ZOOM, 'y': -0.40 * ZOOM, 'z': 0.45 * ZOOM},
         'center': CENTER, 'up': UP}
ALL = {'surface': True, 'ns_axis': True, 'ew_centre': True, 'coast': True}
NS = {'surface': False, 'ns_axis': True, 'ew_centre': False, 'coast': True}
EW = {'surface': False, 'ns_axis': False, 'ew_centre': True, 'coast': True}

# (seconds, camera at the end of the shot or None to hold, layers set at its
# start or None to keep, caption)
SHOTS = [
    (6.0, None, ALL, 'Surface currents, top view'),
    (3.0, PERSP, None, 'Surface and vertical sections'),
    (2.0, None, None, None),
    (6.0, None, NS, 'North\u2013south section'),
    (1.0, None, EW, 'East\u2013west section'),
    (3.0, 'EW_CLOSE', None, None),
    (6.0, None, None, None),
    (3.0, PERSP, ALL, 'Surface and vertical sections'),
    (4.0, None, None, None),
]


def ew_close(meta):
    """Camera looking north at the middle of the east-west section."""
    e, a, zr = meta['extent'], meta['aspect'], meta['zrange']
    s = meta['sections']['ew_centre']
    xm = (min(s['x']) + max(s['x'])) / 2
    ym = sum(s['y']) / len(s['y'])
    # Plotly places the scene box symmetrically about the origin with the
    # sides of the aspect ratio, so a data point maps linearly onto it
    nx = ((xm - e[0]) / (e[1] - e[0]) - 0.5) * a['x']
    ny = ((ym - e[2]) / (e[3] - e[2]) - 0.5) * a['y']
    nz = ((-0.6 - zr[0]) / (zr[1] - zr[0]) - 0.5) * a['z']
    c = {'x': nx, 'y': ny, 'z': nz}
    return {'eye': {'x': nx + 0.02, 'y': ny - 0.26, 'z': nz + 0.06}, 'center': c, 'up': UP}


def ease(t):
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return {k: {c: a[k][c] + (b[k][c] - a[k][c]) * t for c in 'xyz'} for k in a}


class CDP:
    """Minimal DevTools client over one page websocket."""

    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=600, suppress_origin=True)
        self.n = 0

    def call(self, method, timeout=600, **params):
        self.n += 1
        self.ws.settimeout(timeout)
        self.ws.send(json.dumps({'id': self.n, 'method': method, 'params': params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == self.n:
                if 'error' in m:
                    raise RuntimeError(f'{method}: {m["error"]}')
                return m.get('result', {})

    def js(self, expr):
        r = self.call('Runtime.evaluate', expression=expr, awaitPromise=True,
                      returnByValue=True)
        if 'exceptionDetails' in r:
            raise RuntimeError(r['exceptionDetails'].get('exception', {})
                               .get('description', r['exceptionDetails']))
        return r['result'].get('value')


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def frame(cdp, dt, cam):
    """One frame, with a time limit so that a stalled renderer fails loudly."""
    if cdp.js('document.hidden'):
        cdp.call('Page.bringToFront')
    r = cdp.js(f"Promise.race([REC.frame({dt}, {json.dumps(cam)}).then(() => 'ok'), "
               f"new Promise(r => setTimeout(() => r('stall'), 30000))])")
    if r != 'ok':
        raise RuntimeError(f"renderer stalled at {cdp.js('window.__stage')}, "
                           f"frame {cdp.js('shown')}, hidden {cdp.js('document.hidden')}")


def grab(cdp):
    """Screenshot of the page.  Headless Edge now and then stops delivering
    compositor frames and the capture never returns, so it is retried after
    bringing the page to the front; a late reply to the abandoned request
    carries an old id and is skipped."""
    for attempt in range(5):
        try:
            return cdp.call('Page.captureScreenshot', timeout=20, format='png')['data']
        except websocket.WebSocketTimeoutException:
            print('  capture timed out, retrying', flush=True)
            cdp.call('Page.bringToFront', timeout=20)
            cdp.js('REC.frame(0, null, true)')
    raise RuntimeError('screenshot failed five times')


def kill_edge(prof):
    """Stops every Edge process started on this profile.  Terminating the
    launched process leaves the browser it spawned alive, holding the
    debugging port and the profile for the next run."""
    tag = str(prof).replace("'", "''")
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
                    f"Where-Object {{ $_.CommandLine -like '*{tag}*' }} | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def serve(root):
    h = functools.partial(Quiet, directory=str(root))
    srv = ThreadingHTTPServer(('127.0.0.1', HTTP_PORT), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--member', default='WV-')
    ap.add_argument('--out', default=None)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--rate', type=float, default=3600.0,
                    help='model seconds per video second')
    ap.add_argument('--start', type=int, default=0, help='stored instant to start from')
    ap.add_argument('--trail', type=int, default=24)
    ap.add_argument('--size', default='1920x1080')
    ap.add_argument('--no-captions', action='store_true')
    ap.add_argument('--frames-only', action='store_true',
                    help='stop after the first frame of each shot, as PNGs')
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split('x'))
    out = Path(a.out) if a.out else ROOT / 'docs' / 'dsd2026' / 'assets' / f'sections_3d_{a.member}.mp4'
    frames = out.with_suffix('')
    frames = frames.parent / (frames.name + '_frames')

    prof = frames / '_edge'
    kill_edge(prof)
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True, exist_ok=True)
    srv = serve(TAB / f'sections_{a.member}')
    edge = subprocess.Popen([str(EDGE), '--headless=new', '--enable-unsafe-swiftshader',
                             '--use-angle=swiftshader', f'--window-size={w},{h}',
                             '--hide-scrollbars', f'--remote-debugging-port={CDP_PORT}',
                             # a page Chromium deems hidden stops requestAnimationFrame,
                             # and with it the Plotly render loop
                             '--disable-renderer-backgrounding',
                             '--disable-background-timer-throttling',
                             '--disable-backgrounding-occluded-windows',
                             f'--user-data-dir={prof}', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                pages = json.load(urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/list'))
                page = next(p for p in pages if p['type'] == 'page')
                break
            except Exception:
                time.sleep(0.5)
        cdp = CDP(page['webSocketDebuggerUrl'])
        cdp.call('Emulation.setDeviceMetricsOverride', width=w, height=h,
                 deviceScaleFactor=1, mobile=False)
        cdp.call('Emulation.setFocusEmulationEnabled', enabled=True)
        cdp.call('Page.enable')
        cdp.call('Page.bringToFront')
        cdp.call('Page.navigate', url=f'http://127.0.0.1:{HTTP_PORT}/particles.html?record')
        t0 = time.time()
        while not cdp.js('!!window.REC'):
            if time.time() - t0 > 300:
                raise TimeoutError('page did not reach record mode')
            time.sleep(1)
        meta = cdp.js('REC.D')
        cams = {'EW_CLOSE': ew_close(meta)}
        cdp.js(f'REC.set({json.dumps({"trail": a.trail, "tc": a.start, "lw": 1.5})})')

        dt = a.rate / a.fps
        # run the particles in for a moment, so the first frame shows trails
        cdp.js(f'REC.set({json.dumps({"layers": ALL, "caption": ""})})')
        cdp.js(f'(async () => {{ for (let k = 0; k < {a.trail}; k++) await REC.frame({dt}, {json.dumps(TOP)}, true); }})()')

        cam, k = dict(TOP), 0
        for secs, target, layers, cap in SHOTS:
            setting = {}
            if layers is not None:
                setting['layers'] = layers
            if cap is not None and not a.no_captions:
                setting['caption'] = cap
            if setting:
                cdp.js(f'REC.set({json.dumps(setting)})')
            n = round(secs * a.fps)
            start = cam
            end = cams[target] if isinstance(target, str) else (target or cam)
            for j in range(n):
                cam = mix(start, end, ease((j + 1) / n)) if target else start
                frame(cdp, dt, cam)
                png = grab(cdp)
                (frames / f'{k:05d}.png').write_bytes(base64.b64decode(png))
                k += 1
                if a.frames_only:
                    break
            cam = end
            print(f'  shot done, {k} frames', flush=True)
    finally:
        edge.terminate()
        kill_edge(prof)
        srv.shutdown()
    shutil.rmtree(prof, ignore_errors=True)
    if a.frames_only:
        print(f'frames in {frames}')
        return
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
                    '-framerate', str(a.fps), '-i', str(frames / '%05d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                    '-movflags', '+faststart', str(out)], check=True)
    shutil.rmtree(frames)
    print(f'wrote {out}  ({out.stat().st_size / 1e6:.1f} MB, {k} frames, '
          f'{k / a.fps:.0f} s, {a.rate / 3600:g} h of flow per s)')


if __name__ == '__main__':
    main()
