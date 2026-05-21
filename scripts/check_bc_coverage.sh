#!/usr/bin/env bash
#
# Preflight: check that all BCs + meteo forcings in a model dir cover the MDU window.
# Runs locally on the server (uses awk + ncdump, no Python needed).
#
# Usage: bash check_bc_coverage.sh <model_dir>
# Returns 0 if all OK, non-zero if any gap found.

set -u

MODEL_DIR="${1:-}"
[[ -z "$MODEL_DIR" ]] && { echo "Usage: $0 <model_dir>"; exit 1; }
[[ -d "$MODEL_DIR" ]] || { echo "ERROR: $MODEL_DIR not found"; exit 2; }

cd "$MODEL_DIR" || exit 2

# Find master MDU (no _NNNN suffix)
MDU=$(ls Stagnone_*.mdu 2>/dev/null | grep -v '_[0-9]\{4\}\.mdu$' | head -1)
[[ -z "$MDU" ]] && { echo "ERROR: master MDU not found in $MODEL_DIR"; exit 3; }

# Extract window from MDU
START=$(grep -E '^\s*startDateTime\s*=' "$MDU" | head -1 | awk -F'=' '{print $2}' | awk '{print $1}')
STOP=$(grep -E '^\s*stopDateTime\s*=' "$MDU" | head -1 | awk -F'=' '{print $2}' | awk '{print $1}')

# Convert YYYYMMDDhhmmss to epoch
mdu_epoch() {
    local s="$1"
    local fmt="${s:0:4}-${s:4:2}-${s:6:2} ${s:8:2}:${s:10:2}:${s:12:2}"
    date -u -d "$fmt UTC" +%s
}

START_EPOCH=$(mdu_epoch "$START")
STOP_EPOCH=$(mdu_epoch "$STOP")
START_ISO=$(date -u -d "@$START_EPOCH" '+%Y-%m-%d %H:%M:%S')
STOP_ISO=$(date -u -d "@$STOP_EPOCH" '+%Y-%m-%d %H:%M:%S')

echo "==================================================================="
echo " BC + Forcings coverage check"
echo " Model dir : $MODEL_DIR"
echo " MDU       : $MDU"
echo " Window    : $START_ISO -> $STOP_ISO"
echo "==================================================================="

# Parse "since" timestamp from unit string
# e.g. "minutes since 2025-07-01 00:00:00" -> epoch + multiplier
parse_unit_to_epoch_and_factor() {
    local unit="$1"
    # Get multiplier (seconds per unit)
    local mult=1
    case "$unit" in
        minutes*|*minutes*) mult=60 ;;
        hours*|*hours*) mult=3600 ;;
        seconds*|*seconds*) mult=1 ;;
        days*|*days*) mult=86400 ;;
        *) mult=60 ;;  # default minutes
    esac
    # Get the date portion after "since"
    local date_str
    date_str=$(echo "$unit" | sed -nE 's/.*since[[:space:]]+([0-9]{4}-[0-9]{2}-[0-9]{2}([[:space:]]+[0-9]{2}:[0-9]{2}:[0-9]{2})?).*/\1/p')
    [[ -z "$date_str" ]] && { echo "0 0"; return; }
    local ref_epoch
    ref_epoch=$(date -u -d "$date_str UTC" +%s 2>/dev/null) || { echo "0 0"; return; }
    echo "$ref_epoch $mult"
}

# Check .bc file: find unit, first numeric time, last numeric time, convert to absolute
check_bc() {
    local f="$1"
    [[ -f "$f" ]] || { echo "MISSING|$f|-|-|-"; return; }
    # Find first unit line that's "since" (skip "m" or "m3/s" units for quantity)
    local unit
    unit=$(grep -i "unit" "$f" | grep -i since | head -1 | sed 's/^[^=]*=//' | sed 's/^[[:space:]]*//')
    if [[ -z "$unit" ]]; then
        echo "NO_TIME_UNIT|$(basename $f)|-|-|-"
        return
    fi
    read -r ref_epoch mult <<< "$(parse_unit_to_epoch_and_factor "$unit")"
    if [[ "$ref_epoch" == "0" ]]; then
        echo "BAD_UNIT|$(basename $f)|-|-|$unit"
        return
    fi
    # First and last numeric line (per first [Forcing] block; assume all blocks have same range)
    local first_t last_t
    first_t=$(awk '/^\[Forcing\]/{count++} count==1 && /^[0-9]/ {print $1; exit}' "$f")
    last_t=$(awk '/^\[Forcing\]/{count++} count==1 && /^[0-9]/ {last=$1} END{print last}' "$f")
    [[ -z "$first_t" ]] && { echo "EMPTY|$(basename $f)|-|-|-"; return; }
    # Convert to epoch
    local first_epoch last_epoch
    first_epoch=$(awk -v r=$ref_epoch -v m=$mult -v t=$first_t 'BEGIN{printf "%d", r + t*m}')
    last_epoch=$(awk -v r=$ref_epoch -v m=$mult -v t=$last_t 'BEGIN{printf "%d", r + t*m}')
    local first_iso last_iso
    first_iso=$(date -u -d "@$first_epoch" '+%Y-%m-%d %H:%M')
    last_iso=$(date -u -d "@$last_epoch" '+%Y-%m-%d %H:%M')
    # Check coverage
    local status="OK"
    (( first_epoch > START_EPOCH )) && status="LATE_START"
    (( last_epoch < STOP_EPOCH )) && status="EARLY_END"
    echo "$status|$(basename $f)|$first_iso|$last_iso|-"
}

# Check .nc file: use ncdump -t to get time bounds
check_nc() {
    local f="$1"
    [[ -f "$f" ]] || { echo "MISSING|$(basename $f)|-|-|-"; return; }
    # Get time variable name (try common names)
    local timevar
    for tv in time TIME valid_time; do
        if ncdump -h "$f" 2>/dev/null | grep -qE "[[:space:]]$tv\([^)]*\)" ; then
            timevar="$tv"
            break
        fi
    done
    [[ -z "$timevar" ]] && { echo "NO_TIMEVAR|$(basename $f)|-|-|-"; return; }
    # Get unit
    local unit
    unit=$(ncdump -h "$f" 2>/dev/null | grep -E "${timevar}:units" | sed -E 's/.*= *"([^"]+)".*/\1/' | head -1)
    [[ -z "$unit" ]] && { echo "NO_UNIT|$(basename $f)|-|-|-"; return; }
    read -r ref_epoch mult <<< "$(parse_unit_to_epoch_and_factor "$unit")"
    [[ "$ref_epoch" == "0" ]] && { echo "BAD_UNIT|$(basename $f)|-|-|$unit"; return; }
    # First + last time value
    local times
    times=$(ncdump -v "$timevar" "$f" 2>/dev/null | sed -n "/^ ${timevar} = /,/}/p" | tr ',' '\n' | grep -oE '[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?' | head -n -1)
    [[ -z "$times" ]] && { echo "EMPTY|$(basename $f)|-|-|-"; return; }
    local first_t last_t
    first_t=$(echo "$times" | head -1)
    last_t=$(echo "$times" | tail -1)
    local first_epoch last_epoch
    first_epoch=$(awk -v r=$ref_epoch -v m=$mult -v t=$first_t 'BEGIN{printf "%d", r + t*m}')
    last_epoch=$(awk -v r=$ref_epoch -v m=$mult -v t=$last_t 'BEGIN{printf "%d", r + t*m}')
    local first_iso last_iso
    first_iso=$(date -u -d "@$first_epoch" '+%Y-%m-%d %H:%M')
    last_iso=$(date -u -d "@$last_epoch" '+%Y-%m-%d %H:%M')
    local status="OK"
    (( first_epoch > START_EPOCH )) && status="LATE_START"
    (( last_epoch < STOP_EPOCH )) && status="EARLY_END"
    echo "$status|$(basename $f)|$first_iso|$last_iso|-"
}

# Collect forcing file references from .ext files
EXT_FILES=()
for ext in Stagnone_dxy01_15m_new.ext Stagnone_dxy01_15m_old.ext; do
    if [[ -f "$ext" ]]; then
        EXT_FILES+=("$ext")
    fi
done

# Extract referenced .bc and .nc files (from both forcingFile= and discharge= and FILENAME=)
referenced=$(
    for ext in "${EXT_FILES[@]}"; do
        # New format: forcingFile = filename ; discharge = filename ; locationFile = ...
        grep -hE '^\s*(forcingFile|discharge|tracer)\s*=' "$ext" | awk -F'=' '{print $2}' | awk '{print $1}'
        # Old format: FILENAME = filename
        grep -hE '^\s*FILENAME\s*=' "$ext" | awk -F'=' '{print $2}' | awk '{print $1}'
    done | sort -u
)

# Header
printf "%-12s | %-50s | %-19s | %-19s\n" "STATUS" "FILE" "first time" "last time"
printf "%-12s-+-%-50s-+-%-19s-+-%-19s\n" "------------" "$(printf '%.0s-' {1..50})" "-------------------" "-------------------"

FAILS=0
for f in $referenced; do
    # Determine type by extension
    if [[ "$f" == *.bc ]]; then
        result=$(check_bc "$f")
    elif [[ "$f" == *.nc ]]; then
        result=$(check_nc "$f")
    else
        result="SKIP|$f|-|-|not .bc/.nc"
    fi
    IFS='|' read -r status fn first last note <<< "$result"
    printf "%-12s | %-50s | %-19s | %-19s\n" "$status" "$fn" "$first" "$last"
    [[ "$status" == "LATE_START" ]] || [[ "$status" == "EARLY_END" ]] || [[ "$status" == "MISSING" ]] && FAILS=$((FAILS + 1))
done

echo ""
if (( FAILS == 0 )); then
    echo "ALL OK"
    exit 0
else
    echo "FAIL: $FAILS file(s) don't cover the MDU window."
    exit 4
fi
