"""Extract the 3D currents of a member around the lagoon for OpenDrift.

Adapted from MaltaDT/scripts/extract_harbour_currents_3d.py. The partitioned
map output, without the ghost faces, is interpolated onto a regular grid in
longitude and latitude and from the sigma layers onto fixed depths below the
free surface, in the CF names read by the GenericReader of OpenDrift.

Each depth d below the surface maps to sigma = 1 - d/H in a column of depth H,
so the vertical interpolation is linear in sigma between the layer centres.
Above the top centre the top layer applies, and below the bed the deepest
layer, which OpenDrift does not reach since the bed is declared.

When the map holds the vertical eddy viscosity at the faces (mesh2d_vicwws,
wrimap_turbulence = 1), the vertical diffusivity of a scalar is written as
well, viscosity over the turbulent Prandtl-Schmidt number 0.7 of FM, linear in
sigma between the interfaces.

Grid points off the water take the values of the nearest wet point, since zero
current and depth on land would make the bilinear interpolation of OpenDrift
taper both toward the shore across one grid cell. A land mask and the basin of
each wet point (renewal_common) go into the same file.

The box holds the lagoon and some 4 km of the sea to the west and north, so
that water leaving through a mouth can return with the next reversal before
it leaves the box. Runs on plain xarray and scipy next to the map output.

Usage:
    python extract_lagoon_currents_3d.py <model dir> --out <file>
        [--start 2025-07-01T00:00] [--stop 2025-07-10T00:00] [--step 0.0005]
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import distance_transform_edt

from regrid_wetwise_source import FastGridInterp, wet_mask
from renewal_common import basin_id, lagoon_faces

BOX_LON = (12.380, 12.500)
BOX_LAT = (37.790, 37.930)
DEPTHS = np.array([0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0],
                  dtype=np.float32)
PRANDTL_SCHMIDT = 0.7


def load(src: Path):
    """Faces of the box from all partitions, ghosts left out, fields as (time, face[, layer])."""
    files = sorted(glob.glob(str(src / "DFM_OUTPUT_*" / "*_0[0-9][0-9][0-9]_map.nc")))
    keys = ("cx", "cy", "xb", "yb", "bl", "s1", "ucx", "ucy", "nu")
    parts = {k: [] for k in keys}
    times = sigma = None
    for f in files:
        p = int(Path(f).name.split("_")[-2])
        with xr.open_dataset(f) as ds:
            times = ds.time.values if times is None else times
            if sigma is None:   # height of the layer centres above the bed, uniform if absent
                kmx = ds.sizes["mesh2d_nLayers"]
                sigma = (1.0 + ds.mesh2d_layer_sigma.values if "mesh2d_layer_sigma" in ds.variables
                         else (np.arange(kmx) + 0.5) / kmx)
            cx, cy = ds.mesh2d_face_x.values, ds.mesh2d_face_y.values
            sel = np.flatnonzero((ds.mesh2d_flowelem_domain.values == p)
                                 & (cx >= BOX_LON[0] - 0.01) & (cx <= BOX_LON[1] + 0.01)
                                 & (cy >= BOX_LAT[0] - 0.01) & (cy <= BOX_LAT[1] + 0.01))
            if not sel.size:
                continue
            fd = {"mesh2d_nFaces": sel}
            parts["cx"].append(cx[sel]); parts["cy"].append(cy[sel])
            parts["xb"].append(ds.mesh2d_face_x_bnd.values[sel])
            parts["yb"].append(ds.mesh2d_face_y_bnd.values[sel])
            parts["bl"].append(ds.mesh2d_flowelem_bl.values[sel])
            parts["s1"].append(ds.mesh2d_s1.isel(fd).values.astype(np.float32))
            for k in ("ucx", "ucy"):
                parts[k].append(ds[f"mesh2d_{k}"].isel(fd).values.astype(np.float32))
            if "mesh2d_vicwws" in ds:
                parts["nu"].append(ds.mesh2d_vicwws.isel(fd).values.astype(np.float32))
    out = {k: np.concatenate(v, axis=0 if k in ("cx", "cy", "xb", "yb", "bl") else 1)
           for k, v in parts.items() if v}
    for k in ("s1", "ucx", "ucy", "nu"):
        if k in out:
            out[k][np.abs(out[k]) > 1e9] = np.nan
    print(f"{out['cx'].size} faces in the box, {times.size} times, {sigma.size} layers, "
          f"eddy viscosity {'present' if 'nu' in out else 'absent'}")
    return pd.to_datetime(times), sigma, out


def to_depths(field: np.ndarray, H: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """(point, level) on sigma to (depth, point) on DEPTHS below the surface."""
    st = 1.0 - DEPTHS[:, None] / np.maximum(H[None, :], 1e-3)
    st = np.clip(st, sigma[0], sigma[-1])
    k = np.clip(np.searchsorted(sigma, st) - 1, 0, sigma.size - 2)
    t = (st - sigma[k]) / (sigma[k + 1] - sigma[k])
    p = np.arange(field.shape[0])[None, :]
    return (1 - t) * field[p, k] + t * field[p, k + 1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", default="2025-07-01T00:00")
    ap.add_argument("--stop", default="2025-07-10T00:00")
    ap.add_argument("--step", type=float, default=0.0005, help="grid step, degrees, ~50 m")
    args = ap.parse_args(argv)

    times, sigma, f = load(args.src)
    it = np.flatnonzero((times >= pd.Timestamp(args.start)) & (times <= pd.Timestamp(args.stop)))
    interfaces = np.linspace(0.0, 1.0, sigma.size + 1, dtype=np.float32)   # uniform sigma

    glon = np.arange(BOX_LON[0], BOX_LON[1] + args.step / 2, args.step)
    glat = np.arange(BOX_LAT[0], BOX_LAT[1] + args.step / 2, args.step)
    L, A = np.meshgrid(glon, glat)
    mask = wet_mask(f["xb"], f["yb"], glon, glat).ravel()
    interp = FastGridInterp(np.c_[f["cx"], f["cy"]], np.c_[L.ravel(), A.ravel()][mask])
    print(f"grid {glon.size} x {glat.size}, {int(mask.sum())} wet points, {it.size} times")

    bed = interp(f["bl"])
    shp = (it.size, DEPTHS.size, glat.size, glon.size)
    keys = ["ucx", "ucy"] + (["nu"] if "nu" in f else [])
    fields = {k: np.full(shp, np.nan, np.float32) for k in keys}
    for n, i in enumerate(it):
        H = interp(f["s1"][i]) - bed
        for key in keys:
            lev = sigma if key != "nu" else interfaces
            lay = np.stack([interp(f[key][i, :, k]) for k in range(lev.size)], axis=-1)
            g = np.full((DEPTHS.size, mask.size), np.nan, np.float32)
            g[:, mask] = to_depths(lay, H, lev)
            fields[key][n] = g.reshape(DEPTHS.size, glat.size, glon.size)
        if n % 48 == 0:
            print(f"  {str(times[i])[:16]}")

    floor = np.full(mask.size, np.nan, np.float32)
    floor[mask] = -bed
    valid = (np.isfinite(floor) & np.isfinite(fields["ucx"][0, 0].ravel())).reshape(L.shape)
    _, (iy, ix) = distance_transform_edt(~valid, return_indices=True)
    floor = floor.reshape(L.shape)[iy, ix]
    for key in fields:
        fields[key] = fields[key][:, :, iy, ix]
    basin = basin_id(A, lagoon_faces(args.src, L, A)) * valid.astype(np.int8)

    names = {"ucx": ("x_sea_water_velocity", "eastward sea water velocity", "m s-1"),
             "ucy": ("y_sea_water_velocity", "northward sea water velocity", "m s-1"),
             "nu": ("ocean_vertical_diffusivity", "vertical eddy diffusivity of a scalar", "m2 s-1")}
    data = {}
    for k in keys:
        v = np.nan_to_num(fields[k], nan=0.0)
        if k == "nu":
            v = np.maximum(v / PRANDTL_SCHMIDT, 0.0)
        name, ln, unit = names[k]
        data[name] = (("time", "depth", "lat", "lon"), v,
                      {"standard_name": name, "long_name": ln, "units": unit})
    ds = xr.Dataset(data, coords={
        "time": times[it],
        "depth": ("depth", DEPTHS, {"standard_name": "depth", "positive": "down", "units": "m"}),
        "lat": ("lat", glat, {"standard_name": "latitude", "units": "degrees_north"}),
        "lon": ("lon", glon, {"standard_name": "longitude", "units": "degrees_east"})})
    ds["sea_floor_depth_below_sea_level"] = (("lat", "lon"), np.nan_to_num(floor, nan=0.0),
                                             {"standard_name": "sea_floor_depth_below_sea_level", "units": "m"})
    ds["land_binary_mask"] = (("lat", "lon"), (~mask).reshape(L.shape).astype(np.int8),
                              {"standard_name": "land_binary_mask"})
    ds["basin"] = (("lat", "lon"), basin, {"long_name": "0 sea, 1 southern, 2 central, 3 northern basin"})
    ds.attrs.update(source=str(args.src.resolve()), layer_distribution="uniform sigma",
                    vertical="linear in sigma between layer centres")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(args.out, encoding={v: {"zlib": True, "complevel": 4} for v in ds.data_vars})
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
