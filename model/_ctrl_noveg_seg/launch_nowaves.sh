#!/bin/bash
# v04AE_nowaves launch: FM-only, 8 MPI, no SWAN.
# oneAPI must be sourced explicitly: ~/.bashrc only sources it for interactive
# shells, and ssh "cmd" / nohup are non-interactive.
set -e
cd "$HOME/StagnoneDT/model/dflowfm_v04AE_nowaves"

source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
command -v mpiexec >/dev/null || { echo "ERROR: no mpiexec on PATH"; exit 4; }

mkdir -p diag
nohup bash -c "
  export PATH='$PATH'
  export LD_LIBRARY_PATH='$LD_LIBRARY_PATH'
  cd '$PWD'
  exec run_dimr.sh -c 8 -m dimr_config.xml
" > diag/run.log 2>&1 &

echo "launched pid $!"
disown
