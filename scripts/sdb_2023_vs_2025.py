"""SDB (Satellite-Derived Bathymetry) comparison: August 2023 vs August 2025.

Stumpf (2003) log-ratio method:
    I = ln(1000 * B_blue) / ln(1000 * B_green)      [B2=blue, B4=green]

Calibrated against model topobathy (topobathy_combined.nc, WGS84 → UTM 33N).
Harmonization correction: 2023 native SuperDove → harmonized scale via
per-band RC_2025/RC_2023 factor = 0.9101 (uniform, derived from all 2023/2025 XMLs).

Outputs:
    data/processed/planet_sdb_2023_2025/sdb_index_2023.tif
    data/processed/planet_sdb_2023_2025/sdb_index_2025.tif
    data/processed/planet_sdb_2023_2025/depth_2023.tif
    data/processed/planet_sdb_2023_2025/depth_2025.tif
    data/processed/planet_sdb_2023_2025/delta_z.tif
    figures/sdb_2023_vs_2025.png
"""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
import xarray as xr
from pyproj import Transformer
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
PROC = Path('c:/Users/Unipa/Documents/StagnoneDT/data/processed')
FIG  = ROOT / 'figures'

COMP23 = PROC / 'planet2023_rf' / 'composite_aug2023.tif'
COMP25 = PROC / 'planet2025_aug_rf' / 'composite_aug2025.tif'
CLASS23 = PROC / 'planet2023_rf_v3' / 'classified_seagrass_aug2023_v3.tif'
BATHY_NC = PROC / 'mesh_v05' / 'topobathy_combined.nc'

OUT_DIR = PROC / 'planet_sdb_2023_2025'
OUT_DIR.mkdir(exist_ok=True)

# Band indices in the 8-band composite (0-based)
B_BLUE  = 1   # B2 blue  490 nm
B_GREEN = 3   # B4 green 565 nm
B_NIR   = 7   # B8 NIR   865 nm

# Harmonization factor: RC_2025 / RC_2023 averaged over all scenes and bands
HARM_FACTOR = 0.9101  # multiply 2023 values by this to reach harmonized scale

# Depth calibration range: only use cells within [ZMIN, ZMAX] from model
Z_CAL_MIN = -4.0   # avoid offshore deep cells where SDB is less reliable
Z_CAL_MAX = -0.3   # avoid intertidal / exposed cells

# Stumpf normalisation constant (1000 maps DN*1e-4 values from ~0.01->10, keeping ln positive)
NORM = 1000.0

# Lagoon spatial filter (EPSG:32633 approximate)
LAG_UTM = dict(xmin=270700, xmax=281000, ymin=4190000, ymax=4203000)


# ── helpers ────────────────────────────────────────────────────────────────────

def load_composite(path):
    with rasterio.open(path) as src:
        data   = src.read().astype(np.float32)   # (8, H, W)
        nodata = src.nodata
        profile = src.profile.copy()
    if nodata is not None:
        data[data == nodata] = np.nan
    return data, profile


def water_mask(comp):
    """True where pixel is open water: NIR small, blue present, no NaN."""
    return (
        np.isfinite(comp[B_NIR]) &
        (comp[B_NIR]  < 0.15) &
        (comp[B_BLUE] > 0.010) &
        np.isfinite(comp[B_BLUE]) &
        np.isfinite(comp[B_GREEN]) &
        (comp[B_GREEN] > 0.005)
    )


def stumpf_index(comp):
    """Log-ratio depth index: ln(1000*blue) / ln(1000*green). NaN for non-water."""
    wm = water_mask(comp)
    I  = np.full(comp.shape[1:], np.nan, dtype=np.float32)
    b  = comp[B_BLUE][wm];  g = comp[B_GREEN][wm]
    ln_b = np.log(NORM * b);  ln_g = np.log(NORM * g)
    I[wm] = (ln_b / ln_g).astype(np.float32)
    return I


def load_bathy_reprojected(profile):
    """Reproject topobathy (WGS84 lat/lon) onto the composite raster grid."""
    ds  = xr.open_dataset(BATHY_NC)
    lat = ds.lat.values;   lon = ds.lon.values
    z   = ds['topobathy'].values.astype(np.float32)   # (lat, lon), sign: land>0, sea<0
    ds.close()

    H, W     = profile['height'], profile['width']
    dst_crs  = profile['crs']
    dst_tf   = profile['transform']

    # Source transform: uniform lat/lon grid
    dlat = float(lat[1] - lat[0]);  dlon = float(lon[1] - lon[0])
    src_tf = rasterio.transform.from_origin(
        west=float(lon[0]) - abs(dlon) / 2,
        north=float(lat[-1]) + abs(dlat) / 2,
        xsize=abs(dlon), ysize=abs(dlat)
    )
    z_flip = z[::-1]  # rasterio origin top-left, lat increases upward → flip

    z_utm = np.full((H, W), np.nan, dtype=np.float32)
    reproject(
        source=z_flip, destination=z_utm,
        src_transform=src_tf, src_crs='EPSG:4326',
        dst_transform=dst_tf, dst_crs=dst_crs,
        src_nodata=np.nan, dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    print(f'  Reprojected bathy: valid={np.isfinite(z_utm).sum()}  '
          f'range=[{np.nanmin(z_utm):.2f},{np.nanmax(z_utm):.2f}] m')
    return z_utm


def lagoon_mask(profile):
    """Boolean mask for lagoon extent in the raster grid (via bounding box)."""
    H, W = profile['height'], profile['width']
    tf   = profile['transform']
    xs   = tf.c + (np.arange(W) + 0.5) * tf.a
    ys   = tf.f + (np.arange(H) + 0.5) * tf.e
    xg, yg = np.meshgrid(xs, ys)
    return (
        (xg >= LAG_UTM['xmin']) & (xg <= LAG_UTM['xmax']) &
        (yg >= LAG_UTM['ymin']) & (yg <= LAG_UTM['ymax'])
    )


def save_tif(arr, profile, path):
    prof = profile.copy()
    prof.update(count=1, dtype='float32', nodata=np.nan)
    with rasterio.open(path, 'w', **prof) as dst:
        dst.write(arr[np.newaxis].astype(np.float32))


# ── main ───────────────────────────────────────────────────────────────────────

print('Loading composites...')
comp23, prof = load_composite(COMP23)
comp25, _    = load_composite(COMP25)
H, W = comp23.shape[1], comp23.shape[2]
print(f'  Grid: {H}x{W}  CRS={prof["crs"]}')

# Apply harmonization correction to 2023: scale to harmonized space
# so both years are on the same radiometric baseline.
print(f'Applying harmonization correction to 2023 (x{HARM_FACTOR:.4f})...')
comp23 = comp23 * HARM_FACTOR

print('Computing Stumpf index...')
I23 = stumpf_index(comp23)
I25 = stumpf_index(comp25)
print(f'  I_2023 valid={np.isfinite(I23).sum():,}  '
      f'range=[{np.nanmin(I23):.4f},{np.nanmax(I23):.4f}]')
print(f'  I_2025 valid={np.isfinite(I25).sum():,}  '
      f'range=[{np.nanmin(I25):.4f},{np.nanmax(I25):.4f}]')

print('Loading bathymetry...')
z_bathy = load_bathy_reprojected(prof)

lag = lagoon_mask(prof)
wm23 = water_mask(comp23)
wm25 = water_mask(comp25)

# Calibration mask: lagoon water pixels, known depth in calibration range
both_water = wm23 & wm25 & lag
cal_mask = (
    both_water &
    np.isfinite(z_bathy) &
    (z_bathy >= Z_CAL_MIN) & (z_bathy <= Z_CAL_MAX)
)
n_cal = cal_mask.sum()
print(f'Calibration pixels (both water, {Z_CAL_MIN}<z<{Z_CAL_MAX}): {n_cal:,}')

if n_cal < 100:
    raise RuntimeError('Too few calibration pixels — check bathymetry reprojection')

# Sample calibration data: I_2023 vs z_model (2023 is closer in time to 2020 survey)
I23_cal = I23[cal_mask]
z_cal   = z_bathy[cal_mask]

# Thin calibration points to avoid spatial autocorrelation (every 30th pixel)
step = max(1, n_cal // 3000)
I23_s = I23_cal[::step];  z_s = z_cal[::step]
print(f'  Calibration subsample: {len(I23_s)} points  (1 of every {step})')

slope, intercept, r, p, se = stats.linregress(I23_s, z_s)
print(f'  Linear fit z = {slope:.3f} * I + {intercept:.3f}   r={r:.3f}  r2={r**2:.3f}')

# Apply calibration to both years (same coefficients → change is radiometric)
depth23 = slope * I23 + intercept
depth25 = slope * I25 + intercept

# Restrict to common water + lagoon area
mask_show = both_water & lag & np.isfinite(depth23) & np.isfinite(depth25)
depth23[~mask_show] = np.nan
depth25[~mask_show] = np.nan

delta_z = depth25 - depth23   # positive = shallower (deposition), negative = deeper (erosion)
delta_z[~mask_show] = np.nan

# Statistics by seagrass class
print('\nDelta_z statistics by seagrass class (mean +/- std, m):')
with rasterio.open(CLASS23) as src:
    cls23 = src.read(1)
RF_TO_NAME = {0:'unvegetated', 1:'Cymodocea', 2:'Cymodocea+Caulerpa',
              3:'Posidonia+Caulerpa', 4:'Posidonia_atolls', 5:'Posidonia+epiphytes', 7:'reef'}
for rf_id, name in RF_TO_NAME.items():
    m = mask_show & (cls23 == rf_id)
    if m.sum() < 10:
        continue
    d = delta_z[m]
    print(f'  {name:<22}: n={m.sum():6,}  mean={np.nanmean(d):+.3f}  '
          f'std={np.nanstd(d):.3f}  p10={np.nanpercentile(d,10):+.3f}  '
          f'p90={np.nanpercentile(d,90):+.3f} m')

# Lagoon-wide stats (excluding obvious outliers > 3sigma)
dz_valid = delta_z[mask_show]
mu  = np.nanmean(dz_valid)
sig = np.nanstd(dz_valid)
inlier = np.abs(dz_valid - mu) < 3 * sig
print(f'\nLagoon delta_z: mean={mu:+.3f} m  std={sig:.3f} m  '
      f'n_inlier={inlier.sum():,}  range=[{dz_valid.min():.2f},{dz_valid.max():.2f}] m')

# Save GeoTIFFs
print('\nSaving GeoTIFFs...')
save_tif(I23,      prof, OUT_DIR / 'sdb_index_2023.tif')
save_tif(I25,      prof, OUT_DIR / 'sdb_index_2025.tif')
save_tif(depth23,  prof, OUT_DIR / 'depth_2023.tif')
save_tif(depth25,  prof, OUT_DIR / 'depth_2025.tif')
save_tif(delta_z,  prof, OUT_DIR / 'delta_z.tif')

# ── Figure ─────────────────────────────────────────────────────────────────────
print('Generating figure...')

# Downsample for plotting (every 4th pixel = 12m res)
DS = 4
def ds(arr): return arr[::DS, ::DS]

# Raster coordinates for imshow extent
tf  = prof['transform']
xs  = tf.c + np.arange(W) * tf.a
ys  = tf.f + np.arange(H) * tf.e   # decreasing (top-left origin)
extent = [xs[0], xs[-1], ys[-1], ys[0]]  # [left, right, bottom, top]

# Lagoon-only extent for axis limits (UTM metres)
xpad, ypad = 200, 200
ax_ext = [LAG_UTM['xmin'] - xpad, LAG_UTM['xmax'] + xpad,
          LAG_UTM['ymin'] - ypad, LAG_UTM['ymax'] + ypad]

# Color scales
I_vmin = float(np.nanpercentile(I23[mask_show & lag], 2))
I_vmax = float(np.nanpercentile(I23[mask_show & lag], 98))
dz_sym = float(np.nanpercentile(np.abs(dz_valid[inlier]), 95))

fig, axes = plt.subplots(1, 4, figsize=(22, 8))

# Panel A: SDB index 2023
sc = axes[0].imshow(ds(I23), extent=extent, origin='upper', aspect='equal',
                    cmap='viridis_r', vmin=I_vmin, vmax=I_vmax,
                    interpolation='nearest')
plt.colorbar(sc, ax=axes[0], label='Stumpf index I', fraction=0.035, pad=0.02, shrink=0.8)
axes[0].set_xlim(ax_ext[:2]);  axes[0].set_ylim(ax_ext[2:])
axes[0].set_title('A.  SDB index — August 2023\nStumpf ln(Blue)/ln(Green)', fontsize=9, fontweight='bold')

# Panel B: SDB index 2025
sc2 = axes[1].imshow(ds(I25), extent=extent, origin='upper', aspect='equal',
                     cmap='viridis_r', vmin=I_vmin, vmax=I_vmax,
                     interpolation='nearest')
plt.colorbar(sc2, ax=axes[1], label='Stumpf index I', fraction=0.035, pad=0.02, shrink=0.8)
axes[1].set_xlim(ax_ext[:2]);  axes[1].set_ylim(ax_ext[2:])
axes[1].set_title('B.  SDB index — August 2025\n(harmonized, Aug 09 + 17)', fontsize=9, fontweight='bold')

# Panel C: Δz = depth_2025 - depth_2023
norm_dz = TwoSlopeNorm(vmin=-dz_sym, vcenter=0, vmax=dz_sym)
sc3 = axes[2].imshow(ds(delta_z), extent=extent, origin='upper', aspect='equal',
                     cmap='RdBu', norm=norm_dz,
                     interpolation='nearest')
cb3 = plt.colorbar(sc3, ax=axes[2], label='Δz (m, + = shallower)',
                   fraction=0.035, pad=0.02, shrink=0.8)
axes[2].set_xlim(ax_ext[:2]);  axes[2].set_ylim(ax_ext[2:])
axes[2].set_title(f'C.  Δz = SDB_2025 − SDB_2023\n'
                  f'mean={mu:+.3f} m  std={sig:.3f} m  (18-month proxy)',
                  fontsize=9, fontweight='bold')
axes[2].text(0.02, 0.02, f'n={inlier.sum():,} pixels\n± = shallowing/deepening',
             transform=axes[2].transAxes, fontsize=7, va='bottom',
             bbox=dict(fc='white', alpha=0.8, pad=2))

# Panel D: calibration scatter I_2023 vs z_model
axes[3].scatter(I23_s, z_s, s=1, alpha=0.3, color='#2563eb', rasterized=True)
xfit = np.array([I23_s.min(), I23_s.max()])
axes[3].plot(xfit, slope * xfit + intercept, 'r-', lw=2,
             label=f'z = {slope:.2f}·I + {intercept:.2f}\nr={r:.3f}  R²={r**2:.2f}')
axes[3].set_xlabel('Stumpf index I (2023)', fontsize=9)
axes[3].set_ylabel('Model depth z (m)', fontsize=9)
axes[3].set_title(f'D.  Calibration: I_2023 vs topobathy\n'
                  f'({len(I23_s):,} pts, z ∈ [{Z_CAL_MIN},{Z_CAL_MAX}] m)',
                  fontsize=9, fontweight='bold')
axes[3].legend(fontsize=8)
axes[3].grid(alpha=0.3)
axes[3].axhline(0, color='k', lw=0.5, ls='--')

for ax in axes[:3]:
    ax.set_xlabel('Easting (m)', fontsize=8)
    ax.set_ylabel('Northing (m)', fontsize=8)
    ax.tick_params(labelsize=7)

fig.suptitle(
    'Satellite-Derived Bathymetry comparison — Stagnone di Marsala\n'
    'Planet SuperDove 3m  |  August 2023 (native SR) vs August 2025 (harmonized SR)\n'
    'Harmonization correction applied: RC_2025/RC_2023 = 0.9101 (uniform, 8 bands)',
    fontsize=10
)
fig.tight_layout()
out_fig = FIG / 'sdb_2023_vs_2025.png'
fig.savefig(out_fig, dpi=160, bbox_inches='tight')
plt.close(fig)
print(f'\nFig -> {out_fig}')
print('Done.')
