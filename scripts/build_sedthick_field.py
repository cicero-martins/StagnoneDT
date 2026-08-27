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

Optionally the meadow is withheld too. Pass the RF seagrass classification as a
third argument and thickness is scaled by the bare fraction of each node's
neighbourhood, so a fully vegetated node carries no mobile sediment at all.

Why that is needed. FM's taus, the bed shear stress that drives transport,
includes the trachytope drag. Once the .arl reached the whole meadow instead of
5% of it, lagoon shear rose 2.4-fold and the wave-coupled mobile-bed member
began aborting on the bed-change limiter, 73 warnings against none for the same
model with the old file. So canopy form drag was eroding the bed as though it
were skin friction on the grains, which is the opposite of what a Posidonia
meadow does. Withholding sediment under the canopy states the real process:
the stress is carried by the plants and the bed beneath them is not mobile.

Scaling by the bare fraction rather than switching on a majority keeps the same
principle as the depth taper above, which is that a step in availability is an
artefact waiting to happen.

Run where the mesh is. Output: sedthick_lagoon.xyz next to the model files.
"""
import sys
from pathlib import Path

import numpy as np
import xarray as xr

FULL_DEPTH = 15.0     # m, sediment at full thickness shallower than this
ZERO_DEPTH = 20.0     # m, sediment absent deeper than this
THICKNESS = 0.5       # m, the IniSedThick the .sed carried as a scalar

# RF v3 classes that are vegetation: 1 Cymodocea, 2 Cymodocea+Caulerpa,
# 3 Posidonia+Caulerpa, 4 Posidonia atolls, 5 Posidonia+epiphytes. Class 0 is
# unvegetated and 7 the reef plateau; the plateau carries no canopy drag
# (formula 53, n=0.028) so it is left alone here.
VEG_CLASSES = (1, 2, 3, 4, 5)
RADIUS = 20           # m, matching the search radius in build_trachytope_arl.py


def bare_fraction(x, y, class_tif):
    """Fraction of each node's neighbourhood that is classified and unvegetated.

    Nodes with no classified pixel within RADIUS return 1.0, which leaves the
    depth taper as the only restriction there. That is the right default: the
    classification covers the lagoon, and absence of a class offshore is
    absence of evidence, not evidence of bare sand.
    """
    import rasterio
    from pyproj import Transformer

    with rasterio.open(class_tif) as r:
        cls = r.read(1).astype(np.int16)
        tf, H, W, res = r.transform, r.height, r.width, r.res[0]

    veg = np.isin(cls, VEG_CLASSES)
    known = cls >= 0

    # Node coordinates are WGS84; the raster is UTM33N. The transform is only
    # used to index the raster, never written anywhere -- writing UTM into a
    # model input is what silently zeroed the trachytopes once already.
    xu, yu = Transformer.from_crs('EPSG:4326', 'EPSG:32633',
                                  always_xy=True).transform(x, y)
    col = ((xu - tf.c) / tf.a).astype(int)
    row = ((yu - tf.f) / tf.e).astype(int)          # tf.e < 0

    rp = int(np.ceil(RADIUS / res))
    d = np.arange(-rp, rp + 1)
    DC, DR = np.meshgrid(d, d)
    circle = (DR ** 2 + DC ** 2) <= rp ** 2
    DR, DC = DR[circle].ravel(), DC[circle].ravel()

    out = np.ones(len(x))
    inside = ((col >= rp) & (col < W - rp) & (row >= rp) & (row < H - rp))
    for i in np.where(inside)[0]:
        rr, cc = row[i] + DR, col[i] + DC
        k = known[rr, cc]
        if k.any():
            out[i] = 1.0 - veg[rr, cc][k].mean()
    return out, inside


def main(net_nc, out_xyz, class_tif=None):
    ds = xr.open_dataset(net_nc)
    x = ds.mesh2d_node_x.values
    y = ds.mesh2d_node_y.values
    z = ds.mesh2d_node_z.values
    ds.close()

    depth = np.where(z < 0, -z, 0.0)
    # linear taper: 1 above FULL_DEPTH, 0 below ZERO_DEPTH
    frac = np.clip((ZERO_DEPTH - depth) / (ZERO_DEPTH - FULL_DEPTH), 0.0, 1.0)
    thick = THICKNESS * frac

    bare = None
    if class_tif:
        bare, inside = bare_fraction(x, y, class_tif)
        thick = thick * bare

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
    if bare is not None:
        print(f'  seagrass mask from {Path(class_tif).name}')
        print(f'    nodes inside the classified extent   : {inside.sum():6d}')
        print(f'    fully vegetated (bare = 0)           : {int((bare == 0).sum()):6d}')
        print(f'    partly vegetated (0 < bare < 1)      : '
              f'{int(((bare > 0) & (bare < 1)).sum()):6d}')
        print(f'    sediment withheld by the mask        : '
              f'{THICKNESS * frac.sum() - thick.sum():.1f} m summed over nodes '
              f'({100 * (1 - thick.sum() / (THICKNESS * frac.sum())):.1f}%)')
    print(f'  thickness range: {thick.min():.3f} to {thick.max():.3f} m')


if __name__ == '__main__':
    net = sys.argv[1] if len(sys.argv) > 1 else 'Stagnone_dxy01_15m_net.nc'
    out = sys.argv[2] if len(sys.argv) > 2 else 'sedthick_lagoon.xyz'
    tif = sys.argv[3] if len(sys.argv) > 3 else None
    main(net, out, tif)
