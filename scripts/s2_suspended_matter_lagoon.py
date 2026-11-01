"""Suspended matter in the Stagnone from Sentinel-2 L2A, 28 June to 13 July 2025.

Reads the Sentinel-2 L2A scenes of tile 33STB from the public Earth Search
catalogue on AWS and applies the single-band algorithm of Nechad et al. (2010)
at 665 nm,

    T = A rho_w / (1 - rho_w / C),   A = 355.85 g m-3,  C = 0.1728,

with the water reflectance rho_w taken as the Sen2Cor bottom-of-atmosphere
reflectance of B04 less that of B11 (1610 nm), which removes sun glint and
residual haze. Pixels under cloud, cloud shadow, cirrus, saturation or no data
in the scene classification are left out, together with those classed as
vegetation or bare soil, which lie on the shore within reach of the lagoon
mask. The lagoon is that of the renewal computations (renewal_common.py, the
samples of lagoon_tracer_init.xyz within 150 m), and statistics are taken over
the lagoon pixels valid in every scene of the same relative orbit, and also, for
the median and the 95th percentile, over the lagoon pixels valid in the scene
alone (columns tsm_own_p50 and tsm_own_p95). The method and
results are in docs/sentinel2_suspended_matter.md.

Earth Search has already removed the BOA_ADD_OFFSET of processing baseline
04.00 and later (property earthsearch:boa_offset_applied) while the asset
metadata still lists an offset of -0.1; the offset is applied only when the
property is absent or false.

The bands are downloaded whole by requests, which uses the Windows certificate
store, since the TLS stack of GDAL on this host rejects the certificate chain
of the bucket.

Usage:  python s2_suspended_matter_lagoon.py
Writes: data/processed/s2_tsm_july2025.csv (statistics per scene)
        data/raw/satellite/s2_cogs_july2025/s2_tsm_maps.npz (maps for the figures)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pip_system_certs.wrapt_requests  # noqa: F401
import rasterio
import rasterio.warp
import requests
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from renewal_common import lagoon_faces

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'processed' / 's2_tsm_july2025.csv'
CACHE = ROOT / 'data' / 'raw' / 'satellite' / 's2_cogs_july2025'
MASK_DIR = ROOT / 'model' / '_ctrl_noveg_seg'   # lagoon_tracer_init.xyz, the same in every member
STAC = 'https://earth-search.aws.element84.com/v1/search'
BBOX = (12.42, 37.80, 12.49, 37.91)
WINDOW = ('2025-06-28T00:00:00Z', '2025-07-14T00:00:00Z')
A, C = 355.85, 0.1728          # Nechad et al. (2010), 665 nm, g m-3
RHO_MAX = 0.8 * C              # upper limit of validity of the retrieval
RHO_NOISE = -0.01              # negatives above this count as clear water
SCL_OUT = (0, 1, 3, 4, 5, 8, 9, 10)  # no data, saturated, shadow, vegetation, bare soil, cloud x2, cirrus

CACHE.mkdir(parents=True, exist_ok=True)


def fetch(href):
    f = CACHE / '_'.join(href.split('/')[-2:])
    if not f.exists():
        with requests.get(href, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(f.with_suffix('.part'), 'wb') as h:
                for chunk in r.iter_content(1 << 20):
                    h.write(chunk)
        f.with_suffix('.part').rename(f)
    return f


def reflectance(item, key, shape=None):
    asset = item['assets'][key]
    rb = (asset.get('raster:bands') or [{}])[0]
    offset = 0.0 if item['properties'].get('earthsearch:boa_offset_applied') else rb.get('offset', -0.1)
    with rasterio.open(fetch(asset['href'])) as src:
        b = transform_bounds('EPSG:4326', src.crs, *BBOX)
        win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        dn = src.read(1, window=win, out_shape=shape)
        if key == 'scl':
            return dn, None, None
        rho = np.where(dn > 0, dn * rb.get('scale', 1e-4) + offset, np.nan)
        return rho, src.window_transform(win), src.crs


def orbit(item):
    # relative orbit is missing from the item properties; the overpass time
    # separates the two orbits over the tile (R079 near 10:00, R122 near 10:10)
    return 'R122' if item['properties']['datetime'][14:16] == '10' else 'R079'


q = {'collections': ['sentinel-2-l2a'], 'bbox': list(BBOX), 'datetime': '/'.join(WINDOW), 'limit': 50}
items = [i for i in requests.post(STAC, json=q, timeout=60).json()['features'] if '_33STB_' in i['id']]
items.sort(key=lambda i: i['properties']['datetime'])

scenes = []
for it in items:
    red, tr, crs = reflectance(it, 'red')
    swir, _, _ = reflectance(it, 'swir16', red.shape)
    scl, _, _ = reflectance(it, 'scl', red.shape)
    rgb = np.stack([red, reflectance(it, 'green', red.shape)[0], reflectance(it, 'blue', red.shape)[0]])
    rho_w = red - swir
    ok = ~np.isin(scl, SCL_OUT) & np.isfinite(rho_w) & (rho_w > RHO_NOISE) & (rho_w < RHO_MAX)
    rho_w = np.clip(rho_w, 0, None)
    tsm = np.where(ok, A * rho_w / (1 - rho_w / C), np.nan)
    scenes.append(dict(item=it, red=red, swir=swir, scl=scl, rgb=rgb, ok=ok, tsm=tsm))
    print(it['id'], 'read', flush=True)

rows_, cols_ = np.indices(scenes[0]['red'].shape)
px, py = rasterio.transform.xy(tr, rows_.ravel(), cols_.ravel())
lon, lat = rasterio.warp.transform(crs, 'EPSG:4326', px, py)
lagoon = lagoon_faces(MASK_DIR, np.array(lon), np.array(lat)).reshape(scenes[0]['red'].shape)

rows = []
common = {}
for orb in sorted({orbit(s['item']) for s in scenes}):
    sub = [s for s in scenes if orbit(s['item']) == orb]
    common[orb] = lagoon & np.logical_and.reduce([s['ok'] for s in sub])
    for s in sub:
        it = s['item']
        t = s['tsm'][common[orb]]
        own = s['tsm'][lagoon & s['ok']]
        rows.append({'id': it['id'], 'datetime': it['properties']['datetime'][:16], 'orbit': orb,
                     'cloud_tile': it['properties'].get('eo:cloud_cover'),
                     'n_lagoon': int(lagoon.sum()), 'n_valid': int((lagoon & s['ok']).sum()),
                     'n_common': int(common[orb].sum()),
                     'rho_w_p50': np.median(np.clip(s['red'] - s['swir'], 0, None)[common[orb]]),
                     **{f'tsm_p{p}': np.percentile(t, p) for p in (25, 50, 75, 95)},
                     **{f'tsm_own_p{p}': np.percentile(own, p) for p in (50, 95)}})
df = pd.DataFrame(rows).sort_values('datetime')
df.to_csv(OUT, index=False, float_format='%.4g')
print(df.round(3).to_string(index=False))

np.savez_compressed(
    CACHE / 's2_tsm_maps.npz',
    ids=np.array([s['item']['id'] for s in scenes]),
    times=np.array([s['item']['properties']['datetime'][:16] for s in scenes]),
    orbits=np.array([orbit(s['item']) for s in scenes]),
    red=np.stack([s['red'] for s in scenes]).astype('float32'),
    swir=np.stack([s['swir'] for s in scenes]).astype('float32'),
    scl=np.stack([s['scl'] for s in scenes]).astype('uint8'),
    rgb=np.stack([s['rgb'] for s in scenes]).astype('float32'),
    tsm=np.stack([s['tsm'] for s in scenes]).astype('float32'),
    ok=np.stack([s['ok'] for s in scenes]),
    lagoon=lagoon, common_R079=common['R079'], common_R122=common['R122'],
    extent=np.array(rasterio.transform.array_bounds(*lagoon.shape, tr)), crs=str(crs))
print('->', OUT)
