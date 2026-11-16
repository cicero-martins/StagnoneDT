#!/bin/bash
# Summer renewal run, present cover, without waves, on simit.
#   The case of setup_renewal_nudgesea_simit.sh, with the relaxation of salinity
#   and temperature confined to the sea, from a cold start on 8 June 2025 to
#   15 September 2025, 99 days. Changes against that case:
#     forcing over 7 June to 17 September from build_forcing_summer2025.py,
#       copied beforehand into $CASE/forcing (ERA5, AE wind blend, CMEMS
#       boundaries, daily CMEMS relaxation target, turbid laterals at zero);
#     initial salinity and temperature from the mean CMEMS profiles of 8 June
#       over the whole domain, the lagoon included, which starts at the
#       salinity of the sea (the 42 psu lagoon samples are removed);
#     waqInterval 1800 s, the hydrodynamics for the D-WAQ releases.
#   The online lagoon_tracer marks the lagoon water of 8 June.
# Usage, on simit:  bash setup_renewal_summer_simit.sh setup | launch
set -euo pipefail
SRC=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_nudgesea_0701_0710
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_summer_0608_0915
PICK=$HOME/simit_tools/simit_pick_cores.sh
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin
OLD=20250701to20250710
NEW=20250607to20250917

case "$1" in
  setup)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    [[ -d "$CASE/forcing" ]] || { echo "copy the forcing into $CASE/forcing first"; exit 3; }
    [[ ! -e "$CASE/Stagnone_dxy01_15m.mdu" ]] || { echo "$CASE already set up"; exit 3; }
    (cd "$SRC" && find . -maxdepth 1 -type f ! -name '*_000[0-9]*' ! -name '*.cache' \
        ! -name 'DFM_interpreted_*' ! -name '*.dia' ! -name '*.log' ! -name "*$OLD*" \
        ! -name 'nudge_salinity_temperature_*' ! -name 'ic3d_*' ! -name '*CMEMS*.bc' \
        ! -name 'turbid_*.bc' -exec cp -p {} "$CASE/" \;)
    cp -p "$CASE"/forcing/* "$CASE/"
    sed -i -e "s/$OLD/$NEW/g" \
           -e 's/nudge_salinity_temperature_2025-07-01_00-00-00\.nc/nudge_salinity_temperature_2025-06-07_00-00-00.nc/' \
           "$CASE"/Stagnone_dxy01_15m_new.ext "$CASE"/Stagnone_dxy01_15m_old.ext
    # the lagoon starts from the profiles: drop the [Initial] block of the 42 psu samples
    # blocks start at a line opening with '['; blank lines may hold spaces, so no paragraph mode
    awk 'function flush() { if (b != "" && b !~ /dataFile *= *ic3d_lagoon_/) printf "%s", b; b = "" }
         /^\[/ { flush() } { b = b $0 "\n" } END { flush() }' "$CASE/initialFields.ini" > "$CASE/initialFields.tmp"
    mv "$CASE/initialFields.tmp" "$CASE/initialFields.ini"
    n_src=$(grep -c '^\[' "$SRC/initialFields.ini" || true)
    n_new=$(grep -c '^\[' "$CASE/initialFields.ini" || true)
    [[ $n_new == $((n_src - 1)) ]] || { echo "initialFields.ini: $n_new blocks from $n_src, expected one less"; exit 3; }
    sed -i -E \
        -e 's/^(startDateTime *= *)[0-9]+/\120250608000000/' \
        -e 's/^(stopDateTime *= *)[0-9]+/\120250915000000/' \
        -e 's/^(tStop *= *)[0-9.]+/\18553600.0/' \
        -e 's/^(waqInterval *= *)[0-9.]+/\11800.0/' "$CASE/Stagnone_dxy01_15m.mdu"
    # every file the two .ext and the initial fields name must exist and cover the window
    missing=$(cd "$CASE" && { grep -hiE '^\s*(forcingFile|locationFile|discharge|FILENAME)\s*=' *_new.ext *_old.ext \
        | sed -E 's/^[^=]*=\s*//; s/\s.*$//'; grep -hE '^\s*dataFile\s*=' initialFields.ini | awk '{print $3}'; } \
        | tr -d '\r' | sort -u | while read -r f; do [[ -f "$f" ]] || echo "$f"; done)
    [[ -z "$missing" ]] || { echo "missing: $missing"; exit 3; }
    grep -n "$OLD\|2025-07-01" "$CASE"/*.ext && { echo "old window still referenced"; exit 3; }
    if grep -q 'ic3d_lagoon' "$CASE/initialFields.ini"; then echo "lagoon samples still in initialFields.ini"; exit 3; fi
    grep -H -E '^(startDateTime|stopDateTime|tStop|waqInterval|mapInterval|rstInterval|maxVelocity) ' "$CASE/Stagnone_dxy01_15m.mdu"
    grep -E '^\s*(\[|quantity|dataFile\s*=)' "$CASE/initialFields.ini"
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
    " > diag/run.log 2>&1 < /dev/null &
    echo "launched $CASE, pid $!"
    disown
    ;;
esac
