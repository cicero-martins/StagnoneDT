"""Regrid a D-Flow FM ensemble member onto the WetWise portal grids.

Runs on plain xarray/scipy/matplotlib -- no dfm_tools -- so it can execute on
the compute server where the partitioned output lives (tens of GB).  Only the
two small cache files travel back to the laptop.

Two things differ from the regrid that used to live inside
build_wetwise_hydrodynamics_demo.py:

1. The wet mask is an exact point-in-face test against the mesh face polygons,
   not a `distance to nearest face centre > k*dx` threshold.  The old test
   could not resolve features smaller than its own radius, so it filled in the
   island holes (Isola della Scuola is only ~83 m across) and it punched false
   holes offshore, where the mesh is coarser than the threshold.  The exact
   test is resolution-independent and fixes both at once.

2. The fine grid is tightened onto the lagoon and refined, since the old
   0.003 deg (~330 m) was far coarser than the 20-90 m mesh underneath it.

Usage
    python regrid_wetwise_source.py --src <model dir> --out <cache dir>

The model dir is the one holding DFM_OUTPUT_*/, e.g.
    model/dflowfm_v04AE_vr_dens
"""
from pathlib import Path
import argparse
import glob as _glob

import numpy as np
import xarray as xr
from matplotlib.path import Path as MplPath
from scipy.spatial import Delaunay

VARS = ['mesh2d_s1', 'mesh2d_ucx', 'mesh2d_ucy', 'mesh2d_hwav']

# Full domain.  This layer is ALWAYS painted, underneath the lagoon one, so it
# is what fills the map wherever the detail grid does not reach.  At the old
# 530 m the lagoon was only ~4 cells across, and the exact face mask left that
# strip ragged -- which is what read as holes once you zoomed past the detail
# grid's edge.  270 m keeps the base usable at lagoon zoom.
FULL_LON = (11.95, 12.57)
FULL_LAT = (37.68, 38.12)
D_COARSE = 0.003          # ~270 m

# Lagoon, overlaid on top of the base when zoomed in.  Extends to 37.79 / 12.39
# so the whole southern arm of the lagoon is inside the detail grid.
LAG_LON = (12.39, 12.50)
LAG_LAT = (37.79, 37.92)
D_FINE = 0.0005           # ~44 m lon / 55 m lat

# Velocity rides on a coarser grid than the scalars: leaflet-velocity
# interpolates between cells anyway, and the particle field does not benefit
# from resolution the way a painted scalar field does.
VEL_STRIDE = 2


# -- mesh -------------------------------------------------------------------

def load_mesh_and_data(src):
    """Read every partition, de-duplicate ghost faces, return mesh + fields."""
    files = sorted(_glob.glob(str(Path(src) / 'DFM_OUTPUT_*' / '*_0*_map.nc')))
    if not files:
        raise SystemExit(f'no partitioned map.nc under {src}')
    print(f'Opening {len(files)} partitions ...')

    cx, cy, xb, yb = [], [], [], []
    fields = {v: [] for v in VARS}
    times = None

    for f in files:
        ds = xr.open_dataset(f)
        if times is None:
            times = ds['time'].values
        cx.append(ds['mesh2d_face_x'].values)
        cy.append(ds['mesh2d_face_y'].values)
        xb.append(ds['mesh2d_face_x_bnd'].values)
        yb.append(ds['mesh2d_face_y_bnd'].values)
        for v in VARS:
            if v not in ds:
                fields[v].append(None)
                continue
            da = ds[v]
            for d in da.dims:                       # surface layer of a 3D var
                if 'layer' in d.lower() or 'nlay' in d.lower():
                    da = da.isel({d: -1})
            fields[v].append(da.values.astype(np.float32))
        ds.close()

    cx = np.concatenate(cx)
    cy = np.concatenate(cy)
    xb = np.concatenate(xb)
    yb = np.concatenate(yb)

    # Ghost cells are shared between neighbouring partitions; Delaunay chokes
    # on exact duplicates, so keep one face per coordinate.
    _, keep = np.unique(np.round(np.c_[cx, cy], 7), axis=0, return_index=True)
    keep = np.sort(keep)

    data = {}
    for v in VARS:
        if any(p is None for p in fields[v]):
            data[v] = None
            print(f'  {v}: absent from this run')
            continue
        data[v] = np.concatenate(fields[v], axis=1)[:, keep]

    print(f'  faces {cx.size} -> {keep.size} unique, {len(times)} timesteps')
    return cx[keep], cy[keep], xb[keep], yb[keep], times, data


def wet_mask(xb, yb, lon_vec, lat_vec):
    """True where the grid point falls inside some mesh face.

    Walks the faces rather than the grid points: each face touches only a
    handful of cells, so the total work scales with the wet area, not with
    faces x points.
    """
    nx, ny = lon_vec.size, lat_vec.size
    lon0, lat0 = lon_vec[0], lat_vec[0]
    dlon = lon_vec[1] - lon_vec[0]
    dlat = lat_vec[1] - lat_vec[0]
    mask = np.zeros((ny, nx), bool)

    for k in range(xb.shape[0]):
        px, py = xb[k], yb[k]
        good = np.isfinite(px) & np.isfinite(py)
        if good.sum() < 3:
            continue
        px, py = px[good], py[good]

        i0 = int(np.floor((px.min() - lon0) / dlon))
        i1 = int(np.ceil((px.max() - lon0) / dlon))
        j0 = int(np.floor((py.min() - lat0) / dlat))
        j1 = int(np.ceil((py.max() - lat0) / dlat))
        i0, i1 = max(i0, 0), min(i1 + 1, nx)
        j0, j1 = max(j0, 0), min(j1 + 1, ny)
        if i0 >= i1 or j0 >= j1:
            continue

        sub_lon = lon_vec[i0:i1]
        sub_lat = lat_vec[j0:j1]
        L, A = np.meshgrid(sub_lon, sub_lat)
        hit = MplPath(np.c_[px, py]).contains_points(np.c_[L.ravel(), A.ravel()])
        if hit.any():
            mask[j0:j1, i0:i1] |= hit.reshape(L.shape)

    return mask


class FastGridInterp:
    """Delaunay triangulation built once; barycentric weights reused."""

    def __init__(self, pts, xi):
        tri = Delaunay(pts)
        si = tri.find_simplex(xi)
        self._in = si >= 0
        si_c = np.where(self._in, si, 0)
        T = tri.transform[si_c, :2, :]
        r = xi - tri.transform[si_c, 2]
        b2 = np.einsum('mij,mj->mi', T, r)
        bary = np.c_[b2, 1 - b2.sum(1)].astype(np.float32)
        self._bary = bary[self._in]
        self._verts = tri.simplices[si_c][self._in]
        self._size = len(xi)

    def __call__(self, values):
        out = np.full(self._size, np.nan, np.float32)
        if self._in.any():
            out[self._in] = (values[self._verts] * self._bary).sum(1)
        return out


# -- driver -----------------------------------------------------------------

def regrid(label, lons, lats, step, cx, cy, xb, yb, times, data, out_dir):
    lon_vec = np.arange(lons[0], lons[1] + step / 2, step)
    lat_vec = np.arange(lats[0], lats[1] + step / 2, step)
    ny, nx = lat_vec.size, lon_vec.size
    L, A = np.meshgrid(lon_vec, lat_vec)
    xi = np.column_stack([L.ravel(), A.ravel()])
    n_t = len(times)

    print(f'[{label}] {nx}x{ny} at {step} deg')

    print(f'[{label}] exact wet mask ...')
    mask = wet_mask(xb, yb, lon_vec, lat_vec)
    print(f'[{label}]   {mask.sum()} / {mask.size} wet ({100*mask.mean():.1f}%)')

    # Interpolate from face centres near this window only.
    buf = 0.1
    dom = ((cx >= lons[0] - buf) & (cx <= lons[1] + buf) &
           (cy >= lats[0] - buf) & (cy <= lats[1] + buf))
    print(f'[{label}] triangulating {int(dom.sum())} faces ...')
    interp = FastGridInterp(np.column_stack([cx[dom], cy[dom]]), xi)

    grids = {}
    for v in VARS:
        if data[v] is None:
            grids[v] = None
            continue
        arr = np.full((n_t, ny, nx), np.nan, np.float32)
        src = data[v][:, dom]
        for i in range(n_t):
            if i % 100 == 0:
                print(f'[{label}]   {v} frame {i}/{n_t}')
            vals = src[i].copy()
            vals[np.abs(vals) > 1e9] = np.nan
            g = interp(vals).reshape(ny, nx)
            g[~mask] = np.nan
            arr[i] = g
        grids[v] = arr

    ds = xr.Dataset(
        {v: xr.DataArray(grids[v], dims=['time', 'lat', 'lon'])
         for v in VARS if grids[v] is not None},
        coords={'time': times, 'lat': lat_vec, 'lon': lon_vec},
    )
    ds['wet'] = xr.DataArray(mask, dims=['lat', 'lon'])
    ds.attrs['grid_step'] = step
    ds.attrs['vel_stride'] = VEL_STRIDE

    path = Path(out_dir) / f'demo_{label}.nc'
    enc = {v: {'zlib': True, 'complevel': 4} for v in ds.data_vars}
    ds.to_netcdf(path, encoding=enc)
    print(f'[{label}] wrote {path}  ({path.stat().st_size / 1e6:.1f} MB)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='model dir holding DFM_OUTPUT_*/')
    ap.add_argument('--out', required=True, help='where to write demo_*.nc')
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cx, cy, xb, yb, times, data = load_mesh_and_data(args.src)

    regrid('coarse', FULL_LON, FULL_LAT, D_COARSE,
           cx, cy, xb, yb, times, data, out_dir)
    regrid('fine', LAG_LON, LAG_LAT, D_FINE,
           cx, cy, xb, yb, times, data, out_dir)


if __name__ == '__main__':
    main()
