"""Compact fields of the renewal case for the animations, on simit.

The online lagoon_tracer of FM and the three basin tracers of D-WAQ are
averaged over the column and taken every two hours on the faces of the merged
mesh of waqmerge that lie inside the box of the figures. The faces of FM
partitions are matched to those of the merged mesh by the nearest centre. With
uniform sigma layers the plain mean over the layers is the volume mean.

Written to <out>/<tag>/frames.npz together with the face polygons, the bed
level and the basin of each face, so that the figures need no other file of
the case.

Usage, on simit:
    python extract_renewal_frames.py <case dir> <tag> --out <dir>
        [--waq waq_renewal_s24] [--every-hours 2]
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree

from renewal_common import basin_id, lagoon_faces

BOX = (12.38, 12.50, 37.79, 37.93)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", type=Path)
    ap.add_argument("tag")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--waq", default="waq_renewal_s24")
    ap.add_argument("--every-hours", type=int, default=2)
    args = ap.parse_args(argv)

    geom = args.case / "DFM_DELWAQ_Stagnone_dxy01_15m" / "Stagnone_dxy01_15m_waqgeom.nc"
    with xr.open_dataset(geom) as g:
        x, y = g.mesh2d_face_x.values, g.mesh2d_face_y.values
        nx, ny = g.mesh2d_node_x.values, g.mesh2d_node_y.values
        fn = g.mesh2d_face_nodes.values
        start = int(g.mesh2d_face_nodes.attrs.get("start_index", 0))
        nz = g.mesh2d_node_z.values if "mesh2d_node_z" in g else None
    sel = np.flatnonzero((x > BOX[0]) & (x < BOX[1]) & (y > BOX[2]) & (y < BOX[3]))
    fn = fn[sel]
    ok = np.isfinite(fn) & (fn >= start)
    fn = np.where(ok, fn - start, -1).astype(np.int32)
    basin = basin_id(y[sel], lagoon_faces(args.case, x[sel], y[sel]))
    tree = cKDTree(np.c_[x, y])
    slot = np.full(x.size, -1)
    slot[sel] = np.arange(sel.size)

    with xr.open_dataset(args.case / args.waq / "renewal_map.nc") as ds:
        tw = pd.to_datetime(ds.nTimesDlwq.values)[:-1]
        keep = np.flatnonzero((tw - tw[0]) % pd.Timedelta(hours=args.every_hours) == pd.Timedelta(0))
        waq = np.stack([ds[f"mesh2d_cTR{k}"].values[keep][:, :, sel].mean(1) for k in (1, 2, 3)])
    waq = np.where(np.abs(waq) > 1e9, np.nan, waq).astype(np.float32)
    times = tw[keep]

    fm = np.full((times.size, sel.size), np.nan, np.float32)
    bl = np.full(sel.size, np.nan, np.float32)
    for f in sorted(glob.glob(str(args.case / "DFM_OUTPUT_*" / "*_0[0-9][0-9][0-9]_map.nc"))):
        p = int(f.split("_")[-2])
        with xr.open_dataset(f) as ds:
            own = ds.mesh2d_flowelem_domain.values == p
            # the merged mesh places the centre of a third of the faces up to
            # 0.002 degrees from that of FM, and the nearest centre is still
            # one to one over the 25 210 faces, so it is taken without a tolerance
            d, j = tree.query(np.c_[ds.mesh2d_face_x.values[own], ds.mesh2d_face_y.values[own]],
                              distance_upper_bound=0.005)
            hit = np.isfinite(d)
            j = np.where(hit, slot[np.minimum(j, x.size - 1)], -1)
            hit &= j >= 0
            tf = pd.to_datetime(ds.time.values)
            k = np.searchsorted(tf, times)
            c = ds.mesh2d_lagoon_tracer.values[k][:, own][:, hit]
            fm[:, j[hit]] = np.nanmean(np.where(c < -900, np.nan, c), -1)
            bl[j[hit]] = ds.mesh2d_flowelem_bl.values[own][hit]
    print(f"{sel.size} faces in the box, {np.isfinite(bl).sum()} matched to FM, {times.size} frames")

    out = args.out / args.tag
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "frames.npz", times=times.values.astype("datetime64[s]").astype(str),
                        x=x[sel], y=y[sel], node_x=nx, node_y=ny, face_nodes=fn, basin=basin,
                        bed_level=bl, fm=fm, waq=waq,
                        node_z=nz if nz is not None else np.array([]))
    print(f"wrote {out / 'frames.npz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
