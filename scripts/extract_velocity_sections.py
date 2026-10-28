"""Extract vertical sections of the 3D velocity field for the WetWise portal.

Companion to regrid_wetwise_source.py, and like it runs on plain
xarray/scipy so it can execute on the compute server next to the partitioned
output.  Two products are written to one cache file:

1. Sections along fixed polylines, sampled every SECTION_DS metres, with the
   velocity of every sigma layer decomposed into the component normal to the
   section, the component along it and the vertical one.  Layer elevations are
   reconstructed from the uniform sigma distribution of the ensemble,
   z_k = bl + (k + 1/2) / kmx * (s1 - bl), with k = 0 at the bed.
2. The surface-layer velocity on a coarse regular grid over the lagoon, which
   the perspective view draws as arrows on the plane above the sections.

Usage
    python extract_velocity_sections.py --src <model dir> --out <cache dir>
"""
from pathlib import Path
import argparse
import glob as _glob
import sys

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regrid_wetwise_source import FastGridInterp, wet_mask  # noqa: E402

# The N-S axis runs from the Bocca Nord through the centre of the lagoon to
# the deep southern basin; the E-W cut crosses the centre south of Mozia, so
# that it does not run through the island.
SECTIONS = {
    'ns_axis': [(12.4572, 37.9053), (12.4620, 37.8670),
                (12.4560, 37.8450), (12.4600, 37.8250),
                (12.4495, 37.8140)],
    'ew_centre': [(12.4450, 37.8620), (12.4800, 37.8620)],
}
SECTION_DS = 25.0                 # m between section samples

BOX_LON = (12.43, 12.50)          # faces read for the interpolation
BOX_LAT = (37.805, 37.915)
SURF_STEP = 0.001                 # ~90 m, particles and arrows on the surface

# The lagoon is meshed with triangles that follow the shore, and the open sea
# with a quadtree of quadrilaterals, so the lagoon faces are the triangles.
# Transition triangles of the quadtree west of the Bocca Sud and north of the
# Bocca Nord are excluded by this polygon, whose edges run only through the
# sea and across Isola Grande, never along the lagoon shore.
LAGOON_CLIP = [(12.4446, 37.8205), (12.4446, 37.8960), (12.4540, 37.8975),
               (12.4555, 37.9075), (12.4640, 37.9075), (12.5000, 37.9000),
               (12.5000, 37.8000), (12.4300, 37.8000)]

R_EARTH = 6371000.0


def to_xy(lon, lat, lat0):
    """Local equirectangular metres, adequate over a 10 km lagoon."""
    k = np.pi / 180 * R_EARTH
    return lon * k * np.cos(np.radians(lat0)), lat * k


def sample_polyline(vertices, ds, lat0):
    """Points every ds metres along the polyline, with distance and tangent."""
    v = np.asarray(vertices, float)
    x, y = to_xy(v[:, 0], v[:, 1], lat0)
    seg = np.hypot(np.diff(x), np.diff(y))
    cum = np.r_[0, np.cumsum(seg)]
    s = np.arange(0, cum[-1] + ds / 2, ds)
    xs, ys = np.interp(s, cum, x), np.interp(s, cum, y)
    k = np.pi / 180 * R_EARTH
    lon = xs / (k * np.cos(np.radians(lat0)))
    lat = ys / k
    # tangent of the segment each sample falls on
    iseg = np.clip(np.searchsorted(cum, s, side='right') - 1, 0, len(seg) - 1)
    tx, ty = np.diff(x)[iseg] / seg[iseg], np.diff(y)[iseg] / seg[iseg]
    return s, lon, lat, tx, ty


def load_box(src):
    """Face geometry and 3D fields of the faces inside BOX, all partitions."""
    files = sorted(_glob.glob(str(Path(src) / 'DFM_OUTPUT_*' / '*_0*_map.nc')))
    if not files:
        raise SystemExit(f'no partitioned map.nc under {src}')
    print(f'Opening {len(files)} partitions ...')
    parts = {k: [] for k in ('cx', 'cy', 'xb', 'yb', 'bl', 's1',
                             'ucx', 'ucy', 'ucz')}
    times = None
    for f in files:
        ds = xr.open_dataset(f)
        if times is None:
            times = ds['time'].values
        cx, cy = ds['mesh2d_face_x'].values, ds['mesh2d_face_y'].values
        sel = np.flatnonzero((cx >= BOX_LON[0]) & (cx <= BOX_LON[1]) &
                             (cy >= BOX_LAT[0]) & (cy <= BOX_LAT[1]))
        if sel.size:
            fd = 'mesh2d_nFaces'
            parts['cx'].append(cx[sel])
            parts['cy'].append(cy[sel])
            parts['xb'].append(ds['mesh2d_face_x_bnd'].values[sel])
            parts['yb'].append(ds['mesh2d_face_y_bnd'].values[sel])
            # with a mobile bed the bed level evolves; otherwise it is static
            if 'mesh2d_mor_bl' in ds:
                bl = ds['mesh2d_mor_bl'].isel({fd: sel}).values
            else:
                bl0 = ds['mesh2d_flowelem_bl'].values[sel]
                bl = np.broadcast_to(bl0, (len(times), sel.size))
            parts['bl'].append(np.asarray(bl, np.float32))
            parts['s1'].append(ds['mesh2d_s1'].isel({fd: sel}).values
                               .astype(np.float32))
            for v in ('ucx', 'ucy', 'ucz'):
                parts[v].append(ds[f'mesh2d_{v}'].isel({fd: sel}).values
                                .astype(np.float32))
        ds.close()

    out = {k: np.concatenate(v, axis=0 if k in ('cx', 'cy', 'xb', 'yb')
                             else 1) for k, v in parts.items()}
    _, keep = np.unique(np.round(np.c_[out['cx'], out['cy']], 7), axis=0,
                        return_index=True)
    keep = np.sort(keep)
    for k in out:
        out[k] = out[k][keep] if k in ('cx', 'cy', 'xb', 'yb') \
            else out[k][:, keep]
    for v in ('ucx', 'ucy', 'ucz', 's1', 'bl'):
        out[v][np.abs(out[v]) > 1e9] = np.nan
    print(f'  {keep.size} faces in the box, {len(times)} timesteps, '
          f'{out["ucx"].shape[2]} layers')
    return times, out


def point_in_faces(xb, yb, lon, lat):
    """True where a sample point falls inside some mesh face."""
    from matplotlib.path import Path as MplPath
    hit = np.zeros(lon.size, bool)
    pts = np.c_[lon, lat]
    for k in range(xb.shape[0]):
        px, py = xb[k], yb[k]
        good = np.isfinite(px) & np.isfinite(py)
        if good.sum() < 3:
            continue
        px, py = px[good], py[good]
        near = ((lon >= px.min()) & (lon <= px.max()) &
                (lat >= py.min()) & (lat <= py.max()) & ~hit)
        if near.any():
            hit[near] = MplPath(np.c_[px, py]).contains_points(pts[near])
    return hit


def interp_all(interp, arr):
    """Apply a FastGridInterp to (time, face[, layer]) -> (time, pt[, layer])."""
    if arr.ndim == 2:
        return np.stack([interp(arr[i]) for i in range(arr.shape[0])])
    return np.stack([np.stack([interp(arr[i, :, k])
                               for k in range(arr.shape[2])], axis=-1)
                     for i in range(arr.shape[0])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='model dir holding DFM_OUTPUT_*/')
    ap.add_argument('--out', required=True, help='where to write sections.nc')
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    times, f = load_box(args.src)
    kmx = f['ucx'].shape[2]
    lat0 = float(np.mean(BOX_LAT))
    pts_faces = np.c_[f['cx'], f['cy']]
    sigma = (np.arange(kmx) + 0.5) / kmx

    data_vars, coords = {}, {'time': times, 'layer': np.arange(kmx),
                             'sigma': ('layer', sigma)}
    for name, verts in SECTIONS.items():
        s, lon, lat, tx, ty = sample_polyline(verts, SECTION_DS, lat0)
        wet = point_in_faces(f['xb'], f['yb'], lon, lat)
        interp = FastGridInterp(pts_faces, np.c_[lon, lat])
        s1 = interp_all(interp, f['s1'])
        bl = interp_all(interp, f['bl'])
        u = interp_all(interp, f['ucx'])
        v = interp_all(interp, f['ucy'])
        w = interp_all(interp, f['ucz'])
        for a in (s1, bl, u, v, w):
            a[:, ~wet] = np.nan
        # normal points to the left of the direction of travel
        nx, ny = -ty, tx
        un = u * nx[None, :, None] + v * ny[None, :, None]
        ut = u * tx[None, :, None] + v * ty[None, :, None]
        z = bl[..., None] + sigma[None, None, :] * (s1 - bl)[..., None]

        d = f'{name}_pt'
        coords[f'{name}_dist'] = (d, s)
        coords[f'{name}_lon'] = (d, lon)
        coords[f'{name}_lat'] = (d, lat)
        data_vars[f'{name}_s1'] = (('time', d), s1)
        data_vars[f'{name}_bl'] = (('time', d), bl)
        data_vars[f'{name}_z'] = (('time', d, 'layer'), z.astype(np.float32))
        data_vars[f'{name}_un'] = (('time', d, 'layer'), un.astype(np.float32))
        data_vars[f'{name}_ut'] = (('time', d, 'layer'), ut.astype(np.float32))
        data_vars[f'{name}_w'] = (('time', d, 'layer'), w.astype(np.float32))
        print(f'[{name}] {s.size} samples over {s[-1]:.0f} m, '
              f'{int(wet.sum())} wet')

    # lagoon faces, drawn as they are in the mesh
    from matplotlib.path import Path as MplPath
    tri = np.isfinite(f['xb']).sum(1) == 3
    lag = tri & MplPath(LAGOON_CLIP).contains_points(np.c_[f['cx'], f['cy']])
    xb3 = np.stack([r[np.isfinite(r)] for r in f['xb'][lag]])
    yb3 = np.stack([r[np.isfinite(r)] for r in f['yb'][lag]])
    data_vars['lag_xb'] = (('lface', 'corner'), xb3)
    data_vars['lag_yb'] = (('lface', 'corner'), yb3)
    data_vars['lag_s1'] = (('time', 'lface'), f['s1'][:, lag])
    for v in ('ucx', 'ucy'):
        data_vars[f'lag_{v}'] = (('time', 'lface'), f[v][:, lag, -1])
    print(f'[lagoon] {int(lag.sum())} triangular faces')

    # surface grid for particles and arrows, wet only inside lagoon faces
    glon = np.arange(BOX_LON[0], BOX_LON[1] + SURF_STEP / 2, SURF_STEP)
    glat = np.arange(BOX_LAT[0], BOX_LAT[1] + SURF_STEP / 2, SURF_STEP)
    L, A = np.meshgrid(glon, glat)
    mask = wet_mask(f['xb'][lag], f['yb'][lag], glon, glat)
    interp = FastGridInterp(pts_faces, np.c_[L.ravel(), A.ravel()])
    shp = (len(times),) + L.shape
    for v in ('ucx', 'ucy'):
        g = interp_all(interp, f[v][:, :, -1]).reshape(shp)
        g[:, ~mask] = np.nan
        data_vars[f'surf_{v}'] = (('time', 'slat', 'slon'), g)
    g = interp_all(interp, f['s1']).reshape(shp)
    g[:, ~mask] = np.nan
    data_vars['surf_s1'] = (('time', 'slat', 'slon'), g)
    coords.update(slon=glon, slat=glat)

    ds = xr.Dataset(data_vars, coords=coords)
    ds.attrs.update(source=str(Path(args.src).name), kmx=kmx,
                    layer_distribution='uniform sigma',
                    section_ds_m=SECTION_DS,
                    normal_convention='positive to the left of travel')
    for name, verts in SECTIONS.items():
        ds.attrs[f'{name}_vertices'] = str(verts)
    path = out_dir / 'sections.nc'
    ds.to_netcdf(path, encoding={v: {'zlib': True, 'complevel': 4}
                                 for v in ds.data_vars})
    print(f'wrote {path}  ({path.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
