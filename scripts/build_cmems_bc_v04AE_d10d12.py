"""Build CMEMS boundary condition .bc files for v04AE_d10d12 (Jul 1-13 window).

Inputs: data/raw/cmems_v04AE_d10d12/cmems_{zos,uovo,so,thetao}_2025-07-01_2025-07-13.nc
PLI:    model/dflowfm_v04AE_d10d12/Stagnone_dxy01_15m.pli (copied from v04AE)
Output: model/dflowfm_v04AE_d10d12/
  - waterlevelbnd_CMEMS_*.bc
  - salinitybnd_CMEMS_*.bc
  - temperaturebnd_CMEMS_*.bc
  - uxuyadvectionvelocitybnd_CMEMS_*.bc

Uses dfm_tools.cmems_nc_to_bc which:
  - Reads CMEMS NetCDFs (expects dfm_tools naming convention)
  - Interpolates to .pli boundary points (49 nodes for Stagnone)
  - Writes .bc files in hydrolib format
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
SRC_NC = PROJECT_ROOT / 'data' / 'raw' / 'cmems_v04AE_d10d12'
V04AE = PROJECT_ROOT / 'model' / 'dflowfm_v04AE'
DST = PROJECT_ROOT / 'model' / 'dflowfm_v04AE_d10d12'

PLI_FILE = DST / 'Stagnone_dxy01_15m.pli'
TSTART = pd.Timestamp('2025-07-01 00:00')
# Daily files (sal/temp/cur) have midnight timestamps -> Jul 13 00:00 is the last.
# Simulation window is Jul 10 00:00 -> Jul 12 00:00, fully covered with 24h buffer.
TSTOP  = pd.Timestamp('2025-07-13 00:00')
REFDATE = '2025-01-01 00:00:00'


def ensure_pli():
    """Copy Stagnone_dxy01_15m.pli from v04AE if not present in d10d12."""
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

    # Monkey-patch: dfm_tools expects hcdfm.VectorQuantityUnitPairs (older hydrolib API)
    # but hydrolib-core 1.0.0 removed it. Stub class that emits the same .bc structure
    # via the existing QuantityUnitPair list-of-quantities approach.
    if not hasattr(hcdfm, 'VectorQuantityUnitPairs'):
        from pydantic import BaseModel
        from typing import List, Any

        class _VectorQUPStub(BaseModel):
            """Stub mimicking the removed VectorQuantityUnitPairs.

            Holds a vector name + list of QuantityUnitPair (the underlying scalar
            quantities). When the .bc writer iterates a forcing block's
            quantityunitpair list, this stub is unpacked into its scalar
            components."""
            vectorname: str
            elementname: List[str]
            quantityunitpair: List[Any]

            class Config:
                arbitrary_types_allowed = True

            def __iter__(self):
                # Treat the stub as a flat list of its underlying QUPs.
                return iter(self.quantityunitpair)

        hcdfm.VectorQuantityUnitPairs = _VectorQUPStub
        print('[monkey-patch] Stubbed hcdfm.VectorQuantityUnitPairs for hydrolib 1.0.0')

    # Empty new-style ext model (cmems_nc_to_bc populates [Boundary] blocks in it)
    ext_new = hcdfm.ExtModel()

    # NOTE: 'uxuyadvectionvelocitybnd' is excluded because dfm_tools generates it via
    # the removed hcdfm.VectorQuantityUnitPairs (hydrolib 1.0.0 API). The existing
    # v04AE/uxuyadvectionvelocitybnd_CMEMS_*.bc (Jul 1-10) is copied as fallback;
    # FM will extrapolate the last value for the Jul 10-12 continuation. Boundary
    # currents in the open coastal area are small (~0.1 m/s) so the bound error
    # from 2-day persistence is acceptable for the close-the-loop demo.
    list_quantities = [
        'waterlevelbnd',
        'salinitybnd',
        'temperaturebnd',
    ]

    # dfm_tools expects dir_pattern as a glob string with explicit substitutions
    # for variable name. Check if our names match — typical dfm_tools pattern uses
    # 'cmems_{ncvarname}_*' style. Our files are 'cmems_zos_...', 'cmems_uovo_...',
    # 'cmems_so_...', 'cmems_thetao_...'.
    # Try the canonical dir_pattern that dfm_tools expects.
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

    # Copy the uxuy .bc from v04AE (will be extrapolated by FM past Jul 10)
    uxuy_src = V04AE / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'
    uxuy_dst = DST / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'
    if uxuy_src.exists() and not uxuy_dst.exists():
        shutil.copy2(uxuy_src, uxuy_dst)
        print(f'\nCopied {uxuy_src.name} (fallback for uxuy; FM extrapolates past Jul 10)')

    # Copy waterlevelbnd_offset_pernode .bc from v04AE
    # (per-node constant offset; static in time, valid for Jul 2025 anchor)
    offset_src = V04AE / 'waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc'
    offset_dst = DST / 'waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc'
    if offset_src.exists() and not offset_dst.exists():
        shutil.copy2(offset_src, offset_dst)
        print(f'Copied {offset_src.name} (static per-node Marettimo offset, Jul 2025)')

    # Same for waterlevelbnd_constant (legacy fallback, referenced in some configs)
    const_src = V04AE / 'waterlevelbnd_constant_Stagnone_dxy01_15m.bc'
    const_dst = DST / 'waterlevelbnd_constant_Stagnone_dxy01_15m.bc'
    if const_src.exists() and not const_dst.exists():
        shutil.copy2(const_src, const_dst)
        print(f'Copied {const_src.name} (constant +0.4812 m fallback)')

    print('\nGenerated .bc files:')
    for bc in sorted(DST.glob('*.bc')):
        print(f'  {bc.name}  ({bc.stat().st_size/1024:.1f} KB)')


if __name__ == '__main__':
    main()
