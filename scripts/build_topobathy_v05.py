"""Build seamless topobathy raster for mesh v05.

Merges multiple sources on a single 10m regular grid in WGS84:

  Source          | Role               | Path
  ----------------|--------------------|--------------------------------------
  TINITALY 10m    | Land (z > 0)       | data/raw/tinitaly_v05/tinitaly_v05_wgs84.tif
  Copernicus 30m  | Land gap-fill      | data/raw/copernicus_dem_v05/copernicus_dem_v05_wgs84.tif
  bat20m_stgnlg   | Lagoon bathy       | C:/Users/Unipa/Documents/StagnoneLagoon/Datasets/bat20m_stgnlg_Adjusted.xyz
  GEBCO 2024      | Offshore bathy     | data/raw/gebco_2024/GEBCO_2024.nc  (optional)

Merge rules (priority high → low):
  - Inside any sicily_v05.ldb polygon (LAND mask):
      1. TINITALY where defined
      2. Copernicus DEM elsewhere
      → final z > 0
  - Outside the polygons (SEA mask):
      1. bat20m_stgnlg_Adjusted where in lagoon bbox
      2. GEBCO 2024 elsewhere
      → final z < 0 (FM convention: bathy = bottom level below MSL, negative)
  - Buffer ±50 m around coastline: gaussian blend land↔sea to avoid stair-step.

Convention: in the OUTPUT NetCDF we keep z (signed) — land positive,
sea negative. The mesh build (build_mesh_v05.py) will sign-correct to
FM's bedlevel convention if needed.

Output:
  data/processed/mesh_v05/topobathy_combined.nc   (xarray DataArray, EPSG:4326)
  10m grid covering lon [11.95, 12.60] x lat [37.65, 38.25]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from scipy.ndimage import gaussian_filter
from shapely.geometry import Polygon, Point
import geopandas as gpd

BBOX_LON = (11.95, 12.60)
BBOX_LAT = (37.65, 38.25)
TARGET_RES_DEG = 1e-4   # ~11 m at this latitude

TINITALY = Path('data/raw/tinitaly_v05/tinitaly_v05_wgs84.tif')
COPERNICUS = Path('data/raw/copernicus_dem_v05/copernicus_dem_v05_wgs84.tif')
BAT20M = Path(r'C:/Users/Unipa/Documents/StagnoneLagoon/Datasets/bat20m_stgnlg_Adjusted.xyz')
GEBCO = Path('data/raw/gebco_2024/GEBCO_2024.nc')   # optional
LDB = Path('data/processed/sicily_v05.ldb')

OUT_DIR = Path('data/processed/mesh_v05')
OUT_NC = OUT_DIR / 'topobathy_combined.nc'

COAST_BUFFER_DEG = 5e-4   # ~55 m blend buffer either side of coastline


def make_target_grid():
    lon = np.arange(BBOX_LON[0], BBOX_LON[1] + TARGET_RES_DEG, TARGET_RES_DEG)
    lat = np.arange(BBOX_LAT[0], BBOX_LAT[1] + TARGET_RES_DEG, TARGET_RES_DEG)
    return lon, lat


def resample_geotiff_to_grid(geotiff_path, lon, lat, name):
    """Open a GeoTIFF and reproject to our regular grid (no fancy CRS — both WGS84)."""
    with rasterio.open(geotiff_path) as src:
        dst_transform = from_origin(lon[0], lat[-1],
                                    lon[1] - lon[0], lat[1] - lat[0])
        dst = np.full((len(lat), len(lon)), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs or 'EPSG:4326',
            dst_transform=dst_transform,
            dst_crs='EPSG:4326',
            resampling=Resampling.bilinear,
            dst_nodata=np.nan,
        )
        # rasterio writes top-down (lat decreasing); flip to lat ascending
        dst = np.flipud(dst)
        # Mask sentinel nodata
        nd = src.nodata
        if nd is not None:
            dst = np.where(dst == nd, np.nan, dst)
        # Filter outlandish values (Copernicus DEM uses -32767 nodata, TINITALY -9999)
        dst = np.where(dst < -1000, np.nan, dst)
        dst = np.where(dst > 5000, np.nan, dst)
    print(f'  {name}: valid={np.isfinite(dst).sum()}/{dst.size} '
          f'range=({np.nanmin(dst):.1f}, {np.nanmax(dst):.1f})')
    return dst


def load_bat20m(lon, lat, src_path):
    """Load UTM33N XYZ, reproject to lon/lat grid via griddata."""
    from pyproj import Transformer
    from scipy.interpolate import griddata
    print(f'  loading {src_path.name} ({src_path.stat().st_size/1e6:.1f} MB)')
    arr = np.loadtxt(src_path)
    x_utm, y_utm, z = arr[:, 0], arr[:, 1], arr[:, 2]
    print(f'    raw points: {len(z)}, z range: ({z.min():.2f}, {z.max():.2f})')
    tr = Transformer.from_crs('EPSG:32633', 'EPSG:4326', always_xy=True)
    lon_pts, lat_pts = tr.transform(x_utm, y_utm)
    # Restrict to bbox + a small margin
    mask = ((lon_pts >= BBOX_LON[0] - 0.01) & (lon_pts <= BBOX_LON[1] + 0.01) &
            (lat_pts >= BBOX_LAT[0] - 0.01) & (lat_pts <= BBOX_LAT[1] + 0.01))
    lon_pts, lat_pts, z = lon_pts[mask], lat_pts[mask], z[mask]
    print(f'    in bbox: {len(z)} points')
    # Grid via griddata (linear; may be slow for 8M points — subsample if needed)
    if len(z) > 2_000_000:
        # downsample to 2M for griddata
        idx = np.random.default_rng(0).choice(len(z), 2_000_000, replace=False)
        lon_pts, lat_pts, z = lon_pts[idx], lat_pts[idx], z[idx]
        print(f'    downsampled to {len(z)} for griddata')
    LON2D, LAT2D = np.meshgrid(lon, lat)
    grid = griddata((lon_pts, lat_pts), z, (LON2D, LAT2D),
                    method='linear', fill_value=np.nan)
    print(f'  bat20m grid valid={np.isfinite(grid).sum()}/{grid.size}')
    return grid


def load_gebco(lon, lat, src_path):
    if not src_path.exists():
        print(f'  [skip] GEBCO not found at {src_path} — offshore gap will rely on bat20m extrapolation')
        return None
    print(f'  loading {src_path.name}')
    ds = xr.open_dataset(src_path)
    da = ds['elevation'] if 'elevation' in ds else list(ds.data_vars.values())[0]
    da = da.sel(lon=slice(BBOX_LON[0] - 0.05, BBOX_LON[1] + 0.05),
                lat=slice(BBOX_LAT[0] - 0.05, BBOX_LAT[1] + 0.05))
    out = da.interp(lon=lon, lat=lat, method='linear').values.astype(np.float32)
    print(f'  GEBCO grid valid={np.isfinite(out).sum()}/{out.size} '
          f'range=({np.nanmin(out):.1f}, {np.nanmax(out):.1f})')
    return out


def land_mask_from_ldb(ldb_path, lon, lat):
    """Parse sicily_v05.ldb into polygons; rasterize as boolean land mask on grid."""
    print(f'  parsing {ldb_path}')
    polys = []
    with open(ldb_path) as f:
        lines = [ln.rstrip() for ln in f if not ln.startswith('*')]
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        # Class name line
        name = s
        i += 1
        if i >= len(lines):
            break
        # Header: "<n_points>    2"
        parts = lines[i].split()
        if len(parts) < 1:
            i += 1
            continue
        try:
            n = int(parts[0])
        except ValueError:
            i += 1
            continue
        i += 1
        coords = []
        for _ in range(n):
            if i >= len(lines):
                break
            try:
                x, y = lines[i].split()[:2]
                coords.append((float(x), float(y)))
            except ValueError:
                pass
            i += 1
        if len(coords) >= 3:
            try:
                polys.append((name, Polygon(coords)))
            except Exception as e:
                print(f'    [warn] could not build Polygon for {name}: {e}')
    print(f'  found {len(polys)} polygons:')
    for name, p in polys:
        print(f'    {name}: {len(p.exterior.coords)} pts, area_deg2={p.area:.5f}')

    # Rasterize: for each grid cell, is it inside any polygon?
    LON2D, LAT2D = np.meshgrid(lon, lat)
    from rasterio.features import rasterize
    transform = from_origin(lon[0], lat[-1], lon[1] - lon[0], lat[1] - lat[0])
    geoms = [(p, 1) for _, p in polys]
    mask = rasterize(geoms, out_shape=(len(lat), len(lon)), transform=transform,
                     fill=0, dtype=np.uint8)
    mask = np.flipud(mask).astype(bool)
    print(f'  land mask: {mask.sum()}/{mask.size} cells inside polygons')
    return mask, polys


def coastline_blend_weights(land_mask, buffer_pix):
    """Distance-from-coast soft weight: 1 in deep land/sea, fade to 0.5 at coast."""
    from scipy.ndimage import distance_transform_edt
    # distance to nearest sea pixel (inside land mass)
    dist_to_sea = distance_transform_edt(land_mask)
    dist_to_land = distance_transform_edt(~land_mask)
    # min distance to coast in either direction
    dist = np.where(land_mask, dist_to_sea, dist_to_land)
    # Smooth weight: 0.5 at coast, 1.0 at >= buffer_pix
    w = np.clip(dist / buffer_pix, 0, 1) * 0.5 + 0.5
    return w


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lon, lat = make_target_grid()
    print(f'Target grid: {len(lon)} x {len(lat)} (lon, lat); res ~{TARGET_RES_DEG:.5f} deg (~{TARGET_RES_DEG*111000:.1f} m)')

    print('\n[1/5] Land mask from sicily_v05.ldb')
    land_mask, polys = land_mask_from_ldb(LDB, lon, lat)

    print('\n[2/5] TINITALY 10m land DEM (primary)')
    if TINITALY.exists():
        tinitaly = resample_geotiff_to_grid(TINITALY, lon, lat, 'TINITALY')
    else:
        print(f'  [skip] {TINITALY} not found — run download_tinitaly_v05.py first')
        tinitaly = np.full((len(lat), len(lon)), np.nan, dtype=np.float32)

    print('\n[3/5] Copernicus DEM 30m (gap-fill)')
    if COPERNICUS.exists():
        cop = resample_geotiff_to_grid(COPERNICUS, lon, lat, 'Copernicus')
    else:
        print(f'  [skip] {COPERNICUS} not found — run download_copernicus_dem_v05.py first')
        cop = np.full((len(lat), len(lon)), np.nan, dtype=np.float32)

    print('\n[4/5] bat20m_stgnlg_Adjusted lagoon bathy (primary sea)')
    if BAT20M.exists():
        bat20m = load_bat20m(lon, lat, BAT20M)
    else:
        print(f'  [skip] {BAT20M} not found')
        bat20m = np.full((len(lat), len(lon)), np.nan, dtype=np.float32)

    print('\n[5/5] GEBCO 2024 offshore (gap-fill, optional)')
    gebco = load_gebco(lon, lat, GEBCO)

    # === MERGE ===
    print('\nMerging by priority + LDB mask…')
    z = np.full((len(lat), len(lon)), np.nan, dtype=np.float32)

    # LAND priority: TINITALY > Copernicus, on cells inside any polygon
    land_z = np.where(np.isfinite(tinitaly), tinitaly,
                      np.where(np.isfinite(cop), cop, np.nan))
    # Sanity: land cells should be >= 0; if a negative came in (e.g. coastline
    # uncertainty), clip to 0 to avoid sign confusion with sea.
    land_z = np.where(land_mask & (land_z < 0), 0.0, land_z)

    # SEA priority: bat20m > GEBCO, on cells outside polygons
    if gebco is not None:
        sea_z = np.where(np.isfinite(bat20m), bat20m,
                         np.where(np.isfinite(gebco), gebco, np.nan))
    else:
        sea_z = bat20m
    # Sanity: sea cells should be < 0; if positive (likely artifact), clip to -0.1
    sea_z = np.where(~land_mask & (sea_z > 0), -0.1, sea_z)

    z = np.where(land_mask, land_z, sea_z)

    n_nan = np.isnan(z).sum()
    print(f'  combined coverage: {(~np.isnan(z)).sum()}/{z.size} '
          f'(missing {n_nan} cells = {100*n_nan/z.size:.1f}%)')
    if n_nan > 0:
        # Fill remaining NaNs with nearest valid via scipy gaussian fill
        from scipy.ndimage import distance_transform_edt
        mask_valid = ~np.isnan(z)
        indices = distance_transform_edt(~mask_valid, return_distances=False,
                                          return_indices=True)
        z = z[tuple(indices)]
        print('  filled remaining NaN by nearest-neighbour')

    # Optional: gaussian blend over coast buffer to soften the seam
    buffer_pix = max(1, int(COAST_BUFFER_DEG / TARGET_RES_DEG))
    if buffer_pix >= 1:
        print(f'  gaussian blend over coast (sigma={buffer_pix/2:.1f} pixels)')
        smoothed = gaussian_filter(z, sigma=buffer_pix / 2)
        # Only apply blend within buffer_pix of coast
        from scipy.ndimage import distance_transform_edt
        coast_dist = np.minimum(distance_transform_edt(land_mask),
                                distance_transform_edt(~land_mask))
        coast_w = np.clip(1 - coast_dist / buffer_pix, 0, 1)
        z = (1 - coast_w) * z + coast_w * smoothed

    # Stats
    z_land = z[land_mask]
    z_sea = z[~land_mask]
    print(f'\nFinal stats:')
    print(f'  land cells: {land_mask.sum()}  z range=({np.min(z_land):.1f}, {np.max(z_land):.1f}) mean={z_land.mean():.1f}')
    print(f'  sea  cells: {(~land_mask).sum()}  z range=({np.min(z_sea):.1f}, {np.max(z_sea):.1f}) mean={z_sea.mean():.1f}')

    # === WRITE ===
    da = xr.DataArray(
        z.astype(np.float32),
        dims=('lat', 'lon'),
        coords={'lat': lat.astype(np.float32), 'lon': lon.astype(np.float32)},
        name='topobathy',
        attrs={
            'long_name': 'topo-bathymetry (signed: z>0 land, z<0 sea)',
            'units': 'm',
            'sources': 'TINITALY 10m (land), Copernicus DEM 30m (land gap), '
                       'bat20m_stgnlg_Adjusted (lagoon), GEBCO 2024 (offshore)',
            'coastline_mask': 'data/processed/sicily_v05.ldb',
            'crs': 'EPSG:4326',
        },
    )
    ds = da.to_dataset()
    ds['land_mask'] = xr.DataArray(
        land_mask.astype(np.uint8), dims=('lat', 'lon'),
        attrs={'long_name': '1 = inside sicily_v05.ldb polygon (land)'}
    )
    ds.attrs['title'] = 'Stagnone v05 seamless topobathy'
    ds.attrs['conventions'] = 'CF-1.8'
    encoding = {'topobathy': {'zlib': True, 'complevel': 4},
                'land_mask': {'zlib': True, 'complevel': 4}}
    ds.to_netcdf(OUT_NC, encoding=encoding)
    print(f'\nWrote {OUT_NC} ({OUT_NC.stat().st_size/1e6:.1f} MB)')
    print('Next: scripts/diag_topobathy_v05.py for sanity checks')


if __name__ == '__main__':
    main()
