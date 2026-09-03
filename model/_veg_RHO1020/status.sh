#!/bin/bash
# One-line status of the v04AE_nowaves run, for remote polling.
# Two traps this encodes, both of which produced false alarms already:
#   1. The MPI workers are named "dimr", not "dflowfm". pgrep on the wrong name
#      reports 0 processes on a perfectly healthy run.
#   2. A successful DIMR run does NOT print "computation finished". It ends
#      with a TIMER INFO block listing DIMR_EXE seconds. Grepping for the
#      wrong phrase makes a clean finish look like a silent crash.
cd "$HOME/StagnoneDT/model/dflowfm_v04AE_nowaves" 2>/dev/null || { echo "STATE=NODIR"; exit 0; }
L=$(grep -a '^\*\* INFO' diag/run.log 2>/dev/null | tail -1)
PCT=$(echo "$L"  | awk '{print $(NF-1)}')
ETA=$(echo "$L"  | awk '{print $(NF-4)" "$(NF-3)}')
ELAP=$(echo "$L" | awk '{print $(NF-6)" "$(NF-5)}')
SIM=$(echo "$L"  | awk '{print $4" "$5}')
ALIVE=$(pgrep -xc dimr 2>/dev/null || true); [ -z "$ALIVE" ] && ALIVE=0
AGE=$(( $(date +%s) - $(stat -c %Y diag/run.log 2>/dev/null || echo 0) ))
ERR=$(grep -aiE 'fatal|\*\* ERROR|abort|Segmentation|MPI_Abort' diag/run.log 2>/dev/null | tail -1 | cut -c1-160)
FIN=$(grep -acE 'DIMR_EXE|TIMER INFO' diag/run.log 2>/dev/null || true)
WALL=$(grep -aE 'DIMR_EXE' diag/run.log 2>/dev/null | tail -1 | awk '{print $(NF-1)}')
echo "PCT=${PCT:-?} SIM=${SIM:-?} ELAPSED=${ELAP:-?} ETA=${ETA:-?} PROCS=$ALIVE LOGAGE=${AGE}s FINMARK=${FIN:-0} WALL=${WALL:-} ERR=${ERR:-none}"
