"""No-waves member on the v04 mesh with a different vertical discretisation.

The clones support a layer sensitivity test of the no-waves member of the
Paper 1 ensemble. Every clone is model/dflowfm_v04AE_nowaves_v04bed_cfl05 (v04
mesh and bed, maximum Courant number 0.5, initial fields by triangulation)
with only the vertical discretisation changed, so that the 10-layer run
already made with that configuration is the reference of the test.

The ensemble runs with 10 uniform sigma layers (layerType = 1, stretchType =
-1; the interfaces written to the map file are at 0.1 intervals of the water
column). Without further settings, uniform sigma with 20 or 40 layers fails
within 37 minutes on the western slope of Marettimo, 600 m deep and 1.3 km
inside the open boundary, where the start from a column at uniform 24 C and
37.5 meets the stratified boundary water of CMEMS, and so does z-sigma with
20 or 40 sigma layers. The trigger is baroclinic, since the 20-layer run
with uniform density reaches 45 minutes at 0.94 m/s. With 5 layers the run
returns NaN at the first step on the server, the failure that the 120 m
quadtree mesh also shows on that host only.

The failure is a checkerboard instability of the horizontal velocity next to
the open boundary, which the start-up transient excites (D-Flow FM User
Manual, section 10.8.4 and Figure 10.6). With the horizontal momentum filter
(--hmf, horizontalMomentumFilter = 1) the 20-layer run completes two hours
at 3.5 m/s at most, on the Marettimo shore, against 2.8 m/s in the 10-layer
reference, whereas the anti-creep correction of section 10.8.3 alone fails
at 36 minutes as without it. A stratified initial condition (--ic3d,
build_ic3d_profiles.py) or the full CMEMS field (IniWithNudge = 1) only
delays the failure, to 1 h 09 and 1 h 06. The layer test is made on uniform
sigma with the filter, at 5, 10, 20 and 40 layers.

The z-sigma variant (--zsigma N) keeps N uniform sigma layers over a sigma
zone of about 10 m and z layers
below. The lagoon, shallower than 4 m, lies inside the sigma zone at every
level and is discretised by N uniform sigma layers, as the ensemble is by
10. FM makes the sigma zone N * dzTop deep, so dzTop = 10 m / N; the z
layers below start at dzTop and grow by sigmaGrowthFactor = 1.2, which
refines the offshore with the lagoon. Verified levels, sigma zone depth and
number of z layers below it: N = 5, 9.0 m, 23; N = 10, 10.0 m, 27; N = 20,
10.5 m, 31; N = 40, 10.75 m, 34. N = 10 against the uniform-sigma reference
measures the effect of the offshore coordinate on the lagoon.

Output is restricted to what the comparison reads, which leaves the numerics
unchanged. Map output is written only over the drifter window, 7 to 10 July,
and restart files are not written.

Usage:
    python build_v04AE_nowaves_layers.py --kmx 20 --hmf [--smoke 2]
    python build_v04AE_nowaves_layers.py --zsigma 10
"""
from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from build_v04AE_nowaves_bathy26 import SKIP, write_local_launcher
from build_v04AE_nowaves_qt_family import patch_line

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'model/dflowfm_v04AE_nowaves_v04bed_cfl05'
IC3D = ROOT / 'data/processed/ic3d'
MDU = 'Stagnone_dxy01_15m.mdu'
REFDATE = datetime(2025, 1, 1)
MAP_WINDOW = (datetime(2025, 7, 7), datetime(2025, 7, 10))
MAP_INTERVAL = 1800.0
# z-sigma: 10 sigma layers on top, held at a constant count, over z layers
# that are 1 m thick above -5 m and grow by 1.2 below it.
ZSIGMA = {'kmx': 45, 'layerType': 2, 'numTopSig': 10, 'numTopSigUniform': 1,
          'dzTop': 1.0, 'dzTopUniAboveZ': -5.0, 'sigmaGrowthFactor': 1.2}


def write_ic3d(dst):
    """Initial fields with the stratified offshore and the member's lagoon.

    Blocks are applied in file order: the two vertical profiles over the
    whole domain, then the lagoon salinity by cell averaging, then the
    tracers as in the reference.
    """
    for f in IC3D.glob('ic3d_*'):
        shutil.copyfile(f, dst / f.name)
    ini = (dst / 'initialFields.ini').read_text(encoding='utf-8')
    blocks = re.split(r'(?=^\[)', ini, flags=re.M)
    head = [b for b in blocks if b.startswith('[General]')]
    tracers = [b for b in blocks if re.search(r'quantity\s*=\s*initialtracer', b)]
    assert len(head) == 1 and len(tracers) == 3, 'initialFields.ini layout changed'

    def block(q, f, ftype, method, extra=''):
        return (f'[Initial]\n    quantity              = {q}\n    dataFile              = {f}\n'
                f'    dataFileType          = {ftype}\n    interpolationMethod   = {method}\n{extra}'
                f'    operand               = O\n\n')
    # A depth-uniform initialtemperature block resets the temperature of every
    # cell, including those without a sample, which erases the profile; the
    # salinity block does not. The lagoon therefore starts at the surface value
    # of the temperature profile instead of the 24 C of the member.
    new = [head[0],
           block('initialverticaltemperatureprofile', 'ic3d_temperature_profile.pli', 'polygon', 'constant'),
           block('initialverticalsalinityprofile', 'ic3d_salinity_profile.pli', 'polygon', 'constant'),
           block('initialsalinity', 'ic3d_lagoon_salinity.xyz', 'sample', 'averaging', '    averagingType         = mean\n')]
    (dst / 'initialFields.ini').write_text(''.join(new + tracers), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument('--kmx', type=int, help='number of uniform sigma layers')
    grp.add_argument('--zsigma', type=int, nargs='?', const=ZSIGMA['numTopSig'], metavar='N',
                     help=f'N sigma layers on top of z layers (default {ZSIGMA["numTopSig"]})')
    ap.add_argument('--hmf', action='store_true',
                    help='horizontal momentum filter (horizontalMomentumFilter = 1)')
    ap.add_argument('--ic3d', action='store_true',
                    help='stratified offshore initial condition of build_ic3d_profiles.py')
    ap.add_argument('--smoke', type=float, default=None, help='simulated hours of an initialisation test')
    args = ap.parse_args()
    if args.zsigma:
        # The sigma zone is numTopSig * dzTop deep; dzTop = 10 m / N keeps it at
        # 10 m, and the z layers below start at dzTop and grow by the same factor.
        ZSIGMA['dzTop'] = ZSIGMA['dzTop'] * ZSIGMA['numTopSig'] / args.zsigma
        ZSIGMA['kmx'] = args.zsigma + 60
        ZSIGMA['numTopSig'] = args.zsigma
    tag = (f'_zsig{args.zsigma:02d}' if args.zsigma != 10 else '_zsig') if args.zsigma else f'_L{args.kmx:02d}'
    suffix = tag + ('_hmf' if args.hmf else '') + ('_ic3d' if args.ic3d else '') + ('_smoke' if args.smoke else '')
    dst = ROOT / f'model/dflowfm_v04AE_nowaves_v04bed_cfl05{suffix}'
    if dst.exists():
        raise SystemExit(f'{dst} already exists; remove it before rebuilding')
    shutil.copytree(REF, dst, ignore=SKIP)
    write_local_launcher(dst)
    if args.ic3d:
        write_ic3d(dst)

    mdu = (dst / MDU).read_text(encoding='utf-8')
    if args.zsigma:
        for k, v in ZSIGMA.items():
            mdu = patch_line(mdu, k, f'{v:g}', 'z-sigma variant of the layer test')
    else:
        mdu = patch_line(mdu, 'kmx', str(args.kmx), 'uniform sigma layers of the layer test')
    if args.hmf:
        mdu = patch_line(mdu, 'horizontalMomentumFilter', '1', 'filter of spurious velocity oscillations, User Manual 10.8.4')
    t0, t1 = ((d - REFDATE).total_seconds() for d in MAP_WINDOW)
    mdu = patch_line(mdu, 'mapInterval', f'{MAP_INTERVAL:.1f} {t0:.1f} {t1:.1f}', 'drifter window only')
    mdu = patch_line(mdu, 'rstInterval', '0.0', 'no restart files')
    if args.smoke:
        stop = datetime(2025, 7, 1) + timedelta(hours=args.smoke)
        mdu = patch_line(mdu, 'stopDateTime', stop.strftime('%Y%m%d%H%M%S'), f'initialisation test of {args.smoke:g} h')
        mdu = patch_line(mdu, 'mapInterval', '1800.0', 'initialisation test')
    (dst / MDU).write_text(mdu, encoding='utf-8')

    for f in list(dst.glob('*.sh')) + list(dst.glob('*.xml')):
        txt = f.read_bytes().decode('utf-8')
        new = txt.replace('dflowfm_v04AE_nowaves_v04bed_cfl05"', f'dflowfm_v04AE_nowaves_v04bed_cfl05{suffix}"')
        new = new.replace('_v04bed_cfl05 launch', f'_v04bed_cfl05{suffix} launch')
        if new != txt:
            f.write_bytes(new.encode('utf-8'))
    print('[done]', dst)


if __name__ == '__main__':
    main()
