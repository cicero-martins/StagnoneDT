"""Patch the era5_mer_*.nc file in v04 so FM's ec_provider can identify the
variable as rainfall_rate.

Diagnostic: FM ec_provider rejected 'rainfall_rate' because the variable's
standard_name attribute is the literal string 'unknown' (cfgrib could not
map ERA5 'mer' / 'avg_ie' to a CF standard name). FM matches by NetCDF
metadata, not by the QUANTITY field of the ext file alone.

Compare with era5_msl which has standard_name='air_pressure_at_mean_sea_level'
and works fine.

Fix: set standard_name and long_name to 'rainfall_rate' so ec_provider's
match succeeds. We also rename the variable from 'mer' to 'rainfall_rate'
in the NetCDF so the VARNAME entry in ext_old keeps working when set to
either name.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import netCDF4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NC_FILE = PROJECT_ROOT / 'model' / 'dflowfm_v04' / 'era5_mer_20250701to20250710_ERA5.nc'
BACKUP = NC_FILE.with_suffix('.nc.bak_attrs')


def main() -> int:
    if not NC_FILE.exists():
        print(f'ERROR: {NC_FILE} not found')
        return 1
    if not BACKUP.exists():
        print(f'Backup -> {BACKUP.name}')
        shutil.copy2(NC_FILE, BACKUP)

    with netCDF4.Dataset(NC_FILE, 'r+') as nc:
        if 'mer' not in nc.variables:
            print(f'ERROR: variable "mer" not in {NC_FILE.name} (vars={list(nc.variables)})')
            return 1
        var = nc.variables['mer']
        old_std = var.standard_name if hasattr(var, 'standard_name') else '<absent>'
        old_long = var.long_name if hasattr(var, 'long_name') else '<absent>'
        print(f'Before: standard_name={old_std!r}  long_name={old_long!r}')
        var.standard_name = 'rainfall_rate'
        var.long_name = 'rainfall_rate'
        print(f'After:  standard_name={var.standard_name!r}  long_name={var.long_name!r}')

    print('OK — re-inspect with xarray to verify')
    import xarray as xr
    ds = xr.open_dataset(NC_FILE)
    v = ds['mer']
    print(f'  var: mer')
    print(f'  standard_name: {v.attrs.get("standard_name")!r}')
    print(f'  long_name:     {v.attrs.get("long_name")!r}')
    print(f'  units:         {v.attrs.get("units")!r}')
    print(f'  data range:    [{float(v.min()):.3f},{float(v.max()):.3f}] {v.attrs["units"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
