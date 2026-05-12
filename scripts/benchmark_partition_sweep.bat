@echo off
rem ============================================================
rem Partition-count sweep benchmark for v04AE on this Workstation.
rem
rem Runs the v04AE model with several nPart values, archives each
rem DFM_OUTPUT_* under a name that records the partition count, and
rem at the end calls the Python analyzer to print a comparison table.
rem
rem Each sub-run reads the SAME MDU - so it executes the FULL 9-day
rem simulation. For a quicker sweep you can temporarily edit
rem Stagnone_dxy01_15m.mdu to set stopDateTime to (start + 6h),
rem run this script, and restore stopDateTime afterwards.
rem
rem Usage:
rem   benchmark_partition_sweep.bat
rem ============================================================

set MODEL_DIR=%~dp0..\model\dflowfm_v04AE
set RUN_BAT=%MODEL_DIR%\run_model.bat
set OUT_BASE=%MODEL_DIR%\DFM_OUTPUT_Stagnone_dxy01_15m
set PYTHON="C:\Users\Unipa\.conda\envs\dfm_tools_env\python.exe"
set ANALYZER=%~dp0benchmark_hpc_partition_sweep.py

rem Edit this list to choose which partition counts to benchmark.
rem WP284 + Deltares guidance: for our 25k-cell mesh, 4-8 is the recommended
rem range. 16 is already past the WP284 communication-efficiency threshold;
rem 32 is well past it and should be slower.
set SWEEP=4 8 16 32

if not exist "%RUN_BAT%" (
    echo ERROR: %RUN_BAT% not found.
    pause
    exit /b 1
)

set ARCHIVED=

for %%N in (%SWEEP%) do (
    echo.
    echo ============================================================
    echo SWEEP STEP: nPart = %%N
    echo ============================================================

    rem Clean any previous output for this nPart value, then run.
    if exist "%OUT_BASE%_npart_%%N" rmdir /s /q "%OUT_BASE%_npart_%%N"
    if exist "%OUT_BASE%" rmdir /s /q "%OUT_BASE%"

    rem run_model.bat now accepts nPart as %1 - delegate to it.
    call "%RUN_BAT%" %%N
    if errorlevel 1 (
        echo Run with nPart=%%N FAILED, continuing to next value.
    ) else (
        rem Archive the output under a partition-tagged name so subsequent
        rem runs do not overwrite it.
        if exist "%OUT_BASE%" (
            ren "%OUT_BASE%" "DFM_OUTPUT_Stagnone_dxy01_15m_npart_%%N"
            set ARCHIVED=%ARCHIVED% "%OUT_BASE%_npart_%%N"
        )
    )
)

echo.
echo ============================================================
echo SWEEP DONE. Running analyzer on archived outputs.
echo ============================================================
%PYTHON% "%ANALYZER%" %ARCHIVED%
pause
