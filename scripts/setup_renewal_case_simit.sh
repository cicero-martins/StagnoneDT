#!/bin/bash
# Hydrodynamic case of the lagoon renewal study, on simit.
#   The vegetated fixed-bed member without wave coupling (-V-, _veg_hv040_3d_ic3d)
#   from a cold start on 1 July 2025 with the stratified initial condition of
#   dflowfm_v04AE_nowaves_ic3d, run to 10 July, the end of the forcing. Three
#   readings of the same hydrodynamics follow from it: the online lagoon_tracer
#   of FM, particles in OpenDrift and D-Water Quality offline.
#   Changes against the vegetated segment, all in the MDU and initialFields.ini:
#     startDateTime 1 July, no restart file;
#     maxVelocity 25, the cap of the cold-start members, since 10 stopped the
#       uncoupled cold start (ucmag 13.3 offshore);
#     waqInterval 1800 s, the hydrodynamics for D-WAQ;
#     wrimap_turbulence 1, the vertical eddy viscosity for the particles;
#     the stratified initial profiles added to the canopy parameters.
# The case lives on /storage, where the map and D-WAQ output go.
# Ranks are pinned by simit_pick_cores.sh, socket 1 preferred.
# Usage, on simit:  bash setup_renewal_case_simit.sh setup | launch
set -euo pipefail
M=$HOME/StagnoneDT/model
VEG=$M/_veg_hv040_3d_ic3d
BARE=$M/dflowfm_v04AE_nowaves_ic3d
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_0701_0710
PICK=$HOME/simit_tools/simit_pick_cores.sh

case "$1" in
  setup)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    test ! -e "$CASE"
    mkdir -p "$CASE"
    (cd "$VEG" && find . -maxdepth 1 -type f ! -name '*.log' ! -name '*.dia' ! -name '*.bak' \
        ! -name 'status.sh' ! -name 'launch_*.sh' -exec cp -p {} "$CASE/" \;)
    cp -p "$BARE"/ic3d_* "$CASE/"
    # stratified initial condition of the bare member, canopy parameters of the
    # vegetated one
    { cat "$BARE/initialFields.ini"; echo;
      awk '/^\[Parameter\]/{p=1} p' "$VEG/initialFields.ini"; } > "$CASE/initialFields.ini"
    for f in "$CASE"/*.mdu; do
      sed -i -E \
        -e 's/^(startDateTime *= *)[0-9]+/\120250701000000/' \
        -e 's/^(restartFile *=).*/\1/' \
        -e 's/^(restartDateTime *=).*/\1/' \
        -e 's/^(maxVelocity *= *)[0-9.]+/\125.0/' \
        -e 's/^(waqInterval *= *)[0-9.]+/\11800.0/' \
        -e 's/^(wrimap_turbulence *= *)[0-9]+/\11/' "$f"
    done
    grep -H -E '^(startDateTime|stopDateTime|restartFile|maxVelocity|waqInterval|wrimap_turbulence) ' \
        "$CASE"/Stagnone_dxy01_15m.mdu "$CASE"/Stagnone_dxy01_15m_0000.mdu
    grep -c '^\[' "$CASE/initialFields.ini"
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
      export PATH='$PATH' LD_LIBRARY_PATH='${LD_LIBRARY_PATH:-}'
      echo \"pinned to \$CPUS\"
      cd '$CASE'
      exec run_dimr.sh -c 8 -m dimr_config.xml
    " > diag/run.log 2>&1 &
    echo "launched $CASE, pid $!"
    disown
    ;;
esac
