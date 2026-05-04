"""Compute the statistical offset anchor at Marettimo:

    delta(Marettimo) = mean(obs_Marettimo) - mean(zos_CMEMS_at_Marettimo)

over the 2025-01-01 to 2026-01-19 window, using:
- in-situ: JRC TAD device 658 (downloaded by scripts/download_marettimo_wl_long.py)
- CMEMS: MED-MFC analysis-forecast SSH daily-mean (cmems_mod_med_phy-ssh_anfc_4.2km_P1D-m)

Outputs:
- data/raw/cmems/zos_marettimo_anchor/<merged.nc>
- docs/marettimo_offset_anchor_2025.md (table with delta + monthly breakdown)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Marettimo SiAM gauge (JRC TAD 658)
MARETTIMO_LON = 12.0766
MARETTIMO_LAT = 37.9662

# Window
T_MIN = '2025-01-01'
T_MAX = '2026-01-20'

# CMEMS MED-PHY analysis-forecast SSH daily-mean
DATASET_ID = 'cmems_mod_med_phy-ssh_anfc_4.2km_P1D-m'
CMEMS_DIR = PROJECT_ROOT / 'data' / 'raw' / 'cmems' / 'zos_marettimo_anchor'
CMEMS_FILENAME = f'cmems_zos_marettimo_{T_MIN}_{T_MAX}.nc'
CMEMS_FILE = CMEMS_DIR / CMEMS_FILENAME

OBS_FILE = PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'
REPORT = PROJECT_ROOT / 'docs' / 'marettimo_offset_anchor_2025.md'


def download_cmems() -> None:
    if CMEMS_FILE.exists():
        print(f'  CMEMS file cached: {CMEMS_FILE.relative_to(PROJECT_ROOT)}')
        return
    CMEMS_DIR.mkdir(parents=True, exist_ok=True)
    import copernicusmarine
    print(f'  Downloading {DATASET_ID} -> {CMEMS_FILENAME}')
    copernicusmarine.subset(
        dataset_id=DATASET_ID,
        variables=['zos'],
        minimum_longitude=12.0, maximum_longitude=12.15,
        minimum_latitude=37.92, maximum_latitude=38.02,
        start_datetime=f'{T_MIN}T00:00:00',
        end_datetime=f'{T_MAX}T00:00:00',
        output_filename=CMEMS_FILENAME,
        output_directory=str(CMEMS_DIR),
    )


def main() -> int:
    print('=== Marettimo offset anchor 2025 ===')
    print()
    print('Step 1: CMEMS zos download')
    download_cmems()

    print()
    print('Step 2: extract zos at Marettimo')
    ds = xr.open_dataset(CMEMS_FILE)
    print(f'  Variables: {list(ds.data_vars)}')
    print(f'  Coords: {list(ds.coords)}')
    if 'longitude' in ds.coords:
        ds = ds.rename({'longitude': 'lon', 'latitude': 'lat'})
    print(f'  Time: {pd.Timestamp(ds.time.values[0])} -> {pd.Timestamp(ds.time.values[-1])}'
          f' (n={ds.time.size})')
    print(f'  Grid: lon=[{float(ds.lon.min()):.4f},{float(ds.lon.max()):.4f}], '
          f'lat=[{float(ds.lat.min()):.4f},{float(ds.lat.max()):.4f}], '
          f'shape=({ds.lat.size},{ds.lon.size})')

    zos_nearest = ds['zos'].sel(lon=MARETTIMO_LON, lat=MARETTIMO_LAT, method='nearest')
    zos_linear = ds['zos'].interp(lon=MARETTIMO_LON, lat=MARETTIMO_LAT)
    print(f'  Nearest cell: lon={float(zos_nearest.lon):.4f}, lat={float(zos_nearest.lat):.4f}')
    print(f'  Nearest mean: {float(zos_nearest.mean()):+.4f} m  std={float(zos_nearest.std()):.4f}')
    print(f'  Linear  mean: {float(zos_linear.mean()):+.4f} m  std={float(zos_linear.std()):.4f}')

    print()
    print('Step 3: load Marettimo obs (10-min combined)')
    obs = pd.read_csv(OBS_FILE)
    obs['t'] = pd.to_datetime(obs['Time(UTC)'])
    obs = obs.set_index('t')['wl_m']
    print(f'  N=10-min: {len(obs)}, range=[{obs.index[0]},{obs.index[-1]}]')
    print(f'  Mean (raw 10-min): {obs.mean():+.4f} m')

    print()
    print('Step 4: align daily and compute delta')
    print('  Using nearest cell (linear interp would NaN due to Marettimo island land cells)')
    zos_series = zos_nearest.to_pandas()
    zos_series.index = pd.DatetimeIndex(zos_series.index).normalize()

    # Daily mean of obs (12h-23:59h average), aligned to CMEMS daily grid
    obs_daily = obs.resample('1D').mean()
    obs_daily.index = pd.DatetimeIndex(obs_daily.index).normalize()

    df = pd.concat([obs_daily.rename('obs'), zos_series.rename('zos')], axis=1).dropna()
    print(f'  Aligned daily samples: N={len(df)}')
    print(f'  Common window: {df.index[0]} -> {df.index[-1]}')
    print(f'  Mean obs:      {df.obs.mean():+.4f} m')
    print(f'  Mean zos:      {df.zos.mean():+.4f} m')
    delta = df.obs.mean() - df.zos.mean()
    print(f'  delta(Marettimo) = mean(obs) - mean(zos) = {delta:+.4f} m')

    # Monthly breakdown
    monthly = df.resample('1ME').mean()
    monthly['delta'] = monthly['obs'] - monthly['zos']
    monthly.index = monthly.index.strftime('%Y-%m')
    print()
    print('Monthly breakdown (m):')
    print(monthly.to_string(float_format=lambda x: f'{x:+.4f}'))

    # Compare to current empirical offset
    current_offset = 0.4208
    print()
    print('Comparison to current configuration:')
    print(f'  Current empirical offset: +{current_offset:.4f} m')
    print(f'  Anchor delta(Marettimo):  {delta:+.4f} m')
    print(f'  Difference:               {delta - current_offset:+.4f} m')
    print(f'  (negative => current offset overestimates)')

    # Write report
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open('w', encoding='utf-8') as f:
        f.write('# Marettimo statistical offset anchor — 2025-2026\n\n')
        f.write(f'**Computed:** 2026-05-04 from `{OBS_FILE.relative_to(PROJECT_ROOT)}` and '
                f'`{CMEMS_FILE.relative_to(PROJECT_ROOT)}`.\n\n')
        f.write(f'**Method:**\n')
        f.write(f'- CMEMS dataset: `{DATASET_ID}` (MED-MFC analysis-forecast SSH daily mean, NEMO 4.2)\n')
        f.write(f'- `zos` linearly interpolated to Marettimo gauge coords ({MARETTIMO_LON}, {MARETTIMO_LAT})\n')
        f.write(f'- Marettimo obs from JRC TAD 658, 10-min sampled, daily-averaged\n')
        f.write(f'- Window: {df.index[0]} to {df.index[-1]} ({len(df)} aligned daily samples)\n\n')
        f.write(f'**Anchor:**\n\n')
        f.write(f'| Quantity | Value (m) |\n|---|---|\n')
        f.write(f'| mean(obs_Marettimo) | {df.obs.mean():+.4f} |\n')
        f.write(f'| mean(zos_CMEMS @ Marettimo) | {df.zos.mean():+.4f} |\n')
        f.write(f'| **delta(Marettimo) = obs - zos** | **{delta:+.4f}** |\n')
        f.write(f'| Current empirical offset | +{current_offset:.4f} |\n')
        f.write(f'| Difference (anchor - current) | {delta - current_offset:+.4f} |\n\n')
        f.write(f'**Monthly breakdown:**\n\n')
        f.write(f'| Month | obs (m) | zos (m) | delta (m) |\n|---|---|---|---|\n')
        for idx, row in monthly.iterrows():
            f.write(f'| {idx} | {row.obs:+.4f} | {row.zos:+.4f} | {row.delta:+.4f} |\n')
        f.write('\n')
    print()
    print(f'Report saved: {REPORT.relative_to(PROJECT_ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
