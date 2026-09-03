#!/usr/bin/env bash
# Bring a model directory's inputs back from the run server.
#
# Runs launched on simit leave their inputs there. Nothing pulls them back, so
# after the vegetation ensemble only one of the eight factorial members had its
# inputs on this machine and the manuscript rested on a single host. This is the
# repair, and it is meant to be re-run after every batch.
#
# What comes across is everything needed to reproduce the run: the master and
# partition MDUs, both .ext files, the .bc, the .xyz, initialFields.ini,
# dimr_config.xml, the sediment and morphology files, the trachytope .arl/.ttd,
# and the whole wave/ directory. What stays behind is output and anything the
# kernel regenerates.
#
# wave/TMP_ESMF_RegridWeightGen_*.nc are INPUT despite the name. Without them
# SWAN aborts before writing a log and takes the shared MPI communicator with
# it, so FM dies in MPI_Comm_size with a null communicator and no FATAL
# anywhere. They are deliberately not in the exclude list.
#
# The files in scripts/model_shared_inputs.txt are skipped on the wire. They are
# identical in every member and already tracked in the baseline directory;
# complete_model_dir.py copies them in when a directory has to run.
#
#   bash scripts/pull_model_inputs.sh <dir> [<dir> ...]
#   bash scripts/pull_model_inputs.sh --factorial      # the paper's eight
#   bash scripts/pull_model_inputs.sh --all-veg        # everything [veg]-based
#   bash scripts/pull_model_inputs.sh --with-restart --all-veg
#
# --with-restart also brings restart_input/, the initial state each segment
# member starts from. It is 649 MB over the ensemble, in five distinct states,
# and it is bound to the eight-way METIS decomposition of the host that wrote
# it. It is also the one input that cannot be regenerated without re-running the
# nine-day parents, so the ensemble is not reproducible from a lost server
# without it.
#
# REMOTE=other-host bash scripts/pull_model_inputs.sh ... to pull elsewhere.
set -euo pipefail

REMOTE=${REMOTE:-simit}
RPATH=${RPATH:-StagnoneDT/model}
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEST=$ROOT/model
SHARED=$ROOT/scripts/model_shared_inputs.txt

FACTORIAL=(dflowfm_v04AE_nowaves _veg_hv040_3d
           dflowfm_v04AE_nodm _veg_waves
           dflowfm_v04AE_nowaves_dm_dens _veg_nowaves_dm
           dflowfm_v04AE_dens _veg_waves_dm)

# The factorial, the restart control that closes the segment-versus-continuous
# confound, the two probes behind the Rhoveg finding, the pair that established
# the inert trachytope sink, and the four arlfix members.
ALL_VEG=("${FACTORIAL[@]}" _ctrl_noveg_seg _veg_RHO900 _veg_RHO1020
         _trt_inert_A _trt_inert_B
         dflowfm_v04AE_nowaves_vr_arlfix dflowfm_v04AE_nodm_vr_arlfix
         dflowfm_v04AE_vr_dens_arlfix dflowfm_v04AE_nowaves_vrdm_dens_arlfix)

RESTART=no
if [ "${1:-}" = '--with-restart' ]; then RESTART=yes; shift; fi

case "${1:-}" in
    --factorial) DIRS=("${FACTORIAL[@]}") ;;
    --all-veg)   DIRS=("${ALL_VEG[@]}") ;;
    "")          sed -n '31,34p' "$0"; exit 1 ;;
    *)           DIRS=("$@") ;;
esac

# Output, and anything the kernel writes for itself. The partition net.nc and
# the .cache are METIS output and machine-bound; the restart files are bound to
# the partition count as well. See memory partition_files_machine_bound.
EXCL=(
    --exclude='DFM_OUTPUT_*'
    --exclude='*.cache'             --exclude='*.dia'
    --exclude='diag'                --exclude='*_000?_net.nc'
    --exclude='DFM_interpreted_idomain_*'
    --exclude='*_his.nc'
    --exclude='*_map.nc'            --exclude='*.bak*'
    --exclude='*.log'               --exclude='matrix_*.m'
    --exclude='wave/wavm-*'         --exclude='wave/swn-diag.*'
    --exclude='wave/PRINT*'         --exclude='wave/hot_*'
    --exclude='wave/INPUT'          --exclude='wave/NEST*'
    --exclude='wave/TMP_grid2swan*' --exclude='wave/BOTNOW'
    --exclude='wave/CURNOW'         --exclude='wave/WNDNOW'
    --exclude='wave/swaninit'       --exclude='wave/*.prt'
    --exclude='wave/*.sta'
)
# restart_input/ holds exactly *_rst.nc, so the two exclusions have to lift
# together or the directory arrives empty.
[ "$RESTART" = yes ] || EXCL+=(--exclude='restart_input' --exclude='*_rst.nc')

while read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    EXCL+=(--exclude="$line")
done < "$SHARED"

echo "from $REMOTE:$RPATH into ${DEST/$ROOT\//}"
echo "${#DIRS[@]} directories, $(grep -cve '^\s*#' -e '^\s*$' "$SHARED") shared inputs left on the wire"
[ "$RESTART" = yes ] && echo "restart_input included"
echo

mkdir -p "$DEST"
missing=()
for d in "${DIRS[@]}"; do
    if ! ssh "$REMOTE" "test -d '$RPATH/$d'" 2>/dev/null; then
        missing+=("$d"); printf '  %-42s not on the server\n' "$d"; continue
    fi
    ssh "$REMOTE" "cd '$RPATH' && tar czf - ${EXCL[*]} '$d'" 2>/dev/null \
        | tar xzf - -C "$DEST"
    n=$(find "$DEST/$d" -type f | wc -l)
    after=$(du -sm "$DEST/$d" 2>/dev/null | cut -f1)
    printf '  %-42s %4d files  %5s MB\n' "$d" "$n" "$after"
done

echo
if [ ${#missing[@]} -gt 0 ]; then
    echo "not found: ${missing[*]}"
fi
echo "these directories are incomplete by design. To run one:"
echo "  python scripts/complete_model_dir.py model/<dir>"
