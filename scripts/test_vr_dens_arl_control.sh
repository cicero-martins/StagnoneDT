#!/bin/bash
# Is the corrected .arl really what makes v04AE_vr_dens diverge?
#
# The member aborts on MinTimestepBreak at roughly one simulated hour with the
# 9-decimal .arl, twice, while the original completed nine days.  A full
# checksum comparison of all 76 input files shows the clone differs from the
# original only in the .arl, so the .arl is the obvious suspect.  But the
# failing cells sit in the Egadi, three to thirty kilometres beyond the .arl's
# eastern edge, which is a long way for a lagoon roughness field to reach.
#
# So test it directly.  Two clones of the same original, same procedure, same
# guard, differing in one file:
#
#   _trt_test_arl_old   the 6-decimal .arl the original ran with
#   _trt_test_arl_new   the 9-decimal .arl
#
# old survives and new dies  -> the .arl is the cause, clone procedure clean
# both die                   -> the clone procedure or the machine is the cause
# both survive               -> the divergence needs longer than this window
#
# Six simulated hours is enough: both previous aborts came before one hour.
# At roughly three wall hours for nine days coupled, that is a few minutes each.
#
#   bash test_vr_dens_arl_control.sh
set -e

BASE=~/StagnoneDT/model
SRC=$BASE/dflowfm_v04AE_vr_dens
ARL_NEW=~/StagnoneDT/data/processed/planet2023_rf_v3/stagnone_trachytopes_v3.arl
ARL_NAME=stagnone_trachytopes_v3.arl
LOGDIR=~/arlfix_logs
STOP=20250701060000

mkdir -p "$LOGDIR"
[ -d "$SRC" ] || { echo "missing $SRC"; exit 1; }
[ -f "$ARL_NEW" ] || { echo "missing $ARL_NEW"; exit 1; }

for variant in old new; do
    dst=$BASE/_trt_test_arl_$variant
    rm -rf "$dst"; mkdir -p "$dst"

    # Same excludes as setup_arlfix_reruns.sh.  The partition patterns are
    # anchored with a leading '/': unanchored they also match
    # wave/TMP_ESMF_..._0001.nc and strip 10 of the 26 weight files, which are
    # INPUT for SWAN init, not cache.  Stale hot_*.nc segfault deterministically
    # when a clone's sim time hits a pre-existing filename.
    rsync -a \
        --exclude='DFM_OUTPUT_*' \
        --exclude='/*_0[0-9][0-9][0-9].*' \
        --exclude='/*_0[0-9][0-9][0-9]_*' \
        --exclude='hot_*.nc' \
        --exclude='*.bak*' \
        --exclude='*.dia' \
        --exclude='swn-diag.*' \
        --exclude='diag/' \
        "$SRC/" "$dst/"

    # The old .arl travels with the rsync; only the new one needs replacing.
    [ "$variant" = new ] && cp "$ARL_NEW" "$dst/$ARL_NAME"

    M=$dst/Stagnone_dxy01_15m.mdu
    sed -i "s|^\(stopDateTime *= *\)[0-9]*|\1$STOP|I" "$M"
    sed -i 's|^\(wrimap_numLimdt *= *\)[0-9]*|\11|I' "$M"
    # minTimestepBreak deliberately left at the original 0.1 so both variants
    # are judged by the same guard the original passed.

    dec=$(grep -v '^#' "$dst/$ARL_NAME" | head -1 | awk '{print $1}' | cut -d. -f2 | wc -c)
    printf '  %-22s arl_decimals=%s  esmf=%s  stop=%s\n' \
        "arl_$variant" "$((dec-1))" \
        "$(ls "$dst"/wave/TMP_ESMF*.nc 2>/dev/null | wc -l)" \
        "$(grep -i '^stopDateTime' "$M" | awk '{print $3}')"
done

echo
echo "=== launching (sequential: 8 MPI each, one at a time) ==="
for variant in old new; do
    dst=$BASE/_trt_test_arl_$variant
    cd "$dst"
    # ~/.bashrc only sources oneAPI for interactive shells; nohup gets a
    # non-interactive one.
    bash -c "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1;
             export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64;
             export PATH=\$DELFT3D_HOME/bin:\$PATH;
             export LD_LIBRARY_PATH=\$DELFT3D_HOME/lib:\$LD_LIBRARY_PATH;
             bash run_model.sh" > "$LOGDIR/arl_control_$variant.log" 2>&1 || true
    n=$(grep -c 'Computation finished' "$dst"/DFM_OUTPUT_*/*.dia 2>/dev/null | \
        awk -F: '{s+=$2} END {print s+0}')
    brk=$(grep -c 'below threshold' "$LOGDIR/arl_control_$variant.log" 2>/dev/null || echo 0)
    echo "  arl_$variant: partitions finished=$n  timestep-break messages=$brk"
done

echo
echo "old finished and new broke -> the .arl is the cause."
echo "both broke -> look at the clone procedure or the machine, not the .arl."
