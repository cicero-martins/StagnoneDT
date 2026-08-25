"""Feasibility test: does D-Flow FM 1.2.184 accept trachytope formula 156?

Formula 156 (Jarvela 2014) and 155 (Vastila & Jarvela 2017) implement
velocity-dependent vegetation resistance:

    phi = C_D * n * (|U| / U_chi) ** chi
    lambda = phi / h * (C_b / C)**2          -> momentum sink -lambda/2 * u^2

They are in the kernel (trtrou.f90) and accepted by the .ttd reader
(rdtrt.f90: nropar(155)=10, nropar(156)=6), merged from the Aalto University
research branch on 2019-04-05 -- six years before the 1.2.184 build we run.
Neither manual shipped with 2026.01 or the 2026.02 changelist mentions them,
so acceptance by OUR binary has to be established empirically rather than read.

This builds two short FM-only runs off v04AE_vr and compares them:

    _trt153   control, the Baptist 1 classes already in use  -> depth-driven
    _trt156   same classes restated as Jarvela               -> velocity-driven

and checks mesh2d_cftrt ("Manning roughness from trachytopes", per edge per
time) against velocity.  The control should show no velocity dependence; the
test should show a clear negative one.

The runs are FM-only (waveModelNr=0) and morphology-free: neither waves nor
sediment enter the trachytope formula, and dropping them makes the test cheap.

    python scripts/test_trachytope_156_feasibility.py --setup
    python scripts/test_trachytope_156_feasibility.py --run
    python scripts/test_trachytope_156_feasibility.py --check
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'model' / 'dflowfm_v04AE_vr'
RUNS = {'trt153': ROOT / 'model' / '_trt_test_153',
        'trt156': ROOT / 'model' / '_trt_test_156'}
MDU_NAME = 'Stagnone_dxy01_15m.mdu'
TTD_NAME = 'trachytopes.ttd'

DIMRSET = Path('C:/Program Files/Deltares/Delft3D FM Suite 2026.01 HMWQ'
               '/plugins/DeltaShell.Dimr/kernels/x64')
FM_CLI = DIMRSET / 'bin' / 'dflowfm-cli.exe'


def fm_env():
    """bin, lib and share/bin all have to be on PATH.

    Calling the exe directly without them fails at load time on
    pthreadVC2.dll -- run_model.bat sets this up and is easy to bypass.
    """
    import os
    env = dict(os.environ)
    pre = os.pathsep.join(str(DIMRSET / p) for p in ('bin', 'lib', 'share/bin'))
    env['PATH'] = pre + os.pathsep + env.get('PATH', '')
    return env

# 6 h is enough for the tide to swing the lagoon through a range of speeds,
# which is the whole point -- a flat-velocity window would prove nothing.
STOP = '20250701060000'
MAP_INTERVAL = 900.0        # 15 min -> 25 frames

# Anchor U_chi on the lagoon's median current (0.046 m/s, measured from the
# v04AE_vr_dens fields).  At that speed (|U|/U_chi)**chi = 1, so the Jarvela
# drag coefficient equals the Baptist one and the two classes agree; they
# diverge above and below it.  chi = -1.56 is Ciraolo et al. (2006) Eq. 22.
U_CHI = 0.05
CHI = -1.56

# Baptist 1 (153) params are: h_v | n=mD | C_D | C_b
# Jarvela  (156) params are: h_v | n=mD | C_D | U_chi | chi | C_b
TTD_156 = f"""\
* Trachytope definitions -- FEASIBILITY TEST for formula 156 (Jarvela 2014)
* Same vegetation classes as trachytopes.ttd, restated with a velocity
* exponent.  156 params: h_v[m] n=mD[1/m] C_D[-] U_chi[m/s] chi[-] C_b[m^0.5/s]
* U_chi anchored on the lagoon median current so that the drag coefficient
* matches the Baptist value there; chi from Ciraolo et al. (2006) Eq. 22.
  1    53    0.0200
  2   156    0.150    3.200    1.00    {U_CHI}    {CHI}    45.0
  3   156    0.500    5.000    0.80    {U_CHI}    {CHI}    45.0
  4    53    0.0280
"""

# Everything that must NOT travel into a clone.  Stale .arl/.ttd and SWAN hot
# files have bitten this project before; partitioned files and restarts are
# machine-bound.
EXCLUDE_DIRS = {'DFM_OUTPUT_Stagnone_dxy01_15m', 'wave', 'DFM_OUTPUT'}
EXCLUDE_PAT = re.compile(r'(_\d{4}_|_\d{4}\.|\.bak|hot_.*\.nc|_rst\.nc|'
                         r'\.dia$|\.log$|diag)', re.I)


def patch_mdu(text):
    """Short, FM-only, morphology-free, and writing what the test reads."""
    subs = [
        (r'(?im)^(\s*stopDateTime\s*=\s*)\S+', r'\g<1>' + STOP),
        (r'(?im)^(\s*waveModelNr\s*=\s*)\S+', r'\g<1>0'),
        (r'(?im)^(\s*Sedimentmodelnr\s*=\s*)\S+', r'\g<1>0'),
        (r'(?im)^(\s*mapInterval\s*=\s*)\S+', r'\g<1>' + str(MAP_INTERVAL)),
        (r'(?im)^(\s*wrimap_chezy\s*=\s*)\S+', r'\g<1>1'),
        (r'(?im)^(\s*wrimap_velocity_magnitude\s*=\s*)\S+', r'\g<1>1'),
        (r'(?im)^(\s*rstInterval\s*=\s*)\S+', r'\g<1>0'),
        (r'(?im)^(\s*hisInterval\s*=\s*)\S+', r'\g<1>0'),
    ]
    for pat, rep in subs:
        text, n = re.subn(pat, rep, text)
        if n == 0:
            print(f'  ! no MDU line matched {pat!r}')
    return text


def setup():
    for tag, dst in RUNS.items():
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        n = 0
        for p in SRC.iterdir():
            if p.is_dir():
                if p.name in EXCLUDE_DIRS:
                    continue
                shutil.copytree(p, dst / p.name)
                n += 1
                continue
            if EXCLUDE_PAT.search(p.name):
                continue
            shutil.copy2(p, dst / p.name)
            n += 1

        mdu = dst / MDU_NAME
        mdu.write_text(patch_mdu(mdu.read_text(encoding='utf-8',
                                               errors='ignore')),
                       encoding='utf-8')
        if tag == 'trt156':
            (dst / TTD_NAME).write_text(TTD_156, encoding='utf-8')
        print(f'{tag}: {n} entries -> {dst}')
        print(f'   ttd = {(dst / TTD_NAME).read_text().splitlines()[-3].strip()}')


def run():
    if not FM_CLI.exists():
        sys.exit(f'dflowfm-cli not found at {FM_CLI}')
    # 156 first: it is the one that can be rejected outright, and a rejection
    # lands during input parsing, within seconds.
    for tag in ('trt156', 'trt153'):
        d = RUNS[tag]
        print(f'--- {tag} ---')
        r = subprocess.run([str(FM_CLI), '--autostartstop', MDU_NAME],
                           cwd=d, text=True, capture_output=True, env=fm_env())
        tail = (r.stdout or '')[-1500:] + (r.stderr or '')[-1500:]
        print(f'exit {r.returncode}')
        # A rejected formula shows up here, during trachytope input parsing.
        for line in tail.splitlines():
            if re.search(r'error|fatal|trachytope|abort|invalid', line, re.I):
                print('   ', line.strip()[:150])
        (d / 'run_tail.txt').write_text(tail, encoding='utf-8')


def check():
    import numpy as np
    import xarray as xr

    for tag, d in RUNS.items():
        outs = sorted(d.glob('DFM_OUTPUT_*/*_map.nc'))
        print(f'=== {tag} ===')
        if not outs:
            print('  no map.nc -- run did not produce output')
            continue
        ds = xr.open_dataset(outs[0])
        if 'mesh2d_cftrt' not in ds:
            print('  mesh2d_cftrt absent')
            ds.close()
            continue
        cf = ds['mesh2d_cftrt'].values                 # (time, edge)
        print(f'  frames={cf.shape[0]}  edges={cf.shape[1]}')
        var_t = np.nanstd(cf, axis=0)
        moving = np.isfinite(var_t) & (var_t > 1e-9)
        print(f'  edges whose roughness varies in time: {moving.sum()} '
              f'({100*moving.mean():.1f}%)')
        if 'mesh2d_ucmag' in ds:
            u = ds['mesh2d_ucmag'].values
            if u.ndim == 3:
                u = u[:, :, -1]
            print(f'  |U| range {np.nanmin(u):.3f} - {np.nanmax(u):.3f} m/s')
        ds.close()
    print('\nExpectation: the 153 control varies only where depth varies; '
          '156 should vary far more widely, and negatively with |U|.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--setup', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if not (a.setup or a.run or a.check):
        ap.error('pick --setup, --run or --check')
    if a.setup:
        setup()
    if a.run:
        run()
    if a.check:
        check()
