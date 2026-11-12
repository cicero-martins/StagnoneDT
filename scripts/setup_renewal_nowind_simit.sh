#!/bin/bash
# Renewal case without wind, on simit.
#   The case of setup_renewal_nudgesea_simit.sh, 1 to 10 July 2025, with the
#   two wind components of the blended forcing set to zero over the whole
#   window. Pressure, evaporation, boundaries and relaxation are those of the
#   source case. The surface heat flux of the excess temperature model also
#   depends on wind speed and changes with it. The run tests whether the
#   sea-level step north of 37.91 N and the north-to-south throughflow
#   persist without wind, which would place their origin in the boundary
#   forcing or the geometry rather than in the wind over the coast.
# Usage, on simit:  bash setup_renewal_nowind_simit.sh setup | launch
set -euo pipefail
SRC=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_nudgesea_0701_0710
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_nowind_0701_0710
PICK=$HOME/simit_tools/simit_pick_cores.sh
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin
PYENV=$HOME/miniconda3/envs/stagnone_extract/bin/python
WIND="wind_blendedAE_u10n_20250701to20250710.nc:u10n wind_blendedAE_v10n_20250701to20250710.nc:v10n"

case "$1" in
  setup)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    test ! -e "$CASE"
    mkdir -p "$CASE"
    (cd "$SRC" && find . -maxdepth 1 -type f ! -name '*_000[0-9]*' ! -name '*.cache' \
        ! -name 'DFM_interpreted_*' ! -name '*.dia' -exec cp -p {} "$CASE/" \;)
    # the wind of every [Meteo] block must come from the two files zeroed here
    others=$(grep -hE '^\s*forcingFile\s*=' "$CASE"/*.ext | awk '{print $3}' | grep -i -E 'wind|u10|v10' \
        | grep -v -x -F -e "${WIND%%:*}" -e "$(echo "$WIND" | awk '{print $2}' | cut -d: -f1)" || true)
    others="$others$(grep -iE '^\s*QUANTITY\s*=\s*wind' "$CASE"/*_old.ext || true)"
    [[ -z "$others" ]] || { echo "other wind forcing in the .ext: $others"; exit 3; }
    for fv in $WIND; do
        "$PYENV" - "$CASE/${fv%%:*}" "${fv##*:}" <<'PY'
import sys
import netCDF4
with netCDF4.Dataset(sys.argv[1], "r+") as ds:
    v = ds[sys.argv[2]]
    v[:] = 0.0
    print(sys.argv[1].rsplit("/", 1)[-1], v.shape, "max |value| now", float(abs(v[:]).max()))
PY
    done
    ;;
  launch)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    cd "$CASE"
    [[ -z "$(for p in $(pgrep -u "$USER" -x dimr); do readlink /proc/$p/cwd; done | grep -x "$CASE" || true)" ]] \
        || { echo "dimr already running in $CASE"; exit 5; }
    mkdir -p diag
    source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1 || true
    nohup bash -c "
      CPUS=\$(bash '$PICK' 8 0 \$\$) || { echo 'no 8 free cores'; exit 2; }
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
