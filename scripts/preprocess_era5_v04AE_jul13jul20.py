"""ERA5 preprocessing for v04AE Opt-A cold-start Jul 13-21 window.

Reads same monthly raw files as d10d12 (era5_v04AE_d10d12/era5_*_2025-07.nc)
- these cover the whole month, so the Jul 13-21 slice is in there.

Outputs: model/dflowfm_v04AE_jul13jul20/era5_<var>_20250713to20250721_ERA5.nc
        + wind_era5raw_{u10n,v10n}_20250713to20250721.nc
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import os
import shutil
import sys
from pathlib import Path

import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


load_dotenv(PROJECT_ROOT / '.env')

DATE_MIN = '2025-07-12'  # 1d buffer
DATE_MAX = '2025-07-22'
DIR_RAW = PROJECT_ROOT / 'data' / 'raw' / 'era5_v04AE_d10d12'  # monthly file covers all July
DIR_OUT = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_jul13jul20'

ATTRS = {
    'mer':  dict(standard_name='rainfall_rate', long_name='rainfall_rate', units='mm day-1'),
    'msl':  dict(standard_name='air_pressure_at_mean_sea_level',
                 long_name='Mean sea level pressure', units='Pa'),
    'chnk': dict(standard_name='unknown', long_name='Charnock', units='Numeric'),
    'u10n': dict(standard_name='unknown',
                 long_name='10 metre u-component of neutral wind', units='m s**-1'),
    'v10n': dict(standard_name='unknown',
                 long_name='10 metre v-component of neutral wind', units='m s**-1'),
}


def convert_mer(ds):
    da = ds['mer']
    da_mm_day = da * 86400.0 / 1000.0
    da_mm_day = -da_mm_day  # ERA5 mer is downward (into surface)
    ds2 = ds.copy()
    ds2['mer'] = da_mm_day
    return ds2


def preprocess_one(var):
    src = DIR_RAW / f'era5_{var}_2025-07.nc'
    if not src.exists():
        raise FileNotFoundError(f'Missing: {src}')

    ds = xr.open_dataset(src)
    if 'valid_time' in ds.dims or 'valid_time' in ds.coords:
        ds = ds.rename({'valid_time': 'time'})
    data_vars = list(ds.data_vars)
    if var not in data_vars and data_vars:
        ds = ds.rename({data_vars[0]: var})
    ds = ds.sel(time=slice(DATE_MIN, DATE_MAX + 'T23:59'))
    for c in ('expver', 'number'):
        if c in ds.coords:
            ds = ds.drop_vars(c)
    if var == 'mer':
        ds = convert_mer(ds)
    ds[var].attrs.clear()
    ds[var].attrs.update(ATTRS[var])
    ds.attrs = {k: v for k, v in ds.attrs.items() if not k.startswith('GRIB_')}
    out = DIR_OUT / f'era5_{var}_20250713to20250721_ERA5.nc'
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    enc = {var: {'zlib': True, 'complevel': 4}}
    ds.to_netcdf(out, encoding=enc)
    print(f'  wrote {out.name}  ({out.stat().st_size/1024:.1f} KB, '
          f'{len(ds.time)} times {ds.time.values[0]} -> {ds.time.values[-1]})',
          flush=True)
    return out


def main():
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    print(f'Inputs from:  {DIR_RAW}')
    print(f'Outputs to:   {DIR_OUT}')
    print(f'Window:       {DATE_MIN} -> {DATE_MAX}')
    print()
    produced = {}
    for var in ('mer', 'msl', 'chnk', 'u10n', 'v10n'):
        print(f'=== {var} ===')
        produced[var] = preprocess_one(var)
    for var in ('u10n', 'v10n'):
        src = produced[var]
        dst = DIR_OUT / f'wind_era5raw_{var}_20250713to20250721.nc'
        shutil.copy2(src, dst)
        print(f'wind_era5raw copy: {dst.name}', flush=True)
    print('\nDone.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
