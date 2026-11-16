"""Download of the CMEMS and ERA5 forcing for the seasonal renewal runs.

The windows of the two seasons are those of build_forcing_renewal.py, each with
one day of margin at each end of the run (summer 7 June to 17 September 2025,
winter 7 November 2025 to 17 January 2026).

CMEMS Mediterranean physics (MEDSEA, 1/24 degree), into
data/raw/cmems_<season><year>/:
  zos     analysis-forecast at 15 min, which carries the tide;
  uo, vo, so, thetao  daily means of the multiyear reanalysis, or of its interim
          extension (myint) for the days the reanalysis does not yet cover.
ERA5 single levels (mer, msl, chnk, u10n, v10n), monthly files through
dfm_tools into data/raw/era5_v04AE_d10d12/, where the July files already lie.

Usage:
    python download_forcing_renewal.py summer|winter [cmems|era5]
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import os
import sys
from pathlib import Path

import urllib3

from build_forcing_renewal import RAW_ERA5, ROOT, SEASONS, raw_cmems_dir

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BBOX = dict(minimum_longitude=11.70, maximum_longitude=12.70,
            minimum_latitude=37.55, maximum_latitude=38.20)
MAX_DEPTH = 1200.0


def load_env():
    env = ROOT / '.env'
    if env.exists():
        for raw in env.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cmems(season):
    import copernicusmarine
    import xarray as xr
    start, end = SEASONS[season]['d0'], SEASONS[season]['d1']
    dir_cmems = raw_cmems_dir(season)
    dir_cmems.mkdir(parents=True, exist_ok=True)
    auth = dict(username=os.environ['CMEMS_USERNAME'], password=os.environ['CMEMS_PASSWORD'])
    zos = dir_cmems / f'cmems_zos_{start}_{end}.nc'
    if not zos.exists():
        copernicusmarine.subset(dataset_id='cmems_mod_med_phy-ssh_anfc_4.2km_PT15M-i', variables=['zos'],
                                start_datetime=f'{start}T00:00:00', end_datetime=f'{end}T00:00:00',
                                output_directory=str(dir_cmems), output_filename=zos.name, **BBOX, **auth)
    for var, kind in (('uo', 'cur'), ('vo', 'cur'), ('so', 'sal'), ('thetao', 'temp')):
        out = dir_cmems / f'cmems_{var}_{start}_{end}.nc'
        if out.exists():
            continue
        parts = []
        t0 = start
        for prod in ('my', 'myint'):
            part = dir_cmems / f'_part_{var}_{prod}.nc'
            if not part.exists():
                try:
                    copernicusmarine.subset(dataset_id=f'cmems_mod_med_phy-{kind}_{prod}_4.2km_P1D-m',
                                            variables=[var], start_datetime=f'{t0}T00:00:00',
                                            end_datetime=f'{end}T00:00:00', maximum_depth=MAX_DEPTH,
                                            output_directory=str(dir_cmems), output_filename=part.name,
                                            **BBOX, **auth)
                except Exception as exc:  # the window may lie beyond one of the two products
                    print(f'{var} {prod}: {exc}', flush=True)
                    continue
            ds = xr.open_dataset(part)
            parts.append(ds)
            last = ds.time.values[-1]
            print(f'{var} {prod}: {str(ds.time.values[0])[:10]} to {str(last)[:10]}', flush=True)
            if str(last)[:10] >= end:
                break
            t0 = str(last + (ds.time.values[1] - ds.time.values[0]))[:10]
        if not parts:
            sys.exit(f'{var}: no product covers {start} to {end}')
        merged = xr.concat(parts, 'time') if len(parts) > 1 else parts[0]
        merged = merged.sel(time=~merged.get_index('time').duplicated())
        got = (str(merged.time.values[0])[:10], str(merged.time.values[-1])[:10])
        if got[0] > start or got[1] < end:
            sys.exit(f'{var}: only {got[0]} to {got[1]} available')
        merged.to_netcdf(out)
        for ds in parts:
            ds.close()
        print(f'wrote {out.name}, {got[0]} to {got[1]}', flush=True)


def era5(season):
    import dfm_tools as dfmt
    RAW_ERA5.mkdir(parents=True, exist_ok=True)
    for var in ('mer', 'msl', 'chnk', 'u10n', 'v10n'):
        dfmt.download_ERA5(varkey=var, longitude_min=11.85, longitude_max=12.65,
                           latitude_min=37.65, latitude_max=38.10,
                           date_min=SEASONS[season]['d0'], date_max=SEASONS[season]['d1'],
                           dir_output=str(RAW_ERA5), overwrite=False)
        print(f'era5 {var} done', flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in SEASONS:
        sys.exit(f'usage: download_forcing_renewal.py {"|".join(SEASONS)} [cmems|era5]')
    load_env()
    season, what = sys.argv[1], sys.argv[2:] or ['cmems', 'era5']
    if 'cmems' in what:
        cmems(season)
    if 'era5' in what:
        era5(season)
