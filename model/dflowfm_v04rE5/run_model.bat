@echo off
rem ============================================================
rem Stagnone di Marsala - D-Flow FM 3D Model Run (PARALLEL)
rem Period: July 1-10, 2025 (9 days)
rem 8 MPI processes (run on the higher-core-count machine)
rem ============================================================

rem Force CWD to the directory of this bat file (avoids System32 if launched as admin)
cd /d "%~dp0"

set dimrset=C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64
set nPart=8
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
