@echo off
rem ============================================================
rem Stagnone di Marsala - D-Flow FM 3D Model Run (PARALLEL)
rem Period: July 1-10, 2025 (9 days)
rem v04AE: AE-only blend wind (Mulino dropped per drifter validation 2026-05-08)
rem
rem Usage:
rem   run_model.bat            -> uses default nPart = 8
rem   run_model.bat 4          -> overrides to nPart = 4
rem   run_model.bat 16         -> overrides to nPart = 16
rem
rem  For a partition-count sweep, use scripts/benchmark_partition_sweep.bat
rem  which calls this script with different nPart values.
rem
rem 2026-05-11: PARTITION COUNT REDUCED 32 -> 8 default per PRACE WP284 + WP177.
rem  WP284 (Mogé et al. 2019, https://prace-ri.eu/wp-content/uploads/WP284.pdf):
rem    - Communication Efficiency falls below 0.80 when cells/partition < ~6000
rem    - Load imbalance grows to 1.30+ at < 2000 cells/partition
rem    - PETSc (icgSolver=6) does not scale below ~20 000 unknowns/partition
rem    - 25 200 cells / 16 parts = ~1575 cells/partition - ALREADY below threshold
rem    - 25 200 cells / 32 parts = 790 - way below
rem  Deltares FAQ confirms: "For small models, ONP [Optimal Number of Partitions]
rem    is lower" + "Communication between FLOW partitions is relatively intensive"
rem  WP177 (Donners et al. 2014, https://zenodo.org/records/823064/files/WP177.pdf):
rem    - SWAN parallelizes via OpenMP (preferred) or MPI (worse); FLOW+SWAN share
rem      cores alternately, controlled by KMP_AFFINITY when OpenMP is available
rem
rem  CRITICAL FINDING from prior .dia: this build of FM Suite 2026.01 logs
rem    "** INFO   : OpenMP disabled."  --> KMP_AFFINITY / OMP_NUM_THREADS have
rem    NO EFFECT. Investigate whether (a) the binary needs to be rebuilt with
rem    OpenMP, (b) SWAN inside DIMR Online forces single-thread, or (c) there
rem    is a hidden .mdw / dimr_config switch. The env vars are kept below but
rem    commented out until verified.
rem
rem  Other smoking gun: dimr_config.xml had <process>0..7</process> but
rem    run_model.bat was passing nPart=32 -> 24 ranks were idle. Fixed by
rem    aligning both. Re-check dimr_config.xml if you ever change nPart > 8.
rem ============================================================

rem Force CWD to the directory of this bat file (avoids System32 if launched as admin)
cd /d "%~dp0"

set dimrset=C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64

rem Accept nPart as optional first argument; default to 8
if "%~1"=="" (
    set nPart=8
) else (
    set nPart=%~1
)

set mduFile=Stagnone_dxy01_15m.mdu

rem ----- OpenMP env vars for SWAN (swan_omp.exe IS OpenMP-enabled) -----
rem  2026-05-11: confirmed via Task Manager that swan_omp.exe is the binary launched
rem  by DIMR and it does use OpenMP threads. Without OMP_NUM_THREADS set, it
rem  defaults to the number of LOGICAL processors (128 on this Workstation, due
rem  to 64 cores × 2 HT). That's far past SWAN's wave-front parallel scaling
rem  limit and causes massive synchronization overhead — confirmed by Task
rem  Manager showing 128 threads but only 79% CPU utilization on the swan_omp
rem  process, with the rest lost to spinning/contention.
rem
rem  WP177 (Donners 2014) used 32 threads on a Sandy Bridge fat node and it
rem  scaled fine; they explicitly did NOT push past that. For our small inner
rem  grid (~100m, ~10k cells) the wave-front parallelism saturates earlier —
rem  16 threads is a safer starting point.
rem
rem  2026-05-11 (round 2): OMP_NUM_THREADS=16 + KMP_AFFINITY=compact didn't
rem  take effect - swan_omp.exe still spawned ~128 threads (= all logical
rem  cores incl. HT). Cause: Intel MPI mpiexec in run_dimr_parallel.bat
rem  doesn't pass -genv/-genvall, so env vars from this shell may not
rem  propagate cleanly to the spawned dimr/swan processes.
rem
rem  Switching to KMP_HW_SUBSET, Intel-specific, which directly dictates the
rem  topology (16 cores, 1 thread per core - no hyperthreading). This has
rem  higher precedence than OMP_NUM_THREADS in the Intel OpenMP runtime and
rem  is read at swan_omp.exe init, regardless of how env vars propagated.
rem  We also keep OMP_NUM_THREADS=16 as a belt-and-braces fallback and add
rem  MKL_NUM_THREADS=16 in case any internal call uses MKL threading.
rem
rem  Reference: WP177 used 32 threads on a 32-core Sandy Bridge fat node.
rem  Our SWAN inner grid is smaller, so 16 should be enough; if Task Manager
rem  now shows ~16 threads on swan_omp.exe but throughput is no better than
rem  before, bump to 24 or 32.
rem  2026-05-11 (round 4): 32c,1t empiricamente PIOR que 16c,1t (5.4 vs 4.1
rem  min wall por sim-hour). Wave-front do SWAN satura antes de 32 threads
rem  para nosso inner grid 68x53 - WP177 usou 32 threads em grids maiores.
rem  Volta para 16c,1t como sweet spot empirico. Speedup adicional virá de
rem  cortar chamadas SWAN (ComInterval) e nao mais de threads por chamada.
set KMP_HW_SUBSET=16c,1t
set OMP_NUM_THREADS=16
set MKL_NUM_THREADS=16

rem Add Delft3D FM binaries to PATH
set "PATH=%dimrset%\bin;%dimrset%\lib;%dimrset%\share\bin;%PATH%"

echo ============================================================
echo Stagnone 3D FM+SWAN coupled run (%nPart% MPI processes)
echo Working directory: %CD%
echo ============================================================
echo.

rem ----- IMPORTANT: dimr_config.xml has <process>0 1 2 3 4 5 6 7</process>. -----
rem That tag restricts DFlowFM to 8 ranks. If you set nPart > 8 here, you MUST
rem also update dimr_config.xml to list all rank indices, otherwise extra ranks
rem will sit idle while the partitioned mesh has more domains than active ranks.
if %nPart% GTR 8 (
    echo WARNING: nPart=%nPart% exceeds dimr_config.xml '<process>0..7</process>'.
    echo Edit dimr_config.xml to expand the <process> list, or this run will
    echo mismatch the partition count against active MPI ranks.
    echo.
)

rem ----- Step 1: partition the mesh (only needed once per mesh / nPart change) -----
echo [1/2] Partitioning mesh into %nPart% domains...
call "%dimrset%\bin\run_dflowfm.bat" --partition:ndomains=%nPart%:icgsolver=6 %mduFile%
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Partitioning FAILED with exit code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)
echo Partitioning done.
echo.

rem ----- Step 2: run DIMR parallel (FM + SWAN coupling) -----
echo [2/2] Running DIMR with %nPart% processes...
call "%dimrset%\bin\run_dimr_parallel.bat" %nPart% dimr_config.xml

echo.
echo ============================================================
echo Model run finished with exit code: %ERRORLEVEL%
echo ============================================================
pause
