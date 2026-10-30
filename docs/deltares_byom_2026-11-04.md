# Topics for the Bring Your Own Model session, Delft3D User Days 2026

**Session:** Wednesday 4 November 2026, 13:30–17:00

**Model:** three-dimensional D-Flow FM model of the Stagnone di Marsala (western Sicily), coupled online to SWAN through DIMR. It is a micro-tidal lagoon of 0.95 m mean depth colonised by *Posidonia oceanica* and *Cymodocea nodosa*. The mesh has 25,212 faces and 10 uniform sigma layers, and runs use eight MPI partitions. Seagrass enters through the `[veg]` module and sediment through D-Morphology with a sand and a silt fraction.

**Software:** Delft3D FM Suite 2026.01 HMWQ, D-Flow FM kernel `1.2.184.057d2f7c`, DIMR 2.00 (20 October 2025), on Windows 11 and on Rocky Linux with Intel oneAPI.

The topics fall into three groups. The modelling-strategy questions come first, since they are the ones that call for expert judgement. Observations on the software follow, and the earlier reports with their status close the document. Model directories, inputs and two-run comparison pairs can be shared for any item.

## 1. Modelling strategy

### 1.1 Cohesive sediment under waves in a sub-metre lagoon

In the wave-coupled mobile-bed member, lagoon-averaged suspended silt over 7 to 10 July 2025 reaches a mean of 8.1 g/l, with a 95th percentile of 44 g/l, against about 1 mg/l of sand. The maximum bed shear stress exceeds 0.5 N/m² in 30 % of lagoon samples with waves, and its 99th percentile is 7.5 N/m², against 0.39 N/m² without waves. A wave friction factor computed from the total roughness rather than from a skin roughness would give stresses of this order. The settings are `TcrEro = 0.1` N/m², `TcrSed = 0.1` N/m² and `EroPar = 1e-4` kg/m²/s.

A sweep of three-day cold starts is running, with bed updating from the end of the first day. The values below are lagoon statistics over 2 to 4 July.

| Case | Change | Silt p50 / mean / p95 (mg/l) | Median \|Δz_b\| | Bed volume change |
|---|---|---|---|---|
| reference | none | 3.4 / 1707 / 9984 | 5.0 mm | +245 × 10³ m³ |
| deposition | `TcrSed = 1000` | 0.1 / 50 / 272 | 0.3 mm | +83 × 10³ m³ |
| skin friction and deposition | `BsSkin` (Soulsby 2004) with `KsSand = 5e-5`, `KsSilt = 1e-5`, and `TcrSed = 1000` | 0.0 / 0 / 0 | 0.0 mm | −0.2 × 10³ m³ |

Releasing deposition reduces the mean concentration by a factor of 34, and skin friction removes resuspension altogether. The plausibility target adopted for the sweep is a lagoon silt concentration between 1 and 20 mg/l with events up to about 50 mg/l, bed change at the millimetre scale and a closed sediment volume balance. The questions concern how to reach that range on physical grounds rather than by tuning.

- Which bed shear stress, current, wave or combined, and computed with which roughness, enters the Partheniades–Krone erosion and deposition terms in FM 2026.01, and how does `BsSkin` change that when waves are coupled?
- Is continuous deposition (`TcrSed` large) the recommended default for silt in FM, as in Delft3D 4?
- Which calibration strategy is advised for a lagoon without a repeated bathymetric survey, given suspended-sediment observations from satellite only?

### 1.2 Starting morphology from a hydrodynamic spin-up

A run with the sediment module switched on, restarted from a fixed-bed `_rst.nc`, stops at initialisation with `Mismatch in number of sediment fractions in morphology restart file. Not reading restart data at all`, followed by an error. Every mobile-bed member therefore starts cold, and the bed is held through the spin-up by `MorStt`. That parameter is read in the MDU time unit, so a value of 1440 meant 24 minutes in seconds rather than one day. The questions are whether a supported route exists to start the sediment module from a hydrodynamic restart, initialising the bed composition from the `.sed` file, and whether the `.dia` could state `MorStt` with its unit as interpreted.

### 1.3 Cold start of the three-dimensional canopy

With the `[veg]` module active (`Cdveg = 0.8`, `Rhoveg = 900`, stem fields per flow node) and trachytopes off, a cold start on 1 July from the stratified initial state exceeds `maxVelocity = 10` m/s after one hour of simulation. The cell is offshore of the island of Marettimo, at a bed level of −478 m, on a partition boundary. The identical configuration without vegetation integrates normally, and the vegetated configuration restarted from a developed bare state integrates normally as well. With `autoTimestep = 5` in place of 3, the vegetated cold start completes without any velocity warning. The question is whether this interaction between the vegetation term and the time-step limit is expected, and whether `autoTimestep = 5` is the recommended setting for three-dimensional vegetation.

## 2. Observations on the software

### 2.1 Vegetation in D-Waves and SWAN

Three behaviours stand between the D-Waves vegetation keys and a working SWAN vegetation run.

1. The `Veg*` keys of a `[Domain]` block are ignored, and SWAN reports `IVEG 0`, unless `Vegetation = true` is also set in that block.
2. With `FlowVegetation = 1`, the stem height and diameter are written to the SWAN `INPUT` as `******`, and SWAN stops.
3. With a vegetation map and scalar parameters, D-Waves writes `VEGETATION height diameter nstems drag`, the syntax of SWAN versions without the `iveg` selector. The SWAN of the same package reads the height as `iveg` and stops with `Wrong type of data for variable IVEG`.

A wrapper inserting `iveg = 1` (Dalrymple et al., 1984) before SWAN starts restores the run. With it, significant wave height over the vegetated inner-grid points falls to a median of 0.36 of the bare value, while unvegetated points are unchanged.

### 2.2 A "Programming error" message on every rank

Every run on eight partitions logs, on every rank, `Programming error, please report: any_structures_lie_across_multiple_partitions found no partitions with nodes!`. The model defines no structure file. The runs complete and the results are unaffected as far as can be seen, so the message is reported as the text requests.

### 2.3 Abort on the velocity limit

When `maxVelocity` is exceeded, the abort is followed by a segmentation fault in `libdimr`, and the MPI launcher then reports `BAD TERMINATION ... KILLED BY SIGNAL: 9`. The message that identifies the cause appears in the DIMR standard output and in the `.dia` of the reporting partition only. The cell index in that message does not correspond to the global cell numbering, which made the offending cell difficult to locate.

### 2.4 Two defaults found in a companion model

A companion model of the Grand Harbour, Valletta, on the same kernel showed two defaults.

- A boundary `.pli` holding several polylines is accepted, but only the first is used. The `.dia` warns of this, and the remaining sides become closed walls without further notice.
- `TidalForcing` defaults to 1 on a spherical mesh. A run without any forcing over a domain of about 400 km rose by 1 to 2 cm in 6 hours until the key was set to 0.

Both behaviours are documented or warned of. They are listed because in each case the run completed with a physically plausible result.

### 2.5 Conversion of the legacy external-forcing file

ERA5 evaporation enters through the legacy `.ext` as `QUANTITY=rainfall_rate` with negative values, together with `Rainfall = 1` and `Evaporation = 1`, since no evaporation quantity exists in either format ([fm_2026_gotchas.md](fm_2026_gotchas.md)). The conversion demonstration of the session would be an occasion to confirm the equivalent block in the new format.

## 3. Earlier reports

- [deltares_report_2026-09-01.md](deltares_report_2026-09-01.md) covers the vegetation and roughness stack. The canopy momentum sink of trachytope formulas 154 to 156 does not reach the solution. A line counting `.arl` records matched to links would expose precision and CRS errors. The Järvelä keys are inert in 3D, `Rhoveg = 0` removes the canopy rather than stiffening it, and the `[veg]` module is absent from the interface.
- [deltares_hdf5_coupling_report.md](deltares_hdf5_coupling_report.md) covers the HDF error on reopening `com.nc` with `ncFormat = 4`. `ncFormat = 3` remains the workaround in production use, without a size penalty at this mesh size.
- [deltares_modelbuilder_observation.md](deltares_modelbuilder_observation.md) covers the double counting of the tide when the TPXO block of the modelbuilder example is combined with the Mediterranean analysis and forecast `zos`.
- [fm_veg_module_setup.md](fm_veg_module_setup.md) gives the configuration of the `[veg]` module by hand, as used in all vegetated members.
- [fm_2026_gotchas.md](fm_2026_gotchas.md) lists parser and configuration issues met with ERA5 evaporation, D-Morphology and trachytopes.
