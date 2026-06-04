#!/usr/bin/env python3
"""Generate 6 MP4 videos from a chain forecast run (run on simit-server).

Videos produced in ~/StagnoneDT/chain_videos/:
  wl_full.mp4, wl_lagoon.mp4         — Water Level (mesh2d_s1)
  hwav_full.mp4, hwav_lagoon.mp4     — Significant Wave Height (mesh2d_hwav)
  salinity_full.mp4, salinity_lagoon.mp4  — Surface Salinity (mesh2d_sa1 top layer)

Usage:
  ~/miniconda3/envs/stagnone_extract/bin/python generate_chain_videos.py [run_name]
  e.g.: generate_chain_videos.py d2025-07-20_n2

Colormaps: RdYlBu_r (WL), plasma (Hwav), RdYlGn_r (salinity)
Colorbar: horizontal, at bottom of each frame
Colorscale: 2nd–98th percentile of all timesteps
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use('Agg')
# Set explicit ffmpeg path (conda env may not be in PATH when running via nohup)
_FFMPEG = Path.home() / 'miniconda3' / 'envs' / 'stagnone_extract' / 'bin' / 'ffmpeg'
if _FFMPEG.exists():
    matplotlib.rcParams['animation.ffmpeg_path'] = str(_FFMPEG)
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.animation import FFMpegWriter
from matplotlib.colors import Normalize

# ─── Paths ────────────────────────────────────────────────────────────────────
FORECAST_DIR = Path.home() / 'StagnoneDT' / 'runs' / 'forecast'
RUN_NAME = sys.argv[1] if len(sys.argv) > 1 else 'd2025-07-20_n2'
RUN_DIR  = FORECAST_DIR / RUN_NAME
OUT_DIR  = Path.home() / 'StagnoneDT' / 'chain_videos'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Stagnone zoom bbox
LAGOON_LON = (12.427, 12.4888)
LAGOON_LAT = (37.790, 37.9156)

FPS         = 12
DPI         = 130
FV_THRESH   = 1e35   # DFM fill-value threshold

FIELDS = [
    {'name': 'wl',       'var': 'mesh2d_s1',   'layer': None, 'cmap': 'RdYlBu_r',  'label': 'Water Level (m)',             'phys_min': -3.0,  'phys_max': 3.0},
    {'name': 'hwav',     'var': 'mesh2d_hwav',  'layer': None, 'cmap': 'plasma',    'label': 'Significant Wave Height (m)', 'phys_min':  0.0,  'phys_max': 15.0},
    {'name': 'salinity', 'var': 'mesh2d_sa1',   'layer': -1,   'cmap': 'RdYlGn_r', 'label': 'Surface Salinity (ppt)',      'phys_min':  0.0,  'phys_max': 80.0},
]

# ─── Data loading ─────────────────────────────────────────────────────────────
def load_partitioned(run_dir: Path) -> dict:
    sub = run_dir / 'DFM_OUTPUT_Stagnone_dxy01_15m'
    parts = sorted(sub.glob('*_000?_map.nc'))
    if not parts:
        raise FileNotFoundError(f'No map partitions in {sub}')
    print(f'  {len(parts)} partitions')

    lx, ly = [], []
    ls1, lhwav, lsa1 = [], [], []
    times = None

    for p in parts:
        ds = xr.open_dataset(p, mask_and_scale=False)
        if times is None:
            times = ds.time.values
        lx.append(ds['mesh2d_face_x'].values)
        ly.append(ds['mesh2d_face_y'].values)
        ls1.append(ds['mesh2d_s1'].values)
        lhwav.append(ds['mesh2d_hwav'].values)
        lsa1.append(ds['mesh2d_sa1'].values)
        ds.close()

    return {
        'times':        times,
        'lon':          np.concatenate(lx),
        'lat':          np.concatenate(ly),
        'mesh2d_s1':    np.concatenate(ls1,   axis=1),          # (T, N)
        'mesh2d_hwav':  np.concatenate(lhwav, axis=1),          # (T, N)
        'mesh2d_sa1':   np.concatenate(lsa1,  axis=1),          # (T, N, K)
    }


def clean(arr: np.ndarray, phys_min: float = -np.inf, phys_max: float = np.inf) -> np.ndarray:
    out = arr.astype(np.float32)
    out[np.abs(out) > FV_THRESH] = np.nan
    out[out < phys_min] = np.nan   # catches secondary fill (-999) and dry-cell artifacts
    out[out > phys_max] = np.nan
    return out


def vrange(data: np.ndarray, plo=2, phi=98):
    finite = data[np.isfinite(data)]
    if len(finite) == 0:
        return 0.0, 1.0
    return float(np.percentile(finite, plo)), float(np.percentile(finite, phi))


# ─── Triangulation ────────────────────────────────────────────────────────────
def make_tri(lon: np.ndarray, lat: np.ndarray, edge_pct=97.0) -> mtri.Triangulation:
    """Delaunay triangulation of face centres; mask elongated boundary edges."""
    tri = mtri.Triangulation(lon, lat)
    pts = np.stack([lon, lat], axis=1)
    v = pts[tri.triangles]                             # (M, 3, 2)
    e01 = np.linalg.norm(v[:, 1] - v[:, 0], axis=1)
    e12 = np.linalg.norm(v[:, 2] - v[:, 1], axis=1)
    e20 = np.linalg.norm(v[:, 0] - v[:, 2], axis=1)
    max_edge = np.maximum(e01, np.maximum(e12, e20))
    thresh = np.percentile(max_edge, edge_pct)
    tri.set_mask(max_edge > thresh)
    return tri


# ─── Video generation ─────────────────────────────────────────────────────────
def make_video(lon, lat, times, data, cfg, out_path,
               vmin, vmax, xlim=None, ylim=None):
    """
    data : (T, N) float32 with NaN for missing/dry cells
    xlim, ylim : if set → lagoon zoom view
    """
    # Subset faces for lagoon view
    if xlim is not None:
        mask = ((lon >= xlim[0]) & (lon <= xlim[1]) &
                (lat >= ylim[0]) & (lat <= ylim[1]))
        lon_p  = lon[mask]
        lat_p  = lat[mask]
        data_p = data[:, mask]
        fig_w, fig_h = 9.0, 9.5
    else:
        lon_p  = lon
        lat_p  = lat
        data_p = data
        fig_w, fig_h = 12.0, 8.0

    print(f'    Building triangulation ({len(lon_p)} faces)...', flush=True)
    tri_p = make_tri(lon_p, lat_p)

    # ─ Figure layout ─────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor='#0d1b2a')
    # ax occupies everything except bottom stripe for colorbar
    ax  = fig.add_axes([0.06, 0.13, 0.90, 0.80])
    ax.set_facecolor('#0d1b2a')

    if xlim:
        ax.set_xlim(xlim[0] - 0.002, xlim[1] + 0.002)
        ax.set_ylim(ylim[0] - 0.002, ylim[1] + 0.002)
    else:
        m = 0.03
        ax.set_xlim(lon_p.min() - m, lon_p.max() + m)
        ax.set_ylim(lat_p.min() - m, lat_p.max() + m)

    ax.set_aspect('equal')
    ax.set_xlabel('Longitude', color='#889aaa', fontsize=8)
    ax.set_ylabel('Latitude',  color='#889aaa', fontsize=8)
    ax.tick_params(colors='#889aaa', labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor('#223344')

    # ─ Initial tripcolor ─────────────────────────────────────────────────────
    d0 = data_p[0].copy()
    d0[~np.isfinite(d0)] = vmin
    norm = Normalize(vmin=vmin, vmax=vmax)
    tc = ax.tripcolor(tri_p, d0, cmap=cfg['cmap'], norm=norm, shading='gouraud')

    # ─ Colorbar at bottom ────────────────────────────────────────────────────
    cax = fig.add_axes([0.12, 0.04, 0.76, 0.022])
    cb  = fig.colorbar(tc, cax=cax, orientation='horizontal')
    cb.set_label(cfg['label'], color='#ccdde8', fontsize=9)
    cb.ax.tick_params(colors='#889aaa', labelsize=8)
    cb.outline.set_edgecolor('#334455')

    # ─ Title ─────────────────────────────────────────────────────────────────
    view_tag = ' — Stagnone zoom' if xlim else ' — full domain'
    title = ax.set_title('', color='#ddeeff', fontsize=10, pad=6, fontweight='bold')

    # ─ Animation ─────────────────────────────────────────────────────────────
    writer = FFMpegWriter(fps=FPS, bitrate=3500,
                          extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
    n = len(times)
    with writer.saving(fig, str(out_path), dpi=DPI):
        for i in range(n):
            d = data_p[i].copy()
            d[~np.isfinite(d)] = vmin
            tc.set_array(d)
            t_str = str(times[i])[:16].replace('T', ' ')
            title.set_text(f'{t_str} UTC{view_tag}')
            writer.grab_frame()
            if (i + 1) % 20 == 0 or i == n - 1:
                print(f'    frame {i+1}/{n}', flush=True)

    plt.close(fig)
    mb = out_path.stat().st_size / 1e6
    print(f'  Saved: {out_path.name}  ({mb:.1f} MB)')


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f'Run dir : {RUN_DIR}')
    print(f'Output  : {OUT_DIR}')

    print('\nLoading partitioned map.nc...')
    d = load_partitioned(RUN_DIR)
    lon, lat, times = d['lon'], d['lat'], d['times']
    print(f'  Faces: {len(lon)},  Timesteps: {len(times)}')
    print(f'  Time: {str(times[0])[:16]} -> {str(times[-1])[:16]}')

    for cfg in FIELDS:
        raw = d[cfg['var']]
        if cfg['layer'] is not None:
            raw = raw[:, :, cfg['layer']]   # (T, N, K) -> (T, N)
        data = clean(raw, cfg['phys_min'], cfg['phys_max'])

        vmin, vmax = vrange(data)
        print(f'\n=== {cfg["name"]} : range [{vmin:.3f}, {vmax:.3f}] ===')

        out_full = OUT_DIR / f"{cfg['name']}_full.mp4"
        print(f'  -> {out_full.name}')
        make_video(lon, lat, times, data, cfg, out_full, vmin, vmax)

        out_lagoon = OUT_DIR / f"{cfg['name']}_lagoon.mp4"
        print(f'  -> {out_lagoon.name}')
        make_video(lon, lat, times, data, cfg, out_lagoon, vmin, vmax,
                   xlim=LAGOON_LON, ylim=LAGOON_LAT)

    print('\nAll done!')


if __name__ == '__main__':
    main()
