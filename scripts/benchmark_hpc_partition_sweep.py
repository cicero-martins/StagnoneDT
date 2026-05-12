"""HPC partition sweep analyzer for D-Flow FM runs.

Parses *.dia files from one or more completed (or in-progress) FM runs and
prints a comparison table with effective real-time-per-sim-day, cell count
imbalance, PETSc problem size, and the OpenMP / icgSolver / partition-count
status. Use this to empirically pick the optimal MPI partition count for a
given mesh on the dual-socket Xeon 6430 Workstation.

Grounded in PRACE WP284 (D-Flow FM scaling) and WP177 (FM+SWAN coupling) -
see memory hpc_optimization_xeon_64core.md for the rationale.

The .dia files this script understands are the ones produced by
FM Suite 2026.01 in DIMR Online runs. Tested against the 16-MPI v04AE run
from 2026-05-08. Note: the .dia does NOT include MPI_Allreduce / KSPSolve
timings unless `WriteDetailedTimers = 1` is set in the MDU; if you want
those metrics, enable that flag and re-run.

How to run the sweep itself:
  - Easiest: scripts/benchmark_partition_sweep.bat runs the sweep across
    nPart in {4, 8, 16, 32} by calling model/dflowfm_v04AE/run_model.bat
    with each value, then invokes this analyzer on the archived outputs.
  - Manual: edit run_model.bat nPart (or pass it as %1), run it, rename
    DFM_OUTPUT_* to DFM_OUTPUT_*_npart_<N>, repeat, then run:
        python scripts/benchmark_hpc_partition_sweep.py \\
            model/dflowfm_v04AE/DFM_OUTPUT_*_npart_*
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Progress-line format (per partition):
# ** INFO   :           1d 12:00:00          7d 12:00:00          0d  0:17:18          0d  1:26:18       2160    16.7%     7.59494
RE_PROGRESS = re.compile(
    r"\*\*\s*INFO\s*:\s*"
    r"(\d+)d\s+(\d+):(\d+):(\d+)\s+"   # sim time done
    r"\d+d\s+\d+:\d+:\d+\s+"            # sim time left (skip)
    r"(\d+)d\s+(\d+):(\d+):(\d+)\s+"    # real time used
    r"\S+d\s+\S+:\S+:\S+\s+"            # real time left (may contain ??)
    r"\d+\s+"                            # steps left
    r"([\d.]+)%"                         # complete %
)

RE_NETCELLS = re.compile(r"nr of netcells\s*\(\s*\)\s*:\s*(\d+)")
RE_FLOWNODES = re.compile(r"nr of internal flownodes\s*\(\s*\)\s*:\s*(\d+)")
RE_NOGAUSS_NOCG = re.compile(r"nogauss\s*,\s*nocg\s*:\s*(\d+)\s+(\d+)")
RE_ICGSOLVER = re.compile(r"Icgsolver\s*=\s*(\d+)")
RE_OPENMP_DISABLED = re.compile(r"OpenMP\s+disabled", re.IGNORECASE)
RE_OPENMP_ENABLED = re.compile(r"OpenMP\s+enabled|OpenMP threads", re.IGNORECASE)
RE_FATAL = re.compile(r"\*\*\s*FATAL", re.IGNORECASE)
RE_GHOST = re.compile(r"added node-based ghostcells:\s*(\d+)")
RE_BL_TYPE = re.compile(r"BedlevType\s*=\s*(\d+)")


def hms_to_seconds(d: str, h: str, m: str, s: str) -> int:
    return int(d) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)


def parse_dia(path: Path) -> dict:
    """Extract benchmark metrics from a single .dia file."""
    out = {
        'file': path.name,
        'last_sim_s': None,
        'last_real_s': None,
        'last_pct': None,
        'completed': False,
        'fatal_count': 0,
        'netcells': None,
        'flownodes': None,
        'petsc_unknowns': None,
        'icgsolver': None,
        'openmp_disabled': False,
        'ghost_added': 0,
    }
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except OSError as e:
        out['error'] = f'read failed: {e}'
        return out

    out['fatal_count'] = len(RE_FATAL.findall(text))

    # Last progress line
    last = None
    for m in RE_PROGRESS.finditer(text):
        last = m
    if last is not None:
        out['last_sim_s'] = hms_to_seconds(last.group(1), last.group(2), last.group(3), last.group(4))
        out['last_real_s'] = hms_to_seconds(last.group(5), last.group(6), last.group(7), last.group(8))
        out['last_pct'] = float(last.group(9))
        out['completed'] = out['last_pct'] >= 99.9

    # First netcells / flownodes count (initialization block)
    m = RE_NETCELLS.search(text)
    if m:
        out['netcells'] = int(m.group(1))
    m = RE_FLOWNODES.search(text)
    if m:
        out['flownodes'] = int(m.group(1))

    m = RE_NOGAUSS_NOCG.search(text)
    if m:
        out['petsc_unknowns'] = int(m.group(1)) + int(m.group(2))

    m = RE_ICGSOLVER.search(text)
    if m:
        out['icgsolver'] = int(m.group(1))

    out['openmp_disabled'] = bool(RE_OPENMP_DISABLED.search(text))

    out['ghost_added'] = sum(int(g) for g in RE_GHOST.findall(text))
    return out


def summarize_run(run_dir: Path) -> dict:
    """Aggregate per-partition .dia files for one run into one summary row."""
    dias = sorted(run_dir.glob('*.dia'))
    if not dias:
        return {'run': run_dir.name, 'note': 'no *.dia found', 'npart': 0}

    rows = [parse_dia(p) for p in dias]
    npart = len(rows)

    netcells = [r['netcells'] for r in rows if r['netcells'] is not None]
    flownodes = [r['flownodes'] for r in rows if r['flownodes'] is not None]
    petsc = [r['petsc_unknowns'] for r in rows if r['petsc_unknowns'] is not None]
    last_real = [r['last_real_s'] for r in rows if r['last_real_s'] is not None]
    last_sim = [r['last_sim_s'] for r in rows if r['last_sim_s'] is not None]
    last_pct = [r['last_pct'] for r in rows if r['last_pct'] is not None]
    fatal_total = sum(r['fatal_count'] for r in rows)
    ghost_total = sum(r['ghost_added'] for r in rows)
    openmp_disabled_any = any(r['openmp_disabled'] for r in rows)

    summary = {
        'run': run_dir.name,
        'npart': npart,
        'fatal_total': fatal_total,
        'icgsolver': rows[0]['icgsolver'] if rows else None,
        'openmp_disabled': openmp_disabled_any,
        'ghost_total': ghost_total,
    }

    if netcells:
        summary['cells_max'] = max(netcells)
        summary['cells_min'] = min(netcells)
        summary['cells_mean'] = sum(netcells) / len(netcells)
        summary['cells_total'] = sum(netcells)
        summary['cell_imbalance'] = max(netcells) / summary['cells_mean']
    else:
        summary.update({k: None for k in
                        ['cells_max', 'cells_min', 'cells_mean', 'cells_total', 'cell_imbalance']})

    if petsc:
        summary['petsc_max'] = max(petsc)
        summary['petsc_mean'] = sum(petsc) / len(petsc)
    else:
        summary['petsc_max'] = summary['petsc_mean'] = None

    if last_real and last_sim:
        # Take the max across partitions for both (slowest rank dominates wall time).
        real_max = max(last_real)
        sim_max = max(last_sim)
        pct_max = max(last_pct) if last_pct else None
        summary['last_real_s'] = real_max
        summary['last_sim_s'] = sim_max
        summary['last_pct'] = pct_max
        # Effective rate: real seconds per simulated day
        if sim_max > 0:
            summary['real_per_simday_s'] = real_max / (sim_max / 86400.0)
        else:
            summary['real_per_simday_s'] = None
    else:
        summary['last_real_s'] = summary['last_sim_s'] = summary['last_pct'] = None
        summary['real_per_simday_s'] = None

    return summary


def fmt(v, kind: str) -> str:
    if v is None:
        return 'N/A'
    if kind == 'int':
        return f'{int(v)}'
    if kind == 'time':
        if v >= 3600:
            return f'{v/3600:.2f}h'
        if v >= 60:
            return f'{v/60:.1f}min'
        return f'{v:.1f}s'
    if kind == 'pct':
        return f'{v:.1f}%'
    if kind == 'ratio':
        return f'{v:.2f}'
    if kind == 'bool':
        return 'YES' if v else 'no'
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_dirs', nargs='+', type=Path,
                    help='One or more DFM_OUTPUT_* directories (or any dir containing *.dia files)')
    args = ap.parse_args()

    summaries = []
    for d in args.run_dirs:
        if not d.is_dir():
            print(f'WARN: {d} is not a directory, skipping', file=sys.stderr)
            continue
        summaries.append(summarize_run(d))

    if not summaries:
        print('No valid run directories provided.', file=sys.stderr)
        return 1

    print()
    print(f'{"run":<40} {"nP":>3} {"icgS":>4} {"OMP_off":>7} {"cellsMax":>9} '
          f'{"cellsMean":>9} {"cellImb":>7} {"petscMax":>8} {"pct":>6} '
          f'{"realUsed":>9} {"r/simday":>9} {"fatal":>5}')
    print('-' * 140)
    for s in summaries:
        print(f'{s["run"][:40]:<40} '
              f'{fmt(s["npart"], "int"):>3} '
              f'{fmt(s.get("icgsolver"), "int"):>4} '
              f'{fmt(s.get("openmp_disabled"), "bool"):>7} '
              f'{fmt(s.get("cells_max"), "int"):>9} '
              f'{fmt(s.get("cells_mean"), "int"):>9} '
              f'{fmt(s.get("cell_imbalance"), "ratio"):>7} '
              f'{fmt(s.get("petsc_max"), "int"):>8} '
              f'{fmt(s.get("last_pct"), "pct"):>6} '
              f'{fmt(s.get("last_real_s"), "time"):>9} '
              f'{fmt(s.get("real_per_simday_s"), "time"):>9} '
              f'{fmt(s["fatal_total"], "int"):>5}')

    print()
    print('Columns:')
    print('  nP        = number of partitions (counts *.dia files)')
    print('  icgS      = icgSolver actually used at runtime (6 = PETSc)')
    print('  OMP_off   = YES if any partition logged "OpenMP disabled."')
    print('  cellsMax  = largest partition by netcells (drives slowest rank)')
    print('  cellsMean = mean netcells per partition')
    print('  cellImb   = cellsMax / cellsMean. > 1.20 = poor (WP284 threshold)')
    print('  petscMax  = max PETSc unknowns (nogauss + nocg) per partition')
    print('              WP284 says PETSc stops scaling below ~20 000 unknowns')
    print('  pct       = highest % complete reached (across partitions)')
    print('  realUsed  = max real time used so far across partitions')
    print('  r/simday  = real-seconds-per-simulated-day (KEY METRIC; lower = faster)')
    print('  fatal     = sum of "** FATAL" lines across partitions')
    return 0


if __name__ == '__main__':
    sys.exit(main())
