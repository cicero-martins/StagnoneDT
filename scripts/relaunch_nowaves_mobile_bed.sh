#!/bin/bash
# Relaunch the two no-wave mobile-bed members, alone on the machine.
#
# The previous attempt did not abort numerically. Both ranks sets were killed by
# SIGNAL 9 at 47.7% and 50.0%, while the time step was steady near 4 s and
# falling only 6% over the preceding 26 h of simulated time. Five runs were
# writing concurrently at the time, two of them 37-38 GB coupled members. So
# this launches the two on their own, with no parameter changes: there is no
# evidence that anything about the configuration needs changing.
#
# The launch_nowaves.sh sitting in each clone is stale. It hardcodes
# cd .../dflowfm_v04AE_nowaves and then reuses $PWD, so it would run the base
# member from inside either clone. Do not reuse it.
set -e
cd "$HOME/StagnoneDT/model"

source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
command -v mpiexec >/dev/null || { echo "ERROR: no mpiexec on PATH"; exit 4; }

for d in dflowfm_v04AE_nowaves_dm dflowfm_v04AE_nowaves_vrdm; do
  cd "$HOME/StagnoneDT/model/$d"

  # keep the killed output for comparison, do not overwrite it
  if [ -d DFM_OUTPUT_Stagnone_dxy01_15m ]; then
    rm -rf DFM_OUTPUT_Stagnone_dxy01_15m.killed_20260806
    mv DFM_OUTPUT_Stagnone_dxy01_15m DFM_OUTPUT_Stagnone_dxy01_15m.killed_20260806
  fi
  mkdir -p diag
  mv -f diag/run.log diag/run.log.killed_20260806 2>/dev/null || true

  nohup bash -c "
    export PATH='$PATH'
    export LD_LIBRARY_PATH='$LD_LIBRARY_PATH'
    cd '$HOME/StagnoneDT/model/$d'
    exec run_dimr.sh -c 8 -m dimr_config.xml
  " > diag/run.log 2>&1 &
  echo "launched $d  pid $!"
  disown
done

echo
echo "16 MPI ranks total on 96 cores, nothing else running."
free -g | head -2
