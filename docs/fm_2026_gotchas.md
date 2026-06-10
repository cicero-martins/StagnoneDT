# D-Flow FM 2026.01 — gotchas encountered building v04

Operational notes from the v04 build (May 2026). Each item caused a build/run failure that took non-trivial debugging to isolate. Documented here so future iterations of this framework, and anyone adopting a similar setup, can short-circuit the same dead ends.

Verified against:

- **D-Flow FM Suite 2026.01 HMWQ** — kernel `dflowfm 1.2.184`, dimr `2.00.05`
- **D-Flow FM User Manual 2026** (Deltares)
- **D-Morphology User Manual 2026.02 rev 80910** (Deltares)
- **dfm_tools 0.45.0** (modelbuilder pipeline)
- **HYDROLIB-core 1.0.0**

The five gotchas below were ALL needed to get v04 to integrate dynamics (non-zero volume, salinity preserved, evap mass flux applied). Without them, the model either FATAL'd at init or ran to completion silently producing all-NaN/zero output.

## 1. `QUANTITY=evaporation` does not exist in old-ext

**Symptom:** FATAL at init: `** ERROR : Reading *.ext forcings file: getting unknown QUANTITY evaporation`

**Cause:** Per Manual Table C.9 (p.427-429), FM unifies precipitation + evaporation as a single `QUANTITY=rainfall_rate`. The `evaporation` keyword is not recognised in either old-ext or new-ext (`[Meteo]`) format.

**Fix:** Use `QUANTITY=rainfall_rate`. ERA5 `mer` (negative for evap) maps naturally — FM applies the value with sign convention positive=rain in, negative=evap out (continuity equation §3.3.1.2: `Q = ... + P − E`).

```
QUANTITY=rainfall_rate
FILENAME=era5_mer_*.nc
VARNAME=mer
FILETYPE=11
METHOD=3
OPERAND=O
```

dfm_tools `modelbuilder.py:278` codifies this mapping (`'mer' → 'rainfall_rate'`); however dfmt's `preprocess_merge_meteofiles_era5()` writes to ext_old via a HYDROLIB-core API that broke in v0.45.0 (`AttributeError: ExtOldFileType`). For now we manually emit the block.

## 2. `Rainfall=1` and `Evaporation=1` must BOTH be in `[External Forcing]`

**Symptom:** false positive — model loads `rainfall_rate` without error, runs without abort, but hipersalinidade dissipates as if no evap forcing was present (negative values silently dropped).

**Cause:** Manual §A `[external forcing]` keyword block (p.398-400) has two independent mass-balance switches:

```
Rainfall    = 0/1   ; include rainfall (positive part of rainfall_rate)
Evaporation = 0/1   ; include evap in mass balance (negative part)
```

Both default to 0. `Evaporation=1` does NOT enable a separate quantity — it authorises the mass coupling when `rainfall_rate` is negative. If absent, the parser accepts the file but the negative branch is ignored.

**Fix:** add `Rainfall=1` + `Evaporation=1` to the `[External Forcing]` MDU block. Recommend also setting `wrimap_rain=1` and `wrimap_evaporation=1` to validate the forcing post-run.

## 3. Old-ext comment marker is `*`, not `#`

**Symptom:** FATAL: `Unsupported quantity name 'rainfall_rate in mm/day.'` — with the literal text `in mm/day.` appearing as if it were part of the QUANTITY value.

**Cause:** old-ext canonical comment marker is `*` (asterisk). Lines starting with `#` are NOT recognised as comments and are read as data. If a `#` comment line contains the literal substring `QUANTITY=`, the parser captures everything from that token to the end of line as the actual QUANTITY value, contaminating the legitimate `QUANTITY=` line below.

In our case the `#` comment block introducing the rainfall_rate forcing contained the explanatory phrase "FM unifies precip + evap as `QUANTITY=rainfall_rate in mm/day`." — the trailing "in mm/day." segment was glued onto the QUANTITY value.

**Fix:** use `*` for comments, AND never write `QUANTITY=` literally inside any comment text (even with `*` marker — robustness).

```
* v04: ERA5 evap forcing for hipersalinidade fix
* ERA5 mer mm/day, negative=evap. FM uses rainfall_rate.
QUANTITY=rainfall_rate
...
```

This explained why our previous attempts to "fix" the quantity name by patching the NetCDF metadata had no effect: the bad string was coming from the **comment text in the .ext file**, not from any NC attribute.

## 4. ERA5 `mer` NetCDF needs CF metadata patch (cosmetic but harmless)

**Symptom:** prior to identifying gotcha #3, we suspected the NC metadata was the issue and patched `standard_name`, `long_name`, and `units`. Per agent review of FM's `ec_provider.F90` source on the OSS SVN trunk, this patching is **not required** — FM uses `VARNAME=mer` (from the ext file) to bind the variable, not its CF attributes.

**Recommended patch anyway** (improves CF compliance, harmless to FM):

```python
ds["mer"].attrs["standard_name"] = "rainfall_rate"
ds["mer"].attrs["long_name"]     = "rainfall_rate"
ds["mer"].attrs["units"]         = "mm day-1"   # CF/UDUNITS canonical (was 'mm/day')
```

The `units='mm/day'` written by dfmt `xarray_helpers.py:358` (literal string after `* 86400`) is not CF/UDUNITS canonical and is technically a latent bug, even though FM tolerates it.

## 5. `bedLevType=1` requires `mesh2d_face_z` in the netfile

**Symptom:** model partitions and runs without FATAL, but `my model volume = 0.0E+00 m³` in every partition `.dia` file, against `my model area` reporting correct values. Output map.nc fills with NaN/zero. Run wall-time dominated by SWAN (FM has no work to do — all cells dry).

**Cause:** D-Morphology (`Sedimentmodelnr=4`) requires `bedLevType=1` (cell-center bathymetry). FM 2026.01 dropped `bathymetryFile` as an MDU keyword (rejected at parse: `keyword [geometry] bathymetryfile is obsolete`). With neither `bathymetryFile` nor `mesh2d_face_z` in the netfile, FM silently falls back to `bedLevUni=5.0 m` for every cell. With `WaterLevIni=0`, all cells emerge → volume 0.

`mesh2d_node_z` (per-vertex) alone is **not** sufficient for `bedLevType=1` — it's used by `bedLevType=3..6` which compute face z at runtime, but `bedLevType=1` reads pre-computed cell-center values from `mesh2d_face_z` directly.

**Fix:** add `mesh2d_face_z` to the netfile with the UGRID attributes that FM 2026 expects (verified against the official Deltares D-Morphology tutorial netfile `straight_coast_net.nc`):

```
double mesh2d_face_z(mesh2d_nFaces) ;
    mesh2d_face_z:_FillValue    = -999. ;
    mesh2d_face_z:mesh          = "mesh2d" ;
    mesh2d_face_z:location      = "face" ;
    mesh2d_face_z:coordinates   = "mesh2d_face_x mesh2d_face_y" ;
    mesh2d_face_z:standard_name = "altitude" ;
    mesh2d_face_z:long_name     = "z-coordinate of mesh faces" ;
    mesh2d_face_z:units         = "m" ;
```

Values can be computed as the mean of surrounding nodes' z values (functionally equivalent to bedLevType=3 runtime computation, but stored explicitly). Drop `bathymetryFile` from the MDU. See `scripts/add_face_z_to_netfile.py`.

**Critical risk:** any cell with `_FillValue` in `mesh2d_face_z` triggers the `bedLevUni` fallback FOR THAT CELL. After running the fix, verify `(arr != -999).sum() == arr.size` on the variable.

## Companion: `nudgeTimeUni` defeats hipersalinidade IC if too short

Not a parser bug, but an easy-to-miss interaction. The default `nudgeTimeUni=3600 s` (1 hour relaxation timescale) combined with a `nudge_salinity_temperature` field built from CMEMS regional (which doesn't resolve the lagoon's hypersaline core) pulls model state ~63% toward the 37.5 ppt regional value every hour, dominating tide+evap and erasing the 42 ppt initial condition within ~12 h.

**Fix:** set `nudgeTimeUni = 864000` (10 days), longer than the lagoon residence time, so the nudge becomes a slow guard rail offshore without overwriting interior dynamics. Alternative: remove the `nudge_salinity_temperature` block entirely from ext_old.

## Diagnostic checklist when adding ERA5 mass-flux forcing in FM 2026

1. [ ] `QUANTITY=rainfall_rate` (not evaporation) in the ext block
2. [ ] `[External Forcing]` MDU has both `Rainfall=1` and `Evaporation=1`
3. [ ] All ext_old comments use `*` (never `#`); no `QUANTITY=` substrings inside comments
4. [ ] Output flags `wrimap_rain=1` and `wrimap_evaporation=1` for validation
5. [ ] If `Sedimentmodelnr=4` (D-Morph): netfile has `mesh2d_face_z` with the seven UGRID attributes above; no fill values; `bathymetryFile` keyword removed
6. [ ] `nudgeTimeUni > residence_time` (or remove nudge entirely)
7. [ ] After init: `my model volume` in partition `.dia` files is non-zero (~10¹¹ m³ scale for our ~1800 km² domain)
8. [ ] After 12h sim-time: interior salinity has not collapsed to boundary value (compare to `wrimap_salinity` slice in map.nc)

## 6. Trachytope `.arl` is coordinate-based, NOT link-ID-based

**Symptom:** Run aborts at init with:
```
** ERROR  : Read error from file: stagnone_trachytopes_v3.arl, Record: 9
** FATAL  : flow_trachyinit:: Error reading trachytope dimensions (dimtrt)
```
(Record number varies depending on which line FM trips on.)

**Cause:** The `.arl` format (FM Manual §C.7.1) uses **spatial coordinates**, not link IDs. FM reads `xu yu zu TrachytopeNr Fraction` per row. Any other format (link-ID, count header, wrong column order) will produce this FATAL at init. There is NO header/count line.

**Correct format per FM Manual C.7.1** (WGS84 coords for our mesh):
```
# comment lines start with # or *
# COORDS: WGS84 lon/lat -- must match mesh CRS
# xu  yu  zu  TrachytopeNr  Fraction
12.400000  37.804768  0  2  1.0000
12.420000  37.803781  0  2  0.7517
12.420000  37.803781  0  3  0.2483
...
```

Multiple trachytope classes for the same link = consecutive lines with identical `xu,yu,zu`. FM sums fractions; remaining `(1 − sum)` takes the MDU `unifFrictCoef` background roughness.

**TTD formula numbers (FM 2026, §C.7.2.5) — NOT the same as older FM versions:**
- Formula `53` = Manning n [s/m^1/3] (one parameter)
- Formula `153` = Baptist 1 [h_v m, mD 1/m, C_D -, C_b m^0.5/s] (four parameters)
- Formula `1` = flood-protected area fraction — NOT a roughness formula; using it as Manning silently does nothing useful

**Coordinate system — critical silent-failure gotcha (2026-06-10):** The xu/yu in the `.arl` **must be in the same CRS as the mesh**. FM matches ARL entries to flow links by spatial proximity in the mesh CRS. If the mesh is WGS84 (edge_x ~12.4) but the ARL uses UTM33N (~271000), **no links are ever matched and the model runs to completion without FATAL or WARNING, but trachytopes have zero effect** — velocities and WL fields are identical to the no-VR baseline.

Diagnostic: compare time-averaged velocity stats (VR vs no-VR baseline) — if identical to 4+ decimal places, suspect CRS mismatch. Check `ds['mesh2d_edge_x'].values.max()`: if ~13 it is WGS84; if ~280000 it is UTM.

**Build script:** `scripts/build_trachytope_arl.py` — reads WGS84 edge coords, reprojects to UTM33N *only* for TIF raster sampling (20m circular kernel), then writes ARL in **WGS84** (`edge_x`/`edge_y`, not `edge_x_utm`/`edge_y_utm`). The UTM transform must NOT leak into the ARL output coordinates.

## Latent dfm_tools issues worth reporting upstream

- `xarray_helpers.py:358`: writes `units = 'mm/day'` literally; should be `'mm day-1'` (CF/UDUNITS).
- `modelbuilder.py:340`: `hcdfm.ExtOldFileType` does not exist in HYDROLIB-core 1.0.0, breaking `preprocess_merge_meteofiles_era5()` after the .nc is written.
- The mer/mtpr `standard_name='unknown'` from cfgrib should be patched in `preprocess_ERA5()` for CF compliance.
