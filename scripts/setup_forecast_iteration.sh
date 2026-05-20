#!/usr/bin/env bash
#
# Setup + auto-launch one iteration of the Phase B forecast pipeline.
# Runs on simit-server. Parameterized by publish-day.
#
# Window: [publish_day - 2d, publish_day] — N-2 restart workflow.
# Restart: from previous-iteration run (or from nodm for the first 2 iters).
# Forcings: cloned from v04AE_d10d12 (Jul 1-13 covers iters publishing Jul 11/12/13).
#
# Usage:
#   bash setup_forecast_iteration.sh 2025-07-11
#   PUBLISH_DAY=2025-07-12 bash setup_forecast_iteration.sh
#
# Idempotent: existing target dir is backed up to .bak.<timestamp>.
# After setup, launches dimr in background via nohup; PID logged.

set -euo pipefail

PUBLISH_DAY="${1:-${PUBLISH_DAY:-}}"
[[ -n "$PUBLISH_DAY" ]] || { echo "ERROR: PUBLISH_DAY required (YYYY-MM-DD)"; exit 1; }

# Date arithmetic (GNU date)
# Strategy A.1: N-3 restart, 72h run, drop first 48h (warmup+spinup), publish last 24h.
# Warmup needed because restart transient (FM-SWAN sync mismatch) blows up offshore cells
# without spin-up history. nodm cold-start tolerates this because it builds wave field over days.
START_DATE=$(date -u -d "$PUBLISH_DAY - 3 days" +%Y-%m-%d)
STOP_DATE="$PUBLISH_DAY"
START_NOSEP=$(date -u -d "$START_DATE" +%Y%m%d)
STOP_NOSEP=$(date -u -d "$STOP_DATE" +%Y%m%d)
PREV_DAY=$(date -u -d "$PUBLISH_DAY - 1 day" +%Y-%m-%d)
TSTOP_SEC=$(( (\
    $(date -u -d "$STOP_DATE" +%s) - $(date -u -d "$START_DATE" +%s)\
  ) ))

# Paths
ROOT="${ROOT:-$HOME/StagnoneDT}"
TEMPLATE="${TEMPLATE:-$ROOT/model/dflowfm_v04AE_d10d12}"     # cloned base (has forcings)
NODM_OUT="${NODM_OUT:-$ROOT/model/dflowfm_v04AE_nodm/DFM_OUTPUT_Stagnone_dxy01_15m}"
RUNS_DIR="${RUNS_DIR:-$ROOT/runs/forecast}"
NEW="$RUNS_DIR/d${PUBLISH_DAY}"
RESTART_CHAIN="$RUNS_DIR/restart_chain"

echo "=== Forecast iteration setup ==="
echo "  publish_day : $PUBLISH_DAY"
echo "  window      : $START_DATE 00:00 -> $STOP_DATE 00:00 (${TSTOP_SEC} s)"
echo "  template    : $TEMPLATE"
echo "  target      : $NEW"

[[ -d "$TEMPLATE" ]] || { echo "ERROR: template $TEMPLATE not found"; exit 2; }

# Strategy B (cold-start mode): skip restart entirely. Each iteration is independent
# cold-start with 1-2d spinup, publish last 24h. Avoids FM rst <-> SWAN cold-start
# mismatch that injected gravity-wave ringing in continuation runs (visible as ~58cm
# WL oscillations at BocaNord vs nodm). Trade-off: each daily run is independent
# (no chain), needs full forcings for N-3..N window.

echo "  MODE: cold-start (no restart file)"

# 1. Clone template -> NEW (exclude bulky outputs, runtime logs)
echo "=== [1/6] Cloning template -> d${PUBLISH_DAY} ==="
if [[ -d "$NEW" ]]; then
    STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    echo "  Target exists, backing up to $NEW.bak.$STAMP"
    mv "$NEW" "$NEW.bak.$STAMP"
fi
mkdir -p "$NEW"
rsync -a \
  --exclude='DFM_OUTPUT_Stagnone_dxy01_15m/' \
  --exclude='DFM_OUTPUT_*.bak.*' \
  --exclude='restart_input/' \
  --exclude='*.cache' \
  --exclude='run_*.log' \
  --exclude='diag/run_*.log' \
  --exclude='wave/BOTNOW' --exclude='wave/CURNOW' --exclude='wave/WNDNOW' \
  --exclude='wave/PRINT-*' --exclude='wave/swan_omp.exe' \
  --exclude='wave/swaninit' \
  --exclude='wave/hot_*.nc' \
  --exclude='wave/SWANOUT*' --exclude='wave/swn-diag.*' --exclude='wave/esmf_sh.log' \
  "$TEMPLATE"/ "$NEW"/
echo "  Cloned $(du -sh $NEW | cut -f1)"

# 2. (Cold-start mode: no restart files needed)
echo "=== [2/6] Cold-start mode — no restart files ==="
# Remove any pre-existing restart_input/ from previous attempts at this path
rm -rf "$NEW/restart_input" 2>/dev/null || true

# 3. Patch master + 8 per-partition MDUs
echo "=== [3/6] Patching MDUs (master + 8 per-partition) ==="
patch_mdu() {
    local mdu="$1"
    local rank="$2"  # empty for master, "_NNNN" for per-partition (unused in cold-start)
    [[ -f "$mdu" ]] || { echo "  WARN: $mdu not found"; return; }
    cp "$mdu" "$mdu.bak"
    sed -i "s/^tStop\s*=.*/tStop                   = ${TSTOP_SEC}.0/" "$mdu"
    sed -i "s/^startDateTime\s*=.*/startDateTime           = ${START_NOSEP}000000/" "$mdu"
    sed -i "s/^stopDateTime\s*=.*/stopDateTime            = ${STOP_NOSEP}000000/" "$mdu"
    # Cold-start mode: empty restartFile + restartDateTime
    sed -i 's|^restartFile\s*=.*|restartFile     =|' "$mdu"
    sed -i 's|^restartDateTime\s*=.*|restartDateTime =|' "$mdu"
    # Caps (per v04AE_continuation_mdu_patches memory)
    sed -i 's/^maxVelocity\s*=.*/maxVelocity               = 15.0           # raised from 10 to absorb tide+wind peak/' "$mdu"
    sed -i 's/^saliMax\s*=.*/saliMax                        = 80.0           # clip intertidal blowup/' "$mdu"
    # D-Morph off for paper-1 baseline
    sed -i 's/^Sedimentmodelnr\s*=.*/Sedimentmodelnr = 0/' "$mdu"
    # iniFieldFile = initialFields.ini (cold-start needs hypersaline initial salinity)
    sed -i 's|^iniFieldFile\s*=.*|iniFieldFile    = initialFields.ini|' "$mdu"
    # ComInterval = 3600 (default, same as nodm — tested 600 didn't help, just slowed)
    if ! grep -qiE "^ComInterval" "$mdu"; then
        sed -i '/^rstInterval/a ComInterval                       = 3600.0                     # FM<->SWAN coupling [s] — default, nodm-compat' "$mdu"
    else
        sed -i 's/^ComInterval\s*=.*/ComInterval                       = 3600.0                     # FM<->SWAN coupling [s] — default, nodm-compat/' "$mdu"
    fi
    # dtMax = 30 (default, same as nodm — tested 10-15 didn't help either)
    sed -i 's/^dtMax\s*=.*/dtMax                   = 30.0           # Maximal computation timestep (default)/' "$mdu"
    # NOTE: limTypSa and limTypMom left at defaults (4) — minmod=1 didn't prevent
    # the cell 13162 blowup, so reverting. Restart transient is the real issue;
    # warmup (-3d strategy) addresses it from the cause.
}

patch_mdu "$NEW/Stagnone_dxy01_15m.mdu" ""
for n in 0 1 2 3 4 5 6 7; do
    rank=$(printf "%04d" $n)
    patch_mdu "$NEW/Stagnone_dxy01_15m_${rank}.mdu" "${rank}"
done
echo "  Rank 0 sample:"
grep -E "^(tStop|startDateTime|stopDateTime|restartFile|Sedimentmodelnr)" "$NEW/Stagnone_dxy01_15m_0000.mdu"

# 4. Patch dimr_config
echo "=== [4/6] Patching dimr_config.xml ==="
DIMR="$NEW/dimr_config.xml"
cp "$DIMR" "$DIMR.bak"
sed -i "s|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 ${TSTOP_SEC}</time>|" "$DIMR"
grep -E "<(time|process)" "$DIMR" | head -3

# 5. Cleanup stale outputs
echo "=== [5/6] Cleanup ==="
rm -f "$NEW"/*.cache 2>/dev/null || true
rm -rf "$NEW/DFM_OUTPUT_Stagnone_dxy01_15m" 2>/dev/null || true
mkdir -p "$NEW/diag"

# 6. Launch (nohup, oneAPI sourced)
echo "=== [6/6] Launching dimr (nohup, background) ==="
cd "$NEW"
# oneAPI: ~/.bashrc only sources in interactive shells (memory simit_oneapi_nohup_sourcing)
if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
    set +u
    source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true
    set -u
fi
export OMP_NUM_THREADS=8
export KMP_HW_SUBSET=8c,1t
export PATH="$HOME/Scaricati/delft3dfm/lnx64/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/Scaricati/delft3dfm/lnx64/lib:${LD_LIBRARY_PATH:-}"

command -v mpiexec >/dev/null || { echo "ERROR: no mpiexec on PATH"; exit 4; }

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
echo "  PID: $PID"
echo "  Log: $NEW/$LOG"
echo "  Tail with: ssh ... 'tail -f $NEW/$LOG'"
echo ""
echo "Window finishes ${TSTOP_SEC}s sim time; expect ~25 min wall time."
