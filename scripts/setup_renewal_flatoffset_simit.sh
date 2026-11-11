#!/bin/bash
# Renewal case with a uniform water-level offset at the open boundary, on simit.
#   The case of setup_renewal_nudgesea_simit.sh, 1 to 10 July 2025, with the
#   per-node offset of build_v04_offset_bc.py replaced by its Marettimo anchor
#   of July 2025, +0.4812 m, on all 49 nodes. The per-node offset adds the
#   CMEMS mean dynamic topography of each node relative to Marettimo, about
#   2 cm higher at the northern end of the boundary than at the southern one,
#   which zos may already carry. The run tests whether that spread sets the
#   sea-level difference between the mouths of the lagoon and the
#   north-to-south throughflow. Every other input is that of the source case.
# Usage, on simit:  bash setup_renewal_flatoffset_simit.sh setup | launch
set -euo pipefail
SRC=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_nudgesea_0701_0710
CASE=/storage/ciceromartinsjr/StagnoneDT/renewal/veg_ic3d_flatoffset_0701_0710
BC=waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc
ANCHOR=0.4812
PICK=$HOME/simit_tools/simit_pick_cores.sh
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin

case "$1" in
  setup)
    mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }
    test ! -e "$CASE"
    mkdir -p "$CASE"
    (cd "$SRC" && find . -maxdepth 1 -type f ! -name '*_000[0-9]*' ! -name '*.cache' \
        ! -name 'DFM_interpreted_*' ! -name '*.dia' -exec cp -p {} "$CASE/" \;)
    awk -v a="$ANCHOR" '/^[-+]?[0-9]*\.[0-9]+[ \t]*$/ {print a; n++; next} {print}
        END {print n " values set" > "/dev/stderr"}' "$SRC/$BC" > "$CASE/$BC"
    sort -u <(grep -E '^[-+]?[0-9]*\.[0-9]+[ \t]*$' "$CASE/$BC")
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
