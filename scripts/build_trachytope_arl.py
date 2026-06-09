"""
Build Delft3D FM trachytope .arl file from RF v3 seagrass classification.

ARL format (FM Manual C.7.1):
  # comment lines (# or *)
  xu  yu  zu  TrachytopeNr  Fraction
  xu  yu  zu  TrachytopeNr  Fraction   <- same coords = second class for same link
  ...

No header/count line. One row per (link, class) pair. Multiple trachytope
classes for the same link = consecutive lines with the same xu,yu,zu. FM sums
fractions; remaining (1-sum) uses the MDU unifFrictCoef background roughness.

TTD class mapping (trachytopes.ttd, FM 2026 formula numbers):
  0  formula 53  n=0.020  -> bare sand / unvegetated
  1  formula 153           -> Cymodocea Baptist (h_v=0.15m, mD=3.2, CD=1.0, Cb=45)
  2  formula 153           -> Posidonia Baptist (h_v=0.50m, mD=5.0, CD=0.80, Cb=45)
  3  formula 53  n=0.028  -> rock / reef plateau

RF v3 class -> trachytope class:
  0 (Unvegetated)          -> 0
  1 (Cymodocea)            -> 1
  2 (Cymo+Caulerpa)        -> 1
  3 (Posidonia+Caulerpa)   -> 2
  4 (Posidonia atolls)     -> 2
  5 (Posidonia+epiphytes)  -> 2
  7 (Reef plateau)         -> 3
  nodata (-9999)           -> skip (link gets no entry; FM uses unifFrictCoef)
"""
from __future__ import annotations
import numpy as np
import xarray as xr
import rasterio
from pathlib import Path
from pyproj import Transformer
import warnings; warnings.filterwarnings('ignore')

ROOT       = Path(__file__).parent.parent
NET_NC     = ROOT / 'model/dflowfm_v04AE/Stagnone_dxy01_15m_net.nc'
CLASS_TIF  = ROOT / 'data/processed/planet2023_rf_v3/classified_seagrass_aug2023_v3.tif'
ARL_OUT    = ROOT / 'data/processed/planet2023_rf_v3/stagnone_trachytopes_v3.arl'

RADIUS     = 20        # m -- search radius around each edge midpoint
N_TRACHYTOPE = 4       # classes 1-4 in trachytopes.ttd (FM reserves class 0)
TRAC_OFFSET = 1        # classes start at 1, not 0

# RF class -> trachytope class (-1 = skip / nodata)
# FM reserves class 0 as "no trachytope / background" — user classes start at 1
# 1=sand(f53), 2=Cymodocea(f153), 3=Posidonia(f153), 4=rock(f53)
RF_TO_TRAC = {0: 1, 1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 7: 4}

# -- 1. Load mesh edges -------------------------------------------------------
print('Loading mesh...')
ds_net = xr.open_dataset(NET_NC)
edge_x = ds_net['mesh2d_edge_x'].values   # WGS84 lon
edge_y = ds_net['mesh2d_edge_y'].values   # WGS84 lat
N_edges = len(edge_x)
print(f'  {N_edges:,} flow links')

# Convert WGS84 lon/lat -> UTM33N (same CRS as the classified TIF)
xfm = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
edge_x_utm, edge_y_utm = xfm.transform(edge_x, edge_y)
print(f'  UTM33N: X={edge_x_utm.min():.0f}-{edge_x_utm.max():.0f}  '
      f'Y={edge_y_utm.min():.0f}-{edge_y_utm.max():.0f}')

# -- 2. Load classified TIF ---------------------------------------------------
print('Loading classified TIF...')
with rasterio.open(CLASS_TIF) as ds_r:
    class_map = ds_r.read(1).astype(np.int16)
    tf        = ds_r.transform
    H, W      = ds_r.height, ds_r.width
    bounds    = ds_r.bounds
    pix_res   = ds_r.res[0]   # 3.0 m
print(f'  {H}x{W}  res={pix_res}m  '
      f'X={bounds.left:.0f}-{bounds.right:.0f}  Y={bounds.bottom:.0f}-{bounds.top:.0f}')

# Map RF classes -> trachytope classes in-place
trac_map = np.full_like(class_map, -1, dtype=np.int8)
for rf_c, tr_c in RF_TO_TRAC.items():
    trac_map[class_map == rf_c] = tr_c

# -- 3. Build circular offset kernel -----------------------------------------
r_pix = int(np.ceil(RADIUS / pix_res))
dr = np.arange(-r_pix, r_pix + 1)
DC, DR = np.meshgrid(dr, dr)
in_circle = (DR**2 + DC**2) <= r_pix**2
DR_c = DR[in_circle].ravel()
DC_c = DC[in_circle].ravel()
print(f'\nKernel: {RADIUS}m = {r_pix}px  ->  {len(DR_c)} px/link')

# -- 4. Edge pixel coordinates ------------------------------------------------
col_c = ((edge_x_utm - tf.c) / tf.a).astype(int)
row_c = ((edge_y_utm - tf.f) / tf.e).astype(int)   # tf.e < 0

margin = r_pix + 1
in_tif = ((col_c >= margin) & (col_c < W - margin) &
          (row_c >= margin) & (row_c < H - margin))
print(f'  {in_tif.sum():,} / {N_edges:,} links within TIF extent')

# -- 5. Sample + write .arl ---------------------------------------------------
# Format per FM Manual C.7.1: "xu  yu  zu  TrachytopeNr  Fraction"
# Multiple classes for same link = consecutive lines with identical xu,yu,zu.
# NO header/count line.
print('Building .arl...')

n_assigned   = 0
n_skipped    = 0
class_hist   = np.zeros(N_TRACHYTOPE, dtype=np.int64)

lines = [
    '# Trachytope area roughness link file - Stagnone DT',
    '# RF v3 seagrass classification, Planet SuperDove Aug 2023',
    '# build_trachytope_arl.py  --  FM Manual C.7.1 coordinate format',
    f'# Search radius: {RADIUS} m  |  Pixel res: {pix_res} m',
    '# TTD: 1=sand(n53,0.020), 2=Cymodocea(f153), 3=Posidonia(f153), 4=rock(n53,0.028)',
    '# FM class 0 is reserved for background roughness (unifFrictCoef)',
    '# xu  yu  zu  TrachytopeNr  Fraction',
]

for i in range(N_edges):
    if not in_tif[i]:
        continue

    rows = row_c[i] + DR_c
    cols = col_c[i] + DC_c
    valid = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    tc = trac_map[rows[valid], cols[valid]]

    classified = tc[tc >= 0]
    if len(classified) == 0:
        n_skipped += 1
        continue

    counts = np.bincount(classified, minlength=N_TRACHYTOPE + TRAC_OFFSET).astype(float)
    total  = counts.sum()
    fracs  = counts / total

    xu = edge_x_utm[i]
    yu = edge_y_utm[i]

    wrote_any = False
    for cls in range(TRAC_OFFSET, N_TRACHYTOPE + TRAC_OFFSET):   # 1..4
        if fracs[cls] > 0:
            lines.append(f'{xu:.3f}  {yu:.3f}  0  {cls}  {fracs[cls]:.4f}')
            class_hist[cls - TRAC_OFFSET] += int(counts[cls])
            wrote_any = True

    if wrote_any:
        n_assigned += 1

lines.append('# End of file')
ARL_OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')

print(f'\n  Links assigned:     {n_assigned:,}')
print(f'  Links all-nodata:   {n_skipped:,}')
total_px = class_hist.sum()
class_names = ['sand(f53)', 'Cymodocea(f153)', 'Posidonia(f153)', 'rock(f53)']
print(f'\n  Trachytope distribution (pixel-weighted):')
for i, name in enumerate(class_names):
    cls = i + TRAC_OFFSET
    pct = class_hist[i] / total_px * 100 if total_px > 0 else 0
    print(f'    TTD {cls} ({name:18s}): {class_hist[i]:8,} px ({pct:5.1f}%)')
print(f'\nSaved: {ARL_OUT.name}  ({ARL_OUT.stat().st_size/1e3:.0f} kB)')
