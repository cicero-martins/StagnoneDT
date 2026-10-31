"""Renewal of the lagoon from the offline tracers of D-Water Quality.

Reads the map output of the run written by build_renewal_waq.py and the
volumes of the hydrodynamics it ran on. The mass of each tracer in a region is
the concentration times the segment volume summed over the segments of the
region, the volume being read from the binary volumes file at the instants of
the map output. For each basin the mass of its own tracer still inside it,
divided by its initial mass, is the remaining fraction r(t), and the mass of
the three lagoon tracers anywhere in the lagoon gives that of the whole
lagoon. The fate of each basin tracer at the end of the window fills the
exchange matrix. The four tracers sum to 1 in every segment if the transport
conserves mass, and the largest departure is reported.

Usage:
    python renewal_waq_member.py <case dir> <tag> [--out <dir>]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from renewal_common import BASINS, basin_id, lagoon_faces, summary

ROOT = Path(__file__).resolve().parents[1]
REGIONS = {**BASINS, 0: "sea"}


def volumes(vol_file: Path, nseg: int, wanted: np.ndarray) -> np.ndarray:
    """Segment volumes at the wanted times (s since the reference), (time, nseg)."""
    rec = np.dtype([("t", "<i4"), ("v", "<f4", nseg)])
    data = np.fromfile(vol_file, dtype=rec)
    idx = np.searchsorted(data["t"], wanted)
    if not np.array_equal(data["t"][idx], wanted):
        raise SystemExit("map instants missing from the volumes file")
    return data["v"][idx]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", type=Path)
    ap.add_argument("tag")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "renewal")
    args = ap.parse_args(argv)
    out = args.out / args.tag
    out.mkdir(parents=True, exist_ok=True)
    hyd = args.case / "DFM_DELWAQ_Stagnone_dxy01_15m"

    with xr.open_dataset(args.case / "waq_renewal" / "renewal_map.nc") as ds:
        times = pd.to_datetime(ds.time.values)
        c = np.stack([ds[f"mesh2d_cTR{k}"].values for k in (1, 2, 3, 4)])   # (tracer, time, layer, face)
    with xr.open_dataset(hyd / "Stagnone_dxy01_15m_waqgeom.nc") as g:
        x, y = g.mesh2d_face_x.values, g.mesh2d_face_y.values
    c = np.where(np.abs(c) > 1e9, np.nan, c)
    ntr, nt, nlay, nper = c.shape
    ref = pd.Timestamp("2025-01-01")
    secs = ((times - ref).total_seconds()).astype(np.int64)
    v = volumes(hyd / "Stagnone_dxy01_15m.vol", nlay * nper, secs).reshape(nt, nlay, nper)

    b = basin_id(y, lagoon_faces(args.case, x, y))
    mass = np.nan_to_num(c) * v[None]                                       # (tracer, time, layer, face)
    by_region = {k: mass[:, :, :, b == k].sum(axis=(2, 3)) for k in REGIONS}  # (tracer, time)
    m0 = {k: by_region[k][k - 1, 0] for k in BASINS}

    cols = {"lagoon": sum(by_region[k][:3].sum(0) for k in BASINS) / sum(m0.values())}
    for k, name in BASINS.items():
        cols[name] = by_region[k][k - 1] / m0[k]
    total = np.nansum(c, axis=0)
    wet = v > 1e-3
    cols["sum_departure_max"] = np.array([np.nanmax(np.abs(total[i][wet[i]] - 1)) for i in range(nt)])
    r = pd.DataFrame(cols, index=times)
    r.to_csv(out / "waq_remaining.csv")

    fate = {BASINS[k]: {REGIONS[j]: float(by_region[j][k - 1, -1] / m0[k]) for j in REGIONS}
            for k in BASINS}
    res = {"summary": {k: summary(r[k]) for k in ["lagoon", *BASINS.values()]}, "fate": fate,
           "initial_volume_hm3": {BASINS[k]: float(m0[k] / 1e6) for k in BASINS},
           "sum_departure_max": float(np.nanmax(cols["sum_departure_max"]))}
    (out / "waq_summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))

    daily = np.flatnonzero((times - times[0]) % pd.Timedelta("1D") == pd.Timedelta(0))
    vm = v[daily].sum(1)
    conc = np.stack([(mass[k, daily].sum(1) / np.where(vm > 0, vm, np.nan)) for k in range(ntr)])
    np.savez_compressed(out / "waq_daily.npz", cx=x, cy=y, basin=b,
                        times=times[daily].values.astype("datetime64[s]").astype(str),
                        conc=conc.astype(np.float32))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
