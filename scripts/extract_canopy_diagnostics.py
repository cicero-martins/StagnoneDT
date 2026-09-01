"""The three canopy numbers the manuscript quotes but cannot currently re-derive.

Sections 3.6 and 5.6 carry three quantities that were computed from the 3D
fields in an earlier session and never written down anywhere the repository can
reach. The map.nc set is 40 GB and lives on the server, so this runs there and
returns three small CSVs.

  (A) The canopy resistance against the empirical law of Ciraolo, Ferreri and
      La Loggia (2006), evaluated at the model's own depth-averaged speed and
      water depth over the meadow. Section 3.6 states "within 3%".

  (B) Mean bed shear stress over the meadow, for the bare member, the vegetated
      member and the trachytope member. Section 3.6 states that the canopy
      lowers it by an order of magnitude where an equivalent bed roughness
      raises it, so both halves need a number.

  (C) The reconfiguration response, from the controlled pair that differs only
      in Rhoveg. _veg_bend0 holds the canopy rigid and _veg_RHO900 lets it
      bend, everything else identical. Section 5.6 states the velocity ratio
      rises with speed, which is what makes the bending dynamic rather than a
      fixed shortening.

All three are restricted to the lagoon interior and to the window the one-day
probes share, so the members are compared over identical times and cells.

    scp scripts/extract_canopy_diagnostics.py simit:~/StagnoneDT/scripts/
    ssh simit "source ~/miniconda3/etc/profile.d/conda.sh && \
               conda activate stagnone_extract && \
               python ~/StagnoneDT/scripts/extract_canopy_diagnostics.py"
"""
import glob
import sys

import numpy as np
import pandas as pd
import xarray as xr

MODEL = '/home/ciceromartinsjr/StagnoneDT/model/'
OUT = '/home/ciceromartinsjr/'

LON = (12.432, 12.484)
LAT = (37.828, 37.900)
BL_MAX = -0.15
# the window the one-day probes cover, so (C) and the rest are on equal footing
T0, T1 = '2025-07-08', '2025-07-09'

G = 9.81
CD = 0.8            # as configured, Cdveg
# Ciraolo et al. (2006) Eq. 23, S_f = a * U^b / (h * h_v^c)
CIR_A, CIR_B, CIR_C = 3.55e-4, 0.44, 1.56

BARE = 'dflowfm_v04AE_nowaves'
VEG = '_veg_hv040_3d'
TRT = 'dflowfm_v04AE_nowaves_vr_arlfix'    # the meadow as bed roughness
# The bending pair is two runs that BOTH bend and differ only in stiffness.
# _veg_bend0 sets Rhoveg = 0, and that does not mean "rigid canopy", it turns
# the vegetation off: measured against _veg_RHO900 it is 3 to 4 times faster,
# which is the canopy effect and not a reconfiguration effect. Comparing 900
# against 1020 kg/m3 keeps the canopy in both and varies only how far it bends.
BEND_SOFT, BEND_STIFF = '_veg_RHO900', '_veg_RHO1020'


def parts(d):
    f = sorted(glob.glob(MODEL + d + '/DFM_OUTPUT_Stagnone_dxy01_15m/*_0*_map.nc'))
    return [x for x in f if '.bak' not in x]


def interior(ds):
    """Lagoon interior faces, the same mask the other extractors use."""
    fx = ds['mesh2d_face_x'].values
    fy = ds['mesh2d_face_y'].values
    bl = ds['mesh2d_flowelem_bl'].values
    return ((fx >= LON[0]) & (fx <= LON[1]) & (fy >= LAT[0]) &
            (fy <= LAT[1]) & (bl < BL_MAX))


def depth_avg_speed(ds, idx):
    """Depth-averaged speed, preferring the field the solver writes."""
    if 'mesh2d_ucmaga' in ds.variables:
        return ds['mesh2d_ucmaga'].sel(time=slice(T0, T1)).isel(
            mesh2d_nFaces=idx).values
    u = ds['mesh2d_ucxa'].sel(time=slice(T0, T1)).isel(mesh2d_nFaces=idx)
    v = ds['mesh2d_ucya'].sel(time=slice(T0, T1)).isel(mesh2d_nFaces=idx)
    return np.hypot(u.values, v.values)


def part_A():
    """Modelled canopy friction slope against the Ciraolo law."""
    rows = []
    for f in parts(VEG):
        ds = xr.open_dataset(f)
        m = interior(ds)
        idx = np.where(m)[0]
        if idx.size == 0:
            ds.close()
            continue
        hv = ds['mesh2d_stemheight'].isel(mesh2d_nFaces=idx).values
        rn = ds['mesh2d_rnveg'].isel(mesh2d_nFaces=idx).values
        dia = ds['mesh2d_diaveg'].isel(mesh2d_nFaces=idx).values
        # stemheight/rnveg/diaveg may or may not carry a time axis
        hv, rn, dia = [a[0] if a.ndim == 2 else a for a in (hv, rn, dia)]
        meadow = (rn > 0) & (hv > 0)
        if meadow.sum() == 0:
            ds.close()
            continue

        U = depth_avg_speed(ds, idx)
        h = ds['mesh2d_waterdepth'].sel(time=slice(T0, T1)).isel(
            mesh2d_nFaces=idx).values
        nt = U.shape[0]
        hv2, rn2, dia2 = (np.tile(a, (nt, 1)) for a in (hv, rn, dia))
        sel = np.tile(meadow, (nt, 1)) & (U > 0.005) & (h > 0.10)

        # canopy drag per unit bed area over rho*g*h, the friction slope the
        # model's own configuration implies
        sf_mod = CD * rn2 * dia2 * hv2 * U ** 2 / (2.0 * G * h)
        sf_cir = CIR_A * U ** CIR_B / (h * hv2 ** CIR_C)

        rows.append(pd.DataFrame({
            'sf_model': sf_mod[sel], 'sf_ciraolo': sf_cir[sel],
            'U': U[sel], 'h': h[sel], 'hv': hv2[sel],
            'hv_over_h': hv2[sel] / h[sel]}))
        ds.close()

    d = pd.concat(rows, ignore_index=True)
    d['ratio'] = d.sf_model / d.sf_ciraolo
    d['ubin'] = pd.cut(d.U, [0, 0.02, 0.05, 0.10, 0.20, 0.30, 10.0],
                       labels=['<2', '2-5', '5-10', '10-20', '20-30', '>30'])
    byu = d.groupby('ubin', observed=True).agg(
        n=('ratio', 'size'), U_mean=('U', 'mean'),
        ratio_median=('ratio', 'median')).reset_index()
    byu.to_csv(OUT + 'canopy_A_ratio_by_speed.csv', index=False)
    sys.stderr.write('A, ratio by speed band (cm/s):\n'
                     + byu.to_string(index=False) + '\n')
    q = d.ratio.quantile([0.25, 0.5, 0.75])
    summary = pd.DataFrame([{
        'n_samples': len(d),
        'ratio_median': q[0.5], 'ratio_q25': q[0.25], 'ratio_q75': q[0.75],
        'ratio_mean': d.ratio.mean(),
        'U_median': d.U.median(), 'h_median': d.h.median(),
        'hv_over_h_median': d.hv_over_h.median(),
        'hv_over_h_q05': d.hv_over_h.quantile(0.05),
        'hv_over_h_q95': d.hv_over_h.quantile(0.95),
        'sf_model_median': d.sf_model.median(),
        'sf_ciraolo_median': d.sf_ciraolo.median()}])
    summary.to_csv(OUT + 'canopy_A_ciraolo_ratio.csv', index=False)
    sys.stderr.write(f'A: median ratio {q[0.5]:.3f} over {len(d)} samples\n')
    return summary


def part_B():
    """Mean bed shear stress over the meadow, three members."""
    # the meadow mask comes from the vegetated member and is then applied to
    # all three, so the same cells are compared
    mask = {}
    for f in parts(VEG):
        ds = xr.open_dataset(f)
        idx = np.where(interior(ds))[0]
        rn = ds['mesh2d_rnveg'].isel(mesh2d_nFaces=idx).values
        rn = rn[0] if rn.ndim == 2 else rn
        mask[f.split('_')[-2]] = (idx, rn > 0)
        ds.close()

    rows = []
    for label, d in (('bare', BARE), ('canopy', VEG), ('trachytope', TRT)):
        tot, n = 0.0, 0
        for f in parts(d):
            key = f.split('_')[-2]
            if key not in mask:
                continue
            idx, meadow = mask[key]
            ds = xr.open_dataset(f)
            if 'mesh2d_taus' not in ds.variables:
                ds.close()
                continue
            t = ds['mesh2d_taus'].sel(time=slice(T0, T1)).isel(
                mesh2d_nFaces=idx).values[:, meadow]
            tot += float(np.nansum(t))
            n += int(np.isfinite(t).sum())
            ds.close()
        rows.append({'member': label, 'dir': d, 'mean_taus_Pa': tot / n,
                     'n_values': n})
        sys.stderr.write(f'B: {label:11s} taus {tot / n:.4f} Pa\n')
    out = pd.DataFrame(rows)
    out.to_csv(OUT + 'canopy_B_bed_stress.csv', index=False)
    return out


def part_C():
    """Reconfiguration, from the pair differing only in Rhoveg."""
    rows = []
    for fa, fb in zip(parts(BEND_SOFT), parts(BEND_STIFF)):
        da, db = xr.open_dataset(fa), xr.open_dataset(fb)
        idx = np.where(interior(da))[0]
        rn = da['mesh2d_rnveg'].isel(mesh2d_nFaces=idx).values
        rn = rn[0] if rn.ndim == 2 else rn
        meadow = rn > 0
        if meadow.sum() == 0:
            da.close(); db.close()
            continue
        ua = depth_avg_speed(da, idx)
        ub = depth_avg_speed(db, idx)
        nt = min(ua.shape[0], ub.shape[0])
        ua, ub = ua[:nt], ub[:nt]
        sel = np.tile(meadow, (nt, 1)) & (ub > 0.005)
        rows.append(pd.DataFrame({'soft': ua[sel], 'stiff': ub[sel]}))
        da.close(); db.close()

    d = pd.concat(rows, ignore_index=True)
    # stiffer leaves bend less, so they resist more and the flow is slower.
    # a ratio that MOVES with speed is the signature of load-dependent
    # bending; a fixed shortening would give a constant.
    d['ratio'] = d.soft / d.stiff
    # quintiles of the STIFF field, so the binning does not use the response
    d['bin'] = pd.qcut(d.stiff, 5, labels=['q1', 'q2', 'q3', 'q4', 'q5'])
    g = d.groupby('bin', observed=True).agg(
        n=('ratio', 'size'), speed_mean=('stiff', 'mean'),
        ratio_mean=('ratio', 'mean'), ratio_median=('ratio', 'median'))
    top = d[d.stiff >= d.stiff.quantile(0.95)]
    g = g.reset_index()
    g = pd.concat([g, pd.DataFrame([{
        'bin': 'top5pct', 'n': len(top), 'speed_mean': top.stiff.mean(),
        'ratio_mean': top.ratio.mean(),
        'ratio_median': top.ratio.median()}])], ignore_index=True)
    g.to_csv(OUT + 'canopy_C_reconfiguration.csv', index=False)
    sys.stderr.write('C:\n' + g.to_string(index=False) + '\n')
    return g


if __name__ == '__main__':
    part_A()
    part_B()
    part_C()
    sys.stderr.write('done\n')
