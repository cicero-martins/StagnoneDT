"""v04 health check — 4 sequential diagnostics:
  1. Wave coupling: mesh2d_hwav time-varying?
  2. Total volume evolution over 9d
  3. Spatial map of high-salinity cells
  4. WL validation at BocaNord, BocaSud, AltaVilaEst, Marettimo

Outputs to figures/ + console summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import netCDF4 as nc
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
HIS_FILES = sorted(OUT_DIR.glob('Stagnone_dxy01_15m_000?_his.nc'))
MAP_FILES = sorted(OUT_DIR.glob('Stagnone_dxy01_15m_000?_map.nc'))
FIG = PROJECT_ROOT / 'figures'
FIG.mkdir(exist_ok=True)

STATIONS = {
    'BocaNord':    (12.4413, 37.8788),
    'BocaSud':     (12.4413, 37.8528),
    'AltaVilaEst': (12.4593, 37.8742),
    'Marettimo':   (12.0766, 37.9662),
}


def find_station_partition(lon: float, lat: float) -> tuple[int, int, float]:
    """Return (partition, idx, dist_km) of the closest WET cell."""
    best = None
    for p in range(8):
        ds = nc.Dataset(MAP_FILES[p])
        fx = ds.variables['mesh2d_face_x'][:]
        fy = ds.variables['mesh2d_face_y'][:]
        bl = ds.variables['mesh2d_flowelem_bl'][:]
        wet = bl < 0
        if wet.any():
            d2 = (fx - lon) ** 2 + (fy - lat) ** 2
            d2_wet = np.where(wet, d2, np.inf)
            idx = int(np.argmin(d2_wet))
            d = float(np.sqrt(d2_wet[idx])) * 111
            if best is None or d < best[2]:
                best = (p, idx, d)
        ds.close()
    return best


def step1_wave_coupling():
    print('=== 1. Wave coupling: mesh2d_hwav variability ===')
    ds = nc.Dataset(MAP_FILES[3])  # bigger lagoon partition
    fx = ds.variables['mesh2d_face_x'][:]
    fy = ds.variables['mesh2d_face_y'][:]
    t = ds.variables['time']
    times = pd.to_datetime(nc.num2date(t[:], t.units, only_use_cftime_datetimes=False))
    # check 4 representative offshore + lagoon cells
    points = {
        'offshore_W': (12.05, 37.85),
        'offshore_S': (12.30, 37.72),
        'inlet_BN': (12.4413, 37.8788),
        'lagoon_C': (12.46, 37.87),
    }
    if 'mesh2d_hwav' not in ds.variables:
        print(f'  mesh2d_hwav NOT in {MAP_FILES[3].name}; available wave vars: '
              f'{[v for v in ds.variables if "wav" in v.lower() or "hsig" in v.lower()]}')
        ds.close()
        return
    hwav = ds.variables['mesh2d_hwav']
    print(f'  mesh2d_hwav shape: {hwav.shape}')
    fig, ax = plt.subplots(1, 1, figsize=(13, 5))
    for name, (lo, la) in points.items():
        d2 = (fx - lo) ** 2 + (fy - la) ** 2
        idx = int(np.argmin(d2))
        series = np.asarray(hwav[:, idx])
        valid = series[(series > -100) & np.isfinite(series)]
        if len(valid) == 0:
            continue
        ax.plot(times, series, lw=0.8, label=f'{name} ({fx[idx]:.3f}, {fy[idx]:.3f})  std={series.std():.3f}')
        print(f'  {name}: n_valid={len(valid)}, range=[{valid.min():.3f},{valid.max():.3f}], mean={valid.mean():.3f}, std={valid.std():.3f}')
    ax.set_ylabel('mesh2d_hwav (significant wave height) [m]')
    ax.set_title('v04 — wave coupling time series at 4 representative cells')
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc='upper left')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H'))
    fig.tight_layout()
    fig.savefig(FIG / 'v04_wave_coupling_check.png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'  saved {FIG / "v04_wave_coupling_check.png"}')
    ds.close()


def step2_volume_evolution():
    print()
    print('=== 2. Total volume evolution ===')
    times = None
    total_vol = None
    for p, fn in enumerate(MAP_FILES):
        ds = nc.Dataset(fn)
        if times is None:
            t = ds.variables['time']
            times = pd.to_datetime(nc.num2date(t[:], t.units, only_use_cftime_datetimes=False))
            total_vol = np.zeros(len(times))
        # Volume per cell = waterdepth * face_area; sum per timestep
        if 'mesh2d_flowelem_ba' not in ds.variables:
            ba_var = next((v for v in ds.variables if 'flowelem' in v.lower() and ('ba' in v.lower() or 'area' in v.lower())), None)
            if ba_var is None:
                print(f'  no face area var found in {fn.name}')
                ds.close()
                continue
        else:
            ba_var = 'mesh2d_flowelem_ba'
        ba = ds.variables[ba_var][:]
        wd = ds.variables['mesh2d_waterdepth']
        vol_part = (np.asarray(wd[:]) * ba[None, :]).sum(axis=1)
        total_vol += vol_part
        ds.close()
    fig, ax = plt.subplots(1, 1, figsize=(13, 4.5))
    ax.plot(times, total_vol / 1e9, '-', lw=1.5, color='steelblue')
    ax.set_ylabel('Total domain volume [10⁹ m³]')
    ax.set_title(f'v04 — total water volume over 9 sim-days (initial {total_vol[0]/1e9:.1f} x 1e9 m3)')
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.tight_layout()
    fig.savefig(FIG / 'v04_volume_evolution.png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    delta = (total_vol[-1] - total_vol[0]) / total_vol[0]
    print(f'  initial: {total_vol[0]/1e9:.3f} x 1e9 m3')
    print(f'  final:   {total_vol[-1]/1e9:.3f} x 1e9 m3')
    print(f'  delta:   {delta*100:+.2f}%')
    print(f'  range over run: min={total_vol.min()/1e9:.3f}, max={total_vol.max()/1e9:.3f} x 1e9 m3')
    print(f'  saved {FIG / "v04_volume_evolution.png"}')


def step3_high_sal_map():
    print()
    print('=== 3. Spatial distribution of high-salinity cells ===')
    fig, ax = plt.subplots(1, 1, figsize=(11, 9))
    n_total_high = 0
    for p, fn in enumerate(MAP_FILES):
        ds = nc.Dataset(fn)
        fx = ds.variables['mesh2d_face_x'][:]
        fy = ds.variables['mesh2d_face_y'][:]
        bl = ds.variables['mesh2d_flowelem_bl'][:]
        sa_final = np.asarray(ds.variables['mesh2d_sa1'][-1, :, -1])  # surface, last timestep
        # Plot all cells dimly
        ax.scatter(fx, fy, c='lightgray', s=2, alpha=0.3)
        # Color by salinity bins
        masks_thresholds = [
            (sa_final > 50, 50, '#fdcc8a', '50<S<100'),
            (sa_final > 100, 100, '#fc8d59', '100<S<200'),
            (sa_final > 200, 200, '#e34a33', '200<S<500'),
            (sa_final > 500, 500, '#b30000', 'S>500'),
        ]
        # Plot in increasing order of severity (overlapping covers worst on top)
        for mask, _, color, _ in masks_thresholds:
            if mask.sum():
                ax.scatter(fx[mask], fy[mask], c=color, s=8, alpha=0.85)
        n_high = int((sa_final > 50).sum())
        n_total_high += n_high
        ds.close()

    # Add legend
    legend_handles = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgray', markersize=6, label='Normal (S < 50)', alpha=0.5),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#fdcc8a', markersize=8, label='50 < S < 100'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#fc8d59', markersize=8, label='100 < S < 200'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#e34a33', markersize=8, label='200 < S < 500'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#b30000', markersize=8, label='S > 500'),
    ]
    ax.legend(handles=legend_handles, loc='lower right', fontsize=9)

    # Zoom on lagoon area
    ax.set_xlim(12.40, 12.55)
    ax.set_ylim(37.82, 37.95)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title(f'v04 — Surface salinity > 50 ppt at t=final (zoom on lagoon, n={n_total_high} cells)')
    ax.grid(alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    fig.tight_layout()
    fig.savefig(FIG / 'v04_high_sal_map.png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'  Total cells with S > 50 ppt (final): {n_total_high}')
    print(f'  saved {FIG / "v04_high_sal_map.png"}')


def _decode_station_names(arr):
    out = []
    for row in arr:
        if hasattr(row, 'tobytes'):
            s = row.tobytes().decode('utf-8', errors='replace').rstrip('\x00').strip()
        else:
            s = ''.join(c for c in row if c).strip()
        out.append(s)
    return out


def _load_his_waterlevel():
    """Concatenate waterlevel from all 8 partition his.nc files, keyed by station name.
    Each station is stored in only some partitions (the one(s) that own its cell)."""
    series_by_station = {}
    for fn in HIS_FILES:
        ds = nc.Dataset(fn)
        names = _decode_station_names(ds.variables['station_name'][:])
        t = ds.variables['time']
        times = pd.to_datetime(nc.num2date(t[:], t.units, only_use_cftime_datetimes=False))
        wl = ds.variables['waterlevel']  # (time, station)
        for i, name in enumerate(names):
            s = pd.Series(np.asarray(wl[:, i]), index=times)
            # Filter likely fill values (-999) and out-of-range
            s = s.where((s > -10) & (s < 10))
            if name in series_by_station:
                # Merge — if both have non-NaN at a time, keep the first (FM writes
                # the same cell value in all partitions that share the obs).
                series_by_station[name] = series_by_station[name].combine_first(s)
            else:
                series_by_station[name] = s
        ds.close()
    return series_by_station


def _find_marettimo_cell_v03d_compat(
        target_lon: float = 12.0753, target_lat: float = 37.9747,
        bl_max: float = -0.3, bl_min: float = -50.0):
    """Find the cell closest to v03d's known-good Marettimo location
    (12.0753, 37.9747, bl=-0.64m, ~1.78 km from gauge per
    scripts/validate_v03d_marettimo.py). Constraint bl<-0.3m avoids
    intertidal cells that would flat-line from drying.

    Returns (p, idx, lon, lat, bl, dist_km) of the best match, or None.
    """
    best = None
    for p in range(8):
        ds = nc.Dataset(MAP_FILES[p])
        fx = ds.variables['mesh2d_face_x'][:]
        fy = ds.variables['mesh2d_face_y'][:]
        bl = ds.variables['mesh2d_flowelem_bl'][:]
        d_km = np.sqrt((fx - target_lon) ** 2 + (fy - target_lat) ** 2) * 111
        ok = (bl < bl_max) & (bl > bl_min)
        if not ok.any():
            ds.close()
            continue
        d_ok = np.where(ok, d_km, np.inf)
        idx = int(np.argmin(d_ok))
        d = float(d_ok[idx])
        cand = (d, p, idx, float(fx[idx]), float(fy[idx]), float(bl[idx]))
        if best is None or cand[0] < best[0]:
            best = cand
        ds.close()
    return best


def step4_wl_validation():
    print()
    print('=== 4. WL validation: raw + anomaly comparison ===')
    obs_files = {
        'BocaNord': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'boundaries_BN.csv',
        'BocaSud': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'boundaries_BS.csv',
        'AltaVilaEst': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'boundaries_AE.csv',
        'Marettimo': PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv',
    }
    MARETTIMO_GAUGE = (12.0766, 37.9662)

    T_MIN = pd.Timestamp('2025-07-02 00:00')  # skip first sim-day (spinup transient)
    T_MAX = pd.Timestamp('2025-07-10 00:00')

    his_wl = _load_his_waterlevel()
    print(f'  Stations in his.nc: {sorted(his_wl.keys())}')
    target_stations = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'Marettimo']

    # Resolve Marettimo from map.nc using v03d's known-good cell location
    # (12.0753, 37.9747, bl=-0.64m). v03d gave Corr 0.886 at this cell.
    # Constraint bl<-0.3m avoids intertidal cells that flat-line via drying.
    print('  Marettimo cell (closest to v03d anchor 12.0753,37.9747 with bl<-0.3m):')
    m_best = _find_marettimo_cell_v03d_compat()
    if m_best:
        d, p, idx, lon, lat, bl = m_best
        print(f'    part {p} idx {idx} ({lon:.4f},{lat:.4f}) bl={bl:.2f}m '
              f'dist_to_v03d_anchor={d:.2f}km')
        ds = nc.Dataset(MAP_FILES[p])
        t = ds.variables['time']
        times = pd.to_datetime(nc.num2date(t[:], t.units, only_use_cftime_datetimes=False))
        s1 = np.asarray(ds.variables['mesh2d_s1'][:, idx])
        s1 = np.where((s1 > -10) & (s1 < 10), s1, np.nan)
        ds.close()
        his_wl['Marettimo'] = pd.Series(s1, index=times).dropna()

    fig, axes = plt.subplots(len(target_stations), 2, figsize=(16, 11), sharex=True)
    metrics_rows = []
    for row, sname in enumerate(target_stations):
        ax_raw = axes[row, 0]
        ax_anom = axes[row, 1]
        if sname not in his_wl:
            print(f'  {sname}: not in his.nc')
            for a in (ax_raw, ax_anom):
                a.text(0.5, 0.5, f'{sname}: no model data', transform=a.transAxes, ha='center')
            continue
        mod = his_wl[sname].dropna().loc[T_MIN:T_MAX]
        if len(mod) == 0:
            continue

        obs_path = obs_files.get(sname)
        obs = None
        if obs_path and obs_path.exists():
            try:
                if sname == 'Marettimo':
                    obs_df = pd.read_csv(obs_path)
                    obs_df['t'] = pd.to_datetime(obs_df['Time(UTC)'])
                    obs = obs_df.set_index('t')['wl_m'].loc[T_MIN:T_MAX]
                else:
                    obs_df = pd.read_csv(obs_path, encoding='utf-8-sig')
                    tcol = obs_df.columns[0]
                    vcol = obs_df.columns[1]
                    obs_df['t_local'] = pd.to_datetime(obs_df[tcol], dayfirst=False, errors='coerce')
                    obs_df = obs_df.dropna(subset=['t_local'])
                    obs_df['t'] = obs_df['t_local'] - pd.Timedelta(hours=1)
                    obs_df[vcol] = pd.to_numeric(obs_df[vcol], errors='coerce')
                    obs = obs_df.set_index('t')[vcol].dropna().loc[T_MIN:T_MAX]
            except Exception as e:
                print(f'  {sname}: obs load failed: {e}')

        if obs is not None and len(obs) > 10:
            obs_r = obs.reindex(mod.index, method='nearest', tolerance=pd.Timedelta('30min'))
            aligned = pd.concat([mod.rename('mod'), obs_r.rename('obs')], axis=1).dropna()
            if len(aligned) > 10:
                diff = aligned['mod'] - aligned['obs']
                bias = float(diff.mean())
                rmse = float(np.sqrt((diff ** 2).mean()))
                corr = float(aligned['mod'].corr(aligned['obs']))
                # Anomaly: subtract per-series mean (window of overlap)
                mod_anom = aligned['mod'] - aligned['mod'].mean()
                obs_anom = aligned['obs'] - aligned['obs'].mean()
                diff_anom = mod_anom - obs_anom
                rmse_anom = float(np.sqrt((diff_anom ** 2).mean()))
                corr_anom = float(mod_anom.corr(obs_anom))
                std_ratio = float(aligned['mod'].std() / aligned['obs'].std())
                metrics_rows.append({
                    'station': sname, 'n': len(aligned),
                    'rmse_raw': rmse, 'bias': bias, 'corr_raw': corr,
                    'rmse_anom': rmse_anom, 'corr_anom': corr_anom,
                    'std_mod': aligned['mod'].std(), 'std_obs': aligned['obs'].std(),
                    'std_ratio': std_ratio,
                })
                # RAW
                ax_raw.plot(obs.index, obs.values, '-', color='#3a7bd5', lw=0.6, alpha=0.6,
                            label=f'obs (n={len(aligned)})')
                ax_raw.plot(mod.index, mod.values, '-', color='#d96b0d', lw=0.9,
                            label='v04 model')
                ax_raw.set_title(f'{sname}: bias={bias:+.3f} m, RMSE={rmse:.3f}, r={corr:.3f}',
                                 fontsize=10)
                # ANOMALY
                ax_anom.plot(obs_anom.index, obs_anom.values, '-', color='#3a7bd5', lw=0.6,
                             alpha=0.6, label='obs anomaly')
                ax_anom.plot(mod_anom.index, mod_anom.values, '-', color='#d96b0d', lw=0.9,
                             label='v04 anomaly')
                ax_anom.set_title(f'{sname} anomaly: RMSE={rmse_anom:.3f}, r={corr_anom:.3f}, '
                                  f'std_mod/std_obs={std_ratio:.2f}', fontsize=10)
        ax_raw.set_ylabel('WL [m]')
        ax_anom.set_ylabel('WL anomaly [m]')
        ax_raw.grid(alpha=0.3)
        ax_anom.grid(alpha=0.3)
        ax_raw.legend(loc='upper left', fontsize=8)
        ax_anom.legend(loc='upper left', fontsize=8)
        ax_anom.axhline(0, color='gray', lw=0.5)

    for row in range(len(target_stations)):
        for col in range(2):
            axes[row, col].set_xlim(T_MIN, T_MAX)
    for col in range(2):
        axes[-1, col].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.suptitle('v04 - WL validation: raw (left) vs anomaly (right) — Jul 2-10 2025 (post-spinup, day 1 dropped)')
    fig.tight_layout()
    fig.savefig(FIG / 'v04_wl_validation.png', dpi=110, bbox_inches='tight')
    plt.close(fig)
    print(f'  saved {FIG / "v04_wl_validation.png"}')
    if metrics_rows:
        df = pd.DataFrame(metrics_rows)
        print()
        print(df.to_string(index=False, float_format=lambda x: f'{x:+.4f}'))
        out_csv = PROJECT_ROOT / 'data' / 'processed' / 'validation_metrics_v04.csv'
        df.to_csv(out_csv, index=False)
        print(f'  saved {out_csv}')


def main() -> int:
    step1_wave_coupling()
    step2_volume_evolution()
    step3_high_sal_map()
    step4_wl_validation()
    return 0


if __name__ == '__main__':
    sys.exit(main())
