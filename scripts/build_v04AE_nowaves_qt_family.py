"""No-waves member on the quadtree mesh family, one model per lagoon resolution.

Each clone model/dflowfm_v04AE_nowaves_qtL<edge> is model/dflowfm_v04AE_nowaves
with the net file replaced by data/processed/mesh_quadtree_family/
stagnone_qt_L<edge>/stagnone_qt_L<edge>_net.nc, written under the name the MDU
already reads. The open boundary polyline, its per-node forcing, the
meteorological fields, the observation points and the lateral sources are
unchanged, since the meshes share the v04 domain and boundary.

The initial fields are read by triangulation instead of cell averaging, in
every clone including the v04 anchors. The salinity and tracer samples sit
at the v04 face centres, about 60 m apart, so a cell averaging leaves the
cells of 15 and 30 m without a sample, whereas a triangulation reproduces the
sample values at the v04 face centres and interpolates between them
elsewhere.

The maximum Courant number is 0.5 instead of the 0.7 of the parent member.
At 0.7 the quadtree meshes fail within the first 31 minutes on the western
slope of Marettimo (11.975 E, 37.972 N, 600 m deep), where the start from
rest drives currents of 4.5 m/s in v04 as well, and the failure persists
without wind, without nudging and with a six-hour boundary smoothing, whereas
at 0.5 the 60 m mesh passes the transient and returns to 2.8 m/s after three
hours, as v04 does. The same value is applied to the two v04 anchors of the
family, the v04 mesh with its own bed (--v04 v04bed) and with the 2026 bed
of the twin (--v04 bed26), so that the Courant limit is common to every run
compared, and the v04bed anchor measures its effect against the parent.

With --smoke HOURS the clone stops after HOURS of simulated time, as an
initialisation test of the mesh in FM.

Usage:
    python build_v04AE_nowaves_qt_family.py --lagoon-m 120 [--cfl 0.5] [--smoke 2]
    python build_v04AE_nowaves_qt_family.py --v04 bed26
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from build_v04AE_nowaves_bathy26 import SKIP, SRC, write_local_launcher

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / 'data/processed/mesh_quadtree_family'
TWIN = ROOT / 'model/dflowfm_v04AE_nowaves_bathy26'
NET = 'Stagnone_dxy01_15m_net.nc'
MDU = 'Stagnone_dxy01_15m.mdu'
CFL = 0.5


def patch_line(text, key, value, comment):
    """Replace the value and comment of an MDU keyword."""
    out, hit = [], False
    for line in text.splitlines(keepends=True):
        if '=' in line and line.split('=')[0].strip().lower() == key.lower():
            out.append(f'{line.split("=", 1)[0]}= {value} # {comment}\n')
            hit = True
        else:
            out.append(line)
    assert hit, f'{key} not found'
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument('--lagoon-m', type=int, help='lagoon cell edge of the quadtree mesh')
    grp.add_argument('--v04', choices=['v04bed', 'bed26'],
                     help='v04 mesh with its own bed or with the 2026 bed of the twin')
    ap.add_argument('--cfl', type=float, default=CFL, help=f'maximum Courant number (default {CFL})')
    ap.add_argument('--smoke', type=float, default=None, help='simulated hours of an initialisation test')
    args = ap.parse_args()
    if args.lagoon_m:
        name = f'stagnone_qt_L{args.lagoon_m}'
        net = FAMILY / name / f'{name}_net.nc'
        tag = f'_qtL{args.lagoon_m}'
    else:
        net = (SRC if args.v04 == 'v04bed' else TWIN) / NET
        tag = f'_{args.v04}'
    assert net.exists(), f'{net} not built'
    suffix = tag + f'_cfl{args.cfl * 10:02.0f}' + ('_smoke' if args.smoke else '')
    dst = ROOT / f'model/dflowfm_v04AE_nowaves{suffix}'
    if dst.exists():
        raise SystemExit(f'{dst} already exists; remove it before rebuilding')
    shutil.copytree(SRC, dst, ignore=SKIP)
    shutil.copyfile(net, dst / NET)
    write_local_launcher(dst)

    mdu = (dst / MDU).read_text(encoding='utf-8')
    mdu = patch_line(mdu, 'CFLMax', f'{args.cfl:g}', 'Maximum Courant number, common to the mesh family')
    (dst / MDU).write_text(mdu, encoding='utf-8')

    ini = (dst / 'initialFields.ini').read_text(encoding='utf-8')
    n = ini.count('interpolationMethod   = averaging')
    assert n == 4, f'expected four averaged initial fields, found {n}'
    ini = ini.replace('interpolationMethod   = averaging', 'interpolationMethod   = triangulation')
    ini = '\n'.join(l for l in ini.splitlines() if not l.strip().startswith('averagingType')) + '\n'
    (dst / 'initialFields.ini').write_text(ini, encoding='utf-8')

    if args.smoke:
        mdu = (dst / MDU).read_text(encoding='utf-8')
        start = datetime.strptime('20250701000000', '%Y%m%d%H%M%S')
        assert 'startDateTime           = 20250701000000' in mdu, 'start date changed'
        stop = start + timedelta(hours=args.smoke)
        mdu = patch_line(mdu, 'stopDateTime', stop.strftime('%Y%m%d%H%M%S'),
                         f'initialisation test of {args.smoke:g} h')
        (dst / MDU).write_text(mdu, encoding='utf-8')

    for f in list(dst.glob('*.sh')) + list(dst.glob('*.xml')):
        txt = f.read_bytes().decode('utf-8')
        new = txt.replace('dflowfm_v04AE_nowaves"', f'dflowfm_v04AE_nowaves{suffix}"')
        new = new.replace('v04AE_nowaves launch', f'v04AE_nowaves{suffix} launch')
        if f.name == 'launch_nowaves.sh':
            hook = 'mkdir -p diag\n'
            assert hook in new, 'launch script layout changed'
            new = new.replace(hook, hook + '# The net file differs from the parent member, so the partition is redone here.\n'
                              'run_dflowfm.sh --partition:ndomains=8:icgsolver=6 Stagnone_dxy01_15m.mdu > diag/partition.log 2>&1\n')
        if new != txt:
            f.write_bytes(new.encode('utf-8'))
    print('[done]', dst)


if __name__ == '__main__':
    main()
