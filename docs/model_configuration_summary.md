# Configuration of the Stagnone model ensemble

Dimensions, quantities and coefficients of the coupled D-Flow FM and SWAN
model of the Stagnone di Marsala lagoon used in Paper 1, read from the input
files of the members in `model/_arm_*` and `model/dflowfm_v04AE_*` and checked
against `manuscript_v2/`. The base configuration is that of the wave-coupled
vegetated mobile-bed member (`model/_arm_vwm_e2p3_swan/`), and the settings
that differ between members are listed in the last two sections. Values
derived from the inputs rather than read from them are marked as derived.

## Software and computation

| Item | Value |
|---|---|
| Package | Delft3D FM Suite 2026.01 HMWQ |
| Flow solver | D-Flow FM, kernel 1.2.184 |
| Wave model | SWAN through D-Waves, coupled online under DIMR |
| Parallel decomposition | 8 MPI partitions (about 3000 cells each), PETSc solver on the partitioned run |
| Host of record | 48-core Linux server (simit) |
| Wall time, coupled nine-day member | 4.5 to 6 h |
| Wall time, uncoupled nine-day member | under 3 h |
| Wall time, three-day coupled segment | about 1.5 h |
| Share of coupled wall time taken by SWAN | about four fifths |

## Domain and horizontal mesh

| Quantity | Value |
|---|---|
| Coordinate system | Geographic, WGS84 |
| Extent | 11.96 to 12.56° E, 37.70 to 38.06° N |
| Nodes, edges, faces | 21 188, 46 408, 25 212 |
| Faces by shape | 14 969 quadrilateral, 10 243 triangular |
| Spacing offshore | about 880 m |
| Spacing in the lagoon and along the shorelines | about 60 m (lagoon faces 55 to 90 m as equivalent side, median 68 m) |
| Cells across the northern inlet (400 m) | about 6 |
| Cells across the southern inlet (2900 m) | about 40 |
| Flow links inside the lagoon | 7345 |
| Open boundary | One polyline of 49 nodes along the western, southern and northern edges |
| Bed level range (mesh nodes) | −729 m to +10 m |
| Mean depth of the lagoon | 0.95 m |

The lagoon bed comes from the 2006 survey gridded at 20 m (ED50 / UTM 33N in
the source file), held on the mesh nodes and read at cell centres
(`bedLevType = 1`). The Trapani port basin was deepened with EMODnet 2024
samples, never raised. The 20 m dredged channel through the northern sill is
below the mesh scale and enters only through the cell-centre bed level.

## Vertical discretisation

| Quantity | Value |
|---|---|
| Layer type | Sigma (`layerType = 1`) |
| Number of layers | 10 (`kmx = 10`) |
| Distribution | Uniform. `sigmaGrowthFactor = 1.2` is present in the file and inactive with `numTopSig = 0` |
| Layer thickness at the mean lagoon depth | about 0.095 m (derived) |
| Layers occupied by the 0.40 m canopy at the mean depth | lowest four and part of the fifth (derived) |

## Time and numerics

| Setting | Value |
|---|---|
| Simulated window | 1 July 00:00 to 10 July 00:00 2025 UTC (nine days); scoring from day 2 |
| Reference date | 1 January 2025 |
| Time step | Adaptive, Courant limit `CFLMax = 0.7` |
| Maximum time step | 30 s coupled, 15 s uncoupled |
| Growth limit of the time step | factor 1.1 per step (`Dtfacmax`) |
| Time-step criterion | `autoTimestep = 3` (horizontal) |
| Forcing update interval (`dtUser`) | 300 s |
| Initial ramp of boundary forcing (`tlfSmo`) | 3600 s |
| Momentum advection | Perot scheme (`advecType = 33`) |
| Limiter, momentum and salinity/temperature | Monotone central (`limTypMom = limTypSa = 4`) |
| Vertical advection | Implicit for momentum (`vertAdvTypMom = 6`), central implicit for salinity and temperature (`= 4`) |
| Implicitness of the free surface | `teta0 = 0.55` |
| Water-level solver | Preconditioned conjugate gradient |
| Upper bound on salinity | 80 (`saliMax`) |
| Output | Stations every 600 s, maps every 1800 s, restart every 86 400 s, classic NetCDF (`ncFormat = 3`) |

## Physical parameters of the flow model

| Parameter | Value |
|---|---|
| Turbulence closure | k–ε (`turbulenceModel = 3`) |
| Background vertical eddy viscosity and diffusivity | 1 × 10⁻⁴ m²/s |
| Horizontal eddy viscosity and diffusivity | 0.1 m²/s, with a Smagorinsky coefficient of 0.2 on the viscosity |
| Equation of state | UNESCO (`idensform = 2`), reference density 1023 kg/m³ |
| Salinity, temperature | Both transported and active in the density |
| Heat model | Excess temperature (`temperature = 3`), Stanton and Dalton numbers 0.0013, Secchi depth 2 m |
| Bed roughness | Manning, uniform 0.023 s m⁻¹ᐟ³ in every member |
| Trachytopes | Off (`trtRou = N`) in every member, the file references notwithstanding |
| Wind drag | Charnock (`iCdTyp = 4`) with the Charnock parameter from ERA5 |
| Air density | 1.2 kg/m³ |
| Gravity | 9.81 m/s² |
| Wave–current bed stress | Fredsøe (1984) (`rouWav = FR84`), wave effects suppressed below 0.1 m depth (`hminlw`) |
| Rainfall and evaporation | Both enabled, evaporation as negative rainfall from ERA5 |

## Boundary conditions, initial condition and atmospheric forcing

| Quantity | Source and treatment |
|---|---|
| Water level at the open boundary | CMEMS Mediterranean analysis and forecast sea surface height at 15 min (`cmems_mod_med_phy-ssh_anfc_4.2km_PT15M-i`), which carries the tide; no separate tidal constituents |
| Reference-level offset | Per-node offset added to the boundary water level, anchored at +0.449 m on the Marettimo gauge (JRC TAD 658) over 384 days and spread along the boundary by the CMEMS mean dynamic topography |
| Seasonal residual of the anchor | about ±0.07 m (monthly means +0.361 to +0.505 m) |
| Salinity and temperature at the boundary | CMEMS Mediterranean physical reanalysis, depth-resolved |
| Advection velocity at the boundary | CMEMS reanalysis, depth-resolved (`uxuyadvectionvelocitybnd`), needed for stability in the deep offshore cells |
| Interior nudging of salinity and temperature | Towards the CMEMS fields, relaxation time 8.64 × 10⁵ s (10 days) |
| Wind | ERA5 10 m neutral wind, interpolated to 0.005°, blended with the AltaVilaEst station record by a weight of 1 within 3 km of the lagoon centre falling linearly to 0 at 8 km |
| Pressure, Charnock parameter, evaporation | ERA5 hourly |
| Initial salinity, lagoon | 42 |
| Initial temperature and salinity outside the lagoon, stratified start | CMEMS profiles at the start time, 25.8 °C and 37.5 at the surface to 16.2 °C and 38.3 below 260 m |
| Initial temperature and salinity outside the lagoon, uniform start | 24 °C and 37.5 over the column |

Wind statistics over the window at the lagoon centre are 4.5 m/s from the
station against 3.3 m/s from ERA5, with a median difference in direction of
17°.

## Wave model

| Setting | Value |
|---|---|
| Outer grid | 69 × 54 points at about 800 m, whole flow domain |
| Inner grid | 121 × 221 points at 88 m east–west and 111 m north–south, lagoon and inlets, nested in the outer grid |
| Cells across the northern inlet, inner grid | about 4 |
| Boundary spectra | Parametric (Hs, peak period, mean direction) from the CMEMS Mediterranean wave product on nine segments of the outer grid (west, south, north) |
| Directions | 24 over the full circle (15°) |
| Frequencies | 24, logarithmic, 0.05 to 1.0 Hz |
| Physics | Third generation, Komen whitecapping, quadruplets, refraction, frequency shift |
| Triads, wave setup, diffraction | Off |
| Depth-induced breaking | Battjes and Janssen (1978), α = 1.0, γ = 0.73 |
| Bottom friction | JONSWAP, 0.067 m²/s³ |
| Minimum depth | 0.05 m |
| Mode | Stationary within each exchange |
| Convergence | 2 % change in Hs and Tm01 at 98 % of wet points, at most 15 iterations |
| Coupling interval | 3600 s |
| Wave forcing on the flow | Three-dimensional dissipation (`WaveForces = dissipation 3d`) |
| Water density in SWAN | 1025 kg/m³ |

### Canopy in the wave model (members marked ˢ)

| Setting | Value |
|---|---|
| Formulation | Dalrymple et al. (1984) as implemented by Suzuki et al. (2012), selector `iveg = 1` |
| Vegetated points on the inner grid | 3929 |
| Stem density | Flow-model field averaged within half a grid step, mean 1370 and maximum 3000 m⁻² |
| Height | 0.34 m (density-weighted mean of the flow-model field) |
| Diameter | 8.6 mm (density-weighted mean) |
| Drag coefficient | 0.8 |
| Effect in a three-day test | Hs over vegetated points at a median of 0.36 of its value without the canopy in SWAN |

## Seagrass canopy in the flow model

The canopy is resolved per sigma layer through the vegetation module
(`[veg]`, `Vegetationmodelnr = 1`), with drag per unit volume
½ ρ C_D D m |u| u over the layers below the canopy height.

| Parameter | *P. oceanica* | *C. nodosa* |
|---|---|---|
| Shoot density (m⁻²) | 500 | 800 |
| Leaves per shoot | 6 | 3 |
| Leaf density at full cover (m⁻², derived) | 3000 | 2400 |
| Leaf width D (m) | 0.010 | 0.004 |
| Frontal area per unit volume at full cover, m·D (m⁻¹, derived) | 30 | 9.6 |
| Canopy height h_v (m) | 0.40 | 0.15 |
| Leaf material density (kg/m³) | 900 | 900 |
| Drag coefficient C_D | 0.8 | 0.8 |
| Median fractional cover | 0.685 | 0.181 |
| Share of lagoon links dominated by the class | 48.6 % | 22.5 % |

The remaining lagoon links are bare sand (25.6 %) and rock (3.3 %). Cover
multiplies the leaf density only. The resulting stem-density field has 7047
nonzero samples, a median of 1079 and a maximum of 3000 m⁻². Further keys of
the module are `Cdleaf = 0.4`, `Arealeaf = 1.0`, `Uchistem = Uchileaf = 0.10`,
`Expchistem = Expchileaf = −1.56` and `Rhoveg = 900`, the last enabling the
bending response. The classification is a random forest on PlanetScope
SuperDove imagery of August 2023 at 3 m, transferred to the flow links within
a 20 m search radius.

## Sediment and morphology (mobile-bed members)

| Parameter | Sand | Silt |
|---|---|---|
| Type | Non-cohesive | Cohesive |
| Median diameter | 150 µm | |
| Particle density | 2650 kg/m³ | 2650 kg/m³ |
| Dry bed density | 1600 kg/m³ | 500 kg/m³ |
| Transport formula | Van Rijn (2007), TRANSPOR2004 (`TraFrm = −2`) | Partheniades–Krone |
| Settling velocity | from the formula | 0.5 mm/s |
| Initial erodible thickness | 0.5 m above 15 m depth, tapered to 0 at 20 m | same |

| Silt parameter | Original set | Deposition set | Erosion set |
|---|---|---|---|
| Critical shear stress for erosion (N/m²) | 0.1 | 0.1 | 0.2 |
| Critical shear stress for sedimentation (N/m²) | 0.1 | 1000 | 1000 |
| Erosion parameter (kg m⁻² s⁻¹) | 1 × 10⁻⁴ | 1 × 10⁻⁴ | 3 × 10⁻⁵ |

| Morphology setting | Value |
|---|---|
| Morphological acceleration factor | 1 |
| Spin-up before bed update (`MorStt`) | 0 s |
| Suspended sediment in the density field | Off (`DensIn = false`) |
| Bed and suspended load factors | 1.0 |
| Bed-slope factors | `AlfaBs = 1.0`, `AlfaBn = 1.5`, `ISlope = 2` |
| Threshold sediment thickness | 0.05 m (`Thresh`) |
| Reference concentration | 1600 kg/m³ (`Cref`) |

## Ensemble members

| Code | Waves | Canopy | Bed | Run |
|---|---|---|---|---|
| `---` | no | no | fixed | Nine days from 1 July |
| `W--` | SWAN | no | fixed | Nine days from 1 July |
| `-V-` | no | flow | fixed | Restart of `---` on 7 July, three days |
| `WV-` | SWAN | flow | fixed | Restart of `W--` on 7 July, three days |
| `WV-`ˢ | SWAN | flow and SWAN | fixed | Restart of `W--` on 7 July, three days |
| `--M`, `W-M` | as above | no | mobile, original silt | Nine days from 1 July |
| `-VM`, `WVM` | as above | flow | mobile, original silt | Restart of the bare member on 7 July, three days |
| Mobile-bed arm under the deposition and erosion sets | as above | flow, or flow and SWAN in the wave-coupled vegetated members | mobile | As the corresponding members |

The whole factorial was run from the stratified start and repeated from the
uniform start. Discretisation tests (resolution 15 to 120 m on a quadtree mesh
family, 5 to 40 layers, `CFLMax = 0.5`, `autoTimestep = 5`) were run on the
uncoupled fixed-bed member without canopy.

## Observations and scoring

| Item | Value |
|---|---|
| Water-level stations in the lagoon | AltaVilaEst (12.4517° E, 37.8918° N), BocaNord (12.4572, 37.9053), BocaSud (12.4497, 37.8422), ten-minute record |
| Offshore gauge | Marettimo, model cell at 12.0753° E, 37.9747° N with bed level below −0.3 m |
| Water-level metrics | Raw RMSE, bias and anomaly RMSE (RMSE² = bias² + RMSE_anom²), correlation, ratio of standard deviations |
| Drifters | 35 GPS drifters over twelve deployments, 0.4 to 7.2 h each |
| Particle model | OpenDrift, advection step 300 s, positions every 600 s, surface current of the top layer |
| Wind drift factor | 0.02 in every member |
| Lagrangian metrics | Liu and Weisberg (2011) skill score, endpoint separation |
| Suspended matter | Nine Sentinel-2 L2A scenes, 28 June to 13 July 2025, Nechad et al. (2010) at 665 nm on B04 less B11, taken as an upper bound on mineral concentration |

## Settings that differ between members

| Setting | Wave-coupled members | Uncoupled members | Stated in the manuscript |
|---|---|---|---|
| Maximum time step (`dtMax`) | 30 s | 15 s | Yes, Section 3.1 and S1 |
| Drying threshold (`epsHu`) | 1 × 10⁻⁴ m | 1 × 10⁻² m | No |
| Limit on velocity change per step (`maxVelocityDiff`) | none (0) | 5 m/s | No |
| Abort threshold on velocity (`maxVelocity`) | 10 m/s | 25 m/s in `---` and `--M` (10 m/s in the vegetated uncoupled members) | No |

The uncoupled values were introduced on 12 May 2026 (commit `4b00820`), when
the first uncoupled variant aborted on a velocity of 13.3 m/s in an intertidal
cell, and every uncoupled member inspected carries them, including
the members of the discretisation tests. The drying threshold is the one with
a physical effect, since a threshold of 1 cm in place of 0.1 mm removes thin
water films on the intertidal flats from the wet domain earlier in each drying
cycle. The wave contrast of the factorial (`W--` against `---`, `WV-` against
`-V-`) therefore compares members that also differ in the drying threshold,
and the size of that contribution has not been measured. A three-day segment
of `W--` from the 7 July restart with `epsHu = 0.01`, or of `---` with
`epsHu = 1 × 10⁻⁴` if it runs stably, would measure it at about 1.5 h on the
server.

## Statements of the manuscript against the model files

| Manuscript (`manuscript_v2/`) | Model files |
|---|---|
| Horizontal viscosity and diffusivity uniform at 0.1 m²/s (Section S1) | 0.1 m²/s background with a Smagorinsky coefficient of 0.2 added to the viscosity |
| Temperature transported as an active constituent (Sections 3.1 and S1) | Correct, and the heat exchange with the atmosphere follows the excess temperature model with Stanton and Dalton numbers of 0.0013, which the manuscript does not state |
| Drying threshold not mentioned | Differs between coupled and uncoupled members, as above |

## References

Battjes, J.A., Janssen, J.P.F.M. (1978). Energy loss and set-up due to breaking of random waves. *Coastal Engineering Proceedings* 1(16), 569–587.

Dalrymple, R.A., Kirby, J.T., Hwang, P.A. (1984). Wave diffraction due to areas of energy dissipation. *Journal of Waterway, Port, Coastal, and Ocean Engineering* 110, 67–79.

Fredsøe, J. (1984). Turbulent boundary layer in wave–current motion. *Journal of Hydraulic Engineering* 110, 1103–1120.

Liu, Y., Weisberg, R.H. (2011). Evaluation of trajectory modeling in different dynamic regions using normalized cumulative Lagrangian separation. *Journal of Geophysical Research* 116, C09013.

Nechad, B., Ruddick, K.G., Park, Y. (2010). Calibration and validation of a generic multisensor algorithm for mapping of total suspended matter in turbid waters. *Remote Sensing of Environment* 114, 854–866.

Suzuki, T., Zijlema, M., Burger, B., Meijer, M.C., Narayan, S. (2012). Wave dissipation by vegetation with layer schematization in SWAN. *Coastal Engineering* 59, 64–71.

Van Rijn, L.C. (2007). Unified view of sediment transport by currents and waves. I: Initiation of motion, bed roughness, and bed-load transport. *Journal of Hydraulic Engineering* 133, 649–667.
