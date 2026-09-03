@echo off
rem ============================================================
rem Stagnone di Marsala - D-Flow FM 3D STANDALONE (no SWAN coupling)
rem Period: July 1-10, 2025 (9 days)
rem v04AE_nowaves: clone of v04AE with wave coupling DISABLED
rem  - waveModelNr=0 in MDU
rem  - flowWithoutWaves=1 in MDU
rem  - <component name="wave"> removed from dimr_config.xml
rem  - wave/ subdirectory not copied (use v04AE if waves are needed)
rem  - kept saliMax=80 and maxVelocity=10 as insurance
rem
rem Purpose: isolate the contribution of wave coupling to drifter skill
rem  (paper 1 - 3D hydro), and as a fast benchmark of the FM-only ceiling.
rem  Expected wall time vs v04AE coupled: ~3-4x faster (no SWAN bottleneck).
rem
rem ============================================================
rem PARALLEL EXECUTION WITH v04AE COUPLED RUN
rem ============================================================
rem  This .bat pins MPI ranks to NUMA 1 (physical cores 32-39) on the
rem  2x Xeon Gold 6430 Workstation, leaving NUMA 0 (cores 0-31) entirely
rem  for the coupled v04AE run which uses:
rem    - cores 0-7 for 8 FM MPI ranks
rem    - cores 0-15 (compact) for 16 SWAN OpenMP threads
rem  Zero core contention; only shared resources are memory controller
rem  and inter-socket UPI link (per-socket on Sapphire Rapids).
rem
rem  If running ALONE (no coupled run on NUMA 0), remove the I_MPI_PIN_*
rem  vars below to let the OS scheduler use the whole machine.
rem ============================================================
rem WHY nPart=8 (was 16 on 2026-05-11, lowered after crash)
rem  2026-05-12: 16-MPI run aborted at sim-time 11h34min after 28 min wall
rem  via maxVelocity trigger (ucmag=13.31 m/s in intertidal cell).
rem  Two compounding issues identified:
rem    1. maxVelocity=10 was too tight for FM-only (no wave drag) - raised to 25
rem    2. nPart=16 with 1575 cells/partition is below the WP284 sweet spot
rem       (3000 cells/partition needed for CommE>0.85, LB ratio was 1.30)
rem  nPart=8 matches the coupled v04AE configuration exactly, eliminating
rem  partition-dependent numerical behavior as a confound for the
rem  FM-vs-FM+SWAN comparison.
rem ============================================================

cd /d "%~dp0"

set dimrset=C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64

rem Accept nPart as optional first argument; default to 8
if "%~1"=="" (
    set nPart=8
) else (
    set nPart=%~1
)

set mduFile=Stagnone_dxy01_15m.mdu

rem ----- Pin 8 MPI ranks to NUMA 1 cores 32-39, avoid contention with NUMA-0-bound coupled run -----
rem Intel MPI honors I_MPI_PIN_PROCESSOR_LIST when -localonly is used.
set I_MPI_PIN=1
set I_MPI_PIN_DOMAIN=core
set I_MPI_PIN_PROCESSOR_LIST=32-39

rem No OpenMP env vars: FM is MPI-only here (FM-internal OpenMP "disabled"
rem per .dia), and there is no SWAN to over-thread.

set "PATH=%dimrset%\bin;%dimrset%\lib;%dimrset%\share\bin;%PATH%"

echo ============================================================
echo Stagnone 3D FM-ONLY run (%nPart% MPI processes on NUMA 1, cores 32-39)
echo Working directory: %CD%
echo ============================================================
echo.

if %nPart% GTR 8 (
    echo WARNING: nPart=%nPart% but dimr_config.xml '<process>' lists only 0-7.
    echo Edit dimr_config.xml to expand the <process> list, or this run will
    echo mismatch the partition count against active MPI ranks.
    echo.
)

rem ----- Step 1: partition the mesh -----
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

rem ----- Step 2: run DIMR with FM-only component -----
echo [2/2] Running DIMR (FM-only) with %nPart% processes pinned to NUMA 1...
call "%dimrset%\bin\run_dimr_parallel.bat" %nPart% dimr_config.xml

echo.
echo ============================================================
echo Model run finished with exit code: %ERRORLEVEL%
echo ============================================================
pause
