"""Build Stagnone_v05_fxw.pliz from sicily_v05_manualEdited.ldb.

User decision 2026-05-28: implement ALL 10 polygons as fixed weirs with:
  - crest level (z) = +1.0 m  (above model datum / wgs84-EGM-ish)
  - slope left/right = 1.0    (steep, like saltpan walls)
  - crest width    = 0.5 m    (narrow, like real muretas)
  - ground heights = 0.0      (default; weir always active per Sillheightmin=0)
  - roughness code = 0.0      (default)
  - weir type      = v        (Villemonte, matches FixedWeirScheme=9 default)

Per FM 2026.01 UM §C.8, the .pliz format:
  <polyline_name>
    <nrows>  9
    X    Y    CrestLevel  GroundHeightL  GroundHeightR  CrestWidth  SlopeL  SlopeR  RoughCode
    ...
(weir type 'v' or 't' as optional 10th column; omitted -> uses FixedWeirScheme default)
"""
from __future__ import annotations
from pathlib import Path

SRC_LDB = Path('data/processed/sicily_v05_manualEdited.ldb')
DST_PLIZ = Path('model/dflowfm_v05/Stagnone_v05_fxw.pliz')

CREST = 1.0      # m above datum
GHT_L = 0.0
GHT_R = 0.0
WIDTH = 0.5      # m
SLOPE_L = 1.0
SLOPE_R = 1.0
ROUGH = 0.0


def parse_ldb(path: Path):
    polys = []
    with open(path, 'r') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s.startswith('*'):
            i += 1
            continue
        name = s
        i += 1
        try:
            nrow, ncol = map(int, lines[i].split())
        except (ValueError, IndexError):
            i += 1
            continue
        i += 1
        coords = []
        for _ in range(nrow):
            parts = lines[i].split()
            coords.append((float(parts[0]), float(parts[1])))
            i += 1
        polys.append((name, coords))
    return polys


def write_pliz(polys, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w') as f:
        f.write('* Stagnone v05 fixed weirs (muretas das salinas + costas)\n')
        f.write(f'* Built from {SRC_LDB.name} (2026-05-28)\n')
        f.write(f'* Crest: z={CREST} mAD, slope={SLOPE_L}, width={WIDTH} m\n')
        f.write('* Columns: x, y, crestLevel, groundHeightL, groundHeightR, crestWidth, slopeL, slopeR, roughCode\n')
        f.write('*\n')
        for name, coords in polys:
            f.write(f'{name}\n')
            f.write(f'    {len(coords)}    9\n')
            for x, y in coords:
                f.write(f'  {x:11.7f}  {y:11.7f}  {CREST:5.2f}  {GHT_L:4.2f}  {GHT_R:4.2f}  {WIDTH:4.2f}  {SLOPE_L:4.2f}  {SLOPE_R:4.2f}  {ROUGH:4.2f}\n')


def main():
    polys = parse_ldb(SRC_LDB)
    print(f'Parsed {len(polys)} polygons from {SRC_LDB.name}:')
    for name, coords in polys:
        print(f'  {name}: {len(coords)} pts')
    write_pliz(polys, DST_PLIZ)
    total_pts = sum(len(c) for _, c in polys)
    print(f'\nWrote {DST_PLIZ} ({total_pts} total pts across {len(polys)} polylines)')


if __name__ == '__main__':
    main()
