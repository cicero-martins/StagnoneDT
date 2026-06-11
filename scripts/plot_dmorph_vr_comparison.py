"""D-Morph bed level comparison: bl (VR OFF) vs vr (VR ON).

Extracts delta_bl from local bl run if NPZ not present.
Loads vr NPZ transferred from simit server.
Produces 4-panel figure + per-seagrass-class stats.

Output: figures/dmorph_vr_comparison.png
"""
from pathlib import Path
import numpy as np
import xarray as xr
import rasterio
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'

BL_VAR  = 'mesh2d_mor_bl'
NPART   = 8
CLASS_TIF = PROC / 'planet2023_rf_v3' / 'classified_seagrass_aug2023_v3.tif'
RF_TO_TRAC = {0: 1, 1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 7: 4}
TRAC_LABELS = {1: 'sand', 2: 'Cymodocea', 3: 'Posidonia', 4: 'rock'}
TRAC_COLORS = {1: '#f4e04d', 2: '#5ec45e', 3: '#1a7a3e', 4: '#8b4513'}

LAG_LON = (12.40, 12.50)
LAG_LAT = (37.81, 37.93)


def extract_bl_local(run_key, model_dir):
    """Extract delta_bl from local map.nc partitions and save to NPZ."""
    out_f = PROC / f'dmorph_delta_{run_key}.npz'
    if out_f.exists():
        print(f'{run_key}: loading existing {out_f.name}')
        return np.load(out_f)
    print(f'Extracting {run_key} from {model_dir} ...')
    all_x, all_y, all_t0, all_tf = [], [], [], []
    for p in range(NPART):
        mp = model_dir / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not mp.exists():
            break
        ds = xr.open_dataset(mp)
        if BL_VAR not in ds:
            ds.close(); continue
        bl = ds[BL_VAR]
        fx = ds['mesh2d_face_x'].values
        fy = ds['mesh2d_face_y'].values
        t0 = bl.isel(time=0).values
        tf = bl.isel(time=-1).values
        n_t = bl.sizes['time']
        print(f'  p{p}: {n_t} steps  delta [{(tf-t0).min():.3f}, {(tf-t0).max():.3f}] m')
        ds.close()
        all_x.append(fx); all_y.append(fy)
        all_t0.append(t0); all_tf.append(tf)
    face_x   = np.concatenate(all_x)
    face_y   = np.concatenate(all_y)
    bl_t0    = np.concatenate(all_t0)
    bl_final = np.concatenate(all_tf)
    delta_bl = bl_final - bl_t0
    # lagoon filter
    lag = ((face_x >= LAG_LON[0]) & (face_x <= LAG_LON[1]) &
           (face_y >= LAG_LAT[0]) & (face_y <= LAG_LAT[1]))
    np.savez(out_f, face_x=face_x[lag], face_y=face_y[lag],
             bl_t0=bl_t0[lag], bl_final=bl_final[lag], delta_bl=delta_bl[lag])
    print(f'{run_key}: saved {out_f.name}  {lag.sum()} lagoon cells')
    return np.load(out_f)


def sample_seagrass(face_x, face_y):
    t = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
    fx_utm, fy_utm = t.transform(face_x, face_y)
    with rasterio.open(CLASS_TIF) as src:
        coords = list(zip(fx_utm, fy_utm))
        rf_vals = np.array([v[0] for v in src.sample(coords)], dtype=float)
        nodata = src.nodata if src.nodata is not None else -9999
    rf_vals[rf_vals == nodata] = -1
    trac_class = np.zeros(len(face_x), dtype=int)
    for rf_id, tr_id in RF_TO_TRAC.items():
        trac_class[rf_vals == rf_id] = tr_id
    return trac_class


# ---------------------------------------------------------------
# Load bl run (local extraction)
# ---------------------------------------------------------------
BL_MAP_DIR = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
d_bl = extract_bl_local('bl', BL_MAP_DIR)

# ---------------------------------------------------------------
# Load vr run (transferred from server)
# ---------------------------------------------------------------
vr_npz = PROC / 'dmorph_delta_vr.npz'
if not vr_npz.exists():
    print(f'\nERROR: {vr_npz} not found.')
    print('Run scripts/extract_dmorph_comparison_server.py on simit server,')
    print('then scp simit:~/StagnoneDT/data/processed/dmorph_delta_vr.npz data/processed/')
    raise SystemExit(1)
d_vr = np.load(vr_npz)
print(f'vr: loaded {len(d_vr["face_x"])} cells')

# Align by nearest-face match (grids may differ if partitioned differently)
# Both runs use the same mesh, so face coords should match 1:1 after lagoon filter.
# Verify alignment:
max_dist = np.max(np.sqrt((d_bl['face_x'] - d_vr['face_x'])**2 +
                           (d_bl['face_y'] - d_vr['face_y'])**2))
if max_dist > 1e-6:
    print(f'WARNING: max coord mismatch = {max_dist:.2e} deg — rebuilding alignment')
    # Sort both by (x,y) to align
    idx_bl = np.lexsort((d_bl['face_y'], d_bl['face_x']))
    idx_vr = np.lexsort((d_vr['face_y'], d_vr['face_x']))
    face_x   = d_bl['face_x'][idx_bl]
    face_y   = d_bl['face_y'][idx_bl]
    delta_bl_bl = d_bl['delta_bl'][idx_bl]
    delta_bl_vr = d_vr['delta_bl'][idx_vr]
else:
    face_x      = d_bl['face_x']
    face_y      = d_bl['face_y']
    delta_bl_bl = d_bl['delta_bl']
    delta_bl_vr = d_vr['delta_bl']

diff_dmorph = delta_bl_vr - delta_bl_bl  # VR effect on morphology

# ---------------------------------------------------------------
# Sample seagrass class
# ---------------------------------------------------------------
print('Sampling seagrass...')
trac_class = sample_seagrass(face_x, face_y)

# ---------------------------------------------------------------
# Per-class stats
# ---------------------------------------------------------------
print('\nD-Morph delta_bl by class (9-day cumulative, Jul 1-10):')
print(f"{'class':<12} {'n':>5}  {'bl_mean':>9} {'bl_p50':>9} | {'vr_mean':>9} {'vr_p50':>9} | {'diff_mean':>10} {'diff_p50':>10}")
for tc, lbl in TRAC_LABELS.items():
    mask = trac_class == tc
    if mask.sum() < 5:
        continue
    bl_v = delta_bl_bl[mask]; vr_v = delta_bl_vr[mask]; d_v = diff_dmorph[mask]
    print(f"  {lbl:<10} {mask.sum():>5}  "
          f"{bl_v.mean():>+9.4f} {np.median(bl_v):>+9.4f} | "
          f"{vr_v.mean():>+9.4f} {np.median(vr_v):>+9.4f} | "
          f"{d_v.mean():>+10.4f} {np.median(d_v):>+10.4f}")

# ---------------------------------------------------------------
# Figure
# ---------------------------------------------------------------
# Symmetric color scale capped at 95th pct of absolute values
vmax = np.percentile(np.abs(np.concatenate([delta_bl_bl, delta_bl_vr])), 95)
vmax_diff = np.percentile(np.abs(diff_dmorph), 95)

fig, axes = plt.subplots(1, 4, figsize=(20, 7))

sc0 = axes[0].scatter(face_x, face_y, c=delta_bl_bl, cmap='RdBu_r',
                      s=1.5, vmin=-vmax, vmax=vmax, linewidths=0, rasterized=True)
plt.colorbar(sc0, ax=axes[0], label='delta bl (m)', fraction=0.035, pad=0.02)
axes[0].set_title('A.  bl  D-Morph ON, VR OFF', fontsize=9, fontweight='bold')

sc1 = axes[1].scatter(face_x, face_y, c=delta_bl_vr, cmap='RdBu_r',
                      s=1.5, vmin=-vmax, vmax=vmax, linewidths=0, rasterized=True)
plt.colorbar(sc1, ax=axes[1], label='delta bl (m)', fraction=0.035, pad=0.02)
axes[1].set_title('B.  vr  D-Morph ON, VR ON', fontsize=9, fontweight='bold')

sc2 = axes[2].scatter(face_x, face_y, c=diff_dmorph, cmap='RdBu_r',
                      s=1.5, vmin=-vmax_diff, vmax=vmax_diff, linewidths=0, rasterized=True)
plt.colorbar(sc2, ax=axes[2], label='vr - bl (m)', fraction=0.035, pad=0.02)
axes[2].set_title('C.  Diff (vr - bl): VR effect on D-Morph', fontsize=9, fontweight='bold')
n_more_dep = (diff_dmorph < -0.001).sum()
n_less_dep = (diff_dmorph > 0.001).sum()
axes[2].text(0.02, 0.98,
             f'more deposition (blue): {n_more_dep} cells\n'
             f'more erosion (red): {n_less_dep} cells',
             transform=axes[2].transAxes, fontsize=7.5, va='top',
             bbox=dict(fc='white', alpha=0.8, pad=2))

# Panel D: seagrass + diff overlay
for tc in [1, 2, 3, 4]:
    mask = trac_class == tc
    if mask.sum() == 0:
        continue
    axes[3].scatter(face_x[mask], face_y[mask],
                    c=diff_dmorph[mask], cmap='RdBu_r', s=2.5,
                    vmin=-vmax_diff, vmax=vmax_diff, linewidths=0, rasterized=True)
axes[3].set_title('D.  VR D-Morph effect by seagrass class', fontsize=9, fontweight='bold')
# class legend
handles = [mpatches.Patch(color=TRAC_COLORS[tc], label=TRAC_LABELS[tc])
           for tc in [1, 2, 3, 4] if (trac_class == tc).sum() > 0]
axes[3].legend(handles=handles, fontsize=6.5, loc='lower right', framealpha=0.85)

for ax in axes:
    ax.set_xlabel('Longitude', fontsize=8)
    ax.set_aspect('equal')
axes[0].set_ylabel('Latitude', fontsize=8)

fig.suptitle(
    'D-Morph cumulative bed level change — 9 days (Jul 1-10 2025)\n'
    'Blue = deposition, Red = erosion  |  Baptist VR effect on morphological evolution',
    fontsize=10
)
fig.tight_layout()
out = FIG / 'dmorph_vr_comparison.png'
fig.savefig(out, dpi=160, bbox_inches='tight')
plt.close(fig)
print(f'\nFig -> {out}')
print('Done.')
