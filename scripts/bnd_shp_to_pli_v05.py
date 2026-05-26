"""Convert the boundary shapefile produced by build_mesh_v05.py into a
Delft3D FM .pli file ready for boundary-condition assignment.

dfmt.generate_bndpli_cutland() outputs a GeoDataFrame of LineStrings; FM expects
a .pli with one block per polyline:
    <name>
    <n_points>    2
    <lon> <lat>
    ...

Output:
  data/processed/mesh_v05/Stagnone_v05.pli
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np

SHP = Path('data/processed/mesh_v05/Stagnone_v05_bnd.shp')
OUT_PLI = Path('data/processed/mesh_v05/Stagnone_v05.pli')


def main():
    if not SHP.exists():
        raise SystemExit(f'{SHP} not found - run build_mesh_v05.py first')
    gdf = gpd.read_file(SHP)
    print(f'Loaded {len(gdf)} polylines from {SHP}')
    for i, row in gdf.iterrows():
        g = row.geometry
        print(f'  line {i}: type={g.geom_type}, {len(g.coords) if g.geom_type=="LineString" else "?"} pts')

    lines_out = []
    n_blocks = 0
    for i, row in gdf.iterrows():
        g = row.geometry
        if g.geom_type == 'LineString':
            segs = [list(g.coords)]
        elif g.geom_type == 'MultiLineString':
            segs = [list(s.coords) for s in g.geoms]
        else:
            print(f'  [skip] geom_type={g.geom_type}')
            continue
        for j, coords in enumerate(segs):
            name = f'Stagnone_v05_bnd_{n_blocks:04d}'
            lines_out.append(name)
            lines_out.append(f'    {len(coords)}    2')
            for x, y in coords:
                lines_out.append(f'    {x:.7f}    {y:.7f}')
            n_blocks += 1

    OUT_PLI.write_text('\n'.join(lines_out) + '\n', encoding='ascii')
    print(f'\nWrote {OUT_PLI}: {n_blocks} polyline block(s), '
          f'{sum(1 for l in lines_out if not l.startswith(("Stagnone","    ")) and "    " not in l)} headers')

    # quick verification
    with open(OUT_PLI) as f:
        content = f.read()
    n_lines = content.count('\n')
    print(f'  file has {n_lines} lines, {OUT_PLI.stat().st_size/1024:.1f} kB')


if __name__ == '__main__':
    main()
