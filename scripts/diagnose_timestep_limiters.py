"""Which cells collapse the timestep when a run aborts on MinTimestepBreak?

FM writes mesh2d_Numlimdt -- a running count of how often each cell was the
Courant-limiting one -- when wrimap_numLimdt=1. Comparing the last two frames
before an abort turns that cumulative count into a rate, which is what
identifies the culprit: a count accumulated over the whole run is dominated by
whatever was slow from the start, not by whatever broke at the end.

The distinction that matters is one cell versus many. A single cell points at
geometry -- a thin element, a bad bed level, a dry-wet flip -- and is fixable
locally. A diffuse pattern points at the physics, and was what settled the
earlier no-waves mobile-bed abort (memory: nowaves_dm_killed_not_unstable).

Times are read undecoded on purpose: a run killed mid-write leaves the
remaining time slots at the netCDF fill value, which makes xarray's calendar
decoding raise before it ever reaches the data.

    python scripts/diagnose_timestep_limiters.py --out <DFM_OUTPUT dir>
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import xarray as xr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='a DFM_OUTPUT_* directory')
    ap.add_argument('--top', type=int, default=15)
    args = ap.parse_args()

    files = sorted(glob.glob(str(Path(args.out) / '*_0*_map.nc')))
    if not files:
        raise SystemExit(f'no partitioned map.nc under {args.out}')

    rows = []
    for f in files:
        ds = xr.open_dataset(f, decode_times=False)
        if 'mesh2d_Numlimdt' not in ds:
            print(f'{Path(f).name}: no mesh2d_Numlimdt'); ds.close(); continue
        t = ds['time'].values
        good = np.where(np.isfinite(t) & (t < 1e30))[0]
        if len(good) < 2:
            print(f'{Path(f).name}: {len(good)} valid frames, need 2'); ds.close(); continue
        i1, i0 = good[-1], good[-2]

        n1 = ds['mesh2d_Numlimdt'].values[i1]
        n0 = ds['mesh2d_Numlimdt'].values[i0]
        rate = n1 - n0                                  # limits in the last window
        x = ds['mesh2d_face_x'].values
        y = ds['mesh2d_face_y'].values
        bl = ds['mesh2d_flowelem_bl'].values if 'mesh2d_flowelem_bl' in ds else np.full_like(x, np.nan)
        s1 = ds['mesh2d_s1'].values[i1] if 'mesh2d_s1' in ds else np.full_like(x, np.nan)
        u = ds['mesh2d_ucmag'].values[i1] if 'mesh2d_ucmag' in ds else None
        if u is not None and u.ndim == 2:
            u = u[:, -1]                                # surface layer
        elif u is None:
            u = np.full_like(x, np.nan)

        part = int(Path(f).name.split('_')[-2])
        for j in range(len(x)):
            rows.append((part, j, rate[j], n1[j], x[j], y[j], bl[j], s1[j], u[j]))
        span = t[i1] - t[i0]
        ds.close()

    a = np.array(rows)
    rate = a[:, 2]
    tot = rate.sum()
    print(f'window {span:.0f} s, {len(files)} partitions, '
          f'{len(a)} cells, {int(tot)} limiting events in the window')
    if tot <= 0:
        print('no cell limited the timestep in the last window')
        return

    order = np.argsort(-rate)[:args.top]
    print(f'\ntop {args.top} limiting cells:')
    print(f"{'part':>4} {'cell':>7} {'rate':>7} {'share':>7} {'lon':>10} "
          f"{'lat':>9} {'bl':>8} {'s1':>8} {'depth':>7} {'|U|':>6}")
    for i in order:
        p, j, r, _, x, y, bl, s1, u = a[i]
        print(f'{int(p):>4} {int(j):>7} {int(r):>7} {100*r/tot:>6.1f}% '
              f'{x:>10.5f} {y:>9.5f} {bl:>8.2f} {s1:>8.3f} {s1-bl:>7.3f} {u:>6.2f}')

    # One cell or many? The cumulative share of the worst cells says which.
    srt = np.sort(rate)[::-1]
    cum = np.cumsum(srt) / tot
    for k in (1, 5, 20, 100):
        if k <= len(cum):
            print(f'  top {k:>3} cells account for {100*cum[k-1]:.1f}% of the events')
    print(f'  cells with any event: {int((rate > 0).sum())}')


if __name__ == '__main__':
    main()
