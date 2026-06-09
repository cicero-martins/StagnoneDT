"""
Apply RF v3 seagrass classifier (trained on Aug 2023) to summer 2025 Planet composite.

Workflow:
  1. Load summer 2025 composite (planet_composite_summer2025.nc, uint16 SR)
  2. Compute Lyzenga DII (same pairs as 2023, independent k_ij)
  3. Fit PCA on 2023 DII, apply same transform to 2025 DII (consistent feature space)
  4. Retrain RF on training_features_v3.csv (2023 labels), save to joblib
  5. Classify full 2025 scene -> GeoTIFF
  6. Side-by-side comparison figure (2023 vs 2025)

Outputs:
  data/processed/planet2025_rf/classified_seagrass_summer2025.tif
  data/processed/planet2023_rf_v3/rf_model_v3.joblib
  data/processed/planet2025_rf/comparison_2023_vs_2025.png
"""
from __future__ import annotations
import numpy as np
import pandas as pd
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

ROOT      = Path(__file__).parent.parent
COMP25_NC = ROOT / 'data/processed/planet_composite_summer2025.nc'
DII23_TIF = ROOT / 'data/processed/planet2023_rf/lyzenga_dii_aug2023.tif'
COMP23_TIF= ROOT / 'data/processed/planet2023_rf/composite_aug2023.tif'
KIJ23_JSON= ROOT / 'data/processed/planet2023_rf/lyzenga_kij_aug2023.json'
CLASS23_TIF = ROOT / 'data/processed/planet2023_rf_v3/classified_seagrass_aug2023_v3.tif'
TRAIN_CSV = ROOT / 'data/processed/planet2023_rf_v3/training_features_v3.csv'
OUT_DIR   = ROOT / 'data/processed/planet2025_rf'
OUT_DIR.mkdir(parents=True, exist_ok=True)
CLASS25_TIF  = OUT_DIR / 'classified_seagrass_summer2025.tif'
RF_MODEL_OUT = ROOT / 'data/processed/planet2023_rf_v3/rf_model_v3.joblib'
FIG_OUT      = OUT_DIR / 'comparison_2023_vs_2025.png'

SCALE = 1e-4          # uint16 SR -> reflectance
DII_PAIRS = [(0,1),(1,2),(1,3),(3,5)]   # same as 2023 pipeline
N_PCA     = 4                           # must match training_features_v3.csv
RANDOM_SEED = 42

import json
with open(KIJ23_JSON) as _f:
    _kij_data = json.load(_f)
KIJ_2023 = {(int(p[0]), int(p[1])): v for p, v in zip(_kij_data['pairs'], _kij_data['kij'].values())}
del _f, _kij_data

MALTESE_CLASSES = {
    0: {'name': 'Unvegetated',                     'color': '#d4c68a'},
    1: {'name': 'Cymodocea nodosa',                'color': '#90d870'},
    2: {'name': 'Cymo+Caulerpa',                   'color': '#4ab050'},
    3: {'name': 'Posidonia+Caulerpa',              'color': '#2e7d32'},
    4: {'name': 'Posidonia atolls',                'color': '#1b5e20'},
    5: {'name': 'Posidonia+epiphytes',             'color': '#558b2f'},
    7: {'name': 'Reef plateau',                    'color': '#795548'},
}


# ── 1. Load 2025 composite and convert to reflectance ───────────────────────
def load_composite_2025():
    print('Loading 2025 composite...')
    ds   = xr.open_dataset(COMP25_NC)
    med  = ds['median'].values.astype(np.float32) * SCALE  # (8, y, x)
    y    = ds['y'].values
    x    = ds['x'].values
    crs  = ds.attrs.get('crs_wkt', 'EPSG:32633')
    res  = float(ds.attrs.get('pixel_res_m', 3.0))
    H, W = med.shape[1], med.shape[2]
    # rasterio transform: top-left corner
    tf   = from_origin(x[0] - res/2, y[0] + res/2, res, res)
    profile = dict(driver='GTiff', dtype='float32', nodata=np.nan,
                   count=8, height=H, width=W, crs=crs,
                   transform=tf, compress='lzw')
    print(f'  Shape: {H}x{W}  bands=8  res={res}m')
    nir  = med[7]
    blue = med[1]
    water = (~np.isnan(med).any(axis=0) & (nir < 0.15) & (blue > 0.01))
    print(f'  Valid water pixels: {water.sum():,} / {H*W:,}')
    return med, tf, profile, H, W


# ── 2. Lyzenga DII (2023 k_ij — MUST match training feature space) ──────────
def compute_dii(composite):
    """Compute DII using the SAME k_ij as the 2023 training pipeline.
    Using 2025-recalibrated k_ij would shift the DII feature space relative to
    the RF training data and produce unreliable cross-year predictions."""
    H, W   = composite.shape[1], composite.shape[2]
    n_dii  = len(DII_PAIRS)
    dii    = np.full((n_dii, H, W), np.nan, dtype=np.float32)
    nir    = composite[7]; blue = composite[1]
    valid  = (~np.isnan(composite).any(axis=0) &
              (nir  > 0.001) & (nir  < 0.15) &
              (blue > 0.010) & (blue < 0.35))
    print(f'  Using 2023 k_ij: {KIJ_2023}')
    for idx, (i, j) in enumerate(DII_PAIRS):
        ri, rj = composite[i], composite[j]
        ok  = valid & (ri > 0) & (rj > 0)
        lni = np.log(ri, where=ok, out=np.zeros_like(ri))
        lnj = np.log(rj, where=ok, out=np.zeros_like(rj))
        k   = KIJ_2023[(i, j)]
        print(f'    pair ({i},{j}) k={k:.6f} (2023)')
        d = np.full((H, W), np.nan, dtype=np.float32)
        d[ok] = (lni - k * lnj)[ok]
        dii[idx] = d
    return dii


# ── 3. PCA: fit on 2023 DII, apply to 2025 DII ──────────────────────────────
def build_pca_transform():
    """Fit PCA on 2023 DII (N_PCA components). Returns fitted PCA object."""
    print('Fitting PCA on 2023 DII...')
    with rasterio.open(DII23_TIF) as ds:
        dii23 = ds.read().astype(np.float32)   # (4, H, W)
    flat = dii23.reshape(4, -1).T              # (N, 4)
    valid = ~np.isnan(flat).any(axis=1)
    pca = PCA(n_components=N_PCA, random_state=RANDOM_SEED)
    pca.fit(flat[valid])
    print(f'  Variance explained: {pca.explained_variance_ratio_.cumsum()[-1]*100:.1f}%')
    return pca


def apply_pca(pca, dii, H, W):
    flat  = dii.reshape(N_PCA, -1).T
    valid = ~np.isnan(flat).any(axis=1)
    out   = np.full((H * W, N_PCA), np.nan, dtype=np.float32)
    out[valid] = pca.transform(flat[valid])
    return out.reshape(H, W, N_PCA).transpose(2, 0, 1)   # (N_PCA, H, W)


# ── 4. Train RF on 2023 features, save model ────────────────────────────────
def train_rf():
    print('Training RF v3 on 2023 features...')
    df = pd.read_csv(TRAIN_CSV)
    feat_cols = [c for c in df.columns if c not in ('class_id','x','y')]
    df = df.dropna(subset=feat_cols)
    X  = df[feat_cols].values
    le = LabelEncoder()
    y  = le.fit_transform(df['class_id'].values)
    rf = RandomForestClassifier(n_estimators=500, max_depth=None,
                                min_samples_leaf=2, class_weight='balanced',
                                oob_score=True, random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X, y)
    print(f'  OOB accuracy: {rf.oob_score_:.3f}  classes: {dict(zip(le.classes_.tolist(), np.bincount(y).tolist()))}')
    joblib.dump({'rf': rf, 'le': le, 'feature_cols': feat_cols}, RF_MODEL_OUT)
    print(f'  Model saved: {RF_MODEL_OUT.name}')
    return rf, feat_cols, le


# ── 5. Classify full 2025 scene ─────────────────────────────────────────────
def classify_2025(comp25, dii25, pca25, rf, feat_cols, le, profile, H, W):
    print('Building 2025 feature stack...')
    # Stack: pca (4) + band (8) + dii (4) = 16 features, same order as training CSV
    stack = np.concatenate([
        pca25,                          # (4, H, W)
        comp25,                         # (8, H, W)
        dii25,                          # (4, H, W)
    ], axis=0)                          # (16, H, W)

    flat  = stack.reshape(16, H * W).T  # (N, 16)
    valid = ~np.isnan(flat).any(axis=1)
    print(f'  Valid pixels: {valid.sum():,} / {H*W:,}')

    y_pred   = np.full(H * W, -9999, dtype=np.int16)
    idx_valid = np.where(valid)[0]
    BATCH     = 200_000
    preds     = np.empty(idx_valid.size, dtype=np.int16)
    for start in range(0, idx_valid.size, BATCH):
        end = min(start + BATCH, idx_valid.size)
        preds[start:end] = le.inverse_transform(
            rf.predict(flat[idx_valid[start:end]]))
        if start % 2_000_000 == 0:
            print(f'    {end/idx_valid.size*100:.0f}%', flush=True)
    y_pred[idx_valid] = preds
    class_map = y_pred.reshape(H, W)

    prof = profile.copy()
    prof.update(count=1, dtype='int16', nodata=-9999)
    with rasterio.open(CLASS25_TIF, 'w', **prof) as dst:
        dst.write(class_map[np.newaxis])
    print(f'  Saved: {CLASS25_TIF.name}')

    for cid, info in MALTESE_CLASSES.items():
        n = (class_map == cid).sum()
        pct = n / valid.sum() * 100
        print(f'  class {cid} {info["name"]:30s}: {n:8,} px ({pct:4.1f}%)')
    return class_map


# ── 6. Comparison figure ─────────────────────────────────────────────────────
def make_comparison(class_map_25, H25, W25):
    print('Generating comparison figure...')

    # Load 2023 classification (reproject to 2025 grid for fair comparison)
    with rasterio.open(CLASS23_TIF) as ds:
        c23_src = ds.read(1)
        tf23    = ds.transform
        crs23   = ds.crs

    with rasterio.open(CLASS25_TIF) as ds:
        tf25  = ds.transform
        crs25 = ds.crs

    c23_on25 = np.full((H25, W25), -9999, dtype=np.int16)
    reproject(source=c23_src, destination=c23_on25,
              src_transform=tf23, src_crs=crs23,
              dst_transform=tf25, dst_crs=crs25,
              resampling=ResEnum.nearest,
              src_nodata=-9999, dst_nodata=-9999)

    BG = np.array([0.93, 0.93, 0.93])
    def to_rgb(arr):
        rgb = np.ones((*arr.shape, 3)) * BG
        for cid, info in MALTESE_CLASSES.items():
            c = [int(info['color'][1:3],16)/255,
                 int(info['color'][3:5],16)/255,
                 int(info['color'][5:7],16)/255]
            rgb[arr == cid] = c
        return rgb

    rgb23 = to_rgb(c23_on25)
    rgb25 = to_rgb(class_map_25)

    # Change map: same=green, changed=red, nodata=grey
    valid = (c23_on25 >= 0) & (class_map_25 >= 0)
    same  = valid & (c23_on25 == class_map_25)
    diff  = valid & (c23_on25 != class_map_25)
    change_rgb = np.ones((H25, W25, 3)) * BG
    change_rgb[same] = [0.27, 0.69, 0.31]
    change_rgb[diff] = [0.85, 0.22, 0.22]
    if valid.sum() > 0:
        pct_change = diff.sum() / valid.sum() * 100
    else:
        pct_change = 0.0
    print(f'  Change: {pct_change:.1f}% of valid pixels differ between 2023 and 2025')

    # Subsample for plotting (full 38 Mpix is too large)
    step = 3
    def ds(arr): return arr[::step, ::step]

    fig, axes = plt.subplots(1, 3, figsize=(21, 9))
    axes[0].imshow(ds(rgb23), origin='upper', interpolation='nearest')
    axes[0].set_title('(a) RF v3 — August 2023\nPlanet SuperDove 3m', fontsize=10, pad=6)
    axes[0].axis('off')

    axes[1].imshow(ds(rgb25), origin='upper', interpolation='nearest')
    axes[1].set_title('(b) RF v3 (2023 model) — Summer 2025\nPlanet SuperDove 3m, Jun-Sep', fontsize=10, pad=6)
    axes[1].axis('off')

    axes[2].imshow(ds(change_rgb), origin='upper', interpolation='nearest')
    axes[2].set_title(f'(c) Change 2023 → 2025\n{pct_change:.1f}% of classified pixels changed class', fontsize=10, pad=6)
    axes[2].axis('off')

    handles = [mpatches.Patch(facecolor=info['color'], edgecolor='#333', lw=0.5,
                              label=f'{cid}: {info["name"]}')
               for cid, info in MALTESE_CLASSES.items()]
    handles += [
        mpatches.Patch(facecolor='#45b051', edgecolor='#333', lw=0.5, label='No change'),
        mpatches.Patch(facecolor='#d83838', edgecolor='#333', lw=0.5, label='Changed class'),
    ]
    fig.legend(handles=handles, loc='lower center', ncol=5, fontsize=8,
               bbox_to_anchor=(0.5, 0.0), framealpha=0.9)
    fig.suptitle('Seagrass classification — Stagnone di Marsala — RF v3 model (2023 labels)',
                 fontsize=11, y=1.01)
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    fig.savefig(FIG_OUT, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  Saved: {FIG_OUT.name}')


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print('=== Step 1: Load 2025 composite ===')
    comp25, tf25, prof25, H25, W25 = load_composite_2025()

    print('\n=== Step 2: Lyzenga DII (2025) ===')
    dii25 = compute_dii(comp25)

    print('\n=== Step 3: PCA (fit on 2023, apply to 2025) ===')
    pca = build_pca_transform()
    pca25 = apply_pca(pca, dii25, H25, W25)

    print('\n=== Step 4: Train RF v3 + save model ===')
    rf, feat_cols, le = train_rf()

    print('\n=== Step 5: Classify 2025 ===')
    class_map_25 = classify_2025(comp25, dii25, pca25, rf, feat_cols, le, prof25, H25, W25)

    print('\n=== Step 6: Comparison figure ===')
    make_comparison(class_map_25, H25, W25)

    print('\nDone.')


if __name__ == '__main__':
    main()
