"""Subset sicily_lonlat.ldb to the model domain + identify individual island
polylines (Marettimo, Favignana, Levanzo) and Sicily mainland coast.

The sicily_lonlat.ldb is one big polyline F001 with 94k points covering all
of southern Italy coastline including major islands. We need to:
  1. Subset to model bbox (lon 11.9-12.6, lat 37.6-38.2)
  2. Split into separate polylines per landmass (Marettimo, Favignana, Levanzo,
     Sicily mainland coast from Marsala to Trapani)
  3. Write a clean LDB file ready for RGFGRID use

Output: data/processed/sicily_v05.ldb
"""
from pathlib import Path
import numpy as np

SRC = Path(r'C:/Users/Unipa/Documents/StagnoneLagoon/Datasets/2026/bathymetry/sicily_lonlat.ldb')
OUT = Path('data/processed/sicily_v05.ldb')

# Model domain (with margin)
LON_MIN, LON_MAX = 11.90, 12.60
LAT_MIN, LAT_MAX = 37.60, 38.20

def parse_ldb(path):
    """Returns list of polylines (each is Nx2 array)."""
    polys = []
    current = []
    with open(path) as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith('*'):
                continue
            if s.startswith('F') or s.startswith('L'):
                if current:
                    polys.append(np.array(current))
                    current = []
                continue
            parts = s.split()
            if len(parts) == 2:
                # might be header "n_points n_cols"
                try:
                    a, b = float(parts[0]), float(parts[1])
                    if a > 100 and b < 10:  # looks like header
                        continue
                    current.append((a, b))
                except ValueError:
                    pass
    if current:
        polys.append(np.array(current))
    return polys


def split_into_segments(pts, min_pts=20):
    """The single huge polyline often jumps between islands. Detect jumps and
    split. A "jump" = consecutive points >2 km apart.
    """
    # distance between consecutive points (m approx)
    lat_avg = np.mean(pts[:, 1])
    dx_m = (pts[1:, 0] - pts[:-1, 0]) * 111000 * np.cos(np.radians(lat_avg))
    dy_m = (pts[1:, 1] - pts[:-1, 1]) * 111000
    dist = np.sqrt(dx_m**2 + dy_m**2)
    JUMP_THRESH = 2000  # 2 km
    jumps = np.where(dist > JUMP_THRESH)[0]
    print(f'  Detected {len(jumps)} jumps > {JUMP_THRESH}m')
    # Split
    segments = []
    start = 0
    for j in jumps:
        end = j + 1
        if end - start >= min_pts:
            segments.append(pts[start:end])
        start = end
    if len(pts) - start >= min_pts:
        segments.append(pts[start:])
    return segments


def classify_segment(seg):
    """Identify which island/coast this segment represents.

    Strategy: use centroid + spatial extent to differentiate:
      - Egadi islands: small closed polylines centered offshore
      - Sicily mainland: long segment on east side
      - Isola Grande/Lunga (Stagnone barrier islands): in lagoon area
        (lon ~12.43, lat 37.83-37.92), separate from mainland
    """
    lon_c, lat_c = seg[:, 0].mean(), seg[:, 1].mean()
    lon_range = seg[:, 0].max() - seg[:, 0].min()
    lat_range = seg[:, 1].max() - seg[:, 1].min()
    n = len(seg)

    # Marettimo center ~(12.06, 37.97)
    if 12.00 < lon_c < 12.12 and 37.94 < lat_c < 38.02:
        return 'Marettimo'
    # Favignana ~(12.32, 37.93)
    if 12.27 < lon_c < 12.38 and 37.90 < lat_c < 37.98:
        return 'Favignana'
    # Levanzo ~(12.34, 38.00)
    if 12.30 < lon_c < 12.40 and 37.98 < lat_c < 38.05:
        return 'Levanzo'
    # Isola Grande / Lunga (Stagnone barrier islands) — small polylines in ~12.42-12.46
    if 12.42 < lon_c < 12.47 and 37.82 < lat_c < 37.92 and n < 5000:
        return 'StagnoneBarrier'
    # Sicily mainland coast — long segment with lon mostly > 12.40
    if seg[:, 0].max() > 12.40 and lat_range > 0.1:
        return 'SicilyMainland'
    return 'Other'


def main():
    print(f'Loading {SRC} ...')
    polys = parse_ldb(SRC)
    print(f'  parsed {len(polys)} polylines, total points: {sum(len(p) for p in polys)}')

    # Concatenate all into one (they ARE one polyline in this file)
    all_pts = np.concatenate(polys) if polys else np.zeros((0, 2))

    # Subset to domain
    in_domain = (
        (all_pts[:, 0] >= LON_MIN) & (all_pts[:, 0] <= LON_MAX) &
        (all_pts[:, 1] >= LAT_MIN) & (all_pts[:, 1] <= LAT_MAX)
    )
    domain_pts = all_pts[in_domain]
    print(f'  points in domain: {len(domain_pts)} / {len(all_pts)}')

    # Split into segments by jumps
    segments = split_into_segments(domain_pts, min_pts=20)
    print(f'  split into {len(segments)} segments')
    for k, seg in enumerate(segments):
        cls = classify_segment(seg)
        print(f'    seg {k+1:3d}: {len(seg):5d} pts  centroid=({seg[:,0].mean():.4f}, {seg[:,1].mean():.4f})  -> {cls}')

    # Write LDB file
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w') as f:
        f.write('* sicily_v05.ldb — subset of sicily_lonlat.ldb to Stagnone model domain\n')
        f.write('* split into per-landmass polylines for RGFGRID use\n')
        f.write('* column 1 = lon, column 2 = lat (WGS84)\n')
        # Aggregate by classification, write one polyline per class
        by_cls = {}
        for seg in segments:
            cls = classify_segment(seg)
            by_cls.setdefault(cls, []).append(seg)
        for cls, segs in by_cls.items():
            pts = np.concatenate(segs)
            f.write(f'{cls}\n')
            f.write(f'    {len(pts)}    2\n')
            for x, y in pts:
                f.write(f'    {x:.7f}    {y:.7f}\n')
    print(f'\nWrote {OUT}')
    print(f'Total polylines: {len(by_cls)}')
    for cls, segs in by_cls.items():
        n = sum(len(s) for s in segs)
        print(f'  {cls}: {n} pts ({len(segs)} segment(s))')


if __name__ == '__main__':
    main()
