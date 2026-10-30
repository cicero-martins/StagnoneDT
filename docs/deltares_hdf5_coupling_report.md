# D-Flow FM and D-Waves online coupling: HDF error when SWAN reopens `com.nc`

**Suggested subject:** D-Flow FM + D-Waves online coupling, repeated "NetCDF: HDF error" on the `com.nc` write with `ncFormat = 4`, and the wave field held at its first value

**From:** Cicero Martins Jr / Università degli Studi di Palermo (cicero.martinsjr@unipa.it)

---

We came across this while coupling SWAN to our lagoon model, and we write it up
in case it is useful. A simple workaround exists and we use it, so the request
is modest. It may be a known behaviour, or something in our setup that we have
misread.

## Environment

- **Product:** Delft3D FM Suite 2026.01 HMWQ, with
  `DIMR_EXE Version 2.00.057d2f7ceeafda462a1b4e598efa4ce4f0c97cc5, Oct 20 2025` and
  `D-Flow FM kernel: 1.2.184.057d2f7ceeafda462a1b4e598efa4ce4f0c97cc5 (all/release/2026.01)`
- **OS:** Windows 11 (64-bit), NTFS local disk, 16 GB RAM. The same pattern
  appeared on the EDITO Datalab `delft3dfm_run_docker` service, a Linux
  container, so it does not seem to be specific to the operating system.
- **Coupling mode:** DIMR online with flow, the `wave` component in a
  `<startGroup>` within `<parallel>`, alongside `DFlowFM`.
- **Model:** Stagnone di Marsala lagoon (Sicily, Italy). Unstructured FM mesh of
  21k nodes on 4 MPI partitions, and SWAN on nested outer and inner grids of
  about 400 m and 100 m.

## What we observed

At every `wave.Update` after the first, each MPI partition logs the following
pattern (partition 0 shown).

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

Over a nine-day simulation this produces thousands of error lines. The
simulation does not abort and DIMR exits with code 0. As far as we can see,
SWAN writes `hrms`, `tp`, `dir` and the other fields into `com.nc` only during
the first coupling iteration, so D-Flow FM reads the same wave field for the
rest of the run.

```
station BocaNord, hwav time series, 13 samples:
  2025-07-01 00:00  0.0000 m   (start, before iteration 1)
  2025-07-01 00:10  0.1860 m   <- iteration 1 written
  2025-07-01 00:20  0.1860 m   <- later iterations fail, FM reads the iteration-1 value
  2025-07-01 00:30  0.1860 m
  ...
  2025-07-01 02:00  0.1860 m
  total unique values: 2 (zero and the iteration-1 constant)
```

The offshore TPAR forcing varies across the run (nine `.bnd` files from hourly
CMEMS data, Hs from 0.3 to 2.0 m), so the waves would be expected to respond.

## Reproducer

A two-hour window reproduces the pattern reliably, in about 10 minutes on a
six-core laptop. We are happy to share the configuration files and an MDW and
MDU pair that show it. The settings that seem to matter are

```ini
# MDU
[output]
ncFormat                = 4    # see the test matrix below
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

## Test matrix

Two-hour runs, with the same MDU and MDW except for the variable noted.

| Test | `ncFormat` | MPI partitions | `HDF5_USE_FILE_LOCKING` | `AppendCOM` | MDW boundary definition | COMWriteInterval | HDF errors in log | `hwav` unique values |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| baseline | 4 | 4 | ON | false | xy-coordinates | 600 s | 1796 | 2 |
| **nc3 (classic)** | **3** | 4 | ON | false | xy-coordinates | 600 s | **0** | **12–13** |
| nolock | 4 | 4 | FALSE | false | xy-coordinates | 600 s | 429 | 2 |
| serial | 4 | 1 | ON | false | xy-coordinates | 600 s | 429 | 2 |
| append | 4 | 4 | ON | true | xy-coordinates | 600 s | 1672 | 2 |
| nc5 (written as nc3) | 5 | 4 | ON | false | xy-coordinates | 600 s | 0 | 12–13 |
| mn-coords | 4 | 4 | ON | false | grid-coordinates | 600 s | 44 | 2 |
| coupling interval | 4 | 4 | ON | false | xy-coordinates | 1200 s | 780 | 2 |

What the matrix suggests to us:

1. Only `ncFormat = 3` removed the errors and restored a time-varying `hwav` at
   every station (12 to 13 unique values over the 13 output steps).
2. A serial run (`nPart = 1`) and disabling HDF5 file locking each reduced the
   error count about fourfold, but neither restored time-varying waves. Since the
   pattern persists in a serial run, concurrent MPI access seems an unlikely
   cause.
3. `AppendCOM = true`, which the D-Waves manual describes as an alternative
   write mode, left the error count and `hwav` at the baseline.
4. FM accepted `ncFormat = 5` without complaint and wrote `NETCDF3_CLASSIC`
   output (checked with `nc_inq_format`), so we understand `ncFormat` to support
   3 and 4.
5. Declaring the MDW boundaries in `grid-coordinates` (M/N indices), as the
   manual recommends, reduced the HDF errors about fortyfold (1796 to 44) but
   left `hwav` constant after the first iteration. SWAN was still called at every
   coupling step, so the boundary declaration does not seem to be the cause. We
   have kept `grid-coordinates` anyway, following the manual.
6. Doubling the coupling interval from 600 s to 1200 s, the 20-minute
   convention of Choo et al. (2024), did not restore time-varying waves. The
   error count fell from 1796 to 780 because there are fewer `wave.Update`
   calls, but each call after the first showed the same failure. A timing or
   race condition therefore seems unlikely to us, and our guess is that the
   reopen of an HDF5 file is involved.

## Workaround in production use

`ncFormat = 3` (classic NetCDF) removes the HDF errors and restores
time-varying waves at all stations, and every coupled run of the project has
used it since. We first expected the 2 GB ceiling of the classic format to limit
run length, but it applies to the fixed-size part of a file and to each record
of a variable rather than to the file as a whole, and FM writes the output
fields as record variables. Our nine-day 3D runs on eight partitions with
`mapInterval = 1800` produce `map.nc` files of 4.5 to 5.0 GB per partition in
`NETCDF3_CLASSIC`, with all 433 frames readable. The workaround therefore costs
us nothing at the present mesh size, and the questions below concern only the
`ncFormat = 4` path.

## Questions

1. Is this a known behaviour of the 2026.01 release? The same version showed it
   on Windows and in the EDITO Linux image.
2. Is there an MDU, MDW or `dimr_config.xml` option that controls how SWAN
   reopens `com.nc`, or a file-format setting for `com.nc` separate from the
   global `ncFormat` that also sets `map.nc`?
3. If the cause lies in how the D-Waves `put_var` calls meet HDF5 after
   `nc_close` and `nc_open` cycles, is there a build we could test?
4. We tried the same `dimr_config.xml` with the 2025.01 kernels, but that run
   stopped before the first wave iteration, because 2025.01 did not accept the
   `initialFields.ini` entries `initialsalinity` and
   `initialtracerlagoon_tracer` that 2026.01 accepts. If you know whether the HDF
   behaviour is new in 2026.01, that would help us narrow it down.

Full logs, the reproducer directory and the scripts behind the matrix are
available on request.

Thank you for your time.

---

## Attachments available

- `test_matrix.csv`, the test configurations with per-test error counts and `hwav` variance
- `baseline_run.log`, the first 500 lines of `Stagnone_dxy01_15m.dia` or of the DIMR console, with the error signatures
- `Stagnone_dxy01_15m.mdu` and `wave/stagnone.mdw`
- `dimr_config.xml`
