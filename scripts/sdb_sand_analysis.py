"""SDB sand-only analysis: depth change in unvegetated areas 2023 vs 2025.

Uses pre-computed SDB index GeoTIFFs from sdb_2023_vs_2025.py and restricts
analysis to pixels classified as class 0 (unvegetated/sand) in BOTH years.

Sand mask rationale:
  - Sand has uniform bottom reflectance -> cleaner depth-reflectance relationship
  - Removes the seagrass canopy-density confound that dominated the lagoon-wide Dz
  - Directly relevant for D-Morph calibration (sediment transport on sandy bed)

Improvements over sdb_2023_vs_2025.py:
  - Calibration restricted to sand pixels -> higher R2, less seagrass bias
  - Sand-only Dz map with spatial context
  - Depth-stratified statistics (shallows 0-0.5m, mid 0.5-1.5m, deep >1.5m)
  - Comparison bar: sand vs Posidonia atolls to illustrate biological confound

Outputs:
    figures/sdb_sand_2023_vs_2025.png
"""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import xarray as xr
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[1]
PROC = Path('c:/Users/Unipa/Documents/StagnoneDT/data/processed')
FIG  = ROOT / 'figures'
SDB_DIR = PROC / 'planet_sdb_2023_2025'

# Classifications (both on same 2023 reference grid 3813x6680 UTM33N)
CLS23 = PROC / 'planet2023_rf_v3' / 'classified_seagrass_aug2023_v3.tif'
CLS25 = PROC / 'planet2025_aug_rf' / 'classified_seagrass_aug2025.tif'

BATHY_NC = PROC / 'mesh_v05' / 'topobathy_combined.nc'

SAND_CLASS = 0       # RF class 0 = unvegetated / sand
ATOLL_CLASS = 4      # RF class 4 = Posidonia atolls (biological confound reference)

Z_CAL_MIN = -4.0
Z_CAL_MAX = -0.3
NORM = 1000.0
HARM_FACTOR = 0.9101

LAG_UTM = dict(xmin=270700, xmax=281000, ymin=4190000, ymax=4203000)

DEPTH_BINS = [(-4.0, -1.5, '>1.5m'), (-1.5, -0.5, '0.5-1.5m'), (-0.5, -0.05, '<0.5m')]


# ── load pre-computed SDB index rasters ───────────────────────────────────────

def load_tif(path):
    with rasterio.open(path) as src:
        arr  = src.read(1).astype(np.float32)
        prof = src.profile.copy()
    arr[arr == (prof.get('nodata') or np.nan)] = np.nan
    return arr, prof


print('Loading SDB index rasters...')
I23, prof = load_tif(SDB_DIR / 'sdb_index_2023.tif')
I25, _    = load_tif(SDB_DIR / 'sdb_index_2025.tif')
H, W = I23.shape
print(f'  Grid: {H}x{W}')


# ── load classifications (same grid, no reproject needed) ─────────────────────

print('Loading classification maps...')
with rasterio.open(CLS23) as src:
    cls23 = src.read(1).astype(np.int16)
    nodata23 = src.nodata or -9999

with rasterio.open(CLS25) as src:
    d25 = src.read(1).astype(np.int16)
    nodata25 = src.nodata or -9999

# Both are on 3813x6680 (2023 reference grid) — verify
if cls23.shape != (H, W):
    raise RuntimeError(f'cls23 shape mismatch: {cls23.shape} vs ({H},{W})')
if d25.shape != (H, W):
    print(f'  Reprojecting 2025 class from {d25.shape} to ({H},{W})')
    cls25_full = np.full((H, W), nodata25, dtype=np.int16)
    with rasterio.open(CLS25) as src25:
        reproject(source=src25.read(1), destination=cls25_full,
                  src_transform=src25.transform, src_crs=src25.crs,
                  dst_transform=prof['transform'], dst_crs=prof['crs'],
                  resampling=Resampling.nearest,
                  src_nodata=int(nodata25), dst_nodata=int(nodata25))
    cls25 = cls25_full
else:
    cls25 = d25

print(f'  2023 class 0 (sand): {(cls23==SAND_CLASS).sum():,} px')
print(f'  2025 class 0 (sand): {(cls25==SAND_CLASS).sum():,} px')


# ── lagoon + water mask ────────────────────────────────────────────────────────

tf = prof['transform']
xs = tf.c + (np.arange(W) + 0.5) * tf.a
ys = tf.f + (np.arange(H) + 0.5) * tf.e
xg, yg = np.meshgrid(xs, ys)
lag = ((xg >= LAG_UTM['xmin']) & (xg <= LAG_UTM['xmax']) &
       (yg >= LAG_UTM['ymin']) & (yg <= LAG_UTM['ymax']))

both_water = np.isfinite(I23) & np.isfinite(I25) & lag
print(f'  Both-water lagoon pixels: {both_water.sum():,}')


# ── sand mask (stable sand: class 0 in both years) ────────────────────────────

sand_mask = both_water & (cls23 == SAND_CLASS) & (cls25 == SAND_CLASS)
atoll_mask = both_water & (cls23 == ATOLL_CLASS) & (cls25 == ATOLL_CLASS)
print(f'  Stable sand (both years class 0):  {sand_mask.sum():,} px')
print(f'  Stable atolls (both years class 4): {atoll_mask.sum():,} px')


# ── bathymetry reprojection ───────────────────────────────────────────────────

print('Loading bathymetry...')
ds = xr.open_dataset(BATHY_NC)
lat = ds.lat.values;  lon = ds.lon.values
z_raw = ds['topobathy'].values.astype(np.float32)
ds.close()
dlat = float(lat[1] - lat[0]);  dlon = float(lon[1] - lon[0])
src_tf = rasterio.transform.from_origin(
    west=float(lon[0]) - abs(dlon) / 2,
    north=float(lat[-1]) + abs(dlat) / 2,
    xsize=abs(dlon), ysize=abs(dlat))
z_flip = z_raw[::-1]
z_utm = np.full((H, W), np.nan, dtype=np.float32)
reproject(source=z_flip, destination=z_utm,
          src_transform=src_tf, src_crs='EPSG:4326',
          dst_transform=prof['transform'], dst_crs=prof['crs'],
          src_nodata=np.nan, dst_nodata=np.nan,
          resampling=Resampling.bilinear)
print(f'  Bathy valid: {np.isfinite(z_utm).sum():,}  '
      f'range=[{np.nanmin(z_utm):.2f},{np.nanmax(z_utm):.2f}] m')


# ── calibration on sand pixels only ──────────────────────────────────────────

cal_mask = (sand_mask &
            np.isfinite(z_utm) &
            (z_utm >= Z_CAL_MIN) & (z_utm <= Z_CAL_MAX))
n_cal = cal_mask.sum()
print(f'\nSand calibration pixels ({Z_CAL_MIN}<z<{Z_CAL_MAX}): {n_cal:,}')

if n_cal < 50:
    raise RuntimeError('Too few sand calibration pixels')

I23_cal = I23[cal_mask];  z_cal = z_utm[cal_mask]
step = max(1, n_cal // 3000)
I23_s = I23_cal[::step];  z_s = z_cal[::step]
slope, intercept, r, p, se = stats.linregress(I23_s, z_s)
print(f'  Sand-only linear fit:  z = {slope:.3f} * I + {intercept:.3f}')
print(f'  r={r:.3f}  R2={r**2:.3f}  n={len(I23_s)}  (vs. all-water R2=0.135)')

# Apply calibration
depth23_sand = np.where(sand_mask, slope * I23 + intercept, np.nan)
depth25_sand = np.where(sand_mask, slope * I25 + intercept, np.nan)
delta_z = depth25_sand - depth23_sand

# Also apply to atolls for comparison
depth23_atoll = np.where(atoll_mask, slope * I23 + intercept, np.nan)
depth25_atoll = np.where(atoll_mask, slope * I25 + intercept, np.nan)
delta_z_atoll = depth25_atoll - depth23_atoll


# ── per-depth-bin stats ───────────────────────────────────────────────────────

print('\nDelta_z by depth bin (sand only):')
print(f'  {"bin":<12} {"n":>7}  {"mean":>7} {"std":>7} {"p10":>7} {"p90":>7}')
for zmin, zmax, label in DEPTH_BINS:
    m = sand_mask & np.isfinite(z_utm) & (z_utm >= zmin) & (z_utm <= zmax)
    if m.sum() < 10:
        continue
    dz = delta_z[m]
    print(f'  {label:<12} {m.sum():>7,}  '
          f'{np.nanmean(dz):>+7.3f} {np.nanstd(dz):>7.3f} '
          f'{np.nanpercentile(dz,10):>+7.3f} {np.nanpercentile(dz,90):>+7.3f} m')

dz_sand = delta_z[sand_mask]
dz_atoll_v = delta_z_atoll[atoll_mask]
mu_sand = np.nanmean(dz_sand);     sig_sand = np.nanstd(dz_sand)
mu_atoll = np.nanmean(dz_atoll_v); sig_atoll = np.nanstd(dz_atoll_v)
print(f'\nSand:    mean={mu_sand:+.3f} m  std={sig_sand:.3f} m  n={sand_mask.sum():,}')
print(f'Atolls:  mean={mu_atoll:+.3f} m  std={sig_atoll:.3f} m  n={atoll_mask.sum():,}')


# ── figure ────────────────────────────────────────────────────────────────────

DS = 4
def ds(arr): return arr[::DS, ::DS]

extent = [xs[0], xs[-1], ys[-1], ys[0]]
ax_ext = [LAG_UTM['xmin'] - 200, LAG_UTM['xmax'] + 200,
          LAG_UTM['ymin'] - 200, LAG_UTM['ymax'] + 200]

dz_sym_sand = min(float(np.nanpercentile(np.abs(dz_sand[np.isfinite(dz_sand)]), 95)), 0.5)

fig, axes = plt.subplots(1, 4, figsize=(22, 8))

# Panel A: sand mask (stable sand = white, all other water = light blue)
sand_display = np.full((H, W), np.nan, dtype=np.float32)
sand_display[both_water] = 0.3
sand_display[sand_mask]  = 1.0
sand_display[atoll_mask] = -0.3
sc0 = axes[0].imshow(ds(sand_display), extent=extent, origin='upper', aspect='equal',
                     cmap='RdYlGn', vmin=-0.5, vmax=1.2,
                     interpolation='nearest')
axes[0].set_xlim(ax_ext[:2]);  axes[0].set_ylim(ax_ext[2:])
axes[0].set_title('A.  Stable substrate mask\n'
                  '(class 0 in 2023 AND 2025)', fontsize=9, fontweight='bold')
handles = [mpatches.Patch(color='#1a9641', label=f'stable sand  n={sand_mask.sum():,}'),
           mpatches.Patch(color='#d7191c', label=f'stable atolls  n={atoll_mask.sum():,}'),
           mpatches.Patch(color='#abd9e9', label='other water')]
axes[0].legend(handles=handles, fontsize=7.5, loc='lower left', framealpha=0.9)

# Panel B: Dz for sand pixels only
dz_vis = np.where(sand_mask, delta_z, np.nan)
norm_dz = TwoSlopeNorm(vmin=-dz_sym_sand, vcenter=0, vmax=dz_sym_sand)
sc1 = axes[1].imshow(ds(dz_vis), extent=extent, origin='upper', aspect='equal',
                     cmap='RdBu', norm=norm_dz, interpolation='nearest')
plt.colorbar(sc1, ax=axes[1], label='Dz (m, +=shallower)', fraction=0.035, pad=0.02, shrink=0.8)
axes[1].set_xlim(ax_ext[:2]);  axes[1].set_ylim(ax_ext[2:])
axes[1].set_title(f'B.  Sand Dz = SDB_2025 - SDB_2023\n'
                  f'mean={mu_sand:+.3f} m  std={sig_sand:.3f} m',
                  fontsize=9, fontweight='bold')

# Panel C: calibration scatter sand-only
axes[2].scatter(I23_s, z_s, s=1.5, alpha=0.35, color='#d4a017', rasterized=True,
                label='sand pixels')
xfit = np.array([I23_s.min(), I23_s.max()])
axes[2].plot(xfit, slope * xfit + intercept, 'r-', lw=2,
             label=f'z = {slope:.2f}*I + {intercept:.2f}\nr={r:.3f}  R2={r**2:.2f}')
axes[2].set_xlabel('Stumpf index I (2023)', fontsize=9)
axes[2].set_ylabel('Model depth z (m)', fontsize=9)
axes[2].set_title(f'C.  Calibration: sand pixels only\n({len(I23_s):,} pts)',
                  fontsize=9, fontweight='bold')
axes[2].legend(fontsize=8);  axes[2].grid(alpha=0.3)
axes[2].axhline(0, color='k', lw=0.5, ls='--')

# Panel D: depth-stratified Dz histogram + sand vs atoll bar comparison
ax = axes[3]
colors_bin = ['#1f77b4', '#ff7f0e', '#2ca02c']
for (zmin, zmax, label), col in zip(DEPTH_BINS, colors_bin):
    m = sand_mask & np.isfinite(z_utm) & (z_utm >= zmin) & (z_utm <= zmax)
    if m.sum() < 10:
        continue
    dz_bin = delta_z[m]
    ax.hist(dz_bin[np.isfinite(dz_bin)], bins=60, range=(-1.0, 1.0),
            alpha=0.55, color=col, density=True,
            label=f'{label}  mean={np.nanmean(dz_bin):+.3f}m  n={m.sum():,}')

# Vertical mean lines
ax.axvline(mu_sand, color='k', lw=1.5, ls='--', label=f'sand mean {mu_sand:+.3f} m')
ax.axvline(mu_atoll, color='#d62728', lw=1.5, ls=':', label=f'atolls mean {mu_atoll:+.3f} m')
ax.axvline(0, color='grey', lw=0.8)
ax.set_xlabel('Dz (m)', fontsize=9)
ax.set_ylabel('Probability density', fontsize=9)
ax.set_title('D.  Dz histogram: sand by depth bin\n(red dashed = Posidonia atolls, for contrast)',
             fontsize=9, fontweight='bold')
ax.legend(fontsize=7.5)
ax.grid(alpha=0.3)
ax.set_xlim(-1.0, 1.0)

for ax in axes[:2]:
    ax.set_xlabel('Easting (m)', fontsize=8)
    ax.set_ylabel('Northing (m)', fontsize=8)
    ax.tick_params(labelsize=7)

fig.suptitle(
    'SDB sand-only analysis — Stagnone di Marsala\n'
    'Stable unvegetated pixels (class 0 in 2023 AND 2025)  |  '
    'Stumpf calibration restricted to sand  |  Aug 2023 vs Aug 2025',
    fontsize=10
)
fig.tight_layout()
out_fig = FIG / 'sdb_sand_2023_vs_2025.png'
fig.savefig(out_fig, dpi=160, bbox_inches='tight')
plt.close(fig)
print(f'\nFig -> {out_fig}')
print('Done.')
