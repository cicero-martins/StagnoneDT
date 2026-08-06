"""Where does the transport difference between ensemble members live?

The drifter metrics show one member (vr) advecting particles roughly the right
distance (path ratio 0.96) while the other four fall 20-25% short. The bed-level
diagnostic ruled out the final bed state as the cause. By elimination the
difference has to be in the velocity field the particles actually see, which is
the surface layer.

Three views:

  (a) distribution of surface speed over the lagoon, all members. Asks whether
      vr is simply faster everywhere.
  (b) mean speed along each member's OWN simulated trajectory, against the
      observed drifter speed. Sampling the field at the OBSERVED positions was
      tried first and is misleading: it says vr is the SLOWEST of the five
      (0.85x nodm) while its particles travel furthest. The particles are not
      where the observations were, so the speed that sets path length is the
      one along the simulated path.
  (c) map of the mean speed difference between vr and its fixed-bed
      counterpart, to see whether any difference is basin-wide or local.

Four of the five members are drawn in grey and vr in colour, because the
finding is that one member separates from a cluster of four, and that is what
the encoding should say.

Which layer this is, and why it is the right one. Every regrid takes a SINGLE
layer, isel(layer, -1), not a column average. The map.nc carries no sigma
coordinate to consult, so the convention was checked physically: mean speed
rises monotonically from 0.247 m/s at index 0 to 0.415 m/s at index 9, which is
bed friction at the bottom and wind-driven flow at the top. Index -1 is
therefore the surface, which is what surface drifters ride. Both regrid code
paths select the layer the same way, and the empirical check is that nowaves
(server path, 0.118 m/s along track) sits with nodm (local dfm_tools path,
0.121), which a layer inversion in either path would have broken.

That vertical shear, a factor of 1.7 across a sub-metre mean depth, is itself
the argument for running this basin in 3D rather than depth-averaged.

Note on file sizes: the vr and nodm_vr regrids are uncompressed (82 MB) while
the others use zlib (46 MB). Dimensions, window and 30-minute sampling are
identical across all five, so this is storage, not a difference in content.

Output: figures/surface_speed_ensemble.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
MODEL = ROOT / 'model' / 'dflowfm_v04AE_vr'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
LAND = '#e7e6e1'
LAND_EDGE = '#b9b7ae'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
BASE = '#9a9892'          # the four baseline members
ACCENT = '#4a3aa7'        # vr, the member that separates

MEMBERS = [('nowaves', 'v04AE_nowaves'), ('nodm', 'v04AE_nodm'),
           ('nodm_vr', 'v04AE_nodm_vr'), ('bl', 'v04AE'), ('vr', 'v04AE_vr')]
LAGOON = dict(lon=(12.425, 12.487), lat=(37.820, 37.910))
ASPECT = 1.0 / np.cos(np.radians(37.87))

try:
    import cmocean
    DIV = cmocean.cm.balance
except ImportError:
    DIV = plt.get_cmap('RdBu_r')


def parse_ldb(path):
    polys = []
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith('*')]
    i = 0
    while i < len(lines):
        i += 1
        if i >= len(lines):
            break
        try:
            npts = int(lines[i].split()[0])
        except (ValueError, IndexError):
            break
        i += 1
        polys.append(np.array([list(map(float, lines[i + k].split()[:2]))
                               for k in range(npts)]))
        i += npts
    return polys


def track_mean_speeds():
    """Mean speed along the observed track and along each member's own
    simulated track, restricted to the scored window."""
    def hav(lo1, la1, lo2, la2):
        R = 6371000.0
        p1, p2 = np.radians(la1), np.radians(la2)
        dp = np.radians(la2 - la1)
        dl = np.radians(lo2 - lo1)
        a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        return 2 * R * np.arcsin(np.sqrt(a))

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    vo = []
    for _, g in obs.groupby(['deploy', 'source']):
        g = g.sort_values('time')
        d = hav(g['lon'].values[:-1], g['lat'].values[:-1],
                g['lon'].values[1:], g['lat'].values[1:]).sum()
        dt = (g['time'].iloc[-1] - g['time'].iloc[0]).total_seconds()
        if dt > 0:
            vo.append(d / dt)
    v_obs = float(np.mean(vo))

    v_sim = {}
    for key, tag in MEMBERS:
        sim = pd.read_csv(PROC / f'drifter_sim_{tag}.csv', parse_dates=['time'])
        vs = []
        for (dp, did), g in sim.groupby(['deploy', 'drifter_id']):
            o = obs[(obs['deploy'] == dp) & (obs['source'] == did)]
            if o.empty:
                continue
            g = g[(g['time'] >= o['time'].min()) &
                  (g['time'] <= o['time'].max())].sort_values('time')
            if len(g) < 2:
                continue
            d = hav(g['lon'].values[:-1], g['lat'].values[:-1],
                    g['lon'].values[1:], g['lat'].values[1:]).sum()
            dt = (g['time'].iloc[-1] - g['time'].iloc[0]).total_seconds()
            if dt > 0:
                vs.append(d / dt)
        v_sim[key] = float(np.mean(vs))
    return v_obs, v_sim


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})

    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    lagoon_speed, track_speed, means = {}, {}, {}

    for key, tag in MEMBERS:
        ds = xr.open_dataset(PROC / f'{tag}_surface_current.nc')
        spd = np.hypot(ds['x_sea_water_velocity'], ds['y_sea_water_velocity'])

        sub = spd.sel(lon=slice(*LAGOON['lon']), lat=slice(*LAGOON['lat']))
        v = sub.values.ravel()
        lagoon_speed[key] = v[np.isfinite(v)]
        means[key] = sub.mean(dim='time')

        # speed at the observed drifter positions and times
        t0 = pd.Timestamp(ds.time.values[0])
        t1 = pd.Timestamp(ds.time.values[-1])
        o = obs[(obs['time'] >= t0) & (obs['time'] <= t1)]
        s = spd.interp(time=xr.DataArray(o['time'].values, dims='pt'),
                       lat=xr.DataArray(o['lat'].values, dims='pt'),
                       lon=xr.DataArray(o['lon'].values, dims='pt'))
        sv = s.values
        track_speed[key] = sv[np.isfinite(sv)]
        ds.close()
        print(f'{key:9s} lagoon mean {lagoon_speed[key].mean():.4f} m/s | '
              f'along tracks mean {track_speed[key].mean():.4f} m/s '
              f'(n={len(track_speed[key])})')

    print('\n=== along-track speed relative to nodm ===')
    ref = track_speed['nodm'].mean()
    for key, _ in MEMBERS:
        print(f'  {key:9s} {track_speed[key].mean() / ref:5.2f}x')

    polys = parse_ldb(MODEL / 'sicily2.ldb') + parse_ldb(MODEL / 'Stagnone_dxy01_15m.ldb')

    fig = plt.figure(figsize=(11.0, 4.5), dpi=300)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.15, 1.0], wspace=0.30,
                          left=0.06, right=0.97, top=0.88, bottom=0.16)
    fig.patch.set_facecolor(SURFACE)

    def ecdf(ax, data, title, xlabel):
        for key, _ in MEMBERS:
            v = np.sort(data[key])
            y = np.arange(1, len(v) + 1) / len(v)
            step = max(1, len(v) // 4000)
            is_vr = key == 'vr'
            ax.plot(v[::step], y[::step], '-',
                    color=ACCENT if is_vr else BASE,
                    lw=2.0 if is_vr else 1.2,
                    alpha=1.0 if is_vr else 0.75,
                    zorder=4 if is_vr else 3)
        ax.set_xlabel(xlabel, fontsize=8.5, color=MUTED)
        ax.set_ylabel('Cumulative fraction', fontsize=8.5, color=MUTED)
        ax.set_title(title, loc='left', fontsize=9.5, color=INK, pad=7)
        ax.set_ylim(0, 1)
        style(ax)

    ax1 = fig.add_subplot(gs[0, 0])
    ecdf(ax1, lagoon_speed, '(a) Surface speed over the lagoon',
         'Speed (m s$^{-1}$)')
    ax1.set_xlim(0, np.percentile(lagoon_speed['vr'], 99.5))

    ax2 = fig.add_subplot(gs[0, 1])
    v_obs, v_sim = track_mean_speeds()
    keys = [k for k, _ in MEMBERS]
    ys = np.arange(len(keys))[::-1]
    ax2.axvline(v_obs, color=INK, lw=1.4, ls='--', zorder=2)
    ax2.text(v_obs, len(keys) - 0.35, ' observed', fontsize=7.5, color=INK,
             va='center', ha='left')
    for y, k in zip(ys, keys):
        is_vr = k == 'vr'
        ax2.plot([0, v_sim[k]], [y, y], '-',
                 color=ACCENT if is_vr else BASE,
                 lw=3.0 if is_vr else 2.0, alpha=1.0 if is_vr else 0.7, zorder=3)
        ax2.plot([v_sim[k]], [y], 'o', ms=8, mfc=ACCENT if is_vr else BASE,
                 mec='white', mew=1.2, zorder=4)
        ax2.text(v_sim[k] + 0.004, y, f'{v_sim[k] / v_obs:.2f}x', fontsize=7.5,
                 color=INK if is_vr else MUTED, va='center', ha='left')
    ax2.set_yticks(ys)
    ax2.set_yticklabels(keys, fontsize=8.5)
    ax2.set_xlim(0, max(v_sim.values()) * 1.22)
    ax2.set_ylim(-0.6, len(keys) - 0.4)
    ax2.set_xlabel('Mean speed along own track (m s$^{-1}$)', fontsize=8.5,
                   color=MUTED)
    ax2.set_ylabel('')
    ax2.set_title('(b) Speed the particles actually travelled at', loc='left',
                  fontsize=9.5, color=INK, pad=7)
    style(ax2)

    ax3 = fig.add_subplot(gs[0, 2])
    diff = (means['vr'] - means['nodm_vr'])
    lim = float(np.round(np.nanpercentile(np.abs(diff.values), 98), 3))
    for poly in polys:
        ax3.fill(poly[:, 0], poly[:, 1], facecolor=LAND, edgecolor=LAND_EDGE,
                 lw=0.4, zorder=3)
    pc = ax3.pcolormesh(diff.lon, diff.lat, diff.values, cmap=DIV,
                        vmin=-lim, vmax=lim, shading='auto', zorder=1,
                        rasterized=True)
    ax3.set_xlim(*LAGOON['lon'])
    ax3.set_ylim(*LAGOON['lat'])
    ax3.set_aspect(ASPECT)
    ax3.set_title('(c) Mean speed, vr $-$ nodm\\_vr', loc='left', fontsize=9.5,
                  color=INK, pad=7)
    ax3.tick_params(colors=MUTED, labelsize=7)
    for lbl in ax3.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_ha('right')
    for sp in ['top', 'right']:
        ax3.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax3.spines[sp].set_color('#c9c7c1')
    cb = fig.colorbar(pc, ax=ax3, orientation='horizontal', fraction=0.05,
                      pad=0.20, extend='both', aspect=22)
    cb.set_label('$\\Delta$ speed (m s$^{-1}$)', fontsize=8, color=MUTED)
    cb.ax.tick_params(labelsize=7, colors=MUTED)
    cb.outline.set_edgecolor(LAND_EDGE)

    for ext in ('png', 'pdf'):
        p = FIG / f'surface_speed_ensemble.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#c9c7c1')


if __name__ == '__main__':
    main()
