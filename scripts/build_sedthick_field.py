"""Spatially varying initial sediment thickness, to confine morphodynamics to
the depths where waves can plausibly move the modelled sediment.

Why this is needed. The v04 morphodynamic configuration has no spatial
restriction, so bed update runs over the whole domain including offshore water
hundreds of metres deep. Two consequences were traced to it. The largest bed
change in the wave-coupled uniform-roughness member, the 2.4 m in nine days
that is quoted as evidence the erosion threshold is uncalibrated, occurs in a
cell 500 m deep, not in the lagoon. And both no-wave morphodynamic members
aborted on the velocity cap at an offshore cell 27 m deep.

The threshold is taken from the model's own wave field rather than assumed.
Mean orbital velocity at the bed over the drifter window falls from
0.185 m/s at 2-5 m to 0.050 at 10-15 m, 0.030 at 15-20 m and 0.016 at 20-30 m,
an order of magnitude below the range where 150 um sand mobilises. Sediment is
therefore held at full thickness above 15 m depth and tapered linearly to zero
at 20 m, the taper avoiding a step in availability that a hard cutoff would
impose.

FM reads IniSedThick either as a scalar or as a file, so the .sed entry for each
fraction is pointed at the sample file this writes.

Run where the mesh is. Output: sedthick_lagoon.xyz next to the model files.
"""
import sys
from pathlib import Path

import numpy as np
import xarray as xr

FULL_DEPTH = 15.0     # m, sediment at full thickness shallower than this
ZERO_DEPTH = 20.0     # m, sediment absent deeper than this
THICKNESS = 0.5       # m, the IniSedThick the .sed carried as a scalar


def main(net_nc, out_xyz):
    ds = xr.open_dataset(net_nc)
    x = ds.mesh2d_node_x.values
    y = ds.mesh2d_node_y.values
    z = ds.mesh2d_node_z.values
    ds.close()

    depth = np.where(z < 0, -z, 0.0)
    # linear taper: 1 above FULL_DEPTH, 0 below ZERO_DEPTH
    frac = np.clip((ZERO_DEPTH - depth) / (ZERO_DEPTH - FULL_DEPTH), 0.0, 1.0)
    thick = THICKNESS * frac

    with open(out_xyz, 'w') as f:
        for xi, yi, ti in zip(x, y, thick):
            f.write(f'{xi:.7f} {yi:.7f} {ti:.5f}\n')

    n = len(thick)
    print(f'wrote {out_xyz}  ({n} points)')
    print(f'  full thickness (depth < {FULL_DEPTH:.0f} m): '
          f'{(depth < FULL_DEPTH).sum():6d} ({100 * (depth < FULL_DEPTH).mean():.1f}%)')
    print(f'  taper                                   : '
          f'{((depth >= FULL_DEPTH) & (depth < ZERO_DEPTH)).sum():6d}')
    print(f'  zero  (depth > {ZERO_DEPTH:.0f} m)              : '
          f'{(depth >= ZERO_DEPTH).sum():6d} ({100 * (depth >= ZERO_DEPTH).mean():.1f}%)')
    print(f'  thickness range: {thick.min():.3f} to {thick.max():.3f} m')


if __name__ == '__main__':
    net = sys.argv[1] if len(sys.argv) > 1 else 'Stagnone_dxy01_15m_net.nc'
    out = sys.argv[2] if len(sys.argv) > 2 else 'sedthick_lagoon.xyz'
    main(net, out)
