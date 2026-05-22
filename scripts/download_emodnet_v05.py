"""Download EMODnet Bathymetry DTM 2022 (Mediterranean offshore bathy) for the
Stagnone v05 mesh bbox.

EMODnet Bathymetry DTM 2022 is the European-focused bathymetric grid at
~115 m native resolution (1/16 arc-min), compiled from national hydrographic
surveys including ISPRA (Italy) — well-suited to the Sicily Channel region.

Access via ERDDAP griddap (no auth, single HTTPS GET, returns netCDF):
  https://erddap.emodnet.eu/erddap/griddap/bathymetry_2022.html

URL template:
  {ENDPOINT}/{dataset_id}.nc?elevation[(lat_min):1:(lat_max)][(lon_min):1:(lon_max)]

Output: data/raw/gebco_2024/GEBCO_2024.nc  (same path build_topobathy_v05.py
expects; the loader auto-detects var names, so the file can be GEBCO or
EMODnet or anything CF-like).

Falls back gracefully: if the dataset_id has changed, prints the candidate
URLs so the user can adjust.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows SSL fix (see memory [[windows_cds_api_pip_system_certs]])
try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import requests

BBOX_LON = (11.95, 12.60)
BBOX_LAT = (37.65, 38.25)

OUT_DIR = Path('data/raw/gebco_2024')   # same path build_topobathy_v05.py expects
OUT_NC = OUT_DIR / 'GEBCO_2024.nc'

ENDPOINT = 'https://erddap.emodnet.eu/erddap/griddap'
# Known dataset id (as of 2024-25); the loader will try these in order.
CANDIDATE_IDS = ['bathymetry_2022', 'EMODnet_Bathymetry_2022', 'bathymetry_2022_DTM']


def try_download(dataset_id):
    url = (f'{ENDPOINT}/{dataset_id}.nc'
           f'?elevation[({BBOX_LAT[0]}):1:({BBOX_LAT[1]})]'
           f'[({BBOX_LON[0]}):1:({BBOX_LON[1]})]')
    print(f'\n  trying: {url}')
    try:
        r = requests.get(url, timeout=180, stream=True)
    except requests.RequestException as e:
        print(f'    request failed: {e}')
        return False
    if r.status_code != 200:
        print(f'    HTTP {r.status_code}: {r.text[:200]}')
        return False
    total = 0
    with open(OUT_NC, 'wb') as f:
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
    print(f'    downloaded {total/1e6:.2f} MB to {OUT_NC}')
    return True


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_NC.exists():
        print(f'  [skip] {OUT_NC} already exists ({OUT_NC.stat().st_size/1e6:.1f} MB)')
        print('  Delete it first if you want to redownload.')
        return

    print(f'Fetching EMODnet bathymetry bbox lon{BBOX_LON} lat{BBOX_LAT}')
    success = False
    for ds_id in CANDIDATE_IDS:
        if try_download(ds_id):
            success = True
            break

    if not success:
        print('\nERROR: all candidate dataset_ids failed.')
        print('Check available datasets at:')
        print(f'  {ENDPOINT}/index.html?searchFor=bathymetry')
        sys.exit(1)

    # Quick sanity peek
    try:
        import xarray as xr
        ds = xr.open_dataset(OUT_NC)
        print(f'\n  vars: {list(ds.data_vars)}')
        print(f'  dims: {dict(ds.sizes)}')
        for name in ('elevation', 'z', 'altitude'):
            if name in ds.data_vars:
                da = ds[name]
                print(f'  {name}: range=({float(da.min()):.0f}, {float(da.max()):.0f}) '
                      f'mean={float(da.mean()):.0f}')
                break
        # check resolution
        for cname in ('latitude', 'lat'):
            if cname in ds.coords and len(ds[cname]) > 1:
                step = float(abs(ds[cname][1] - ds[cname][0]))
                print(f'  {cname} step: {step:.5f} deg (~{step*111000:.1f} m)')
                break
        ds.close()
    except Exception as e:
        print(f'  [warn] could not introspect file: {e}')

    print(f'\nDone. Next: rerun scripts/build_topobathy_v05.py')


if __name__ == '__main__':
    main()
