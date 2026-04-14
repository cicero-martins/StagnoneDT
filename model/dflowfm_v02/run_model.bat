@echo off
rem ============================================================
rem Stagnone di Marsala — D-Flow FM 3D Model Run
rem Period: July 1-10, 2025 (9 days)
rem ============================================================

set dimrset="C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64"

rem Add Delft3D FM binaries to PATH
set PATH=%dimrset%\bin;%dimrset%\lib;%dimrset%\share\bin;%PATH%

echo ============================================================
echo Starting Stagnone 3D model (DIMR)
echo Working directory: %CD%
echo ============================================================
echo.

rem Run DIMR (single process)
"%dimrset%\bin\dimr.exe" dimr_config.xml

echo.
echo ============================================================
echo Model run finished with exit code: %ERRORLEVEL%
echo ============================================================
pause
