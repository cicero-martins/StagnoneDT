#!/usr/bin/env bash
#
# Clone v04AE master -> v04AE_jul13jul20 with all patches for Opt-A cold-start.
#
# Pre-requisites (run these BEFORE this script):
#   - scripts/download_cmems_phy_v04AE_jul13jul20.py  -> data/raw/cmems_v04AE_jul13jul20/
#   - scripts/preprocess_era5_v04AE_jul13jul20.py     -> model/dflowfm_v04AE_jul13jul20/era5_*
#   - scripts/prepare_v04AE_jul13jul20_ae_blend.py    -> model/dflowfm_v04AE_jul13jul20/wind_blendedAE_*
#   - scripts/build_cmems_bc_v04AE_jul13jul20.py      -> model/dflowfm_v04AE_jul13jul20/*.bc
#
# Patches applied per [[v04AE_continuation_mdu_patches]] + Opt-A cold-start:
#   - startDateTime = 20250713000000, stopDateTime = 20250721000000, tStop = 691200
#   - restartFile = empty (cold-start)
#   - Sedimentmodelnr = 0 (D-Morph off per [[dmorph_off_for_paper1]])
#   - maxVelocity = 15
#   - iniFieldFile: KEEP initialFields.ini for cold-start (hypersaline IC accelerates spinup)
#   - All ext refs: 20250701to20250710 -> 20250713to20250721

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/model/dflowfm_v04AE"
DST="$ROOT/model/dflowfm_v04AE_jul13jul20"

# Windows-style paths for python.exe calls (Git Bash /c/ -> C:/)
to_win() { python3 -c "import sys, os; print(os.path.abspath(sys.argv[1]).replace(chr(92),'/'))" "$1" 2>/dev/null || cygpath -w "$1" 2>/dev/null || echo "$1"; }
SRC_WIN="$(to_win "$SRC")"
DST_WIN="$(to_win "$DST")"

# Pre-flight: forcings present
echo "=== Pre-flight check ==="
for f in \
    "$DST/era5_mer_20250713to20250721_ERA5.nc" \
    "$DST/era5_msl_20250713to20250721_ERA5.nc" \
    "$DST/era5_chnk_20250713to20250721_ERA5.nc" \
    "$DST/era5_u10n_20250713to20250721_ERA5.nc" \
    "$DST/era5_v10n_20250713to20250721_ERA5.nc" \
    "$DST/wind_blendedAE_u10n_20250713to20250721.nc" \
    "$DST/wind_blendedAE_v10n_20250713to20250721.nc" \
    "$DST/waterlevelbnd_CMEMS_Stagnone_dxy01_15m.bc" \
    "$DST/salinitybnd_CMEMS_Stagnone_dxy01_15m.bc" \
    "$DST/temperaturebnd_CMEMS_Stagnone_dxy01_15m.bc" \
    "$DST/waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc" \
    "$DST/Stagnone_dxy01_15m.pli"
do
    if [[ ! -f "$f" ]]; then
        echo "MISSING: $f"
        exit 1
    fi
done
echo "  All forcings present"

# Clone v04AE source files via python (rsync not available in Git Bash on Windows)
echo ""
echo "=== Clone files from v04AE master ==="
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
import shutil
from pathlib import Path
import os
src = Path(r"$SRC_WIN")
dst = Path(r"$DST_WIN")
dst.mkdir(parents=True, exist_ok=True)

exclude_dirs = {'DFM_OUTPUT_Stagnone_dxy01_15m', 'diag'}
exclude_globs = {'Stagnone_dxy01_15m.mdu', 'Stagnone_dxy01_15m_new.ext',
                 'Stagnone_dxy01_15m_old.ext', 'dimr_config.xml'}
def should_skip(name):
    if name in exclude_globs: return True
    if name.startswith('Stagnone_dxy01_15m_000'): return True  # partition files
    if name.endswith('.bak') or '.bak.' in name: return True
    if name.endswith('.cache'): return True
    if name.endswith('.bc'): return True  # already in DST
    if name.startswith('era5_') and '20250701to20250710' in name: return True
    if name.startswith('wind_') and '2025' in name: return True
    return False

n_copied = 0
n_skipped = 0
for item in src.iterdir():
    if item.name in exclude_dirs:
        n_skipped += 1
        continue
    if should_skip(item.name):
        n_skipped += 1
        continue
    target = dst / item.name
    if item.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(item, target)
        n_copied += 1
    else:
        shutil.copy2(item, target)
        n_copied += 1
print(f'  copied: {n_copied}, skipped: {n_skipped}')
EOF
echo "  Cloned (excluding ext/mdu/dimr — will be patched)"

# Patch MDU
echo ""
echo "=== Patch MDU ==="
cp "$SRC/Stagnone_dxy01_15m.mdu" "$DST/Stagnone_dxy01_15m.mdu"
MDU="$DST/Stagnone_dxy01_15m.mdu"
sed -i 's/^tStop\s*=.*/tStop                   = 691200.0       # Stop time w.r.t. RefDate (8 days, Jul 13 00:00 -> Jul 21 00:00)/' "$MDU"
sed -i 's/^startDateTime\s*=.*/startDateTime           = 20250713000000 # Cold-start Opt-A Jul 13 spin-up + Jul 20 publish/' "$MDU"
sed -i 's/^stopDateTime\s*=.*/stopDateTime            = 20250721000000 # Opt-A 8d cold-start window/' "$MDU"
sed -i 's/^Sedimentmodelnr\s*=.*/Sedimentmodelnr = 0               # D-Morph OFF per dmorph_off_for_paper1/' "$MDU"
sed -i 's/^maxVelocity\s*=.*/maxVelocity               = 15.0   # Opt-A per v04AE_continuation_mdu_patches/' "$MDU"
# Confirm patch
echo "  MDU patched:"
grep -E "^(tStop|startDateTime|stopDateTime|Sedimentmodelnr|maxVelocity)" "$MDU" | sed 's/^/    /'

# Patch new.ext: change forcing file refs
echo ""
echo "=== Patch _new.ext ==="
cp "$SRC/Stagnone_dxy01_15m_new.ext" "$DST/Stagnone_dxy01_15m_new.ext"
EXT_NEW="$DST/Stagnone_dxy01_15m_new.ext"
# Wind: 20250701to20250710 -> 20250713to20250721
sed -i 's/wind_blendedAE_u10n_20250701to20250710.nc/wind_blendedAE_u10n_20250713to20250721.nc/g' "$EXT_NEW"
sed -i 's/wind_blendedAE_v10n_20250701to20250710.nc/wind_blendedAE_v10n_20250713to20250721.nc/g' "$EXT_NEW"
# ERA5 (msl, chnk in new.ext; mer in old.ext)
sed -i 's/era5_msl_20250701to20250710_ERA5.nc/era5_msl_20250713to20250721_ERA5.nc/g' "$EXT_NEW"
sed -i 's/era5_chnk_20250701to20250710_ERA5.nc/era5_chnk_20250713to20250721_ERA5.nc/g' "$EXT_NEW"
echo "  _new.ext refs updated:"
grep -E "20250713to20250721" "$EXT_NEW" | sed 's/^/    /'

# Patch old.ext: ERA5 mer + nudge file
echo ""
echo "=== Patch _old.ext ==="
cp "$SRC/Stagnone_dxy01_15m_old.ext" "$DST/Stagnone_dxy01_15m_old.ext"
EXT_OLD="$DST/Stagnone_dxy01_15m_old.ext"
sed -i 's/era5_mer_20250701to20250710_ERA5.nc/era5_mer_20250713to20250721_ERA5.nc/g' "$EXT_OLD"
# Nudge file: v04AE has nudge_salinity_temperature_2025-07-01_00-00-00.nc — for Jul 13 cold-start the IC
# nudging from Jul 1 file is wrong. Remove the nudge block entirely (FM tolerates missing nudging).
EXT_OLD_WIN="$(to_win "$EXT_OLD")"
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
from pathlib import Path
p = Path(r"$EXT_OLD_WIN")
text = p.read_text()
# Find and remove QUANTITY=nudge_salinity_temperature block (5 lines: QUANTITY, FILENAME, FILETYPE, METHOD, OPERAND)
lines = text.splitlines()
out = []
i = 0
while i < len(lines):
    if lines[i].strip().startswith('QUANTITY=nudge_salinity_temperature'):
        # Skip until next blank line or QUANTITY=
        out.append('* Nudge block removed for Opt-A Jul 13 cold-start (Jul 01 IC nudge file would be wrong)')
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('QUANTITY='):
            i += 1
    else:
        out.append(lines[i])
        i += 1
p.write_text('\n'.join(out))
print('  Removed nudge_salinity_temperature block')
EOF
echo "  _old.ext refs updated:"
grep -E "20250713to20250721" "$EXT_OLD" | sed 's/^/    /'

# Patch dimr_config
echo ""
echo "=== Patch dimr_config.xml ==="
cp "$SRC/dimr_config.xml" "$DST/dimr_config.xml"
DIMR="$DST/dimr_config.xml"
sed -i 's|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 691200</time>|' "$DIMR"
echo "  dimr_config.xml time updated:"
grep -E "<time>" "$DIMR" | sed 's/^/    /'

# Clean output dir (will be created by run)
rm -rf "$DST/DFM_OUTPUT_Stagnone_dxy01_15m" 2>/dev/null || true
mkdir -p "$DST/diag"

# Summary
echo ""
echo "=== Setup complete ==="
echo "Total size:"
du -sh "$DST" | sed 's/^/  /'
echo ""
echo "Next steps:"
echo "  1. Upload to simit-server:"
echo "     rsync -av --progress $DST/ ciceromartinsjr@147.163.48.52:~/StagnoneDT/model/dflowfm_v04AE_jul13jul20/"
echo "  2. Launch on simit-server:"
echo "     ssh ciceromartinsjr@147.163.48.52 'cd ~/StagnoneDT/model/dflowfm_v04AE_jul13jul20 && bash run_model.sh'"
