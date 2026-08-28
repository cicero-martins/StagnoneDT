"""Turn the seagrass trachytope map into D-Flow FM native vegetation fields.

D-Flow FM carries vegetation in two unrelated places, and only one of them
reaches the momentum equation:

  trachytopes  a roughness pre-processor. Formula 154 computes both a bed Chezy
               and a canopy momentum sink, but the FM solver reads only the
               first. Measured, not inferred: two runs whose .ttd differed only
               in C_D, 0.00 against 0.80, giving a sink of 0.0 against 4.0 1/m
               over 16359 links, produced a bit-identical solution across 48
               frames and 27901 cells. See compare_trt_sink_inertia.py.

  [veg]        Vegetationmodelnr, m_vegetation, setbaptist.f90. Its arrays are
               FM's own (stemheight(ndx), stemdens(ndx), diaveg, rnveg) and it
               produces cfuveg, a friction coefficient on links. The kernel
               refuses Trachytopes together with Vegetationmodelnr >= 2, which
               only makes sense if the two set the same thing.

This writes the three sample files the second path takes as spatial input:
stemheight, stemdensity and stemdiameter, one value per flow node, zero off the
meadow. Full coverage is deliberate -- a sample file that only covers the
meadow leaves every other cell to whatever the interpolation defaults to.

Parameters come from Ciraolo, Ferreri & La Loggia (2006), JHR 44(2):189-202,
a flume study of P. oceanica carried out at UNIPA for this lagoon:

  leaves ribbon-like, about 1 cm wide, in nature usually over 1 m long
  tufts of six leaves
  500 to 1000 plants/m2 in nature; 682 in the flume

so for Posidonia stemdensity = 6 x 500 = 3000 leaves/m2 at 1 cm each, giving
mD = 30 1/m. The trachytope .ttd carried mD = 5.0, which counted one 1 cm stem
per plant and so missed the tuft by a factor of six.

Note that Ciraolo's h_v is the leaf length, not the deflected height: they
tested including the measured deflected thickness k in their resistance law and
found it does not enter, because k is itself a function of U, h and leaf
length. So stemheight is the leaf length.

Cymodocea has no equivalent flume study here. Its values are the existing
planning-document ones scaled the same way, 3 leaves per shoot, and should be
read as provisional. De Marchis et al. (2012) give the only local anchor,
ks = 0.30 m against 0.10 m for Posidonia -- Cymodocea rougher in bulk, which
Ciraolo's Eq. 23 explains rather than contradicts, since friction slope falls
with leaf length as h_v^-1.56.

    python build_veg_fields_from_arl.py <arl> <outdir> [--faces faces.npz]
"""
import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

# class -> (stemheight m, stemdensity 1/m2, stemdiameter m, label)
#
# stemheight is the CANOPY height, not the leaf length. Those differ for a
# plant whose leaves lie over, and conflating them was an error: Ciraolo's h_v
# is leaf length, "usually over 1 m" in nature, but the canopy occupies far
# less of the column. Prinos et al. (2010) built their experiment at
# submergence ratios h_s/D of 0.323, 0.423 and 0.500 precisely because that is
# what a real meadow does, and Ciraolo's own measured deflected thickness k/h
# sits mostly between 0.2 and 0.6, reaching 1.0 only in his slowest run
# (4.3 cm/s). Field observation in this lagoon agrees: Posidonia rarely reaches
# the surface. For a 1 m column that puts the canopy at 0.3-0.5 m.
VEG = {
    2: (0.15, 2400.0, 0.004, 'Cymodocea, 800 shoots x 3 leaves x 4 mm'),
    3: (0.40, 3000.0, 0.010, 'Posidonia, 500 plants x 6 leaves x 1 cm'),
}
# A sample is claimed by a link no further than this, in degrees (~110 m).
TOL_DEG = 0.001


def read_arl(path):
    """Link position, class, and AREA FRACTION.

    The fraction is not decoration. In this map the median Posidonia link is
    0.685 covered and the median Cymodocea link 0.181, with only 2% of the
    Cymodocea links fully covered. Taking the class value and ignoring the
    fraction overstates Cymodocea density by about 5.5x, and that error would
    end up absorbed into C_D during calibration -- exactly the cross
    compensation the calibration design is meant to prevent.
    """
    xy, cls, frac = [], [], []
    for line in Path(path).read_text(errors='ignore').splitlines():
        if line.lstrip().startswith('#'):
            continue
        s = line.split()
        if len(s) >= 5 and int(s[3]) in VEG:
            xy.append((float(s[0]), float(s[1])))
            cls.append(int(s[3]))
            frac.append(float(s[4]))
    return np.array(xy), np.array(cls), np.array(frac)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arl')
    ap.add_argument('outdir')
    ap.add_argument('--faces', required=True,
                    help='npz or npy with face_x, face_y')
    ap.add_argument('--posidonia-height', type=float,
                    help='override the class 3 canopy height, m')
    a = ap.parse_args()
    if a.posidonia_height:
        h, d, dia, lab = VEG[3]
        VEG[3] = (a.posidonia_height, d, dia, lab)

    d = np.load(a.faces)
    fx, fy = d['x'], d['y']
    xy, cls, frac = read_arl(a.arl)
    print(f'{len(fx)} flow nodes, {len(xy)} vegetated links')

    # FM's own consistency check: a plant may not cover more than its share of
    # bed. Fail here rather than let the kernel warn on every cell.
    for c, (h, dens, dia, lab) in VEG.items():
        if np.pi / 4 * dia ** 2 > 1.0 / dens:
            raise SystemExit(f'class {c}: pi/4*D^2 {np.pi/4*dia**2:.2e} exceeds '
                             f'1/density {1/dens:.2e} -- FM will reject it')

    dist, idx = cKDTree(xy).query(np.c_[fx, fy])
    hit = dist < TOL_DEG
    node_cls = np.zeros(len(fx), int)
    node_cls[hit] = cls[idx[hit]]
    node_frac = np.zeros(len(fx))
    node_frac[hit] = frac[idx[hit]]

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    # Fractional cover scales the AREAL density and nothing else. Height and
    # diameter are properties of a plant, not of how much bed it covers, so
    # scaling them would be a different and wrong claim about the biology.
    fields = {'stemheight': 0, 'stemdensity': 1, 'stemdiameter': 2}
    for name, k in fields.items():
        v = np.zeros(len(fx))
        for c, params in VEG.items():
            sel = node_cls == c
            v[sel] = params[k] * (node_frac[sel] if name == 'stemdensity' else 1.0)
        f = out / f'veg_{name}.xyz'
        with f.open('w') as fh:
            for x, y, z in zip(fx, fy, v):
                fh.write(f'{x:.9f} {y:.9f} {z:.6f}\n')
        nz = v > 0
        u = np.unique(np.round(v[nz], 4))
        print(f'  {f.name:22s} {len(v)} samples, {int(nz.sum())} nonzero, '
              + (f'values {list(u)}' if len(u) <= 4
                 else f'{len(u)} distinct, {u.min():g} to {u.max():g}'))

    for c, (h, dens, dia, lab) in VEG.items():
        sel = node_cls == c
        if not sel.any():
            continue
        md = dens * dia * node_frac[sel]
        print(f'  class {c}: {int(sel.sum()):6d} nodes  h_v={h} m  '
              f'cover median {np.median(node_frac[sel]):.3f}  '
              f'mD median {np.median(md):.1f} (was {dens*dia:.1f} at full cover)   {lab}')
    print(f'  bare: {int((node_cls == 0).sum())} nodes')


if __name__ == '__main__':
    main()
