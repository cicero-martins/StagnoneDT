"""Net discharge between the sea and the sub-basins of the lagoon, and the mean levels.

The flow flux mesh2d_q1 of the map output, summed over the layers, is added up
on the edges that separate two of the regions sea, southern, central and
northern basin (renewal_common.basin_id, with the lagoon taken from the
lagoon_tracer at the first output), positive from the region of lower to the
region of higher number, sea being 0. An edge is counted by the partition that
owns its first face. The time-mean water level is given on the sea faces
adjacent to each basin, inside each basin, and in a band of the coastal sea
west of Isola Lunga, after the first day.

Runs on plain xarray next to the partitioned map output.

Usage:
    python diagnose_lagoon_throughflow.py <model dir> <tag> [--out <dir>]
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from renewal_common import basin_id, lagoon_faces

ROOT = Path(__file__).resolve().parents[1]
NAMES = {0: "sea", 1: "S", 2: "C", 3: "N"}
COAST_BAND = (12.36, 12.42)       # lon, coastal sea west of Isola Lunga


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("tag")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "renewal")
    args = ap.parse_args(argv)
    out = args.out / args.tag
    out.mkdir(parents=True, exist_ok=True)

    flux, levels, coast = {}, {}, []
    times = None
    for f in sorted(glob.glob(str(args.src / "DFM_OUTPUT_*" / "*_0[0-9][0-9][0-9]_map.nc"))):
        p = int(Path(f).name.split("_")[-2])
        with xr.open_dataset(f) as ds:
            times = ds.time.values
            own = ds.mesh2d_flowelem_domain.values == p
            x, y = ds.mesh2d_face_x.values, ds.mesh2d_face_y.values
            lagoon = lagoon_faces(args.src, x, y)
            b = basin_id(y, lagoon)
            ef = ds.mesh2d_edge_faces.values
            ef = np.where(np.isfinite(ef), ef, 0).astype(int) - int(ds.mesh2d_edge_faces.attrs.get("start_index", 0))
            ok = (ef >= 0).all(1)
            f1, f2 = np.where(ok, ef[:, 0], 0), np.where(ok, ef[:, 1], 0)
            q = ds.mesh2d_q1.values
            if q.ndim == 3:
                q = np.nansum(np.where(np.abs(q) > 1e9, np.nan, q), axis=-1)
            for e in np.flatnonzero(ok & own[f1] & (b[f1] != b[f2])):
                key = (min(b[f1[e]], b[f2[e]]), max(b[f1[e]], b[f2[e]]))
                sgn = 1 if b[f1[e]] == key[0] else -1
                flux[key] = flux.get(key, 0) + sgn * q[:, e]
            s1 = ds.mesh2d_s1.values
            s1 = np.where(np.abs(s1) > 1e9, np.nan, s1)[(times - times[0]) >= np.timedelta64(1, "D")]
            sm = np.nanmean(s1, axis=0)
            for e in np.flatnonzero(ok):
                for a, c in ((f1[e], f2[e]), (f2[e], f1[e])):
                    if own[a] and b[a] == 0 and b[c] > 0:
                        levels.setdefault(f"sea next to {NAMES[b[c]]}", {})[a + p * 10**7] = sm[a]
            for k in (1, 2, 3):
                for a in np.flatnonzero(own & (b == k)):
                    levels.setdefault(f"inside {NAMES[k]}", {})[a + p * 10**7] = sm[a]
            band = own & (x > COAST_BAND[0]) & (x < COAST_BAND[1])
            coast.append(np.c_[y[band], sm[band]])

    df = pd.DataFrame({f"{NAMES[k[0]]}->{NAMES[k[1]]}": v for k, v in sorted(flux.items())},
                      index=pd.to_datetime(times))
    df.to_csv(out / "throughflow.csv")
    late = df[df.index >= df.index[0] + pd.Timedelta("1D")]
    print(f"{args.tag}: net discharge after the first day, m3/s, positive from first to second")
    print(late.agg(["mean", "std", "min", "max"]).round(1).to_string())
    print(f"hours of inflow at the northern mouth: {(late['sea->N'] > 0).mean():.3f}")
    print("time-mean water level after the first day, m")
    for k, v in sorted(levels.items()):
        print(f"  {k:16s} {np.nanmean(list(v.values())):+.3f}")
    c = np.concatenate(coast)
    print(f"  coastal sea {COAST_BAND[0]}-{COAST_BAND[1]} E by latitude:")
    for lat in np.arange(37.79, 37.98, 0.03):
        m = (c[:, 0] >= lat) & (c[:, 0] < lat + 0.03)
        if np.isfinite(c[m, 1]).any():
            print(f"    {lat:.2f}-{lat + 0.03:.2f} N  {np.nanmean(c[m, 1]):+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
