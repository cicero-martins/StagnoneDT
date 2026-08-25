"""How much of the seagrass map actually receives trachytope roughness?

The .arl designates a set of flow links as vegetated.  This counts how many of
them carry a roughness that differs from the uniform background at a chosen
frame -- i.e. how much of the map the model is really using.

Written to settle a scope question: a 6% application rate was measured in short
FM-only test runs cloned from v04AE_vr, but those differ from the production
runs (single process vs 8 MPI partitions, no morphology, no waves), and the
local v04AE_vr map.nc holds only frame 0, which predates the first trachytope
update and so proves nothing either way.  This runs against the full
partitioned output, where the question can be answered.

    python check_trachytope_coverage.py --model <model dir> [--frame N]
"""
from pathlib import Path
import argparse
import glob
import sys

import numpy as np
import xarray as xr
from scipy.spatial import cKDTree

BACKGROUND = 0.023        # unifFrictCoef in the MDU, Manning
TOL = 1e-4                # a link counts as "background" within this


def read_arl(path):
    """xu yu zu TrachytopeNr Fraction, with '#' comments."""
    pts = []
    for line in Path(path).read_text(errors='ignore').splitlines():
        if line.lstrip().startswith('#'):
            continue
        s = line.split()
        if len(s) < 5:
            continue
        try:
            pts.append((float(s[0]), float(s[1]), int(s[3]), float(s[4])))
        except ValueError:
            continue
    return np.array(pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--arl', default=None, help='defaults to the .arl in the model dir')
    ap.add_argument('--frame', type=int, default=None, help='default: mid-run')
    ap.add_argument('--veg-classes', default='2,3')
    args = ap.parse_args()

    mdir = Path(args.model)
    arl = Path(args.arl) if args.arl else next(iter(sorted(mdir.glob('*.arl'))), None)
    if arl is None:
        sys.exit(f'no .arl in {mdir}')
    # Only the canonical output dir.  Model dirs here also hold .bak_* copies of
    # earlier runs -- including one made with the UTM .arl that assigned no
    # links at all -- and globbing them together silently mixes a broken run
    # into the count.
    outdirs = [d for d in sorted(mdir.glob('DFM_OUTPUT_*'))
               if d.is_dir() and '.bak' not in d.name]
    if len(outdirs) != 1:
        print(f'output dirs considered: {[d.name for d in outdirs]}')
        if not outdirs:
            sys.exit('no non-.bak output dir')
    files = sorted(glob.glob(str(outdirs[0] / '*_0*_map.nc')))
    print(f'reading {outdirs[0].name}')
    if not files:
        sys.exit(f'no partitioned map.nc under {outdirs[0]}')

    veg_classes = {int(c) for c in args.veg_classes.split(',')}
    pts = read_arl(arl)
    veg_pts = np.unique(pts[np.isin(pts[:, 2], list(veg_classes))][:, :2], axis=0)
    print(f'{arl.name}: {len(pts)} lines, '
          f'{len(veg_pts)} distinct vegetated coordinates')

    # Gather edges across partitions, dropping ghost duplicates by coordinate.
    ex, ey, cf = [], [], []
    n_t = None
    for f in files:
        ds = xr.open_dataset(f)
        if 'mesh2d_cftrt' not in ds:
            print(f'  {Path(f).name}: no mesh2d_cftrt'); ds.close(); continue
        n_t = ds.sizes['time']
        frame = args.frame if args.frame is not None else n_t // 2
        ex.append(ds['mesh2d_edge_x'].values)
        ey.append(ds['mesh2d_edge_y'].values)
        cf.append(ds['mesh2d_cftrt'].values[frame])
        ds.close()
    if not ex:
        sys.exit('no cftrt in any partition')

    ex = np.concatenate(ex); ey = np.concatenate(ey); cf = np.concatenate(cf)
    key = np.round(np.c_[ex, ey], 7)
    _, keep = np.unique(key, axis=0, return_index=True)
    ex, ey, cf = ex[keep], ey[keep], cf[keep]
    frame = args.frame if args.frame is not None else n_t // 2
    print(f'{len(files)} partitions, {n_t} frames, reading frame {frame}')
    print(f'edges after de-duplication: {len(ex)}')

    dist, idx = cKDTree(np.c_[ex, ey]).query(veg_pts)
    m = 111000 * np.cos(np.deg2rad(37.87))
    print(f'.arl -> nearest edge: median {np.median(dist)*m:.1f} m, '
          f'p90 {np.percentile(dist, 90)*m:.1f} m')

    ei = np.unique(idx[dist * m < 25])          # only trust close matches
    v = cf[ei]
    ok = np.isfinite(v)
    bg = np.abs(v - BACKGROUND) < TOL
    print()
    print(f'vegetated links matched          : {len(ei)}')
    print(f'  carrying a roughness != background: {int((ok & ~bg).sum())} '
          f'({100*(ok & ~bg).mean():.1f}%)')
    print(f'  sitting at the background {BACKGROUND}  : {int(bg.sum())} '
          f'({100*bg.mean():.1f}%)')
    vals, counts = np.unique(np.round(v[ok], 4), return_counts=True)
    order = np.argsort(-counts)[:8]
    print('  most common values:')
    for i in order:
        print(f'     {vals[i]:.4f} : {counts[i]:6d}')


if __name__ == '__main__':
    main()
