#!/bin/bash
# Readings of the renewal case after FM has finished, on simit.
#   merge   waqmerge joins the D-WAQ files of the eight partitions
#   waq     build_renewal_waq.py writes the input and delwaq runs in the background;
#           an integration option as second argument runs in waq_renewal_s<scheme>
#   releases  the repeated D-WAQ releases of the seasonal cases, in parallel
#   fm      the online lagoon_tracer, the throughflow and the currents for OpenDrift
# Outputs under $CASE/waq_renewal and $OUT, the currents file under $OUT/<tag>.
# The case is veg_ic3d_0701_0710 unless RENEWAL_CASE names another directory under
# renewal/, as veg_summer_0608_0915 or veg_winter_1108_0115.
# Usage, on simit:  [RENEWAL_CASE=<case>] bash postrun_renewal_case_simit.sh merge | waq [24.70] | releases | fm
set -euo pipefail
TAG=${RENEWAL_CASE:-veg_ic3d_0701_0710}
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/$TAG
[[ -d "$CASE" ]] || { echo "no case $CASE"; exit 3; }
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
  releases)
    # Repeated releases of the seasonal cases (docs/lagoon_renewal.md, Section 11):
    # every 10 days from 15 June (7) or 15 November (4), each a D-WAQ run with
    # scheme 24 from the release, where the basins hold 1, to the end of FM.
    # The runs are independent and share one launcher, one core each on socket 1.
    case "$TAG" in
      veg_summer_*) FIRST=2025-06-15; N=7 ;;
      veg_winter_*) FIRST=2025-11-15; N=4 ;;
      *) echo "no release calendar for $TAG"; exit 3 ;;
    esac
    STOP=$(sed -nE 's/^stopDateTime *= *([0-9]{4})([0-9]{2})([0-9]{2}).*/\1\/\2\/\3-00:00:00/p' \
        "$CASE/Stagnone_dxy01_15m.mdu")
    RUNS=()
    for k in $(seq 0 $((N - 1))); do
      R=$(date -ud "$FIRST + $((10 * k)) days" +%Y%m%d)
      RUN="$CASE/waq_release_$R"
      (cd "$SCRIPTS" && "$PY" build_renewal_waq.py "$CASE/DFM_DELWAQ_Stagnone_dxy01_15m/Stagnone_dxy01_15m.hyd" \
          "$CASE" "$RUN" --scheme 24.70 --start "${R:0:4}/${R:4:2}/${R:6:2}-00:00:00" --stop "$STOP" > /dev/null)
      RUNS+=("$RUN")
    done
    nohup bash -c "
      CPUS=\$(bash '$HOME/simit_tools/simit_pick_cores.sh' $N 1 \$\$) || { echo 'no $N free cores'; exit 2; }
      IFS=, read -ra C <<< \"\$CPUS\"
      i=0
      for r in ${RUNS[*]}; do
        (cd \$r && OMP_NUM_THREADS=1 taskset -c \${C[\$i]} '$BIN/run_delwaq.sh' renewal.inp > run.log 2>&1) &
        echo \"\$r on core \${C[\$i]}\"
        i=\$((i + 1))
      done
      wait
      echo 'all releases finished'
    " > "$CASE/diag/releases.log" 2>&1 < /dev/null &
    echo "releases launched, $N runs to $STOP, pid $!"
    disown
    ;;
  fm)
    # the currents cover the window of the case, read from the MDU
    win() { sed -nE "s/^$1 *= *([0-9]{4})([0-9]{2})([0-9]{2}).*/\1-\2-\3T00:00/p" "$CASE/Stagnone_dxy01_15m.mdu"; }
    cd "$SCRIPTS"
    "$PY" renewal_tracer_member.py "$CASE" "$TAG" --out "$OUT"
    "$PY" diagnose_lagoon_throughflow.py "$CASE" "$TAG" --out "$OUT"
    "$PY" extract_lagoon_currents_3d.py "$CASE" --out "$OUT/$TAG/currents_3d.nc" \
        --start "$(win startDateTime)" --stop "$(win stopDateTime)"
    ;;
esac
