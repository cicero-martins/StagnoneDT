#!/usr/bin/env bash
#
# Setup v04AE_jul06jul13 — cold-start Jul 6 -> Jul 13 (7d).
#
# Hypothesis test: if Jul 6-13 runs clean and Jul 13-21 doesn't, confirms
# wind ramp Jul 12-13 noon + cumulative momentum ~28h is the crash mechanism.
#
# Reuses Jul 1-13 forcings already prepared for d10d12.
# Builds new SWAN TPAR .bnd for Jul 5-14 (fresh CMEMS wave download).
#
# Window: Jul 6 00:00 -> Jul 13 00:00 = 604800s = 7d

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/model/dflowfm_v04AE"
D10D12="$ROOT/model/dflowfm_v04AE_d10d12"
DST="$ROOT/model/dflowfm_v04AE_jul06jul13"

to_win() { python3 -c "import sys, os; print(os.path.abspath(sys.argv[1]).replace(chr(92),'/'))" "$1" 2>/dev/null || cygpath -w "$1" 2>/dev/null || echo "$1"; }
SRC_WIN="$(to_win "$SRC")"
DST_WIN="$(to_win "$DST")"
D10D12_WIN="$(to_win "$D10D12")"

echo "=== Clone v04AE master (excluding ext/mdu/dimr/forcings) ==="
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
import shutil
from pathlib import Path
src = Path(r"$SRC_WIN")
dst = Path(r"$DST_WIN")
dst.mkdir(parents=True, exist_ok=True)
exclude_dirs = {'DFM_OUTPUT_Stagnone_dxy01_15m', 'diag'}  # wave/ now INCLUDED (mdw, grid, bathy needed; .bnd replaced after)
exclude_globs = {'Stagnone_dxy01_15m.mdu', 'Stagnone_dxy01_15m_new.ext',
                 'Stagnone_dxy01_15m_old.ext', 'dimr_config.xml'}
def skip(name):
    if name in exclude_globs: return True
    if name.startswith('Stagnone_dxy01_15m_000'): return True
    if name.endswith(('.bak','.cache','.bc')): return True
    if '.bak.' in name: return True
    if name.startswith('era5_') and '20250701to20250710' in name: return True
    if name.startswith('wind_') and '2025' in name: return True
    return False
n = 0
for item in src.iterdir():
    if item.name in exclude_dirs or skip(item.name): continue
    tgt = dst / item.name
    if item.is_dir():
        if tgt.exists(): shutil.rmtree(tgt)
        shutil.copytree(item, tgt); n += 1
    else:
        shutil.copy2(item, tgt); n += 1
print(f'  copied {n} items from v04AE master')
EOF

echo ""
echo "=== Copy d10d12 forcings (cover Jul 1-13, fully include Jul 6-13) ==="
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
import shutil
from pathlib import Path
src = Path(r"$D10D12_WIN")
dst = Path(r"$DST_WIN")
n = 0
# Copy ERA5 (use _optimized.nc if exists, else original)
for f in src.glob('era5_*.nc'):
    opt = f.with_name(f.stem + '_optimized.nc')
    pick = opt if opt.exists() else f
    shutil.copy2(pick, dst / pick.name); n += 1
# Copy wind blend (prefer _optimized.nc)
for stem in ['wind_blendedAE_u10n_20250701to20250713', 'wind_blendedAE_v10n_20250701to20250713']:
    opt = src / f'{stem}_optimized.nc'
    orig = src / f'{stem}.nc'
    pick = opt if opt.exists() else orig
    if pick.exists():
        shutil.copy2(pick, dst / pick.name); n += 1
# wind_era5raw (optional, for diag) - skip to save space
for f in src.glob('*.bc'):
    shutil.copy2(f, dst / f.name); n += 1
# tracer_zero.bc lives in v04AE master, not d10d12
v04ae = Path(r"$SRC_WIN")
tz = v04ae / 'tracer_zero.bc'
if tz.exists():
    shutil.copy2(tz, dst / 'tracer_zero.bc'); n += 1
    print('  added tracer_zero.bc from v04AE master')
print(f'  copied {n} forcing files from d10d12')
EOF

echo ""
echo "=== Download CMEMS wave Jul 5-14 + build TPAR .bnd ==="
WAVE_OUT_NC="data/raw/cmems_v04AE_jul06jul13/MEDSEA_WAV_2025-07-05_2025-07-14.nc"
mkdir -p "$(dirname "$WAVE_OUT_NC")"
ROOT_WIN="$(to_win "$ROOT")"
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
import os
from pathlib import Path
import xarray as xr
import numpy as np
import pandas as pd
try:
    import pip_system_certs.wrapt_requests
except ImportError: pass
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(r"$ROOT_WIN")
WAVE_NC = ROOT / "data/raw/cmems_v04AE_jul06jul13" / "MEDSEA_WAV_2025-07-05_2025-07-14.nc"
WAVE_DIR = Path(r"$DST_WIN") / "wave"
WAVE_DIR.mkdir(parents=True, exist_ok=True)

# Load .env
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k, v = line.split('=', 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

if not WAVE_NC.exists():
    import copernicusmarine
    print(f'  Downloading CMEMS wave Jul 5-14...')
    copernicusmarine.subset(
        dataset_id='cmems_mod_med_wav_anfc_4.2km_PT1H-i',
        variables=['VHM0', 'VTPK', 'VMDR'],
        minimum_longitude=11.85, maximum_longitude=12.60,
        minimum_latitude=37.65, maximum_latitude=38.10,
        start_datetime='2025-07-05T00:00:00', end_datetime='2025-07-14T00:00:00',
        output_directory=str(WAVE_NC.parent), output_filename=WAVE_NC.name,
        username=os.environ['CMEMS_USERNAME'], password=os.environ['CMEMS_PASSWORD'],
    )
    print(f'  OK ({WAVE_NC.stat().st_size/1024:.0f} KB)')
else:
    print(f'  CMEMS wave file already exists: {WAVE_NC.name}')

# Build TPAR .bnd files
SAMPLE_POINTS = {
    'west':  [('seg1', 11.90, 37.75), ('seg2', 11.90, 37.88), ('seg3', 11.90, 38.00)],
    'south': [('seg1', 12.05, 37.67), ('seg2', 12.25, 37.67), ('seg3', 12.45, 37.67)],
    'north': [('seg1', 12.10, 38.08), ('seg2', 12.30, 38.08), ('seg3', 12.50, 38.08)],
}
ds = xr.open_dataset(WAVE_NC)
if 'longitude' in ds.coords: ds = ds.rename({'longitude':'lon', 'latitude':'lat'})

DIR_SPREAD = 4.0
for boundary, pts in SAMPLE_POINTS.items():
    for name, lo, la in pts:
        pt = ds.sel(lon=lo, lat=la, method='nearest')
        times = pd.to_datetime(pt.time.values)
        hs, tp_, dr = pt['VHM0'].values, pt['VTPK'].values, pt['VMDR'].values
        mask = ~(np.isnan(hs) | np.isnan(tp_) | np.isnan(dr))
        out = WAVE_DIR / f'{boundary}_{name}.bnd'
        with open(out, 'w') as f:
            f.write('TPAR\n')
            for t, h, p, d in zip(times[mask], hs[mask], tp_[mask], dr[mask]):
                f.write(f'{t.strftime("%Y%m%d.%H%M")}  {h:.3f}  {p:.2f}  {d:.2f}  {DIR_SPREAD:.2f}\n')
        print(f'  {out.name}: {mask.sum()} rows')
ds.close()
EOF

echo ""
echo "=== Patch MDU (Jul 6 -> Jul 13, cold-start, Sedimentmodelnr=0, maxVel=15) ==="
cp "$SRC/Stagnone_dxy01_15m.mdu" "$DST/Stagnone_dxy01_15m.mdu"
MDU="$DST/Stagnone_dxy01_15m.mdu"
sed -i 's/^tStop\s*=.*/tStop                   = 604800.0       # 7 days Jul 6 -> Jul 13/' "$MDU"
sed -i 's/^startDateTime\s*=.*/startDateTime           = 20250706000000 # Jul 6-13 cold-start (no wind ramp peak crossing)/' "$MDU"
sed -i 's/^stopDateTime\s*=.*/stopDateTime            = 20250713000000 # ends Jul 13 00:00 BEFORE wind ramp peak Jul 13 noon/' "$MDU"
sed -i 's/^Sedimentmodelnr\s*=.*/Sedimentmodelnr = 0/' "$MDU"
sed -i 's/^maxVelocity\s*=.*/maxVelocity               = 15.0/' "$MDU"
echo "  MDU date keys:"
grep -E "^(tStop|startDateTime|stopDateTime|Sedimentmodelnr|maxVelocity)" "$MDU" | sed 's/^/    /'

echo ""
echo "=== Patch _new.ext (refs to 20250701to20250713 — already match d10d12 files; remove uxuy + Lateral) ==="
cp "$SRC/Stagnone_dxy01_15m_new.ext" "$DST/Stagnone_dxy01_15m_new.ext"
EXT_NEW="$DST/Stagnone_dxy01_15m_new.ext"
sed -i 's/wind_blendedAE_u10n_20250701to20250710.nc/wind_blendedAE_u10n_20250701to20250713_optimized.nc/g' "$EXT_NEW"
sed -i 's/wind_blendedAE_v10n_20250701to20250710.nc/wind_blendedAE_v10n_20250701to20250713_optimized.nc/g' "$EXT_NEW"
sed -i 's/era5_msl_20250701to20250710_ERA5.nc/era5_msl_20250701to20250713_ERA5_optimized.nc/g' "$EXT_NEW"
sed -i 's/era5_chnk_20250701to20250710_ERA5.nc/era5_chnk_20250701to20250713_ERA5.nc/g' "$EXT_NEW"
EXT_NEW_WIN="$(to_win "$EXT_NEW")"
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
from pathlib import Path
p = Path(r"$EXT_NEW_WIN")
text = p.read_text(encoding='utf-8')
lines = text.splitlines()
out = []
i = 0
while i < len(lines):
    s = lines[i].strip()
    if s.startswith('[Lateral]'):
        i += 1
        while i < len(lines) and not lines[i].strip().startswith('['): i += 1
        continue
    if s.startswith('[Boundary]'):
        block = [lines[i]]
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith('['):
            block.append(lines[j]); j += 1
        if any('tracerbndturbid' in b for b in block) or any('uxuyadvectionvelocitybnd' in b for b in block):
            i = j; continue
        out.extend(block); i = j; continue
    out.append(lines[i]); i += 1
p.write_text('\n'.join(out), encoding='utf-8')
print('  removed: uxuy, Lateral turbid, tracerbndturbid blocks')
EOF

echo ""
echo "=== Patch _old.ext (ERA5 mer ref; keep nudge from Jul 1 — d10d12 only has Jul 1 nudge file, won't be useful at Jul 6 start; remove block) ==="
cp "$SRC/Stagnone_dxy01_15m_old.ext" "$DST/Stagnone_dxy01_15m_old.ext"
EXT_OLD="$DST/Stagnone_dxy01_15m_old.ext"
sed -i 's/era5_mer_20250701to20250710_ERA5.nc/era5_mer_20250701to20250713_ERA5.nc/g' "$EXT_OLD"
EXT_OLD_WIN="$(to_win "$EXT_OLD")"
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
from pathlib import Path
p = Path(r"$EXT_OLD_WIN")
text = p.read_text(encoding='utf-8')
lines = text.splitlines()
out = []; i = 0
while i < len(lines):
    if lines[i].strip().startswith('QUANTITY=nudge_salinity_temperature'):
        out.append('* Nudge removed (Jul 1 file inappropriate for Jul 6 cold-start)')
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('QUANTITY='):
            i += 1
    else:
        out.append(lines[i]); i += 1
p.write_text('\n'.join(out), encoding='utf-8')
print('  removed: Jul 1 nudge block')
EOF

echo ""
echo "=== Patch dimr_config.xml ==="
cp "$SRC/dimr_config.xml" "$DST/dimr_config.xml"
sed -i 's|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 604800</time>|' "$DST/dimr_config.xml"
echo "  dimr time:"
grep -E "<time>" "$DST/dimr_config.xml" | sed 's/^/    /'

echo ""
echo "=== Setup complete ==="
du -sh "$DST" | sed 's/^/  /'
echo "  forcings:"
ls "$DST" | grep -E "\.(nc|bc)$" | head -20 | sed 's/^/    /'
echo "  wave/:"
ls "$DST/wave" | sed 's/^/    /'
echo ""
echo "To launch on Workstation: copy entire $DST to Workstation + run_model.bat 8"
