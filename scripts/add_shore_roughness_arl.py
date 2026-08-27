"""Append a rocky-shore roughness class to the trachytope .arl.

Why. On Baptist 154 the wave-coupled fixed-bed member aborts at the southwest
shore of Marettimo, 45 km from the lagoon and 34 km outside the seagrass map.
The six cells involved sit where 0.7 m of water meets neighbours 21 to 28 m
deep: within 1 km the bed spans -51.5 to +10.0 m, because a steep-sided island
is resolved with roughly 1 km cells. Water level there moves 1.79 m in 58
seconds while the tide falls by centimetres. Those links currently carry the
uniform 0.023 Manning, which is a sandy-bed value on what is a rocky shore.

So this is a physical correction with a numerical benefit, not a fudge: friction
acts on velocity, which is the channel the wetting-and-drying feedback runs
through. It should be reported as what it is.

Scope is deliberately narrow for the first test: a radius around one island, far
enough from the lagoon that any lagoon response is unambiguous. Widen only after
the lagoon effect has been measured rather than assumed. Note that these cells
exist in all eight members, so if the treatment is adopted the whole ensemble
has to be rerun for comparability.

Edge bed level comes from the mean of the four nearest mesh nodes, since the net
file carries bathymetry on nodes. The band excludes the deep shelf: it targets
the shore fringe and the links that connect it to deeper water.

Coordinates are written with 9 decimals. FM matches .arl records to links within
1 cm and 6 decimals quantise to about 9 cm here, which silently discarded 94% of
the seagrass map once already.

    python scripts/add_shore_roughness_arl.py [--n 0.05] [--radius 10]
"""
from pathlib import Path
import argparse

import numpy as np
import xarray as xr
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
NET = ROOT / 'model/dflowfm_v04AE/Stagnone_dxy01_15m_net.nc'
ARL_IN = ROOT / 'data/processed/planet2023_rf_v3/stagnone_trachytopes_v3.arl'
ARL_OUT = ROOT / 'data/processed/planet2023_rf_v3/stagnone_trachytopes_v3_shore.arl'
# The base .ttd is kept under data/processed rather than read from a model dir:
# the model directories live on the server, and the vegetation formula number
# differs between them (153 vs 154), so the base has to be chosen explicitly.
TTD_IN = ROOT / 'data/processed/planet2023_rf_v3/trachytopes_154_base.ttd'
TTD_OUT = ROOT / 'data/processed/planet2023_rf_v3/trachytopes_shore.ttd'

CENTRE = (12.0530, 37.9700)     # Marettimo
BL_BAND = (-15.0, 1.0)          # shore fringe and its links to deeper water
SHORE_CLASS = 5                 # classes 1-4 are already defined in the .ttd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=float, default=0.05,
                    help='Manning for the rocky shore; literature puts rock and '
                         'boulder beds at 0.04-0.07')
    ap.add_argument('--radius', type=float, default=10.0, help='km')
    ap.add_argument('--ttd', default=str(TTD_IN),
                    help='base .ttd; the vegetation formula number differs '
                         'between the 153 and 154 members')
    a = ap.parse_args()
    ttd_in = Path(a.ttd)

    ds = xr.open_dataset(NET)
    ex, ey = ds['mesh2d_edge_x'].values, ds['mesh2d_edge_y'].values
    nx, ny, nz = (ds['mesh2d_node_x'].values, ds['mesh2d_node_y'].values,
                  ds['mesh2d_node_z'].values)
    ds.close()

    _, i = cKDTree(np.c_[nx, ny]).query(np.c_[ex, ey], k=4)
    ez = np.nanmean(nz[i], axis=1)
    r = np.hypot((ex - CENTRE[0]) * 88.0, (ey - CENTRE[1]) * 111.0)
    m = (r < a.radius) & (ez > BL_BAND[0]) & (ez < BL_BAND[1]) & np.isfinite(ez)

    src = ARL_IN.read_text(errors='ignore').rstrip().splitlines()
    # The seagrass map stops at lon 12.4963 and this mask ends at 12.09, so the
    # two never address the same link. Assert it rather than trust it.
    have = set()
    for line in src:
        if line.lstrip().startswith('#'):
            continue
        s = line.split()
        if len(s) >= 5:
            have.add((round(float(s[0]), 9), round(float(s[1]), 9)))
    clash = sum((round(float(px), 9), round(float(py), 9)) in have
                for px, py in zip(ex[m], ey[m]))
    if clash:
        raise SystemExit(f'{clash} masked links already carry a seagrass class')

    out = [l for l in src if l.strip() != '# End of file']
    out += [
        f'# --- rocky-shore class appended by add_shore_roughness_arl.py ---',
        f'# {int(m.sum())} links within {a.radius:.0f} km of {CENTRE}, '
        f'bed level in ({BL_BAND[0]:.0f}, {BL_BAND[1]:.0f}) m',
        f'# class {SHORE_CLASS} = Manning {a.n}, formula 53',
    ]
    for px, py in zip(ex[m], ey[m]):
        out.append(f'{px:.9f}  {py:.9f}  0  {SHORE_CLASS}  1.0000')
    out.append('# End of file')
    ARL_OUT.write_text('\n'.join(out) + '\n', encoding='utf-8')

    ttd = ttd_in.read_text(errors='ignore').rstrip().splitlines()
    ttd.append(f'  {SHORE_CLASS}    53    {a.n:.4f}')
    TTD_OUT.write_text('\n'.join(ttd) + '\n', encoding='utf-8')

    print(f'{ARL_OUT.name}: {len(src)} -> {len(out)} lines, '
          f'{int(m.sum())} shore links added')
    print(f'  bed level p5 {np.percentile(ez[m], 5):.2f}  '
          f'p50 {np.median(ez[m]):.2f}  p95 {np.percentile(ez[m], 95):.2f} m')
    print(f'  lon {ex[m].min():.4f}..{ex[m].max():.4f}  '
          f'lat {ey[m].min():.4f}..{ey[m].max():.4f}')
    print(f'  nearest approach to the lagoon (12.42): '
          f'{(12.42 - ex[m].max()) * 88:.1f} km')
    print(f'{TTD_OUT.name}: class {SHORE_CLASS} = formula 53, n = {a.n}')
    print('\n'.join('  ' + l for l in TTD_OUT.read_text().splitlines()[-6:]))


if __name__ == '__main__':
    main()
