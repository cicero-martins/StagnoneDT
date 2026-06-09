"""
Retrain RF using labels sampled from the segmented Maltese Figure 5 map.

Instead of 45 digitized validation points, we sample ~600 pixels per class
from the ~130k classified pixels in the Figure 5 segmentation (18m resolution).
This gives ~4000 balanced training samples covering the full lagoon.

Key changes vs build_planet2023_maltese_rf.py:
  - Training labels come from Fig5 segmentation (not digitized points)
  - 7 Maltese classes kept distinct (class 3 no longer merged into 4)
  - Spatial stratification: lagoon divided into grid cells, sample spread across them
  - Features extracted at Fig5 pixel centres (no 30m buffer needed — 18m label
    already represents a spatially averaged pixel)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import reproject
from rasterio.enums import Resampling as ResEnum
from pathlib import Path
from scipy.ndimage import binary_erosion
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings; warnings.filterwarnings('ignore')

ROOT      = Path(__file__).parent.parent
FIG5_TIF  = ROOT / 'data/processed/fig5_2023_georef_32633.tif'
COMP_TIF  = ROOT / 'data/processed/planet2023_rf/composite_aug2023.tif'
DII_TIF   = ROOT / 'data/processed/planet2023_rf/lyzenga_dii_aug2023.tif'
PCA_TIF   = ROOT / 'data/processed/planet2023_rf/pca_dii_aug2023.tif'
OUT_DIR   = ROOT / 'data/processed/planet2023_rf_v3'
OUT_DIR.mkdir(parents=True, exist_ok=True)
CLASS_TIF2 = OUT_DIR / 'classified_seagrass_aug2023_v3.tif'
COMP_OUT   = ROOT / 'data/processed/fig5_comparison.png'

N_SAMPLES_PER_CLASS = 600   # default training samples per class
GRID_CELLS          = 8     # default spatial grid size
RANDOM_SEED         = 42

# Per-class overrides — address P+Ep undersampling
N_SAMPLES_OVERRIDE  = {5: 1500}   # class 5 (Posidonia+epiphytes): 2.5x more samples
GRID_CELLS_OVERRIDE = {5: 16}    # finer grid -> samples drawn from patch interiors, not just edges
ERODE_PIXELS        = 2          # default erosion (avoids mixed-cover boundary pixels)
ERODE_PIXELS_OVERRIDE = {}        # all classes use default ERODE_PIXELS=2
# Note: Cymodocea (class 1) erodes to only ~127px (thin strips), area 3.3% vs 5.2% Maltese.
# Accepted: (a) at 3m those strips are sub-resolution mixed pixels anyway;
#           (b) Manning n identical to Cymo+Caulerpa (0.035) so mixing is benign for the model.

# ── Cluster centres + segmentation logic (same as _fig5_comparison.py) ────────
CENTERS = np.array([
    [0.673, 0.849, 0.648],  # C00 -> Reef plateau       -> class 7
    [0.490, 0.489, 0.486],  # C01 -> background
    [0.892, 0.893, 0.891],  # C02 -> background
    [0.864, 0.315, 0.216],  # C03 -> Unvegetated        -> class 0
    [0.695, 0.698, 0.694],  # C04 -> background
    [0.214, 0.214, 0.214],  # C05 -> background
    [0.740, 0.443, 0.333],  # C06 -> Cymodocea          -> class 1
    [0.890, 0.490, 0.315],  # C07 -> Cymo+Caulerpa      -> class 2
    [0.602, 0.605, 0.585],  # C08 -> background
    [0.833, 0.844, 0.646],  # C09 -> Posidonia+epiph.   -> class 5
    [0.514, 0.749, 0.666],  # C10 -> Posidonia atolls   -> class 4
    [0.359, 0.359, 0.359],  # C11 -> background
    [0.839, 0.647, 0.489],  # C12 -> Posidonia+Caulerpa -> class 3
    [0.791, 0.797, 0.792],  # C13 -> background
])
COLORED_IDS        = [0, 3, 6, 7, 9, 10, 12]
SAT_THRESH         = 0.06
CLUSTER_TO_MALTESE = {0:7, 1:-1, 2:-1, 3:0, 4:-1, 5:-1,
                      6:1, 7:2, 8:-1, 9:5, 10:4, 11:-1, 12:3, 13:-1}

MALTESE_CLASSES = {
    0: {'name': 'Unvegetated seabed',                      'color': CENTERS[3]},
    1: {'name': 'Cymodocea nodosa',                        'color': CENTERS[6]},
    2: {'name': 'Cymodocea nodosa + Caulerpa prolifera',   'color': CENTERS[7]},
    3: {'name': 'Posidonia oceanica + Caulerpa prolifera', 'color': CENTERS[12]},
    4: {'name': 'Posidonia oceanica, atolls and banks',    'color': CENTERS[10]},
    5: {'name': 'Posidonia oceanica with epiphytes',       'color': CENTERS[9]},
    7: {'name': 'Reef plateau',                            'color': CENTERS[0]},
}
MALTESE_TO_RF_COARSE = {0:0, 1:1, 2:2, 3:3, 4:4, 5:5, 7:7}

MANNING_MAP = {0:0.020, 1:0.035, 2:0.035, 3:0.050, 4:0.050, 5:0.050, 7:0.028}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Re-segment Figure 5
# ─────────────────────────────────────────────────────────────────────────────
def segment_fig5():
    print('Segmenting Figure 5 (saturation fix)...')
    with rasterio.open(FIG5_TIF) as ds:
        rgb_raw  = ds.read()[:3].astype(np.float32) / 255.0
        alpha    = ds.read(4) if ds.count >= 4 else np.ones((ds.height, ds.width), np.uint8)*255
        fig5_tf  = ds.transform
        fig5_crs = ds.crs
        H5, W5   = ds.height, ds.width

    flat       = rgb_raw.reshape(3, H5*W5).T
    alpha_mask = alpha.ravel() > 10
    mx         = flat.max(axis=1)
    mn         = flat.min(axis=1)
    sat        = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)

    dists_all  = np.sum((flat[:,None,:] - CENTERS[None,:,:]) ** 2, axis=2)
    dists_col  = dists_all[:, COLORED_IDS]
    near_col   = np.array(COLORED_IDS)[np.argmin(dists_col, axis=1)]
    near_all   = np.argmin(dists_all, axis=1)
    km_labels  = np.where(sat > SAT_THRESH, near_col, near_all)

    maltese_vec = np.vectorize(CLUSTER_TO_MALTESE.get)
    class_fig5  = maltese_vec(km_labels, -1).astype(np.int16)
    class_fig5[~alpha_mask] = -1
    class_fig5  = class_fig5.reshape(H5, W5)

    for cid, info in MALTESE_CLASSES.items():
        n = (class_fig5 == cid).sum()
        print('  %-44s %6d px' % (info['name'], n))

    return class_fig5, fig5_tf, fig5_crs, H5, W5


# ─────────────────────────────────────────────────────────────────────────────
# 2. Stratified spatial sampling from Figure 5 labels
# ─────────────────────────────────────────────────────────────────────────────
def stratified_sample(class_fig5, fig5_tf, H5, W5):
    """Sample up to N_SAMPLES pixels per class, spread across a spatial grid.

    Improvements vs v2:
    - Per-class N_SAMPLES and GRID_CELLS overrides (class 5 gets 1500/16x16)
    - Boundary erosion: erode class mask by ERODE_PIXELS before sampling so
      mixed-cover boundary pixels (18m label -> 3m feature mismatch) are excluded.
      Falls back to un-eroded mask if erosion would leave < 20 pixels.
    """
    rng = np.random.default_rng(RANDOM_SEED)
    records = []

    for cid in MALTESE_CLASSES:
        n_samp   = N_SAMPLES_OVERRIDE.get(cid, N_SAMPLES_PER_CLASS)
        n_cells  = GRID_CELLS_OVERRIDE.get(cid, GRID_CELLS)
        n_erode  = ERODE_PIXELS_OVERRIDE.get(cid, ERODE_PIXELS)

        # Build candidate mask with boundary erosion
        raw_mask  = (class_fig5 == cid)
        eroded    = binary_erosion(raw_mask, iterations=n_erode) if n_erode > 0 else raw_mask
        use_mask  = eroded if eroded.sum() >= 20 else raw_mask
        n_eroded  = eroded.sum()
        n_raw     = raw_mask.sum()

        rows_c, cols_c = np.where(use_mask)
        if len(rows_c) == 0:
            continue

        xs = fig5_tf.c + (cols_c + 0.5) * fig5_tf.a
        ys = fig5_tf.f + (rows_c + 0.5) * fig5_tf.e

        x_min, x_max = xs.min(), xs.max()
        y_min, y_max = ys.min(), ys.max()
        gx = np.clip(((xs - x_min) / max(x_max - x_min, 1) * n_cells).astype(int),
                     0, n_cells - 1)
        gy = np.clip(((ys - y_min) / max(y_max - y_min, 1) * n_cells).astype(int),
                     0, n_cells - 1)
        cell_id = gy * n_cells + gx

        cells, _ = np.unique(cell_id, return_counts=True)
        per_cell = max(1, n_samp // len(cells))

        chosen = []
        for c in cells:
            idx_in_cell = np.where(cell_id == c)[0]
            n_take = min(per_cell, len(idx_in_cell))
            chosen.append(rng.choice(idx_in_cell, n_take, replace=False))

        chosen = np.concatenate(chosen)
        if len(chosen) > n_samp:
            chosen = rng.choice(chosen, n_samp, replace=False)

        for i in chosen:
            records.append({'class_id': int(cid), 'x': float(xs[i]), 'y': float(ys[i])})

        erode_note = '' if n_eroded >= 20 else ' (erosion skipped, too few interior px)'
        print('    class %d %-44s %4d pts  [pool: %d eroded / %d raw]%s'
              % (cid, MALTESE_CLASSES[cid]['name'], len(chosen),
                 n_eroded, n_raw, erode_note))

    df = pd.DataFrame(records)
    print(f'  Total: {len(df)} training points')
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. Extract Planet features at sampled locations
# ─────────────────────────────────────────────────────────────────────────────
def extract_at_xy(df, tif_path, prefix):
    with rasterio.open(tif_path) as ds:
        data = ds.read()           # (B, H, W)
        tf   = ds.transform
        H, W = ds.height, ds.width
        n_b  = ds.count

    feats = []
    for _, row in df.iterrows():
        col_f = (row.x - tf.c) / tf.a
        row_f = (row.y - tf.f) / tf.e
        c = int(np.clip(col_f, 0, W - 1))
        r = int(np.clip(row_f, 0, H - 1))
        feats.append(data[:, r, c])

    feat_df = pd.DataFrame(feats, columns=[f'{prefix}_{i+1}' for i in range(n_b)])
    return feat_df


# ─────────────────────────────────────────────────────────────────────────────
# 4. Train RF on 7 classes
# ─────────────────────────────────────────────────────────────────────────────
def train_rf(df_all):
    feature_cols = [c for c in df_all.columns if c not in ('class_id', 'x', 'y')]
    df_clean = df_all.dropna(subset=feature_cols)
    print(f'  {len(df_clean)} samples, {len(feature_cols)} features')

    X  = df_clean[feature_cols].values
    le = LabelEncoder()
    y  = le.fit_transform(df_clean['class_id'].values)
    print('  Classes:', dict(zip(le.classes_.tolist(), np.bincount(y).tolist())))

    rf = RandomForestClassifier(
        n_estimators=500, max_depth=None, min_samples_leaf=2,
        class_weight='balanced', oob_score=True, random_state=RANDOM_SEED, n_jobs=-1)
    rf.fit(X, y)
    print(f'  OOB accuracy: {rf.oob_score_:.3f}')

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    cv_s = cross_val_score(rf, X, y, cv=cv, scoring='accuracy')
    print(f'  CV-5 accuracy: {cv_s.mean():.3f} +/- {cv_s.std():.3f}')

    imp = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print('  Top-5:', ', '.join(f'{k}={v:.3f}' for k, v in imp.head(5).items()))
    return rf, feature_cols, le


# ─────────────────────────────────────────────────────────────────────────────
# 5. Classify full scene
# ─────────────────────────────────────────────────────────────────────────────
def classify_scene(rf, feature_cols, le):
    sources = [(PCA_TIF, 'pca'), (COMP_TIF, 'band'), (DII_TIF, 'dii')]
    arrays, profile = [], None
    H = W = None
    for tif, _ in sources:
        with rasterio.open(tif) as ds:
            arrays.append(ds.read())
            if profile is None:
                profile = ds.profile.copy()
                H, W = ds.height, ds.width

    combined = np.concatenate(arrays, axis=0)
    flat     = combined.reshape(combined.shape[0], H * W).T
    valid    = ~np.isnan(flat).any(axis=1)
    print(f'  Classifying {valid.sum():,} valid pixels...')

    y_pred = np.full(H * W, -1, dtype=np.int16)
    y_pred[valid] = le.inverse_transform(rf.predict(flat[valid]))

    class_map = y_pred.reshape(H, W).astype(np.int16)
    class_map[~valid.reshape(H, W)] = -9999

    profile.update(count=1, dtype='int16', nodata=-9999)
    with rasterio.open(CLASS_TIF2, 'w', **profile) as dst:
        dst.write(class_map[np.newaxis])
    print(f'  Saved: {CLASS_TIF2.name}')
    return class_map, profile


# ─────────────────────────────────────────────────────────────────────────────
# 6. Comparison figure (same layout as _fig5_comparison.py)
# ─────────────────────────────────────────────────────────────────────────────
def make_comparison(class_fig5, fig5_tf, fig5_crs, H5, W5):
    with rasterio.open(CLASS_TIF2) as ds:
        rf_src = ds.read(1)
        rf_tf  = ds.transform
        rf_crs = ds.crs

    rf_on_fig5 = np.full((H5, W5), -1, dtype=np.int16)
    reproject(source=rf_src, destination=rf_on_fig5,
              src_transform=rf_tf, src_crs=rf_crs,
              dst_transform=fig5_tf, dst_crs=fig5_crs,
              resampling=ResEnum.nearest, dst_nodata=-1, src_nodata=-9999)
    rf_on_fig5[class_fig5 == -1] = -1   # mask to Maltese footprint

    valid = (class_fig5 >= 0) & (rf_on_fig5 >= 0)
    y_m   = class_fig5[valid]
    y_r   = rf_on_fig5[valid]
    agree = (y_m == y_r)
    agree_2d    = np.zeros((H5, W5), dtype=bool)
    agree_2d[valid] = agree
    disagree_2d = valid & ~agree_2d
    pct = agree.mean() * 100

    print(f'\n  Pixel agreement: {pct:.1f}%  ({agree.sum():,}/{valid.sum():,})')
    print('\n  Area %% comparison:')
    print('  %-44s %8s %8s' % ('Class', 'Maltese%', 'RF%'))
    n_v = valid.sum()
    cm = confusion_matrix(y_m, y_r, labels=sorted(MALTESE_CLASSES.keys()))
    for i, cid in enumerate(sorted(MALTESE_CLASSES.keys())):
        pm = (y_m == cid).sum() / n_v * 100
        pr = (y_r == cid).sum() / n_v * 100
        acc = cm[i, i] / cm[i].sum() * 100 if cm[i].sum() > 0 else 0
        print('  %-44s %8.1f %8.1f  class_acc=%.0f%%' % (MALTESE_CLASSES[cid]['name'], pm, pr, acc))

    BG = np.array([0.88, 0.88, 0.88])

    def make_rgb(arr, cls_dict):
        rgb = np.ones((*arr.shape, 3)) * BG
        for cid, info in cls_dict.items():
            rgb[arr == cid] = info['color']
        return rgb

    rgb_m     = make_rgb(class_fig5, MALTESE_CLASSES)
    rgb_r     = make_rgb(rf_on_fig5, MALTESE_CLASSES)
    agree_rgb = np.ones((H5, W5, 3)) * BG
    agree_rgb[agree_2d]    = [0.25, 0.70, 0.25]
    agree_rgb[disagree_2d] = [0.82, 0.18, 0.18]

    fig = plt.figure(figsize=(20, 10))
    ax0 = fig.add_axes([0.01,  0.22, 0.305, 0.74])
    ax1 = fig.add_axes([0.345, 0.22, 0.305, 0.74])
    ax2 = fig.add_axes([0.68,  0.22, 0.305, 0.74])

    ax0.imshow(rgb_m, origin='upper', interpolation='nearest')
    ax0.set_title('(a) Maltese et al. (2025), Figure 5\n2023 panel — colour segmentation', fontsize=10, pad=6)
    ax0.axis('off')

    ax1.imshow(rgb_r, origin='upper', interpolation='nearest')
    ax1.set_title('(b) This study — RF v3 classification\nPlanet SuperDove, August 2023', fontsize=10, pad=6)
    ax1.axis('off')

    ax2.imshow(agree_rgb, origin='upper', interpolation='nearest')
    ax2.set_title('(c) Agreement map\n%.1f%% pixel agreement' % pct, fontsize=10, pad=6)
    ax2.axis('off')

    leg_ax = fig.add_axes([0.01, 0.005, 0.98, 0.20])
    leg_ax.axis('off')
    leg_ax.text(0.0, 0.97, 'Seagrass / habitat classes:', fontsize=8, fontweight='bold',
                transform=leg_ax.transAxes, va='top')

    n_cls  = len(MALTESE_CLASSES)
    x_step = 0.98 / n_cls
    sw, sh = 0.10, 0.35
    for i, (cid, info) in enumerate(MALTESE_CLASSES.items()):
        x = i * x_step + 0.01
        rect = mpatches.FancyBboxPatch((x, 0.52), x_step * sw, sh,
                                        boxstyle='round,pad=0.01',
                                        facecolor=info['color'], edgecolor='#444', linewidth=0.7,
                                        transform=leg_ax.transAxes, clip_on=False)
        leg_ax.add_patch(rect)
        leg_ax.text(x + x_step * (sw + 0.02), 0.52 + sh/2, info['name'],
                    ha='left', va='center', fontsize=7.2, transform=leg_ax.transAxes)

    leg_ax.text(0.0, 0.42, 'Agreement map:', fontsize=8, fontweight='bold',
                transform=leg_ax.transAxes, va='top')
    x_step2 = 0.98 / 3
    for i, (color, label) in enumerate([
        ([0.25, 0.70, 0.25], 'Agreement — both maps assign the same class'),
        ([0.82, 0.18, 0.18], 'Disagreement — maps assign different classes'),
        (BG.tolist(),         'Outside classified area'),
    ]):
        x = i * x_step2 + 0.01
        rect = mpatches.FancyBboxPatch((x, 0.05), x_step2 * sw, sh,
                                        boxstyle='round,pad=0.01',
                                        facecolor=color, edgecolor='#444', linewidth=0.7,
                                        transform=leg_ax.transAxes, clip_on=False)
        leg_ax.add_patch(rect)
        leg_ax.text(x + x_step2 * (sw + 0.02), 0.05 + sh/2, label,
                    ha='left', va='center', fontsize=7.2, transform=leg_ax.transAxes)

    fig.suptitle(
        'Comparison: Maltese et al. (2025) vs RF v3 classification '
        '(erode+oversample P+Ep) — Stagnone di Marsala, August 2023',
        fontsize=11, y=0.995)
    fig.savefig(COMP_OUT, dpi=160, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('Saved: %s' % COMP_OUT.name)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print('=== Step 1: Segment Figure 5 ===')
    class_fig5, fig5_tf, fig5_crs, H5, W5 = segment_fig5()

    print('\n=== Step 2: Stratified spatial sampling (v3: erode + per-class overrides) ===')
    df_pts = stratified_sample(class_fig5, fig5_tf, H5, W5)

    print('\n=== Step 3: Extract Planet features ===')
    df_pca  = extract_at_xy(df_pts, PCA_TIF,  'pca')
    df_band = extract_at_xy(df_pts, COMP_TIF, 'band')
    df_dii  = extract_at_xy(df_pts, DII_TIF,  'dii')

    df_all = pd.concat([
        df_pts[['class_id', 'x', 'y']].reset_index(drop=True),
        df_pca.reset_index(drop=True),
        df_band.reset_index(drop=True),
        df_dii.reset_index(drop=True),
    ], axis=1)
    df_all.to_csv(OUT_DIR / 'training_features_v3.csv', index=False)
    print('  Feature matrix:', df_all.shape)

    print('\n=== Step 4: Train RF ===')
    rf, feature_cols, le = train_rf(df_all)

    print('\n=== Step 5: Classify full scene ===')
    class_map, _ = classify_scene(rf, feature_cols, le)

    print('\n=== Step 6: Comparison figure ===')
    make_comparison(class_fig5, fig5_tf, fig5_crs, H5, W5)

    print('\nDone.')


if __name__ == '__main__':
    main()
