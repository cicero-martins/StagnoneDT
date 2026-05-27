"""Assemble model/dflowfm_v05/ for a cold-start diagnostic run.

Strategy: clone v04AE config skeleton, REPLACE the boundary configuration
with a fresh minimal _new.ext (WL/sal/temp + meteo only), patch MDU paths
and key flags.

Initial scope: FM-only (no SWAN coupling), no D-Morph, no tracers, no
laterals -- enough to test that the new mesh + bathy + BCs run.
SWAN can be wired in a later iteration.

Inputs:
  data/processed/mesh_v05/Stagnone_v05_net.nc  (mesh with face_z)
  data/processed/mesh_v05/Stagnone_v05.pli      (boundary, 333 nodes)
  model/dflowfm_v05/*_CMEMS_Stagnone_v05.bc     (already from build_cmems_bc_v05)
  model/dflowfm_v04AE_d10d12/era5_*.nc          (meteo, Jul 1-13)
  model/dflowfm_v04AE_d10d12/wind_blendedAE_*.nc (wind blend, Jul 1-13)

Output: model/dflowfm_v05/ with MDU + ext + meteo .nc + BC .bc + net.nc
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_V04 = PROJECT_ROOT / 'model' / 'dflowfm_v04AE'
SRC_D10D12 = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_d10d12'
MESH_DIR = PROJECT_ROOT / 'data' / 'processed' / 'mesh_v05'
DST = PROJECT_ROOT / 'model' / 'dflowfm_v05'

MDU_NAME = 'Stagnone_v05.mdu'
EXT_NEW_NAME = 'Stagnone_v05_new.ext'
EXT_OLD_NAME = 'Stagnone_v05_old.ext'
PLI_NAME = 'Stagnone_v05.pli'
NET_NAME = 'Stagnone_v05_net.nc'

# Diagnostic 3-day window: Jul 1 -> Jul 4 2025
T_START_REL = 0.0
T_STOP_REL  = 3 * 86400.0   # 3 days in seconds
STOP_DATE   = '20250704000000'
REF_DATE    = '20250701'    # refDate in v04AE MDU

# Meteo forcings to copy from d10d12 (covers Jul 1-13, plenty of margin)
METEO_FILES = [
    'era5_msl_20250701to20250713_ERA5.nc',
    'era5_chnk_20250701to20250713_ERA5.nc',
    # wind blend AE-only
    'wind_blendedAE_u10n_20250701to20250713.nc',
    'wind_blendedAE_v10n_20250701to20250713.nc',
]

# MDU patches (key=value lines to update; preserve formatting around them)
MDU_PATCHES = {
    'netFile': NET_NAME,
    'dryPointsFile': '',
    'iniFieldFile': '',
    'waterLevIniFile': '',
    'landBoundaryFile': '',
    'extForceFile': EXT_OLD_NAME,
    'extForceFileNew': EXT_NEW_NAME,
    'Sedimentmodelnr': '0',
    'MorFile': '',
    'SedFile': '',
    'waveModelNr': '0',
    'tStart': str(T_START_REL),
    'tStop': str(T_STOP_REL),
    'stopDateTime': STOP_DATE,
    # Keep refDate from v04AE (20250701)
    'obsFile': '',  # avoid hydrolib validation error (v04AE obs.xyn not present in v05 dir)
}

# Lines to comment out (hydrolib doesn't recognise; FM kernel still accepts).
MDU_COMMENT_OUT = {'hminlw'}


def patch_mdu_line(line: str) -> str:
    """If line is 'key = ...', maybe replace value per MDU_PATCHES. Preserve
    indentation, comments after '#'."""
    m = re.match(r'^(\s*)(\w+)(\s*=\s*)([^#\n]*)(#.*)?$', line)
    if not m:
        return line
    indent, key, eq, val, comment = m.groups()
    if key in MDU_COMMENT_OUT:
        return f'# [v05 disabled by setup_model_v05.py] {line}'
    if key in MDU_PATCHES:
        new_val = MDU_PATCHES[key]
        # preserve column alignment of value (best-effort: same width as old val)
        pad = len(val) - len(val.lstrip())
        old_clean = val.strip()
        # Replace, keep value column width approximately
        width = max(len(old_clean), len(new_val))
        new_val_padded = new_val.ljust(width)
        return f'{indent}{key}{eq}{new_val_padded:<{len(val.rstrip()) if val.rstrip() else len(new_val)}}{comment or ""}\n'.rstrip() + '\n'
    return line


def write_ext_new(path: Path):
    """Minimal _new.ext for FM-only v05 diagnostic: WL/sal/temp boundary."""
    content = f"""# v05 minimal ext (FM-only diagnostic).  Written by setup_model_v05.py.

[Boundary]
quantity     = waterlevelbnd
locationFile = {PLI_NAME}
forcingFile  = waterlevelbnd_CMEMS_Stagnone_v05.bc

[Boundary]
quantity     = salinitybnd
locationFile = {PLI_NAME}
forcingFile  = salinitybnd_CMEMS_Stagnone_v05.bc

[Boundary]
quantity     = temperaturebnd
locationFile = {PLI_NAME}
forcingFile  = temperaturebnd_CMEMS_Stagnone_v05.bc

[Meteo]
quantity        = windx
forcingFile     = wind_blendedAE_u10n_20250701to20250713.nc
forcingFileType = netcdf
operand         = O

[Meteo]
quantity        = windy
forcingFile     = wind_blendedAE_v10n_20250701to20250713.nc
forcingFileType = netcdf
operand         = O

[Meteo]
quantity        = airpressure
forcingFile     = era5_msl_20250701to20250713_ERA5.nc
forcingFileType = netcdf
operand         = O

[Meteo]
quantity        = charnock
forcingFile     = era5_chnk_20250701to20250713_ERA5.nc
forcingFileType = netcdf
operand         = O
"""
    path.write_text(content, encoding='ascii')


def write_ext_old(path: Path):
    """Legacy _old.ext format. For FM-only minimal, we leave it empty
    (no QUANTITY= entries) so FM uses only _new.ext content."""
    path.write_text('* v05 minimal _old.ext (legacy meteo format; empty for FM-only diagnostic).\n',
                    encoding='ascii')


def main():
    if not (MESH_DIR / NET_NAME).exists():
        raise SystemExit(f'Mesh not found: {MESH_DIR / NET_NAME}')
    if not (MESH_DIR / PLI_NAME).exists():
        raise SystemExit(f'PLI not found: {MESH_DIR / PLI_NAME}')

    DST.mkdir(parents=True, exist_ok=True)
    print(f'Target: {DST}')

    # 1. Copy net.nc and .pli
    for src, name in [(MESH_DIR / NET_NAME, NET_NAME),
                       (MESH_DIR / PLI_NAME, PLI_NAME)]:
        dst = DST / name
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)
            print(f'  copy: {name} ({dst.stat().st_size/1024:.0f} KB)')
        else:
            print(f'  [skip up-to-date] {name}')

    # 2. Copy meteo files from d10d12
    for f in METEO_FILES:
        src = SRC_D10D12 / f
        dst = DST / f
        if not src.exists():
            print(f'  [WARN missing source] {src}')
            continue
        if not dst.exists():
            shutil.copy2(src, dst)
            print(f'  copy meteo: {f} ({dst.stat().st_size/1e6:.1f} MB)')
        else:
            print(f'  [skip up-to-date] {f}')

    # 3. Copy and patch MDU
    src_mdu = SRC_V04 / 'Stagnone_dxy01_15m.mdu'
    dst_mdu = DST / MDU_NAME
    print(f'  Patching MDU -> {MDU_NAME}')
    in_text = src_mdu.read_text(encoding='utf-8', errors='replace')
    out_lines = []
    n_patched = 0
    for line in in_text.splitlines(keepends=True):
        patched = patch_mdu_line(line)
        if patched != line:
            n_patched += 1
        out_lines.append(patched)
    dst_mdu.write_text(''.join(out_lines), encoding='utf-8')
    print(f'    {n_patched} keys patched')

    # 4. Write fresh _new.ext + empty _old.ext
    write_ext_new(DST / EXT_NEW_NAME)
    write_ext_old(DST / EXT_OLD_NAME)
    print(f'  wrote {EXT_NEW_NAME} (4 boundaries + 4 meteo)')
    print(f'  wrote {EXT_OLD_NAME} (empty)')

    # 5. Quick sanity: BC files present
    print('\nBC files present:')
    for bc in sorted(DST.glob('*.bc')):
        print(f'  {bc.name}  ({bc.stat().st_size/1024:.1f} KB)')

    # 6. Summary
    print(f'\nDone. Model dir: {DST}')
    print(f'  total files: {len(list(DST.iterdir()))}')
    total_mb = sum(f.stat().st_size for f in DST.iterdir() if f.is_file()) / 1e6
    print(f'  total size : {total_mb:.1f} MB')
    print('\nNext steps:')
    print('  1. Validate MDU via hydrolib-core FMModel(mdu_path)')
    print('  2. Partition: dflowfm.exe --partition:ndomains=8 Stagnone_v05.mdu')
    print('  3. Cold-start run: 3-day diagnostic Jul 1->4')


if __name__ == '__main__':
    main()
