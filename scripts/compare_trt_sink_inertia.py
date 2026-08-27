"""Does D-Flow FM consume the Baptist 154 momentum sink?

Formula 154 splits vegetation resistance in two: a bed Chezy that stays the
bed's, and a canopy drag carried as a separate momentum sink, rttfu, in
trtrou.f90:

    hk   = max(1, depth/vheigh)
    ch   = cbed + sqrt(g)/kappa*log(hk)*sqrt(1 + C_D*mD*h_v*cbed^2/(2g))
    rttfu(nm,1) += fraccu * C_D*mD/hk * (cbed/ch)^2

trtrou.f90 writes rttfu into gdtrachy%dir(jdir)%rttfu. Whether the FM solver
then reads it is not visible in the trachytope sources, and it matters: the
measured lagoon is 21% FASTER under 154 than under uniform roughness, which is
what a meadow with no canopy drag and a very smooth representative Chezy would
give. With the current parameters ch reaches 121 at 1 m depth against a bare-bed
45, so if the sink is inert the meadow is modelled as smoother than sand.

The test isolates the sink exactly, using the one regime where the two terms
decouple. When depth <= vheigh, hk clamps to 1, log(1) = 0, and

    ch   = cbed            independent of C_D, mD and depth
    sink = C_D * mD        and nothing else

Setting vheigh = 40 m clamps every vegetated link (the deepest is 31.6 m). The
two runs then carry a byte-identical roughness field and differ only in C_D,
0.00 against 0.80, so the sink is 0.0 against 4.0 1/m.

  identical fields  -> FM ignores rttfu; 154 is its bed Chezy alone, and the
                       Ciraolo-anchored reparametrisation is pointless until
                       this is resolved
  fields differ     -> the sink is live, and the difference measures it

Everything else is held: same restart, same partitions, same .arl, same
maxVelocity, 24 h from 8 July.

The same comparison serves the second question this raised, whether FM's own
[veg] module is live where the trachytope sink is not, so the wording of the
verdict is deliberately generic: it reports on whichever term the pair of runs
isolates. Read the frame-count warning before reading anything else. A run
still in flight is indistinguishable from a short one, and comparing a finished
run against a running one produces confident nonsense.

    python scripts/compare_trt_sink_inertia.py --a <dirA> --b <dirB>
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import xarray as xr

STATIONS = ('BocaNord', 'BocaSud', 'AltaVilaEst')
LAGOON = (12.41, 12.50, 37.84, 37.92)


def his(d):
    f = glob.glob(f'{d}/DFM_OUTPUT_*/*_0000_his.nc')
    if not f:
        return None
    ds = xr.open_dataset(f[0])
    names = [b.tobytes().decode('utf-8', 'ignore').strip() if isinstance(b, bytes)
             else str(b).strip() for b in ds['station_name'].values]
    out = {}
    for s in STATIONS:
        hit = [i for i, n in enumerate(names) if n.replace(' ', '') == s]
        if hit:
            out[s] = ds['waterlevel'].values[:, hit[0]]
    ds.close()
    return out


def maps(d):
    """Surface speed and water level per partition, plus lagoon coordinates."""
    sp, wl, xs, ys = [], [], [], []
    for f in sorted(glob.glob(f'{d}/DFM_OUTPUT_*/*_00??_map.nc')):
        ds = xr.open_dataset(f, decode_times=False)
        ux, uy = ds['mesh2d_ucx'], ds['mesh2d_ucy']
        if 'mesh2d_nLayers' in ux.dims or 'laydim' in ux.dims:
            ux, uy = ux.isel({ux.dims[-1]: -1}), uy.isel({uy.dims[-1]: -1})
        sp.append(np.hypot(ux.values, uy.values))
        wl.append(ds['mesh2d_s1'].values)
        xs.append(ds['mesh2d_face_x'].values)
        ys.append(ds['mesh2d_face_y'].values)
        ds.close()
    n = min(s.shape[0] for s in sp)
    return (np.concatenate([s[:n] for s in sp], axis=1),
            np.concatenate([w[:n] for w in wl], axis=1),
            np.concatenate(xs), np.concatenate(ys))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True, help='canopy drag OFF')
    ap.add_argument('--b', required=True, help='canopy drag ON')
    a = ap.parse_args()

    ha, hb = his(a.a), his(a.b)
    print('=== water level at the gauges ===')
    if ha and hb:
        for s in STATIONS:
            if s in ha and s in hb:
                n = min(len(ha[s]), len(hb[s]))
                d = hb[s][:n] - ha[s][:n]
                print(f'  {s:13s} n={n:4d}  mean |diff| {np.nanmean(np.abs(d))*1000:9.4f} mm   '
                      f'max |diff| {np.nanmax(np.abs(d))*1000:9.4f} mm   '
                      f'identical: {np.array_equal(ha[s][:n], hb[s][:n])}')
    else:
        print('  (no his.nc)')

    sa, wa, x, y = maps(a.a)
    sb, wb, _, _ = maps(a.b)
    na, nb = sa.shape[0], sb.shape[0]
    n = min(na, nb)
    sa, sb, wa, wb = sa[:n], sb[:n], wa[:n], wb[:n]
    lag = ((x > LAGOON[0]) & (x < LAGOON[1]) &
           (y > LAGOON[2]) & (y < LAGOON[3]))
    print(f'\n=== fields: {n} frames, {sa.shape[1]} cells, '
          f'{int(lag.sum())} in the lagoon ===')

    for label, m in (('whole domain', np.ones_like(lag, bool)), ('lagoon', lag)):
        A, B = sa[:, m], sb[:, m]
        ok = np.isfinite(A) & np.isfinite(B)
        d = np.abs(B - A)[ok]
        print(f'  speed  {label:12s} A {A[ok].mean():.5f}  B {B[ok].mean():.5f}  '
              f'B/A {B[ok].mean()/A[ok].mean():.4f}   '
              f'mean|dif| {d.mean():.3e}  max {d.max():.3e} m/s')
        WA, WB = wa[:, m], wb[:, m]
        ok = np.isfinite(WA) & np.isfinite(WB)
        d = np.abs(WB - WA)[ok]
        print(f'  WL     {label:12s} mean|dif| {d.mean()*1000:.4f} mm  '
              f'max {d.max()*1000:.4f} mm')

    same = np.array_equal(np.nan_to_num(sa), np.nan_to_num(sb))
    print(f'\nbit-identical speed field: {same}')
    print('VERDICT: the term under test is INERT -- it never reaches the solver'
          if same else
          'VERDICT: the term under test is LIVE -- it acts on the flow')
    # A verdict on truncated output is worthless, and a run still in flight
    # looks exactly like a short one. Two runs of the same window must carry
    # the same frame count.
    if na != nb:
        print(f'!! frame counts differ: {na} against {nb}. One run is either '
              f'still going or stopped early -- do not read the numbers above.')


if __name__ == '__main__':
    main()
