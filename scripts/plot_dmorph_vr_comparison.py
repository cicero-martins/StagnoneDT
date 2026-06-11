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
# Load both NPZs from server extraction (27901 cells, same mesh, no filter)
# Prefer server versions so bl and vr are guaranteed aligned.
# Fallback to local bl extraction if server version not present.
# ---------------------------------------------------------------
bl_server = PROC / 'dmorph_delta_bl_server.npz'
bl_local  = PROC / 'dmorph_delta_bl.npz'
vr_npz    = PROC / 'dmorph_delta_vr.npz'

for f in [vr_npz]:
    if not f.exists():
        print(f'\nERROR: {f.name} not found.')
        print('Run scripts/extract_dmorph_comparison_server.py on simit server,')
        print('then scp the NPZ to data/processed/')
        raise SystemExit(1)

d_vr = np.load(vr_npz)
d_bl = np.load(bl_server if bl_server.exists() else bl_local)
print(f'bl: {len(d_bl["face_x"])} cells  vr: {len(d_vr["face_x"])} cells')

# Apply lagoon filter and align — both NPZs from same mesh so coords match 1:1
# Sort by (x,y) to guarantee alignment regardless of partition order
idx_bl = np.lexsort((d_bl['face_y'], d_bl['face_x']))
idx_vr = np.lexsort((d_vr['face_y'], d_vr['face_x']))
fx_all  = d_bl['face_x'][idx_bl]
fy_all  = d_bl['face_y'][idx_bl]
dbl_all = d_bl['delta_bl'][idx_bl]
dvr_all = d_vr['delta_bl'][idx_vr]

# Lagoon filter
lag = ((fx_all >= LAG_LON[0]) & (fx_all <= LAG_LON[1]) &
       (fy_all >= LAG_LAT[0]) & (fy_all <= LAG_LAT[1]))
face_x      = fx_all[lag]
face_y      = fy_all[lag]
delta_bl_bl = dbl_all[lag]
delta_bl_vr = dvr_all[lag]

# Flag blowup cells (delta > 5m in vr — unphysical with TcrEro=0.1)
blowup_mask = np.abs(delta_bl_vr) > 5.0
print(f'Blowup cells (|delta|>5m): {blowup_mask.sum()}')
if blowup_mask.sum() > 0:
    print(f'  coords: {list(zip(face_x[blowup_mask].round(4), face_y[blowup_mask].round(4)))}')
    print(f'  delta_bl_vr: {delta_bl_vr[blowup_mask]}  delta_bl_bl: {delta_bl_bl[blowup_mask]}')

diff_dmorph = delta_bl_vr - delta_bl_bl  # VR effect on morphology

# Capped arrays for visualisation (blowup cell plotted separately)
delta_bl_vr_capped = np.where(blowup_mask, np.nan, delta_bl_vr)
diff_dmorph_capped = np.where(blowup_mask, np.nan, diff_dmorph)

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
# Robust color scale: use 98th pct of absolute values, excluding blowup
vmax = float(np.nanpercentile(np.abs(np.concatenate([delta_bl_bl,
                                                      delta_bl_vr_capped[~np.isnan(delta_bl_vr_capped)]])), 98))
vmax_diff = float(np.nanpercentile(np.abs(diff_dmorph_capped[~np.isnan(diff_dmorph_capped)]), 98))

fig, axes = plt.subplots(1, 4, figsize=(20, 7))

def _add_blowup_marker(ax, show_legend=True):
    if blowup_mask.sum() > 0:
        ax.scatter(face_x[blowup_mask], face_y[blowup_mask],
                   c='magenta', s=80, marker='*', zorder=10,
                   label=f'blowup VR={delta_bl_vr[blowup_mask][0]:.0f} m\n'
                         f'(bl={delta_bl_bl[blowup_mask][0]:.2f} m)')
        if show_legend:
            ax.legend(fontsize=7.5, loc='lower right',
                      framealpha=0.9, edgecolor='grey')

# ------ Panel A: bl baseline D-Morph ------
sc0 = axes[0].scatter(face_x, face_y, c=delta_bl_bl, cmap='RdBu_r',
                      s=1.5, vmin=-vmax, vmax=vmax, linewidths=0, rasterized=True)
plt.colorbar(sc0, ax=axes[0], label='delta bl (m)', fraction=0.035, pad=0.02)
axes[0].set_title('A.  bl  D-Morph ON, VR OFF', fontsize=9, fontweight='bold')
axes[0].text(0.02, 0.98, f'max erosion: {delta_bl_bl.min():.2f} m\n'
                          f'max deposition: {delta_bl_bl.max():.2f} m',
             transform=axes[0].transAxes, fontsize=7.5, va='top',
             bbox=dict(fc='white', alpha=0.8, pad=2))

# ------ Panel B: VR effect on D-Morph (tight scale ±vmax_diff) ------
# Replace near-duplicate vr map with the diff at its own scale —
# the absolute vr pattern is identical to bl at the ±0.7m scale.
sc1 = axes[1].scatter(face_x, face_y, c=diff_dmorph_capped, cmap='RdBu_r',
                      s=1.5, vmin=-vmax_diff, vmax=vmax_diff, linewidths=0, rasterized=True)
plt.colorbar(sc1, ax=axes[1], label='vr - bl (m)', fraction=0.035, pad=0.02)
axes[1].set_title('B.  Diff (vr - bl): VR effect on D-Morph', fontsize=9, fontweight='bold')
valid_diff = diff_dmorph_capped[~np.isnan(diff_dmorph_capped)]
n_more_dep = (valid_diff < -0.001).sum()
n_more_ero = (valid_diff >  0.001).sum()
axes[1].text(0.02, 0.98,
             f'more deposition (blue): {n_more_dep}\n'
             f'more erosion   (red):   {n_more_ero}',
             transform=axes[1].transAxes, fontsize=7.5, va='top',
             bbox=dict(fc='white', alpha=0.8, pad=2))
_add_blowup_marker(axes[1])

# ------ Panel C: per-class bar chart bl vs vr delta_bl (mean ± std) ------
ax = axes[2]
class_labels, bl_means, bl_stds, vr_means, vr_stds, diff_means = [], [], [], [], [], []
for tc in [1, 2, 3, 4]:
    mask = trac_class == tc
    if mask.sum() < 5:
        continue
    class_labels.append(TRAC_LABELS[tc])
    bl_means.append(delta_bl_bl[mask].mean())
    bl_stds.append(delta_bl_bl[mask].std())
    vr_means.append(delta_bl_vr_capped[mask][~np.isnan(delta_bl_vr_capped[mask])].mean())
    vr_stds.append(delta_bl_vr_capped[mask][~np.isnan(delta_bl_vr_capped[mask])].std())
    diff_means.append(diff_dmorph[mask].mean())

x = np.arange(len(class_labels))
w = 0.35
bars_bl = ax.barh(x + w/2, bl_means, w, xerr=bl_stds, error_kw=dict(lw=0.8, capsize=3),
                  color='#2563eb', alpha=0.8, label='bl (VR OFF)')
bars_vr = ax.barh(x - w/2, vr_means, w, xerr=vr_stds, error_kw=dict(lw=0.8, capsize=3),
                  color='#dc2626', alpha=0.8, label='vr (VR ON)')
ax.axvline(0, color='k', lw=0.8, ls='--')
ax.set_yticks(x)
ax.set_yticklabels(class_labels, fontsize=9)
ax.set_xlabel('Mean delta_bl (m, 9-day cumulative)', fontsize=8)
ax.set_title('C.  D-Morph delta_bl per seagrass class\n'
             '(mean ± 1 std, blue=bl, red=vr)',
             fontsize=9, fontweight='bold')
# annotate diff on each bar pair
for i, (dm, lbl) in enumerate(zip(diff_means, class_labels)):
    ax.text(max(bl_means[i], vr_means[i]) + 0.01, i,
            f'Δ={dm:+.3f}m', va='center', fontsize=8, color='#555555')
ax.legend(fontsize=8, loc='lower right')
ax.grid(True, axis='x', alpha=0.3)
ax.invert_yaxis()

# ------ Panel D: seagrass/trachytope classification (reference) ------
axes[3].scatter(face_x[trac_class == 0], face_y[trac_class == 0],
                c='#aaaaaa', s=1.2, linewidths=0, rasterized=True, label='unclassified')
for tc in [1, 2, 3, 4]:
    mask = trac_class == tc
    if mask.sum() == 0:
        continue
    axes[3].scatter(face_x[mask], face_y[mask],
                    c=TRAC_COLORS[tc], s=2.5, linewidths=0, rasterized=True)
axes[3].set_title('D.  Seagrass / trachytope class (reference)', fontsize=9, fontweight='bold')
handles = [mpatches.Patch(color=TRAC_COLORS[tc],
                          label=f'{TRAC_LABELS[tc]}  n={( trac_class==tc).sum()}')
           for tc in [1, 2, 3, 4] if (trac_class == tc).sum() > 0]
handles += [mpatches.Patch(color='#aaaaaa',
                           label=f'unclassified  n={(trac_class==0).sum()}')]
axes[3].legend(handles=handles, fontsize=8, loc='lower right',
               framealpha=0.92, edgecolor='grey')
_add_blowup_marker(axes[3], show_legend=False)

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
