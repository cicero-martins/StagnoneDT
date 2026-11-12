#!/bin/bash
# Wall time of the FM-SWAN coupling under three placements of the SWAN threads, on simit.
#   One day, 7 to 8 July 2025, of the wave-coupled vegetated member
#   _veg_waves_ic3d from its restart of 7 July, run three times in sequence on
#   socket 1 so that the cases do not share memory bandwidth:
#     A  8 cores, 8 MPI ranks pinned one per core, SWAN on 1 thread (the
#        configuration of the Paper 1 ensemble);
#     B  8 cores, ranks unpinned inside a taskset of the same 8 cores, idle
#        ranks yielding (I_MPI_THREAD_YIELD=3), SWAN on 8 threads;
#     C  as B on 16 cores, the over-allocation test of Deltares note UNST-8665.
#   Pinned ranks hand their one-core affinity to the SWAN process spawned by
#   rank 0, so its threads share one core. B removes the pinning, C shows
#   whether any contention remains: a C much faster than B means the
#   MPI-OpenMP interaction of the note persists.
# Usage, on simit:  nohup bash bench_swan_threads_simit.sh > bench_swan.log 2>&1 &
set -uo pipefail
SRC=$HOME/StagnoneDT/model/_veg_waves_ic3d
ROOT=/storage/ciceromartinsjr/StagnoneDT/bench_swan
PICK=$HOME/simit_tools/simit_pick_cores.sh
mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }

setup() {   # $1 case directory
    local D=$1
    [[ -e "$D" ]] && return 0
    mkdir -p "$D/wave" "$D/restart_input" "$D/diag"
    (cd "$SRC" && find . -maxdepth 1 -type f ! -name '*.log' ! -name '*.dia' ! -name '*.bak' \
        ! -name 'status.sh' ! -name 'machinefile' -exec cp -p {} "$D/" \;)
    (cd "$SRC/wave" && find . -maxdepth 1 -type f ! -name 'wavm-*' ! -name 'swn-diag*' ! -name '*.log' \
        ! -name 'PET*' ! -name 'hot_*' ! -name '*com*.nc' ! -name 'PRINT*' -exec cp -p {} "$D/wave/" \;)
    cp -p "$SRC"/restart_input/*_rst.nc "$D/restart_input/"
    for m in "$D"/Stagnone_dxy01_15m.mdu "$D"/Stagnone_dxy01_15m_0[0-9][0-9][0-9].mdu; do
        sed -i -E -e 's/^(stopDateTime +=) *[0-9]+/\1 20250708000000/' \
                  -e 's/^(tStop +=) *[0-9.]+/\1 86400.0/' "$m"
    done
    sed -i -E 's#<time>0 3600 [0-9]+</time>#<time>0 3600 86400</time>#' "$D/dimr_config.xml"
    bad=$(grep -LE '^stopDateTime += *20250708000000' "$D"/*.mdu; grep -L '<time>0 3600 86400</time>' "$D/dimr_config.xml")
    [[ -z "$bad" ]] || { echo "edit did not apply in: $bad"; exit 3; }
    [[ $(ls "$D"/restart_input/*_rst.nc | wc -l) == 8 ]] || { echo "restart files missing"; exit 3; }
}

run() {   # $1 case, $2 cores, $3 pinned (1) or unpinned (0), $4 SWAN threads
    local D=$ROOT/$1 N=$2 PIN=$3 T=$4 CPUS t0 t1
    setup "$D"
    until CPUS=$(bash "$PICK" "$N" 1 $$); do sleep 120; done
    echo "$(date -Is) $1 on $CPUS, pinned $PIN, SWAN threads $T"
    t0=$(date +%s)
    (
        source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
        export PATH=$HOME/Scaricati/delft3dfm/lnx64/bin:$PATH
        export OMP_NUM_THREADS=1 I_MPI_WAIT_MODE=1
        if [[ $PIN == 1 ]]; then
            export I_MPI_PIN=1 I_MPI_PIN_PROCESSOR_LIST=$CPUS
            unset OMP_NUM_THREADS_SWAN
            cd "$D" && run_dimr.sh -c 8 -m dimr_config.xml
        else
            export I_MPI_PIN=0 I_MPI_THREAD_YIELD=3 OMP_NUM_THREADS_SWAN=$T
            cd "$D" && taskset -c "$CPUS" run_dimr.sh -c 8 -m dimr_config.xml
        fi
    ) > "$D/diag/run.log" 2>&1
    t1=$(date +%s)
    rm -f "$HOME/.simit_cores/$$.claim"
    local ok=no
    grep -q 'Computation finished' "$D"/DFM_OUTPUT_*/*_0000.dia 2>/dev/null && ok=yes
    local thr wave
    thr=$(grep -m1 'Number of threads' "$D/wave/swan_sh.log" 2>/dev/null | awk '{print $NF}')
    wave=$(grep -E '#0 >> wave\s*:' "$D/diag/run.log" | tail -1 | awk '{print $(NF-1)}')
    echo "$(date -Is) $1 finished=$ok wall=$((t1 - t0)) s, wave=${wave:-?} s, SWAN threads reported ${thr:-?}"
    echo "$1 $N $PIN $T $ok $((t1 - t0)) ${wave:-NA} ${thr:-NA}" >> "$ROOT/summary.txt"
}

mkdir -p "$ROOT"
[[ -s "$ROOT/summary.txt" ]] || echo "case cores pinned swan_threads finished wall_s wave_s threads_reported" > "$ROOT/summary.txt"
run A 8 1 1
run B 8 0 8
run C 16 0 8
echo "$(date -Is) all done"
cat "$ROOT/summary.txt"
