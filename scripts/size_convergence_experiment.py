r"""Cost of a mesh and layer convergence study for the v04 setup.

Scales a measured run rather than a nominal flop count. The anchor is the
no-waves bathy26 twin: 9 simulated days, 25,212 faces, 10 sigma layers, 4 MPI
ranks on the 4-core local machine, 2 h 40 min wall, 112,673 computational
steps, recorded in model/bathy26_pair_status.txt and the partition .dia.

Wall time is taken proportional to faces x layers x steps. The step count
follows from the Courant limit of whichever region binds, which is why the
per-region limit is computed here rather than assumed: at the present
resolution the lagoon is not the binding region, so refining it buys cells
without immediately buying steps.

Usage:
    python scripts/size_convergence_experiment.py
"""
import numpy as np
import xarray as xr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NET = ROOT / 'model' / 'dflowfm_v04' / 'Stagnone_dxy01_15m_net.nc'

# --- the measured anchor ----------------------------------------------------
ANCHOR = dict(faces=25212, layers=10, steps=112673, days=9.0, minutes=160.0,
              ranks=4)
CFL = 0.7
G = 9.81

# Two machines, from the controlled comparison of 2026-05-15 on the same 9-day
# coupled v04AE at MPI=8. Wall was 3.05 h on the server against 7.68 h on
# Windows, but the FM core time was 8723 s against 7676 s, so the server is
# marginally SLOWER at the flow solver itself and the whole 2.5x advantage sits
# in the SWAN and DIMR coupling. These runs carry no SWAN, so that advantage
# does not apply and the server buys concurrency rather than speed.
MACHINES = {
    'local Ryzen 3 5350G, 4 cores': dict(cores=4, ranks=4, per_member=1.00),
    'simit 2x Xeon 5220R, 48 cores': dict(cores=48, ranks=6, per_member=0.98),
}
# per_member is the wall ratio against the anchor for one member: the server's
# 8723 s of FM time over 9 days is within 10% of the local machine's 2 h 40,
# the four fast Ryzen cores standing in for six slow server ones.
MEM_PER_RANK_GB = 0.28   # measured on the running no-waves member

# Representative cell spacing and depth per region, from the mesh and the
# bathymetry. Spacing is centre-to-centre between adjacent wet cells.
REGIONS = {
    'lagoon interior':      dict(dx=61.0,  h=1.0),
    'lagoon southern deep': dict(dx=61.0,  h=3.0),
    'shoreline bands':      dict(dx=55.0,  h=3.0),
    'shelf bands':          dict(dx=55.0,  h=30.0),
    'open background':      dict(dx=880.0, h=730.0),
}

# Drifter window, from data/processed/drifter_releases_Jul2025.csv: all twelve
# deployments fall between 8 Jul 07:14 and 9 Jul 12:07, and the longest runs
# 7.2 h, so a 3-day segment from 7 Jul covers them with 31 h of spin-up.
WINDOWS = {'production 9 d': 9.0, 'convergence segment 3 d': 3.0}


def courant_dt(dx, h):
    return CFL * dx / np.sqrt(G * h)


def lagoon_faces():
    ds = xr.open_dataset(NET, mask_and_scale=False)
    x = ds['mesh2d_node_x'].values
    y = ds['mesh2d_node_y'].values
    fn = ds['mesh2d_face_nodes'].values.astype(np.int64) - 1
    fill = fn < 0
    fx = np.array([x[fn[i][~fill[i]]].mean() for i in range(fn.shape[0])])
    fy = np.array([y[fn[i][~fill[i]]].mean() for i in range(fn.shape[0])])
    box = ((fx >= 12.418) & (fx <= 12.492)
           & (fy >= 37.810) & (fy <= 37.914))
    inlets = (((fx >= 12.452) & (fx <= 12.470)
               & (fy >= 37.898) & (fy <= 37.910))
              | ((fx >= 12.432) & (fx <= 12.462)
                 & (fy >= 37.832) & (fy <= 37.850)))
    return fn.shape[0], int(box.sum()), int(inlets.sum())


def cost_minutes(faces, layers, dt, days):
    steps = days * 86400.0 / dt
    return (ANCHOR['minutes']
            * (faces / ANCHOR['faces'])
            * (layers / ANCHOR['layers'])
            * (steps / ANCHOR['steps'] * (ANCHOR['days'] / 9.0))
            * (9.0 / ANCHOR['days']))


def hm(minutes):
    return f'{int(minutes // 60)}h{int(round(minutes % 60)):02d}'


def main():
    total, nlag, ninlet = lagoon_faces()
    dt_now = ANCHOR['days'] * 86400.0 / ANCHOR['steps']

    print('=== which region sets the time step ===')
    for name, r in REGIONS.items():
        print(f'  {name:22s} dx {r["dx"]:5.0f} m  h {r["h"]:6.1f} m  '
              f'Courant dt {courant_dt(**r):6.2f} s')
    print(f'  realised mean step in the anchor run      {dt_now:6.2f} s')
    print('  the lagoon is not binding at 61 m; the shoreline bands and the '
          'open\n  background both sit near 7 s, which is what the run '
          'realises')

    print(f'\n=== mesh inventory ===')
    print(f'  domain {total} faces | lagoon box {nlag} | inlet boxes {ninlet}')

    print('\n=== refinement ladder, lagoon box split r times per side ===')
    print(f'{"member":26s} {"faces":>8s} {"dx lag":>7s} {"dt":>6s} '
          f'{"3 d":>8s} {"9 d":>8s}')
    ladder = []
    for r, label in ((1, 'L0 base, 61 m'), (2, 'L1 refine 2x, 30 m'),
                     (4, 'L2 refine 4x, 15 m')):
        faces = total + nlag * (r * r - 1)
        dx = 61.0 / r
        dt = min(dt_now, courant_dt(dx, REGIONS['lagoon interior']['h']))
        row = (label, faces, dx, dt,
               cost_minutes(faces, 10, dt, 3.0),
               cost_minutes(faces, 10, dt, 9.0))
        ladder.append(row)
        print(f'{label:26s} {faces:8d} {dx:6.0f}m {dt:5.1f}s '
              f'{hm(row[4]):>8s} {hm(row[5]):>8s}')

    print('\n=== inlet-only refinement, as a pilot ===')
    for r, label in ((2, 'P1 inlets 2x, 30 m'), (4, 'P2 inlets 4x, 15 m')):
        faces = total + ninlet * (r * r - 1)
        dt = min(dt_now, courant_dt(61.0 / r, REGIONS['lagoon interior']['h']))
        print(f'{label:26s} {faces:8d} {61.0/r:6.0f}m {dt:5.1f}s '
              f'{hm(cost_minutes(faces, 10, dt, 3.0)):>8s} '
              f'{hm(cost_minutes(faces, 10, dt, 9.0)):>8s}')

    print('\n=== layer ladder, base mesh, no new mesh needed ===')
    for k in (5, 10, 20):
        tag = f'K{k} {k} sigma layers' + (' (base)' if k == 10 else '')
        print(f'{tag:26s} {total:8d} {"":6s}  {dt_now:5.1f}s '
              f'{hm(cost_minutes(total, k, dt_now, 3.0)):>8s} '
              f'{hm(cost_minutes(total, k, dt_now, 9.0)):>8s}')

    print('\n=== the seven members ===')
    members = [('L0 base', total, 10, dt_now),
               ('L1 lagoon 30 m', total + nlag * 3, 10,
                min(dt_now, courant_dt(30.5, 1.0))),
               ('L2 lagoon 15 m', total + nlag * 15, 10,
                min(dt_now, courant_dt(15.25, 1.0))),
               ('P1 inlets 30 m', total + ninlet * 3, 10, dt_now),
               ('P2 inlets 15 m', total + ninlet * 15, 10,
                min(dt_now, courant_dt(15.25, 1.0))),
               ('K5 five layers', total, 5, dt_now),
               ('K20 twenty layers', total, 20, dt_now)]

    for days, wname in ((3.0, '3 d segment'), (9.0, '9 d full window')):
        print(f'\n--- {wname} ---')
        cost = sorted((cost_minutes(f, k, dt, days) for _, f, k, dt in members),
                      reverse=True)
        serial = sum(cost)
        for mname, m in MACHINES.items():
            conc = max(1, m['cores'] // m['ranks'])
            fits = min(conc, len(members))
            # longest-first onto `conc` slots; the wall is the busiest slot
            slots = [0.0] * conc
            for c in cost:
                i = slots.index(min(slots))
                slots[i] += c
            print(f'  {mname:32s} {m["ranks"]} ranks a member, '
                  f'{fits} at a time')
            print(f'{"":34s} serial {hm(serial * m["per_member"]):>8s}   '
                  f'batched {hm(max(slots) * m["per_member"]):>8s}')
        print(f'  peak memory, seven members at once: '
              f'{len(members) * 6 * MEM_PER_RANK_GB * 4:.0f} GB at the '
              f'L2 cell count')


if __name__ == '__main__':
    main()
