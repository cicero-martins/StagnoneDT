#!/usr/bin/env bash
#
# Overnight chain: wait for current Jul 1-12 cold-start to finish, then run
# Jul 13 continuation (rst @ Jul 10 from current). Stops on first failure.
#
# Run on simit-server via nohup (survives SSH disconnect):
#   ssh ciceromartinsjr@147.163.48.52 \
#     "nohup bash ~/StagnoneDT/scripts/chain_overnight.sh > ~/StagnoneDT/runs/forecast/_chain.log 2>&1 &"
#
# Monitor next day:
#   ssh ciceromartinsjr@147.163.48.52 "tail -50 ~/StagnoneDT/runs/forecast/_chain.log"

set -uo pipefail

ROOT="${ROOT:-$HOME/StagnoneDT}"
CURRENT_PID="${CURRENT_PID:-213310}"   # Jul 1-12 cold-start launched by user earlier
CURRENT_DIR="$ROOT/runs/test_jul1-12"
CURRENT_DFM="$CURRENT_DIR/DFM_OUTPUT_Stagnone_dxy01_15m"
CURRENT_LOG="$(ls -t $CURRENT_DIR/diag/run_jul1-12_*.log 2>/dev/null | head -1)"

NODM="$ROOT/model/dflowfm_v04AE_nodm"
D10D12="$ROOT/model/dflowfm_v04AE_d10d12"  # has Jul 1-13 meteo
RUNS_FORECAST="$ROOT/runs/forecast"
LOG_FILE="$RUNS_FORECAST/_chain.log"

mkdir -p "$RUNS_FORECAST"
mkdir -p "$RUNS_FORECAST/restart_chain"

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

log "=== CHAIN START ==="
log "Current run PID: $CURRENT_PID"
log "Current dir: $CURRENT_DIR"
log "Current log: $CURRENT_LOG"

# === STAGE 1: wait for current Jul 1-12 to finish ===
log ""
log "STAGE 1 — wait for Jul 1-12 cold-start completion"
WAITED=0
while ps -p "$CURRENT_PID" > /dev/null 2>&1; do
    sleep 300  # 5 min
    WAITED=$((WAITED + 5))
    if (( WAITED % 30 == 0 )); then
        last_sim=$(grep -E 'INFO.*[0-9]d.*[0-9]+:00:00' "$CURRENT_DFM/Stagnone_dxy01_15m_0000.dia" 2>/dev/null | tail -1 | awk '{print $3" "$4}' || echo "n/a")
        log "  ...still running ($WAITED min waited), sim @ $last_sim"
    fi
    if (( WAITED > 240 )); then
        log "  TIMEOUT (>4h): aborting chain"
        exit 10
    fi
done
log "Current PID gone after $WAITED min."

# === STAGE 2: verify Jul 1-12 succeeded ===
log ""
log "STAGE 2 — verify Jul 1-12 result"
if grep -q "Computation finished" "$CURRENT_LOG"; then
    log "  PASS — 'Computation finished' found"
else
    log "  FAIL — no 'Computation finished' in log. Last 10 log lines:"
    tail -10 "$CURRENT_LOG" | sed 's/^/    /'
    log "Aborting chain."
    exit 11
fi

# Check no FATAL/SIGSEGV
if grep -qE 'FATAL|Segmentation fault' "$CURRENT_LOG"; then
    log "  WARN — found FATAL/SIGSEGV in log:"
    grep -E 'FATAL|Segmentation' "$CURRENT_LOG" | head -3 | sed 's/^/    /'
    log "Aborting chain."
    exit 12
fi

# Verify rst @ Jul 10 exists (we need this for the continuation)
RST_J10=$(ls "$CURRENT_DFM"/Stagnone_dxy01_15m_*_20250710_000000_rst.nc 2>/dev/null | wc -l)
if [[ "$RST_J10" -ne 8 ]]; then
    log "  FAIL — expected 8 rst @ Jul 10, found $RST_J10"
    log "Aborting chain."
    exit 13
fi
log "  8 rst @ Jul 10 found ✓"

# === STAGE 3: launch Jul 13 continuation (rst @ Jul 10, run Jul 10 -> Jul 13) ===
log ""
log "STAGE 3 — Jul 13 continuation (rst @ Jul 10, run 72h)"
PUBLISH_DAY="2025-07-13"
START_DATE="2025-07-10"
STOP_DATE="2025-07-13"
START_NOSEP="20250710"
STOP_NOSEP="20250713"
TSTOP_SEC=259200

NEW="$RUNS_FORECAST/d${PUBLISH_DAY}"
if [[ -d "$NEW" ]]; then
    mv "$NEW" "$NEW.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "$NEW"

# Clone nodm clean (NOT d10d12 — that was the polluted template)
rsync -a \
    --exclude='DFM_OUTPUT_Stagnone_dxy01_15m/' \
    --exclude='DFM_OUTPUT_*.bak.*' \
    --exclude='diag/run_*.log' \
    --exclude='diag/Stagnone_dxy01_15m_*.dia' \
    --exclude='diag/swn-diag*' \
    --exclude='wave/hot_*.nc' \
    --exclude='wave/BOTNOW' --exclude='wave/CURNOW' --exclude='wave/WNDNOW' \
    --exclude='wave/PRINT-*' --exclude='wave/swaninit' \
    --exclude='wave/swan_omp.exe' --exclude='wave/swn-diag.*' \
    --exclude='wave/esmf_sh.log' --exclude='wave/SWANOUT*' \
    --exclude='*.cache' \
    "$NODM"/ "$NEW"/
log "  Cloned $(du -sh $NEW | cut -f1)"

# Replace meteo + BCs with Jul 1-13 versions (BCs CRITICAL — nodm's only cover Jul 1-10)
rm -f "$NEW"/era5_*_20250701to20250710_ERA5.nc
rm -f "$NEW"/wind_blendedAE_*_20250701to20250710.nc
rm -f "$NEW"/wind_era5raw_*_20250701to20250710.nc
for f in "$D10D12"/era5_*_20250701to20250713_ERA5.nc \
         "$D10D12"/wind_blendedAE_*_20250701to20250713.nc \
         "$D10D12"/wind_era5raw_*_20250701to20250713.nc; do
    [[ -f "$f" ]] && cp "$f" "$NEW/"
done
# CMEMS BC files extended to Jul 1-13 (avoid EC-module Error at sim 9d)
for bc in waterlevelbnd_CMEMS_Stagnone_dxy01_15m.bc \
          salinitybnd_CMEMS_Stagnone_dxy01_15m.bc \
          temperaturebnd_CMEMS_Stagnone_dxy01_15m.bc \
          uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc; do
    [[ -f "$D10D12/$bc" ]] && cp "$D10D12/$bc" "$NEW/"
done

# Patch .ext files
for EXT in "$NEW/Stagnone_dxy01_15m_new.ext" "$NEW/Stagnone_dxy01_15m_old.ext"; do
    [[ -f "$EXT" ]] || continue
    cp "$EXT" "$EXT.bak"
    sed -i 's/_20250701to20250710/_20250701to20250713/g' "$EXT"
done

# Restart files (8 ranks)
mkdir -p "$NEW/restart_input"
for n in 0 1 2 3 4 5 6 7; do
    rank=$(printf "%04d" $n)
    cp "$CURRENT_DFM/Stagnone_dxy01_15m_${rank}_${START_NOSEP}_000000_rst.nc" "$NEW/restart_input/"
done
log "  8 rst @ $START_DATE installed"

# Patch MDUs — dates + restart only (no exotic patches)
patch_mdu() {
    local mdu="$1"
    local rank="$2"
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
}
patch_mdu "$NEW/Stagnone_dxy01_15m.mdu" ""
for n in 0 1 2 3 4 5 6 7; do
    rank=$(printf "%04d" $n)
    patch_mdu "$NEW/Stagnone_dxy01_15m_${rank}.mdu" "${rank}"
done
log "  MDUs patched (rank 0):"
grep -E "^(tStop|startDateTime|stopDateTime|restartFile)" "$NEW/Stagnone_dxy01_15m_0000.mdu" | sed 's/^/    /'

# Patch dimr_config
DIMR="$NEW/dimr_config.xml"
cp "$DIMR" "$DIMR.bak"
sed -i "s|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 ${TSTOP_SEC}</time>|" "$DIMR"

# Launch
cd "$NEW"
rm -rf DFM_OUTPUT_Stagnone_dxy01_15m 2>/dev/null || true
mkdir -p diag

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
    set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true; set -u
fi
export OMP_NUM_THREADS=8 KMP_HW_SUBSET=8c,1t
export PATH="$HOME/Scaricati/delft3dfm/lnx64/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/Scaricati/delft3dfm/lnx64/lib:${LD_LIBRARY_PATH:-}"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LAUNCH_LOG="diag/run_d${PUBLISH_DAY}_${STAMP}.log"
nohup bash -c "
  export OMP_NUM_THREADS=8 KMP_HW_SUBSET=8c,1t
  export PATH='$PATH'
  export LD_LIBRARY_PATH='$LD_LIBRARY_PATH'
  cd '$NEW'
  exec run_dimr.sh -c 8 -m dimr_config.xml
" > "$LAUNCH_LOG" 2>&1 &
JUL13_PID=$!
disown $JUL13_PID 2>/dev/null || true
log "  Launched PID $JUL13_PID, log: $NEW/$LAUNCH_LOG"

# === STAGE 4: monitor Jul 13 ===
log ""
log "STAGE 4 — monitor Jul 13 run"
WAITED=0
while ps -p "$JUL13_PID" > /dev/null 2>&1; do
    sleep 300
    WAITED=$((WAITED + 5))
    if (( WAITED % 15 == 0 )); then
        last_sim=$(grep -E 'INFO.*[0-9]d.*[0-9]+:00:00' "$NEW/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000.dia" 2>/dev/null | tail -1 | awk '{print $3" "$4}' || echo "n/a")
        log "  ...Jul 13 running ($WAITED min waited), sim @ $last_sim"
    fi
    if (( WAITED > 120 )); then
        log "  TIMEOUT (>2h): aborting"
        exit 20
    fi
done
log "Jul 13 PID gone after $WAITED min."

# Verify Jul 13
if grep -q "Computation finished" "$NEW/$LAUNCH_LOG"; then
    log "  Jul 13 PASS — 'Computation finished' found"
    log ""
    log "=== CHAIN END (Jul 13 OK) ==="
    log "Next steps (require user attention next session):"
    log "  - Validate Jul 13 outputs vs whatever ground truth"
    log "  - Extend ERA5+CMEMS forcings to Jul 1-16"
    log "  - Chain Jul 14, Jul 15 publish days"
    exit 0
else
    log "  Jul 13 FAIL — no 'Computation finished'. Tail:"
    tail -10 "$NEW/$LAUNCH_LOG" | sed 's/^/    /'
    log ""
    log "=== CHAIN END (Jul 13 FAILED, stopping per user instruction) ==="
    exit 21
fi
