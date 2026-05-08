@echo off
rem ============================================================
rem Stagnone di Marsala - D-Flow FM 3D Model Run (PARALLEL)
rem Period: July 1-10, 2025 (9 days)
rem v04AE: AE-only blend wind (Mulino dropped per drifter validation 2026-05-08)
rem
rem Default 32 MPI partitions for the 64-core / 128 GB machine.
rem  Mesh has ~25 200 cells -> ~790 cells/partition at 32 MPI (healthy).
rem  Going to 48 MPI (~525 cells) or 64 MPI (~395 cells) may speed things up
rem  but communication overhead can dominate at very small partition sizes;
rem  benchmark a 12h sim at 32/48/64 first if you want to push past 32.
rem  Leaving 32 cores headroom for OS / I/O buffering tends to scale better
rem  than packing all 64 with FM ranks for this small mesh.
rem ============================================================

rem Force CWD to the directory of this bat file (avoids System32 if launched as admin)
cd /d "%~dp0"

set dimrset=C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64
set nPart=32
set mduFile=Stagnone_dxy01_15m.mdu

rem Add Delft3D FM binaries to PATH
set "PATH=%dimrset%\bin;%dimrset%\lib;%dimrset%\share\bin;%PATH%"

echo ============================================================
echo Stagnone 3D FM+SWAN coupled run (%nPart% MPI processes)
echo Working directory: %CD%
echo ============================================================
echo.

rem ----- Step 1: partition the mesh (only needed once per mesh change) -----
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
