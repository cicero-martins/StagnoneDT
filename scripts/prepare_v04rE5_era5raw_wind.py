"""
Prepare ERA5 raw wind files for v04rE5 (re-run without blending). The original
ERA5 files have extra GRIB-derived coords (`number`, `expver`) that FM 2026.01
may or may not tolerate. We strip those and save clean copies named in
parallel to the blended files for clarity.

Output:
  model/dflowfm_v04rE5/wind_era5raw_u10n_20250701to20250710.nc
  model/dflowfm_v04rE5/wind_era5raw_v10n_20250701to20250710.nc
"""
from pathlib import Path
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'model' / 'dflowfm_v04rE5'

for var in ['u10n', 'v10n']:
    in_path = SRC / f'era5_{var}_20250701to20250710_ERA5.nc'
    out_path = SRC / f'wind_era5raw_{var}_20250701to20250710.nc'
    ds = xr.open_dataset(in_path)
    # Drop `number` and `expver` coords if present; they don't index u10n/v10n
    drop_coords = [c for c in ['number', 'expver'] if c in ds.coords]
    if drop_coords:
        ds = ds.drop_vars(drop_coords)
    # Cleanup attrs to keep only what's needed (FM reads standard_name/units)
    ds[var].attrs = {
        'standard_name': 'eastward_wind' if var == 'u10n' else 'northward_wind',
        'long_name': f'10 metre u-component of neutral wind' if var == 'u10n' else f'10 metre v-component of neutral wind',
        'units': 'm s-1',
    }
    ds.attrs = {
        'source': 'ERA5 reanalysis at 0.25 deg, raw (no blending with in-situ stations)',
        'note': 'Created for v04rE5 sensitivity test - drifter validation',
    }
    enc = {var: {'zlib': True, 'complevel': 4, '_FillValue': -9999.0}}
    ds.to_netcdf(out_path, encoding=enc)
    print(f'Wrote {out_path} ({out_path.stat().st_size/1e3:.1f} kB)')
    print(f'  shape: {dict(ds[var].sizes)}, time {ds.time.values[0]} -> {ds.time.values[-1]}')
    print(f'  coords kept: {list(ds.coords)}')
