"""Lyzenga (1978) SDB on sand pixels — comparison with Stumpf (2003).

Lyzenga SDB model:  z = a0 + a1*u_blue + a2*u_green
  where  u_i = ln(R_i - R_inf_i)
  and    R_inf estimated from p5 of offshore deep-water pixels (NIR<0.05).

This is different from the DII used in classification (depth-invariant):
  DII = ln(Ri) - k_ij*ln(Rj)  removes depth signal, unsuitable for SDB.

Outputs:
    figures/sdb_lyzenga_sand.png
"""
from pathlib import Path
import json
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
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'

COMP23   = PROC / 'planet2023_rf'      / 'composite_aug2023.tif'
COMP25   = PROC / 'planet2025_aug_rf'  / 'composite_aug2025.tif'
CLS23    = PROC / 'planet2023_rf_v3'   / 'classified_seagrass_aug2023_v3.tif'
CLS25    = PROC / 'planet2025_aug_rf'  / 'classified_seagrass_aug2025.tif'
BATHY_NC = PROC / 'mesh_v05'           / 'topobathy_combined.nc'

# Pre-computed Stumpf Dz for comparison
STUMPF_D23 = PROC / 'planet_sdb_2023_2025' / 'depth_2023.tif'
STUMPF_D25 = PROC / 'planet_sdb_2023_2025' / 'depth_2025.tif'

HARM_FACTOR = 0.9101   # RC_2025/RC_2023 — apply to 2023 to match 2025 scale
B_BLUE  = 1            # 490 nm
B_GREEN = 3            # 531 nm
B_NIR   = 7            # 865 nm
SAND_CLASS  = 0
ATOLL_CLASS = 4
Z_CAL_MIN   = -4.0
Z_CAL_MAX   = -0.3
EPS         = 1e-4     # floor for ln(R - R_inf) to avoid log(<=0)

LAG_UTM = dict(xmin=270700, xmax=281000, ymin=4190000, ymax=4203000)


# ── 1. Load composites ────────────────────────────────────────────────────────

print('Loading composites...')
with rasterio.open(COMP23) as src:
    comp23 = src.read().astype(np.float32)
    prof   = src.profile.copy()
    tf     = src.transform
    H, W   = src.height, src.width

with rasterio.open(COMP25) as src:
    comp25 = src.read().astype(np.float32)

comp23 = comp23 * HARM_FACTOR   # harmonise 2023 to 2025 scale

xs = tf.c + (np.arange(W) + 0.5) * tf.a
ys = tf.f + (np.arange(H) + 0.5) * tf.e
xg, yg = np.meshgrid(xs, ys)
lag = ((xg >= LAG_UTM['xmin']) & (xg <= LAG_UTM['xmax']) &
       (yg >= LAG_UTM['ymin']) & (yg <= LAG_UTM['ymax']))


# ── 2. Estimate R_inf from offshore deep-water pixels ─────────────────────────

print('Estimating R_inf from offshore pixels...')
outside = ~lag
nir23   = comp23[B_NIR]
blue23  = comp23[B_BLUE]
green23 = comp23[B_GREEN]

# Very clear water: outside lagoon, low NIR (no bottom), some blue signal
deep = (outside &
        (nir23 > 0.002) & (nir23 < 0.05) &
        (blue23 > 0.005) & (blue23 < 0.08) &
        ~np.isnan(comp23).any(axis=0))
print(f'  Deep-water calibration pixels: {deep.sum():,}')

R_inf_blue  = float(np.percentile(blue23[deep],  5))
R_inf_green = float(np.percentile(green23[deep], 5))
print(f'  R_inf  blue={R_inf_blue:.4f}  green={R_inf_green:.4f}')


# ── 3. Water mask + Lyzenga u-variables ──────────────────────────────────────

def water_mask(comp):
    return (comp[B_NIR] < 0.15) & (comp[B_BLUE] > 0.01) & ~np.isnan(comp).any(axis=0)

def lyzenga_uv(comp, Rb_inf, Rg_inf):
    """Return (u_blue, u_green) arrays, NaN outside water mask."""
    wm = water_mask(comp) & lag
    b  = comp[B_BLUE]
    g  = comp[B_GREEN]
    ub = np.full((H, W), np.nan, np.float32)
    ug = np.full((H, W), np.nan, np.float32)
    diff_b = np.where(wm, np.maximum(b - Rb_inf, EPS), np.nan)
    diff_g = np.where(wm, np.maximum(g - Rg_inf, EPS), np.nan)
    ub[wm] = np.log(diff_b[wm]).astype(np.float32)
    ug[wm] = np.log(diff_g[wm]).astype(np.float32)
    return ub, ug

# Per-year R_inf: normalize each composite against its own offshore baseline.
# This removes inter-annual atmospheric/radiometric offsets (the 2025 composite
# is ~40-50% brighter offshore even after the 0.9101 harmonization factor).
print('Estimating 2025 R_inf (per-year normalization)...')
deep25 = (outside &
          (comp25[B_NIR] > 0.002) & (comp25[B_NIR] < 0.05) &
          (comp25[B_BLUE] > 0.005) & (comp25[B_BLUE] < 0.08) &
          ~np.isnan(comp25).any(axis=0))
R_inf_blue_25  = float(np.percentile(comp25[B_BLUE][deep25],  5))
R_inf_green_25 = float(np.percentile(comp25[B_GREEN][deep25], 5))
print(f'  R_inf 2023: blue={R_inf_blue:.4f}  green={R_inf_green:.4f}')
print(f'  R_inf 2025: blue={R_inf_blue_25:.4f}  green={R_inf_green_25:.4f}')
print(f'  Offshore ratio 2025/2023: blue={R_inf_blue_25/R_inf_blue:.2f}  green={R_inf_green_25/R_inf_green:.2f}')

print('Computing Lyzenga u-variables...')
ub23, ug23 = lyzenga_uv(comp23, R_inf_blue,    R_inf_green)
ub25, ug25 = lyzenga_uv(comp25, R_inf_blue_25, R_inf_green_25)  # per-year R_inf

both_valid = np.isfinite(ub23) & np.isfinite(ub25)
print(f'  Both-valid lagoon pixels: {both_valid.sum():,}')


# ── 4. Load classifications ───────────────────────────────────────────────────

print('Loading classifications...')
with rasterio.open(CLS23) as src:
    cls23 = src.read(1).astype(np.int16)
with rasterio.open(CLS25) as src:
    d25 = src.read(1).astype(np.int16)
    if d25.shape != (H, W):
        cls25 = np.full((H, W), -9999, np.int16)
        with rasterio.open(CLS25) as src25:
            reproject(src25.read(1), cls25,
                      src_transform=src25.transform, src_crs=src25.crs,
                      dst_transform=tf, dst_crs=prof['crs'],
                      resampling=Resampling.nearest,
                      src_nodata=-9999, dst_nodata=-9999)
    else:
        cls25 = d25

sand_mask  = both_valid & (cls23 == SAND_CLASS)  & (cls25 == SAND_CLASS)
atoll_mask = both_valid & (cls23 == ATOLL_CLASS) & (cls25 == ATOLL_CLASS)
print(f'  Stable sand : {sand_mask.sum():,}  atolls: {atoll_mask.sum():,}')


# ── 5. Reproject bathymetry ───────────────────────────────────────────────────

print('Reprojecting bathymetry...')
ds_b = xr.open_dataset(BATHY_NC)
lat  = ds_b.lat.values;  lon = ds_b.lon.values
z_raw = ds_b['topobathy'].values.astype(np.float32)
ds_b.close()
dlat = float(lat[1]-lat[0]); dlon = float(lon[1]-lon[0])
src_tf = rasterio.transform.from_origin(
    float(lon[0])-abs(dlon)/2, float(lat[-1])+abs(dlat)/2, abs(dlon), abs(dlat))
z_utm = np.full((H, W), np.nan, np.float32)
reproject(z_raw[::-1], z_utm,
          src_transform=src_tf, src_crs='EPSG:4326',
          dst_transform=tf, dst_crs=prof['crs'],
          src_nodata=np.nan, dst_nodata=np.nan,
          resampling=Resampling.bilinear)
print(f'  Bathy range: [{np.nanmin(z_utm):.2f}, {np.nanmax(z_utm):.2f}] m')


# ── 6. Lyzenga calibration (sand-only, MLR 2 predictors) ─────────────────────

cal_mask = (sand_mask & np.isfinite(z_utm) &
            (z_utm >= Z_CAL_MIN) & (z_utm <= Z_CAL_MAX))
n_cal = cal_mask.sum()
print(f'\nSand calibration pixels: {n_cal:,}')

ub_cal = ub23[cal_mask];  ug_cal = ug23[cal_mask];  z_cal = z_utm[cal_mask]
step   = max(1, n_cal // 3000)
ub_s   = ub_cal[::step];  ug_s = ug_cal[::step];  z_s = z_cal[::step]

# OLS:  z = a0 + a1*ub + a2*ug   via lstsq
X  = np.column_stack([np.ones(len(z_s)), ub_s, ug_s])
coeff, _, _, _ = np.linalg.lstsq(X, z_s, rcond=None)
a0, a1, a2 = coeff
z_pred = X @ coeff
ss_res = np.sum((z_s - z_pred)**2)
ss_tot = np.sum((z_s - z_s.mean())**2)
r2_lyz = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
r_lyz  = float(np.corrcoef(z_s, z_pred)[0, 1])
print(f'  Lyzenga fit:  z = {a0:.3f} + {a1:.3f}*ub + {a2:.3f}*ug')
print(f'  r={r_lyz:.3f}  R2={r2_lyz:.3f}  n={len(z_s)}  (Stumpf R2 was 0.000)')

# Apply to both years
def apply_lyzenga(ub, ug):
    return np.where(np.isfinite(ub) & np.isfinite(ug),
                    a0 + a1*ub + a2*ug, np.nan).astype(np.float32)

depth23_lyz = apply_lyzenga(ub23, ug23)
depth25_lyz = apply_lyzenga(ub25, ug25)
dz_lyz = np.where(sand_mask, depth25_lyz - depth23_lyz, np.nan)

dz_sand   = dz_lyz[sand_mask]
mu_lyz    = float(np.nanmean(dz_sand));   sig_lyz = float(np.nanstd(dz_sand))
print(f'  Sand Dz:  mean={mu_lyz:+.4f} m  std={sig_lyz:.4f} m')

# Depth-bin breakdown
DEPTH_BINS = [(-4.0, -1.5, '>1.5m'), (-1.5, -0.5, '0.5-1.5m'), (-0.5, -0.05, '<0.5m')]
print('\nDelta_z by depth bin (Lyzenga, sand only):')
for zmin, zmax, label in DEPTH_BINS:
    m = sand_mask & np.isfinite(z_utm) & (z_utm >= zmin) & (z_utm <= zmax)
    if m.sum() < 10:
        continue
    dz = dz_lyz[m]
    print(f'  {label:<12} {m.sum():>7,}  '
          f'{np.nanmean(dz):>+7.4f}  std={np.nanstd(dz):.4f} m')


# ── 7. Load Stumpf Dz for comparison ─────────────────────────────────────────

print('\nLoading Stumpf depth TIFs for comparison...')
with rasterio.open(STUMPF_D23) as src: d23_st = src.read(1).astype(np.float32)
with rasterio.open(STUMPF_D25) as src: d25_st = src.read(1).astype(np.float32)
dz_stumpf = np.where(sand_mask, d25_st - d23_st, np.nan)
mu_st  = float(np.nanmean(dz_stumpf[sand_mask]))
sig_st = float(np.nanstd( dz_stumpf[sand_mask]))
print(f'  Stumpf sand Dz: mean={mu_st:+.4f} m  std={sig_st:.4f} m')


# ── 8. Stumpf calibration R2 on same sand pixels (for comparison bar) ─────────

# Re-derive Stumpf index from harmonized comp23 for the same calibration pixels
NORM = 1000.0
b23  = comp23[B_BLUE];  g23 = comp23[B_GREEN]
ok   = (b23 > 0) & (g23 > 0) & cal_mask
I23  = np.full((H,W), np.nan, np.float32)
I23[ok] = (np.log(NORM*b23[ok]) / np.log(NORM*g23[ok])).astype(np.float32)
I23_cal = I23[cal_mask];  I23_s = I23_cal[::step]
slope_st, intercept_st, r_st, _, _ = stats.linregress(I23_s, z_s)
r2_st = r_st**2
print(f'\n  Stumpf sand cal: z = {slope_st:.3f}*I + {intercept_st:.3f}  R2={r2_st:.3f}')
print(f'  Lyzenga sand cal: R2={r2_lyz:.3f}')


# ── 9. Figure ─────────────────────────────────────────────────────────────────

DS = 4
def ds(arr): return arr[::DS, ::DS]

extent = [xs[0], xs[-1], ys[-1], ys[0]]
ax_ext = [LAG_UTM['xmin']-200, LAG_UTM['xmax']+200,
          LAG_UTM['ymin']-200, LAG_UTM['ymax']+200]

fig, axes = plt.subplots(2, 2, figsize=(14, 12))
axes = axes.ravel()

# Panel A: Lyzenga calibration scatter
ax = axes[0]
ax.scatter(ub_s, z_s, s=1.5, alpha=0.35, c='#1a7a3e', rasterized=True,
           label='sand pixels')
ub_fit = np.linspace(ub_s.min(), ub_s.max(), 50)
ug_med = np.median(ug_s)
ax.plot(ub_fit, a0 + a1*ub_fit + a2*ug_med, 'r-', lw=2,
        label=f'MLR @ ug=median\nr={r_lyz:.3f}  R2={r2_lyz:.3f}')
ax.set_xlabel('u_blue = ln(R_blue - R_inf)', fontsize=9)
ax.set_ylabel('Model depth z (m)', fontsize=9)
ax.set_title(f'A.  Lyzenga calibration (sand, {len(z_s):,} pts)\n'
             f'z = {a0:.2f} + {a1:.2f}*u_b + {a2:.2f}*u_g', fontsize=9, fontweight='bold')
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.axhline(0, c='k', lw=0.5, ls='--')

# Panel B: Stumpf calibration scatter (same pixels)
ax = axes[1]
ax.scatter(I23_s, z_s, s=1.5, alpha=0.35, c='#d4a017', rasterized=True,
           label='sand pixels')
xfit = np.linspace(I23_s.min(), I23_s.max(), 50)
ax.plot(xfit, slope_st*xfit + intercept_st, 'r-', lw=2,
        label=f'OLS\nr={r_st:.3f}  R2={r2_st:.3f}')
ax.set_xlabel('Stumpf index I = ln(1000*B_blue)/ln(1000*B_green)', fontsize=9)
ax.set_ylabel('Model depth z (m)', fontsize=9)
ax.set_title(f'B.  Stumpf calibration (sand, {len(I23_s):,} pts)\n'
             f'z = {slope_st:.2f}*I + {intercept_st:.2f}', fontsize=9, fontweight='bold')
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.axhline(0, c='k', lw=0.5, ls='--')

# Panel C: Dz map (Lyzenga sand)
dz_sym = min(float(np.nanpercentile(np.abs(dz_sand[np.isfinite(dz_sand)]), 95)), 0.5)
norm_dz = TwoSlopeNorm(vmin=-dz_sym, vcenter=0, vmax=dz_sym)
sc = axes[2].imshow(ds(np.where(sand_mask, dz_lyz, np.nan)),
                    extent=extent, origin='upper', aspect='equal',
                    cmap='RdBu', norm=norm_dz, interpolation='nearest')
plt.colorbar(sc, ax=axes[2], label='Lyzenga Dz (m)', fraction=0.035, pad=0.02, shrink=0.8)
axes[2].set_xlim(ax_ext[:2]); axes[2].set_ylim(ax_ext[2:])
axes[2].set_title(f'C.  Lyzenga Dz (sand, Aug 2023 vs 2025)\n'
                  f'mean={mu_lyz:+.4f} m  std={sig_lyz:.4f} m',
                  fontsize=9, fontweight='bold')
axes[2].set_xlabel('Easting (m)', fontsize=8); axes[2].set_ylabel('Northing (m)', fontsize=8)

# Panel D: Histogram comparison Lyzenga vs Stumpf for sand
ax = axes[3]
bins = np.linspace(-0.15, 0.15, 61)
dz_l_fin = dz_sand[np.isfinite(dz_sand)]
dz_s_fin = dz_stumpf[sand_mask][np.isfinite(dz_stumpf[sand_mask])]
ax.hist(dz_l_fin, bins=bins, alpha=0.6, density=True, color='#1a7a3e',
        label=f'Lyzenga  mean={mu_lyz:+.4f} m  std={sig_lyz:.4f} m')
ax.hist(dz_s_fin, bins=bins, alpha=0.5, density=True, color='#d4a017',
        label=f'Stumpf   mean={mu_st:+.4f} m  std={sig_st:.4f} m')
ax.axvline(mu_lyz, c='#1a7a3e', lw=1.5, ls='--')
ax.axvline(mu_st,  c='#d4a017',  lw=1.5, ls='--')
ax.axvline(0, c='grey', lw=0.8)
ax.set_xlabel('Dz (m, +=shallower)', fontsize=9)
ax.set_ylabel('Probability density', fontsize=9)
ax.set_title(f'D.  Dz histogram: Lyzenga vs Stumpf (sand)\n'
             f'R2_lyz={r2_lyz:.3f}  R2_stumpf={r2_st:.3f}',
             fontsize=9, fontweight='bold')
ax.legend(fontsize=8); ax.grid(alpha=0.3)

fig.suptitle(
    'Lyzenga (1978) SDB vs Stumpf (2003) — sand pixels only  |  per-year R_inf normalization\n'
    f'R_inf 2023: blue={R_inf_blue:.4f} green={R_inf_green:.4f}  '
    f'| R_inf 2025: blue={R_inf_blue_25:.4f} green={R_inf_green_25:.4f}  '
    f'(offshore ratio 2025/2023: blue×{R_inf_blue_25/R_inf_blue:.2f} green×{R_inf_green_25/R_inf_green:.2f})',
    fontsize=9
)
fig.tight_layout()
out = FIG / 'sdb_lyzenga_sand.png'
fig.savefig(out, dpi=160, bbox_inches='tight')
plt.close(fig)
print(f'\nFig -> {out}')
print('Done.')
