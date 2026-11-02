@echo off
rem ============================================================
rem DEPRECATED 2026-05-11 — DO NOT RUN
rem
rem This script previously launched a 64-MPI variant of v04AE to "saturate"
rem the 64-core Workstation. That was the wrong approach.
rem
rem Per PRACE WP284 (Mogé et al. 2019, https://prace-ri.eu/wp-content/uploads/WP284.pdf):
rem   With a 25 200-cell mesh, 64 partitions = 395 cells/partition. At that
rem   ratio communication efficiency collapses to <0.5 and load imbalance
rem   exceeds 1.4. Halo overhead also dominates. The PETSc linear solver
rem   stops scaling below ~20 000 unknowns/partition.
rem
rem Per PRACE WP177 (Donners et al. 2014, https://zenodo.org/records/823064/files/WP177.pdf):
rem   The coupled FM+SWAN runtime is far more sensitive to SWAN OpenMP
rem   thread affinity and to the FLOW/SWAN core-sharing pattern than to
rem   raw MPI count for FLOW. Going to 64 MPI for FLOW also leaves zero
rem   cores for SWAN OpenMP threads, which contradicts the WP177 design.
rem
rem Use run_model.bat (8 MPI) and the partition sweep benchmark instead.
rem See memory hpc_optimization_xeon_64core.md for the full rationale.
rem ============================================================

echo.
echo  ========================================================
echo   run_model_64mpi.bat is DEPRECATED as of 2026-05-11.
echo   Per PRACE WP284 + WP177 this configuration is sub-optimal
echo   for the 25 200-cell mesh on dual-socket Xeon 6430.
echo.
echo   Use run_model.bat (8 MPI default) or run the partition sweep
echo   benchmark: scripts/benchmark_hpc_partition_sweep.bat
echo  ========================================================
echo.
pause
exit /b 1
