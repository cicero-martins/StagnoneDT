"""
D-Morph diagnostic for v04AE coupled run, focused on Boca Nord.

User observation: 'Boca Nord parece que fica com várias células quase secas
já depois do primeiro dia (o que é complicado pois o modelo ainda está
instável), o que acontece na vida real mas em uma escala muito mais lenta'.

Goal: quantify how fast the bed at Boca Nord is changing, given:
  - MorFac = 1.0 (no acceleration), so the bed change rate reported IS the
    physical rate
  - MorStt = 1440 min (bed update starts at sim-day 1 — matches user's
    observation that drying appears right after day 1)
  - SedThr = 0.5 m (transport suppressed where h < 0.5 m, intended to be a
    safety knob in shallow water)

Outputs:
  figs/v04AE_dmorph_bocanord.png with 4 panels:
    1. Map of cumulative |Delta bedlevel| over 9 days, full lagoon
    2. Zoom on Boca Nord (BocaNord obs at 12.4572 / 37.9053)
    3. Time series of bedlevel at BocaNord, BocaSud, AltaVilaEst (his.nc)
    4. Time series of waterdepth at the same stations to see drying

  data/processed/v04AE_bed_change_summary.csv with per-station numbers.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
FIG = ROOT / 'figures'
PROC = ROOT / 'data' / 'processed'
FIG.mkdir(parents=True, exist_ok=True)

BOCA_NORD = (12.457240, 37.905274)
BOCA_SUD = (12.449667, 37.842221)
ALTA_VILA = (12.451652, 37.891785)
STATIONS = {'BocaNord': BOCA_NORD, 'BocaSud': BOCA_SUD, 'AltaVilaEst': ALTA_VILA}

LAG_X = (12.42, 12.47)
LAG_Y = (37.81, 37.92)
BN_PAD = 0.008   # ~700 m around Boca Nord


def load_per_partition_bl():
    """Concat bedlevel at first and last map timesteps + face_x/y across 8 parts."""
    xs, ys, bl0, blF, depthF = [], [], [], [], []
    t0 = tF = None
    for p in range(8):
        ds = xr.open_dataset(OUT_DIR / f'Stagnone_dxy01_15m_{p:04d}_map.nc')
        # mesh2d_mor_bl is D-Morph time-evolving bed; mesh2d_flowelem_bl is static.
        bl = ds['mesh2d_mor_bl']  # (time, nFaces)
        i0 = 0
        iF = bl.sizes['time'] - 1
        bl0_p = bl.isel(time=i0).values
        blF_p = bl.isel(time=iF).values
        if t0 is None:
            t0 = ds.time.values[i0]
            tF = ds.time.values[iF]
        # waterdepth at end (surface layer is irrelevant for h; mesh2d_waterdepth is per face)
        if 'mesh2d_waterdepth' in ds.variables:
            wd = ds['mesh2d_waterdepth']
            if 'time' in wd.dims:
                wd_p = wd.isel(time=wd.sizes['time'] - 1).values
            else:
                wd_p = wd.values
        else:
            wd_p = np.full_like(bl0_p, np.nan)
        xs.append(ds['mesh2d_face_x'].values)
        ys.append(ds['mesh2d_face_y'].values)
        bl0.append(bl0_p)
        blF.append(blF_p)
        depthF.append(wd_p)
    return (np.concatenate(xs), np.concatenate(ys),
            np.concatenate(bl0), np.concatenate(blF),
            np.concatenate(depthF), t0, tF)


def load_his_at_station(name):
    """Load waterlevel, bedlevel, waterdepth time series at a named station from his.nc partition 0."""
    his = OUT_DIR / 'Stagnone_dxy01_15m_0000_his.nc'
    ds = xr.open_dataset(his)
    names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
             for s in ds.station_name.values]
    if name not in names:
        # try other partitions
        for p in range(1, 8):
            his_p = OUT_DIR / f'Stagnone_dxy01_15m_{p:04d}_his.nc'
            if not his_p.exists():
                continue
            ds_p = xr.open_dataset(his_p)
            names_p = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
                       for s in ds_p.station_name.values]
            if name in names_p:
                ds = ds_p
                names = names_p
                break
    if name not in names:
        return None
    i = names.index(name)
    out = {}
    out['time'] = pd.to_datetime(ds.time.values)
    for v in ['waterlevel', 'bedlevel']:
        if v in ds.variables:
            arr = ds[v].isel(stations=i).values if 'stations' in ds[v].dims \
                  else ds[v].isel(station=i).values
            out[v] = arr
    # waterdepth not output to his (wrihis_waterdepth=0 in MDU); derive from wl - bl
    if 'waterlevel' in out and 'bedlevel' in out:
        out['waterdepth'] = np.maximum(out['waterlevel'] - out['bedlevel'], 0.0)
    return out


def main():
    print('Loading per-partition map.nc (bedlevel + waterdepth at last timestep)...')
    x, y, bl0, blF, wd, t0, tF = load_per_partition_bl()
    delta_bl = blF - bl0
    abs_delta = np.abs(delta_bl)
    print(f'  Map first/last time:  {t0}  ->  {tF}')
    print(f'  Faces total:          {len(x)}')
    print(f'  delta_bl stats (m):   mean={delta_bl.mean():+.4f}  '
          f'absmax={abs_delta.max():.3f}  std={delta_bl.std():.4f}')

    in_lag = (x >= LAG_X[0]) & (x <= LAG_X[1]) & (y >= LAG_Y[0]) & (y <= LAG_Y[1])
    in_bn = ((x >= BOCA_NORD[0] - BN_PAD) & (x <= BOCA_NORD[0] + BN_PAD) &
             (y >= BOCA_NORD[1] - BN_PAD) & (y <= BOCA_NORD[1] + BN_PAD))
    print(f'  Lagoon zoom faces:    {int(in_lag.sum())}')
    print(f'  Boca Nord zoom:       {int(in_bn.sum())}')
    print(f'  Lagoon: |db| > 5cm:   {int(((abs_delta > 0.05) & in_lag).sum())}')
    print(f'  Lagoon: |db| > 10cm:  {int(((abs_delta > 0.10) & in_lag).sum())}')
    print(f'  Lagoon: |db| > 25cm:  {int(((abs_delta > 0.25) & in_lag).sum())}')
    print(f'  BN zoom: |db| max:    {abs_delta[in_bn].max():.3f} m')
    print(f'  BN zoom: depth<0.1 m: {int((wd[in_bn] < 0.1).sum())}')
    print(f'  BN zoom: depth<0.3 m: {int((wd[in_bn] < 0.3).sum())}')

    # Load his.nc series for the three stations
    series = {}
    for n in STATIONS:
        s = load_his_at_station(n)
        if s is None:
            print(f'  WARN: {n} not found in any his.nc partition')
            continue
        series[n] = s
        if 'bedlevel' in s and 'waterdepth' in s:
            bl_arr = np.atleast_1d(s['bedlevel'])
            wd_arr = np.atleast_1d(s['waterdepth'])
            db_total = bl_arr[-1] - bl_arr[0]
            d_min = wd_arr.min()
            d_end = wd_arr[-1]
            print(f'  {n}: bedlevel delta = {db_total:+.4f} m,  '
                  f'min depth = {d_min:.3f} m,  final depth = {d_end:.3f} m')

    fig, axes = plt.subplots(2, 2, figsize=(15.5, 13))

    # --- 1. Full lagoon, |delta_bl|
    ax = axes[0, 0]
    sc = ax.scatter(x[in_lag], y[in_lag], c=abs_delta[in_lag], s=10,
                    cmap='magma_r', vmin=0, vmax=max(0.10, abs_delta[in_lag].max() * 0.7))
    for nm, (sx, sy) in STATIONS.items():
        ax.scatter(sx, sy, marker='*', color='cyan', s=180,
                   edgecolors='black', linewidths=0.8)
        ax.annotate(nm, (sx, sy), xytext=(6, 6), textcoords='offset points',
                    color='cyan', fontsize=8, fontweight='bold')
    ax.set_title(f'v04AE — Cumulative |delta bedlevel| over\n'
                 f'{str(t0)[:10]} -> {str(tF)[:10]}')
    ax.set_xlabel('lon'); ax.set_ylabel('lat')
    ax.set_aspect('equal', adjustable='box')
    plt.colorbar(sc, ax=ax, label='|delta_bl| [m]')

    # --- 2. Boca Nord zoom — signed delta_bl
    ax = axes[0, 1]
    vmax = max(0.10, np.abs(delta_bl[in_bn]).max())
    sc = ax.scatter(x[in_bn], y[in_bn], c=delta_bl[in_bn], s=30,
                    cmap='RdBu_r', vmin=-vmax, vmax=vmax)
    ax.scatter(*BOCA_NORD, marker='*', color='black', s=220,
               edgecolors='cyan', linewidths=1.4, label='BocaNord obs')
    ax.legend(fontsize=9)
    ax.set_title('Boca Nord zoom — signed delta_bl\n'
                 '(red = deposition / rising bed, blue = erosion)')
    ax.set_xlabel('lon'); ax.set_ylabel('lat')
    ax.set_aspect('equal', adjustable='box')
    plt.colorbar(sc, ax=ax, label='delta_bl [m]')

    # --- 3. Bedlevel time series at the three stations
    ax = axes[1, 0]
    for nm, color in zip(STATIONS, ['tab:red', 'tab:blue', 'tab:green']):
        if nm not in series or 'bedlevel' not in series[nm]:
            continue
        bl_arr = np.atleast_1d(series[nm]['bedlevel'])
        t_arr = series[nm]['time']
        if bl_arr.size == 1:
            ax.axhline(bl_arr[0], color=color, label=f'{nm} bl(t0)={bl_arr[0]:.3f}')
        else:
            ax.plot(t_arr, bl_arr, color=color, lw=1.4, label=nm)
    ax.set_title('Bedlevel at interior obs stations (his.nc)\nMorStt=1440 min so bed update starts at sim-day 1')
    ax.set_ylabel('bedlevel [m AD]')
    ax.legend(loc='best', fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
    ax.grid(alpha=0.3)

    # --- 4. Waterdepth time series
    ax = axes[1, 1]
    for nm, color in zip(STATIONS, ['tab:red', 'tab:blue', 'tab:green']):
        if nm not in series or 'waterdepth' not in series[nm]:
            continue
        wd_arr = np.atleast_1d(series[nm]['waterdepth'])
        if wd_arr.size == 1:
            continue
        ax.plot(series[nm]['time'], wd_arr, color=color, lw=1.4, label=nm)
    ax.axhline(0.5, color='black', ls='--', alpha=0.5, label='SedThr=0.5 m (transport suppressed below)')
    ax.axhline(0.1, color='red', ls=':', alpha=0.6, label='~drying threshold')
    ax.set_title('Waterdepth at interior obs stations')
    ax.set_ylabel('depth [m]')
    ax.legend(loc='best', fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
    ax.grid(alpha=0.3)

    plt.tight_layout()
    out = FIG / 'v04AE_dmorph_bocanord.png'
    plt.savefig(out, dpi=140, bbox_inches='tight')
    print(f'Saved {out}')

    # Per-station CSV summary
    rows = []
    for nm in STATIONS:
        if nm not in series:
            continue
        bl_arr = np.atleast_1d(series[nm].get('bedlevel', [np.nan]))
        wd_arr = np.atleast_1d(series[nm].get('waterdepth', [np.nan]))
        wl_arr = np.atleast_1d(series[nm].get('waterlevel', [np.nan]))
        rows.append({
            'station': nm,
            'bl_t0_m': float(bl_arr[0]) if bl_arr.size else np.nan,
            'bl_tF_m': float(bl_arr[-1]) if bl_arr.size else np.nan,
            'bl_delta_m': float(bl_arr[-1] - bl_arr[0]) if bl_arr.size > 1 else 0.0,
            'depth_min_m': float(wd_arr.min()) if wd_arr.size else np.nan,
            'depth_end_m': float(wd_arr[-1]) if wd_arr.size else np.nan,
            'wl_min_m': float(wl_arr.min()) if wl_arr.size else np.nan,
            'wl_max_m': float(wl_arr.max()) if wl_arr.size else np.nan,
        })
    csv = PROC / 'v04AE_bed_change_summary.csv'
    pd.DataFrame(rows).to_csv(csv, index=False, float_format='%.4f')
    print(f'Saved {csv}')


if __name__ == '__main__':
    main()
