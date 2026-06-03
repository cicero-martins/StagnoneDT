"""Build CMEMS .bc files for v04AE Opt-A cold-start Jul 13-21 window.

Inputs: data/raw/cmems_v04AE_jul13jul20/cmems_{zos,uo,vo,so,thetao}_2025-07-12_2025-07-22.nc
PLI:    model/dflowfm_v04AE/Stagnone_dxy01_15m.pli
Output: model/dflowfm_v04AE_jul13jul20/
"""
from __future__ import annotations

try:
    import pip_system_certs.wrapt_requests  # noqa: F401
except ImportError:
    pass

import shutil
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_NC = PROJECT_ROOT / 'data' / 'raw' / 'cmems_v04AE_jul13jul20'
V04AE = PROJECT_ROOT / 'model' / 'dflowfm_v04AE'
DST = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_jul13jul20'

PLI_FILE = DST / 'Stagnone_dxy01_15m.pli'
TSTART = pd.Timestamp('2025-07-13 00:00')
TSTOP  = pd.Timestamp('2025-07-21 00:00')
REFDATE = '2025-01-01 00:00:00'


def ensure_pli():
    if PLI_FILE.exists():
        return
    src = V04AE / 'Stagnone_dxy01_15m.pli'
    if not src.exists():
        raise FileNotFoundError(f'PLI not found at {src}')
    DST.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, PLI_FILE)
    print(f'Copied {src.name} -> {PLI_FILE}')


def main():
    ensure_pli()

    import dfm_tools as dfmt
    import hydrolib.core.dflowfm as hcdfm

    # Monkey-patch hydrolib 1.0.0 missing VectorQuantityUnitPairs
    if not hasattr(hcdfm, 'VectorQuantityUnitPairs'):
        from pydantic import BaseModel
        from typing import List, Any

        class _VectorQUPStub(BaseModel):
            vectorname: str
            elementname: List[str]
            quantityunitpair: List[Any]

            class Config:
                arbitrary_types_allowed = True

            def __iter__(self):
                return iter(self.quantityunitpair)

        hcdfm.VectorQuantityUnitPairs = _VectorQUPStub
        print('[monkey-patch] Stubbed hcdfm.VectorQuantityUnitPairs for hydrolib 1.0.0')

    ext_new = hcdfm.ExtModel()

    list_quantities = [
        'waterlevelbnd',
        'salinitybnd',
        'temperaturebnd',
    ]

    dir_pattern = str(SRC_NC / 'cmems_{ncvarname}_*.nc')

    print(f'PLI:          {PLI_FILE}')
    print(f'Pattern:      {dir_pattern}')
    print(f'tstart/tstop: {TSTART} -> {TSTOP}')
    print(f'Quantities:   {list_quantities}')
    print()

    dfmt.cmems_nc_to_bc(
        ext_new=ext_new,
        list_quantities=list_quantities,
        tstart=TSTART,
        tstop=TSTOP,
        file_pli=str(PLI_FILE),
        dir_pattern=dir_pattern,
        dir_output=str(DST),
        refdate_str=f'minutes since {REFDATE} +00:00',
    )

    # Copy uxuy fallback (FM extrapolates past data range)
    uxuy_src = V04AE / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'
    uxuy_dst = DST / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'
    if uxuy_src.exists() and not uxuy_dst.exists():
        shutil.copy2(uxuy_src, uxuy_dst)
        print(f'\nCopied {uxuy_src.name} (uxuy fallback)')

    # Copy WL offset per-node (static, Marettimo anchor)
    offset_src = V04AE / 'waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc'
    offset_dst = DST / 'waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc'
    if offset_src.exists() and not offset_dst.exists():
        shutil.copy2(offset_src, offset_dst)
        print(f'Copied {offset_src.name} (per-node Marettimo offset)')

    # Copy constant fallback
    const_src = V04AE / 'waterlevelbnd_constant_Stagnone_dxy01_15m.bc'
    const_dst = DST / 'waterlevelbnd_constant_Stagnone_dxy01_15m.bc'
    if const_src.exists() and not const_dst.exists():
        shutil.copy2(const_src, const_dst)
        print(f'Copied {const_src.name} (constant fallback)')

    print('\nGenerated .bc files:')
    for bc in sorted(DST.glob('*.bc')):
        print(f'  {bc.name}  ({bc.stat().st_size/1024:.1f} KB)')


if __name__ == '__main__':
    main()
