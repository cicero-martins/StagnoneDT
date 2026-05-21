#!/usr/bin/env bash
#
# Reset test: clone nodm + extend window from 9d (Jul 1-10) to 11d (Jul 1-12).
# Zero MDU patches except dates. Pure validation that nodm setup is reproducible
# and that the extension produces new content for Jul 10-12.
#
# Usage:
#   bash test_extend_nodm_window.sh
#
# Output goes to ~/StagnoneDT/runs/test_jul1-12/

set -euo pipefail

ROOT="${ROOT:-$HOME/StagnoneDT}"
NODM="${NODM:-$ROOT/model/dflowfm_v04AE_nodm}"
NEW="${NEW:-$ROOT/runs/test_jul1-12}"

START_DATE="2025-07-01"
STOP_DATE="2025-07-12"
START_NOSEP="20250701"
STOP_NOSEP="20250712"
TSTOP_SEC=$(( (\
    $(date -u -d "$STOP_DATE" +%s) - $(date -u -d "$START_DATE" +%s)\
  ) ))  # 11 days = 950400 s

echo "=== Reset Test: extend nodm window to Jul 1-12 ==="
echo "  template : $NODM"
echo "  target   : $NEW"
echo "  window   : $START_DATE -> $STOP_DATE (${TSTOP_SEC} s)"

[[ -d "$NODM" ]] || { echo "ERROR: nodm template $NODM not found"; exit 2; }

# Clone nodm (exclude its DFM_OUTPUT_ + run logs but KEEP everything else)
echo "=== [1/4] Cloning nodm -> $NEW ==="
if [[ -d "$NEW" ]]; then
    STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    mv "$NEW" "$NEW.bak.$STAMP"
    echo "  Existing target backed up to $NEW.bak.$STAMP"
fi
mkdir -p "$NEW"
rsync -a \
  --exclude='DFM_OUTPUT_Stagnone_dxy01_15m/' \
  --exclude='DFM_OUTPUT_*.bak.*' \
  --exclude='diag/run_*.log' \
  --exclude='diag/Stagnone_dxy01_15m_*.dia' \
  --exclude='diag/swn-diag*' \
  --exclude='wave/hot_*.nc' \
  --exclude='wave/BOTNOW' --exclude='wave/CURNOW' --exclude='wave/WNDNOW' \
  --exclude='wave/PRINT-*' --exclude='wave/swaninit' \
  --exclude='wave/swan_omp.exe' \
  --exclude='wave/swn-diag.*' --exclude='wave/esmf_sh.log' --exclude='wave/SWANOUT*' \
  --exclude='*.cache' \
  "$NODM"/ "$NEW"/
echo "  Cloned $(du -sh $NEW | cut -f1)"

# Replace meteo + BC forcings with Jul 1-13 versions from d10d12 (has extended files)
echo "=== [1.5/4] Replacing meteo + BCs with Jul 1-13 versions ==="
D10D12="$ROOT/model/dflowfm_v04AE_d10d12"
# Remove nodm Jul 1-10 meteo
rm -f "$NEW"/era5_*_20250701to20250710_ERA5.nc
rm -f "$NEW"/wind_blendedAE_*_20250701to20250710.nc
rm -f "$NEW"/wind_era5raw_*_20250701to20250710.nc
# Install d10d12 Jul 1-13 meteo
for f in "$D10D12"/era5_*_20250701to20250713_ERA5.nc \
         "$D10D12"/wind_blendedAE_*_20250701to20250713.nc \
         "$D10D12"/wind_era5raw_*_20250701to20250713.nc; do
    [[ -f "$f" ]] && cp "$f" "$NEW/"
done
# CRITICAL: nodm's CMEMS .bc files only cover Jul 1-10. d10d12 has Jul 1-13 versions.
# Without this, test will crash with EC-module Error at sim 9d (Jul 10 0:00).
for bc in waterlevelbnd_CMEMS_Stagnone_dxy01_15m.bc \
          salinitybnd_CMEMS_Stagnone_dxy01_15m.bc \
          temperaturebnd_CMEMS_Stagnone_dxy01_15m.bc \
          uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc; do
    if [[ -f "$D10D12/$bc" ]]; then
        cp "$D10D12/$bc" "$NEW/"
    fi
done
# Patch both .ext files (new+old) to reference new meteo file dates
for EXT in "$NEW/Stagnone_dxy01_15m_new.ext" "$NEW/Stagnone_dxy01_15m_old.ext"; do
    [[ -f "$EXT" ]] || continue
    cp "$EXT" "$EXT.bak"
    sed -i 's/_20250701to20250710/_20250701to20250713/g' "$EXT"
done

# Patch MDUs (master + 8 per-partition) — ONLY dates, nothing else
echo "=== [2/4] Patching MDUs — dates only ==="
patch_dates() {
    local mdu="$1"
    [[ -f "$mdu" ]] || return
    cp "$mdu" "$mdu.bak"
    sed -i "s/^tStop\s*=.*/tStop                   = ${TSTOP_SEC}.0/" "$mdu"
    sed -i "s/^stopDateTime\s*=.*/stopDateTime            = ${STOP_NOSEP}000000/" "$mdu"
    # startDateTime stays Jul 1 (cold-start same as nodm)
}
patch_dates "$NEW/Stagnone_dxy01_15m.mdu"
for n in 0 1 2 3 4 5 6 7; do
    rank=$(printf "%04d" $n)
    patch_dates "$NEW/Stagnone_dxy01_15m_${rank}.mdu"
done
echo "  Rank 0 dates:"
grep -E "^(tStop|startDateTime|stopDateTime)" "$NEW/Stagnone_dxy01_15m_0000.mdu"

# Patch dimr_config
echo "=== [3/4] Patching dimr_config.xml ==="
DIMR="$NEW/dimr_config.xml"
cp "$DIMR" "$DIMR.bak"
sed -i "s|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 ${TSTOP_SEC}</time>|" "$DIMR"
grep -E "<time>" "$DIMR"

# Cleanup + launch
echo "=== [4/4] Launch ==="
cd "$NEW"
rm -rf DFM_OUTPUT_Stagnone_dxy01_15m 2>/dev/null || true
rm -f *.cache 2>/dev/null || true
mkdir -p diag

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
    set +u
    source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true
    set -u
fi
export OMP_NUM_THREADS=8
export KMP_HW_SUBSET=8c,1t
export PATH="$HOME/Scaricati/delft3dfm/lnx64/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/Scaricati/delft3dfm/lnx64/lib:${LD_LIBRARY_PATH:-}"

command -v mpiexec >/dev/null || { echo "ERROR: no mpiexec"; exit 4; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="diag/run_jul1-12_${STAMP}.log"
nohup bash -c "
  export OMP_NUM_THREADS=8 KMP_HW_SUBSET=8c,1t
  export PATH='$PATH'
  export LD_LIBRARY_PATH='$LD_LIBRARY_PATH'
  cd '$NEW'
  exec run_dimr.sh -c 8 -m dimr_config.xml
" > "$LOG" 2>&1 &
PID=$!
disown $PID 2>/dev/null || true
echo "  PID: $PID"
echo "  Log: $NEW/$LOG"
echo ""
echo "Expected wall time ~2.5h (nodm did 9d in ~1.9h; +2d ~30 min more)."
