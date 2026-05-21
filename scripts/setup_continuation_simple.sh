#!/usr/bin/env bash
#
# Setup minimal N-3 continuation using d10d12 as template (NOT nodm).
# Reason: d10d12 has BCs + meteo + .mdw all aligned for Jul 1-13 window.
# Replacing some files from nodm clone caused SWAN time_read errors.
#
# Usage:  bash setup_continuation_simple.sh <publish_day>
# E.g.:   bash setup_continuation_simple.sh 2025-07-13

set -euo pipefail

PUBLISH_DAY="${1:?Usage: $0 <publish_day YYYY-MM-DD>}"
ROOT="${ROOT:-$HOME/StagnoneDT}"
TEMPLATE="$ROOT/model/dflowfm_v04AE_d10d12"
NODM_OUT="$ROOT/model/dflowfm_v04AE_nodm/DFM_OUTPUT_Stagnone_dxy01_15m"
RUNS="$ROOT/runs/forecast"
NEW="$RUNS/d${PUBLISH_DAY}"

# Window: N-3 -> N (72h)
START_DATE=$(date -u -d "$PUBLISH_DAY - 3 days" +%Y-%m-%d)
STOP_DATE="$PUBLISH_DAY"
START_NOSEP=$(date -u -d "$START_DATE" +%Y%m%d)
STOP_NOSEP=$(date -u -d "$STOP_DATE" +%Y%m%d)
TSTOP_SEC=$(( $(date -u -d "$STOP_DATE" +%s) - $(date -u -d "$START_DATE" +%s) ))

echo "=== Continuation setup ==="
echo "  publish day : $PUBLISH_DAY"
echo "  window      : $START_DATE -> $STOP_DATE (${TSTOP_SEC} s)"
echo "  template    : $TEMPLATE"
echo "  target      : $NEW"

# Verify rst @ START_DATE exists in nodm
RST_COUNT=$(ls "$NODM_OUT"/Stagnone_dxy01_15m_*_${START_NOSEP}_000000_rst.nc 2>/dev/null | wc -l)
if [[ "$RST_COUNT" -ne 8 ]]; then
    echo "ERROR: expected 8 rst @ ${START_DATE} in $NODM_OUT, found $RST_COUNT"
    exit 3
fi

# Clone d10d12 (exclude its DFM_OUTPUT + run logs + stale wave artifacts)
mkdir -p "$RUNS"
if [[ -d "$NEW" ]]; then
    mv "$NEW" "$NEW.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "$NEW"
rsync -a \
    --exclude='DFM_OUTPUT_Stagnone_dxy01_15m/' \
    --exclude='DFM_OUTPUT_*.bak.*' \
    --exclude='restart_input/' \
    --exclude='diag/run_*.log' \
    --exclude='diag/Stagnone_dxy01_15m_*.dia' \
    --exclude='diag/swn-diag*' \
    --exclude='wave/hot_*.nc' \
    --exclude='wave/BOTNOW' --exclude='wave/CURNOW' --exclude='wave/WNDNOW' \
    --exclude='wave/PRINT-*' --exclude='wave/swaninit' \
    --exclude='wave/swan_omp.exe' --exclude='wave/swn-diag.*' \
    --exclude='wave/esmf_sh.log' --exclude='wave/SWANOUT*' \
    --exclude='*.cache' --exclude='*.bak' --exclude='*.bak.*' \
    "$TEMPLATE"/ "$NEW"/
echo "  Cloned $(du -sh $NEW | cut -f1)"

# Install rst @ START_DATE from nodm
mkdir -p "$NEW/restart_input"
for n in 0 1 2 3 4 5 6 7; do
    rank=$(printf "%04d" $n)
    cp "$NODM_OUT/Stagnone_dxy01_15m_${rank}_${START_NOSEP}_000000_rst.nc" "$NEW/restart_input/"
done
echo "  8 rst @ $START_DATE installed from nodm"

# Patch MDUs (master + 8 per-partition)
patch_mdu() {
    local mdu="$1"
    local rank="$2"  # "" or "NNNN"
    [[ -f "$mdu" ]] || return
    cp "$mdu" "$mdu.bak"
    sed -i "s/^tStop\s*=.*/tStop                   = ${TSTOP_SEC}.0/" "$mdu"
    sed -i "s/^startDateTime\s*=.*/startDateTime           = ${START_NOSEP}000000/" "$mdu"
    sed -i "s/^stopDateTime\s*=.*/stopDateTime            = ${STOP_NOSEP}000000/" "$mdu"
    if [[ -z "$rank" ]]; then
        sed -i "s|^restartFile\s*=.*|restartFile     = restart_input/Stagnone_dxy01_15m_${START_NOSEP}_000000_rst.nc|" "$mdu"
    else
        sed -i "s|^restartFile\s*=.*|restartFile     = restart_input/Stagnone_dxy01_15m_${rank}_${START_NOSEP}_000000_rst.nc|" "$mdu"
    fi
    sed -i "s|^restartDateTime\s*=.*|restartDateTime = ${START_NOSEP}000000|" "$mdu"
    # D-Morph off: nodm rst has no sediment fractions; d10d12 MDU has Sedimentmodelnr=4
    # which causes "Mismatch in number of sediment fractions" error. Force OFF.
    sed -i 's/^Sedimentmodelnr\s*=.*/Sedimentmodelnr = 0/' "$mdu"
}
patch_mdu "$NEW/Stagnone_dxy01_15m.mdu" ""
for n in 0 1 2 3 4 5 6 7; do
    rank=$(printf "%04d" $n)
    patch_mdu "$NEW/Stagnone_dxy01_15m_${rank}.mdu" "${rank}"
done
echo "  MDUs patched (rank 0):"
grep -E "^(tStop|startDateTime|stopDateTime|restartFile)" "$NEW/Stagnone_dxy01_15m_0000.mdu" | sed 's/^/    /'

# Patch dimr_config (time stop)
DIMR="$NEW/dimr_config.xml"
cp "$DIMR" "$DIMR.bak"
sed -i "s|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 ${TSTOP_SEC}</time>|" "$DIMR"

# Cleanup output dir
rm -rf "$NEW/DFM_OUTPUT_Stagnone_dxy01_15m" 2>/dev/null || true
mkdir -p "$NEW/diag"

# Run preflight
echo ""
echo "=== Preflight BC coverage check ==="
bash "$ROOT/scripts/check_bc_coverage.sh" "$NEW" 2>&1 | tail -30

# Launch
echo ""
echo "=== Launching dimr ==="
cd "$NEW"
if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
    set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true; set -u
fi
export OMP_NUM_THREADS=8 KMP_HW_SUBSET=8c,1t
export PATH="$HOME/Scaricati/delft3dfm/lnx64/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/Scaricati/delft3dfm/lnx64/lib:${LD_LIBRARY_PATH:-}"
command -v mpiexec >/dev/null || { echo "ERROR: no mpiexec"; exit 4; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="diag/run_d${PUBLISH_DAY}_${STAMP}.log"
nohup bash -c "
  export OMP_NUM_THREADS=8 KMP_HW_SUBSET=8c,1t
  export PATH='$PATH'
  export LD_LIBRARY_PATH='$LD_LIBRARY_PATH'
  cd '$NEW'
  exec run_dimr.sh -c 8 -m dimr_config.xml
" > "$LOG" 2>&1 &
PID=$!
disown $PID 2>/dev/null || true
echo "  PID: $PID, log: $NEW/$LOG"
echo "Expected wall time ~25 min for 72h coupled."
