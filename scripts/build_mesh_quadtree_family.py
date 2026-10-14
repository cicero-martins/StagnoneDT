"""Quadtree meshes of the Stagnone domain at four lagoon resolutions.

The family supports a mesh sensitivity test of the no-waves member of the
Paper 1 ensemble. The four meshes share the domain, the offshore grading, the
open boundary and the bed surface, and differ only in the edge of the cells
inside the lagoon and its inlets, 120, 60, 30 or 15 m. The three finest
levels form the triplet for the grid convergence index (Celik et al. 2008,
J. Fluids Eng. 130, 078001), and the 120 m level shows the coarse end, where
the northern inlet is spanned by three to four cells.

Construction follows MaltaDT/scripts/build_mesh_v02.py. A regular base grid
is refined by polygon zones, coarse to fine, with a band of BAND_CELLS cells
of every intermediate level around each zone, so that neighbouring cells
differ by one level. The mesh is built in a conformal projection and only the
node coordinates are transformed to WGS84 at the end, since quadtree
transitions refined in geographic coordinates exceed the orthogonality of 0.5
at which FM rejects the network. The projection is World Mercator
(EPSG:3395) rather than UTM, since the v04 domain is a rectangle in longitude
and latitude and Mercator maps it to a rectangle, so that the base grid edges
fall on the open boundary of v04 and its polyline and per-node boundary
forcing are reused unchanged. Lengths in the projection are true lengths
divided by the cosine of the latitude, which varies by 0.5 % across the
domain, and every target is converted at the central latitude.

The wet domain is the union of the v04 faces, so the coastline, the islands
and the Trapani port are those of v04 at every level, and a face is removed
where its circumcentre falls on land, which keeps narrow channels at their
v04 width. Faces left disconnected from the main water body are removed.

    zone                                           edge
    farther than 4 km from land                    960 m
    within 4 km of land                            480 m
    within 1 km of land                            120 m
    lagoon and 500 m around it                     120, 60, 30 or 15 m

The lagoon is the set of v04 faces where lagoon_tracer_init.xyz exceeds 0.5,
the definition used by the bed-level twin. Bed level is given at face centres
(bedLevType = 1, as in v04) and sampled from one surface for every member of
the family. The surface is the v04 bed, linearly interpolated between v04
face centres, plus w * d, where d is the 2026 raster minus the v04 bed on wet
raster cells of the lagoon and the value of the nearest such cell elsewhere,
and w is 1 on the lagoon and falls linearly to zero at RAMP_M from it. This
is the rule of build_v04AE_nowaves_bathy26.py evaluated on the 10 m raster
grid instead of on the v04 faces, so the twin is the v04 mesh carrying the
same surface. Filled values are capped at a depth of FILL_MIN_DEPTH.

Usage:
    python build_mesh_quadtree_family.py [--lagoon-m 120 60 30 15] [--figure]
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_bathy_levigata_2006 import load_new  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NET_V04 = ROOT / 'model/dflowfm_v04/Stagnone_dxy01_15m_net.nc'
MEMBER = ROOT / 'model/dflowfm_v04AE_nowaves'
TRACER = MEMBER / 'lagoon_tracer_init.xyz'
PLI = MEMBER / 'Stagnone_dxy01_15m.pli'
OUT = ROOT / 'data/processed/mesh_quadtree_family'

CRS = 'EPSG:4326'
MERC = 'EPSG:3395'
UTM = 'EPSG:32633'
BASE_M = 960.0
COAST_FAR_M = 4000.0
COAST_NEAR_M = 1000.0
COAST_NEAR_EDGE_M = 120.0
RAMP_M = 500.0          # lagoon zone and bed ramp beyond the lagoon limit
BAND_CELLS = 3
FILL_MIN_DEPTH = 0.01
LAND_Z = 2.0            # v04 faces at or above this level are land
FM_ORTHO_LIMIT = 0.5
LAGOON_LEVELS = (120.0, 60.0, 30.0, 15.0)


# ---- v04 geometry -----------------------------------------------------------

def load_v04():
    """v04 faces in Mercator and UTM, bed level and lagoon flag."""
    with netCDF4.Dataset(NET_V04) as nc:
        lon = nc['mesh2d_node_x'][:].filled(np.nan)
        lat = nc['mesh2d_node_y'][:].filled(np.nan)
        fn = nc['mesh2d_face_nodes'][:].filled(-1).astype(int)
        fn = np.where(fn >= 0, fn - int(getattr(nc['mesh2d_face_nodes'], 'start_index', 1)), -1)
        flon = nc['mesh2d_face_x'][:].filled(np.nan)
        flat = nc['mesh2d_face_y'][:].filled(np.nan)
        fz = nc['mesh2d_face_z'][:].filled(np.nan)
    to_m = Transformer.from_crs(CRS, MERC, always_xy=True)
    to_u = Transformer.from_crs(CRS, UTM, always_xy=True)
    mx, my = to_m.transform(lon, lat)
    ux, uy = to_u.transform(lon, lat)
    fux, fuy = to_u.transform(flon, flat)
    tr = pd.read_csv(TRACER, sep=r'\s+', header=None, names=['lon', 'lat', 'c'])
    tx, ty = to_u.transform(tr.lon.values, tr.lat.values)
    from scipy.spatial import cKDTree
    dist, j = cKDTree(np.c_[tx, ty]).query(np.c_[fux, fuy])
    lagoon = (tr.c.values[j] > 0.5) & (dist < 50.0)
    domain = fz < LAND_Z
    return dict(domain=domain,lon=lon, lat=lat, fn=fn, mx=mx, my=my, ux=ux, uy=uy, fux=fux, fuy=fuy, fz=fz,
                lagoon=lagoon, lon_range=(lon.min(), lon.max()), lat_range=(lat.min(), lat.max()))


def union_faces(x, y, fn, sel):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(np.c_[x[r[r >= 0]], y[r[r >= 0]]]).buffer(0.01) for r in fn[sel]]
    return unary_union(polys).buffer(-0.01)


# ---- zones and refinement ---------------------------------------------------

def to_geometrylist(geom):
    """A (multi)polygon with its holes as a meshkernel GeometryList."""
    import meshkernel as mk
    sep, inner = -999.0, -998.0
    xs, ys = [], []
    parts = list(geom.geoms) if geom.geom_type == 'MultiPolygon' else [geom]
    for p in parts:
        if p.is_empty or p.area < 1.0:
            continue
        if xs:
            xs.append(sep)
            ys.append(sep)
        x, y = p.exterior.coords.xy
        xs.extend(x)
        ys.extend(y)
        for ring in p.interiors:
            xs.append(inner)
            ys.append(inner)
            x, y = ring.coords.xy
            xs.extend(x)
            ys.extend(y)
    return mk.GeometryList(x_coordinates=np.asarray(xs, dtype=float),
                           y_coordinates=np.asarray(ys, dtype=float),
                           geometry_separator=sep, inner_outer_separator=inner)


def passes_for(lagoon_m, bounds, land, lagoon_poly, k):
    """Refinement passes, coarse to fine, as (name, polygon, true edge in m).

    k converts true metres to Mercator units at the central latitude.
    """
    from shapely.geometry import box
    dom = box(*bounds)
    lagoon_zone = lagoon_poly.buffer(RAMP_M * k)
    out = [('coast_far', land.buffer(COAST_FAR_M * k).intersection(dom), 480.0),
           ('band_240', land.buffer((COAST_NEAR_M + BAND_CELLS * 240.0) * k).intersection(dom), 240.0),
           ('coast_near', land.buffer(COAST_NEAR_M * k).intersection(dom), COAST_NEAR_EDGE_M)]
    levels = []
    s = COAST_NEAR_EDGE_M / 2
    while s > lagoon_m:
        levels.append(s)
        s /= 2
    # bands of the intermediate levels, widest (coarsest) first
    for i, s in enumerate(levels):
        width = BAND_CELLS * sum(levels[i:])
        out.append((f'band_{s:.0f}', lagoon_zone.buffer(width * k), s))
    if lagoon_m < COAST_NEAR_EDGE_M:
        out.append(('lagoon', lagoon_zone, lagoon_m))
    return out, lagoon_zone


def refine(m, geom, edge, last):
    import meshkernel as mk
    par = mk.MeshRefinementParameters(min_edge_size=edge, max_refinement_iterations=10,
                                      refine_intersected=True, connect_hanging_nodes=last,
                                      smoothing_iterations=2)
    m.mesh2d_refine_based_on_polygon(to_geometrylist(geom), par)


def delete_land(m, land):
    import meshkernel as mk
    parts = list(land.geoms) if land.geom_type == 'MultiPolygon' else [land]
    for p in parts:
        assert not p.interiors, 'a land polygon encloses water'
        x, y = p.exterior.coords.xy
        gl = mk.GeometryList(x_coordinates=np.asarray(x, dtype=float),
                             y_coordinates=np.asarray(y, dtype=float))
        m.mesh2d_delete(geometry_list=gl,
                        delete_option=mk.DeleteMeshOption.FACES_WITH_INCLUDED_CIRCUMCENTERS,
                        invert_deletion=False)


def largest_component(grid):
    """Subset of the grid holding the largest edge-connected set of faces."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    ef = grid.edge_face_connectivity
    ef = ef[(ef >= 0).all(axis=1)]
    n = grid.n_face
    a = coo_matrix((np.ones(len(ef)), (ef[:, 0], ef[:, 1])), shape=(n, n))
    _, lab = connected_components(a, directed=False)
    keep = lab == np.bincount(lab).argmax()
    return grid.topology_subset(np.flatnonzero(keep)), int((~keep).sum())


def enclosed_holes(grid):
    """Faces that a reconstruction from the edges finds and the grid does not hold.

    A land feature narrower than a cell, such as a jetty, is removed as a row
    of single faces whose four edges remain, and a solver that builds its
    cells from the edges recovers those holes as cells.
    """
    import meshkernel as mk
    k = mk.MeshKernel(projection=mk.ProjectionType.CARTESIAN)
    k.mesh2d_set(mk.Mesh2d(node_x=grid.node_x.astype(float), node_y=grid.node_y.astype(float),
                           edge_nodes=grid.edge_node_connectivity.ravel().astype(np.int32)))
    r = k.mesh2d_get()
    assert r.node_x.size == grid.n_node, 'node set changed on reconstruction'
    held = {frozenset(row[row >= 0]) for row in grid.face_node_connectivity}
    extra, j = [], 0
    for n in r.nodes_per_face:
        f = r.face_nodes[j:j + n]
        j += n
        if frozenset(f) not in held:
            extra.append(f)
    return extra


def restore_holes(projected, pre):
    """Node coordinates and faces with the enclosed holes refilled from the mesh before deletion.

    pre holds the node coordinates and face rows of the refined mesh before
    land was deleted. Each hole takes back the faces of that mesh whose centre
    lies inside it, so that it is filled by the original cells rather than by
    one polygon with collinear nodes.
    """
    from scipy.spatial import cKDTree
    from shapely import contains_xy
    from shapely.geometry import Polygon
    holes = enclosed_holes(projected)
    nx, ny = list(projected.node_x), list(projected.node_y)
    rows = [list(r[r >= 0]) for r in projected.face_node_connectivity]
    if not holes:
        return np.array(nx), np.array(ny), rows, 0
    px, py, pre_rows = pre
    cx = np.array([px[r].mean() for r in pre_rows])
    cy = np.array([py[r].mean() for r in pre_rows])
    tree = cKDTree(np.c_[nx, ny])
    tol = 1e-3
    restored = 0
    for h in holes:
        poly = Polygon(np.c_[np.asarray(nx)[h], np.asarray(ny)[h]])
        for f in np.flatnonzero(contains_xy(poly, cx, cy)):
            row = []
            for n in pre_rows[f]:
                d, i = tree.query((px[n], py[n]))
                if d > tol:
                    nx.append(px[n])
                    ny.append(py[n])
                    i = len(nx) - 1
                    tree = cKDTree(np.c_[nx, ny])
                row.append(int(i))
            rows.append(row)
            restored += 1
    return np.array(nx), np.array(ny), rows, restored


def to_wgs84(m, pre):
    """Grid with the nodes transformed to WGS84 and the projected connectivity kept.

    Enclosed holes are refilled before the transformation.
    """
    import dfm_tools as dfmt
    import xugrid as xu
    projected = dfmt.meshkernel_to_UgridDataset(m, crs=MERC).grid
    nx, ny, rows, restored = restore_holes(projected, pre)
    width = max(len(r) for r in rows)
    fnc = np.full((len(rows), width), -1, dtype=np.int64)
    for i, r in enumerate(rows):
        fnc[i, :len(r)] = r
    tr = Transformer.from_crs(MERC, CRS, always_xy=True)
    lon, lat = tr.transform(nx, ny)
    grid = xu.Ugrid2d(node_x=np.asarray(lon, dtype=float), node_y=np.asarray(lat, dtype=float),
                      fill_value=-1, face_node_connectivity=fnc,
                      name='mesh2d', is_projected=False, crs=CRS)
    assert not enclosed_holes(grid), 'enclosed holes remain after refilling'
    return grid, restored


def spherical_orthogonality(grid, raw=False):
    """Orthogonality of the interior edges on the sphere, in the edge order of the grid."""
    import meshkernel as mk
    s = mk.MeshKernel(projection=mk.ProjectionType.SPHERICAL)
    s.mesh2d_set(mk.Mesh2d(node_x=grid.node_x.astype(float), node_y=grid.node_y.astype(float),
                           edge_nodes=grid.edge_node_connectivity.ravel().astype(np.int32)))
    v = s.mesh2d_get_orthogonality().values
    return v if raw else np.abs(v[v > -998])


# ---- bed surface ------------------------------------------------------------

def bed_surface(v04):
    """The surface of the module docstring, on the 10 m raster grid, and the v04 interpolant."""
    from rasterio.features import rasterize
    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
    from scipy.ndimage import distance_transform_edt

    d = v04['domain']
    pts = np.c_[v04['fux'][d], v04['fuy'][d]]
    lin = LinearNDInterpolator(pts, v04['fz'][d])
    near = NearestNDInterpolator(pts, v04['fz'][d])

    def v04_bed(x, y):
        z = lin(x, y)
        return np.where(np.isfinite(z), z, near(x, y))

    z_new, wet_new, _, tf, _ = load_new()
    ny, nx = z_new.shape
    res = tf.a
    gx = tf.c + res * (np.arange(nx) + 0.5)
    gy = tf.f + tf.e * (np.arange(ny) + 0.5)
    GX, GY = np.meshgrid(gx, gy)
    V = v04_bed(GX, GY)
    lagoon_u = union_faces(v04['ux'], v04['uy'], v04['fn'], v04['lagoon'])
    lag = rasterize([(lagoon_u, 1)], out_shape=(ny, nx), transform=tf, fill=0, dtype='uint8').astype(bool)
    core = lag & (V < 0)
    src = core & wet_new
    _, (ri, ci) = distance_transform_edt(~src, return_indices=True)
    delta = (z_new - V)[ri, ci]
    dcore = distance_transform_edt(~core) * res
    w = np.where(core, 1.0, np.clip(1.0 - dcore / RAMP_M, 0.0, 1.0)) * (V < 0)
    S = V + w * delta
    fill = (w > 0) & ~src
    S[fill] = np.minimum(S[fill], -FILL_MIN_DEPTH)

    def sample(x, y):
        from scipy.ndimage import map_coordinates
        col = (x - tf.c) / res - 0.5
        row = (y - tf.f) / tf.e - 0.5
        inside = (col >= 0) & (col <= nx - 1) & (row >= 0) & (row <= ny - 1)
        out = v04_bed(x, y)
        out[inside] = map_coordinates(S, np.vstack([row[inside], col[inside]]), order=1)
        return out

    return sample, lagoon_u


# ---- outputs ----------------------------------------------------------------

def write_net(grid, face_z, node_z, path, note):
    """Net file with the variables, attributes and one-based indexing of the v04 net file.

    The xugrid writer leaves the mesh topology without its connectivity
    attributes and omits the face coordinates, and FM then reads no faces.
    """
    fn = grid.face_node_connectivity.copy()
    x, y = grid.node_x, grid.node_y
    # counterclockwise faces
    for i, row in enumerate(fn):
        idx = row[row >= 0]
        if np.sum(x[idx] * np.roll(y[idx], -1) - np.roll(x[idx], -1) * y[idx]) < 0:
            fn[i, :len(idx)] = idx[::-1]
    en = grid.edge_node_connectivity
    ef = grid.edge_face_connectivity
    fx, fy = grid.face_x, grid.face_y
    with netCDF4.Dataset(NET_V04) as src, netCDF4.Dataset(path, 'w', format='NETCDF4') as nc:
        nc.setncatts({'institution': 'Universita degli Studi di Palermo',
                      'source': 'scripts/build_mesh_quadtree_family.py',
                      'Conventions': 'CF-1.8 UGRID-1.0 Deltares-0.10', 'bed_level_note': note})
        nc.createDimension('Two', 2)
        nc.createDimension('mesh2d_nEdges', grid.n_edge)
        nc.createDimension('mesh2d_nNodes', grid.n_node)
        nc.createDimension('mesh2d_nFaces', grid.n_face)
        nc.createDimension('mesh2d_nMax_face_nodes', fn.shape[1])
        for name in ('wgs84', 'mesh2d'):
            v = nc.createVariable(name, src[name].dtype)
            v.setncatts(src[name].__dict__)

        def put(name, dims, dtype, data, fill=None):
            v = nc.createVariable(name, dtype, dims, fill_value=fill)
            v.setncatts({a: src[name].getncattr(a) for a in src[name].ncattrs() if a != '_FillValue'})
            v[:] = data

        put('mesh2d_node_x', ('mesh2d_nNodes',), 'f8', x)
        put('mesh2d_node_y', ('mesh2d_nNodes',), 'f8', y)
        put('mesh2d_node_z', ('mesh2d_nNodes',), 'f8', node_z, -999.0)
        put('mesh2d_edge_x', ('mesh2d_nEdges',), 'f8', grid.edge_x)
        put('mesh2d_edge_y', ('mesh2d_nEdges',), 'f8', grid.edge_y)
        put('mesh2d_edge_nodes', ('mesh2d_nEdges', 'Two'), 'i4', en + 1)
        put('mesh2d_face_nodes', ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'), 'i4',
            np.where(fn >= 0, fn + 1, -999), -999)
        put('mesh2d_edge_faces', ('mesh2d_nEdges', 'Two'), 'i4', np.where(ef >= 0, ef + 1, -999), -999)
        put('mesh2d_face_x', ('mesh2d_nFaces',), 'f8', fx)
        put('mesh2d_face_y', ('mesh2d_nFaces',), 'f8', fy)
        bx = np.where(fn >= 0, x[np.clip(fn, 0, None)], -999.0)
        by = np.where(fn >= 0, y[np.clip(fn, 0, None)], -999.0)
        put('mesh2d_face_x_bnd', ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'), 'f8', bx, -999.0)
        put('mesh2d_face_y_bnd', ('mesh2d_nFaces', 'mesh2d_nMax_face_nodes'), 'f8', by, -999.0)
        put('mesh2d_face_z', ('mesh2d_nFaces',), 'f8', face_z, -999.0)


def face_sizes_m(grid):
    """Square root of face area in metres, from the UTM coordinates of the nodes."""
    tr = Transformer.from_crs(CRS, UTM, always_xy=True)
    x, y = tr.transform(grid.node_x, grid.node_y)
    fn = grid.face_node_connectivity
    out = np.empty(grid.n_face)
    for i, row in enumerate(fn):
        idx = row[row >= 0]
        xx, yy = x[idx], y[idx]
        out[i] = math.sqrt(abs(0.5 * np.sum(xx * np.roll(yy, -1) - np.roll(xx, -1) * yy)))
    return out


def pli_offset_m(grid):
    """Distance from each point of the v04 boundary polyline to the mesh boundary, in metres."""
    from shapely.geometry import MultiLineString, Point
    tr = Transformer.from_crs(CRS, UTM, always_xy=True)
    x, y = tr.transform(grid.node_x, grid.node_y)
    ef = grid.edge_face_connectivity
    bnd = grid.edge_node_connectivity[(ef < 0).any(axis=1)]
    lines = MultiLineString([[(x[a], y[a]), (x[b], y[b])] for a, b in bnd])
    pli = pd.read_csv(PLI, skiprows=2, sep=r'\s+', header=None)
    px, py = tr.transform(pli[0].values, pli[1].values)
    return np.array([lines.distance(Point(a, b)) for a, b in zip(px, py)])


def build(lagoon_m, bounds, land, lagoon_m_poly, k, bed, lagoon_u, figure):
    import dfm_tools as dfmt
    t0 = time.time()
    name = f'stagnone_qt_L{lagoon_m:.0f}'
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = bounds
    nx = max(1, round((x1 - x0) / (BASE_M * k)))
    ny = max(1, round((y1 - y0) / (BASE_M * k)))
    dx, dy = (x1 - x0) / nx, (y1 - y0) / ny
    print(f'\n[{name}] base {nx} x {ny} cells, {dx / k:.1f} x {dy / k:.1f} m at the central latitude')
    m = dfmt.make_basegrid(x0, x1, y0, y1, dx=dx, dy=dy, crs=MERC)
    passes, lagoon_zone = passes_for(lagoon_m, bounds, land, lagoon_m_poly, k)
    unit = min(dx, dy) / BASE_M     # Mercator units of one true metre of the base grid
    for i, (key, geom, edge) in enumerate(passes):
        refine(m, geom, 0.99 * edge * unit, last=i == len(passes) - 1)
        print(f'  refined {key:11s} {m.mesh2d_get().face_x.size:8d} faces (edge {edge:.0f} m)')
    g0 = m.mesh2d_get()
    j = np.r_[0, np.cumsum(g0.nodes_per_face)]
    pre = (g0.node_x.copy(), g0.node_y.copy(), [g0.face_nodes[j[i]:j[i + 1]].copy() for i in range(len(j) - 1)])
    delete_land(m, land)
    grid, restored = to_wgs84(m, pre)
    grid, dropped = largest_component(grid)
    print(f'  after land deletion {grid.n_face:8d} faces, {grid.n_node} nodes, {restored} faces restored in '
          f'enclosed holes, {dropped} disconnected faces removed ({time.time() - t0:.0f} s)')

    tr = Transformer.from_crs(CRS, UTM, always_xy=True)
    fux, fuy = tr.transform(grid.face_x, grid.face_y)
    nux, nuy = tr.transform(grid.node_x, grid.node_y)
    face_z = bed(fux, fuy)
    node_z = bed(nux, nuy)
    from shapely import contains_xy
    in_lagoon = contains_xy(lagoon_u, fux, fuy)
    note = (f'mesh2d_face_z sampled from v04 + w * (BATHY_STAGNONE_LEVIGATA_SIGMA30M - v04), w = 1 on the '
            f'v04 lagoon and linear to 0 over {RAMP_M:.0f} m; lagoon cell edge {lagoon_m:.0f} m')
    net = out / f'{name}_net.nc'
    write_net(grid, face_z, node_z, net, note)

    sizes = face_sizes_m(grid)
    tri = (grid.face_node_connectivity >= 0).sum(axis=1) == 3
    o = spherical_orthogonality(grid)
    worst = np.argsort(o)[::-1][:5]
    ex, ey = grid.edge_x, grid.edge_y
    interior = np.flatnonzero(spherical_orthogonality(grid, raw=True) > -998)
    print('  largest orthogonality at ' + ', '.join(
        f'({ex[interior[i]]:.4f}, {ey[interior[i]]:.4f}) {o[i]:.3f}' for i in worst))
    off = pli_offset_m(grid)
    area = sizes ** 2
    vol = float(np.sum(area[in_lagoon] * np.clip(-face_z[in_lagoon], 0, None)))
    print(f'  written {net}')
    print(f'  faces {grid.n_face}, triangles {tri.sum()}, lagoon faces {in_lagoon.sum()}')
    for sz in (15, 30, 60, 120, 240, 480, 960):
        sel = (~tri) & (sizes > sz / 1.41) & (sizes <= sz * 1.41)
        print(f'    {sz:4d} m quadrilaterals {sel.sum():7d}')
    print(f'  lagoon wet area {area[in_lagoon].sum() / 1e6:.2f} km2, volume {vol / 1e6:.2f} Mm3, '
          f'faces at or above 0 m {(face_z >= 0).sum()}, lagoon faces shallower than 0.10 m '
          f'{(in_lagoon & (face_z > -0.10)).sum()}')
    print(f'  orthogonality on the sphere: p99 {np.percentile(o, 99):.5f}, max {o.max():.5f}, '
          f'above {FM_ORTHO_LIMIT}: {(o > FM_ORTHO_LIMIT).sum()}')
    print(f'  v04 boundary polyline to mesh boundary: median {np.median(off):.2f} m, max {off.max():.2f} m')
    print(f'  total {time.time() - t0:.0f} s')
    row = dict(lagoon_m=lagoon_m, faces=grid.n_face, triangles=int(tri.sum()), lagoon_faces=int(in_lagoon.sum()),
               lagoon_area_km2=area[in_lagoon].sum() / 1e6, lagoon_volume_Mm3=vol / 1e6,
               ortho_max=float(o.max()), ortho_above_limit=int((o > FM_ORTHO_LIMIT).sum()),
               pli_offset_max_m=float(off.max()))
    if figure:
        plot(grid, sizes, out / f'{name}.png', name)
    return row


def plot(grid, sizes, path, name):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import LogNorm
    xy = np.c_[grid.node_x, grid.node_y]
    faces = [xy[r[r >= 0]] for r in grid.face_node_connectivity]
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw=dict(width_ratios=[1.3, 1]))
    for ax, ext in ((axs[0], None), (axs[1], (12.40, 37.81, 12.50, 37.92))):
        pc = PolyCollection(faces, array=sizes, cmap='viridis_r', norm=LogNorm(15, 960),
                            edgecolors='#52514e', linewidths=0.08 if ext is None else 0.15)
        ax.add_collection(pc)
        if ext is None:
            ax.set_xlim(grid.node_x.min(), grid.node_x.max())
            ax.set_ylim(grid.node_y.min(), grid.node_y.max())
            ax.set_title(f'{name}, face size', fontsize=9, loc='left')
        else:
            ax.set_xlim(ext[0], ext[2])
            ax.set_ylim(ext[1], ext[3])
            ax.set_title('Lagoon and inlets', fontsize=9, loc='left')
        ax.set_aspect(1 / math.cos(math.radians(37.88)))
    fig.colorbar(pc, ax=axs, label='square root of face area, m', shrink=0.8)
    fig.savefig(path, dpi=160, facecolor='#fcfcfb', bbox_inches='tight')
    plt.close(fig)
    print(f'  figure {path}')


def main(argv=None):
    from shapely.geometry import box
    ap = argparse.ArgumentParser()
    ap.add_argument('--lagoon-m', type=float, nargs='+', default=list(LAGOON_LEVELS))
    ap.add_argument('--figure', action='store_true')
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    v04 = load_v04()
    lat0 = 0.5 * sum(v04['lat_range'])
    k = 1.0 / math.cos(math.radians(lat0))
    print(f'central latitude {lat0:.4f}, Mercator units per true metre {k:.5f}')
    water = union_faces(v04['mx'], v04['my'], v04['fn'], v04['domain'])
    if water.geom_type == 'MultiPolygon':
        parts = sorted(water.geoms, key=lambda p: p.area)
        print(f'v04 water below {LAND_Z:+.0f} m in {len(parts)} parts, {len(parts) - 1} smaller ones '
              f'({sum(p.area for p in parts[:-1]) / k ** 2 / 1e6:.3f} km2) left as land')
        water = parts[-1]
    lagoon_m_poly = union_faces(v04['mx'], v04['my'], v04['fn'], v04['lagoon'])
    dom = box(v04['mx'].min(), v04['my'].min(), v04['mx'].max(), v04['my'].max())
    # The v04 boundary nodes are not exactly collinear, which leaves slivers of
    # zero area between the box and the water; the smallest real islet is 2000 m2.
    from shapely.geometry import MultiPolygon
    land = dom.difference(water)
    land = MultiPolygon([p for p in getattr(land, 'geoms', [land]) if p.area > 100.0 * k ** 2])
    print(f'v04 water domain {water.area / k ** 2 / 1e6:.1f} km2 with {len(water.interiors)} islands, '
          f'lagoon {lagoon_m_poly.area / k ** 2 / 1e6:.2f} km2 on {v04["lagoon"].sum()} faces')
    bed, lagoon_u = bed_surface(v04)

    rows = [build(L, dom.bounds, land, lagoon_m_poly, k, bed, lagoon_u, args.figure) for L in args.lagoon_m]
    t = pd.DataFrame(rows)
    print('\n' + t.to_string(index=False, float_format='%.4f'))
    t.to_csv(OUT / 'family_summary.csv', index=False, float_format='%.5f')
    return 0


if __name__ == '__main__':
    sys.exit(main())
