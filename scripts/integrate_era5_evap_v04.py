"""Append ERA5 evaporation forcing to v04 ext_old after the download by
download_era5_evap_v04.py completes.

ERA5 'mer' was converted by dfm_tools' preprocess_merge_meteofiles_era5
from kg/m^2/s to mm/day (verified by inspecting the .nc 'units' attribute).
Sign convention: NEGATIVE for evaporation (water leaving the surface).

FM 2026.01 unifies precip + evap as a single QUANTITY=rainfall_rate (the
canonical convention used by dfm_tools, see modelbuilder.py:278). Sign
convention: POSITIVE for water entering surface (rain), NEGATIVE for water
leaving (evap). Unit: mm/day, matching ERA5 mer after preprocess.

So no FACTOR is needed. ERA5's negative-evap maps to FM negative-rainfall_rate
naturally. Earlier attempts using QUANTITY=evaporation FAILED at runtime with
"unknown QUANTITY evaporation" because FM does not have a separate evap
quantity in old-ext format.

Idempotent: replaces any pre-existing rainfall_rate or legacy evaporation
block with the canonical form.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V04_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v04'
EXT_OLD = V04_DIR / 'Stagnone_dxy01_15m_old.ext'


def strip_legacy_evap_block(text: str) -> str:
    """Remove any pre-existing v04 evap/rainfall_rate block. Idempotent rebuild."""
    import re
    # Strip the v04 comment header through to the closing FACTOR line (or OPERAND
    # if FACTOR omitted). Match either legacy QUANTITY=evaporation or current
    # QUANTITY=rainfall_rate forms.
    pattern = re.compile(
        r'\n*# v04: ERA5 evaporation.*?'
        r'(QUANTITY=evaporation|QUANTITY=rainfall_rate).*?'
        r'(FACTOR=[^\n]*\n|OPERAND=[^\n]*\n)',
        re.DOTALL,
    )
    return pattern.sub('\n', text)


def main() -> int:
    candidates = sorted(V04_DIR.glob('era5_mer_*.nc'))
    if not candidates:
        print(f'ERROR: no era5_mer_*.nc in {V04_DIR}; run download_era5_evap_v04.py first')
        return 1
    mer_file = candidates[-1].name
    print(f'Using ERA5 mer file: {mer_file}')

    text = EXT_OLD.read_text(encoding='utf-8')
    text = strip_legacy_evap_block(text)

    block = (f'\n# v04: ERA5 evaporation forcing for hipersalinidade fix\n'
             f'#      ERA5 mer in mm/day (dfmt preprocess), negative = evap.\n'
             f'#      FM unifies precip + evap as QUANTITY=rainfall_rate in mm/day.\n'
             f'#      ERA5 negative-evap matches FM negative-rainfall_rate => no FACTOR needed.\n'
             f'QUANTITY=rainfall_rate\n'
             f'FILENAME={mer_file}\n'
             f'VARNAME=mer\n'
             f'FILETYPE=11\n'
             f'METHOD=3\n'
             f'OPERAND=O\n')
    EXT_OLD.write_text(text.rstrip() + '\n' + block, encoding='utf-8')
    print(f'Wrote rainfall_rate block to {EXT_OLD.name}')
    print(block)
    return 0


if __name__ == '__main__':
    sys.exit(main())
