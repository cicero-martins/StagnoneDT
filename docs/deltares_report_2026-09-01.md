# Notes from a three-dimensional vegetated-lagoon model in Delft3D FM 2026.01

**Suggested subject:** Observations on the vegetation and roughness stack in D-Flow FM 2026.01, from a 3D seagrass lagoon application

**From:** Cicero Martins Jr / Università degli Studi di Palermo (cicero.martinsjr@unipa.it)

---

## Context

We have been building a three-dimensional coupled FM + SWAN model of a shallow
seagrass lagoon in western Sicily since early 2026. The suite has carried the
project well, and the vegetation and morphodynamics modules in particular have
let us ask questions we could not have asked otherwise.

Along the way we collected a handful of observations that might be useful to
you. Five are new and concern how submerged vegetation reaches the solver. Two
we wrote up earlier and have attached in full.

We are not certain that all of them are problems. Some may be intended
behaviour that we misread, and at least two were plainly our own input errors
that better diagnostics would have caught sooner. We describe what we observed,
what we think is happening, and where we can, a suggestion. We would be glad to
be corrected on any of it.

## Environment

- **Product:** Delft3D FM Suite 2026.01 HMWQ
- **Kernel:** `D-Flow FM 1.2.184.057d2f7ceeafda462a1b4e598efa4ce4f0c97cc5 (all/release/2026.01)`
- **DIMR:** `DIMR_EXE Version 2.00.057d2f7ceeafda462a1b4e598efa4ce4f0c97cc5, Oct 20 2025`
- **OS:** Windows 11 (64-bit) and Rocky Linux (Intel oneAPI build), same behaviour on both
- **Model:** Stagnone di Marsala lagoon, Sicily. Unstructured mesh, 21,188 nodes,
  25,212 faces, 10 sigma layers, 8 MPI partitions. Mean depth 0.95 m, colonised
  by *Posidonia oceanica* and *Cymodocea nodosa*.

---

# Part 1 — Vegetation and roughness

## 1.1 Canopy momentum sink under trachytope formulas 154, 155 and 156

The Technical Reference describes the Baptist formulation as separating
vegetation resistance into an equivalent bed roughness and a canopy momentum
sink that enters the momentum equation as a `-λ/2·u²` term. Formulas 154, 155
and 156 compute that sink and write it to `rttfu`. In our runs the solution does
not appear to respond to it.

**What we observed.** Two simulations identical except for the canopy drag
coefficient in the trachytope definition, 0.00 against 0.80, giving a momentum
sink of 0 m⁻¹ against 4.0 m⁻¹ over 16,359 vegetated flow links. Formula 154,
`trtRou = Y`. The two solutions come out bit-identical across 48 output frames
and 27,901 cells, in water level, in the three velocity components and in bed
shear stress.

**Our reading, offered tentatively.** `trtrou.f90` looks to us like a correct
implementation of Eqs. 13.36 and 13.37, so we suspect the computed field is not
picked up downstream rather than mis-computed. Two things are consistent with
that. Formula 153, which folds the canopy into one combined Chézy value and
writes no separate sink, does respond to the same parameter change. And under
154 the meadow ends up hydraulically smoother than bare sand, which is what the
bed-roughness half of the formulation would give on its own.

**If it would help,** we can share the two-run pair, the comparison script and
the outputs. It is a three-day window, about 25 minutes on eight cores, so it is
inexpensive to reproduce.

## 1.2 A diagnostic line for `.arl` record matching

This one was our error, and we mention it only because a small addition would
have caught it immediately.

FM matches `.arl` records to flow links by spatial proximity, with what we
measured as roughly a 1 cm tolerance. We wrote our roughness area file with six
decimal places of longitude and latitude, about 11 cm at this latitude, so
around 94% of the records did not match. The run completed normally and the
`.dia` echoed the trachytope configuration as read, so we had no signal that the
field was reaching 5.5% of the meadow. Rewriting with nine decimals brought it to
essentially full coverage.

**Suggestion.** A single line at initialisation reporting the counts, something
like `trachytopes: 16359 of 17280 records matched to links`, would make this
class of error self-evident. The information is available at the point of
matching.

## 1.3 The same diagnostic would cover a CRS mismatch

A related case with the same remedy. If the mesh is geographic and the `.arl` is
projected, or the reverse, no record matches and the run completes with fields
indistinguishable from a run carrying no trachytopes at all.

We now compare time-averaged velocity statistics against a no-trachytope
baseline and suspect a coordinate mismatch when they agree to four decimal
places. The count line proposed above would make that check unnecessary.

## 1.4 Järvelä and Västilä keys in a three-dimensional model

The `[veg]` block accepts `Uchistem`, `Expchistem`, `Uchileaf`, `Expchileaf`,
`Cdleaf` and `Arealeaf`, and the `.dia` echoes them back with the values
supplied. Reading `setbaptist.f90`, the routine consuming them is guarded by
`kmx == 0`, so it runs in the depth-averaged case. With `kmx > 0` the per-layer
path in `setveg.f90` is taken instead. Consistent with that, we found runs with
`Vegetationmodelnr` set to 1, 2 and 3 to be bit-identical in three dimensions.

We raise it because the velocity-dependent reconfiguration the Järvelä
formulation represents is the physically important behaviour for *Posidonia
oceanica*, whose leaves lie over progressively as the flow strengthens. The
three-dimensional path offers mechanical bending, which is a reasonable
alternative model of the same phenomenon, and we have used it.

**Suggestions.** A note in the manual that the empirical reconfiguration
formulation is depth-averaged only would orient users quickly, and a warning
when one of those keys is set with `kmx > 0` would be a natural companion. If a
per-layer Järvelä path is something you are considering, we would be glad to
test it.

## 1.5 The meaning of `Rhoveg = 0`

We set `Rhoveg = 0` intending a canopy held rigid, as a control against which to
measure the bending response. Compared with an otherwise identical run at
`Rhoveg = 900` kg m⁻³, the flow over the meadow is 3 to 4 times faster, which is
the scale of the whole canopy effect rather than of a reconfiguration effect.
Our reading is that `Rhoveg` gates the vegetation drag itself, so zero removes
the canopy.

If that is the intent, a sentence in the manual would be welcome, since "leaf
density is zero" and "the canopy does not bend" are different physical
statements and the first is a natural way to attempt the second. A dedicated
switch for rigid-canopy behaviour would be useful for anyone wanting to separate
the two effects.

**A related observation you may find worth documenting.** Between `Rhoveg = 900`
and `Rhoveg = 1020`, both inside the published natural range for the species, the
velocity field over the meadow differs by about 20% at the upper end of our
velocity range. That is a useful thing for a user to know when choosing the
value.

---

# Part 2 — Earlier reports, attached in full

## 2.1 D-Waves online coupling, HDF error on the `com.nc` write

Attached as `deltares_hdf5_coupling_report.md`.

With `ncFormat = 4`, wave coupling iterations after the first do not reopen
`com.nc` for writing, producing repeated `NetCDF: HDF error` and
`Not a valid ID` messages. The run does not abort and DIMR exits 0, but FM
continues with the iteration-1 wave field, so the wave forcing is effectively
held constant. The report includes an eight-configuration isolation matrix,
which suggests MPI concurrency, HDF5 file locking, the coupling interval and the
MDW boundary declaration style are not the cause.

`ncFormat = 3` removes the symptom entirely and is our workaround. The cost is
the 2 GB classic-NetCDF per-file limit, which our `map.nc` passes for runs longer
than about five days. Our suggestion there was whether `[output] ncFormat` might
accept a large-file non-HDF5 format such as CDF-2 or CDF-5, which would keep the
fix without the size ceiling.

## 2.2 modelbuilder example, three water level boundary blocks

Attached as `deltares_modelbuilder_observation.md`.

The public `modelbuilder_example.ipynb` demonstrates `constant_to_bc`,
`interpolate_tide_to_bc` and `cmems_nc_to_bc` in sequence, each appending a
`waterlevelbnd` block for the same polyline, and FM sums them. For Mediterranean
setups the CMEMS `zos` field already carries the tide, so the combination
double-counts it. We took the example as a self-consistent setup and carried it
through four model versions, reaching about 0.5 m boundary amplitude against a
prescribed 0.24 m.

The notebook reads naturally as a menu of options, which is useful. A short note
that the three are alternatives rather than a sequence, or a warning inside
`cmems_nc_to_bc` when the `ExtModel` already carries a `waterlevelbnd` block on
the same location file, would make that reading unambiguous. We would be happy
to contribute the note as a pull request if that is easier.

## 2.3 Three smaller `dfm_tools` items

- `xarray_helpers.py:358` writes `units = 'mm/day'`; `'mm day-1'` would be
  CF and UDUNITS conformant.
- `modelbuilder.py:340` references `hcdfm.ExtOldFileType`, which is absent from
  HYDROLIB-core 1.0.0, so `preprocess_merge_meteofiles_era5()` fails after the
  NetCDF has been written.
- `preprocess_ERA5()` leaves `standard_name = 'unknown'` on the `mer` and `mtpr`
  variables as cfgrib produces them.

---

## What we can share

For any of the above we can provide the model directory, the input files, the
comparison scripts and the output pairs. The vegetation cases in Part 1 all
reduce to two-run comparisons on a three-day window and are quick to rerun.

The seagrass canopy has turned out to be the first-order control on transport in
this lagoon, which is the subject of a manuscript we are preparing, so this part
of the suite matters to us well beyond the present model. If a patched build
would be useful to test at any point, we would be glad to help.

Thank you for the software and for your time.
