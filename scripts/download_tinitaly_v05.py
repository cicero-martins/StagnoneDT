"""Process pre-downloaded TINITALY DEM tiles into a single WGS84 GeoTIFF.

TINITALY DEM v1.1 (Tarquini et al. 2023, DOI 10.13127/TINITALY/1.1) is the
authoritative 10m DEM for Italy, distributed by INGV under CC-BY-4.0. The
portal uses a JavaScript-based tile picker without a stable REST API, so the
HUMAN STEP is required:

  1. Open https://tinitaly.pi.ingv.it/Download_Area1_1.html
  2. Select tiles covering lon [11.95, 12.60] x lat [37.65, 38.25]
     For our bbox (Egadi + Marsala/Trapani coast) the 3 tiles to grab are:
       w41580_s10.tif  (covers ~37.6-38.0 N, 12.0-12.6 E - Marsala/Stagnone)
       w42075_s10.tif  (covers ~37.95-38.25 N, 11.5-12.1 E - Marettimo)
       w42080_s10.tif  (covers ~37.95-38.30 N, 12.0-12.6 E - Trapani/Levanzo)
     All TINITALY tiles are 50x50 km in EPSG:32632 (UTM zone 32N).
  3. Save downloaded .tif files (in EPSG:32632 UTM 32N) to:
       data/raw/tinitaly_v05_raw/

THEN run this script: it reprojects each tile to WGS84, mosaics, clips to
bbox, and writes data/raw/tinitaly_v05/tinitaly_v05_wgs84.tif ready for
build_topobathy_v05.py.

If TINITALY tiles are not available, you can skip this and rely on the
fallback Copernicus DEM GLO-30 alone (see download_copernicus_dem_v05.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.merge import merge
from rasterio.windows import from_bounds

BBOX_LON = (11.95, 12.60)
BBOX_LAT = (37.65, 38.25)

RAW_DIR = Path('data/raw/tinitaly_v05_raw')
OUT_DIR = Path('data/raw/tinitaly_v05')
MOSAIC = OUT_DIR / 'tinitaly_v05_wgs84.tif'

DST_CRS = 'EPSG:4326'


def reproject_tile(src_path, dst_path):
    print(f'  reproject {src_path.name} -> WGS84')
    with rasterio.open(src_path) as src:
        if src.crs is None:
            print(f'  [warn] {src_path.name} has no CRS; assuming EPSG:32633')
            src_crs = 'EPSG:32633'
        else:
            src_crs = src.crs
        transform, width, height = calculate_default_transform(
            src_crs, DST_CRS, src.width, src.height, *src.bounds)
        meta = src.meta.copy()
        meta.update({'crs': DST_CRS, 'transform': transform,
                     'width': width, 'height': height, 'compress': 'lzw'})
        with rasterio.open(dst_path, 'w', **meta) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src_crs,
                    dst_transform=transform,
                    dst_crs=DST_CRS,
                    resampling=Resampling.bilinear,
                )


def mosaic_and_clip(tile_paths, out_path, bbox_lon, bbox_lat):
    print(f'\nMosaic {len(tile_paths)} reprojected tiles -> {out_path}')
    srcs = [rasterio.open(p) for p in tile_paths]
    arr, transform = merge(srcs, bounds=(bbox_lon[0], bbox_lat[0],
                                         bbox_lon[1], bbox_lat[1]))
    meta = srcs[0].meta.copy()
    meta.update({'height': arr.shape[1], 'width': arr.shape[2],
                 'transform': transform, 'compress': 'lzw'})
    with rasterio.open(out_path, 'w', **meta) as dst:
        dst.write(arr)
    for s in srcs:
        s.close()
    print(f'  shape: {arr.shape}, bounds: {(bbox_lon[0], bbox_lat[0], bbox_lon[1], bbox_lat[1])}')


def main():
    if not RAW_DIR.exists() or not list(RAW_DIR.glob('*.tif')):
        print(f'ERROR: no .tif tiles in {RAW_DIR}')
        print('Please follow the manual download step in the docstring.')
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = OUT_DIR / '_reprojected'
    tmp_dir.mkdir(exist_ok=True)

    raw_tiles = sorted(RAW_DIR.glob('*.tif'))
    print(f'Found {len(raw_tiles)} raw tiles in {RAW_DIR}')

    reprojected = []
    for raw in raw_tiles:
        dst = tmp_dir / raw.name
        if not dst.exists():
            reproject_tile(raw, dst)
        else:
            print(f'  [skip] {dst.name} already reprojected')
        reprojected.append(dst)

    mosaic_and_clip(reprojected, MOSAIC, BBOX_LON, BBOX_LAT)
    print(f'\nDone. Mosaic at: {MOSAIC}')
    print('Next: scripts/build_topobathy_v05.py')


if __name__ == '__main__':
    main()
