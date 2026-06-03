"""Diagnose forcings driving timestep collapse Jul 13 05:00 -> crash Jul 14 04:00.

Inspects all forcings during the critical window:
  - Wind (ERA5 raw + AE-blended) at lagoon center
  - Atmospheric pressure (ERA5 msl)
  - SSH at boundary (CMEMS waterlevel.bc)
  - SWAN waves at 9 boundary segments
  - 3D currents/sal/temp (CMEMS at boundary)

Output: figures/diag_forcings_jul13jul14.png + summary statistics.

Suspect drivers of CFL violation:
  1. Wind gust > 15 m/s at lagoon center
  2. Pressure drop > 5 hPa in 6h (mesoscale low)
  3. SSH gradient at boundary > 0.5 m in 6h
  4. Wave Hs > 3 m or Tp spike
"""
from __future__ import annotations

import re
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / 'model' / 'dflowfm_v04AE_jul13jul20'
FIG = ROOT / 'figures' / 'diag_forcings_jul13jul14.png'

# Critical window
T_START = pd.Timestamp('2025-07-12 00:00')
T_END = pd.Timestamp('2025-07-15 00:00')
T_CRASH = pd.Timestamp('2025-07-14 04:00')
T_TS_JUMP = pd.Timestamp('2025-07-13 05:00')

LAGOON_LON, LAGOON_LAT = 12.462, 37.867


def sample_grid_at_point(ds, var, lon, lat):
    """Nearest neighbor at a point, return series."""
    lon_dim = 'longitude' if 'longitude' in ds.dims else 'lon'
    lat_dim = 'latitude' if 'latitude' in ds.dims else 'lat'
    return ds[var].sel({lon_dim: lon, lat_dim: lat}, method='nearest')


def parse_bc_first_node(path: Path):
    """Parse first [Forcing] block of .bc file, return (times, values)."""
    text = path.read_text()
    # Find first [Forcing] block, look for quantity timeseries
    # .bc format has [Forcing] + name=... + function=timeseries + then data table
    # Find first data table (lines that are pure numeric pairs)
    lines = text.split('\n')
    in_data = False
    times = []
    vals = []
    refdate_match = re.search(r'minutes since (\d{4}-\d{2}-\d{2})', text)
    refdate = pd.Timestamp(refdate_match.group(1)) if refdate_match else pd.Timestamp('2025-01-01')
    quantity_count = 0
    for line in lines:
        s = line.strip()
        if s.startswith('quantity'):
            quantity_count += 1
            continue
        if s.startswith('[Forcing]'):
            if times:
                break
            continue
        if s and s[0].isdigit() or (s and s[0] == '-' and len(s) > 1 and s[1].isdigit()):
            parts = s.split()
            try:
                t_min = float(parts[0])
                # First data col after time, depending on quantity count layout
                v = float(parts[1])
                times.append(refdate + pd.Timedelta(minutes=t_min))
                vals.append(v)
            except (ValueError, IndexError):
                continue
    return pd.Series(vals, index=pd.DatetimeIndex(times))


def main():
    fig, axes = plt.subplots(6, 1, figsize=(15, 18), sharex=True)
    summary = []

    # 1. Wind (AE-blended, lagoon center)
    print('Loading wind...')
    ds_uw = xr.open_dataset(DST / 'wind_blendedAE_u10n_20250713to20250721.nc')
    ds_vw = xr.open_dataset(DST / 'wind_blendedAE_v10n_20250713to20250721.nc')
    u10 = sample_grid_at_point(ds_uw, 'u10n', LAGOON_LON, LAGOON_LAT)
    v10 = sample_grid_at_point(ds_vw, 'v10n', LAGOON_LON, LAGOON_LAT)
    times_w = pd.to_datetime(u10.time.values)
    spd = np.sqrt(u10.values**2 + v10.values**2)
    direc = np.degrees(np.arctan2(v10.values, u10.values))  # math direction (from)
    win = (times_w >= T_START) & (times_w <= T_END)
    ax = axes[0]
    ax.plot(times_w[win], spd[win], 'b-', label='|wind| AE-blend center')
    ax.plot(times_w[win], u10.values[win], 'g-', alpha=0.5, label='u10')
    ax.plot(times_w[win], v10.values[win], 'r-', alpha=0.5, label='v10')
    ax.set_ylabel('Wind (m/s)')
    ax.axvline(T_TS_JUMP, color='orange', linestyle='--', alpha=0.6, label='dt jump 7s→10s')
    ax.axvline(T_CRASH, color='red', linestyle='--', alpha=0.6, label='CRASH Jul 14 04:00')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_title('Wind at lagoon center (12.462, 37.867)')
    win_max = float(np.max(spd[win]))
    win_at_crash = float(spd[(times_w >= T_CRASH - pd.Timedelta('1h')) & (times_w <= T_CRASH + pd.Timedelta('1h'))].mean()) if (times_w >= T_CRASH).any() else np.nan
    summary.append(f'Wind: max={win_max:.1f} m/s in window; mean ±1h crash={win_at_crash:.1f} m/s')

    # 2. ERA5 raw wind for comparison (offshore values - boundary)
    ds_ueu = xr.open_dataset(DST / 'wind_era5raw_u10n_20250713to20250721.nc')
    ds_veu = xr.open_dataset(DST / 'wind_era5raw_v10n_20250713to20250721.nc')
    # ERA5 grid is coarser - sample at boundary west center (12.0, 37.9)
    u10e = sample_grid_at_point(ds_ueu, 'u10n', 12.0, 37.9)
    v10e = sample_grid_at_point(ds_veu, 'v10n', 12.0, 37.9)
    times_e = pd.to_datetime(u10e.time.values)
    spd_e = np.sqrt(u10e.values**2 + v10e.values**2)
    win_e = (times_e >= T_START) & (times_e <= T_END)
    ax = axes[1]
    ax.plot(times_e[win_e], spd_e[win_e], 'k-', label='|wind| ERA5 raw (offshore W)')
    ax.set_ylabel('Wind ERA5 (m/s)')
    ax.axvline(T_TS_JUMP, color='orange', linestyle='--', alpha=0.6)
    ax.axvline(T_CRASH, color='red', linestyle='--', alpha=0.6)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_title('ERA5 raw wind at offshore W (12.0, 37.9) — boundary forcing')
    summary.append(f'ERA5 wind: max={float(np.max(spd_e[win_e])):.1f} m/s in window')

    # 3. MSL (atmospheric pressure)
    print('Loading MSL...')
    ds_msl = xr.open_dataset(DST / 'era5_msl_20250713to20250721_ERA5.nc')
    msl = sample_grid_at_point(ds_msl, 'msl', LAGOON_LON, LAGOON_LAT)
    times_msl = pd.to_datetime(msl.time.values)
    msl_hpa = msl.values / 100.0
    win_msl = (times_msl >= T_START) & (times_msl <= T_END)
    ax = axes[2]
    ax.plot(times_msl[win_msl], msl_hpa[win_msl], 'm-', label='MSL ERA5 (lagoon)')
    ax.set_ylabel('MSL (hPa)')
    ax.axvline(T_TS_JUMP, color='orange', linestyle='--', alpha=0.6)
    ax.axvline(T_CRASH, color='red', linestyle='--', alpha=0.6)
    # Rate of change
    msl_drop_6h = msl_hpa[win_msl].max() - msl_hpa[win_msl].min()
    summary.append(f'MSL: range={msl_drop_6h:.1f} hPa over window; min={msl_hpa[win_msl].min():.1f}, max={msl_hpa[win_msl].max():.1f}')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_title('Atmospheric pressure at lagoon')

    # 4. SSH boundary from CMEMS .bc (first node)
    print('Parsing waterlevelbnd_CMEMS.bc...')
    try:
        wl = parse_bc_first_node(DST / 'waterlevelbnd_CMEMS_Stagnone_dxy01_15m.bc')
        win_wl = (wl.index >= T_START) & (wl.index <= T_END)
        ax = axes[3]
        ax.plot(wl.index[win_wl], wl.values[win_wl], 'b-', label='SSH @ PLI node 1')
        ax.set_ylabel('SSH (m)')
        ax.axvline(T_TS_JUMP, color='orange', linestyle='--', alpha=0.6)
        ax.axvline(T_CRASH, color='red', linestyle='--', alpha=0.6)
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(alpha=0.3)
        ax.set_title('SSH boundary CMEMS anfc PT15M (first PLI node)')
        wl_range = wl[win_wl].max() - wl[win_wl].min()
        summary.append(f'SSH bnd: range={wl_range:.2f} m; min={wl[win_wl].min():.2f}, max={wl[win_wl].max():.2f}')
    except Exception as e:
        print(f'SSH parse failed: {e}')
        summary.append(f'SSH parse error: {e}')

    # 5. SWAN wave Hs at all 9 boundary segments
    print('Parsing wave .bnd files...')
    bnd_files = sorted((DST / 'wave').glob('*_seg*.bnd'))
    ax = axes[4]
    for bf in bnd_files:
        with open(bf) as f:
            lines = f.readlines()
        times_w = []
        hs = []
        for line in lines[1:]:  # skip TPAR header
            parts = line.strip().split()
            if len(parts) >= 5:
                try:
                    ts = pd.Timestamp(parts[0][:8] + ' ' + parts[0][9:11] + ':' + parts[0][11:13])
                    times_w.append(ts)
                    hs.append(float(parts[1]))
                except (ValueError, IndexError):
                    continue
        times_w_arr = pd.DatetimeIndex(times_w)
        win_w = (times_w_arr >= T_START) & (times_w_arr <= T_END)
        ax.plot(times_w_arr[win_w], np.array(hs)[win_w], alpha=0.4, label=bf.stem)
    ax.set_ylabel('Hs (m)')
    ax.axvline(T_TS_JUMP, color='orange', linestyle='--', alpha=0.6)
    ax.axvline(T_CRASH, color='red', linestyle='--', alpha=0.6)
    ax.set_title('SWAN wave Hs at 9 boundary segments (TPAR .bnd)')
    ax.legend(loc='upper left', fontsize=6, ncol=3)
    ax.grid(alpha=0.3)

    # 6. mer (evaporation) — could be huge driving thermal stratification
    print('Loading ERA5 mer (evaporation)...')
    ds_mer = xr.open_dataset(DST / 'era5_mer_20250713to20250721_ERA5.nc')
    mer = sample_grid_at_point(ds_mer, 'mer', LAGOON_LON, LAGOON_LAT)
    times_mer = pd.to_datetime(mer.time.values)
    win_mer = (times_mer >= T_START) & (times_mer <= T_END)
    ax = axes[5]
    ax.plot(times_mer[win_mer], mer.values[win_mer], 'c-', label='mer ERA5 (mm/day)')
    ax.set_ylabel('Evap/precip (mm/day)')
    ax.set_xlabel('UTC')
    ax.axvline(T_TS_JUMP, color='orange', linestyle='--', alpha=0.6)
    ax.axvline(T_CRASH, color='red', linestyle='--', alpha=0.6)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIG, dpi=130, bbox_inches='tight')
    print(f'\nFigure: {FIG}')

    print('\n=== SUMMARY ===')
    for s in summary:
        print(f'  {s}')


if __name__ == '__main__':
    main()
