"""Renewal of the lagoon from the online lagoon_tracer of a member.

The tracer starts at 1 in the lagoon and 0 outside (lagoon_tracer_init.xyz)
and is transported by FM with the turbulent diffusivity of the model, so its
mass inside the lagoon, divided by the initial mass, is the Eulerian remaining
fraction r(t) of the lagoon water. The mass is the layer mean of the
concentration, uniform sigma layers being of equal thickness, times the face
area and the water depth, summed over the faces of each partition without the
ghost faces. Mass rather than concentration is summed, since evaporation
concentrates the tracer without changing its mass.

For each sub-basin the same ratio gives the content of lagoon water, which
other basins can resupply, so that it bounds the renewal of the basin from
above in time. The mass over the whole domain checks conservation.

Runs on plain xarray next to the partitioned map output.

Usage:
    python renewal_tracer_member.py <model dir> <tag> [--out <dir>]
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from renewal_common import BASINS, basin_id, summary

ROOT = Path(__file__).resolve().parents[1]


def read_partitions(src: Path):
    files = sorted(glob.glob(str(src / "DFM_OUTPUT_*" / "*_0[0-9][0-9][0-9]_map.nc")))
    if not files:
        raise SystemExit(f"no partitioned map.nc under {src}")
    parts = {k: [] for k in ("cx", "cy", "ba", "mass", "vol", "cmax")}
    seen = set()
    times = None
    for f in files:
        with xr.open_dataset(f, mask_and_scale=True) as ds:
            times = ds.time.values if times is None else times
            cx, cy = ds.mesh2d_face_x.values, ds.mesh2d_face_y.values
            if "mesh2d_flowelem_domain" in ds:      # ghost faces belong to another domain
                own = ds.mesh2d_flowelem_domain.values == int(Path(f).name.split("_")[-2])
            else:
                key = [(round(x, 7), round(y, 7)) for x, y in zip(cx, cy)]
                own = np.array([k not in seen for k in key])
                seen.update(key)
            ba = ds.mesh2d_flowelem_ba.values[own]
            h = (ds.mesh2d_s1.values[:, own] - ds.mesh2d_flowelem_bl.values[own]).clip(0)
            c = ds.mesh2d_lagoon_tracer.values[:, own, :]
            cm = np.nan_to_num(np.nanmean(np.where(c < -900, np.nan, c), axis=-1))
            parts["cx"].append(cx[own]); parts["cy"].append(cy[own]); parts["ba"].append(ba)
            parts["vol"].append(h * ba)
            parts["mass"].append(cm * h * ba)
            parts["cmax"].append(np.nanmax(np.where(c < -900, np.nan, c), axis=(1, 2)))
        print(f"  {Path(f).name}: {own.sum()} own faces")
    out = {k: np.concatenate(v, axis=0 if k in ("cx", "cy", "ba") else 1)
           for k, v in parts.items() if k != "cmax"}
    out["cmax"] = np.nanmax(np.stack(parts["cmax"]), axis=0)
    return pd.to_datetime(times), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("tag")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "renewal")
    args = ap.parse_args(argv)
    out = args.out / args.tag
    out.mkdir(parents=True, exist_ok=True)

    times, f = read_partitions(args.src)
    c0 = f["mass"][0] / np.where(f["vol"][0] > 0, f["vol"][0], np.nan)
    lagoon = np.nan_to_num(c0) > 0.5
    basin = basin_id(f["cy"], lagoon)
    m0 = f["mass"][0]
    cols = {"lagoon": f["mass"][:, lagoon].sum(1) / m0[lagoon].sum()}
    for b, name in BASINS.items():
        cols[name] = f["mass"][:, basin == b].sum(1) / m0[basin == b].sum()
    cols["domain"] = f["mass"].sum(1) / m0[lagoon].sum()
    cols["lagoon_volume_hm3"] = f["vol"][:, lagoon].sum(1) / 1e6
    cols["tracer_max"] = f["cmax"]
    r = pd.DataFrame(cols, index=times)
    r.to_csv(out / "tracer_remaining.csv")

    v0 = f["vol"][0]
    print(f"lagoon: {lagoon.sum()} faces, {f['ba'][lagoon].sum() / 1e6:.2f} km2, "
          f"{v0[lagoon].sum() / 1e6:.2f} hm3 at t0")
    for b, name in BASINS.items():
        s = basin == b
        print(f"  {name}: {s.sum()} faces, {v0[s].sum() / 1e6:.2f} hm3")
    print(f"domain mass / initial lagoon mass: {cols['domain'].min():.4f} to "
          f"{cols['domain'].max():.4f}; tracer max {np.nanmax(f['cmax']):.3f}")

    res = {k: summary(r[k]) for k in ["lagoon", *BASINS.values()]}
    (out / "tracer_summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))

    # depth-mean concentration of each face once a day, for the maps
    daily = np.flatnonzero((times - times[0]) % pd.Timedelta("1D") == pd.Timedelta(0))
    conc = f["mass"][daily] / np.where(f["vol"][daily] > 0, f["vol"][daily], np.nan)
    np.savez_compressed(out / "tracer_daily.npz", cx=f["cx"], cy=f["cy"], basin=basin,
                        times=times[daily].values.astype("datetime64[s]").astype(str),
                        conc=conc.astype(np.float32))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
