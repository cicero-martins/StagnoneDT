"""
Planet Aug-2023 composite + Lyzenga DII + PCA + Random Forest classifier
following Maltese et al. 2025 SPIE methodology.

Training data: 45 validation points digitized from Figure 6 of Maltese 2025.
Input imagery: 6 Planet SuperDove 8-band SR scenes, Aug 2023.
Output: classified seagrass map (GeoTIFF) + roughness XYZ for Delft3D FM.

Bands (1-based): coastal_blue(443), blue(490), green_i(531), green(565),
                  yellow(610), red(665), red_edge(705), nir(865)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import rasterio.transform
from rasterio.features import geometry_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.enums import Resampling as ResEnum
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import warnings
warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent
PLANET_DIR = ROOT / 'data/raw/satellite/planet/stagnone2023aug_MalteseValidation_psscene_analytic_8b_sr_udm2'
GEOJSON    = ROOT / 'data/processed/maltese_validation_points_fig6.geojson'
OUT_DIR    = ROOT / 'data/processed/planet2023_rf'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Output files
COMP_TIF     = OUT_DIR / 'composite_aug2023.tif'
DII_TIF      = OUT_DIR / 'lyzenga_dii_aug2023.tif'
PCA_TIF      = OUT_DIR / 'pca_dii_aug2023.tif'
CLASS_TIF    = OUT_DIR / 'classified_seagrass_aug2023.tif'
ROUGH_XYZ    = ROOT / 'data/processed/roughness_satellite_planet2023.xyz'
PLOT_CLASS   = OUT_DIR / 'classified_map_aug2023.png'

SCALE = 1e-4          # Planet SR uint16 ->reflectance
BUFFER_M = 30         # m around each validation point for feature extraction

# Manning roughness lookup (class_id ->n value for FM)
MANNING_MAP = {
    0: 0.020,   # Unvegetated seabed (bare sand)
    1: 0.035,   # Cymodocea nodosa
    2: 0.035,   # Cymodocea + Caulerpa
    4: 0.050,   # Posidonia atolls/banks
    5: 0.050,   # Posidonia with epiphytes
    7: 0.028,   # Reef plateau
}

# Class display names for figures
CLASS_NAMES = {
    0: 'Unvegetated',
    1: 'Cymodocea',
    2: 'Cymodocea+Caulerpa',
    4: 'Posidonia atolls',
    5: 'Posidonia+epiphytes',
    7: 'Reef plateau',
}
CLASS_COLORS = {
    0: '#d4c5a9',   # sandy beige
    1: '#90ee90',   # light green
    2: '#3cb371',   # medium sea green
    4: '#006400',   # dark green
    5: '#228b22',   # forest green
    7: '#8b4513',   # saddle brown
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Build composite
# ─────────────────────────────────────────────────────────────────────────────
def build_composite() -> None:
    """Median composite over clear pixels (UDM2 band 1 = clear flag).

    All scenes are reprojected to match the first scene's grid so shapes align.
    """
    if COMP_TIF.exists():
        print(f'  Composite exists: {COMP_TIF.name}')
        return

    sr_files  = sorted(PLANET_DIR.rglob('*SR_8b_clip.tif'))
    udm_files = sorted(PLANET_DIR.rglob('*udm2_clip.tif'))
    print(f'  Building composite from {len(sr_files)} scenes...')

    # Reference grid: first scene
    with rasterio.open(sr_files[0]) as ref:
        profile     = ref.profile.copy()
        ref_crs     = ref.crs
        ref_tf      = ref.transform
        ref_nodata  = ref.nodata
        H, W        = ref.height, ref.width

    n_scenes = len(sr_files)
    arr = np.full((n_scenes, 8, H, W), np.nan, dtype=np.float32)

    for i, (sr, udm) in enumerate(zip(sr_files, udm_files)):
        with rasterio.open(sr) as ds:
            if ds.height == H and ds.width == W:
                data = ds.read().astype(np.float32) * SCALE
            else:
                # Reproject to reference grid
                data = np.zeros((8, H, W), dtype=np.float32)
                for b in range(1, 9):
                    reproject(
                        source=rasterio.band(ds, b),
                        destination=data[b-1],
                        src_transform=ds.transform,
                        src_crs=ds.crs,
                        dst_transform=ref_tf,
                        dst_crs=ref_crs,
                        resampling=ResEnum.nearest,
                        dst_nodata=0,
                    )
                data = data * SCALE

        with rasterio.open(udm) as ds:
            if ds.height == H and ds.width == W:
                clear = ds.read(1).astype(bool)
            else:
                clear_arr = np.zeros((H, W), dtype=np.float32)
                reproject(
                    source=rasterio.band(ds, 1),
                    destination=clear_arr,
                    src_transform=ds.transform,
                    src_crs=ds.crs,
                    dst_transform=ref_tf,
                    dst_crs=ref_crs,
                    resampling=ResEnum.nearest,
                    dst_nodata=0,
                )
                clear = clear_arr.astype(bool)

        data[:, ~clear] = np.nan
        arr[i] = data
        pct = clear.sum() / (H * W) * 100
        print(f'    {sr.name}: clear={pct:.1f}% ({ds.height}x{ds.width}->{H}x{W})')

    composite = np.nanmedian(arr, axis=0)    # (8, H, W)
    valid_frac = (~np.isnan(composite[0])).sum() / (H * W) * 100
    print(f'  Valid pixels: {valid_frac:.1f}%')

    profile.update(count=8, dtype='float32', nodata=np.nan)
    with rasterio.open(COMP_TIF, 'w', **profile) as dst:
        dst.write(composite)
    print(f'  Saved: {COMP_TIF.name}')


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lyzenga Depth-Invariant Index
# ─────────────────────────────────────────────────────────────────────────────
# Band pairs (0-indexed): (cb,blue), (blue,green_i), (blue,green), (green,red)
# = (0,1), (1,2), (1,3), (3,5)
DII_PAIRS = [(0, 1), (1, 2), (1, 3), (3, 5)]
DII_NAMES = ['DII_cb_blue', 'DII_blue_greeni', 'DII_blue_green', 'DII_green_red']


def compute_dii(composite: np.ndarray) -> np.ndarray:
    """
    Lyzenga DII = ln(Ri) - k_ij * ln(Rj)
    k_ij estimated from 'optically deep' sand-like pixels where
    depth variability drives covariance in log-reflectance.

    Sand calibration mask: low NIR (not vegetation), moderate blue
    (not turbid deep ocean), and above water (not glint/cloud).
    """
    n_dii = len(DII_PAIRS)
    H, W  = composite.shape[1], composite.shape[2]
    dii   = np.full((n_dii, H, W), np.nan, dtype=np.float32)

    # Mask: water pixels with clean signal (not land, not cloud)
    nir   = composite[7]   # band 8 (865 nm)
    blue  = composite[1]   # band 2 (490 nm)
    valid = (~np.isnan(composite).any(axis=0) &
             (nir  > 0.001) & (nir  < 0.15) &   # water, not land/cloud
             (blue > 0.010) & (blue < 0.35))

    # Calibration pixels: shallow-ish, relatively bright blue (sand areas)
    # Use top-30% blue pixels within water mask as sand proxy
    blue_vals = blue[valid]
    thresh    = np.percentile(blue_vals, 70)
    sand_mask = valid & (blue > thresh)
    n_sand    = sand_mask.sum()
    print(f'  Lyzenga calibration pixels: {n_sand}')

    for idx, (i, j) in enumerate(DII_PAIRS):
        ri = composite[i]
        rj = composite[j]
        ok = valid & (ri > 0) & (rj > 0)

        ln_i  = np.log(ri,  where=ok, out=np.zeros_like(ri))
        ln_j  = np.log(rj,  where=ok, out=np.zeros_like(rj))

        # k_ij from sand calibration pixels
        sand  = sand_mask & (ri > 0) & (rj > 0)
        if sand.sum() > 10:
            ln_i_s = ln_i[sand]
            ln_j_s = ln_j[sand]
            k_ij   = np.cov(ln_i_s, ln_j_s)[0, 1] / np.var(ln_j_s)
        else:
            k_ij   = np.sqrt(np.nanvar(ln_i[ok]) / np.nanvar(ln_j[ok]))
            print(f'    Warning: few sand pixels for pair ({i},{j}), using variance ratio')

        print(f'  DII pair ({i},{j}): k={k_ij:.4f}')
        d = np.full((H, W), np.nan, dtype=np.float32)
        d[ok] = (ln_i - k_ij * ln_j)[ok]
        dii[idx] = d

    return dii


def build_dii() -> None:
    if DII_TIF.exists():
        print(f'  DII exists: {DII_TIF.name}')
        return

    with rasterio.open(COMP_TIF) as ds:
        composite = ds.read()
        profile   = ds.profile.copy()

    dii = compute_dii(composite)

    profile.update(count=len(DII_PAIRS), dtype='float32', nodata=np.nan)
    with rasterio.open(DII_TIF, 'w', **profile) as dst:
        dst.write(dii)
    print(f'  Saved: {DII_TIF.name}')


# ─────────────────────────────────────────────────────────────────────────────
# 3. PCA on DII layers (Maltese 2025 §2.2)
# ─────────────────────────────────────────────────────────────────────────────
def build_pca(n_components: int = 4) -> None:
    if PCA_TIF.exists():
        print(f'  PCA exists: {PCA_TIF.name}')
        return

    with rasterio.open(DII_TIF) as ds:
        dii    = ds.read()
        profile = ds.profile.copy()
        H, W   = ds.height, ds.width

    # Valid pixels only
    valid  = ~np.isnan(dii).any(axis=0)   # (H, W)
    X      = dii[:, valid].T               # (n_valid, n_bands)

    pca    = PCA(n_components=n_components, whiten=False)
    X_pca  = pca.fit_transform(X)         # (n_valid, n_components)

    var_exp = pca.explained_variance_ratio_
    print(f'  PCA explained variance: {var_exp}  cumsum={var_exp.cumsum()[-1]:.4f}')

    out = np.full((n_components, H, W), np.nan, dtype=np.float32)
    for k in range(n_components):
        layer      = np.full((H, W), np.nan, dtype=np.float32)
        layer[valid] = X_pca[:, k]
        out[k]     = layer

    profile.update(count=n_components, dtype='float32', nodata=np.nan)
    with rasterio.open(PCA_TIF, 'w', **profile) as dst:
        dst.write(out)
    print(f'  Saved: {PCA_TIF.name}')


# ─────────────────────────────────────────────────────────────────────────────
# 4. Load and clean validation points
# ─────────────────────────────────────────────────────────────────────────────
def load_validation_pts(img_crs: str) -> gpd.GeoDataFrame:
    pts = gpd.read_file(GEOJSON)
    pts = pts.to_crs(img_crs)

    # Fix class_id=6 "Reef plateau" ->class_id=7
    reef_mask = (pts['class_id'] == 6) & (pts['class_name'].str.lower() == 'reef plateau')
    pts.loc[reef_mask, 'class_id'] = 7
    print(f'  Fixed {reef_mask.sum()} reef plateau points: class 6 ->7')

    # Merge class_id=3 (Posidonia+Caulerpa, 1 pt) into class_id=4 (Posidonia atolls)
    pts.loc[pts['class_id'] == 3, 'class_id'] = 4
    print(f'  Merged class 3 ->class 4 (1 pt with insufficient samples)')

    # Merge class_id=6 (Posidonia meadows, ≤2 pts) into class_id=5 (Posidonia+epiphytes)
    meadow_count = (pts['class_id'] == 6).sum()
    if meadow_count > 0:
        pts.loc[pts['class_id'] == 6, 'class_id'] = 5
        print(f'  Merged class 6 ({meadow_count} pts) ->class 5 (Posidonia meadows ->with epiphytes)')

    print(f'\n  Final class distribution:')
    for cid, grp in pts.groupby('class_id'):
        print(f'    class {int(cid)} ({CLASS_NAMES.get(int(cid), "?")}): {len(grp)} pts')

    return pts


# ─────────────────────────────────────────────────────────────────────────────
# 5. Feature extraction with 30 m buffer
# ─────────────────────────────────────────────────────────────────────────────
def extract_features(pts: gpd.GeoDataFrame, img_tif: Path,
                     feature_prefix: str) -> pd.DataFrame:
    """Extract median pixel values within BUFFER_M of each point."""
    with rasterio.open(img_tif) as ds:
        data    = ds.read()           # (n_bands, H, W)
        transform = ds.transform
        crs     = ds.crs
        n_bands = ds.count

    px_res = abs(transform.a)   # pixel size in metres
    buf_px = int(np.ceil(BUFFER_M / px_res))   # buffer in pixels

    records = []
    for _, row in pts.iterrows():
        x, y = row.geometry.x, row.geometry.y
        # Convert coords to pixel indices
        col, row_idx = ~transform * (x, y)
        col, row_idx = int(col), int(row_idx)

        r0 = max(0, row_idx - buf_px)
        r1 = min(data.shape[1], row_idx + buf_px + 1)
        c0 = max(0, col - buf_px)
        c1 = min(data.shape[2], col + buf_px + 1)

        patch = data[:, r0:r1, c0:c1].reshape(n_bands, -1).T  # (n_px, n_bands)
        # Remove NaN pixels
        valid  = ~np.isnan(patch).any(axis=1)
        patch  = patch[valid]

        if len(patch) == 0:
            medians = [np.nan] * n_bands
        else:
            medians = np.nanmedian(patch, axis=0).tolist()

        rec = {f'{feature_prefix}_{k+1}': v for k, v in enumerate(medians)}
        rec['class_id']  = int(row['class_id'])
        rec['fid']       = row.get('fid', row.name)
        records.append(rec)

    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Train RF
# ─────────────────────────────────────────────────────────────────────────────
def train_rf(df: pd.DataFrame) -> tuple[RandomForestClassifier, list[str], LabelEncoder]:
    feature_cols = [c for c in df.columns if c not in ('class_id', 'fid')]
    df_clean     = df.dropna(subset=feature_cols)
    print(f'\n  Training RF: {len(df_clean)} samples, {len(feature_cols)} features')
    print(f'  Dropped {len(df) - len(df_clean)} points with NaN features')

    X  = df_clean[feature_cols].values
    le = LabelEncoder()
    y  = le.fit_transform(df_clean['class_id'].values)
    class_labels = le.classes_

    print(f'  Classes: {dict(zip(class_labels, np.bincount(y)))}')

    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=1,
        class_weight='balanced',
        oob_score=True,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X, y)
    print(f'  OOB accuracy: {rf.oob_score_:.3f}')

    # Cross-validation (stratified k=3, safe for min class size >=3)
    n_min = np.bincount(y).min()
    k_cv  = min(3, n_min)
    if k_cv >= 2:
        cv  = StratifiedKFold(n_splits=k_cv, shuffle=True, random_state=42)
        cv_scores = cross_val_score(rf, X, y, cv=cv, scoring='accuracy')
        print(f'  CV-{k_cv} accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}')
    else:
        print(f'  CV skipped (min class size={n_min})')

    # Feature importance
    imp = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print(f'  Top-5 features:\n{imp.head(5).to_string()}')

    # Classification report
    y_pred = rf.predict(X)
    print(f'\n  In-sample report (OOB is a better unbiased estimate):')
    print(classification_report(y, y_pred,
          target_names=[CLASS_NAMES.get(int(c), str(c)) for c in class_labels]))

    return rf, feature_cols, le


# ─────────────────────────────────────────────────────────────────────────────
# 7. Classify full scene (reads all 3 feature sources: PCA, raw bands, DII)
# ─────────────────────────────────────────────────────────────────────────────
def classify_scene(rf: RandomForestClassifier, feature_cols: list[str],
                   le: LabelEncoder) -> None:
    # Read all three feature sources and stack in same order as training
    sources = [(PCA_TIF, 'pca'), (COMP_TIF, 'band'), (DII_TIF, 'dii')]
    arrays  = []
    profile = None
    H = W   = None

    for tif, prefix in sources:
        with rasterio.open(tif) as ds:
            data = ds.read()   # (n_bands, H, W)
            if profile is None:
                profile = ds.profile.copy()
                H, W    = ds.height, ds.width
        arrays.append(data)

    # Stack: (total_features, H, W), then reshape to (H*W, total_features)
    combined = np.concatenate(arrays, axis=0)
    n_feat   = combined.shape[0]
    flat     = combined.reshape(n_feat, H * W).T   # (H*W, n_feat)
    valid    = ~np.isnan(flat).any(axis=1)

    print(f'  Classifying {valid.sum()} valid pixels out of {H*W}...')

    y_pred   = np.full(H * W, -1, dtype=np.int16)
    y_pred[valid] = le.inverse_transform(rf.predict(flat[valid]))

    class_map = y_pred.reshape(H, W).astype(np.int16)
    class_map[~valid.reshape(H, W)] = -9999

    profile.update(count=1, dtype='int16', nodata=-9999)
    with rasterio.open(CLASS_TIF, 'w', **profile) as dst:
        dst.write(class_map[np.newaxis, ...])
    print(f'  Saved: {CLASS_TIF.name}')

    proba     = np.full(H * W, np.nan, dtype=np.float32)
    proba[valid] = rf.predict_proba(flat[valid]).max(axis=1)
    print(f'  Mean prediction confidence: {np.nanmean(proba):.3f}')


# ─────────────────────────────────────────────────────────────────────────────
# 8. Save roughness XYZ for Delft3D FM
# ─────────────────────────────────────────────────────────────────────────────
def save_roughness_xyz() -> None:
    with rasterio.open(CLASS_TIF) as ds:
        class_map = ds.read(1).astype(np.float32)
        transform = ds.transform
        crs_obj   = ds.crs
        H, W      = ds.height, ds.width
        nodata    = ds.nodata

    # Build x, y, n arrays — only valid (water) cells
    rows, cols = np.where((class_map != nodata) & np.isin(class_map,
                          list(MANNING_MAP.keys())))
    xs   = transform.c + (cols + 0.5) * transform.a
    ys   = transform.f + (rows + 0.5) * transform.e
    cids = class_map[rows, cols].astype(int)
    ns   = np.array([MANNING_MAP.get(c, 0.020) for c in cids], dtype=np.float32)

    # Reproject to WGS84 for FM (which expects lon/lat in roughness.xyz)
    from pyproj import Transformer
    trans = Transformer.from_crs(crs_obj.to_epsg(), 4326, always_xy=True)
    lons, lats = trans.transform(xs, ys)

    df_out = pd.DataFrame({'lon': lons, 'lat': lats, 'manning_n': ns})
    df_out.to_csv(ROUGH_XYZ, sep=' ', index=False, header=False,
                  float_format='%.6f')
    print(f'  Saved roughness XYZ: {ROUGH_XYZ.name}  ({len(df_out)} points)')


# ─────────────────────────────────────────────────────────────────────────────
# 9. Plot classified map
# ─────────────────────────────────────────────────────────────────────────────
def plot_classified() -> None:
    with rasterio.open(CLASS_TIF) as ds:
        class_map = ds.read(1).astype(np.float32)
        transform = ds.transform
        H, W      = ds.height, ds.width
        bounds    = ds.bounds

    class_map[class_map == -9999] = np.nan

    cmap_list = ['white'] + [CLASS_COLORS.get(k, 'grey')
                             for k in sorted(CLASS_NAMES.keys())]
    classes   = sorted(CLASS_NAMES.keys())
    n_cls     = len(classes)

    # Map class IDs to consecutive integers for display
    display = np.full_like(class_map, np.nan)
    for i, cid in enumerate(classes):
        display[class_map == cid] = i + 1

    fig, ax = plt.subplots(figsize=(10, 12))
    extent  = [bounds.left, bounds.right, bounds.bottom, bounds.top]
    im = ax.imshow(display, extent=extent,
                   cmap=mcolors.ListedColormap(cmap_list[:n_cls+1]),
                   vmin=0.5, vmax=n_cls + 0.5,
                   interpolation='nearest', origin='upper')

    from matplotlib.patches import Patch
    legend_els = [Patch(fc=CLASS_COLORS[c], label=f'{c}: {CLASS_NAMES[c]}')
                  for c in classes]
    ax.legend(handles=legend_els, loc='lower right', fontsize=8, framealpha=0.9)
    ax.set_title('Planet Aug-2023 Seagrass Classification\n(Lyzenga DII + PCA + Random Forest)',
                 fontsize=11)
    ax.set_xlabel('Easting (m, UTM 33N)')
    ax.set_ylabel('Northing (m, UTM 33N)')

    fig.tight_layout()
    fig.savefig(PLOT_CLASS, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved plot: {PLOT_CLASS.name}')


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print('=== Step 1: Build composite ===')
    build_composite()

    print('\n=== Step 2: Lyzenga DII ===')
    build_dii()

    print('\n=== Step 3: PCA on DII layers ===')
    build_pca(n_components=4)

    print('\n=== Step 4: Load validation points ===')
    with rasterio.open(COMP_TIF) as ds:
        img_crs = ds.crs.to_string()
    pts = load_validation_pts(img_crs)

    print('\n=== Step 5: Extract features from PCA composite ===')
    df_pca  = extract_features(pts, PCA_TIF,    feature_prefix='pca')
    df_comp = extract_features(pts, COMP_TIF,   feature_prefix='band')
    df_dii  = extract_features(pts, DII_TIF,    feature_prefix='dii')

    # Merge feature tables on fid
    df_all = (df_pca
              .merge(df_comp.drop(columns='class_id'), on='fid')
              .merge(df_dii.drop(columns='class_id'),  on='fid'))
    print(f'\n  Feature matrix: {df_all.shape}')
    df_all.to_csv(OUT_DIR / 'training_features.csv', index=False)

    print('\n=== Step 6: Train RF ===')
    # Use PCA + raw bands as features (Maltese-style: PCA of DII + bands)
    rf, feature_cols, le = train_rf(df_all)

    print('\n=== Step 7: Classify full scene ===')
    classify_scene(rf, feature_cols, le)

    print('\n=== Step 8: Save roughness XYZ ===')
    save_roughness_xyz()

    print('\n=== Step 9: Plot classified map ===')
    plot_classified()

    print('\nDone.')


if __name__ == '__main__':
    main()
