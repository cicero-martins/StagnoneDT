"""Download ERA5 for v04AE Jul 10->12 continuation run.

Window: Jul 1-13 2025 (Jul 1-10 overlaps the original v04AE for sanity,
Jul 10-13 is the new continuation). 5 variables: mer, msl, chnk, u10n, v10n.

Outputs:
  - data/raw/era5_v04AE_d10d12/*.nc         (raw CDS downloads, monthly chunks)
  - model/dflowfm_v04AE_d10d12/era5_*.nc    (FM-ready preprocessed)
  - model/dflowfm_v04AE_d10d12/wind_era5raw_{u10n,v10n}_20250701to20250713.nc
        (raw netcdf for AE wind blend input -- mirrors v04rE5 pattern)
"""
from __future__ import annotations

# Windows SSL workaround: use system cert store (must import BEFORE requests/urllib3)
try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    print('pip-system-certs not installed; SSL may fail on Windows', flush=True)

import os
import shutil
import sys
from pathlib import Path

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

if not os.environ.get('CDSAPI_URL') or not os.environ.get('CDSAPI_KEY'):
    sys.exit('ERROR: CDSAPI_URL/CDSAPI_KEY not set in .env or environment')
print(f'CDS auth: URL={os.environ["CDSAPI_URL"]} '
      f'KEY={os.environ["CDSAPI_KEY"][:8]}...{os.environ["CDSAPI_KEY"][-4:]}',
      flush=True)

# --- Windows SSL workaround (same family as edito_ssl_workaround) ---
# Local Windows trusts system store; Python urllib3/requests don't see it.
# Two-step fix: try certifi bundle first (clean); if that fails, fall back
# to disabling verification with a warning (insecure but workable for CDS).
import certifi
ca_bundle = certifi.where()
os.environ.setdefault('SSL_CERT_FILE', ca_bundle)
os.environ.setdefault('REQUESTS_CA_BUNDLE', ca_bundle)
print(f'CA bundle: {ca_bundle}', flush=True)

# Monkey-patch SSL context globally as last resort
if os.environ.get('CDS_SSL_INSECURE', '0') == '1':
    import ssl
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    ssl._create_default_https_context = ssl._create_unverified_context
    print('WARNING: SSL verification DISABLED (CDS_SSL_INSECURE=1)', flush=True)

# Domain (same as previous v04 runs)
LON_MIN, LON_MAX = 11.85, 12.65
LAT_MIN, LAT_MAX = 37.65, 38.10

# Extended window: Jul 1-13 (covers original Jul 1-10 + continuation Jul 10-13)
DATE_MIN = '2025-07-01'
DATE_MAX = '2025-07-13'

VARKEYS = ['mer', 'msl', 'chnk', 'u10n', 'v10n']

DIR_RAW = PROJECT_ROOT / 'data' / 'raw' / 'era5_v04AE_d10d12'
DIR_OUT = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_d10d12'


def main() -> int:
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    DIR_OUT.mkdir(parents=True, exist_ok=True)

    import dfm_tools as dfmt

    # Step 1: download each variable (per-month chunks, dfm_tools handles)
    for varkey in VARKEYS:
        print(f'\n=== Downloading ERA5 {varkey} for {DATE_MIN} to {DATE_MAX} ===',
              flush=True)
        dfmt.download_ERA5(
            varkey=varkey,
            longitude_min=LON_MIN, longitude_max=LON_MAX,
            latitude_min=LAT_MIN, latitude_max=LAT_MAX,
            date_min=DATE_MIN, date_max=DATE_MAX,
            dir_output=str(DIR_RAW),
            overwrite=False,
        )

    # Step 2: preprocess into FM-ready merged netcdf (per varkey)
    print(f'\n=== Preprocessing into {DIR_OUT} ===', flush=True)
    import hydrolib.core.dflowfm as hcdfm
    tmp_ext = hcdfm.ExtOldModel()
    dfmt.preprocess_merge_meteofiles_era5(
        ext_old=tmp_ext,
        varkey_list=VARKEYS,
        dir_data=str(DIR_RAW),
        dir_output=str(DIR_OUT),
        time_slice=slice(DATE_MIN, DATE_MAX),
    )

    produced = sorted(DIR_OUT.glob('era5_*.nc'))
    print(f'\nFM-ready ERA5 files: {[p.name for p in produced]}', flush=True)

    # Step 3: copy u10n/v10n as wind_era5raw_*.nc for blend script
    for var in ('u10n', 'v10n'):
        # Find the matching era5_*.nc
        srcs = list(DIR_OUT.glob(f'era5_{var}_*.nc'))
        if not srcs:
            print(f'WARNING: era5_{var}_*.nc not produced')
            continue
        src = srcs[0]
        dst = DIR_OUT / f'wind_era5raw_{var}_20250701to20250713.nc'
        shutil.copy2(src, dst)
        print(f'Copied {src.name} -> {dst.name} (blend input)', flush=True)

    print('\nERA5 download + preprocess complete.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
