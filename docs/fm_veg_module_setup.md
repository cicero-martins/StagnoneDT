# Configuring FM's native vegetation module by hand

D-Flow FM carries submerged vegetation in two unrelated places. Only one of them
is reachable from the Delft3D FM Suite interface, and it is not the one that
delivers the canopy term.

| | trachytopes | `[veg]` module |
|---|---|---|
| in the GUI | yes, `TrtRou` | **no** |
| in `dflowfm-properties.csv` | yes | absent |
| canopy momentum sink reaches the solver | **no** in kernel 1.2.184 | yes |
| resolution | depth-averaged equivalent roughness | per sigma layer |
| documented | User Manual ch. 13 | User Manual §13.3 |

The GUI builds its model-settings panels from
`plugins/DeltaShell.Plugins.FMSuite.FlowFM/CsvFiles/dflowfm-properties.csv`,
which holds 277 properties. The only vegetation entry is `TrtRou`. The strings
`Vegetationmodelnr`, `stemheight`, `stemdensity` and `stemdiameter` appear
nowhere in any GUI resource, only inside `dflowfm.dll` and `dflowfm-cli.exe`.

So the module has to be configured by editing files. There are three pieces.

## 1. The `[veg]` block, appended to every partition MDU

Append to each `*_000?.mdu` as well as the master `.mdu`. Ours:

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

Three things about this block that cost us time.

**`Rhoveg = 0` does not mean a rigid canopy, it disables the vegetation.**
Measured against an otherwise identical run at 900, the zero case runs 3 to 4
times faster over the meadow, which is the whole canopy effect and not a
reconfiguration effect. To vary stiffness, vary `Rhoveg` between two non-zero
values.

**The Järvelä and Västilä keys are read, echoed to the `.dia`, and inert in
3D.** `Uchistem`, `Expchistem`, `Uchileaf`, `Expchileaf`, `Cdleaf` and
`Arealeaf` are consumed by `setbaptist.f90`, which is guarded by `kmx == 0`.
With layers the per-layer path in `setveg.f90` runs instead. Consistent with
that, `Vegetationmodelnr` 1, 2 and 3 give bit-identical solutions in 3D.

**Turn trachytopes off**, `trtRou = N`. The kernel refuses trachytopes together
with `Vegetationmodelnr >= 2`, and where it does not refuse them the two would
add a second, redundant resistance on top of the canopy.

## 2. `initialFields.ini`, three `[Parameter]` blocks

Alongside whatever `[Initial]` blocks the model already has:

```ini
[Parameter]
    quantity              = stemheight
    dataFile              = veg_stemheight.xyz
    dataFileType          = sample
    interpolationMethod   = averaging
    averagingType         = mean
    operand               = O
```

and the same for `stemdensity` and `stemdiameter`.

## 3. Three `.xyz` sample files, one value per flow node

Plain text, `x y value` per line, in the **same CRS as the mesh**.

```
12.432104881  37.861993204  0.400000
12.432338115  37.861774903  0.400000
```

**Cover the whole domain, not just the meadow.** A sample file that only carries
the vegetated cells leaves every other cell to whatever the interpolation
defaults to. Write an explicit zero everywhere the canopy is absent.

**Fractional cover scales the areal density and nothing else.** Height and
diameter are properties of a plant, not of how much bed it covers, so scaling
them would be a different and wrong claim about the biology.

**FM applies a plant-area consistency check.** A plant may not cover more than
its share of bed, so `pi/4 * D^2` must not exceed `1/density`. Check it when
building the file rather than letting the kernel complain per cell.

Units are metres for `stemheight` and `stemdiameter`, and stems per square metre
for `stemdensity`, counted **per leaf** if that is what presents the frontal
area. For *P. oceanica*, six leaves per shoot means the areal density is six
times the shoot density.

## Building the files

`scripts/build_veg_fields_from_arl.py` writes the three `.xyz` from a
trachytope `.arl` and the mesh face coordinates:

```bash
python scripts/build_veg_fields_from_arl.py <arl> <outdir> --faces faces.npz
```

`scripts/setup_veg_member.sh` assembles a complete member, copying the fields
and `initialFields.ini` from a reference directory, setting `trtRou = N` and
appending the `[veg]` block to every MDU.

## Checking it took effect

The vegetation fields are written to `map.nc` as `mesh2d_stemheight`,
`mesh2d_rnveg` and `mesh2d_diaveg`. If they are absent or all zero the module
is not running. A live canopy also shows up as a large drop in `mesh2d_taus`
over the meadow, where an equivalent bed roughness raises it instead, and as a
surface-to-bed speed ratio well above what a logarithmic profile can produce.
