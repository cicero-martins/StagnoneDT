"""Stratified initial condition for the offshore, with the hypersaline lagoon kept.

The no-waves member starts from a column at uniform 24 C and 37.5 everywhere,
while the open boundary imposes the stratified water of CMEMS, about 14.6 C
at 600 m. Over the western slope of Marettimo, 1.3 km inside the boundary,
the baroclinic adjustment of that mismatch drives currents of several m/s in
the first hour, and any vertical discretisation other than 10 layers fails
there (build_v04AE_nowaves_layers.py).

This script writes the inputs of an initial condition consistent with the
boundary, for initialFields.ini:

  ic3d_temperature_profile.pli  vertical profile of temperature, (z, T)
  ic3d_salinity_profile.pli     vertical profile of salinity, (z, S)
  ic3d_lagoon_salinity.xyz      the hypersaline samples of the member, lagoon
                                faces only
  ic3d_lagoon_temperature.xyz   the initial temperature of the member, 24 C,
                                at the same points

The profiles are the mean over the sea points of the CMEMS nudging field of
the member (GLORYS, daily means at 12:00 on 30 June and 1 July 2025),
interpolated linearly in time to the start, 1 July 00:00. FM applies them as
horizontally uniform profiles. The lagoon samples are applied after them as
depth-uniform fields with cell averaging, so that every lagoon cell of the
v04 mesh, whose centre holds a sample, keeps the salinity and temperature of
the member, and every other cell keeps the profiles. The lagoon is the set of samples where
lagoon_tracer_init.xyz exceeds 0.5, as in the bed-level twin.

Usage:
    python build_ic3d_profiles.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
MEMBER = ROOT / 'model/dflowfm_v04AE_nowaves'
NUDGE = MEMBER / 'nudge_salinity_temperature_2025-07-01_00-00-00.nc'
SAMPLES = MEMBER / 'initialsalinity_hypersaline.xyz'
TRACER = MEMBER / 'lagoon_tracer_init.xyz'
OUT = ROOT / 'data/processed/ic3d'
T0 = np.datetime64('2025-07-01T00:00')
Z_MAX = 800.0
LAGOON_T = 24.0   # initial temperature of the member (MDU default), kept in the lagoon


def write_pli(path, name, z, v):
    with open(path, 'w') as f:
        f.write(f'{name}\n    {len(z)}    2\n')
        for a, b in zip(z, v):
            f.write(f'{a:12.3f} {b:10.4f}\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ds = xr.open_dataset(NUDGE)
    w = float((T0 - ds.time.values[0]) / (ds.time.values[1] - ds.time.values[0]))
    prof = {}
    for v in ('thetao', 'so'):
        a = (1 - w) * ds[v].isel(time=0) + w * ds[v].isel(time=1)
        m = a.mean(('latitude', 'longitude'), skipna=True)
        n = a.notnull().sum(('latitude', 'longitude'))
        keep = (ds.depth.values <= Z_MAX) & (n.values > 0)
        prof[v] = (-ds.depth.values[keep][::-1], m.values[keep][::-1], n.values[keep][::-1])
    z, T, nT = prof['thetao']
    _, S, _ = prof['so']
    # The profile is extended to the surface and below the deepest CMEMS level.
    z = np.r_[-1000.0, z, 0.0]
    T = np.r_[T[0], T, T[-1]]
    S = np.r_[S[0], S, S[-1]]
    write_pli(OUT / 'ic3d_temperature_profile.pli', 'ic3d_temperature', z, T)
    write_pli(OUT / 'ic3d_salinity_profile.pli', 'ic3d_salinity', z, S)
    print('[profile] z (m), T (C), S, sea points')
    for a, b, c, d in zip(z[1:-1], T[1:-1], S[1:-1], nT):
        if a > -20 or a in z[1:-1][::6]:
            print(f'  {a:8.1f} {b:7.2f} {c:7.3f} {d:3d}')

    s = pd.read_csv(SAMPLES, sep=r'\s+', header=None, names=['x', 'y', 's'])
    tr = pd.read_csv(TRACER, sep=r'\s+', header=None, names=['x', 'y', 'c'])
    dist, j = cKDTree(tr[['x', 'y']].values).query(s[['x', 'y']].values)
    lag = (tr.c.values[j] > 0.5) & (dist < 1e-4)
    s[lag].to_csv(OUT / 'ic3d_lagoon_salinity.xyz', sep=' ', header=False, index=False, float_format='%.6f')
    t = s[lag].assign(s=LAGOON_T)
    t.to_csv(OUT / 'ic3d_lagoon_temperature.xyz', sep=' ', header=False, index=False, float_format='%.6f')
    print(f'[lagoon] {lag.sum()} of {len(s)} samples, salinity {s.s[lag].min():.2f} to {s.s[lag].max():.2f}, '
          f'outside the lagoon {s.s[~lag].min():.2f} to {s.s[~lag].max():.2f}')


if __name__ == '__main__':
    main()
