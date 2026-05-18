#!/usr/bin/env bash
#
# Stagnone v04rAE -- Phase A: 1-day run Jul 8 -> Jul 9 2025
# Coupled D-Flow FM + SWAN via DIMR online, 8 MPI processes.
#
# Augments the canonical Deltares launcher pattern with:
#   - KMP/OMP env vars (SWAN OMP tuning, avoids over-threading on 96-CPU box)
#   - DFM_OUTPUT backup before run (avoids stale com.nc cross-machine gotcha)
#   - DFMROOT detection so the script works regardless of who installed dflowfm
#
# Usage:
#   ./run_model.sh                   # full: backup + partition + dimr
#   ./run_model.sh --skip-partition  # reuse existing _NNNN_.mdu/_NNNN_net.nc
#   ./run_model.sh --no-clean        # keep previous DFM_OUTPUT in place
#
# Memory cross-refs:
#   - stale_com_nc_cross_machine    -> backup DFM_OUTPUT before run
#   - hpc_optimization_xeon_64core  -> SWAN OMP cap via KMP_HW_SUBSET
#   - fm_restart_file_naming_gotcha -> restartFile in MDU must NOT include _NNNN_

set -euo pipefail

# ---- args ----
SKIP_PARTITION=0
DO_BACKUP=1
for arg in "$@"; do
  case "$arg" in
    --skip-partition) SKIP_PARTITION=1 ;;
    --no-clean)       DO_BACKUP=0 ;;
    *) echo "unknown flag: $arg"; exit 2 ;;
  esac
done

# ---- config ----
NPART="${NPART:-8}"
MDU_FILE="Stagnone_dxy01_15m.mdu"
DIMR_FILE="dimr_config.xml"
OUTPUT_DIR="DFM_OUTPUT_Stagnone_dxy01_15m"

# Force CWD = directory of this script
cd "$(dirname "$(readlink -f "$0")")"

# ---- locate Delft3DFM install ----
if [[ -n "${DFMROOT:-}" ]]; then
  :  # already exported by caller
elif [[ -d "$HOME/Scaricati/delft3dfm/lnx64" ]]; then
  DFMROOT="$HOME/Scaricati/delft3dfm/lnx64"
elif command -v run_dimr.sh >/dev/null 2>&1; then
  DFMROOT="$(dirname "$(dirname "$(command -v run_dimr.sh)")")"
else
  echo "ERROR: cannot find Delft3DFM Linux install. Set DFMROOT env var."
  exit 1
fi
export DFMROOT
export PATH="$DFMROOT/bin:$PATH"
export LD_LIBRARY_PATH="$DFMROOT/lib:${LD_LIBRARY_PATH:-}"

# ---- environment: SWAN threading + Intel MPI shm ----
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
export KMP_HW_SUBSET="${KMP_HW_SUBSET:-8c,1t}"
export KMP_AFFINITY="${KMP_AFFINITY:-granularity=fine,compact,1,0}"

echo "============================================================"
echo "Stagnone v04rAE -- Phase A 1-day run ($NPART MPI processes)"
echo "Working dir: $(pwd)"
echo "DFMROOT:     $DFMROOT"
echo "OMP_NUM_THREADS=$OMP_NUM_THREADS  KMP_HW_SUBSET=$KMP_HW_SUBSET"
echo "Start time:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"

# ---- [0/3] backup previous DFM_OUTPUT (avoids stale com.nc gotcha) ----
if [[ -d "$OUTPUT_DIR" && $DO_BACKUP -eq 1 ]]; then
  BACKUP="${OUTPUT_DIR}.bak.$(date +%Y%m%d_%H%M%S)"
  echo "[0/3] Backing up $OUTPUT_DIR -> $BACKUP"
  mv "$OUTPUT_DIR" "$BACKUP"
fi

# ---- ensure dimr_config has the right process list for NPART ----
PROCESSSTR="$(seq -s ' ' 0 $((NPART-1)))"
sed -i.bak "s|\(<process.*>\)[^<>]*\(<\/process.*\)|\1$PROCESSSTR\2|" "$DIMR_FILE"

# ---- [1/3] partition ----
if [[ $SKIP_PARTITION -eq 0 ]]; then
  echo "[1/3] Partitioning mesh into $NPART domains..."
  run_dflowfm.sh --partition:ndomains=$NPART:icgsolver=6 "$MDU_FILE"
else
  echo "[1/3] --skip-partition: reusing existing _NNNN_.mdu files."
fi

# ---- [2/3] launch DIMR coupled ----
echo "[2/3] Launching DIMR ($NPART MPI processes)..."
if [[ "$NPART" == "1" ]]; then
  run_dimr.sh -m "$DIMR_FILE"
else
  run_dimr.sh -c "$NPART" -m "$DIMR_FILE"
fi

# ---- [3/3] sanity checks ----
echo ""
echo "[3/3] Run complete. End time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Tail of rank-0 .dia:"
tail -30 "$OUTPUT_DIR/Stagnone_dxy01_15m_0000.dia" || true

echo ""
echo "============================================================"
echo "Quick sanity (run \`grep ... 0000.dia\` if these are empty):"
grep -E "nr of setbacks|total computation time \(h\)|Computation finished" \
  "$OUTPUT_DIR/Stagnone_dxy01_15m_0000.dia" 2>/dev/null || true
echo ""
echo "Expected (1d v04rAE coupled, on simit-server):"
echo "  setbacks         O(6000-8000)"
echo "  computation time ~0.3-0.5 h"
echo "  hwav.std() > 0   confirm via post-proc (notebook 24)"
echo "============================================================"
