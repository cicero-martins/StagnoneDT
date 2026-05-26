"""Build Stagnone v05 mesh via dfm_tools/meshkernel automation.

Workflow:
  1. Read sicily_v05.ldb -> GeoDataFrame of land polygons (closing mainland east)
  2. Read combined bathy XYZ -> rasterize to regular grid (sea only, z<0)
  3. dfmt.make_basegrid() - base regular grid covering bbox
  4. dfmt.refine_basegrid() - refine based on bathy depth (shallow=fine, deep=coarse)
  5. dfmt.meshkernel_delete_withgdf() - delete cells inside land polygons
  6. dfmt.generate_bndpli_cutland() - auto-generate .pli boundary
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
from meshkernel import GeometryList


# ============ INPUTS ============
SICILY_LDB = Path('data/processed/sicily_v05.ldb')
# Seamless topobathy from MDT pipeline (build_topobathy_v05.py). Signed: land z>0, sea z<0.
TOPOBATHY_NC = Path('data/processed/mesh_v05/topobathy_combined.nc')
OUT_DIR = Path('data/processed/mesh_v05')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============ DOMAIN ============
LON_MIN, LON_MAX = 11.95, 12.60
LAT_MIN, LAT_MAX = 37.65, 38.25

# Base grid resolution (~1500 m at 37.95 deg N). Aggressive coarsening of the
# base grid drastically reduces cell count where bathy doesn't trigger
# refinement (deep ocean, high-elevation land).
DX_BASE = 0.017
DY_BASE = 0.017

# Refinement parameters
# refine_basegrid uses RefinementType.WAVE_COURANT:
#   target_edge = sqrt(g * |bathy|) * max_courant_time_s   (capped at min_edge_size)
# max_courant_time in SECONDS (meshkernel default is 120 s; way too coarse for us).
#
# Settings 2026-05-26:
#   - 0.01 deg base grid + min_edge=80 + courant=6 + smoothing=5
#   - Land cells get NaN bathy => SKIPPED by refinement (stay at base 880 m)
#     Prevents the Sicily salt-pan strip (TINITALY z ~ +1 m over many km of
#     flat coastal plain) from being refined to 80 m as if it were shallow
#     water -- user-reported "dense vertical bar" artifact along east coast.
#   - At sea: z=-15m -> 73m (floor 80) lagoon; z=-50m -> 132m shelf;
#             z=-100m -> 187m; z=-1000m -> 594m (stays at 880m base).
#   - smoothing=5 propagates refinement levels gradually so sea<->land
#     transition is a 1-2 cell buffer (not a hard step at the coastline).
# FOUR-PASS refinement controlled by BATHY (no polygon). Each pass refines
# only cells whose |bathy| falls inside its (zmin, zmax) band. Combined effect:
# 5 tiers of cell size following the depth contour.
#   pass A: 0  ..  5 m   -> min 50  m, courant  4 s   -> tier 50  m
#   pass B: 5  .. 20 m   -> min 100 m, courant  6 s   -> tier 100 m
#   pass C: 20 ..100 m   -> min 300 m, courant 10 s   -> tier 300 m
#   pass D: 100..300 m   -> min 500 m, courant 12 s   -> tier 500 m
#   beyond 300 m       -> no refinement -> base 1500 m
PASSES = [
    # (zmin, zmax, min_edge_m, courant_s, label)
    (  0.0,    5.0,  50.0,  4.0, 'A_shallow'),
    (  5.0,   20.0, 100.0,  6.0, 'B_intermediate'),
    ( 20.0,  100.0, 300.0, 10.0, 'C_midshelf'),
    (100.0,  300.0, 500.0, 12.0, 'D_slope'),
]
SMOOTHING_ITERS = 5

# CRS
CRS = 'EPSG:4326'


# ============ STEP 1: parse sicily_v05.ldb -> GeoDataFrame ============
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

# Build TWO GeoDataFrames:
#   delete_gdf: polygons to be REMOVED from the mesh entirely (permanent land,
#               outside any flooding/SLR scenario we care about)
#   island_gdf: KEPT in the mesh as wet/dry cells with positive bedlevel from
#               TINITALY. FM with bedLevType=1 leaves them dry while WL < bl,
#               floods them as WL rises. This makes the v05 mesh SLR-ready.
delete_geoms = []
delete_names = []
island_geoms = []
island_names = []

# Marettimo, Favignana, Levanzo: KEEP as island land cells in the mesh
for name in ['Marettimo', 'Favignana', 'Levanzo']:
    if name not in polys:
        continue
    pts = polys[name]
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[:1]])
    poly = Polygon(pts)
    if poly.is_valid and poly.area > 0:
        island_geoms.append(poly)
        island_names.append(name)

# StagnoneBarrier: KEEP all sub-polygons (Isola Grande/Lunga + smaller islets)
# as land cells with topobathy bedlevel.
if 'StagnoneBarrier' in polys:
    pts = polys['StagnoneBarrier']
    lat_avg = pts[:, 1].mean()
    dx_m = (pts[1:, 0] - pts[:-1, 0]) * 111000 * np.cos(np.radians(lat_avg))
    dy_m = (pts[1:, 1] - pts[:-1, 1]) * 111000
    dist = np.sqrt(dx_m**2 + dy_m**2)
    splits = np.where(dist > 500)[0]
    start = 0
    for j in list(splits) + [len(pts) - 1]:
        seg = pts[start:j + 1]
        if len(seg) > 10:
            if not np.allclose(seg[0], seg[-1]):
                seg = np.vstack([seg, seg[:1]])
            poly = Polygon(seg)
            if poly.is_valid and poly.area > 0:
                island_geoms.append(poly)
                island_names.append(f'StagnoneBarrier_sub{len(island_geoms)}')
        start = j + 1

# SicilyMainland: KEEP as land cells (TINITALY elevation). The whole point of
# v05's MDT integration is to support coastal flooding / SLR scenarios on the
# mainland coast too -- delete_gdf stays empty; Step 6 becomes a no-op.
if 'SicilyMainland' in polys:
    coast = polys['SicilyMainland']
    closed = np.vstack([
        coast,
        [[LON_MAX + 0.1, coast[-1, 1]]],
        [[LON_MAX + 0.1, coast[0, 1]]],
        coast[:1],
    ])
    poly = Polygon(closed)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_valid and poly.area > 0:
        island_geoms.append(poly)
        island_names.append('SicilyMainland_closed_east')

# Other small features: KEEP as islands too (they showed up around the lagoon)
if 'Other' in polys:
    pts = polys['Other']
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
            if poly.is_valid and poly.area > 100 * (1/111000)**2:
                island_geoms.append(poly)
                island_names.append(f'Other_sub{len(island_geoms)}')
        start = j + 1

delete_gdf = gpd.GeoDataFrame({'name': delete_names, 'geometry': delete_geoms}, crs=CRS)
island_gdf = gpd.GeoDataFrame({'name': island_names, 'geometry': island_geoms}, crs=CRS)
print(f'\nDelete from mesh: {len(delete_gdf)} polygon(s)')
print(delete_gdf[['name']])
print(f'\nKeep as land cells (bl from TINITALY): {len(island_gdf)} polygon(s)')
print(island_gdf[['name']])

# land_gdf preserved for downstream code that expects it (overview plot etc.)
land_gdf = island_gdf


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

# For refinement: NaN-out land cells so they are SKIPPED by refine_basegrid.
# Earlier attempt with signed TINITALY values produced a dense refinement band
# over the entire Sicily coastal plain (salt pans at +1 m -> celerity small
# -> fine refinement everywhere on flat lowland). NaN forces those cells to
# stay at base 880 m. Smoothing then bridges the few cells of sea<->land
# transition naturally. TINITALY values are still used for face_z assignment
# later (interp_bathy_to_mesh_v05.py).
land_mask = topo_ds['land_mask'].values.astype(bool) if 'land_mask' in topo_ds else (topo.values > 0)
refine_z = topo.values.astype(np.float32).copy()
refine_z[land_mask] = np.nan
bathy_da = xr.DataArray(
    refine_z, dims=('lat', 'lon'),
    coords={'lat': topo['lat'].values, 'lon': topo['lon'].values},
    name='bathymetry',
    attrs={'note': 'land cells masked to NaN so refine_basegrid skips them; '
                   'positive z from TINITALY only used in interp_bathy step.'},
)
bathy_da.to_netcdf(OUT_DIR / 'bathy_gridded.nc')
print(f'  Saved {OUT_DIR / "bathy_gridded.nc"} (refinement field, land NaN)')


# ============ STEP 3: base grid ============
print('\n=== Step 3: base grid ===')
mk = dfmt.make_basegrid(
    lon_min=LON_MIN, lon_max=LON_MAX,
    lat_min=LAT_MIN, lat_max=LAT_MAX,
    dx=DX_BASE, dy=DY_BASE,
    crs=CRS,
)
print(f'  Base grid created, bbox = {dfmt.meshkernel_get_bbox(mk)}')


# ============ STEP 4: MULTI-PASS adaptive refinement ============
# One pass per depth band. Refinement is monotonic (only subdivides), so the
# finest pass that touches a cell wins. Order doesn't matter for end result,
# but we go outer -> inner; all but the last pass keep hanging nodes.
print(f'\n=== Step 4: multi-pass adaptive refinement ({len(PASSES)} passes) ===')
for idx, (zmin, zmax, min_e, courant, label) in enumerate(PASSES[::-1]):
    is_last = idx == len(PASSES) - 1
    arr = bathy_da.values.copy()
    valid = ~np.isnan(arr) & (np.abs(arr) >= zmin) & (np.abs(arr) < zmax)
    arr[~valid] = np.nan
    bathy_pass = xr.DataArray(
        arr, dims=bathy_da.dims, coords=bathy_da.coords,
        name=f'bathymetry_{label}',
    )
    n_valid = int(np.isfinite(bathy_pass.values).sum())
    print(f'  pass {label}: |z| in [{zmin:.0f}, {zmax:.0f}) m, '
          f'{n_valid} valid cells ({100*n_valid/bathy_pass.size:.2f}%), '
          f'min_edge={min_e}m, courant={courant}s, '
          f'{"final" if is_last else "intermediate"}')
    dfmt.refine_basegrid(
        mk, data_bathy_sel=bathy_pass,
        min_edge_size=min_e,
        max_courant_time=courant,
        smoothing_iterations=SMOOTHING_ITERS,
        connect_hanging_nodes=is_last,
    )
print('  multi-pass refinement done')


# ============ STEP 5: boundary .pli (BEFORE land cut - on uncut grid) ============
print('\n=== Step 5: generate boundary .pli (on uncut refined grid) ===')
bnd_gdf = dfmt.generate_bndpli_cutland(mk, res='f', crs=CRS)
print(f'  .pli boundary: {len(bnd_gdf)} line(s)')
try:
    bnd_gdf.to_file(OUT_DIR / 'Stagnone_v05_bnd.shp')
except Exception as e:
    print(f'  WARN shapefile save: {e}')


# ============ STEP 6: delete cells (now no-op -- everything kept as land) ============
print('\n=== Step 6: delete cells inside land polygons ===')
if len(delete_gdf) > 0:
    dfmt.meshkernel_delete_withgdf(mk, delete_gdf)
    print(f'  cells deleted ({len(delete_gdf)} polygon(s))')
else:
    print('  no delete polygons -- all land kept in mesh with TINITALY elevation')


# ============ STEP 7: convert + save (QuickPlot-compatible) ============
print('\n=== Step 7: convert to UgridDataset + save ===')
uds = dfmt.meshkernel_to_UgridDataset(mk, crs=CRS)
n_faces = uds.grid.face_x.size
print(f'  UgridDataset created, faces: {n_faces}')

# Save initial via xugrid
nc_path = OUT_DIR / 'Stagnone_v05_net.nc'
uds.ugrid.to_netcdf(str(nc_path))

# QuickPlot-compatibility patch: cast connectivity to int32, add face/edge coords,
# write as NETCDF3_CLASSIC (Delft3D-MATLAB cannot handle int64 in face_nodes).
print('  patching for QuickPlot compat (int32 conn + face_coords)...')
import netCDF4 as _nc
src = _nc.Dataset(nc_path, 'r')
tmp_path = nc_path.with_suffix('.nc.tmp')
dst = _nc.Dataset(tmp_path, 'w', format='NETCDF3_CLASSIC')
for n, d in src.dimensions.items():
    dst.createDimension(n, len(d) if not d.isunlimited() else None)
for k in src.ncattrs():
    dst.setncattr(k, src.getncattr(k))
int_conn_vars = {'mesh2d_face_nodes', 'mesh2d_edge_nodes', 'mesh2d_face_edges',
                  'mesh2d_edge_faces', 'mesh2d_face_links'}
for name, var in src.variables.items():
    new_dtype = 'i4' if (name in int_conn_vars or var.dtype == np.int64) else var.dtype
    attrs = {k: var.getncattr(k) for k in var.ncattrs()}
    fill = attrs.pop('_FillValue', None)
    if name in int_conn_vars and fill is not None:
        fill = np.int32(-999)
    elif fill is not None:
        fill = np.array(fill, dtype=new_dtype)
    nv = dst.createVariable(name, new_dtype, var.dimensions, fill_value=fill)
    data = var[:]
    if new_dtype == 'i4' and data.dtype != np.int32:
        data = data.astype(np.int32)
    nv[:] = data
    for k, v in attrs.items():
        if k == 'start_index' and name in int_conn_vars:
            v = np.int32(v)
        nv.setncattr(k, v)

# Compute and add face_x, face_y, edge_x, edge_y (centroids) for QuickPlot
nodes_x = src.variables['mesh2d_node_x'][:]
nodes_y = src.variables['mesh2d_node_y'][:]
face_nodes = src.variables['mesh2d_face_nodes'][:]
start_idx = int(src.variables['mesh2d_face_nodes'].start_index)
fn_zero = np.where(face_nodes < 0, 0, face_nodes - start_idx)
fn_mask = face_nodes < 0
fx = np.where(fn_mask, np.nan, nodes_x[fn_zero])
fy = np.where(fn_mask, np.nan, nodes_y[fn_zero])
face_x = np.nanmean(fx, axis=1)
face_y = np.nanmean(fy, axis=1)
fxv = dst.createVariable('mesh2d_face_x', 'f8', ('mesh2d_nFaces',))
fxv[:] = face_x
fxv.standard_name = 'longitude'
fxv.long_name = 'Characteristic longitude of mesh face'
fxv.units = 'degrees_east'
fyv = dst.createVariable('mesh2d_face_y', 'f8', ('mesh2d_nFaces',))
fyv[:] = face_y
fyv.standard_name = 'latitude'
fyv.long_name = 'Characteristic latitude of mesh face'
fyv.units = 'degrees_north'

edge_nodes = src.variables['mesh2d_edge_nodes'][:]
e_start = int(src.variables['mesh2d_edge_nodes'].start_index)
en_zero = edge_nodes - e_start
edge_x = (nodes_x[en_zero[:, 0]] + nodes_x[en_zero[:, 1]]) / 2
edge_y = (nodes_y[en_zero[:, 0]] + nodes_y[en_zero[:, 1]]) / 2
exv = dst.createVariable('mesh2d_edge_x', 'f8', ('mesh2d_nEdges',))
exv[:] = edge_x
exv.standard_name = 'longitude'
exv.long_name = 'Characteristic longitude of mesh edge'
exv.units = 'degrees_east'
eyv = dst.createVariable('mesh2d_edge_y', 'f8', ('mesh2d_nEdges',))
eyv[:] = edge_y
eyv.standard_name = 'latitude'
eyv.long_name = 'Characteristic latitude of mesh edge'
eyv.units = 'degrees_north'

# wire face_coordinates / edge_coordinates into mesh2d
if 'mesh2d' in dst.variables:
    m = dst.variables['mesh2d']
    m.face_coordinates = 'mesh2d_face_x mesh2d_face_y'
    m.edge_coordinates = 'mesh2d_edge_x mesh2d_edge_y'

src.close()
dst.close()
nc_path.unlink()
tmp_path.rename(nc_path)
print(f'  Saved {nc_path} (NETCDF3_CLASSIC, int32 conn, face_x/y, edge_x/y)')


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
ax.set_title(f'Stagnone v05 mesh - {len(fx)} cells')
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / 'mesh_v05_overview.png', dpi=140, bbox_inches='tight')
print(f'  Saved {OUT_DIR / "mesh_v05_overview.png"}')

print('\nDone.')
