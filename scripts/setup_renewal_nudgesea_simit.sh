#!/bin/bash
# Renewal case with the relaxation of salinity and temperature confined to the sea, on simit.
#   The case of setup_renewal_case_simit.sh, 1 to 10 July 2025, with the
#   relaxation toward the CMEMS fields (nudge_salinity_temperature) removed
#   inside the lagoon. The rate of relaxation is given as the [Parameter]
#   nudgerate of initialFields.ini, which FM reads in d^-1, 0.1 at sea as the
#   nudgeTimeUni of 10 days, and 0 where lagoon_tracer_init.xyz marks the lagoon, at the face centres.
#   wrimap_nudging writes the relaxation time to the map output for checking.
#   No D-WAQ output, the online lagoon_tracer being kept.
# Usage, on simit:  bash setup_renewal_nudgesea_simit.sh setup | launch
set -euo pipefail
SRC=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_0701_0710
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_nudgesea_0701_0710
PICK=$HOME/simit_tools/simit_pick_cores.sh
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin

case "$1" in
  setup)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    test ! -e "$CASE"
    mkdir -p "$CASE"
    (cd "$SRC" && find . -maxdepth 1 -type f ! -name '*_000[0-9]*' ! -name '*.cache' \
        ! -name 'DFM_interpreted_*' ! -name '*waqmerge.log' ! -name '*.dia' -exec cp -p {} "$CASE/" \;)
    awk '{printf "%s %s %.9e\n", $1, $2, (1 - $3) * 0.1}' "$SRC/lagoon_tracer_init.xyz" \
        > "$CASE/nudgerate_sea_only.xyz"
    cat >> "$CASE/initialFields.ini" <<'EOF'

[Parameter]
    quantity              = nudgerate
    dataFile              = nudgerate_sea_only.xyz
    dataFileType          = sample
    interpolationMethod   = averaging
    averagingType         = mean
    operand               = O
EOF
    f="$CASE/Stagnone_dxy01_15m.mdu"
    sed -i -E 's/^(waqInterval *= *)[0-9.]+/\10.0/' "$f"
    grep -q -i '^wrimap_nudging' "$f" \
        || sed -i -E 's/^(wrimap_turbulence *=.*)$/\1\nwrimap_nudging                    = 1/' "$f"
    grep -H -i -E '^(startDateTime|waqInterval|wrimap_turbulence|wrimap_nudging|nudgeTimeUni) ' "$f"
    awk '$3 == 0 {n++} END {print n, "faces without relaxation"}' "$CASE/nudgerate_sea_only.xyz"
    ;;
  launch)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    cd "$CASE"
    [[ -z "$(for p in $(pgrep -u "$USER" -x dimr); do readlink /proc/$p/cwd; done | grep -x "$CASE" || true)" ]] \
        || { echo "dimr already running in $CASE"; exit 5; }
    mkdir -p diag
    source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true
    nohup bash -c "
      CPUS=\$(bash '$PICK' 8 1 \$\$) || { echo 'no 8 free cores'; exit 2; }
      export I_MPI_PIN=1 I_MPI_PIN_PROCESSOR_LIST=\$CPUS I_MPI_WAIT_MODE=1 OMP_NUM_THREADS=1
      export PATH='$BIN:$PATH' LD_LIBRARY_PATH='${LD_LIBRARY_PATH:-}'
      echo \"pinned to \$CPUS\"
      cd '$CASE'
      bash run_model.sh
    " > diag/run.log 2>&1 &
    echo "launched $CASE, pid $!"
    disown
    ;;
esac
