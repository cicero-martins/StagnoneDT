"""Append ERA5 evaporation forcing to v04 ext_old after the download by
download_era5_evap_v04.py completes.

ERA5 'mer' was converted by dfm_tools' preprocess_merge_meteofiles_era5
from kg/m^2/s to mm/day (verified by inspecting the .nc 'units' attribute).
Sign convention: NEGATIVE for evaporation (water leaving the surface).

FM 'evaporation' expects m/s POSITIVE upward (out of ocean), so we apply:
    FACTOR = -1e-3 / 86400 = -1.1574e-8
which simultaneously converts mm/day -> m/s and flips the sign so a
negative ERA5 mer (evap) becomes a positive FM evap.

Sanity check: ERA5 mean ~-2.55 mm/day in this domain in Jul 2025
            -> after FACTOR: +2.95e-8 m/s ~ +2.55 mm/day to FM.

Idempotent: only appends if the evaporation block is not already present.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V04_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v04'
EXT_OLD = V04_DIR / 'Stagnone_dxy01_15m_old.ext'

MARKER = 'QUANTITY=evaporation'


def main() -> int:
    candidates = sorted(V04_DIR.glob('era5_mer_*.nc'))
    if not candidates:
        print(f'ERROR: no era5_mer_*.nc in {V04_DIR}; run download_era5_evap_v04.py first')
        return 1
    mer_file = candidates[-1].name
    print(f'Using ERA5 mer file: {mer_file}')

    text = EXT_OLD.read_text(encoding='utf-8')
    if MARKER in text:
        print(f'Evaporation block already present; updating filename only')
        # Replace the FILENAME line that follows our marker
        import re
        pattern = (r'(QUANTITY=evaporation\s*\nFILENAME=)([^\n]+)')
        new_text = re.sub(pattern, lambda m: m.group(1) + mer_file, text)
        EXT_OLD.write_text(new_text, encoding='utf-8')
        print('  filename updated')
        return 0

    block = (f'\n# v04: ERA5 evaporation forcing for hipersalinidade fix\n'
             f'#      ERA5 mer is in mm/day (converted by dfmt preprocess),\n'
             f'#      sign NEGATIVE for evaporation. FM expects m/s positive up.\n'
             f'#      factor = -1e-3/86400 = -1.1574e-8 (mm/day -> m/s + sign flip).\n'
             f'QUANTITY=evaporation\n'
             f'FILENAME={mer_file}\n'
             f'VARNAME=mer\n'
             f'FILETYPE=11\n'
             f'METHOD=3\n'
             f'OPERAND=O\n'
             f'FACTOR=-1.1574e-8\n')
    EXT_OLD.write_text(text.rstrip() + '\n' + block, encoding='utf-8')
    print(f'Appended evaporation block to {EXT_OLD.name}')
    print(block)
    return 0


if __name__ == '__main__':
    sys.exit(main())
