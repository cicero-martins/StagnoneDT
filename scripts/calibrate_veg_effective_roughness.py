"""What Manning roughness does the [veg] canopy drag amount to, and what does
Ciraolo say it should be?

The three literature anchors for this lagoon are in different units and do not
measure the same thing, so none of them can be a target on its own:

  Ciraolo, Ferreri & La Loggia 2006   local resistance of a dense P. oceanica
                                      meadow, UNIPA flume, this species
  Ingrassia et al. 2024               bulk Manning for the WHOLE lagoon, MIKE21
  De Marchis et al. 2012              BED roughness under the canopy, PANORMUS

Ciraolo is the only one measuring the quantity the vegetation module produces,
so it is the target; the other two are sanity bounds. Converted through
lambda = 52e6 Re_v^-1.56 and C = sqrt(8g/lambda), Ciraolo gives an effective
Manning that runs from 0.40 at 2 cm/s to 0.048 at 30 cm/s -- steeply
velocity-dependent, and at 0.10 m/s it is 0.114, which is ROUGHER than the
0.050 bulk value that made the module look over-damped at first reading.

Their flume covers Re_v from 3.5e4 to 1e6, so with a 1 m leaf that is U from
0.04 to 1.14 m/s. Below that the power law is extrapolation, not measurement,
and the lagoon spends a lot of time there. Everything here is restricted to the
measured range and the excluded fraction is reported rather than hidden.

The model's own effective roughness cannot be read off a parameter, because the
canopy drag is a separate momentum term rather than a roughness. So it is
measured with the model as its own instrument: a ladder of runs with vegetation
OFF and the meadow given a fixed Manning through trachytope formula 53, which
is plain Manning and never touches the momentum sink this build discards. The
ladder maps Manning to meadow speed; any vegetation run is then read off that
curve.

Comparison speed is the depth-averaged one, not the surface. The surface is the
least damped layer of the column -- vegetated lagoon cells run at 0.26 of the
control there against 0.088 at the bed -- so reading resistance off the surface
would understate it.

    python scripts/calibrate_veg_effective_roughness.py --ladder <dir>=<n> ... \
        --veg <dir>=<label> ... --control <dir>
"""
import argparse
import glob

import numpy as np
import xarray as xr

G = 9.81
NU = 1.14e-6
LAGOON = (12.41, 12.50, 37.84, 37.92)
# Ciraolo Table 1 / Fig. 4: reliable runs sit above Re_v ~ 3.5e4.
RE_V_MIN = 3.5e4


def load(d):
    """Depth-averaged speed, depth, and the vegetation map, over all ranks."""
    S, H, X, Y, V = [], [], [], [], []
    for f in sorted(glob.glob(d + '/DFM_OUTPUT_*/*_00??_map.nc')):
        ds = xr.open_dataset(f, decode_times=False)
        sp = np.hypot(ds['mesh2d_ucx'].values, ds['mesh2d_ucy'].values)
        # sigma layers of equal thickness, so the layer mean IS the depth mean
        S.append(sp.mean(axis=2) if sp.ndim == 3 else sp)
        H.append(ds['mesh2d_waterdepth'].values)
        X.append(ds['mesh2d_face_x'].values)
        Y.append(ds['mesh2d_face_y'].values)
        V.append(ds['mesh2d_stemheight'].values[-1] if 'mesh2d_stemheight' in ds
                 else np.zeros(len(ds['mesh2d_face_x'])))
        ds.close()
    n = min(s.shape[0] for s in S)
    return dict(s=np.concatenate([s[:n] for s in S], 1),
                h=np.concatenate([h[:n] for h in H], 1),
                x=np.concatenate(X), y=np.concatenate(Y), v=np.concatenate(V),
                n=n)


def ciraolo_n(U, h, hv):
    """Effective Manning implied by Ciraolo Eq. 22, elementwise."""
    with np.errstate(divide='ignore', invalid='ignore'):
        lam = 52e6 * (U * hv / NU) ** -1.56
        return h ** (1 / 6) / np.sqrt(8 * G / lam)


def meadow_speed(r, mask):
    v = r['s'][:, mask]
    return float(np.nanmean(v))


def meadow_cftrt(d, arl, tol=0.001):
    """The Manning actually applied on vegetated links, not the .ttd value.

    The .arl carries an area fraction per link and it is far from 1: the median
    Posidonia link is 0.685 covered and the median Cymodocea link 0.181. FM
    blends the class value with the background over that fraction, so a ladder
    rung labelled 0.12 does not put 0.12 on the bed. mesh2d_cftrt is what
    landed, and it lives on links (51836) rather than faces.
    """
    from scipy.spatial import cKDTree
    V, X, Y = [], [], []
    for f in sorted(glob.glob(d + '/DFM_OUTPUT_*/*_00??_map.nc')):
        ds = xr.open_dataset(f, decode_times=False)
        if 'mesh2d_cftrt' not in ds:
            ds.close()
            return None
        v = ds['mesh2d_cftrt'].values
        V.append(v[-1] if v.ndim > 1 else v)
        X.append(ds['mesh2d_edge_x'].values)
        Y.append(ds['mesh2d_edge_y'].values)
        ds.close()
    v, x, y = np.concatenate(V), np.concatenate(X), np.concatenate(Y)
    dist, _ = cKDTree(arl).query(np.c_[x, y])
    m = ((dist < tol) & (x > LAGOON[0]) & (x < LAGOON[1]) &
         (y > LAGOON[2]) & (y < LAGOON[3]) & np.isfinite(v) & (v > 0))
    return float(np.median(v[m])), int(m.sum())


def read_arl_points(path, classes=(2, 3)):
    pts = []
    for line in open(path, errors='ignore'):
        if line.lstrip().startswith('#'):
            continue
        s = line.split()
        if len(s) >= 5 and int(s[3]) in classes:
            pts.append((float(s[0]), float(s[1])))
    return np.array(pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--control', required=True, help='no vegetation, bare bed')
    ap.add_argument('--ladder', nargs='+', required=True, metavar='DIR=N')
    ap.add_argument('--veg', nargs='+', default=[], metavar='DIR=LABEL')
    ap.add_argument('--bare-n', type=float, default=0.023)
    ap.add_argument('--arl', help='to place the ladder rungs at their MEASURED '
                                  'Manning rather than their nominal one')
    a = ap.parse_args()

    ctrl = load(a.control)
    x, y, veg = ctrl['x'], ctrl['y'], ctrl['v']
    # The vegetation map comes from a run that has one; fall back to any --veg.
    if not veg.any() and a.veg:
        veg = load(a.veg[0].split('=')[0])['v']
    lag = ((x > LAGOON[0]) & (x < LAGOON[1]) &
           (y > LAGOON[2]) & (y < LAGOON[3]))
    m = lag & (veg > 0)
    print(f'{int(m.sum())} vegetated lagoon cells, depth-averaged speed\n')

    arl = read_arl_points(a.arl) if a.arl else None
    pts = [(a.bare_n, meadow_speed(ctrl, m), 'control', a.bare_n, 0)]
    for spec in a.ladder:
        d, nom = spec.rsplit('=', 1)
        meas = meadow_cftrt(d, arl) if arl is not None else None
        n = meas[0] if meas else float(nom)
        pts.append((n, meadow_speed(load(d), m), d.split('/')[-1],
                    float(nom), meas[1] if meas else 0))
    pts.sort()
    print(f"{'n used':>8} {'nominal':>8} {'links':>7} {'|U| m/s':>9}   run")
    for n, s, lab, nom, nl in pts:
        print(f'{n:8.4f} {nom:8.3f} {nl:7d} {s:9.5f}   {lab}')
    if arl is not None:
        print('  "n used" is the median mesh2d_cftrt actually applied on '
              'vegetated lagoon links; it falls short of nominal because the '
              '.arl area fraction blends it with the 0.023 background.')

    ns = np.array([p[0] for p in pts])
    us = np.array([p[1] for p in pts])
    if not np.all(np.diff(us) < 0):
        print('\n!! meadow speed is not monotone in Manning -- the ladder cannot '
              'be inverted; widen or re-check it before reading anything below.')
        return

    print()
    for spec in a.veg:
        d, lab = spec.rsplit('=', 1)
        r = load(d)
        u = meadow_speed(r, m)
        # invert the ladder in log space: speed falls roughly as a power of n
        neff = float(np.exp(np.interp(np.log(u), np.log(us[::-1]),
                                      np.log(ns[::-1]))))
        inside = us.min() <= u <= us.max()
        if not inside:
            # np.interp CLAMPS, so an off-ladder run silently reports the
            # endpoint. Reporting a ratio against that endpoint produced a
            # confident "within a factor 1.25, acceptable" for two runs that
            # were nowhere near it. Say what is known and stop.
            side = 'slower than' if u < us.min() else 'faster than'
            print(f'{lab}: meadow |U| {u:.5f} m/s -- {side} every rung '
                  f'({us.min():.5f} to {us.max():.5f}). NO effective Manning '
                  f'can be read: the ladder saturates, and canopy drag spread '
                  f'through the column is not equivalent to a bed roughness.')
            print(f'   Against the Ciraolo-equivalent rung {ns[np.argmin(np.abs(ns-0.106))]:.4f} '
                  f'({us[np.argmin(np.abs(ns-0.106))]:.5f} m/s): '
                  f'{us[np.argmin(np.abs(ns-0.106))]/u:.2f}x too slow.')
            continue
        print(f'{lab}: meadow |U| {u:.5f} m/s  ->  effective Manning {neff:.4f}')

        uu, hh = r['s'][:, m], r['h'][:, m]
        hv = np.broadcast_to(r['v'][m], uu.shape)
        ok = np.isfinite(uu) & np.isfinite(hh) & (hh > 0.05) & (hv > 0)
        inrange = ok & (uu * hv / NU >= RE_V_MIN)
        cn = ciraolo_n(uu[inrange], hh[inrange], hv[inrange])
        print(f'   Ciraolo at the model\'s own U and h, Re_v >= {RE_V_MIN:.0e}: '
              f'median {np.nanmedian(cn):.4f}  '
              f'[p25 {np.nanpercentile(cn, 25):.4f}, '
              f'p75 {np.nanpercentile(cn, 75):.4f}]')
        print(f'   {100*inrange.sum()/ok.sum():.1f}% of cell-times are inside the '
              f'flume\'s measured range; the rest run slower than 4 cm/s and are '
              f'unconstrained')
        r_ = neff / np.nanmedian(cn)
        print(f'   model / Ciraolo = {r_:.2f}  ->  '
              + ('lower C_D' if r_ > 1.25 else
                 'raise C_D' if r_ < 0.8 else 'within a factor 1.25, acceptable'))


if __name__ == '__main__':
    main()
