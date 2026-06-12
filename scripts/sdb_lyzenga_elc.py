"""Empirical Line Calibration (ELC) of 2025 composite + Lyzenga SDB comparison.

The 2025 composite is already August-only (20250809 + 20250817) -- step A is done.
This script performs step B: ELC to normalise 2025 onto the 2023 radiometric scale.

ELC method (2-anchor, per-band affine):
  dark  anchor = p5 of offshore deep-water pixels (NIR<0.05, outside lagoon)
  bright anchor = median of salt-flat pixels (NDVI<0.10, blue>0.12, outside lagoon)

  SR_25_elc[b] = a[b] * SR_25[b] + offset[b]
  where a[b], offset[b] fit:  SR_23_anchor = a * SR_25_anchor + offset
  at the two anchor points for each band.

After ELC, re-run Lyzenga SDB on sand pixels and compare Dz before/after.

Outputs:
  data/processed/planet2025_aug_rf/composite_aug2025_elc.tif
  figures/sdb_lyzenga_elc.png
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

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'

COMP23   = PROC / 'planet2023_rf'     / 'composite_aug2023.tif'
COMP25   = PROC / 'planet2025_aug_rf' / 'composite_aug2025.tif'
COMP25_ELC = PROC / 'planet2025_aug_rf' / 'composite_aug2025_elc.tif'
CLS23    = PROC / 'planet2023_rf_v3'  / 'classified_seagrass_aug2023_v3.tif'
CLS25    = PROC / 'planet2025_aug_rf' / 'classified_seagrass_aug2025.tif'
BATHY_NC = PROC / 'mesh_v05'          / 'topobathy_combined.nc'

HARM_FACTOR = 0.9101
B_BLUE  = 1;  B_GREEN = 3;  B_NIR = 7
SAND_CLASS = 0
Z_CAL_MIN  = -4.0;  Z_CAL_MAX = -0.3
EPS        = 1e-4
LAG_UTM    = dict(xmin=270700, xmax=281000, ymin=4190000, ymax=4203000)


# ── 1. Load composites ────────────────────────────────────────────────────────

print('Loading composites...')
with rasterio.open(COMP23) as src:
    comp23 = src.read().astype(np.float32) * HARM_FACTOR
    prof   = src.profile.copy()
    tf     = src.transform
    H, W   = src.height, src.width
with rasterio.open(COMP25) as src:
    comp25 = src.read().astype(np.float32)

xs = tf.c + (np.arange(W)+0.5)*tf.a
ys = tf.f + (np.arange(H)+0.5)*tf.e
xg, yg = np.meshgrid(xs, ys)
outside = ~((xg>=LAG_UTM['xmin']) & (xg<=LAG_UTM['xmax']) &
             (yg>=LAG_UTM['ymin']) & (yg<=LAG_UTM['ymax']))
lag     = ~outside


# ── 2. ELC anchors ────────────────────────────────────────────────────────────

print('Identifying ELC anchors...')

# -- Dark anchor: p5 of offshore deep-water pixels per band
deep = (outside &
        (comp23[B_NIR] > 0.002) & (comp23[B_NIR] < 0.05) &
        (comp23[B_BLUE] > 0.005) & (comp23[B_BLUE] < 0.08) &
        (comp25[B_NIR] > 0.002) & (comp25[B_NIR] < 0.05) &
        ~np.isnan(comp23).any(axis=0) & ~np.isnan(comp25).any(axis=0))
dark23 = np.array([float(np.percentile(comp23[b][deep],  5)) for b in range(8)])
dark25 = np.array([float(np.percentile(comp25[b][deep],  5)) for b in range(8)])
print(f'  Dark anchor pixels: {deep.sum():,}')

# -- Bright anchor: median of stable salt-flat / dry-land pixels
#    NDVI<0.10, blue>0.12, outside lagoon, valid in both composites
nir23  = comp23[B_NIR]; red23 = comp23[5]
nir25  = comp25[B_NIR]; red25 = comp25[5]
ndvi23 = (nir23 - red23) / (nir23 + red23 + 1e-9)
ndvi25 = (nir25 - red25) / (nir25 + red25 + 1e-9)
bright_mask = (outside &
               (ndvi23 < 0.10) & (ndvi25 < 0.10) &
               (comp23[B_BLUE] > 0.12) & (comp25[B_BLUE] > 0.10) &
               ~np.isnan(comp23).any(axis=0) & ~np.isnan(comp25).any(axis=0))
bright23 = np.array([float(np.median(comp23[b][bright_mask])) for b in range(8)])
bright25 = np.array([float(np.median(comp25[b][bright_mask])) for b in range(8)])
print(f'  Bright anchor pixels: {bright_mask.sum():,}')

# Anchors table
BAND_NAMES = ['cb','blue','green_i','green','yellow','red','rededge','nir']
print(f'\n  {"band":<10} {"dark23":>8} {"dark25":>8} {"r_dark":>7} | '
      f'{"brt23":>8} {"brt25":>8} {"r_brt":>7}')
for b in range(8):
    print(f'  {BAND_NAMES[b]:<10} {dark23[b]:>8.4f} {dark25[b]:>8.4f} '
          f'{dark25[b]/dark23[b]:>7.3f} | '
          f'{bright23[b]:>8.4f} {bright25[b]:>8.4f} '
          f'{bright25[b]/bright23[b]:>7.3f}')


# ── 3. Fit ELC per band and apply to comp25 ───────────────────────────────────

print('\nFitting ELC (2-anchor affine per band)...')
elc_a = np.zeros(8, np.float32)
elc_b = np.zeros(8, np.float32)

for band in range(8):
    # SR_23 = a * SR_25 + offset  at both anchor points
    d23, d25 = dark23[band],   dark25[band]
    r23, r25 = bright23[band], bright25[band]
    a = (r23 - d23) / (r25 - d25 + 1e-9)
    offset = d23 - a * d25
    elc_a[band] = a
    elc_b[band] = offset
    # Verify: residual at anchors
    res_dark   = abs(a*d25 + offset - d23)
    res_bright = abs(a*r25 + offset - r23)
    print(f'  band {BAND_NAMES[band]:<10}: a={a:.4f}  offset={offset:+.5f}  '
          f'res_dark={res_dark:.5f}  res_bright={res_bright:.5f}')

# Apply ELC: comp25_elc[b] = elc_a[b] * comp25[b] + elc_b[b]
comp25_elc = np.zeros_like(comp25)
for b in range(8):
    comp25_elc[b] = np.where(~np.isnan(comp25[b]),
                             elc_a[b] * comp25[b] + elc_b[b],
                             np.nan)

# Save corrected composite
if not COMP25_ELC.exists():
    prof_out = prof.copy()
    prof_out.update(count=8, dtype='float32', nodata=np.nan)
    with rasterio.open(COMP25_ELC, 'w', **prof_out) as dst:
        dst.write(comp25_elc)
    print(f'\nSaved: {COMP25_ELC.name}')
else:
    print(f'\n  ELC composite already exists: {COMP25_ELC.name} (overwriting)')
    prof_out = prof.copy()
    prof_out.update(count=8, dtype='float32', nodata=np.nan)
    with rasterio.open(COMP25_ELC, 'w', **prof_out) as dst:
        dst.write(comp25_elc)

# Verify: offshore statistics after ELC
deep25_elc_b = float(np.percentile(comp25_elc[B_BLUE][deep],  5))
deep25_elc_g = float(np.percentile(comp25_elc[B_GREEN][deep], 5))
deep23_b     = float(np.percentile(comp23[B_BLUE][deep],  5))
deep23_g     = float(np.percentile(comp23[B_GREEN][deep], 5))
print(f'\nOffshore p5 after ELC:  blue={deep25_elc_b:.4f} (was 0.0197, target {deep23_b:.4f})')
print(f'                        green={deep25_elc_g:.4f} (was 0.0132, target {deep23_g:.4f})')


# ── 4. Load classification masks ──────────────────────────────────────────────

print('\nLoading classifications...')
with rasterio.open(CLS23) as src: cls23 = src.read(1).astype(np.int16)
with rasterio.open(CLS25) as src:
    d25 = src.read(1).astype(np.int16)
    if d25.shape != (H, W):
        cls25 = np.full((H, W), -9999, np.int16)
        with rasterio.open(CLS25) as s25:
            reproject(s25.read(1), cls25, src_transform=s25.transform, src_crs=s25.crs,
                      dst_transform=tf, dst_crs=prof['crs'],
                      resampling=Resampling.nearest, src_nodata=-9999, dst_nodata=-9999)
    else:
        cls25 = d25


# ── 5. Reproject bathymetry ───────────────────────────────────────────────────

print('Reprojecting bathymetry...')
ds_b = xr.open_dataset(BATHY_NC)
lat  = ds_b.lat.values; lon = ds_b.lon.values
z_raw = ds_b['topobathy'].values.astype(np.float32)
ds_b.close()
dlat = float(lat[1]-lat[0]); dlon = float(lon[1]-lon[0])
src_tf = rasterio.transform.from_origin(
    float(lon[0])-abs(dlon)/2, float(lat[-1])+abs(dlat)/2, abs(dlon), abs(dlat))
z_utm = np.full((H, W), np.nan, np.float32)
reproject(z_raw[::-1], z_utm, src_transform=src_tf, src_crs='EPSG:4326',
          dst_transform=tf, dst_crs=prof['crs'],
          src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)


# ── 6. Lyzenga SDB (common R_inf = 2023, single calibration) ─────────────────

# Use 2023 R_inf for both years — composites are now on the same radiometric scale
R_inf_blue  = dark23[B_BLUE]
R_inf_green = dark23[B_GREEN]
print(f'\nR_inf (2023 scale): blue={R_inf_blue:.4f}  green={R_inf_green:.4f}')

def water_mask(comp):
    return (comp[B_NIR] < 0.15) & (comp[B_BLUE] > 0.01) & ~np.isnan(comp).any(axis=0) & lag

def lyzenga_uv(comp, Rb, Rg):
    wm = water_mask(comp)
    ub = np.full((H, W), np.nan, np.float32)
    ug = np.full((H, W), np.nan, np.float32)
    ub[wm] = np.log(np.maximum(comp[B_BLUE][wm]  - Rb, EPS)).astype(np.float32)
    ug[wm] = np.log(np.maximum(comp[B_GREEN][wm] - Rg, EPS)).astype(np.float32)
    return ub, ug

print('Computing Lyzenga u-variables...')
ub23, ug23 = lyzenga_uv(comp23,     R_inf_blue, R_inf_green)
ub25, ug25 = lyzenga_uv(comp25_elc, R_inf_blue, R_inf_green)  # ELC-corrected 2025

both_valid = np.isfinite(ub23) & np.isfinite(ub25)
sand_mask  = both_valid & (cls23 == SAND_CLASS) & (cls25 == SAND_CLASS)
print(f'  Stable sand pixels: {sand_mask.sum():,}')

# Calibration on 2023 sand pixels
cal_mask = (sand_mask & np.isfinite(z_utm) & (z_utm >= Z_CAL_MIN) & (z_utm <= Z_CAL_MAX))
n_cal = cal_mask.sum()
ub_cal = ub23[cal_mask]; ug_cal = ug23[cal_mask]; z_cal = z_utm[cal_mask]
step   = max(1, n_cal // 3000)
ub_s   = ub_cal[::step]; ug_s = ug_cal[::step]; z_s = z_cal[::step]

X  = np.column_stack([np.ones(len(z_s)), ub_s, ug_s])
coeff, _, _, _ = np.linalg.lstsq(X, z_s, rcond=None)
a0, a1, a2 = coeff
z_pred = X @ coeff
r2_lyz = 1 - np.sum((z_s-z_pred)**2) / np.sum((z_s-z_s.mean())**2)
r_lyz  = float(np.corrcoef(z_s, z_pred)[0, 1])
print(f'\nCalibration: z = {a0:.3f} + {a1:.3f}*ub + {a2:.3f}*ug')
print(f'  r={r_lyz:.3f}  R2={r2_lyz:.3f}  n={len(z_s)}')

depth23 = np.where(both_valid, a0 + a1*ub23 + a2*ug23, np.nan).astype(np.float32)
depth25 = np.where(both_valid, a0 + a1*ub25 + a2*ug25, np.nan).astype(np.float32)
dz_elc  = np.where(sand_mask, depth25 - depth23, np.nan)

dz_sand_elc = dz_elc[sand_mask]
mu_elc  = float(np.nanmean(dz_sand_elc))
sig_elc = float(np.nanstd(dz_sand_elc))
print(f'\nLyzenga Dz (ELC):  mean={mu_elc:+.4f} m  std={sig_elc:.4f} m')

DEPTH_BINS = [(-4.0, -1.5, '>1.5m'), (-1.5, -0.5, '0.5-1.5m'), (-0.5, -0.05, '<0.5m')]
print('  By depth bin:')
for zmin, zmax, label in DEPTH_BINS:
    m = sand_mask & np.isfinite(z_utm) & (z_utm >= zmin) & (z_utm <= zmax)
    if m.sum() < 10: continue
    dz = dz_elc[m]
    print(f'    {label:<12} n={m.sum():>7,}  mean={np.nanmean(dz):>+7.4f}  std={np.nanstd(dz):.4f} m')


# ── 7. Figure ─────────────────────────────────────────────────────────────────

DS = 4
extent = [xs[0], xs[-1], ys[-1], ys[0]]
ax_ext = [LAG_UTM['xmin']-200, LAG_UTM['xmax']+200,
          LAG_UTM['ymin']-200, LAG_UTM['ymax']+200]
def ds(a): return a[::DS, ::DS]

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
axes = axes.ravel()

# ---- Panel A: ELC correction function per band (slope vs band) ----
ax = axes[0]
bnames_short = ['cb','blue','grn_i','green','yel','red','redge','nir']
x_bands = np.arange(8)
ax.bar(x_bands, elc_a, color='#2563eb', alpha=0.75, label='slope a')
ax2 = ax.twinx()
ax2.bar(x_bands + 0.35, elc_b * 1000, color='#dc2626', alpha=0.7, width=0.35,
        label='offset ×1000')
ax.set_xticks(x_bands); ax.set_xticklabels(bnames_short, fontsize=8)
ax.set_ylabel('ELC slope a', fontsize=8); ax2.set_ylabel('ELC offset ×1000', fontsize=8)
ax.axhline(1, color='grey', lw=0.8, ls='--')
ax.set_title('A.  ELC per-band coefficients\n(slope≈1 = mainly additive correction)',
             fontsize=9, fontweight='bold')
lines1, labs1 = ax.get_legend_handles_labels()
lines2, labs2 = ax2.get_legend_handles_labels()
ax.legend(lines1+lines2, labs1+labs2, fontsize=8, loc='upper right')
ax.grid(alpha=0.3)

# ---- Panel B: before vs after ELC — offshore green reflectance ----
ax = axes[1]
g23_off = comp23[B_GREEN][deep]
g25_off = comp25[B_GREEN][deep]
g25e_off = comp25_elc[B_GREEN][deep]
bins = np.linspace(0.0, 0.06, 80)
ax.hist(g23_off, bins=bins, alpha=0.6, density=True, color='#1a9641',
        label=f'2023  p5={dark23[B_GREEN]:.4f}')
ax.hist(g25_off, bins=bins, alpha=0.5, density=True, color='#d62728',
        label=f'2025 raw  p5={dark25[B_GREEN]:.4f}')
ax.hist(g25e_off, bins=bins, alpha=0.5, density=True, color='#2563eb',
        label=f'2025 ELC  p5={deep25_elc_g:.4f}')
ax.set_xlabel('Green reflectance (offshore pixels)', fontsize=9)
ax.set_ylabel('Density', fontsize=9)
ax.set_title('B.  ELC effect: offshore GREEN distribution\n(blue should align with green after correction)',
             fontsize=9, fontweight='bold')
ax.legend(fontsize=8); ax.grid(alpha=0.3)

# ---- Panel C: Lyzenga calibration scatter (ELC) ----
ax = axes[2]
ax.scatter(ub_s, z_s, s=1.5, alpha=0.35, c='#1a7a3e', rasterized=True)
ub_fit = np.linspace(ub_s.min(), ub_s.max(), 50)
ug_med = float(np.median(ug_s))
ax.plot(ub_fit, a0 + a1*ub_fit + a2*ug_med, 'r-', lw=2,
        label=f'r={r_lyz:.3f}  R2={r2_lyz:.3f}')
ax.set_xlabel('u_blue', fontsize=9); ax.set_ylabel('Model depth z (m)', fontsize=9)
ax.set_title(f'C.  Lyzenga calibration on sand (ELC)\nz={a0:.2f}+{a1:.2f}*ub+{a2:.2f}*ug',
             fontsize=9, fontweight='bold')
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.axhline(0, c='k', lw=0.5, ls='--')

# ---- Panel D: Dz map (ELC) ----
fin_dz = dz_sand_elc[np.isfinite(dz_sand_elc)]
dz_sym = float(np.percentile(np.abs(fin_dz), 95)) if len(fin_dz) > 10 else 0.3
dz_sym = max(min(dz_sym, 0.3), 0.01)
sc = axes[3].imshow(ds(np.where(sand_mask, dz_elc, np.nan)),
                    extent=extent, origin='upper', aspect='equal',
                    cmap='RdBu', vmin=-dz_sym, vmax=dz_sym,
                    interpolation='nearest')
plt.colorbar(sc, ax=axes[3], label='Dz (m)', fraction=0.035, pad=0.02, shrink=0.8)
axes[3].set_xlim(ax_ext[:2]); axes[3].set_ylim(ax_ext[2:])
axes[3].set_title(f'D.  Lyzenga Dz sand (ELC-corrected)\nmean={mu_elc:+.4f} m  std={sig_elc:.4f} m',
                  fontsize=9, fontweight='bold')
axes[3].set_xlabel('Easting (m)', fontsize=8); axes[3].set_ylabel('Northing (m)', fontsize=8)

# ---- Panel E: Dz histogram — before/after ELC vs Stumpf ----
ax = axes[4]
# Load original Lyzenga Dz (before ELC) — recompute from pre-ELC script results
ub25_raw, ug25_raw = lyzenga_uv(comp25, R_inf_blue, R_inf_green)  # raw 2025 with 2023 Rinf
dz_raw = np.where(sand_mask,
                  (a0 + a1*ub25_raw + a2*ug25_raw) - depth23, np.nan)
dz_sand_raw = dz_raw[sand_mask]
mu_raw  = float(np.nanmean(dz_sand_raw))
sig_raw = float(np.nanstd(dz_sand_raw))

# Load Stumpf Dz from pre-computed files
STUMPF_D23 = PROC / 'planet_sdb_2023_2025' / 'depth_2023.tif'
STUMPF_D25 = PROC / 'planet_sdb_2023_2025' / 'depth_2025.tif'
with rasterio.open(STUMPF_D23) as src: d23_st = src.read(1).astype(np.float32)
with rasterio.open(STUMPF_D25) as src: d25_st = src.read(1).astype(np.float32)
dz_st_sand = (d25_st - d23_st)[sand_mask]
mu_st  = float(np.nanmean(dz_st_sand)); sig_st = float(np.nanstd(dz_st_sand))

bins = np.linspace(-0.5, 0.5, 81)
fin = lambda a: a[np.isfinite(a)]
ax.hist(fin(dz_sand_raw), bins=bins, alpha=0.45, density=True, color='#d62728',
        label=f'Lyzenga raw   {mu_raw:+.3f}m ±{sig_raw:.3f}')
ax.hist(fin(dz_sand_elc), bins=bins, alpha=0.6, density=True, color='#2563eb',
        label=f'Lyzenga ELC   {mu_elc:+.3f}m ±{sig_elc:.3f}')
ax.hist(fin(dz_st_sand),  bins=bins, alpha=0.45, density=True, color='#f9a825',
        label=f'Stumpf        {mu_st:+.3f}m ±{sig_st:.3f}')
for mu, c in [(mu_raw,'#d62728'), (mu_elc,'#2563eb'), (mu_st,'#f9a825')]:
    ax.axvline(mu, color=c, lw=1.5, ls='--')
ax.axvline(0, color='grey', lw=0.8)
ax.set_xlabel('Dz sand (m)', fontsize=9); ax.set_ylabel('Density', fontsize=9)
ax.set_title('E.  Dz histogram: Lyzenga raw vs ELC vs Stumpf\n(sand pixels)',
             fontsize=9, fontweight='bold')
ax.legend(fontsize=8); ax.grid(alpha=0.3)

print(f'\nSummary:')
print(f'  Lyzenga raw (single R_inf 2023):  mean={mu_raw:+.4f} m  std={sig_raw:.4f} m')
print(f'  Lyzenga ELC:                      mean={mu_elc:+.4f} m  std={sig_elc:.4f} m')
print(f'  Stumpf (unchanged):               mean={mu_st:+.4f} m  std={sig_st:.4f} m')

# ---- Panel F: scatter ELC Dz vs model bathy (spatial sanity check) ----
ax = axes[5]
m = sand_mask & np.isfinite(z_utm) & np.isfinite(dz_elc)
step_f = max(1, m.sum() // 3000)
ax.scatter(z_utm[m][::step_f], dz_elc[m][::step_f],
           s=1.5, alpha=0.35, c='#2563eb', rasterized=True)
ax.axhline(0, c='k', lw=0.8, ls='--'); ax.axvline(0, c='k', lw=0.5, ls=':')
r_dz, p_dz = stats.pearsonr(z_utm[m][::step_f], dz_elc[m][::step_f])
ax.set_xlabel('Model depth z (m)', fontsize=9)
ax.set_ylabel('Lyzenga Dz ELC (m)', fontsize=9)
ax.set_title(f'F.  Dz(ELC) vs depth — depth-dependent bias?\nr={r_dz:.3f}  p={p_dz:.3f}',
             fontsize=9, fontweight='bold')
ax.grid(alpha=0.3)

fig.suptitle(
    'Empirical Line Calibration (ELC) + Lyzenga SDB — Stagnone Aug 2023 vs Aug 2025\n'
    f'ELC anchors: dark=offshore p5 | bright=salt-flat median ({bright_mask.sum():,} px)\n'
    f'After ELC: offshore green p5 aligned {dark25[B_GREEN]:.4f}→{deep25_elc_g:.4f} (target {dark23[B_GREEN]:.4f})',
    fontsize=9
)
fig.tight_layout()
out = FIG / 'sdb_lyzenga_elc.png'
fig.savefig(out, dpi=160, bbox_inches='tight')
plt.close(fig)
print(f'\nFig -> {out}')
print('Done.')
