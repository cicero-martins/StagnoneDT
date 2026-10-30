# D-Flow FM 2026.01: configuration points met while building the v04 model

These notes collect the configuration points that took us time to work out while
building the v04 model in May 2026, in the hope that they save others the same
search. Several were our own misreadings, and in each case the answer was in the
manual once we knew where to look. We would be glad to hear of anything we have
misunderstood.

The versions we used are

- **D-Flow FM Suite 2026.01 HMWQ**, kernel `dflowfm 1.2.184`, DIMR `2.00.05`
- **D-Flow FM User Manual 2026** (Deltares)
- **D-Morphology User Manual 2026.02 rev 80910** (Deltares)
- **dfm_tools 0.45.0** (modelbuilder pipeline)
- **HYDROLIB-core 1.0.0**

The first five points were all needed before v04 ran with a wet domain, a
preserved salinity field and the evaporation flux applied. Without them the
model either stopped at initialisation or completed with empty output.

## 1. Evaporation enters as `rainfall_rate`

**What we saw.** The run stopped at initialisation with
`** ERROR : Reading *.ext forcings file: getting unknown QUANTITY evaporation`.

**What we learned.** Manual Table C.9 (pp. 427–429) treats precipitation and
evaporation as a single quantity, `rainfall_rate`, and we found no
`evaporation` quantity in either the old or the new external-forcing format.

**What works for us.** `QUANTITY=rainfall_rate`, with the ERA5 `mer` field,
whose evaporation values are negative. FM applies the sign as positive for rain
in and negative for evaporation out (continuity equation, §3.3.1.2).

```
QUANTITY=rainfall_rate
FILENAME=era5_mer_*.nc
VARNAME=mer
FILETYPE=11
METHOD=3
OPERAND=O
```

`dfm_tools` encodes this mapping (`modelbuilder.py:278`, `'mer' → 'rainfall_rate'`).
Its `preprocess_merge_meteofiles_era5()` writes the old-format file through a
HYDROLIB-core call that is not available in HYDROLIB-core 1.0.0
(`AttributeError: ExtOldFileType`), so for now we write the block by hand.

## 2. Both `Rainfall = 1` and `Evaporation = 1` in `[External Forcing]`

**What we saw.** The model loaded `rainfall_rate` and ran without error, but the
hypersaline lagoon freshened as if no evaporation were applied.

**What we learned.** The `[external forcing]` keywords (Manual §A, pp. 398–400)
include two mass-balance switches, both defaulting to 0.

```
Rainfall    = 0/1   ; include rainfall (positive part of rainfall_rate)
Evaporation = 0/1   ; include evaporation in the mass balance (negative part)
```

Our understanding is that `Evaporation = 1` does not introduce a separate
quantity but lets the negative part of `rainfall_rate` enter the mass balance.

**What works for us.** Both switches set to 1, with `wrimap_rain = 1` and
`wrimap_evaporation = 1` to check the forcing after the run.

## 3. Comments in the old-format `.ext` start with `*`

**What we saw.** The run stopped with
`Unsupported quantity name 'rainfall_rate in mm/day.'`, the words `in mm/day.`
apparently taken as part of the quantity.

**What we learned.** In the old format the comment marker is `*`. Our comment
lines started with `#`, and one of them contained the phrase
"`QUANTITY=rainfall_rate in mm/day`". The parser appears to have read that line
as data, so the end of the phrase was attached to the quantity value.

**What works for us.** `*` for comments, and no literal `QUANTITY=` inside a
comment.

```
* v04: ERA5 evaporation forcing
* ERA5 mer in mm/day, negative for evaporation.
QUANTITY=rainfall_rate
...
```

This also explained why our earlier attempts to fix the quantity name through
the NetCDF metadata had no effect, since the string came from the comment text.

## 4. CF metadata of the ERA5 `mer` file

While chasing point 3 we patched `standard_name`, `long_name` and `units` of the
ERA5 file. Reading `ec_provider.F90`, our understanding is that FM binds the
variable through `VARNAME` and does not need these attributes. We keep the patch
for CF conformance.

```python
ds["mer"].attrs["standard_name"] = "rainfall_rate"
ds["mer"].attrs["long_name"]     = "rainfall_rate"
ds["mer"].attrs["units"]         = "mm day-1"   # CF/UDUNITS form of 'mm/day'
```

`dfm_tools` writes `units = 'mm/day'` (`xarray_helpers.py:358`), which FM
accepts; the CF and UDUNITS form would be `'mm day-1'`.

## 5. `bedLevType = 1` reads `mesh2d_face_z` from the net file

**What we saw.** The model partitioned and ran without error, but every
partition `.dia` reported `my model volume = 0.0E+00 m³` against a correct
`my model area`, and the map output was empty. Almost all the wall time went to
SWAN.

**What we learned.** D-Morphology (`Sedimentmodelnr = 4`) asks for
`bedLevType = 1`, cell-centre bed levels. In FM 2026.01 `bathymetryFile` is no
longer an MDU keyword (`keyword [geometry] bathymetryfile is obsolete`). With
neither that file nor `mesh2d_face_z` in the net file, FM used
`bedLevUni = 5.0 m` for every cell, and with `WaterLevIni = 0` the whole domain
was dry. `mesh2d_node_z` alone serves `bedLevType = 3` to 6, which compute face
levels at run time, while `bedLevType = 1` reads `mesh2d_face_z` directly.

**What works for us.** Adding `mesh2d_face_z` to the net file with the
attributes of the D-Morphology tutorial net file `straight_coast_net.nc`.

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

We take the mean of the surrounding node levels and drop `bathymetryFile` from
the MDU (`scripts/add_face_z_to_netfile.py`). A face left at `_FillValue` falls
back to `bedLevUni`, so we check that no fill values remain.

## A related point on `nudgeTimeUni`

This one is an interaction rather than a parser point. With the default
`nudgeTimeUni = 3600` s and a `nudge_salinity_temperature` field from the CMEMS
regional model, which does not resolve the hypersaline lagoon, the interior was
pulled towards the regional 37.5 within about 12 hours, erasing the initial 42.
A relaxation time of 864000 s (10 days), longer than the lagoon residence time,
keeps the nudging as a slow constraint offshore and leaves the interior free.

## Checklist we now use when adding ERA5 mass-flux forcing

1. [ ] `QUANTITY=rainfall_rate` in the external-forcing block
2. [ ] `Rainfall = 1` and `Evaporation = 1` in `[External Forcing]`
3. [ ] Old-format comments start with `*`, with no `QUANTITY=` inside them
4. [ ] `wrimap_rain = 1` and `wrimap_evaporation = 1` for checking
5. [ ] With D-Morphology, `mesh2d_face_z` in the net file with the attributes above, no fill values, and no `bathymetryFile`
6. [ ] `nudgeTimeUni` longer than the residence time, or no nudging
7. [ ] After initialisation, a non-zero `my model volume` in the partition `.dia` files (of order 10¹¹ m³ for our domain of about 1800 km²)
8. [ ] After 12 h, interior salinity still distinct from the boundary value

## 6. The trachytope `.arl` file is matched by coordinates

**What we saw.** The run stopped at initialisation with

```
** ERROR  : Read error from file: stagnone_trachytopes_v3.arl, Record: 9
** FATAL  : flow_trachyinit:: Error reading trachytope dimensions (dimtrt)
```

with the record number depending on the line.

**What we learned.** The `.arl` format (Manual §C.7.1) gives one record per line
as `xu yu zu TrachytopeNr Fraction`, located by coordinates rather than by link
number, and without a header or count line. Our first file used link numbers.

```
# comment lines start with # or *
# coordinates in the CRS of the mesh (WGS84 lon/lat here)
# xu  yu  zu  TrachytopeNr  Fraction
12.400000  37.804768  0  2  1.0000
12.420000  37.803781  0  2  0.7517
12.420000  37.803781  0  3  0.2483
...
```

Several classes on one link are consecutive lines with the same `xu, yu, zu`.
FM sums their fractions, and the remainder takes the background roughness
`unifFrictCoef`.

The trachytope formula numbers of FM 2026 (§C.7.2.5) differ from those of
earlier versions. Formula 53 is Manning n (one parameter), formula 153 is
Baptist 1 with h_v, mD, C_D and C_b (four parameters), and formula 1 is a
flood-protected area fraction rather than a roughness.

Two further points cost us time, both because the run completes normally.

- **Coordinate system.** The coordinates must be in the CRS of the mesh. With a
  WGS84 mesh and a UTM `.arl`, no record matched and the run gave results
  identical to a run without trachytopes. We now compare time-averaged velocity
  statistics against a no-trachytope baseline, and agreement to four decimal
  places points to a mismatch.
- **Coordinate precision.** FM matched records to links within about 1 cm in
  our tests. With six decimal places of longitude and latitude, about 11 cm at
  this latitude, around 94 % of our records did not match, and nine decimals
  restored full coverage.

`scripts/build_trachytope_arl.py` samples the classification raster in UTM
and writes the `.arl` in the WGS84 coordinates of the mesh edges.

## Small `dfm_tools` items

- `xarray_helpers.py:358` writes `units = 'mm/day'`; `'mm day-1'` would be the CF and UDUNITS form.
- `modelbuilder.py:340` refers to `hcdfm.ExtOldFileType`, which is not in HYDROLIB-core 1.0.0, so `preprocess_merge_meteofiles_era5()` stops after writing the NetCDF.
- `preprocess_ERA5()` leaves the cfgrib `standard_name = 'unknown'` on `mer` and `mtpr`.
