# Deltares support — D-Flow FM + D-Waves DIMR online coupling: HDF error on com.nc write

**Suggested subject:** D-Flow FM + D-Waves DIMR online coupling: repeating "NetCDF: HDF error" on com.nc write (ncFormat=4) — time-varying waves not transmitted to FM

**From:** Cicero Martins Jr / Università degli Studi di Palermo (cicero.martinsjr@unipa.it)

---

## Environment

- **Product**: Delft3D FM Suite 2026.01 HMWQ, DIMR binary:
  `DIMR_EXE Version 2.00.057d2f7ceeafda462a1b4e598efa4ce4f0c97cc5, Oct 20 2025`
  `D-Flow FM kernel: 1.2.184.057d2f7ceeafda462a1b4e598efa4ce4f0c97cc5 (all/release/2026.01)`
- **OS**: Windows 11 (64-bit), NTFS local disk, 16 GB RAM
- **Same symptom observed in parallel deployment**: EDITO Datalab `delft3dfm_run_docker` service, Linux container (Kubernetes pod). Identical error pattern, so the issue is not OS-specific.
- **Coupling mode**: DIMR Online with FLOW (`<parallel>` with `<startGroup>` running `wave` component alongside `DFlowFM`).
- **Model**: Stagnone di Marsala lagoon (Sicily, Italy). Unstructured FM mesh, 21k nodes, 4 MPI partitions. SWAN nested outer + inner grids (~400 m + ~100 m).

## Symptom

At every `wave.Update` after the very first, each MPI partition logs the following pattern (example for partition 0):

```
ERROR opening file. NetCDF file : "../DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000_com.nc".
  Error message: NetCDF: HDF error
ERROR inq_dimid nFlowElemWithBnd. NetCDF file : "..._0000_com.nc". Error message: NetCDF: Not a valid ID
ERROR inq_dimid time. ... NetCDF: Not a valid ID
ERROR inq_varid time. ... NetCDF: Not a valid ID
ERROR inq_varid hrms. ... NetCDF: Not a valid ID
ERROR put_var hrms. ... NetCDF: Not a valid ID
(... full list of wave output variables ...)
ERROR: time_read(0.00000E+00) is not equal to curtime(0.15639E+08)
ERROR closing file. ... NetCDF: Not a valid ID
```

Over a 9-day simulation this produces thousands of lines of errors. **The simulation does not abort**; DIMR finishes with exit code 0. The observable consequence is that **SWAN successfully writes `hrms/tp/dir/...` into `com.nc` only during the first coupling iteration**, so D-Flow FM reads the same iter-1 wave field for the rest of the run:

```
station BocaNord — hwav time series, 13 samples:
  2025-07-01 00:00  0.0000 m   (sim start, before iter 1)
  2025-07-01 00:10  0.1860 m   <- iter 1 writes successfully
  2025-07-01 00:20  0.1860 m   <- iter 2+ all fail, FM reads the stale iter-1 value
  2025-07-01 00:30  0.1860 m
  ...
  2025-07-01 02:00  0.1860 m
  → total unique values: 2 (zero + iter-1 constant)
```

Offshore TPAR forcing is genuinely time-varying across the run (9 `.bnd` files, hourly CMEMS data, 0.3-2.0 m Hs range), so the waves should respond. They do not, because of the com.nc write failures.

## Reproducer

Minimal local reproducer runs on a 2-hour sim window and reproduces the symptom reliably (~10 min wallclock on a 6-core laptop). All configuration files + an MDW / MDU pair that exhibit the issue are available to share on request. The key MDU + MDW settings that matter:

```ini
# MDU
[output]
ncFormat                = 4    # critical — see test matrix below
ncNoForcedFlush         = 0

# MDW
[Output]
WriteCOM             = true
UseHotFile           = true
COMWriteInterval     = 600     # 10 min coupling
```

```xml
<!-- dimr_config.xml -->
<control>
  <parallel>
    <startGroup>
      <time>0 600 7200</time>
      <start name="wave"/>
    </startGroup>
    <start name="DFlowFM"/>
  </parallel>
</control>
```

## Isolation — test matrix (2-hour sim, same MDU/MDW except the noted variable)

| Test                    | `ncFormat` | MPI partitions | `HDF5_USE_FILE_LOCKING` | `AppendCOM` | HDF errors in log | `hwav` unique values |
|-------------------------|:----------:|:--------------:|:-----------------------:|:-----------:|:-----------------:|:--------------------:|
| baseline                | 4          | 4              | ON                      | false       | 1796              | 2                    |
| **nc3 (classic)**       | **3**      | **4**          | **ON**                  | **false**   | **0**             | **12-13 (fixed)**    |
| nolock                  | 4          | 4              | FALSE                   | false       | 429               | 2                    |
| serial                  | 4          | 1              | ON                      | false       | 429               | 2                    |
| append                  | 4          | 4              | ON                      | true        | 1672              | 2                    |
| nc5 (silent→nc3)        | 5          | 4              | ON                      | false       | 0                 | 12-13                |

**Observations:**

1. Only `ncFormat = 3` eliminates the errors completely.
2. Serial run (`nPart = 1`) and disabling HDF5 file locking each reduce the error count ~4×, but neither restores time-varying waves. **This rules out MPI concurrent-access as the root cause**; the issue reproduces in pure serial.
3. `AppendCOM = true` (suggested by the D-Waves manual as an alternative data-write semantics) does not help — error count and `hwav` stays at baseline.
4. FM accepts `ncFormat = 5` without error but silently writes NETCDF3_CLASSIC output (verified via `nc_inq_format`). So `ncFormat` only officially supports 3 or 4.

## Our provisional workaround, and why we cannot rely on it

`ncFormat = 3` (classic NetCDF) is our current workaround because it completely eliminates the HDF errors and restores time-varying waves at all stations. However, classic NetCDF has a **2 GB per-file limit** which is not viable for our production runs:

- Our typical map.nc grows to ~14 GB per partition for a 9-day 3D run (4 MPI partitions, `mapInterval = 900`, ~60 output variables).
- For 30-day residence-time studies the per-partition map.nc would reach ~47 GB.
- Even aggressive reductions via `wrimap_*` flags + longer `mapInterval` only halve the volume, leaving us above 2 GB per partition for any run longer than ~5 days.

We have therefore built the model so that we can produce scientifically meaningful results via `ncFormat = 3` for short demonstrations, but we cannot run longer simulations, which blocks the residence-time and resuspension studies that are the main objective of the project.

## Ask

1. Is this a known issue with the 2026.01 release? (The same Delft3D FM version runs on both Windows and the EDITO Linux Docker image with identical symptoms.)
2. Is there an undocumented MDU / MDW / `dimr_config.xml` option that controls how SWAN re-opens `com.nc` — or a separate file-format setting specifically for `com.nc` (as opposed to the global `ncFormat` that also dictates `map.nc`)?
3. If the underlying issue is how D-Waves' C-level `put_var` calls interact with HDF5 after `nc_close`/`nc_open` cycles, is there a patched kernel build we can try?
4. Alternatively, would it be possible to extend `[output] ncFormat` to accept `64BIT_OFFSET` (CDF-2) or `64BIT_DATA` (CDF-5) as non-HDF5 large-file formats? This would preserve the fix while eliminating the 2 GB constraint.
5. Attempted regression test with **Delft3D FM Suite 2025.01 HMWQ** (pointing the same `dimr_config.xml` to the 2025.01 kernels) was inconclusive: 2025.01 rejected the `initialFields.ini` entries that 2026.01 accepts (`initialsalinity`, `initialtracerlagoon_tracer`), so the run aborted before any wave iteration. If there is a compatibility note between the two releases for `[Initial]` block keywords, a confirmation that the HDF symptom is new in 2026.01 would help us narrow the scope.

Full logs, the reproducer model directory, and the test scripts used to generate the isolation matrix above are available on request.

Thank you for your time.

---

## Attachments suggested

- `test_matrix.csv` — the 6 test configurations + per-test error counts + `hwav` variance
- `baseline_run.log` (UTF-8, first 500 lines of `Stagnone_dxy01_15m.dia` or the DIMR console) showing the error signatures
- `Stagnone_dxy01_15m.mdu` and `wave/stagnone.mdw` (anonymized if sensitive)
- `dimr_config.xml`
