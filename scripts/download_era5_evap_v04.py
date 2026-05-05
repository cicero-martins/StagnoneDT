"""Download ERA5 mean evaporation rate (mer) for Jul 2025 + preprocess via
dfm_tools. Output goes into model/dflowfm_v04/ as era5_mer_20250701to20250710_ERA5.nc.

This is the v03c hipersalinidade fix: lagoon evap is dominated by net surface
mass flux (~5-7 mm/day in summer Mediterranean). Without this forcing, FM's
internal excess-heat model (temperature=3) does not remove water mass, only
heat — so salinity drifts upward during long runs.

Variable: 'mer' (mean evaporation rate) in kg m-2 s-1, sign convention NEGATIVE
for downward-into-ocean flux (ERA5 convention). FM expects evaporation in m/s
positive upward (out of ocean), so we apply factor=-1/1025 (water density)
in the ext entry, OR convert in preprocess.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(env_path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line, no quoting, '#' comments.
    Only sets keys not already in os.environ (existing env wins)."""
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

# Sanity check before invoking dfm_tools
if not os.environ.get('CDSAPI_URL') or not os.environ.get('CDSAPI_KEY'):
    sys.exit('ERROR: CDSAPI_URL and/or CDSAPI_KEY not set in environment '
             '(checked .env and os.environ). Add them to .env at project root.')
print(f'CDS auth: URL={os.environ["CDSAPI_URL"]} '
      f'KEY={os.environ["CDSAPI_KEY"][:8]}...{os.environ["CDSAPI_KEY"][-4:]}')

# Same domain as v03d ERA5 (use bbox slightly larger than mesh extent)
LON_MIN, LON_MAX = 11.85, 12.65
LAT_MIN, LAT_MAX = 37.65, 38.10

# Match the v03d Jul 2025 9-day window (matches startDateTime/stopDateTime)
DATE_MIN = '2025-07-01'
DATE_MAX = '2025-07-10'

DIR_RAW = PROJECT_ROOT / 'data' / 'raw' / 'era5'
DIR_OUT = PROJECT_ROOT / 'model' / 'dflowfm_v04'


def main() -> int:
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    import dfm_tools as dfmt

    # Step 1: download monthly ERA5 'mer' files
    print(f'Downloading ERA5 mer for {DATE_MIN} to {DATE_MAX}')
    dfmt.download_ERA5(
        varkey='mer',
        longitude_min=LON_MIN, longitude_max=LON_MAX,
        latitude_min=LAT_MIN, latitude_max=LAT_MAX,
        date_min=DATE_MIN, date_max=DATE_MAX,
        dir_output=str(DIR_RAW),
        overwrite=False,
    )

    # Step 2: preprocess into v04 directory (FM-ready merged netcdf)
    print(f'Preprocessing -> {DIR_OUT}')
    import pandas as pd
    ext_old_dummy = None  # we don't need dfmt to mutate an ext_old; we just want the file
    # Trick: use a temporary ExtOldModel, ignore its mutation
    import hydrolib.core.dflowfm as hcdfm
    tmp_ext = hcdfm.ExtOldModel()
    dfmt.preprocess_merge_meteofiles_era5(
        ext_old=tmp_ext,
        varkey_list=['mer'],
        dir_data=str(DIR_RAW),
        dir_output=str(DIR_OUT),
        time_slice=slice(DATE_MIN, DATE_MAX),
    )

    # Verify the output exists
    candidates = list(DIR_OUT.glob('era5_mer_*.nc'))
    print(f'Output files: {[c.name for c in candidates]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
