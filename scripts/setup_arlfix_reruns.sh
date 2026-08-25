#!/bin/bash
# Prepare re-runs of the factorial's variable-roughness arm with the corrected
# .arl (9 decimals instead of 6).
#
# The old file quantised link coordinates to ~9 cm while FM matches them to a
# net link within 1 cm, so ~94% of the seagrass map was silently discarded and
# every VR member ran on ~5.5% of the meadow.  These four members are the VR
# cells of the 2x2x2 design: {waves, no waves} x {fixed bed, mobile bed}.
#
# Clones go to <member>_arlfix so the existing output -- which is what the
# Paper 1 figures were made from -- is left untouched.
#
#   bash setup_arlfix_reruns.sh          # prepare only
#   bash setup_arlfix_reruns.sh --launch # prepare and start all four
set -e

BASE=~/StagnoneDT/model
ARL=~/StagnoneDT/data/processed/planet2023_rf_v3/stagnone_trachytopes_v3.arl
ARL_NAME=stagnone_trachytopes_v3.arl
LOGDIR=~/arlfix_logs

COUPLED="v04AE_vr_dens v04AE_nodm_vr"          # waveModelNr=3, needs SWAN
NOWAVES="v04AE_nowaves_vrdm_dens v04AE_nowaves_vr"
MEMBERS="$COUPLED $NOWAVES"

if [ ! -f "$ARL" ]; then echo "missing $ARL"; exit 1; fi
mkdir -p "$LOGDIR"

echo "=== preparing ==="
for m in $MEMBERS; do
    src=$BASE/dflowfm_$m
    dst=$BASE/dflowfm_${m}_arlfix
    [ -d "$src" ] || { echo "  $m: source missing, skipped"; continue; }
    rm -rf "$dst"; mkdir -p "$dst"

    # Excluded on purpose:
    #   DFM_OUTPUT_*        regenerable, and the originals must survive
    #   *_0NNN.*/_0NNN_*    partition files; re-partitioned below, and they are
    #                       machine-bound anyway
    #   hot_*.nc            stale SWAN hot files cause a deterministic segfault
    #                       when a clone's sim time hits a pre-existing name
    #   swn-diag/*.dia/logs bulky leftovers
    # Kept on purpose:
    #   wave/TMP_ESMF_*.nc  these are INPUT for SWAN init under DIMR, not cache;
    #                       without them wave aborts silently and FM dies on
    #                       MPI_Comm_size(comm=0x0)
    # The partition excludes are anchored to the model root with a leading '/'.
    # Unanchored, '*_0NNN.*' also matches wave/TMP_ESMF_..._0001.nc and quietly
    # strips 10 of the 26 ESMF weight files -- which would make SWAN abort at
    # init and take FM down with MPI_Comm_size(comm=0x0).
    rsync -a \
        --exclude='DFM_OUTPUT_*' \
        --exclude='/*_0[0-9][0-9][0-9].*' \
        --exclude='/*_0[0-9][0-9][0-9]_*' \
        --exclude='hot_*.nc' \
        --exclude='*.bak*' \
        --exclude='*.dia' \
        --exclude='swn-diag.*' \
        --exclude='diag/' \
        "$src/" "$dst/"

    cp "$ARL" "$dst/$ARL_NAME"

    dec=$(grep -v '^#' "$dst/$ARL_NAME" | head -1 | awk '{print $1}' | cut -d. -f2 | wc -c)
    esmf=$(ls "$dst"/wave/TMP_ESMF*.nc 2>/dev/null | wc -l)
    part=$(ls "$dst" | grep -cE '_0[0-9]{3}[._]' || true)
    printf "  %-30s arl_decimals=%s  esmf=%s  stale_partitions=%s\n" \
           "${m}_arlfix" "$((dec-1))" "$esmf" "$part"
done

if [ "$1" != "--launch" ]; then
    echo; echo "prepared. re-run with --launch to start."
    exit 0
fi

echo; echo "=== launching ==="
# oneAPI must be sourced explicitly: ~/.bashrc only sources it for interactive
# shells, and nohup gets a non-interactive one.
for m in $MEMBERS; do
    dst=$BASE/dflowfm_${m}_arlfix
    [ -d "$dst" ] || continue
    cd "$dst"
    nohup bash -c "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1;
                   export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64;
                   export PATH=\$DELFT3D_HOME/bin:\$PATH;
                   export LD_LIBRARY_PATH=\$DELFT3D_HOME/lib:\$LD_LIBRARY_PATH;
                   bash run_model.sh" \
          > "$LOGDIR/${m}_arlfix.log" 2>&1 &
    echo "  $m -> pid $! , log $LOGDIR/${m}_arlfix.log"
    sleep 20        # stagger: the partition step is I/O heavy
done

echo; echo "all launched. monitor with:"
echo "  tail -f $LOGDIR/*.log"
echo "  grep -l 'Computation finished' $BASE/dflowfm_*_arlfix/DFM_OUTPUT_*/*.dia"
