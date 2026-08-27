"""The rocky-shore roughness treatment: where it is applied, and what it costs.

On Baptist 154 the wave-coupled fixed-bed member aborts at the southwest shore
of Marettimo. Giving those links a rocky-shore Manning of 0.05 instead of the
uniform 0.023 lets the member run: from an identical day-3 restart, the
untreated run aborts at 18:00:58 on the velocity cap and the treated one
completes the full 24 hours with no cap hits at all.

The question this figure answers is the other one, whether the treatment is
free at the lagoon 29 km away. It is not. The Egadi sector, where the change is
made, settles at a bounded 4 to 7 mm. The lagoon keeps climbing through the
window, which is the signature of a perturbation propagating rather than a
local offset, and it has not levelled off by hour 18.

Panel (a) is the treated links. Panels (b) to (d) are the three lagoon gauges,
observations against both runs.

Read the station panels as an effect measurement, not a skill assessment: 24
hours starting from a restart is far too short for the latter, and the two runs
share only the 18 hours before the untreated one aborts.

    python scripts/plot_shore_roughness_effect.py
"""
from pathlib import Path
import os

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.environ.get('CLAUDE_SCRATCH', ROOT / 'data' / 'processed'))
NPZ = SCRATCH / 'failregion.npz'
ARL = ROOT / 'data/processed/planet2023_rf_v3/stagnone_trachytopes_v3_shore.arl'
HIS_ON = ROOT / 'model/_trt_test_shore/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000_his.nc'
HIS_OFF = ROOT / 'model/dflowfm_v04AE_nodm_vr_154_chain/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000_his.nc'
PROC = ROOT / 'data' / 'processed'
OUT = ROOT / 'figures' / 'shore_roughness_effect.png'

STATIONS = [('BocaNord', 'wl_BocaNord_10min_UTC.csv'),
            ('BocaSud', 'wl_BocaSud_10min_UTC.csv'),
            ('AltaVilaEst', 'wl_AltavilaEst_10min_UTC.csv')]
SHORE_CLASS = 5

# Both runs start from the same day-3 restart and both ring for the first few
# hours, most visibly at BocaNord. That ringing is the restart adjustment, not
# the treatment, and it is common to the pair, so differences taken across it
# say nothing about the roughness. Everything quantitative is measured after it.
SETTLE_H = 6

# Validated with the dataviz palette checker: adjacent CVD dE 21.6 (protan),
# normal-vision 30.4, both clear of the floors.
OFF, ON = '#1f77b4', '#d95f02'
INK, MUTED, GRID, OBS = '#1c1c1c', '#6b6b6b', '#dcdcdc', '#4a4a4a'


def read_shore_links():
    pts = []
    for line in ARL.read_text(errors='ignore').splitlines():
        if line.lstrip().startswith('#'):
            continue
        s = line.split()
        if len(s) >= 5 and int(s[3]) == SHORE_CLASS:
            pts.append((float(s[0]), float(s[1])))
    return np.array(pts)


def read_his(path):
    ds = xr.open_dataset(path)
    names = [b.tobytes().decode('utf-8', 'ignore').strip() if isinstance(b, bytes)
             else str(b).strip() for b in ds['station_name'].values]
    wl = ds['waterlevel'].values
    t = pd.to_datetime(ds.time.values)
    ds.close()
    out = {}
    for st, _ in STATIONS:
        hit = [i for i, n in enumerate(names) if n.replace(' ', '') == st]
        if hit:
            out[st] = pd.Series(wl[:, hit[0]], index=t)
    return out


def main():
    d = np.load(NPZ)
    x, y, bl = d['x'], d['y'], d['bl']
    shore = read_shore_links()
    on, off = read_his(HIS_ON), read_his(HIS_OFF)

    fig = plt.figure(figsize=(14.6, 6.4))
    gs = fig.add_gridspec(3, 2, width_ratios=[1.0, 1.35], hspace=0.55,
                          wspace=0.20)

    # (a) the treated links
    ax = fig.add_subplot(gs[:, 0])
    m = (np.abs(x - 12.055) < 0.075) & (np.abs(y - 37.972) < 0.055)
    sc = ax.scatter(x[m], y[m], c=bl[m], s=30, cmap='terrain',
                    norm=TwoSlopeNorm(vcenter=0, vmin=-60, vmax=15),
                    linewidths=0, zorder=2)
    ax.scatter(shore[:, 0], shore[:, 1], s=3.0, c=ON, linewidths=0, zorder=4,
               label=f'{len(shore)} links at n = 0.05')
    cb = plt.colorbar(sc, ax=ax, fraction=0.043, pad=0.13)
    cb.set_label('bed level (m)', fontsize=8, color=MUTED)
    cb.ax.tick_params(labelsize=7, colors=MUTED)
    ax.legend(loc='upper left', fontsize=8, frameon=False, markerscale=3,
              bbox_to_anchor=(0, -0.10))
    ax.set_title('(a)  treated links: Marettimo shore fringe,\n'
                 'bed level between −15 and +1 m',
                 fontsize=9.5, color=INK, loc='left')
    ax.set_aspect(1 / np.cos(np.deg2rad(37.97)))
    ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    ax.tick_params(labelsize=7, colors=MUTED)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.set_xlabel('lon', fontsize=8, color=MUTED)
    ax.set_ylabel('lat', fontsize=8, color=MUTED)

    # (b)-(d) the lagoon gauges
    for k, (st, fn) in enumerate(STATIONS):
        ax = fig.add_subplot(gs[k, 1])
        o = pd.read_csv(PROC / fn)
        tc = [c for c in o.columns if 'time' in c.lower()][0]
        vc = [c for c in o.columns if c != tc][0]
        o[tc] = pd.to_datetime(o[tc])
        o = o.set_index(tc)[vc]
        o = o[(o.index >= on[st].index[0]) & (o.index <= on[st].index[-1])]

        t0 = on[st].index[0]
        settle = t0 + pd.Timedelta(hours=SETTLE_H)
        ax.axvspan(t0, settle, color='#f0efe9', zorder=0)

        ax.plot(o.index, o.values, lw=1.6, color=OBS, alpha=0.55,
                label='observed', zorder=2)
        # The untreated run is drawn thicker and underneath: the two are almost
        # coincident, so a thin line on top would simply hide it.
        ax.plot(off[st].index, off[st].values, lw=2.6, color=OFF, alpha=0.85,
                label='n = 0.023 (aborts 18:01)', zorder=3)
        ax.plot(on[st].index, on[st].values, lw=1.1, color=ON,
                label='n = 0.05 shore', zorder=4)

        common = off[st].index.intersection(on[st].index)
        post = common[common >= settle]
        dmax = np.abs(on[st][post] - off[st][post]).max() * 1000
        ax.text(0.985, 0.06, f'max |diff| after h+{SETTLE_H}: {dmax:.1f} mm',
                transform=ax.transAxes, ha='right', fontsize=7.5, color=ON)
        if k == 0:
            ax.text(t0 + pd.Timedelta(hours=SETTLE_H / 2),
                    ax.get_ylim()[0], ' restart ringing', fontsize=7,
                    color=MUTED, va='bottom', ha='center')
        ax.set_title(f'({"bcd"[k]})  {st}', fontsize=9.5, color=INK, loc='left')
        ax.set_ylabel('WL (m)', fontsize=8, color=MUTED)
        ax.tick_params(labelsize=7, colors=MUTED)
        ax.grid(True, color=GRID, lw=0.5, alpha=0.6)
        ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        for s in ('left', 'bottom'):
            ax.spines[s].set_color(GRID)
        if k == 0:
            ax.legend(fontsize=7.5, frameon=False, ncol=3, loc='upper left',
                      bbox_to_anchor=(0, 1.55))
        if k < 2:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel('2025-07-04 (UTC)', fontsize=8, color=MUTED)

    fig.suptitle('Rocky-shore roughness at Marettimo: what it fixes and what it '
                 'moves', fontsize=11, color=INK, x=0.007, ha='left', y=0.985)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, bbox_inches='tight', facecolor='white')
    print(f'wrote {OUT}')

    print(f'\ntreated links: {len(shore)}   '
          f'lon {shore[:, 0].min():.4f}..{shore[:, 0].max():.4f}   '
          f'lat {shore[:, 1].min():.4f}..{shore[:, 1].max():.4f}')
    print(f"\npost-settle window only (from h+{SETTLE_H}):")
    print(f"{'station':13s} {'RMSE off':>9} {'RMSE on':>9} {'bias off':>9} "
          f"{'bias on':>9} {'mean|diff|':>11} {'max|diff|':>10}")
    for st, fn in STATIONS:
        o = pd.read_csv(PROC / fn)
        tc = [c for c in o.columns if 'time' in c.lower()][0]
        vc = [c for c in o.columns if c != tc][0]
        o[tc] = pd.to_datetime(o[tc])
        o = o.set_index(tc)[vc]
        common = off[st].index.intersection(on[st].index)
        common = common[common >= on[st].index[0] + pd.Timedelta(hours=SETTLE_H)]
        oo = o.reindex(common, method='nearest',
                       tolerance=pd.Timedelta('10min'))
        ok = np.isfinite(oo.values)
        a, b = on[st][common].values[ok], off[st][common].values[ok]
        r = oo.values[ok]
        print(f'{st:13s} {np.sqrt(np.mean((b - r) ** 2)):9.4f} '
              f'{np.sqrt(np.mean((a - r) ** 2)):9.4f} '
              f'{np.mean(b - r):9.4f} {np.mean(a - r):9.4f} '
              f'{np.mean(np.abs(a - b)) * 1000:10.3f}mm '
              f'{np.max(np.abs(a - b)) * 1000:9.2f}mm')
    print(f'\n{len(common)} common steps after settling; the two runs share only '
          f'the 18 h before the untreated one aborts.')
    print('24 h from a restart: an effect measurement, not a skill assessment.')


if __name__ == '__main__':
    main()
