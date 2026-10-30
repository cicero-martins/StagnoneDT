# Configuring the FM vegetation module by hand

These notes describe how we set up the `[veg]` module of D-Flow FM for our
seagrass lagoon model, in case they are useful to others doing the same. We
configured it by editing the input files, since we could not find the module
in the Delta Shell interface, and we may well have missed a route that exists.

As far as we can tell, D-Flow FM can represent submerged vegetation in two
ways. The interface offers the trachytope route, and the per-layer vegetation
module is configured through the files. In our three-dimensional runs only the
second produced a response to the canopy drag, as described in
[deltares_report_2026-09-01.md](deltares_report_2026-09-01.md).

| | trachytopes | `[veg]` module |
|---|---|---|
| in the GUI | yes, `TrtRou` | not found |
| in `dflowfm-properties.csv` | yes | not found |
| response to the canopy drag in our 3D runs (kernel 1.2.184) | none observed | yes |
| resolution | depth-averaged equivalent roughness | per sigma layer |
| documented | User Manual ch. 13 | User Manual §13.3 |

The GUI appears to build its model-settings panels from
`plugins/DeltaShell.Plugins.FMSuite.FlowFM/CsvFiles/dflowfm-properties.csv`,
which holds 277 properties, and the only vegetation entry we found there is
`TrtRou`. We found the strings `Vegetationmodelnr`, `stemheight`,
`stemdensity` and `stemdiameter` inside `dflowfm.dll` and `dflowfm-cli.exe`
but in no GUI resource.

The setup has three pieces.

## 1. The `[veg]` block, appended to every partition MDU

We append it to each `*_000?.mdu` as well as to the master `.mdu`. Ours reads

```ini
[veg]
Vegetationmodelnr         = 1
Cdveg                     = 0.8
StemheightConvention      = upward_from_bed
Uchistem                  = 0.10
Expchistem                = -1.56
Uchileaf                  = 0.10
Expchileaf                = -1.56
Cdleaf                    = 0.4
Arealeaf                  = 1.0
Densvegminbap             = 0.0
Rhoveg                    = 900
```

Three points about this block took us some time to work out, and may save
others the same.

**`Rhoveg = 0` appears to switch the vegetation off rather than make the canopy
rigid.** Against an otherwise identical run at 900, the zero case ran 3 to 4
times faster over the meadow, which is the size of the whole canopy effect
rather than of a reconfiguration effect. To vary the stiffness we therefore
varied `Rhoveg` between two non-zero values.

**The Järvelä and Västilä keys seem to act only in depth-averaged runs.**
`Uchistem`, `Expchistem`, `Uchileaf`, `Expchileaf`, `Cdleaf` and `Arealeaf`
are read and echoed to the `.dia`. Our reading of the source is that they are
consumed in `setbaptist.f90`, under a `kmx == 0` guard, and that with layers the
per-layer path in `setveg.f90` is taken instead. Consistent with that,
`Vegetationmodelnr` 1, 2 and 3 gave bit-identical solutions in our 3D runs.

**We keep trachytopes off, `trtRou = N`.** The kernel refuses trachytopes
together with `Vegetationmodelnr >= 2`, and where both are accepted they would
add a second resistance on top of the canopy.

## 2. `initialFields.ini`, three `[Parameter]` blocks

These go alongside the `[Initial]` blocks the model already has.

```ini
[Parameter]
    quantity              = stemheight
    dataFile              = veg_stemheight.xyz
    dataFileType          = sample
    interpolationMethod   = averaging
    averagingType         = mean
    operand               = O
```

The blocks for `stemdensity` and `stemdiameter` follow the same pattern.

## 3. Three `.xyz` sample files, one value per flow node

Each is plain text with `x y value` per line, in the same coordinate system as
the mesh.

```
12.432104881  37.861993204  0.400000
12.432338115  37.861774903  0.400000
```

A few things we learned while building them.

- **Covering the whole domain.** We write an explicit zero wherever the canopy
  is absent, so that no cell is left to the interpolation default.
- **Applying fractional cover.** We scale only the areal density by the cover
  fraction. Height and diameter describe the plant rather than how much of the
  bed it occupies, so we leave them unscaled.
- **The plant-area check.** FM checks that a plant does not cover more than its
  share of bed, so that `pi/4 * D^2` does not exceed `1/density`. We now check
  this when building the file, which is quicker than reading the per-cell
  messages from the kernel.
- **Units.** Metres for `stemheight` and `stemdiameter`, stems per square metre
  for `stemdensity`. We count density per leaf, since the leaf presents the
  frontal area. For *P. oceanica*, with six leaves per shoot, the areal density
  is six times the shoot density.

## Building the files

`scripts/build_veg_fields_from_arl.py` writes the three `.xyz` files from a
trachytope `.arl` and the mesh face coordinates:

```bash
python scripts/build_veg_fields_from_arl.py <arl> <outdir> --faces faces.npz
```

`scripts/setup_veg_member.sh` assembles a complete member. It copies the fields
and `initialFields.ini` from a reference directory, sets `trtRou = N` and
appends the `[veg]` block to every MDU.

## Checking that the module is active

The vegetation fields are written to `map.nc` as `mesh2d_stemheight`,
`mesh2d_rnveg` and `mesh2d_diaveg`, and if they are absent or all zero the
module is probably not running. In our runs a live canopy also showed as a
marked drop in `mesh2d_taus` over the meadow, where an equivalent bed roughness
raises it instead, and as a surface-to-bed speed ratio well above what a
logarithmic profile gives.

We would be glad to hear of a simpler route, or of anything above that we have
misread.
