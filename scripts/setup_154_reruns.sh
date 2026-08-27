#!/bin/bash
# Re-run the factorial's four variable-roughness members on Baptist formula 154.
#
# Two changes from the members that produced the Paper 1 figures, and only two:
#
#   1. the .arl written with 9 decimals, so FM's 1 cm matching tolerance can
#      find the links -- the old file reached 5.5% of the meadow
#   2. trachytope formula 153 -> 154 for the two vegetation classes
#
# Why 154. From trtrou.f90, 153 folds the canopy drag into a single
# representative Chezy:
#
#   ch = 1/sqrt( 1/cbed^2 + drag*densit*vheigh/(2g) )
#
# so taus, the stress that drives sediment transport, carries the canopy form
# drag as though it were skin friction on the grains. 154 keeps them apart:
#
#   ch = cbed + sqrt(g)/kappa*log(hk)*sqrt(1 + drag*densit*vheigh*cbed^2/(2g))
#   rttfu(nm,1) += fraccu*drag*densit/hk*(cbed/ch)^2
#
# the bed Chezy stays the bed Chezy and the canopy becomes an independent
# momentum sink. Same four parameters, so only the formula number changes.
#
# Measured over six simulated hours on the hardest member (waves + mobile bed),
# with the corrected .arl throughout: on 153 it aborts with bed change reaching
# 20 m in 45 minutes; on 154 it completes with mean taus 0.626 N/m2, below the
# old control's 0.748, and bed roughness on vegetated links at 0.0257. That last
# number is not tuned and lands on De Marchis et al. (2012), who give Posidonia
# ks = 0.10 m for this lagoon, n ~ 0.026.
#
# The four uniform-roughness members carry no trachytopes and are untouched.
# The _arlfix clones stay as they are: they isolate the .arl fix on 153, which
# is the other half of the decomposition.
#
# Formulas 155 and 156 follow 154's pattern, so RQ9 inherits this.
#
#   bash setup_154_reruns.sh          # prepare and verify only
#   bash setup_154_reruns.sh --launch # prepare and start all four
set -e

BASE=~/StagnoneDT/model
ARL=~/StagnoneDT/data/processed/planet2023_rf_v3/stagnone_trachytopes_v3.arl
ARL_NAME=stagnone_trachytopes_v3.arl
TTD_NAME=trachytopes.ttd
LOGDIR=~/154_logs

MEMBERS=${MEMBERS:-"v04AE_nowaves_vr v04AE_nodm_vr v04AE_nowaves_vrdm_dens v04AE_vr_dens"}
SUFFIX=${SUFFIX:-154}
# Optional overrides. TTD_FILE replaces the file wholesale, which also skips the
# 153 -> 154 substitution below: supply a .ttd that already carries 154.
ARL_FILE=${ARL_FILE:-$ARL}
TTD_FILE=${TTD_FILE:-}

[ -f "$ARL_FILE" ] || { echo "missing $ARL_FILE"; exit 1; }
mkdir -p "$LOGDIR"

echo "=== preparing ==="
fail=0
for m in $MEMBERS; do
    src=$BASE/dflowfm_$m
    dst=$BASE/dflowfm_${m}_${SUFFIX}
    [ -d "$src" ] || { echo "  $m: source missing, SKIPPED"; fail=1; continue; }
    rm -rf "$dst"; mkdir -p "$dst"

    # Excluded: regenerable or machine-bound output, and stale SWAN hot files,
    # which segfault deterministically when a clone's sim time hits a
    # pre-existing filename.
    # Kept: wave/TMP_ESMF_*.nc, which are INPUT for SWAN init under DIMR, not
    # cache -- without them wave aborts silently and FM dies on
    # MPI_Comm_size(comm=0x0).
    # The partition patterns are anchored with a leading '/' precisely because
    # unanchored they also match wave/TMP_ESMF_..._0001.nc and quietly remove
    # 10 of the 26 weight files.
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

    cp "$ARL_FILE" "$dst/$ARL_NAME"
    if [ -n "$TTD_FILE" ]; then
        cp "$TTD_FILE" "$dst/$TTD_NAME"
    else
        # Classes 2 (Cymodocea) and 3 (Posidonia) only; 1 and 4 are Manning (53).
        sed -i 's|^\( *[23] *\)153|\1154|' "$dst/$TTD_NAME"
    fi

    # Verify rather than assume. Every one of these has failed silently at some
    # point in this project: UTM coordinates in the .arl, 6-decimal rounding,
    # ESMF files eaten by an unanchored exclude, a stale hot file.
    dec=$(( $(grep -v '^#' "$dst/$ARL_NAME" | head -1 | awk '{print $1}' | cut -d. -f2 | wc -c) - 1 ))
    n154=$(grep -cE '^ +[23] +154' "$dst/$TTD_NAME" || true)
    n153=$(grep -cE '^ +[0-9]+ +153' "$dst/$TTD_NAME" || true)
    esmf=$(ls "$dst"/wave/TMP_ESMF*.nc 2>/dev/null | wc -l)
    hot=$(ls "$dst"/wave/hot_*.nc "$dst"/hot_*.nc 2>/dev/null | wc -l)
    trt=$(grep -ioE '^trtRou *= *[YN]' "$dst"/*.mdu | head -1 | awk '{print $NF}')

    ok="ok"
    [ "$dec" -eq 9 ] || { ok="BAD arl decimals"; fail=1; }
    [ "$n154" -eq 2 ] || { ok="BAD ttd 154 count"; fail=1; }
    [ "$n153" -eq 0 ] || { ok="BAD leftover 153"; fail=1; }
    [ "$hot" -eq 0 ] || { ok="BAD stale hot files"; fail=1; }
    printf '  %-36s arl_dec=%s arl_rec=%s ttd154=%s esmf=%s hot=%s trtRou=%s  %s\n' \
        "${m}_${SUFFIX}" "$dec" "$(grep -cvE '^#' "$dst/$ARL_NAME")" \
        "$n154" "$esmf" "$hot" "$trt" "$ok"
done

# The coupled members need all 26 ESMF weight files; the no-wave ones need none.
echo
if [ "$fail" -ne 0 ]; then
    echo "verification FAILED -- not launching."
    exit 1
fi
echo "verified."

if [ "$1" != "--launch" ]; then
    echo "re-run with --launch to start."
    exit 0
fi

echo; echo "=== launching ==="
# ~/.bashrc sources oneAPI only for interactive shells and nohup gets a
# non-interactive one, so source it explicitly.
for m in $MEMBERS; do
    dst=$BASE/dflowfm_${m}_${SUFFIX}
    [ -d "$dst" ] || continue
    cd "$dst"
    nohup bash -c "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1;
                   export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64;
                   export PATH=\$DELFT3D_HOME/bin:\$PATH;
                   export LD_LIBRARY_PATH=\$DELFT3D_HOME/lib:\$LD_LIBRARY_PATH;
                   bash run_model.sh" \
          > "$LOGDIR/${m}_${SUFFIX}.log" 2>&1 &
    echo "  $m -> pid $! , log $LOGDIR/${m}_${SUFFIX}.log"
    sleep 20        # stagger: the partition step is I/O heavy
done

echo; echo "monitor with:"
echo "  grep -c 'below threshold' $LOGDIR/*.log"
echo "  grep -l 'Computation finished' $BASE/dflowfm_*_${SUFFIX}/DFM_OUTPUT_*/*.dia | wc -l"
