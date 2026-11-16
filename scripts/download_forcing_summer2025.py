"""Download of the CMEMS and ERA5 forcing for the summer renewal run, 8 June to 15 September 2025.

The window carries one day of margin at each end, 7 June to 17 September.

CMEMS Mediterranean physics (MEDSEA, 1/24 degree), into data/raw/cmems_summer2025/:
  zos     analysis-forecast at 15 min, which carries the tide;
  uo, vo, so, thetao  daily means of the multiyear reanalysis, or of its interim
          extension (myint) for the days the reanalysis does not yet cover.
ERA5 single levels (mer, msl, chnk, u10n, v10n), monthly files through
dfm_tools into data/raw/era5_v04AE_d10d12/, where the July files already lie.

Usage:
    python download_forcing_summer2025.py [cmems|era5]
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parent.parent
DIR_CMEMS = ROOT / 'data' / 'raw' / 'cmems_summer2025'
DIR_ERA5 = ROOT / 'data' / 'raw' / 'era5_v04AE_d10d12'
START, END = '2025-06-07', '2025-09-17'
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


def cmems():
    import copernicusmarine
    import xarray as xr
    DIR_CMEMS.mkdir(parents=True, exist_ok=True)
    auth = dict(username=os.environ['CMEMS_USERNAME'], password=os.environ['CMEMS_PASSWORD'])
    zos = DIR_CMEMS / f'cmems_zos_{START}_{END}.nc'
    if not zos.exists():
        copernicusmarine.subset(dataset_id='cmems_mod_med_phy-ssh_anfc_4.2km_PT15M-i', variables=['zos'],
                                start_datetime=f'{START}T00:00:00', end_datetime=f'{END}T00:00:00',
                                output_directory=str(DIR_CMEMS), output_filename=zos.name, **BBOX, **auth)
    for var, kind in (('uo', 'cur'), ('vo', 'cur'), ('so', 'sal'), ('thetao', 'temp')):
        out = DIR_CMEMS / f'cmems_{var}_{START}_{END}.nc'
        if out.exists():
            continue
        parts = []
        t0 = START
        for prod in ('my', 'myint'):
            part = DIR_CMEMS / f'_part_{var}_{prod}.nc'
            if not part.exists():
                try:
                    copernicusmarine.subset(dataset_id=f'cmems_mod_med_phy-{kind}_{prod}_4.2km_P1D-m',
                                            variables=[var], start_datetime=f'{t0}T00:00:00',
                                            end_datetime=f'{END}T00:00:00', maximum_depth=MAX_DEPTH,
                                            output_directory=str(DIR_CMEMS), output_filename=part.name,
                                            **BBOX, **auth)
                except Exception as exc:  # the window may lie beyond one of the two products
                    print(f'{var} {prod}: {exc}', flush=True)
                    continue
            ds = xr.open_dataset(part)
            parts.append(ds)
            last = ds.time.values[-1]
            print(f'{var} {prod}: {str(ds.time.values[0])[:10]} to {str(last)[:10]}', flush=True)
            if str(last)[:10] >= END:
                break
            t0 = str(last + (ds.time.values[1] - ds.time.values[0]))[:10]
        merged = xr.concat(parts, 'time') if len(parts) > 1 else parts[0]
        merged = merged.sel(time=~merged.get_index('time').duplicated())
        got = (str(merged.time.values[0])[:10], str(merged.time.values[-1])[:10])
        if got[0] > START or got[1] < END:
            sys.exit(f'{var}: only {got[0]} to {got[1]} available')
        merged.to_netcdf(out)
        for ds in parts:
            ds.close()
        print(f'wrote {out.name}, {got[0]} to {got[1]}', flush=True)


def era5():
    import dfm_tools as dfmt
    DIR_ERA5.mkdir(parents=True, exist_ok=True)
    for var in ('mer', 'msl', 'chnk', 'u10n', 'v10n'):
        dfmt.download_ERA5(varkey=var, longitude_min=11.85, longitude_max=12.65,
                           latitude_min=37.65, latitude_max=38.10, date_min=START, date_max=END,
                           dir_output=str(DIR_ERA5), overwrite=False)
        print(f'era5 {var} done', flush=True)


if __name__ == '__main__':
    load_env()
    what = sys.argv[1:] or ['cmems', 'era5']
    if 'cmems' in what:
        cmems()
    if 'era5' in what:
        era5()
