"""
Build a high-resolution (50 m) land mask for the Stagnone area from the FM v04
mesh — captures small features like Isola della Scuola that the LDB
(`sicily2.ldb`) is missing.

Method: rasterise the FM mesh's dry faces (bedlevel >= -0.05 m) at 50 m onto a
regular lat/lon grid via nearest-face cKDTree query. Cells whose nearest face
is dry AND within ~150 m → land (1). Cells with no nearby face (offshore Med,
outside FM domain) → 0, so the figure won't paint Marettimo / Sicily-mainland
coasts as land — those still come from sicily2.ldb as a vector outline.

Output:
  data/processed/v04_land_mask_50m.nc
    - lat (~880), lon (~1100), land (int8: 1=land, 0=water)
"""
from pathlib import Path
import numpy as np
import xarray as xr
import dfm_tools as dfmt
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
V04 = ROOT / 'model' / 'dflowfm_v04' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
OUT = ROOT / 'data' / 'processed' / 'v04_land_mask_50m.nc'

# Target grid — covers the Stagnone area + offshore approach
LON_MIN, LON_MAX = 12.00, 12.55
LAT_MIN, LAT_MAX = 37.70, 38.05
DX = 0.0005   # ~46 m at lat 37.87
DY = 0.0005   # ~55 m

LAND_BL_THRESH = -0.05    # match the regrid script
NEAR_FACE_DEG  = 0.0015   # ~150 m: only paint pixels with a nearby FM face


def main():
    print(f'Opening {V04 / "Stagnone_dxy01_15m_0*_map.nc"}...')
    ds = dfmt.open_partitioned_dataset(str(V04 / 'Stagnone_dxy01_15m_0*_map.nc'))
    fx = np.asarray(ds.grid.face_x)
    fy = np.asarray(ds.grid.face_y)
    bl = np.asarray(ds['mesh2d_flowelem_bl'].values).flatten()
    is_dry = bl >= LAND_BL_THRESH
    print(f'Mesh faces: {len(fx)} ({is_dry.sum()} dry, {(~is_dry).sum()} wet)')

    lons = np.arange(LON_MIN, LON_MAX + DX/2, DX)
    lats = np.arange(LAT_MIN, LAT_MAX + DY/2, DY)
    LON, LAT = np.meshgrid(lons, lats)
    print(f'Output grid: {len(lons)} x {len(lats)} = {len(lons)*len(lats)} cells')

    tree = cKDTree(np.column_stack([fx, fy]))
    dists, nearest = tree.query(np.column_stack([LON.ravel(), LAT.ravel()]))
    near = dists < NEAR_FACE_DEG
    land = is_dry[nearest] & near

    land_grid = land.reshape(LAT.shape).astype(np.int8)
    print(f'Land pixels: {land_grid.sum()} ({100*land_grid.mean():.1f}% of {land_grid.size})')

    ds_out = xr.Dataset(
        {'land': (('lat', 'lon'), land_grid, {
            'long_name': 'Land binary mask from FM v04 mesh dry faces',
            'comment': f'1 if nearest FM face has bl >= {LAND_BL_THRESH} m AND within {NEAR_FACE_DEG} deg',
        })},
        coords={
            'lat': ('lat', lats, {'units': 'degrees_north', 'standard_name': 'latitude'}),
            'lon': ('lon', lons, {'units': 'degrees_east', 'standard_name': 'longitude'}),
        },
        attrs={
            'Conventions': 'CF-1.8',
            'source': 'Derived from FM v04 mesh face bedlevel via build_v04_land_mask_hires.py',
            'resolution_m': '~50',
        },
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ds_out.to_netcdf(OUT, encoding={'land': {'zlib': True, 'complevel': 6}})
    print(f'\nWrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)')


if __name__ == '__main__':
    main()
