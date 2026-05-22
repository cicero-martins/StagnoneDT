"""Build Stagnone v05 mesh via dfm_tools/meshkernel automation.

Workflow:
  1. Read sicily_v05.ldb → GeoDataFrame of land polygons (closing mainland east)
  2. Read combined bathy XYZ → rasterize to regular grid (sea only, z<0)
  3. dfmt.make_basegrid() — base regular grid covering bbox
  4. dfmt.refine_basegrid() — refine based on bathy depth (shallow=fine, deep=coarse)
  5. dfmt.meshkernel_delete_withgdf() — delete cells inside land polygons
  6. dfmt.generate_bndpli_cutland() — auto-generate .pli boundary
  7. dfmt.meshkernel_to_UgridDataset() + save Stagnone_v05_net.nc

Output: data/processed/mesh_v05/
  - Stagnone_v05_net.nc
  - Stagnone_v05.pli
  - bathy_gridded.nc (intermediate, debug)
  - mesh_v05_overview.png

Usage:
    python scripts/build_mesh_v05.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point

import dfm_tools as dfmt
from meshkernel import MeshKernel, GeometryList, MeshRefinementParameters, RefinementType


# ============ INPUTS ============
SICILY_LDB = Path('data/processed/sicily_v05.ldb')
# Seamless topobathy from MDT pipeline (build_topobathy_v05.py). Signed: land z>0, sea z<0.
TOPOBATHY_NC = Path('data/processed/mesh_v05/topobathy_combined.nc')
OUT_DIR = Path('data/processed/mesh_v05')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============ DOMAIN ============
LON_MIN, LON_MAX = 11.95, 12.60
LAT_MIN, LAT_MAX = 37.65, 38.25

# Base grid resolution (~500m at 37.95°N)
DX_BASE = 0.005
DY_BASE = 0.005

# Refinement parameters
MIN_EDGE_SIZE_M = 15.0       # smallest allowed cell (m) — matches current lagoon resolution
MAX_COURANT = 0.2            # CFL-like refinement criterion (smaller = finer)

# CRS
CRS = 'EPSG:4326'


# ============ STEP 1: parse sicily_v05.ldb → GeoDataFrame ============
def parse_ldb_to_polys(path):
    """Returns dict {name: np.array((N,2))}."""
    polys = {}
    cur_name = None
    cur_pts = []
    n_expect = 0
    with open(path) as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith('*'):
                continue
            parts = s.split()
            if len(parts) == 2:
                # could be header "<n> 2" or data point
                try:
                    a, b = float(parts[0]), float(parts[1])
                    # heuristic: header if a is integer-ish AND second is 2.0
                    if a > 10 and a == int(a) and b == 2.0:
                        n_expect = int(a)
                        continue
                    # otherwise data point
                    cur_pts.append((a, b))
                    continue
                except ValueError:
                    pass
            # otherwise a name header
            if cur_pts and cur_name:
                polys[cur_name] = np.array(cur_pts)
            cur_name = s
            cur_pts = []
    if cur_pts and cur_name:
        polys[cur_name] = np.array(cur_pts)
    return polys


print('=== Step 1: parse sicily_v05.ldb ===')
polys = parse_ldb_to_polys(SICILY_LDB)
for name, p in polys.items():
    print(f'  {name}: {len(p)} pts, bbox lon=[{p[:,0].min():.4f},{p[:,0].max():.4f}] lat=[{p[:,1].min():.4f},{p[:,1].max():.4f}]')

# Build GeoDataFrame of land polygons
geoms = []
geom_names = []

# Marettimo, Favignana, Levanzo: closed polygons (close them defensively)
for name in ['Marettimo', 'Favignana', 'Levanzo']:
    if name not in polys:
        continue
    pts = polys[name]
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[:1]])
    poly = Polygon(pts)
    if poly.is_valid and poly.area > 0:
        geoms.append(poly)
        geom_names.append(name)

# StagnoneBarrier: may be multiple sub-polylines concatenated. Try as Polygon, fallback to splitting.
if 'StagnoneBarrier' in polys:
    pts = polys['StagnoneBarrier']
    # Detect jumps (split sub-polylines)
    lat_avg = pts[:, 1].mean()
    dx_m = (pts[1:, 0] - pts[:-1, 0]) * 111000 * np.cos(np.radians(lat_avg))
    dy_m = (pts[1:, 1] - pts[:-1, 1]) * 111000
    dist = np.sqrt(dx_m**2 + dy_m**2)
    splits = np.where(dist > 500)[0]   # 500m jump = new sub-polyline
    start = 0
    for j in list(splits) + [len(pts) - 1]:
        seg = pts[start:j + 1]
        if len(seg) > 10:
            if not np.allclose(seg[0], seg[-1]):
                seg = np.vstack([seg, seg[:1]])
            poly = Polygon(seg)
            if poly.is_valid and poly.area > 0:
                geoms.append(poly)
                geom_names.append(f'StagnoneBarrier_sub{len(geoms)}')
        start = j + 1

# SicilyMainland: open coastline. Close to EAST edge to form a polygon enclosing all mainland.
if 'SicilyMainland' in polys:
    coast = polys['SicilyMainland']
    # Sort or ensure ordering — assume coastline is already sequential
    # Close: from last point go to (LON_MAX, last_lat), then (LON_MAX, first_lat), then back to first point
    closed = np.vstack([
        coast,
        [[LON_MAX + 0.1, coast[-1, 1]]],
        [[LON_MAX + 0.1, coast[0, 1]]],
        coast[:1],
    ])
    poly = Polygon(closed)
    if poly.is_valid and poly.area > 0:
        geoms.append(poly)
        geom_names.append('SicilyMainland_closed_east')
    else:
        # Try buffer fix
        poly2 = Polygon(closed).buffer(0)
        if poly2.is_valid:
            geoms.append(poly2)
            geom_names.append('SicilyMainland_closed_east_buffered')

# Other small features (if closed enough)
if 'Other' in polys:
    pts = polys['Other']
    # split into sub-polylines
    lat_avg = pts[:, 1].mean()
    dx_m = (pts[1:, 0] - pts[:-1, 0]) * 111000 * np.cos(np.radians(lat_avg))
    dy_m = (pts[1:, 1] - pts[:-1, 1]) * 111000
    dist = np.sqrt(dx_m**2 + dy_m**2)
    splits = np.where(dist > 2000)[0]
    start = 0
    for j in list(splits) + [len(pts) - 1]:
        seg = pts[start:j + 1]
        if len(seg) > 10:
            if not np.allclose(seg[0], seg[-1]):
                seg = np.vstack([seg, seg[:1]])
            poly = Polygon(seg)
            if poly.is_valid and poly.area > 100 * (1/111000)**2:  # >100 m² area
                geoms.append(poly)
                geom_names.append(f'Other_sub{len(geoms)}')
        start = j + 1

land_gdf = gpd.GeoDataFrame({'name': geom_names, 'geometry': geoms}, crs=CRS)
print(f'\nLand GeoDataFrame: {len(land_gdf)} polygons')
print(land_gdf[['name']])


# ============ STEP 2: load topobathy (seamless MDT+bathy) ============
print('\n=== Step 2: load topobathy_combined.nc ===')
if not TOPOBATHY_NC.exists():
    raise FileNotFoundError(
        f'{TOPOBATHY_NC} not found. Run scripts/build_topobathy_v05.py first '
        '(needs TINITALY + Copernicus DEM + bat20m + optional GEBCO).'
    )
topo_ds = xr.open_dataset(TOPOBATHY_NC)
topo = topo_ds['topobathy']
print(f'  loaded shape={dict(topo.sizes)} z range=({float(topo.min()):.1f}, {float(topo.max()):.1f})')

# For refine_basegrid we need a depth field: shallower → finer cells.
# Convention: sea z<0 in topobathy. refine_basegrid uses |z| via celerity sqrt(g*|z|).
# Land cells (z>0) would produce large celerity → coarse refinement; we want FINE near coast.
# Substitute land cells with sentinel -1 m so refine treats them as shallow water; they'll
# be deleted by step 6 via the LDB polygons anyway.
land_mask = topo_ds['land_mask'].values.astype(bool) if 'land_mask' in topo_ds else (topo.values > 0)
refine_z = topo.values.astype(np.float32).copy()
refine_z[land_mask] = -1.0
bathy_da = xr.DataArray(
    refine_z, dims=('lat', 'lon'),
    coords={'lat': topo['lat'].values, 'lon': topo['lon'].values},
    name='bathymetry',
    attrs={'note': 'land cells substituted with -1 m sentinel for refinement; '
                   'real signed values are in topobathy_combined.nc'},
)
bathy_da.to_netcdf(OUT_DIR / 'bathy_gridded.nc')
print(f'  Saved {OUT_DIR / "bathy_gridded.nc"} (refinement field with land sentinel)')


# ============ STEP 3: base grid ============
print('\n=== Step 3: base grid ===')
mk = dfmt.make_basegrid(
    lon_min=LON_MIN, lon_max=LON_MAX,
    lat_min=LAT_MIN, lat_max=LAT_MAX,
    dx=DX_BASE, dy=DY_BASE,
    crs=CRS,
)
print(f'  Base grid created, bbox = {dfmt.meshkernel_get_bbox(mk)}')


# ============ STEP 4: refine on bathy ============
print('\n=== Step 4: refine based on bathy ===')
dfmt.refine_basegrid(
    mk, data_bathy_sel=bathy_da,
    min_edge_size=MIN_EDGE_SIZE_M,
    max_courant_time=MAX_COURANT,
)
print(f'  Refined')


# ============ STEP 5: boundary .pli (BEFORE land cut — on uncut grid) ============
print('\n=== Step 5: generate boundary .pli (on uncut refined grid) ===')
bnd_gdf = dfmt.generate_bndpli_cutland(mk, res='f', crs=CRS)
print(f'  .pli boundary: {len(bnd_gdf)} line(s)')
try:
    bnd_gdf.to_file(OUT_DIR / 'Stagnone_v05_bnd.shp')
except Exception as e:
    print(f'  WARN shapefile save: {e}')


# ============ STEP 6: delete land cells ============
print('\n=== Step 6: delete cells inside land polygons ===')
dfmt.meshkernel_delete_withgdf(mk, land_gdf)
print('  Land cells deleted')


# ============ STEP 7: convert + save ============
print('\n=== Step 7: convert to UgridDataset + save ===')
uds = dfmt.meshkernel_to_UgridDataset(mk, crs=CRS)
print(f'  UgridDataset created, faces: {uds.grid.face_x.size}')
uds.ugrid.to_netcdf(str(OUT_DIR / 'Stagnone_v05_net.nc'))
print(f'  Saved {OUT_DIR / "Stagnone_v05_net.nc"}')


# ============ Step 8: overview plot ============
print('\n=== Step 8: overview plot ===')
fig, ax = plt.subplots(figsize=(11, 11))
fx = np.asarray(uds.grid.face_x)
fy = np.asarray(uds.grid.face_y)
ax.scatter(fx, fy, c='blue', s=0.5, alpha=0.5, label=f'{len(fx)} cells')
# Land polygons
for _, row in land_gdf.iterrows():
    geom = row.geometry
    if geom.geom_type == 'Polygon':
        x, y = geom.exterior.xy
        ax.fill(x, y, color='#cccccc', alpha=0.5)
        ax.plot(x, y, 'k-', lw=0.5)
ax.set_xlim(LON_MIN - 0.02, LON_MAX + 0.02)
ax.set_ylim(LAT_MIN - 0.02, LAT_MAX + 0.02)
ax.set_aspect(1/np.cos(np.radians(37.95)))
ax.set_xlabel('lon')
ax.set_ylabel('lat')
ax.set_title(f'Stagnone v05 mesh — {len(fx)} cells')
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / 'mesh_v05_overview.png', dpi=140, bbox_inches='tight')
print(f'  Saved {OUT_DIR / "mesh_v05_overview.png"}')

print('\nDone.')
