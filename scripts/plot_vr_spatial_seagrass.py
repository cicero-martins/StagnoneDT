"""
VR spatial effect map overlaid with seagrass trachytope classification.

Panels:
  A. Trachytope class per face (sampled from RF v3 TIF)
  B. Absolute velocity change: nodm_vr - nodm  (m/s)
  C. Relative velocity change  (%)
  + stats by trachytope class
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

CLASS_TIF = PROC / 'planet2023_rf_v3' / 'classified_seagrass_aug2023_v3.tif'

# trachytope IDs (0 = no match / nodata → skip, else 1-4)
RF_TO_TRAC = {0: 1, 1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 7: 4}
TRAC_LABELS = {
    0: 'no data',
    1: 'sand (n=0.020)',
    2: 'Cymodocea Baptist\n(hv=0.15m, 24×bg)',
    3: 'Posidônia Baptist\n(hv=0.50m, 92×bg)',
    4: 'rock (n=0.028)',
}
TRAC_COLORS = {0: '#aaaaaa', 1: '#f4e04d', 2: '#5ec45e', 3: '#1a7a3e', 4: '#8b4513'}

# -------------------------------------------------------------------
# 1. Load velocity NPZ
# -------------------------------------------------------------------
d_vr = np.load(PROC / 'vel_lagoon_nodm_vr.npz')
d_nm = np.load(PROC / 'vel_lagoon_nodm.npz')
face_x = d_vr['face_x']
face_y = d_vr['face_y']
diff   = d_vr['umean'] - d_nm['umean']
pct    = diff / (d_nm['umean'] + 1e-6) * 100

# -------------------------------------------------------------------
# 2. Sample trachytope class at each face center
# -------------------------------------------------------------------
print('Sampling seagrass raster...')
t = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
fx_utm, fy_utm = t.transform(face_x, face_y)

with rasterio.open(CLASS_TIF) as src:
    # rasterio sample: list of (x, y) tuples
    coords = list(zip(fx_utm, fy_utm))
    rf_vals = np.array([v[0] for v in src.sample(coords)], dtype=float)
    nodata = src.nodata if src.nodata is not None else -9999

rf_vals[rf_vals == nodata] = -1
trac_class = np.full(len(face_x), 0, dtype=int)  # 0 = no match
for rf_id, tr_id in RF_TO_TRAC.items():
    trac_class[rf_vals == rf_id] = tr_id

print('Trachytope class distribution:')
for tc in range(5):
    n = (trac_class == tc).sum()
    pct_cells = n / len(trac_class) * 100
    print(f'  {tc} {TRAC_LABELS[tc][:20]:<20}: {n:5d} cells ({pct_cells:.1f}%)')

# -------------------------------------------------------------------
# 3. Statistics by trachytope class
# -------------------------------------------------------------------
print('\nVelocity change by trachytope class (nodm_vr - nodm):')
print(f"{'class':<6} {'label':<22} {'n':>5}  {'dU mean':>8} {'dU p50':>8} {'dU%mean':>9} {'dU%p50':>9}")
for tc in [1, 2, 3, 4]:
    mask = trac_class == tc
    if mask.sum() < 5:
        continue
    d = diff[mask]
    ref = d_nm['umean'][mask]
    dp = pct[mask]
    label = TRAC_LABELS[tc].split('\n')[0]
    print(f"  {tc:<4} {label:<22} {mask.sum():>5}  "
          f"{d.mean():>+8.5f} {np.median(d):>+8.5f} "
          f"{dp.mean():>+9.1f}% {np.median(dp):>+9.1f}%")

# -------------------------------------------------------------------
# 4. Figure — 3-panel map
# -------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(16, 7))

# Panel A: trachytope classification
ax = axes[0]
for tc in [0, 1, 2, 3, 4]:
    mask = trac_class == tc
    if mask.sum() == 0:
        continue
    ax.scatter(face_x[mask], face_y[mask],
               c=TRAC_COLORS[tc], s=1.5, label=TRAC_LABELS[tc].split('\n')[0],
               linewidths=0, rasterized=True)
ax.set_title('A. Trachytope class', fontsize=10, fontweight='bold')
handles = [mpatches.Patch(color=TRAC_COLORS[tc],
                          label=f'{TRAC_LABELS[tc].split(chr(10))[0]} ({(trac_class==tc).sum()})')
           for tc in [1, 2, 3, 4] if (trac_class == tc).sum() > 0]
ax.legend(handles=handles, fontsize=6.5, loc='lower right', framealpha=0.85)

# Panel B: absolute Δ|u|
ax = axes[1]
vmax_abs = np.percentile(np.abs(diff), 97)
sc = ax.scatter(face_x, face_y, c=diff, cmap='RdBu_r', s=1.5,
                vmin=-vmax_abs, vmax=vmax_abs, linewidths=0, rasterized=True)
plt.colorbar(sc, ax=ax, label='Δ|u| (m/s)', fraction=0.035, pad=0.02)
ax.set_title('B. Absolute Δ|u| (nodm_vr − nodm)', fontsize=10, fontweight='bold')
# count cells
n_faster = (diff > 0).sum()
n_slower = (diff < 0).sum()
ax.text(0.02, 0.98, f'faster: {n_faster} ({n_faster/len(diff)*100:.0f}%)\n'
        f'slower: {n_slower} ({n_slower/len(diff)*100:.0f}%)',
        transform=ax.transAxes, fontsize=7.5, va='top',
        bbox=dict(fc='white', alpha=0.75, pad=2))

# Panel C: relative %
ax = axes[2]
vmax_pct = np.percentile(np.abs(pct), 97)
sc2 = ax.scatter(face_x, face_y, c=pct, cmap='RdBu_r', s=1.5,
                 vmin=-vmax_pct, vmax=vmax_pct, linewidths=0, rasterized=True)
plt.colorbar(sc2, ax=ax, label='Δ|u| (%)', fraction=0.035, pad=0.02)
ax.set_title('C. Relative Δ|u| (%)', fontsize=10, fontweight='bold')

for ax in axes:
    ax.set_xlabel('Longitude', fontsize=9)
    ax.set_aspect('equal')
axes[0].set_ylabel('Latitude', fontsize=9)

fig.suptitle('VR spatial effect — Baptist vegetation roughness (nodm_vr vs nodm, D-Morph OFF)\n'
             'Red = VR accelerates, Blue = VR slows down', fontsize=10)
fig.tight_layout()
out = FIG / 'vr_spatial_seagrass_full.png'
fig.savefig(out, dpi=160, bbox_inches='tight')
plt.close(fig)
print(f'\nFig -> {out}')

# -------------------------------------------------------------------
# 5. Zoomed figure — class-by-class comparison in 2 rows
# -------------------------------------------------------------------
fig2, axes2 = plt.subplots(2, 2, figsize=(12, 10))
titles = {2: 'Cymodocea (trac 2)', 3: 'Posidônia (trac 3)',
          1: 'sand (trac 1)', 4: 'rock (trac 4)'}
axlist = [axes2[0,0], axes2[0,1], axes2[1,0], axes2[1,1]]
for ax, tc in zip(axlist, [2, 3, 1, 4]):
    mask = trac_class == tc
    rest = ~mask
    # background: all cells grey
    ax.scatter(face_x[rest], face_y[rest], c='#e0e0e0', s=0.8,
               linewidths=0, rasterized=True)
    if mask.sum() > 0:
        vmax_tc = np.percentile(np.abs(pct[mask]), 97) if mask.sum() > 5 else 50
        sc = ax.scatter(face_x[mask], face_y[mask], c=pct[mask],
                        cmap='RdBu_r', s=3,
                        vmin=-vmax_tc, vmax=vmax_tc, linewidths=0, rasterized=True)
        plt.colorbar(sc, ax=ax, label='Δ|u| (%)', fraction=0.03)
        med = np.median(pct[mask])
        ax.set_title(f'{titles[tc]}\nn={mask.sum()}  median Δ={med:+.1f}%',
                     fontsize=9, fontweight='bold')
    ax.set_aspect('equal')
    ax.set_xlabel('Lon', fontsize=8); ax.set_ylabel('Lat', fontsize=8)

fig2.suptitle('VR Δ|u| (%) by seagrass class\n'
              'Red = accelerated, Blue = decelerated', fontsize=10)
fig2.tight_layout()
out2 = FIG / 'vr_spatial_by_class.png'
fig2.savefig(out2, dpi=160, bbox_inches='tight')
plt.close(fig2)
print(f'Fig2 -> {out2}')
print('Done.')
