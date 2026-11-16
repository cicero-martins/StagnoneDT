#!/bin/bash
# Seasonal renewal runs, present cover, without waves, on simit.
#   The case of setup_renewal_nudgesea_simit.sh, with the relaxation of salinity
#   and temperature confined to the sea, from a cold start:
#     summer  8 June to 15 September 2025, 99 days;
#     winter  8 November 2025 to 15 January 2026, 68 days.
#   Changes against that case:
#     forcing over the window of the season from build_forcing_renewal.py,
#       copied beforehand into $CASE/forcing (ERA5, AE wind blend, CMEMS
#       boundaries, daily CMEMS relaxation target, turbid laterals at zero);
#     initial salinity and temperature from the mean CMEMS profiles at the
#       start over the whole domain, the lagoon included, which starts at the
#       salinity of the sea (the 42 psu lagoon samples are removed);
#     waqInterval 1800 s, the hydrodynamics for the D-WAQ releases.
#   The online lagoon_tracer marks the lagoon water at the start.
# Usage, on simit:  bash setup_renewal_season_simit.sh summer|winter setup|launch
set -euo pipefail
case "${1:-}" in
  summer) CASE_NAME=veg_summer_0608_0915; NEW=20250607to20250917; D0=2025-06-07
          T0=2025-06-08; T1=2025-09-15 ;;
  winter) CASE_NAME=veg_winter_1108_0115; NEW=20251107to20260117; D0=2025-11-07
          T0=2025-11-08; T1=2026-01-15 ;;
  *) echo "usage: $0 summer|winter setup|launch"; exit 1 ;;
esac
SRC=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_nudgesea_0701_0710
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/$CASE_NAME
PICK=$HOME/simit_tools/simit_pick_cores.sh
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin
OLD=20250701to20250710
TSTOP=$(( $(date -ud "$T1" +%s) - $(date -ud "$T0" +%s) ))

case "${2:-}" in
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
           -e "s/nudge_salinity_temperature_2025-07-01_00-00-00\.nc/nudge_salinity_temperature_${D0}_00-00-00.nc/" \
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
        -e "s/^(startDateTime *= *)[0-9]+/\1${T0//-/}000000/" \
        -e "s/^(stopDateTime *= *)[0-9]+/\1${T1//-/}000000/" \
        -e "s/^(tStop *= *)[0-9.]+/\1${TSTOP}.0/" \
        -e 's/^(waqInterval *= *)[0-9.]+/\11800.0/' "$CASE/Stagnone_dxy01_15m.mdu"
    # every file the two .ext and the initial fields name must exist and cover the window
    missing=$(cd "$CASE" && { grep -hiE '^\s*(forcingFile|locationFile|discharge|FILENAME)\s*=' *_new.ext *_old.ext \
        | sed -E 's/^[^=]*=\s*//; s/\s.*$//'; grep -hE '^\s*dataFile\s*=' initialFields.ini | awk '{print $3}'; } \
        | tr -d '\r' | sort -u | while read -r f; do [[ -f "$f" ]] || echo "$f"; done)
    [[ -z "$missing" ]] || { echo "missing: $missing"; exit 3; }
    grep -n "$OLD\|2025-07-01" "$CASE"/*.ext && { echo "old window still referenced"; exit 3; }
    if grep -q 'ic3d_lagoon' "$CASE/initialFields.ini"; then echo "lagoon samples still in initialFields.ini"; exit 3; fi
    grep -H -E '^(refDate|startDateTime|stopDateTime|tStop|waqInterval|mapInterval|rstInterval|maxVelocity) ' "$CASE/Stagnone_dxy01_15m.mdu"
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
  *) echo "usage: $0 summer|winter setup|launch"; exit 1 ;;
esac
