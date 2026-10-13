"""Twin of the v04AE no-waves member on the 2026 lagoon bathymetry.

The clone model/dflowfm_v04AE_nowaves_bathy26 differs from
model/dflowfm_v04AE_nowaves in one field, mesh2d_face_z of the net file,
which the model reads as bed level (bedLevType = 1). The bed of the clone is
v04 + w * d, where d is the 2026 minus v04 difference on the wet faces of
the lagoon interior (lagoon_tracer_init.xyz), w = 1 there, and w decays
linearly to zero over RAMP_M outside it. Faces in the ramp, and lagoon
faces that the 2026 raster codes as land, take d from the nearest lagoon
face, which keeps the wet domain identical and avoids isolated steps.
Beyond the ramp the v04 bed is untouched, so that the open-sea approach and
the boundary forcing are identical in the pair. The difference between the
two runs then isolates the lagoon bed level.

The raster is not used outside the lagoon. On the outer slope of the
northern mouth the bed falls from 1 to 5 m within a few hundred metres, the
faces are about 120 m wide, and the 2026 surface is on average 1.1 m deeper
than v04 and 0.7 m deeper than the 2006 survey within 250 m of the lagoon
limit. Blending toward the raster there would import that disagreement
into the test.

The ramp width follows from the step between neighbouring faces. A hard
switch at the lagoon limit adds 0.20 m on average, and up to 0.99 m, to the
bed step across the 94 edges of the limit, against an rms step of 0.09 m
between neighbouring faces in the v04 lagoon. With faces of about 70 to
100 m, 500 m spreads that difference over five to seven faces.

No fringe exclusion is applied. On lagoon faces within 90 m of the shore
the 2026 surface is 0.10 to 0.24 m shallower than v04, and the 2006 survey
is shallower than v04 by a similar amount there (0.07 to 0.20 m), while
2026 and 2006 agree within 0.03 m. The shallow fringe is therefore a
property of the survey that the v04 mesh does not carry, and not a product
of the coastal taper of the 2026 raster.

Output directories, partition files, diagnostics and logs are not cloned.
Partitioning is redone on the run host, since the partition files embed the
bed level.

With --control the script builds model/dflowfm_v04AE_nowaves_ctrl, the same
clone with the v04 bed. The parent member ran on eight partitions under
Linux, and the partition count affects the numerical result, so a pair run
on another host needs its own control. Both clones carry run_local.bat and
dimr_config_local.xml for the four-core Windows workstation.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from assess_bathy_levigata_impact_v04 import TO_UTM
from compare_bathy_levigata_2006 import NEW_TIF, WET_FRAC_MIN, load_new, sample_new

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'model/dflowfm_v04AE_nowaves'
DST = ROOT / 'model/dflowfm_v04AE_nowaves_bathy26'
NET = 'Stagnone_dxy01_15m_net.nc'
CTRL = ROOT / 'model/dflowfm_v04AE_nowaves_ctrl'
N_PART = 8
N_PART_LOCAL = 4
DIMR_WIN = r'C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64'
RAMP_M = 500.0           # width of the transition outside the lagoon
FILL_MIN_DEPTH = 0.01    # depth floor of faces filled from a neighbour (m)

SKIP = shutil.ignore_patterns('DFM_OUTPUT_*', 'diag', '*_000?.mdu', '*_000?_*', '*.bak', '*.log',
                              'hot_*', '*.dia', 'status.sh')


def write_local_launcher(dst):
    """Launcher for the 4-core Windows workstation, next to the server one."""
    xml = (dst / 'dimr_config.xml').read_bytes().decode('utf-8')
    procs = ' '.join(str(i) for i in range(N_PART_LOCAL))
    head, rest = xml.split('<process>', 1)
    (dst / 'dimr_config_local.xml').write_bytes(
        (head + '<process>' + procs + '</process>' + rest.split('</process>', 1)[1]).encode('utf-8'))
    bat = '\r\n'.join([
        '@echo off',
        f'rem FM-only run on {N_PART_LOCAL} MPI ranks, no core pinning, no pause.',
        'cd /d "%~dp0"',
        f'set dimrset={DIMR_WIN}',
        'if not exist diag mkdir diag',
        f'call "%dimrset%\\bin\\run_dflowfm.bat" --partition:ndomains={N_PART_LOCAL}:icgsolver=6 '
        'Stagnone_dxy01_15m.mdu > diag\\partition.log 2>&1',
        'if errorlevel 1 exit /b 1',
        f'call "%dimrset%\\bin\\run_dimr_parallel.bat" {N_PART_LOCAL} dimr_config_local.xml > diag\\run.log 2>&1',
        'exit /b %ERRORLEVEL%', ''])
    (dst / 'run_local.bat').write_bytes(bat.encode('ascii'))


def main():
    control = '--control' in sys.argv[1:]
    dst = CTRL if control else DST
    if dst.exists():
        raise SystemExit(f'{dst} already exists; remove it before rebuilding')
    shutil.copytree(SRC, dst, ignore=SKIP)
    write_local_launcher(dst)
    if control:
        print('[done] control with the v04 bed,', dst)
        return

    # ---- bed level ----------------------------------------------------------
    z_new, wet_new, valid_new, tf, _ = load_new()
    with netCDF4.Dataset(DST / NET, 'r+') as nc:
        fx, fy = TO_UTM.transform(nc['mesh2d_face_x'][:].filled(np.nan), nc['mesh2d_face_y'][:].filled(np.nan))
        fz = nc['mesh2d_face_z'][:].filled(np.nan)
        tr = pd.read_csv(SRC / 'lagoon_tracer_init.xyz', sep=r'\s+', header=None, names=['lon', 'lat', 'c'])
        tx, ty = TO_UTM.transform(tr.lon.values, tr.lat.values)
        dist, j = cKDTree(np.c_[tx, ty]).query(np.c_[fx, fy])
        lagoon = (tr.c.values[j] > 0.5) & (dist < 50.0)
        new_f, wfrac, inside = sample_new(z_new, wet_new, valid_new, tf, fx, fy)
        wet = fz < 0
        core = lagoon & wet
        valid = wet & inside & (wfrac >= WET_FRAC_MIN) & np.isfinite(new_f)
        # weight 1 on the lagoon, falling linearly to 0 at RAMP_M from it
        # The difference is taken from the raster on the lagoon faces only.
        # Every other touched face inherits it from the nearest such face.
        src = core & valid
        dsrc, k = cKDTree(np.c_[fx[src], fy[src]]).query(np.c_[fx, fy])
        dcore, _ = cKDTree(np.c_[fx[core], fy[core]]).query(np.c_[fx, fy])
        w = np.where(core, 1.0, np.clip(1.0 - dcore / RAMP_M, 0.0, 1.0)) * wet
        touched = w > 0
        delta = np.where(src, new_f - fz, (new_f - fz)[src][k])
        fill = touched & ~src
        out = fz.copy()
        out[touched] = fz[touched] + w[touched] * delta[touched]
        out[fill] = np.minimum(out[fill], -FILL_MIN_DEPTH)
        nc['mesh2d_face_z'][:] = out
        nc.setncattr('bed_level_note',
                     f'mesh2d_face_z = v04 + w * ({NEW_TIF.name} - v04), w = 1 on {int(core.sum())} lagoon faces '
                     f'and linear to 0 over {RAMP_M:.0f} m outside; all other faces as in dflowfm_v04AE_nowaves')
    d = out[core] - fz[core]
    print('[bed] %d lagoon faces at weight 1 (%d of them filled from the nearest valid difference), '
          '%d faces in the %.0f m ramp' % (core.sum(), (fill & core).sum(), (touched & ~core).sum(), RAMP_M))
    print('[bed] clone minus v04 on lagoon faces: mean %+.3f m, rmse %.3f m, min %+.3f, max %+.3f' % (
        d.mean(), np.sqrt((d ** 2).mean()), d.min(), d.max()))
    print('[bed] shallowest lagoon face %.3f m, faces below 0.10 m depth: %d (v04: %d)' % (
        -out[core].max(), (out[core] > -0.10).sum(), (fz[core] > -0.10).sum()))
    assert np.array_equal(out[~touched], fz[~touched], equal_nan=True)
    assert (out[wet] < 0).all(), 'a wet face became dry'

    # ---- step between neighbouring wet faces, before and after --------------
    with netCDF4.Dataset(DST / NET) as nc:
        ef = nc['mesh2d_edge_faces'][:].filled(-1).astype(int) - int(getattr(nc['mesh2d_edge_faces'], 'start_index', 1))
    e = ef[(ef >= 0).all(axis=1)]
    e = e[wet[e[:, 0]] & wet[e[:, 1]]]
    rms = lambda v: float(np.sqrt((v ** 2).mean()))
    s0, s1 = fz[e[:, 0]] - fz[e[:, 1]], out[e[:, 0]] - out[e[:, 1]]
    for label, m in [('lagoon interior', core[e[:, 0]] & core[e[:, 1]]),
                     ('lagoon edge', core[e[:, 0]] != core[e[:, 1]]),
                     ('ramp', touched[e].any(axis=1) & ~core[e].any(axis=1))]:
        print('[step] %-16s %5d edges, rms v04 %.3f m, clone %.3f m, largest added step %.3f m' % (
            label, m.sum(), rms(s0[m]), rms(s1[m]), np.abs(s1[m] - s0[m]).max()))

    # ---- paths and launch ---------------------------------------------------
    for f in list(DST.glob('*.sh')) + list(DST.glob('*.xml')):
        txt = f.read_bytes().decode('utf-8')
        new = txt.replace('dflowfm_v04AE_nowaves"', 'dflowfm_v04AE_nowaves_bathy26"')
        new = new.replace('v04AE_nowaves:', 'v04AE_nowaves_bathy26:').replace('v04AE_nowaves launch', 'v04AE_nowaves_bathy26 launch')
        if f.name == 'launch_nowaves.sh':
            hook = 'mkdir -p diag\n'
            assert hook in new, 'launch script layout changed'
            new = new.replace(hook, hook + '# The net file differs from the parent member, so the partition is redone here.\n'
                              f'run_dflowfm.sh --partition:ndomains={N_PART}:icgsolver=6 Stagnone_dxy01_15m.mdu > diag/partition.log 2>&1\n')
            assert 'dflowfm_v04AE_nowaves_bathy26"' in new, 'working directory not patched'
        if new != txt:
            f.write_bytes(new.encode('utf-8'))
            print('[patch]', f.name)
    print('[done]', DST)


if __name__ == '__main__':
    main()
