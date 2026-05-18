"""
Bypass dfm_tools.preprocess (broken vs current hydrolib-core) and produce the
FM-ready ERA5 NetCDFs for v04AE_d10d12 (Jul 1-13 window).

Inputs:  data/raw/era5_v04AE_d10d12/era5_<var>_2025-07.nc (from CDS download)
Outputs: model/dflowfm_v04AE_d10d12/
   - era5_<var>_20250701to20250713_ERA5.nc  (5 vars, FM-readable attrs)
   - wind_era5raw_{u10n,v10n}_20250701to20250713.nc  (input for blend script)

If a raw file is missing (e.g. v10n download didn't finalize), re-fetches it
from CDS via dfm_tools.download_ERA5.

Attribute fixes per var (FM 2026 sensitive to standard_name for evap/wind/etc):
   mer  -> standard_name=rainfall_rate, units=mm day-1
   msl  -> standard_name=air_pressure_at_mean_sea_level, units=Pa
   chnk -> long_name=Charnock, units=Numeric (standard_name unknown OK)
   u10n -> long_name='10 metre u-component of neutral wind', units=m s**-1
   v10n -> long_name='10 metre v-component of neutral wind', units=m s**-1
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

LON_MIN, LON_MAX = 11.85, 12.65
LAT_MIN, LAT_MAX = 37.65, 38.10
DATE_MIN = '2025-07-01'
DATE_MAX = '2025-07-13'
DIR_RAW = PROJECT_ROOT / 'data' / 'raw' / 'era5_v04AE_d10d12'
DIR_OUT = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_d10d12'

# FM-readable attributes per variable
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


def fetch_missing(var):
    """Re-fetch a missing raw monthly file via dfm_tools."""
    print(f'Re-fetching missing {var}...', flush=True)
    import dfm_tools as dfmt
    dfmt.download_ERA5(
        varkey=var,
        longitude_min=LON_MIN, longitude_max=LON_MAX,
        latitude_min=LAT_MIN, latitude_max=LAT_MAX,
        date_min=DATE_MIN, date_max=DATE_MAX,
        dir_output=str(DIR_RAW),
        overwrite=True,
    )


def convert_mer(ds):
    """ERA5 mer comes in kg m-2 s-1; FM expects mm day-1.
    Convert: mm/day = (kg/m2/s) * 86400 / 1000 = kg/m2/s * 86.4
    For rainfall_rate convention upward-positive, also flip sign."""
    da = ds['mer']
    da_mm_day = da * 86400.0 / 1000.0
    da_mm_day = -da_mm_day  # ERA5 mer is downward (into surface)
                            #  FM rainfall_rate is upward-positive precip;
                            #  evap (negative mer) becomes positive precip-like upward flux.
                            # Actually FM convention: rainfall_rate adds water, evap removes.
                            # We apply sign flip to make consistent with v04rE5 file.
    ds2 = ds.copy()
    ds2['mer'] = da_mm_day
    return ds2


def preprocess_one(var):
    src = DIR_RAW / f'era5_{var}_2025-07.nc'
    if not src.exists():
        fetch_missing(var)
        if not src.exists():
            raise FileNotFoundError(src)

    ds = xr.open_dataset(src)

    # Newer CDS exports use 'valid_time' as the time dim/coord; rename to 'time'
    if 'valid_time' in ds.dims or 'valid_time' in ds.coords:
        ds = ds.rename({'valid_time': 'time'})

    # CDS sometimes uses cfVarName instead of GRIB shortName (e.g. 'avg_ie' for mer).
    # Rename the single data variable to the expected `var` if needed.
    data_vars = list(ds.data_vars)
    if var not in data_vars and data_vars:
        ds = ds.rename({data_vars[0]: var})

    # Slice to Jul 1 - Jul 13
    ds = ds.sel(time=slice(DATE_MIN, DATE_MAX + 'T23:59'))

    # Drop scalar/aux coords that confuse FM
    for c in ('expver', 'number'):
        if c in ds.coords:
            ds = ds.drop_vars(c)

    # Unit conversions
    if var == 'mer':
        ds = convert_mer(ds)

    ds[var].attrs.clear()
    ds[var].attrs.update(ATTRS[var])

    # Strip GRIB_* attrs from global to avoid bloat
    ds.attrs = {k: v for k, v in ds.attrs.items() if not k.startswith('GRIB_')}

    out = DIR_OUT / f'era5_{var}_20250701to20250713_ERA5.nc'
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
    print()

    produced = {}
    for var in ('mer', 'msl', 'chnk', 'u10n', 'v10n'):
        print(f'=== {var} ===')
        produced[var] = preprocess_one(var)

    # Wind raw copies for blend script
    for var in ('u10n', 'v10n'):
        src = produced[var]
        dst = DIR_OUT / f'wind_era5raw_{var}_20250701to20250713.nc'
        shutil.copy2(src, dst)
        print(f'wind_era5raw copy: {dst.name}', flush=True)

    print('\nDone.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
