"""Renewal of the lagoon by particles released in the 3D currents of a member.

Adapted from MaltaDT/scripts/renewal_opendrift.py. Particles fill the water
column of the three basins of the lagoon at the start of the window and are
advected by OpenDrift (OceanDrift) in the horizontal currents written by
extract_lagoon_currents_3d.py, with a random walk for the vertical mixing and
no vertical advection. The fraction of the volume of each basin found inside
it, r(t), gives the measures of renewal of renewal_common. Particles that leave
and return are counted again on return, and a particle that leaves the box of
the currents is deactivated and counted as renewed.

Each particle stands for the volume of its share of the column, the column
being divided into N_LEVELS equal parts of a grid cell of fixed area, so that
r(t) is a fraction of the volume of the basin at the start.

The vertical diffusivity is either a constant, run at two working bounds as
for the harbours of Valletta, or, with --kz model, the eddy diffusivity of the
member written into the currents file. OpenDrift 1.14 reads both
diffusivities as environment variables and accepts
drift:horizontal_diffusivity without applying it, so both are set as
environment constants, and a constant overrides the field of the file.

Usage:
    python renewal_lagoon_opendrift.py <currents file> <tag> [--kz 1e-4 1e-2 model]
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from renewal_common import BASINS, summary

ROOT = Path(__file__).resolve().parents[1]
N_LEVELS = 3                      # particles per column, at the centres of equal parts
MIN_DEPTH = 0.2                   # m, columns shallower than this are not seeded
STRIDE = 2                        # seed every second grid point, about 100 m apart
HORIZONTAL_DIFFUSIVITY = 0.1      # m2/s, working value as for Valletta
TIME_STEP = 300                   # s
VERTICAL_STEP = 60                # s, random walk of the mixing


def label(kz: str) -> str:
    return "model" if kz == "model" else f"{float(kz):.0e}"


def seeds(currents: xr.Dataset):
    """Positions, depths, volume weights and basin of each particle."""
    L, A = np.meshgrid(currents.lon.values, currents.lat.values)
    H = currents.sea_floor_depth_below_sea_level.values
    b = currents.basin.values
    take = np.zeros_like(b, bool)
    take[::STRIDE, ::STRIDE] = True
    cell = (STRIDE * float(np.diff(currents.lon.values[:2])[0]) * 111320 * np.cos(np.radians(37.86))
            * STRIDE * float(np.diff(currents.lat.values[:2])[0]) * 110540)
    lon, lat, z, w, basin = [], [], [], [], []
    for n, name in BASINS.items():
        inside = take & (b == n) & (H >= MIN_DEPTH)
        for f in (np.arange(N_LEVELS) + 0.5) / N_LEVELS:
            lon.append(L[inside]); lat.append(A[inside])
            z.append(-f * H[inside]); w.append(H[inside] * cell / N_LEVELS)
            basin.append(np.full(inside.sum(), n))
        print(f"{name}: {inside.sum()} columns, volume below the bed datum {H[inside].sum() * cell / 1e6:.2f} hm3")
    return [np.concatenate(a) for a in (lon, lat, z, w, basin)]


def run(path: Path, kz: str, out: Path) -> Path:
    from opendrift.models.oceandrift import OceanDrift
    from opendrift.readers import reader_netCDF_CF_generic

    currents = xr.open_dataset(path)
    lon, lat, z, w, basin = seeds(currents)
    start = pd.Timestamp(currents.time.values[0]).to_pydatetime()
    stop = pd.Timestamp(currents.time.values[-1]).to_pydatetime()
    o = OceanDrift(loglevel=50)   # the shallow lagoon sends hundreds of seafloor warnings a step
    o.add_reader(reader_netCDF_CF_generic.Reader(str(path)))
    config = {"general:use_auto_landmask": False,
              "general:coastline_action": "previous",
              "general:seafloor_action": "previous",
              "drift:advection_scheme": "runge-kutta4",
              "drift:vertical_advection": False,
              "drift:vertical_mixing": True,
              "environment:constant:horizontal_diffusivity": HORIZONTAL_DIFFUSIVITY,
              "vertical_mixing:diffusivitymodel": "environment",
              "vertical_mixing:timestep": VERTICAL_STEP,
              "seed:wind_drift_factor": 0.0}
    if kz != "model":
        config["environment:constant:ocean_vertical_diffusivity"] = float(kz)
    for key, value in config.items():
        o.set_config(key, value)
    o.seed_elements(lon=lon, lat=lat, z=z, time=start, wind_drift_factor=0.0)
    path_out = out / f"particles_kz{label(kz)}.nc"
    o.run(end_time=stop - timedelta(seconds=TIME_STEP), time_step=TIME_STEP,
          time_step_output=3600, outfile=str(path_out), export_variables=["lon", "lat", "z"])
    np.savez(out / f"seeds_kz{label(kz)}.npz", w=w, basin=basin, lon=lon, lat=lat, z=z)
    return path_out


def positions(particles: Path, currents: Path):
    """Basin of each particle at each output, -1 once it has left the box."""
    with xr.open_dataset(currents) as c:
        glon, glat, b = c.lon.values, c.lat.values, c.basin.values
    with xr.open_dataset(particles) as ds:
        lon, lat = ds.lon.values, ds.lat.values          # (trajectory, time)
        times = pd.to_datetime(ds.time.values)
    i = np.rint((lon - glon[0]) / (glon[1] - glon[0]))
    j = np.rint((lat - glat[0]) / (glat[1] - glat[0]))
    ok = np.isfinite(i) & np.isfinite(j) & (i >= 0) & (i < glon.size) & (j >= 0) & (j < glat.size)
    where = np.full(lon.shape, -1, np.int8)
    where[ok] = b[j[ok].astype(int), i[ok].astype(int)]
    return times, where


def tables(times, where, s):
    """Remaining fraction of each basin and of the lagoon, and the fate of each basin."""
    w = s["w"]
    rows = {"lagoon": ((where > 0) * w[:, None]).sum(0) / w.sum()}
    fate = {}
    for n, name in BASINS.items():
        own = s["basin"] == n
        rows[name] = ((where[own] == n) * w[own, None]).sum(0) / w[own].sum()
        fate[name] = {dest: float(((where[own, -1] == k) * w[own]).sum() / w[own].sum())
                      for k, dest in [(1, "southern"), (2, "central"), (3, "northern"),
                                      (0, "sea in the box"), (-1, "out of the box")]}
    return pd.DataFrame(rows, index=times), fate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("currents", type=Path)
    ap.add_argument("tag")
    ap.add_argument("--kz", nargs="+", default=["1e-4", "1e-2", "model"],
                    help="vertical diffusivity, m2/s, or model for the field of the file")
    ap.add_argument("--analyse-only", action="store_true",
                    help="summarise particle files already written")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "renewal")
    args = ap.parse_args(argv)
    out = args.out / args.tag
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for kz in args.kz:
        p = out / f"particles_kz{label(kz)}.nc" if args.analyse_only else run(args.currents, kz, out)
        times, where = positions(p, args.currents)
        r, fate = tables(times, where, np.load(out / f"seeds_kz{label(kz)}.npz"))
        r.to_csv(out / f"remaining_kz{label(kz)}.csv")
        results[label(kz)] = {"summary": {k: summary(r[k]) for k in r}, "fate": fate}
        print(json.dumps(results[label(kz)], indent=1))
    (out / "particles_summary.json").write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
