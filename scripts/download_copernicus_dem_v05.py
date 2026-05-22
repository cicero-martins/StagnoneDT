"""Download Copernicus DEM GLO-30 tiles covering the Stagnone v05 mesh bbox.

Anonymous S3 access (no credentials). Tiles are 1degx1deg GeoTIFF in EPSG:4326.
For bbox lon [11.95, 12.60] x lat [37.65, 38.25] we need 2 tiles:
  - N37_00_E011_00 (covers lon 11-12, lat 37-38)
  - N37_00_E012_00 (covers lon 12-13, lat 37-38)
  - N38_00_E011_00 (covers lon 11-12, lat 38-39)
  - N38_00_E012_00 (covers lon 12-13, lat 38-39)

This is the FALLBACK source (30m resolution) per plan
~/.claude/plans/guarda-na-mem-ria-planejamento-essas-dapper-fountain.md.
TINITALY 10m is the primary land DEM; see scripts/download_tinitaly_v05.py.

Output: data/raw/copernicus_dem_v05/<tile>.tif + mosaic copernicus_dem_v05_wgs84.tif
"""
from __future__ import annotations

import sys
from pathlib import Path

import boto3
import rasterio
from botocore import UNSIGNED
from botocore.config import Config
from rasterio.merge import merge

BBOX_LON = (11.95, 12.60)
BBOX_LAT = (37.65, 38.25)

OUT_DIR = Path('data/raw/copernicus_dem_v05')
MOSAIC = OUT_DIR / 'copernicus_dem_v05_wgs84.tif'

BUCKET = 'copernicus-dem-30m'
# Naming convention per registry.opendata.aws/copernicus-dem/
# Copernicus_DSM_COG_10_N<lat>_00_E<lon>_00_DEM/Copernicus_DSM_COG_10_N<lat>_00_E<lon>_00_DEM.tif


def tile_keys(bbox_lon, bbox_lat):
    lon_min = int(bbox_lon[0])
    lon_max = int(bbox_lon[1])
    lat_min = int(bbox_lat[0])
    lat_max = int(bbox_lat[1])
    keys = []
    for lon in range(lon_min, lon_max + 1):
        for lat in range(lat_min, lat_max + 1):
            stem = f'Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM'
            keys.append((stem, f'{stem}/{stem}.tif'))
    return keys


def download_tile(s3, stem, key, out_dir):
    out = out_dir / f'{stem}.tif'
    if out.exists():
        print(f'  [skip] {out.name} already exists')
        return out
    print(f'  [get ] s3://{BUCKET}/{key}')
    try:
        s3.download_file(BUCKET, key, str(out))
    except Exception as e:
        print(f'  [fail] {key}: {e}')
        return None
    return out


def mosaic_tiles(tile_paths, out_path):
    print(f'\nMosaicking {len(tile_paths)} tiles -> {out_path}')
    srcs = [rasterio.open(p) for p in tile_paths]
    arr, transform = merge(srcs)
    meta = srcs[0].meta.copy()
    meta.update({'height': arr.shape[1], 'width': arr.shape[2],
                 'transform': transform, 'compress': 'lzw'})
    with rasterio.open(out_path, 'w', **meta) as dst:
        dst.write(arr)
    for s in srcs:
        s.close()
    print(f'  shape: {arr.shape}, dtype: {arr.dtype}, nodata: {meta.get("nodata")}')


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED,
                                          region_name='eu-central-1'))
    keys = tile_keys(BBOX_LON, BBOX_LAT)
    print(f'Expected tiles for bbox lon{BBOX_LON} lat{BBOX_LAT}: {len(keys)}')
    for stem, _ in keys:
        print(f'  {stem}')

    downloaded = []
    for stem, key in keys:
        p = download_tile(s3, stem, key, OUT_DIR)
        if p is not None:
            downloaded.append(p)

    if not downloaded:
        print('No tiles downloaded - abort.')
        sys.exit(1)

    mosaic_tiles(downloaded, MOSAIC)
    print(f'\nDone. Mosaic at: {MOSAIC}')


if __name__ == '__main__':
    main()
