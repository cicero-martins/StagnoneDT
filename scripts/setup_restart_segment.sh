#!/bin/bash
# Build a restart segment of an existing member: clone it, install the restart
# files for a given day, and run from there.
#
# Written for the nodm_vr_154 blow-up and then kept, because the two uses are
# the same mechanism with different parameters.
#
# The investigation it came from. On formula 154 the wave-coupled fixed-bed
# member aborts twice, deterministically, at the same cell index and the same
# simulated instant, 2025-07-04 21:00, reaching 10.35 m/s against a 10 m/s cap
# and then 28.8 against 25. Every documented cause was checked and cleared:
# uxuyadvectionvelocitybnd present with a byte-identical well-formed .bc, nPart
# 8, SWAN coupled and producing waves, hot files hourly rather than a stale
# collision, the deep western boundary identical to the runs that complete (same
# 4.75 m/s maximum in all three), the salt cap holding 333 cells against 444 in
# the run that finished. Restarted from the day-3 file the event is not
# attenuated, it is absent: over the 23 hours containing it the domain maximum
# stays between 2.58 and 2.64 m/s and nothing anywhere exceeds 5. So it is a
# knife-edge event belonging to one continuously integrated trajectory, not a
# structural defect of the formulation.
#
# Two things this encodes that are easy to get wrong:
#
#   Partition files are copied, never regenerated. Restart files are
#   partition-bound, so re-partitioning silently invalidates them. That is also
#   why it launches run_dimr.sh directly instead of run_model.sh, which
#   re-partitions.
#
#   hot_*.nc are excluded. SWAN writes them hourly by timestamp, and a
#   pre-existing file at a timestamp the run reaches segfaults deterministically.
#
# mapInterval is snapped up to a multiple of dtUser (300 s) by FM, so asking for
# 60 gets 300. Not an error, but do not expect the number you asked for.
#
# Follows the restart pattern from chain_overnight.sh: tStop is the DURATION,
# the DIMR <time> takes the same duration, restart files live in restart_input/
# under their full partition-and-datetime name, and all nine MDUs are patched.
#
#   bash setup_restart_segment.sh <src_dir> <dst_dir> <START_YYYYMMDD> <STOP_YYYYMMDDHHMMSS> [--launch]
#
# Options via environment: MAPINT (default 1800), MAXVEL (default 10.0),
# RSTINT (default 86400), CSTBND (unset = leave alone).
#
# CSTBND is the MDU cstBnd, shown in the FM interface as "use Delft3D velocity
# handling": it forces the velocity at open-boundary cells to be normal to the
# boundary, suppressing the tangential component. Worth trying here because the
# spiking cells sit near the deep western open boundary. Tempered expectation:
# the project tested it once before, on the no-wave mobile-bed abort, and it
# changed nothing -- that run failed at the same cell, the same instant and the
# same velocity to six decimals as the run without it. But that was a different
# physics configuration and a different failure, so it is not settled here.
set -e

SRC_NAME=$1; DST_NAME=$2; START=$3; STOP_DT=$4; LAUNCH=$5
[ -n "$STOP_DT" ] || { sed -n '30,34p' "$0"; exit 1; }

BASE=~/StagnoneDT/model
SRC=$BASE/$SRC_NAME
DST=$BASE/$DST_NAME
OUT=$SRC/DFM_OUTPUT_Stagnone_dxy01_15m
LOGDIR=~/154_logs
MAPINT=${MAPINT:-1800}
MAXVEL=${MAXVEL:-10.0}
RSTINT=${RSTINT:-86400}
# Optional replacements, copied in under the names the MDU already references,
# so trtL and trtDef need no patching.
ARL_FILE=${ARL_FILE:-}
TTD_FILE=${TTD_FILE:-}

[ -d "$SRC" ] || { echo "missing $SRC"; exit 1; }
mkdir -p "$LOGDIR"

# Duration in seconds between the restart instant and the stop instant.
s0=$(date -u -d "${START:0:4}-${START:4:2}-${START:6:2} 00:00:00" +%s)
s1=$(date -u -d "${STOP_DT:0:4}-${STOP_DT:4:2}-${STOP_DT:6:2} ${STOP_DT:8:2}:${STOP_DT:10:2}:${STOP_DT:12:2}" +%s)
DURATION=$(( s1 - s0 ))
[ "$DURATION" -gt 0 ] || { echo "stop is not after start"; exit 1; }

rm -rf "$DST"; mkdir -p "$DST"
rsync -a \
    --exclude='DFM_OUTPUT_*' \
    --exclude='hot_*.nc' \
    --exclude='*.bak*' \
    --exclude='*.dia' \
    --exclude='swn-diag.*' \
    --exclude='diag/' \
    "$SRC/" "$DST/"

if [ -n "$ARL_FILE" ]; then
    cp "$ARL_FILE" "$DST/$(grep -ioE 'trtL *= *\S+' "$DST/Stagnone_dxy01_15m.mdu" | awk '{print $3}')"
fi
if [ -n "$TTD_FILE" ]; then
    cp "$TTD_FILE" "$DST/$(grep -ioE 'trtDef *= *\S+' "$DST/Stagnone_dxy01_15m.mdu" | awk '{print $3}')"
fi

mkdir -p "$DST/restart_input"
for n in 0 1 2 3 4 5 6 7; do
    r=$(printf '%04d' $n)
    f=$OUT/Stagnone_dxy01_15m_${r}_${START}_000000_rst.nc
    [ -f "$f" ] || { echo "missing restart for rank $r at $START"; exit 1; }
    cp "$f" "$DST/restart_input/"
done

patch_mdu() {
    local mdu="$1" rank="$2"
    [ -f "$mdu" ] || return
    sed -i "s/^tStop\s*=.*/tStop                   = ${DURATION}.0/" "$mdu"
    sed -i "s/^startDateTime\s*=.*/startDateTime           = ${START}000000/" "$mdu"
    sed -i "s/^stopDateTime\s*=.*/stopDateTime            = ${STOP_DT}/" "$mdu"
    if [ -z "$rank" ]; then
        sed -i "s|^restartFile\s*=.*|restartFile     = restart_input/Stagnone_dxy01_15m_${START}_000000_rst.nc|" "$mdu"
    else
        sed -i "s|^restartFile\s*=.*|restartFile     = restart_input/Stagnone_dxy01_15m_${rank}_${START}_000000_rst.nc|" "$mdu"
    fi
    sed -i "s|^restartDateTime\s*=.*|restartDateTime = ${START}000000|" "$mdu"
    sed -i "s|^\(mapInterval  *= *\)[0-9.]*|\1${MAPINT}.0|I" "$mdu"
    sed -i "s|^\(rstInterval  *= *\)[0-9.]*|\1${RSTINT}.0|I" "$mdu"
    sed -i "s|^\(wrimap_numLimdt  *= *\)[0-9]*|\11|I" "$mdu"
    sed -i "s|^\(maxVelocity  *= *\)[0-9.]*|\1${MAXVEL}|I" "$mdu"
    [ -n "$CSTBND" ] && sed -i "s|^\( *cstBnd  *= *\)[0-9]*|\1${CSTBND}|I" "$mdu"
    return 0
}
patch_mdu "$DST/Stagnone_dxy01_15m.mdu" ""
for n in 0 1 2 3 4 5 6 7; do
    patch_mdu "$DST/Stagnone_dxy01_15m_$(printf '%04d' $n).mdu" "$(printf '%04d' $n)"
done

sed -i "s|<time>0 [0-9]\+ [0-9]\+</time>|<time>0 3600 ${DURATION}</time>|" "$DST/dimr_config.xml"

echo "=== $DST_NAME ==="
grep -E "^(tStop|startDateTime|stopDateTime|restartFile|restartDateTime)" \
     "$DST/Stagnone_dxy01_15m_0000.mdu" | sed 's/^/  /'
grep -iE "^ *(mapInterval|rstInterval|wrimap_numLimdt|maxVelocity|cstBnd) " \
     "$DST/Stagnone_dxy01_15m.mdu" | cut -d'#' -f1 | sed 's/^/  /'
echo "  duration: ${DURATION}s ($(( DURATION / 86400 ))d $(( DURATION % 86400 / 3600 ))h)"
echo "  dimr: $(grep -o '<time>[^<]*</time>' "$DST/dimr_config.xml")"
echo "  restart files: $(ls "$DST"/restart_input/*.nc | wc -l)/8"
echo "  partition net/mdu kept: $(ls "$DST"/*_0[0-9][0-9][0-9]_net.nc | wc -l)/$(ls "$DST"/*_0[0-9][0-9][0-9].mdu | wc -l)"
echo "  esmf: $(ls "$DST"/wave/TMP_ESMF*.nc 2>/dev/null | wc -l)   stale hot: $(ls "$DST"/wave/hot_*.nc 2>/dev/null | wc -l)"
echo "  ttd: $(grep -E '^ +[0-9]+ +[0-9]+' "$DST/trachytopes.ttd" | tr -s ' ' | paste -sd'; ')"
echo "  arl: $(grep -cvE '^#' "$DST"/*.arl) records, $(grep -vE '^#' "$DST"/*.arl | head -1 | awk '{print $1}') first x"

[ "$LAUNCH" = "--launch" ] || { echo; echo "re-run with --launch to start."; exit 0; }

echo; echo "=== launching ==="
cd "$DST"
nohup bash -c "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1;
               export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64;
               export PATH=\$DELFT3D_HOME/bin:\$PATH;
               export LD_LIBRARY_PATH=\$DELFT3D_HOME/lib:\$LD_LIBRARY_PATH;
               run_dimr.sh -c 8 -m dimr_config.xml" \
      > "$LOGDIR/${DST_NAME}.log" 2>&1 &
echo "launched pid $!, log $LOGDIR/${DST_NAME}.log"
