"""Two lagoon diagnostics that need the full map.nc set, so they run on the server.

(1) Mean current speed of the cells assigned to each trachytope class.
    Class comes from the .arl the model actually used, taking the dominant
    class at the nearest roughness link to each face centroid. Surface and bed
    layers are reported separately, because canopy drag acts at the bed while
    drifters ride the surface, and a single depth-averaged number would hide
    whichever of the two responds.

(2) Wave orbital velocity at the bed over the same cells, which is the quantity
    that decides whether waves can mobilise sediment and the one that sets the
    wave contribution to bed stress. Reported as a distribution over time as
    well as a mean, because the window contains one swell event and a mean over
    nine days flattens it.

Emits CSV to stdout. Run:
    source ~/miniconda3/etc/profile.d/conda.sh && conda activate stagnone_extract
    python ~/StagnoneDT/scripts/extract_class_speed_and_uorb.py
"""
import glob
import sys

import numpy as np
import xarray as xr
from scipy.spatial import cKDTree

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ensemble import KEYS, MODELDIR

ROOT = '/home/ciceromartinsjr/StagnoneDT/'
MODEL = ROOT + 'model/'
# the nine-decimal .arl. Class assignment matches on a 200 m KD-tree
# tolerance so the precision fix does not change it, but there is no
# reason to keep reading the file the model could not match.
ARL = MODEL + 'dflowfm_v04AE_nowaves_vr_arlfix/stagnone_trachytopes_v3.arl'

MEMBERS = [(k, MODELDIR[k]) for k in KEYS]
LON = (12.432, 12.484)
LAT = (37.828, 37.900)
BL_MAX = -0.15
T0, T1 = '2025-07-07', '2025-07-10'
CLASS_NAME = {1: 'sand', 2: 'Cymodocea', 3: 'Posidonia', 4: 'rock'}


def load_arl():
    """Dominant trachytope class per roughness link."""
    xs, ys, cls, frac = [], [], [], []
    with open(ARL) as f:
        for ln in f:
            if ln.startswith('#') or not ln.strip():
                continue
            p = ln.split()
            if len(p) != 5:
                continue
            xs.append(float(p[0]))
            ys.append(float(p[1]))
            cls.append(int(p[3]))
            frac.append(float(p[4]))
    xs, ys = np.array(xs), np.array(ys)
    cls, frac = np.array(cls), np.array(frac)
    # one dominant class per unique coordinate
    key = np.round(xs, 6).astype(str) + '_' + np.round(ys, 6).astype(str)
    order = np.argsort(-frac)
    seen, keep = set(), []
    for i in order:
        if key[i] not in seen:
            seen.add(key[i])
            keep.append(i)
    keep = np.array(keep)
    return xs[keep], ys[keep], cls[keep]


def main():
    ax, ay, ac = load_arl()
    tree = cKDTree(np.column_stack([ax, ay]))
    sys.stderr.write(f'arl: {len(ac)} unique links\n')

    print('member,metric,klass,value,n_faces')
    for key, d in MEMBERS:
        files = [f for f in sorted(glob.glob(
            MODEL + d + '/DFM_OUTPUT_Stagnone_dxy01_15m/*_0*_map.nc'))
            if '.bak' not in f]
        acc = {}
        for f in files:
            ds = xr.open_dataset(f)
            fx = ds['mesh2d_face_x'].values
            fy = ds['mesh2d_face_y'].values
            bl = ds['mesh2d_flowelem_bl'].values
            m = ((fx >= LON[0]) & (fx <= LON[1]) & (fy >= LAT[0]) &
                 (fy <= LAT[1]) & (bl < BL_MAX))
            idx = np.where(m)[0]
            if idx.size == 0:
                ds.close()
                continue
            dist, near = tree.query(np.column_stack([fx[idx], fy[idx]]))
            klass = np.where(dist < 0.002, ac[near], 0)   # ~200 m tolerance

            u = ds['mesh2d_ucx'].sel(time=slice(T0, T1)).isel(mesh2d_nFaces=idx)
            v = ds['mesh2d_ucy'].sel(time=slice(T0, T1)).isel(mesh2d_nFaces=idx)
            surf = np.hypot(u.isel(mesh2d_nLayers=-1), v.isel(mesh2d_nLayers=-1))
            bed = np.hypot(u.isel(mesh2d_nLayers=0), v.isel(mesh2d_nLayers=0))
            surf = surf.mean(dim='time').values
            bed = bed.mean(dim='time').values

            uorb = None
            if 'mesh2d_uorb' in ds.variables:
                uorb = ds['mesh2d_uorb'].sel(time=slice(T0, T1)).isel(
                    mesh2d_nFaces=idx)
                uorb_mean = uorb.mean(dim='time').values
                uorb_p95 = uorb.quantile(0.95, dim='time').values

            for c in (1, 2, 3, 4):
                sel = klass == c
                if sel.sum() == 0:
                    continue
                a = acc.setdefault(c, {'surf': 0.0, 'bed': 0.0, 'uorb': 0.0,
                                       'uorb95': 0.0, 'n': 0})
                a['surf'] += float(np.nansum(surf[sel]))
                a['bed'] += float(np.nansum(bed[sel]))
                if uorb is not None:
                    a['uorb'] += float(np.nansum(uorb_mean[sel]))
                    a['uorb95'] += float(np.nansum(uorb_p95[sel]))
                a['n'] += int(sel.sum())
            ds.close()

        for c, a in sorted(acc.items()):
            n = a['n']
            print(f'{key},surface_speed,{CLASS_NAME[c]},{a["surf"] / n:.6f},{n}')
            print(f'{key},bed_speed,{CLASS_NAME[c]},{a["bed"] / n:.6f},{n}')
            if a['uorb'] > 0:
                print(f'{key},uorb_mean,{CLASS_NAME[c]},{a["uorb"] / n:.6f},{n}')
                print(f'{key},uorb_p95,{CLASS_NAME[c]},{a["uorb95"] / n:.6f},{n}')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
