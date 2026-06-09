"""
Classify August 2025 Planet composite using 2023 RF v3 model.

Uses only the Aug 09 + Aug 17 2025 scenes — the closest calendar window to
the Aug 01/16/21/26 2023 training composite. This avoids the seasonal bias
introduced by the Jun-Sep 2025 composite used in classify_planet2025.py.

Key difference vs classify_planet2025.py:
  - Composite built directly from raw 2025 Aug TIFs (not from the nc composite)
  - Same k_ij as 2023 (loaded from lyzenga_kij_aug2023.json)
  - Same PCA fit on 2023 DII
  - Same RF trained on 2023 labels

Outputs (saved to data/processed/planet2025_aug_rf/):
  composite_aug2025.tif               -- Aug-only 2025 median composite
  classified_seagrass_aug2025.tif     -- classified map
  comparison_aug2023_vs_aug2025.png   -- side-by-side vs 2023
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import json
import xarray as xr
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject
from rasterio.enums import Resampling as ResEnum
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA
from sklearn.preprocessing import LabelEncoder
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings; warnings.filterwarnings('ignore')

ROOT        = Path(__file__).parent.parent
PLANET25_DIR = ROOT / 'data/raw/satellite/planet/summer2025/PSScene'
COMP23_TIF  = ROOT / 'data/processed/planet2023_rf/composite_aug2023.tif'
DII23_TIF   = ROOT / 'data/processed/planet2023_rf/lyzenga_dii_aug2023.tif'
KIJ23_JSON  = ROOT / 'data/processed/planet2023_rf/lyzenga_kij_aug2023.json'
CLASS23_TIF = ROOT / 'data/processed/planet2023_rf_v3/classified_seagrass_aug2023_v3.tif'
TRAIN_CSV   = ROOT / 'data/processed/planet2023_rf_v3/training_features_v3.csv'
RF_MODEL    = ROOT / 'data/processed/planet2023_rf_v3/rf_model_v3.joblib'
OUT_DIR      = ROOT / 'data/processed/planet2025_aug_rf'
OUT_DIR.mkdir(parents=True, exist_ok=True)
COMP25_TIF   = OUT_DIR / 'composite_aug2025.tif'
COMP25N_TIF  = OUT_DIR / 'composite_aug2025_norm.tif'   # band-normalized version
CLASS25_TIF  = OUT_DIR / 'classified_seagrass_aug2025.tif'
CLASS25N_TIF = OUT_DIR / 'classified_seagrass_aug2025_norm.tif'
FIG_OUT      = OUT_DIR / 'comparison_aug2023_vs_aug2025.png'
FIG_OUTN     = OUT_DIR / 'comparison_aug2023_vs_aug2025_norm.png'

SCALE       = 1e-4
DII_PAIRS   = [(0,1),(1,2),(1,3),(3,5)]
N_PCA       = 4
RANDOM_SEED = 42
AUG_DATES   = ('20250809', '20250817')   # closest to Aug 2023 composite window

with open(KIJ23_JSON) as f:
    _kij = json.load(f)
KIJ_2023 = {(int(p[0]), int(p[1])): v for p, v in zip(_kij['pairs'], _kij['kij'].values())}

MALTESE_CLASSES = {
    0: {'name': 'Unvegetated',          'color': '#d4c68a'},
    1: {'name': 'Cymodocea nodosa',     'color': '#90d870'},
    2: {'name': 'Cymo+Caulerpa',        'color': '#4ab050'},
    3: {'name': 'Posidonia+Caulerpa',   'color': '#2e7d32'},
    4: {'name': 'Posidonia atolls',     'color': '#1b5e20'},
    5: {'name': 'Posidonia+epiphytes',  'color': '#558b2f'},
    7: {'name': 'Reef plateau',         'color': '#795548'},
}


# ── 1. Build Aug-only 2025 composite (on 2023 reference grid) ───────────────
def build_composite_aug2025():
    """Reproject all Aug 2025 scenes onto the 2023 composite grid so that
    spatial extents match exactly for the comparison figure."""
    if COMP25_TIF.exists():
        print(f'  Composite exists: {COMP25_TIF.name}')
        with rasterio.open(COMP25_TIF) as ds:
            return ds.read().astype(np.float32), ds.profile.copy(), ds.height, ds.width
    print('Building August 2025 composite (on 2023 grid)...')
    sr_files  = sorted(f for f in PLANET25_DIR.glob('*SR_8b_harmonized_clip_file_format.tif')
                       if any(f.name.startswith(d) for d in AUG_DATES))
    udm_files = sorted(f for f in PLANET25_DIR.glob('*udm2_clip_file_format.tif')
                       if any(f.name.startswith(d) for d in AUG_DATES))
    print(f'  {len(sr_files)} SR scenes: {[f.name[:8] for f in sr_files]}')

    # Use 2023 composite as the target grid (CRS, extent, resolution)
    with rasterio.open(COMP23_TIF) as ref:
        ref_crs = ref.crs
        ref_tf  = ref.transform
        H, W    = ref.height, ref.width
        profile = ref.profile.copy()
    print(f'  Target grid (2023): {H}x{W}  X:{ref_tf.c:.0f}  res={ref_tf.a:.1f}m')

    arr = np.full((len(sr_files), 8, H, W), np.nan, dtype=np.float32)
    for i, (sr, udm) in enumerate(zip(sr_files, udm_files)):
        with rasterio.open(sr) as ds:
            src_tf  = ds.transform; src_crs = ds.crs
            data = np.zeros((8, H, W), dtype=np.float32)
            for b in range(1, 9):
                reproject(source=rasterio.band(ds, b), destination=data[b-1],
                          src_transform=src_tf, src_crs=src_crs,
                          dst_transform=ref_tf, dst_crs=ref_crs,
                          resampling=ResEnum.bilinear, dst_nodata=0)
            data *= SCALE
        with rasterio.open(udm) as ds:
            clear = np.zeros((H, W), dtype=np.float32)
            reproject(source=rasterio.band(ds, 1), destination=clear,
                      src_transform=ds.transform, src_crs=ds.crs,
                      dst_transform=ref_tf, dst_crs=ref_crs,
                      resampling=ResEnum.nearest, dst_nodata=0)
            clear = clear.astype(bool)
        data[:, ~clear] = np.nan
        # pixels where all bands are 0 after reproject = outside scene footprint
        data[:, (data == 0).all(axis=0)] = np.nan
        arr[i] = data
        pct = (~np.isnan(data[0])).sum() / (H * W) * 100
        print(f'    {sr.name[:8]}: reprojected  valid={pct:.1f}%')

    composite = np.nanmedian(arr, axis=0)
    valid_pct  = (~np.isnan(composite[0])).sum() / (H * W) * 100
    print(f'  Valid pixels: {valid_pct:.1f}%  shape={H}x{W}')

    prof = profile.copy()
    prof.update(count=8, dtype='float32', nodata=np.nan)
    with rasterio.open(COMP25_TIF, 'w', **prof) as dst:
        dst.write(composite)
    print(f'  Saved: {COMP25_TIF.name}')
    return composite, prof, H, W


# ── 1b. Per-band affine normalization: match 2025 distribution to 2023 ───────
def normalize_bands_to_2023(comp25, H, W):
    """Affine normalization per band: stretch 2025 water-pixel distribution
    to match 2023 mean+std.  Computed on water pixels only (NIR<0.15, blue>0.01).
    Applied to the whole image including non-water; clipped to [0, 1].

    This is a diagnostic test: if it recovers stable classes (reef plateau, sand)
    the raw-band distribution shift is confirmed as the root cause of misclassification.
    """
    with rasterio.open(COMP23_TIF) as ds:
        comp23 = ds.read().astype(np.float32)

    def water_mask(c):
        return (~np.isnan(c).any(axis=0) & (c[7] < 0.15) & (c[1] > 0.01))

    w23 = water_mask(comp23)
    w25 = water_mask(comp25)

    BAND_NAMES = ['coastal_blue','blue','green_i','green','yellow','red','red_edge','nir']
    print(f'  Water pixels: 2023={w23.sum():,}  2025={w25.sum():,}')
    print(f'  {"Band":14s}  {"mean23":>8} {"std23":>7}  {"mean25":>8} {"std25":>7}  {"scale":>7} {"offset":>8}')

    comp25n = comp25.copy()
    for i in range(8):
        m23, s23 = comp23[i][w23].mean(), comp23[i][w23].std()
        m25, s25 = comp25[i][w25].mean(), comp25[i][w25].std()
        # affine: norm = (raw - m25) / s25 * s23 + m23
        scale  = s23 / s25 if s25 > 0 else 1.0
        offset = m23 - scale * m25
        comp25n[i] = np.clip(comp25[i] * scale + offset, 0.0, 1.0)
        # set NaN back where original was NaN
        comp25n[i][np.isnan(comp25[i])] = np.nan
        print(f'  {BAND_NAMES[i]:14s}  {m23:8.4f} {s23:7.4f}  {m25:8.4f} {s25:7.4f}  {scale:7.4f} {offset:+8.4f}')

    # Save normalized composite for inspection
    with rasterio.open(COMP25_TIF) as ref:
        prof = ref.profile.copy()
    with rasterio.open(COMP25N_TIF, 'w', **prof) as dst:
        dst.write(comp25n)
    print(f'  Saved: {COMP25N_TIF.name}')
    return comp25n


# ── 2. Lyzenga DII with 2023 k_ij ───────────────────────────────────────────
def compute_dii(composite):
    H, W  = composite.shape[1], composite.shape[2]
    dii   = np.full((len(DII_PAIRS), H, W), np.nan, dtype=np.float32)
    nir   = composite[7]; blue = composite[1]
    valid = (~np.isnan(composite).any(axis=0) &
             (nir > 0.001) & (nir < 0.15) &
             (blue > 0.010) & (blue < 0.35))
    print(f'  Valid water pixels: {valid.sum():,}')
    print(f'  Using 2023 k_ij: {KIJ_2023}')
    for idx, (i, j) in enumerate(DII_PAIRS):
        ri, rj = composite[i], composite[j]
        ok     = valid & (ri > 0) & (rj > 0)
        lni = np.log(ri, where=ok, out=np.zeros_like(ri))
        lnj = np.log(rj, where=ok, out=np.zeros_like(rj))
        k   = KIJ_2023[(i, j)]
        d   = np.full((H, W), np.nan, dtype=np.float32)
        d[ok] = (lni - k * lnj)[ok]
        dii[idx] = d
    return dii


# ── 3. PCA: fit on 2023 DII, apply to 2025 DII ──────────────────────────────
def apply_pca_2023(dii25, H, W):
    print('Fitting PCA on 2023 DII, applying to Aug 2025...')
    with rasterio.open(DII23_TIF) as ds:
        dii23 = ds.read().astype(np.float32)
    flat23 = dii23.reshape(4, -1).T
    v23    = ~np.isnan(flat23).any(axis=1)
    pca    = PCA(n_components=N_PCA, random_state=RANDOM_SEED)
    pca.fit(flat23[v23])
    print(f'  Variance explained: {pca.explained_variance_ratio_.cumsum()[-1]*100:.1f}%')
    flat25 = dii25.reshape(N_PCA, -1).T
    v25    = ~np.isnan(flat25).any(axis=1)
    out    = np.full((H * W, N_PCA), np.nan, dtype=np.float32)
    out[v25] = pca.transform(flat25[v25])
    return out.reshape(H, W, N_PCA).transpose(2, 0, 1)


# ── 4. Load RF (reuse saved model) ───────────────────────────────────────────
def load_rf():
    bundle = joblib.load(RF_MODEL)
    print(f'  RF loaded: OOB not stored; features={len(bundle["feature_cols"])}')
    return bundle['rf'], bundle['feature_cols'], bundle['le']


# ── 5. Classify ──────────────────────────────────────────────────────────────
def classify(comp25, dii25, pca25, rf, feat_cols, le, H, W, out_tif=None):
    if out_tif is None:
        out_tif = CLASS25_TIF
    stack = np.concatenate([pca25, comp25, dii25], axis=0)   # (16, H, W)
    flat  = stack.reshape(16, H * W).T
    valid = ~np.isnan(flat).any(axis=1)
    print(f'  Valid pixels: {valid.sum():,} / {H*W:,}')

    y_pred    = np.full(H * W, -9999, dtype=np.int16)
    idx_valid = np.where(valid)[0]
    BATCH     = 200_000
    preds     = np.empty(idx_valid.size, dtype=np.int16)
    for start in range(0, idx_valid.size, BATCH):
        end = min(start + BATCH, idx_valid.size)
        preds[start:end] = le.inverse_transform(rf.predict(flat[idx_valid[start:end]]))
        if start % 2_000_000 == 0:
            print(f'    {end/idx_valid.size*100:.0f}%', flush=True)
    y_pred[idx_valid] = preds
    class_map = y_pred.reshape(H, W)

    with rasterio.open(COMP25_TIF) as ref:
        prof = ref.profile.copy()
    prof.update(count=1, dtype='int16', nodata=-9999)
    with rasterio.open(out_tif, 'w', **prof) as dst:
        dst.write(class_map[np.newaxis])
    print(f'  Saved: {out_tif.name}')

    for cid, info in MALTESE_CLASSES.items():
        n   = (class_map == cid).sum()
        pct = n / valid.sum() * 100
        print(f'  class {cid} {info["name"]:28s}: {n:8,} px ({pct:4.1f}%)')
    return class_map


# ── 6. 3-panel comparison figure ─────────────────────────────────────────────
def make_comparison(class_map_25, H25, W25, out_fig=None, label25='August 2025\nPlanet SuperDove 3m, 09+17 Aug'):
    if out_fig is None:
        out_fig = FIG_OUT
    print('Generating comparison figure...')
    with rasterio.open(CLASS23_TIF) as ds:
        c23_src = ds.read(1); tf23 = ds.transform; crs23 = ds.crs
    with rasterio.open(COMP25_TIF) as ds:
        tf25 = ds.transform; crs25 = ds.crs

    c23_on25 = np.full((H25, W25), -9999, dtype=np.int16)
    reproject(source=c23_src, destination=c23_on25,
              src_transform=tf23, src_crs=crs23,
              dst_transform=tf25, dst_crs=crs25,
              resampling=ResEnum.nearest, src_nodata=-9999, dst_nodata=-9999)

    BG = np.array([0.93, 0.93, 0.93])
    def to_rgb(arr):
        rgb = np.ones((*arr.shape, 3)) * BG
        for cid, info in MALTESE_CLASSES.items():
            c = [int(info['color'][k:k+2], 16)/255 for k in (1,3,5)]
            rgb[arr == cid] = c
        return rgb

    rgb23 = to_rgb(c23_on25)
    rgb25 = to_rgb(class_map_25)

    valid   = (c23_on25 >= 0) & (class_map_25 >= 0)
    same    = valid & (c23_on25 == class_map_25)
    diff    = valid & (c23_on25 != class_map_25)
    chg_rgb = np.ones((H25, W25, 3)) * BG
    chg_rgb[same] = [0.27, 0.69, 0.31]
    chg_rgb[diff] = [0.85, 0.22, 0.22]
    pct_chg = diff.sum() / valid.sum() * 100 if valid.sum() > 0 else 0
    print(f'  Change: {pct_chg:.1f}% of valid pixels differ')

    step = 3
    def ds_img(arr): return arr[::step, ::step]

    fig, axes = plt.subplots(1, 3, figsize=(21, 9))
    axes[0].imshow(ds_img(rgb23), origin='upper', interpolation='nearest')
    axes[0].set_title('(a) RF v3 — August 2023\nPlanet SuperDove 3m', fontsize=10, pad=6)
    axes[0].axis('off')

    axes[1].imshow(ds_img(rgb25), origin='upper', interpolation='nearest')
    axes[1].set_title(f'(b) RF v3 (2023 model) — {label25}', fontsize=10, pad=6)
    axes[1].axis('off')

    axes[2].imshow(ds_img(chg_rgb), origin='upper', interpolation='nearest')
    axes[2].set_title(f'(c) Change 2023 → 2025\n{pct_chg:.1f}% of classified pixels changed class',
                      fontsize=10, pad=6)
    axes[2].axis('off')

    handles = [mpatches.Patch(facecolor=info['color'], edgecolor='#333', lw=0.5,
                              label=f'{cid}: {info["name"]}')
               for cid, info in MALTESE_CLASSES.items()]
    handles += [mpatches.Patch(facecolor='#45b051', edgecolor='#333', lw=0.5, label='No change'),
                mpatches.Patch(facecolor='#d83838', edgecolor='#333', lw=0.5, label='Changed class')]
    fig.legend(handles=handles, loc='lower center', ncol=5, fontsize=8,
               bbox_to_anchor=(0.5, 0.0), framealpha=0.9)
    fig.suptitle('Seagrass classification — Stagnone di Marsala — August 2023 vs August 2025 (RF v3)',
                 fontsize=11, y=1.01)
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    fig.savefig(out_fig, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  Saved: {out_fig.name}')


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print('=== Step 1: Build August 2025 composite ===')
    comp25, prof25, H25, W25 = build_composite_aug2025()

    print('\n=== Step 2: Lyzenga DII (2023 k_ij) ===')
    dii25 = compute_dii(comp25)

    print('\n=== Step 3: PCA (fit on 2023, apply to Aug 2025) ===')
    pca25 = apply_pca_2023(dii25, H25, W25)

    print('\n=== Step 4: Load RF v3 ===')
    rf, feat_cols, le = load_rf()

    print('\n=== Step 5a: Classify August 2025 (raw bands, no normalization) ===')
    class_map_raw = classify(comp25, dii25, pca25, rf, feat_cols, le, H25, W25,
                             out_tif=CLASS25_TIF)

    print('\n=== Step 5b: Band normalization (affine match to 2023 distribution) ===')
    comp25n = normalize_bands_to_2023(comp25, H25, W25)
    dii25n  = compute_dii(comp25n)
    pca25n  = apply_pca_2023(dii25n, H25, W25)

    print('\n=== Step 5c: Classify August 2025 (band-normalized) ===')
    class_map_norm = classify(comp25n, dii25n, pca25n, rf, feat_cols, le, H25, W25,
                              out_tif=CLASS25N_TIF)

    print('\n=== Step 6: Comparison figures ===')
    make_comparison(class_map_raw,  H25, W25,
                    out_fig=FIG_OUT,
                    label25='August 2025 — raw bands\nPlanet SuperDove 3m, 09+17 Aug')
    make_comparison(class_map_norm, H25, W25,
                    out_fig=FIG_OUTN,
                    label25='August 2025 — band-normalized to 2023\nPlanet SuperDove 3m, 09+17 Aug')

    print('\nDone.')


if __name__ == '__main__':
    main()
