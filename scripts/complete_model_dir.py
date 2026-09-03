"""Fill in the shared forcing a pulled model directory deliberately lacks.

pull_model_inputs.sh leaves eighteen files on the wire because they are
identical in every v04AE-derived member and one copy is already tracked here, in
model/dflowfm_v04AE_nowaves. That saves 71 MB per member and 1.2 GB over the
ensemble, at the cost of directories that will not run until the files are put
back. This puts them back.

    python scripts/complete_model_dir.py model/_veg_waves_dm
    python scripts/complete_model_dir.py --check model/_veg_waves_dm
    python scripts/complete_model_dir.py --all

--check reports without writing, and is also the guard on the arrangement
itself. A file only belongs on the shared list while it is genuinely identical
everywhere, so a member that has grown its own version must be caught before the
baseline is copied over it.
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / 'model' / 'dflowfm_v04AE_nowaves'
SHARED = ROOT / 'scripts' / 'model_shared_inputs.txt'


def shared_paths():
    out = []
    for line in SHARED.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(line)
    return out


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def complete(target, paths, check):
    """Return (copied, present, diverged, absent_from_baseline)."""
    copied, present, diverged, absent = [], [], [], []
    for rel in paths:
        src, dst = BASELINE / rel, target / rel
        if not src.exists():
            absent.append(rel)
            continue
        if dst.exists():
            (present if md5(dst) == md5(src) else diverged).append(rel)
            continue
        if not check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        copied.append(rel)
    return copied, present, diverged, absent


def report(target, res, check):
    copied, present, diverged, absent = res
    verb = 'would copy' if check else 'copied'
    bits = [f'{verb} {len(copied)}']
    if present:
        bits.append(f'{len(present)} already matched')
    if diverged:
        bits.append(f'{len(diverged)} DIVERGED')
    if absent:
        bits.append(f'{len(absent)} missing from the baseline')
    print(f'  {target.name:42s} {", ".join(bits)}')
    for rel in diverged:
        print(f'      diverged, left untouched: {rel}')
    for rel in absent:
        print(f'      not in the baseline:      {rel}')
    return not (diverged or absent)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dirs', nargs='*', type=Path)
    ap.add_argument('--check', action='store_true',
                    help='report without writing')
    ap.add_argument('--all', action='store_true',
                    help='every model directory missing shared inputs')
    args = ap.parse_args()

    paths = shared_paths()
    if not BASELINE.is_dir():
        sys.exit(f'baseline not found: {BASELINE}')

    targets = list(args.dirs)
    if args.all:
        # A directory the pull left incomplete is missing every one of the
        # eighteen. An older model version that carries its own forcing is
        # missing some and has its own copies of the rest, and is not in scope
        # here however much it may look like a candidate.
        targets = sorted(
            d for d in (ROOT / 'model').iterdir()
            if d.is_dir() and d != BASELINE
            and (d / 'Stagnone_dxy01_15m.mdu').exists()
            and not any((d / rel).exists() for rel in paths))
    if not targets:
        sys.exit('nothing to do (pass directories, or --all)')

    print(f'baseline {BASELINE.relative_to(ROOT)}, {len(paths)} shared inputs')
    ok = True
    for t in targets:
        t = t if t.is_absolute() else ROOT / t
        if not t.is_dir():
            print(f'  {t.name:42s} not a directory')
            ok = False
            continue
        ok &= report(t, complete(t, paths, args.check), args.check)
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
