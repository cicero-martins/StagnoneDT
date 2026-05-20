#!/usr/bin/env bash
#
# Setup v04AE_nodm on simit-server: clone v04AE (Jul 1-10 window),
# disable D-Morph (Sedimentmodelnr=0). No restart, cold start same as v04AE.
# Same meteo + BC files; only MDU patched (Sedimentmodelnr in master + per-rank).
#
# Idempotent: existing v04AE_nodm is backed up to .bak.<timestamp>.

set -euo pipefail

V04AE="${V04AE:-$HOME/StagnoneDT/model/dflowfm_v04AE}"
NEW="${NEW:-$HOME/StagnoneDT/model/dflowfm_v04AE_nodm}"

[[ -d "$V04AE" ]] || { echo "ERROR: $V04AE not found"; exit 2; }

echo "=== [1/4] Cloning v04AE -> v04AE_nodm ==="
if [[ -d "$NEW" ]]; then
  STAMP=$(date +%Y%m%d_%H%M%S)
  echo "  Target exists, backing up to $NEW.bak.$STAMP"
  mv "$NEW" "$NEW.bak.$STAMP"
fi
mkdir -p "$NEW"
rsync -a \
  --exclude='DFM_OUTPUT_Stagnone_dxy01_15m/' \
  --exclude='DFM_OUTPUT_*.bak.*' \
  --exclude='*.cache' \
  --exclude='run_*.log' \
  --exclude='wave/BOTNOW' --exclude='wave/CURNOW' --exclude='wave/WNDNOW' \
  --exclude='wave/PRINT-*' --exclude='wave/swan_omp.exe' \
  --exclude='wave/swaninit' \
  "$V04AE"/ "$NEW"/
echo "  Cloned $(du -sh $NEW | cut -f1)"

echo "=== [2/5] Patching master MDU (Sedimentmodelnr=0 + 9d window + ComInterval) ==="
MDU="$NEW/Stagnone_dxy01_15m.mdu"
cp "$MDU" "$MDU.bak"
sed -i 's/^Sedimentmodelnr\s*=.*/Sedimentmodelnr = 0               # D-Morph OFF (paper 1: hydrodynamic skill)/' "$MDU"
# Force full 9-day window (defensive: previous tests may have shortened it)
sed -i 's/^tStop\s*=.*/tStop                   = 777600.0       # 9 days (Jul 1 -> Jul 10 2025)/' "$MDU"
sed -i 's/^startDateTime\s*=.*/startDateTime           = 20250701000000/' "$MDU"
sed -i 's/^stopDateTime\s*=.*/stopDateTime            = 20250710000000/' "$MDU"
# Inject ComInterval=3600 (matches DIMR coupling step). Without it, FM never writes com.nc
# after init -> SWAN can't read flow fields on 2nd coupling step -> ABORT.
# Insert just after rstInterval if not already present.
if ! grep -qiE "^ComInterval" "$MDU"; then
  sed -i '/^rstInterval/a ComInterval                       = 3600.0                     # Communication file (com.nc) write interval [s] for FM<->SWAN coupling' "$MDU"
fi
grep -niE "^Sedimentmodelnr|^MorFile|^SedFile|^tStop|^startDateTime|^stopDateTime|^maxVelocity|^saliMax|^ComInterval" "$MDU"

echo "=== [3/5] Patching per-partition MDUs ==="
for n in 0 1 2 3 4 5 6 7; do
  rank=$(printf "%04d" $n)
  PMDU="$NEW/Stagnone_dxy01_15m_${rank}.mdu"
  if [[ -f "$PMDU" ]]; then
    cp "$PMDU" "$PMDU.bak"
    sed -i 's/^Sedimentmodelnr\s*=.*/Sedimentmodelnr = 0/' "$PMDU"
    sed -i 's/^tStop\s*=.*/tStop                   = 777600.0/' "$PMDU"
    sed -i 's/^startDateTime\s*=.*/startDateTime           = 20250701000000/' "$PMDU"
    sed -i 's/^stopDateTime\s*=.*/stopDateTime            = 20250710000000/' "$PMDU"
    if ! grep -qiE "^ComInterval" "$PMDU"; then
      sed -i '/^rstInterval/a ComInterval                       = 3600.0' "$PMDU"
    fi
  else
    echo "  WARN: $PMDU not found"
  fi
done
echo "  Rank 0 verification:"
grep -E "^Sedimentmodelnr|^tStop|^startDateTime|^stopDateTime" "$NEW/Stagnone_dxy01_15m_0000.mdu" 2>/dev/null || true

echo "=== [4/5] Patching dimr_config.xml (coupling time = 9d) ==="
DIMR="$NEW/dimr_config.xml"
if [[ -f "$DIMR" ]]; then
  cp "$DIMR" "$DIMR.bak"
  sed -i 's|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 777600</time>|' "$DIMR"
  grep -E "(time|process)>" "$DIMR" | head -5
fi

echo "=== [5/5] Cleanup ==="
rm -f "$NEW"/*.cache 2>/dev/null || true
rm -f "$NEW/wave/swaninit"
# Wipe stale DFM_OUTPUT from any previous failed launch (just in case)
rm -rf "$NEW/DFM_OUTPUT_Stagnone_dxy01_15m" 2>/dev/null || true

echo ""
echo "Setup complete. Window unchanged from v04AE: Jul 1 -> Jul 10 2025 (9 days)."

# Auto-launch unless NOLAUNCH=1
if [[ "${NOLAUNCH:-0}" == "1" ]]; then
  echo ""
  echo "NOLAUNCH=1 set, skipping launch. To run manually:"
  echo "  cd $NEW && bash $(realpath $0 | sed 's|setup_v04AE_nodm_server.sh|launch_v04AE_nodm.sh|')"
  exit 0
fi

echo ""
echo "=== [6/5] Launching run (background, nohup) ==="
cd "$NEW"
mkdir -p diag

# Source Intel oneAPI (mpiexec lives at /opt/intel/oneapi/mpi/2021.10.0/bin/mpiexec).
# The user's ~/.bashrc only sources oneAPI in interactive shells, so non-interactive
# launches via nohup need it explicitly.
if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
  # setvars.sh is noisy; silence its banner via > /dev/null but keep errors
  set +u
  source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true
  set -u
fi

export OMP_NUM_THREADS=8
export KMP_HW_SUBSET=8c,1t
export PATH="$HOME/Scaricati/delft3dfm/lnx64/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/Scaricati/delft3dfm/lnx64/lib:${LD_LIBRARY_PATH:-}"

# Sanity check: mpiexec must be on PATH now
if ! command -v mpiexec >/dev/null 2>&1; then
  echo "ERROR: mpiexec not on PATH after sourcing oneAPI."
  echo "       Looked for /opt/intel/oneapi/setvars.sh — exists? $([[ -f /opt/intel/oneapi/setvars.sh ]] && echo yes || echo NO)"
  echo "       Try: source /opt/intel/oneapi/setvars.sh && which mpiexec"
  exit 4
fi
echo "  mpiexec: $(command -v mpiexec)"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="diag/run_nodm_${STAMP}.log"
# Pass the now-set environment through to nohup
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
echo "Monitor with:"
echo "  tail -f $NEW/$LOG"
echo "  ps -p $PID  # check still running"
echo "  grep -E 'FATAL|ERROR|finished' $NEW/$LOG"
