#!/bin/bash
# Readings of the renewal case after FM has finished, on simit.
#   merge   waqmerge joins the D-WAQ files of the eight partitions
#   waq     build_renewal_waq.py writes the input and delwaq runs in the background;
#           an integration option as second argument runs in waq_renewal_s<scheme>
#   fm      the online lagoon_tracer, the throughflow and the currents for OpenDrift
# Outputs under $CASE/waq_renewal and $OUT, the currents file under $OUT/<tag>.
# Usage, on simit:  bash postrun_renewal_case_simit.sh merge | waq [24.70] | fm
set -euo pipefail
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_0701_0710
TAG=veg_ic3d_0701_0710
OUT=/storage/ciceromartinsjr/StagnoneDT/renewal/outputs
PY=$HOME/miniconda3/envs/stagnone_extract/bin/python
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin
SCRIPTS=$HOME/StagnoneDT/scripts

mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
[[ -z "$(for p in $(pgrep -u "$USER" -x dimr); do readlink /proc/$p/cwd; done | grep -x "$CASE" || true)" ]] \
    || { echo "FM still running in $CASE"; exit 5; }

case "$1" in
  merge)
    cd "$CASE"
    "$BIN/run_waqmerge.sh" Stagnone_dxy01_15m.mdu > diag/waqmerge.log 2>&1
    tail -3 diag/waqmerge.log
    ls -la DFM_DELWAQ_Stagnone_dxy01_15m/Stagnone_dxy01_15m.*
    ;;
  waq)
    cd "$SCRIPTS"
    SCHEME=${2:-15.70}
    RUN=waq_renewal; [[ "$SCHEME" == 15.70 ]] || RUN=waq_renewal_s${SCHEME%%.*}
    "$PY" build_renewal_waq.py "$CASE/DFM_DELWAQ_Stagnone_dxy01_15m/Stagnone_dxy01_15m.hyd" \
        "$CASE" "$CASE/$RUN" --scheme "$SCHEME"
    cd "$CASE/$RUN"
    nohup "$BIN/run_delwaq.sh" renewal.inp > run.log 2>&1 &
    echo "delwaq launched, pid $!"
    disown
    ;;
  fm)
    cd "$SCRIPTS"
    "$PY" renewal_tracer_member.py "$CASE" "$TAG" --out "$OUT"
    "$PY" diagnose_lagoon_throughflow.py "$CASE" "$TAG" --out "$OUT"
    "$PY" extract_lagoon_currents_3d.py "$CASE" --out "$OUT/$TAG/currents_3d.nc"
    ;;
esac
