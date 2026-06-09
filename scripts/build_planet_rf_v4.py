"""
RF v4 seagrass classifier: DII + PCA features only (no raw bands).

Motivation: RF v3 used raw bands (65.8% of importance) which are NOT year-invariant
— the Aug 2025 Planet scenes showed +70-80% shift in red/NIR relative to Aug 2023,
causing reef plateau and sand to be misclassified without per-band normalization.
DII (Lyzenga depth-invariant index) and its PCA are designed to be spectrally stable
across dates when computed with the same k_ij and PCA transform.

Features (8 total vs 16 in v3):
  pca_1..4  : PCA of 2023 DII (fitted on lyzenga_dii_aug2023.tif)
  dii_1..4  : Lyzenga DII, pairs (0,1),(1,2),(1,3),(3,5), k_ij from 2023

Outputs:
  data/processed/planet2023_rf_v4/
    rf_model_v4.joblib
    classified_seagrass_aug2023_v4.tif
    classified_seagrass_aug2025_v4.tif  (no band normalization needed)
    comparison_v4_aug2023_vs_aug2025.png
    comparison_v3_vs_v4_aug2023.png     (in-year quality check)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import json
import rasterio
from rasterio.warp import reproject
from rasterio.enums import Resampling as ResEnum
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings; warnings.filterwarnings('ignore')

ROOT         = Path(__file__).parent.parent
# 2023 inputs
DII23_TIF    = ROOT / 'data/processed/planet2023_rf/lyzenga_dii_aug2023.tif'
PCA23_TIF    = ROOT / 'data/processed/planet2023_rf/pca_dii_aug2023.tif'
KIJ23_JSON   = ROOT / 'data/processed/planet2023_rf/lyzenga_kij_aug2023.json'
CLASS23_V3   = ROOT / 'data/processed/planet2023_rf_v3/classified_seagrass_aug2023_v3.tif'
TRAIN_CSV    = ROOT / 'data/processed/planet2023_rf_v3/training_features_v3.csv'
# 2025 inputs
COMP25_TIF   = ROOT / 'data/processed/planet2025_aug_rf/composite_aug2025.tif'
# outputs
OUT_DIR      = ROOT / 'data/processed/planet2023_rf_v4'
OUT_DIR.mkdir(parents=True, exist_ok=True)
RF_MODEL     = OUT_DIR / 'rf_model_v4.joblib'
CLASS23_V4   = OUT_DIR / 'classified_seagrass_aug2023_v4.tif'
CLASS25_V4   = OUT_DIR / 'classified_seagrass_aug2025_v4.tif'
FIG_2325     = OUT_DIR / 'comparison_v4_aug2023_vs_aug2025.png'
FIG_V3V4     = OUT_DIR / 'comparison_v3_vs_v4_aug2023.png'

DII_PAIRS   = [(0,1),(1,2),(1,3),(3,5)]
N_PCA       = 4
RANDOM_SEED = 42
SCALE       = 1e-4

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


# ── 1. Train RF v4 on DII + PCA features only ────────────────────────────────
def train_rf_v4():
    print('Loading training features...')
    df = pd.read_csv(TRAIN_CSV)
    feat_cols = [c for c in df.columns if c.startswith('pca_') or c.startswith('dii_')]
    df = df.dropna(subset=feat_cols)
    print(f'  {len(df)} samples  |  features ({len(feat_cols)}): {feat_cols}')

    X  = df[feat_cols].values
    le = LabelEncoder()
    y  = le.fit_transform(df['class_id'].values)
    print(f'  Classes: {dict(zip(le.classes_.tolist(), np.bincount(y).tolist()))}')

    rf = RandomForestClassifier(
        n_estimators=500, max_depth=None, min_samples_leaf=2,
        class_weight='balanced', oob_score=True,
        random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X, y)
    print(f'  OOB accuracy: {rf.oob_score_:.3f}')

    cv  = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    cvs = cross_val_score(rf, X, y, cv=cv, scoring='accuracy')
    print(f'  CV-5 accuracy: {cvs.mean():.3f} ± {cvs.std():.3f}')

    imp = pd.Series(rf.feature_importances_, index=feat_cols).sort_values(ascending=False)
    print(f'  Feature importances: {imp.to_dict()}')

    joblib.dump({'rf': rf, 'le': le, 'feature_cols': feat_cols}, RF_MODEL)
    print(f'  Saved: {RF_MODEL.name}')
    return rf, feat_cols, le


# ── 2. Classify a scene given (pca, dii) arrays ──────────────────────────────
def classify_scene(pca, dii, rf, le, H, W, out_tif, ref_tif):
    """pca: (4,H,W)  dii: (4,H,W)  — stack and batch-predict."""
    stack = np.concatenate([pca, dii], axis=0)   # (8, H, W)
    flat  = stack.reshape(8, H * W).T
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

    with rasterio.open(ref_tif) as ds:
        prof = ds.profile.copy()
    prof.update(count=1, dtype='int16', nodata=-9999)
    with rasterio.open(out_tif, 'w', **prof) as dst:
        dst.write(class_map[np.newaxis])
    print(f'  Saved: {out_tif.name}')

    n_valid = valid.sum()
    for cid, info in MALTESE_CLASSES.items():
        n   = (class_map == cid).sum()
        pct = n / n_valid * 100
        print(f'  class {cid} {info["name"]:28s}: {n:8,} px ({pct:4.1f}%)')
    return class_map


# ── 3. Compute 2025 DII and PCA from raw composite ───────────────────────────
def compute_dii_2025(comp25):
    H, W  = comp25.shape[1], comp25.shape[2]
    dii   = np.full((4, H, W), np.nan, dtype=np.float32)
    nir   = comp25[7]; blue = comp25[1]
    valid = (~np.isnan(comp25).any(axis=0) &
             (nir > 0.001) & (nir < 0.15) &
             (blue > 0.010) & (blue < 0.35))
    for idx, (i, j) in enumerate(DII_PAIRS):
        ri, rj = comp25[i], comp25[j]
        ok     = valid & (ri > 0) & (rj > 0)
        lni = np.log(ri, where=ok, out=np.zeros_like(ri))
        lnj = np.log(rj, where=ok, out=np.zeros_like(rj))
        k   = KIJ_2023[(i, j)]
        d   = np.full((H, W), np.nan, dtype=np.float32)
        d[ok] = (lni - k * lnj)[ok]
        dii[idx] = d
    print(f'  2025 DII valid: {(~np.isnan(dii[0])).sum():,}')
    return dii


def apply_pca_2023(dii25, H, W):
    with rasterio.open(DII23_TIF) as ds:
        dii23 = ds.read().astype(np.float32)
    flat23 = dii23.reshape(4, -1).T
    v23    = ~np.isnan(flat23).any(axis=1)
    pca    = PCA(n_components=N_PCA, random_state=RANDOM_SEED)
    pca.fit(flat23[v23])
    flat25 = dii25.reshape(N_PCA, -1).T
    v25    = ~np.isnan(flat25).any(axis=1)
    out    = np.full((H * W, N_PCA), np.nan, dtype=np.float32)
    out[v25] = pca.transform(flat25[v25])
    return out.reshape(H, W, N_PCA).transpose(2, 0, 1)


# ── 4. Comparison figures ─────────────────────────────────────────────────────
def _to_rgb(arr):
    BG  = np.array([0.93, 0.93, 0.93])
    rgb = np.ones((*arr.shape, 3)) * BG
    for cid, info in MALTESE_CLASSES.items():
        c = [int(info['color'][k:k+2], 16)/255 for k in (1,3,5)]
        rgb[arr == cid] = c
    return rgb


def _change_panel(c_ref, c_new, H, W):
    valid = (c_ref >= 0) & (c_new >= 0)
    same  = valid & (c_ref == c_new)
    diff  = valid & (c_ref != c_new)
    rgb   = np.ones((H, W, 3)) * 0.93
    rgb[same] = [0.27, 0.69, 0.31]
    rgb[diff] = [0.85, 0.22, 0.22]
    pct = diff.sum() / valid.sum() * 100 if valid.sum() > 0 else 0
    return rgb, pct


def make_figure(tif_a, tif_b, title_a, title_b, out_fig, suptitle):
    """Generic 3-panel: (a) map A, (b) map B, (c) change A->B."""
    with rasterio.open(tif_a) as ds:
        arr_a = ds.read(1); tf_a = ds.transform; crs_a = ds.crs; H, W = ds.height, ds.width
    with rasterio.open(tif_b) as ds:
        arr_b_src = ds.read(1); tf_b = ds.transform; crs_b = ds.crs

    # reproject B onto A grid for direct comparison
    arr_b = np.full((H, W), -9999, dtype=np.int16)
    reproject(source=arr_b_src, destination=arr_b,
              src_transform=tf_b, src_crs=crs_b,
              dst_transform=tf_a, dst_crs=crs_a,
              resampling=ResEnum.nearest, src_nodata=-9999, dst_nodata=-9999)

    step = 3
    def ds_img(a): return a[::step, ::step]

    chg_rgb, pct_chg = _change_panel(arr_a, arr_b, H, W)
    print(f'  Change {title_a[:8]} -> {title_b[:8]}: {pct_chg:.1f}%')

    fig, axes = plt.subplots(1, 3, figsize=(21, 9))
    axes[0].imshow(ds_img(_to_rgb(arr_a)),   origin='upper', interpolation='nearest')
    axes[0].set_title(f'(a) {title_a}', fontsize=10, pad=6); axes[0].axis('off')
    axes[1].imshow(ds_img(_to_rgb(arr_b)),   origin='upper', interpolation='nearest')
    axes[1].set_title(f'(b) {title_b}', fontsize=10, pad=6); axes[1].axis('off')
    axes[2].imshow(ds_img(chg_rgb),          origin='upper', interpolation='nearest')
    axes[2].set_title(f'(c) Change\n{pct_chg:.1f}% of classified pixels changed',
                      fontsize=10, pad=6); axes[2].axis('off')

    handles = [mpatches.Patch(facecolor=info['color'], edgecolor='#333', lw=0.5,
                              label=f'{cid}: {info["name"]}')
               for cid, info in MALTESE_CLASSES.items()]
    handles += [mpatches.Patch(facecolor='#45b051', edgecolor='#333', lw=0.5, label='No change'),
                mpatches.Patch(facecolor='#d83838', edgecolor='#333', lw=0.5, label='Changed class')]
    fig.legend(handles=handles, loc='lower center', ncol=5, fontsize=8,
               bbox_to_anchor=(0.5, 0.0), framealpha=0.9)
    fig.suptitle(suptitle, fontsize=11, y=1.01)
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    fig.savefig(out_fig, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  Saved: {out_fig.name}')


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print('=== Step 1: Train RF v4 (DII + PCA only) ===')
    rf, feat_cols, le = train_rf_v4()

    print('\n=== Step 2: Classify August 2023 with RF v4 ===')
    with rasterio.open(PCA23_TIF) as ds:
        pca23 = ds.read().astype(np.float32)
        H23, W23 = ds.height, ds.width
    with rasterio.open(DII23_TIF) as ds:
        dii23 = ds.read().astype(np.float32)
    class23_v4 = classify_scene(pca23, dii23, rf, le, H23, W23,
                                out_tif=CLASS23_V4, ref_tif=DII23_TIF)

    print('\n=== Step 3: Compute 2025 DII + PCA (2023 k_ij, 2023 PCA, no normalization) ===')
    with rasterio.open(COMP25_TIF) as ds:
        comp25 = ds.read().astype(np.float32)
        H25, W25 = ds.height, ds.width
    dii25  = compute_dii_2025(comp25)
    pca25  = apply_pca_2023(dii25, H25, W25)

    print('\n=== Step 4: Classify August 2025 with RF v4 (no normalization) ===')
    class25_v4 = classify_scene(pca25, dii25, rf, le, H25, W25,
                                out_tif=CLASS25_V4, ref_tif=COMP25_TIF)

    print('\n=== Step 5: Comparison figures ===')
    make_figure(
        CLASS23_V4, CLASS25_V4,
        title_a='RF v4 — August 2023\nPlanet SuperDove 3m',
        title_b='RF v4 — August 2025 (no band normalization)\nPlanet SuperDove 3m, 09+17 Aug',
        out_fig=FIG_2325,
        suptitle='Seagrass classification — Stagnone di Marsala — RF v4 (DII+PCA only)',
    )
    make_figure(
        CLASS23_V3, CLASS23_V4,
        title_a='RF v3 — August 2023\n(DII + PCA + bands, 16 features)',
        title_b='RF v4 — August 2023\n(DII + PCA only, 8 features)',
        out_fig=FIG_V3V4,
        suptitle='RF v3 vs RF v4 — same scene (Aug 2023) — in-year quality check',
    )

    print('\nDone.')


if __name__ == '__main__':
    main()
