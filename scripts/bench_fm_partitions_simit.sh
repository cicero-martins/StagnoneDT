#!/bin/bash
# Wall time of the FM-SWAN coupling against the number of D-Flow FM partitions, on simit.
#   One day, 1 to 2 July 2025, of the wave-coupled vegetated member
#   _veg_waves_ic3d from its cold start, in three cases run in sequence on
#   socket 1 (24 physical cores):
#     P8   8 partitions,  taskset on 8 cores,  SWAN on 8 threads;
#     P16  16 partitions, taskset on 16 cores, SWAN on 16 threads;
#     P24  24 partitions, taskset on 24 cores, SWAN on 16 threads.
#   Every case uses the unpinned placement of bench_swan_threads_simit.sh
#   (I_MPI_PIN=0, I_MPI_THREAD_YIELD=3), under which SWAN no longer limits the
#   coupled run and D-Flow FM takes about three quarters of the wall time. A
#   restart is tied to its partitioning, so the three cases share a cold start
#   instead of the restart of 7 July used in that benchmark. Each case is
#   partitioned on simit from the global grid, and the wave component
#   regenerates its regridding weights for the new partitions at start-up.
# Usage, on simit:  nohup bash bench_fm_partitions_simit.sh > bench_fm_partitions.log 2>&1 &
set -uo pipefail
SRC=$HOME/StagnoneDT/model/_veg_waves_ic3d
ROOT=/storage/ciceromartinsjr/StagnoneDT/bench_partitions
PICK=$HOME/simit_tools/simit_pick_cores.sh
BIN=$HOME/Scaricati/delft3dfm/lnx64/bin
MDU=Stagnone_dxy01_15m.mdu
mountpoint -q /storage || { echo "/storage not mounted"; exit 4; }

setup() {   # $1 case directory, $2 number of partitions, $3 further partitioner options
    local D=$1 N=$2 OPT=${3:-}
    [[ -e "$D" ]] && return 0
    mkdir -p "$D/wave" "$D/diag"
    # global files only: partitioned grids, MDUs, caches and restarts belong to the 8-way split
    (cd "$SRC" && find . -maxdepth 1 -type f ! -name '*_00[0-9][0-9]*' ! -name '*.cache' \
        ! -name 'DFM_interpreted_*' ! -name '*.log' ! -name '*.dia' ! -name '*.bak' \
        ! -name 'status.sh' ! -name 'machinefile' -exec cp -p {} "$D/" \;)
    (cd "$SRC/wave" && find . -maxdepth 1 -type f ! -name 'wavm-*' ! -name 'swn-diag*' ! -name '*.log' \
        ! -name 'PET*' ! -name 'hot_*' ! -name '*com*.nc' ! -name 'PRINT*' -exec cp -p {} "$D/wave/" \;)
    sed -i -E -e 's/^(restartFile +=).*/\1/' \
              -e 's/^(startDateTime +=) *[0-9]+/\1 20250701000000/' \
              -e 's/^(stopDateTime +=) *[0-9]+/\1 20250702000000/' \
              -e 's/^(tStop +=) *[0-9.]+/\1 86400.0/' "$D/$MDU"
    sed -i -E 's#<time>0 3600 [0-9]+</time>#<time>0 3600 86400</time>#' "$D/dimr_config.xml"
    sed -i "s#\(<process>\)[^<]*\(</process>\)#\1$(seq -s ' ' 0 $((N - 1)))\2#" "$D/dimr_config.xml"
    (
        source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
        export PATH=$BIN:$PATH
        cd "$D" && run_dflowfm.sh --partition:ndomains=$N:icgsolver=6$OPT $MDU
    ) > "$D/diag/partition.log" 2>&1
    local bad
    bad=$(grep -LE '^stopDateTime += *20250702000000' "$D"/Stagnone_dxy01_15m*.mdu
          grep -lE '^restartFile += *[^ #]' "$D"/Stagnone_dxy01_15m*.mdu
          grep -L '<time>0 3600 86400</time>' "$D/dimr_config.xml")
    [[ -z "$bad" ]] || { echo "edit did not apply in: $bad"; exit 3; }
    [[ $(ls "$D"/Stagnone_dxy01_15m_00[0-9][0-9]_net.nc | wc -l) == "$N" ]] \
        || { echo "partitioning into $N failed, see $D/diag/partition.log"; exit 3; }
}

run() {   # $1 case, $2 partitions and cores, $3 SWAN threads, $4 further partitioner options
    local D=$ROOT/$1 N=$2 T=$3 CPUS t0 t1
    setup "$D" "$N" "${4:-}"
    until CPUS=$(bash "$PICK" "$N" 1 $$); do sleep 120; done
    echo "$(date -Is) $1 on $CPUS, $N partitions, SWAN threads $T"
    t0=$(date +%s)
    (
        source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
        export PATH=$BIN:$PATH
        export OMP_NUM_THREADS=1 I_MPI_WAIT_MODE=1
        export I_MPI_PIN=0 I_MPI_THREAD_YIELD=3 OMP_NUM_THREADS_SWAN=$T
        cd "$D" && taskset -c "$CPUS" run_dimr.sh -c "$N" -m dimr_config.xml
    ) > "$D/diag/run.log" 2>&1
    t1=$(date +%s)
    rm -f "$HOME/.simit_cores/$$.claim"
    local ok=no thr wave fm
    grep -q 'Computation finished' "$D"/DFM_OUTPUT_*/*_0000.dia 2>/dev/null && ok=yes
    thr=$(grep -m1 'Number of threads' "$D/wave/swan_sh.log" 2>/dev/null | awk '{print $NF}')
    wave=$(grep -E '#0 >> wave\s*:' "$D/diag/run.log" | tail -1 | awk '{print $(NF-1)}')
    fm=$(grep -E '#0 >> DFlowFM\s*:' "$D/diag/run.log" | tail -1 | awk '{print $(NF-1)}')
    echo "$(date -Is) $1 finished=$ok wall=$((t1 - t0)) s, fm=${fm:-?} s, wave=${wave:-?} s, SWAN threads reported ${thr:-?}"
    echo "$1 $N $T $ok $((t1 - t0)) ${fm:-NA} ${wave:-NA} ${thr:-NA} $CPUS" >> "$ROOT/summary.txt"
}

mkdir -p "$ROOT"
[[ -s "$ROOT/summary.txt" ]] || echo "case partitions swan_threads finished wall_s fm_s wave_s threads_reported cpus" > "$ROOT/summary.txt"
if [[ $# -ge 3 ]]; then
    # a single case: name, partitions, SWAN threads, further partitioner options
    run "$1" "$2" "$3" "${4:-}"
else
    run P8 8 8
    run P16 16 16
    run P24 24 16
fi
echo "$(date -Is) all done"
cat "$ROOT/summary.txt"
