# Sediment and canopy parameters: what is wrong, and what the literature supports

Written 2026-08-26, after the corrected trachytope `.arl` made the wave-coupled
mobile-bed member stop integrating. The failure turned out to be diagnostic
rather than a nuisance: it exposed a calibration that only survived because 94%
of the seagrass map was never being applied.

There are no in-situ sediment measurements for the Stagnone, so every value
below is either a published measurement from this lagoon or a published value
from the closest analogous system. Nothing here is tuned to make a run finish.

## What the corrected roughness revealed

With the meadow reaching 88-90% of the vegetated links instead of 5.5%, lagoon
bed shear stress at a matched instant went from 0.75 to 1.76 N/m² in the mean
and 11.0 to 27.0 N/m² at p99. Suspended concentration reached 379 kg/m³ in
shallow, fully vegetated cells. The wave-coupled mobile-bed member then aborted
on `MinTimestepBreak`, twice, at 0.087 s.

Seven variants localised the cause. Numerics did nothing: `CFLMax` 0.7 to 0.5,
`dtMax` 30 to 10 s and `TrtMnH` 0.3 m all failed identically. Disabling
sediment (`Sedimentmodelnr = 0`) or deferring morphology (`MorStt`) both ran
clean at the same mean timestep as the control, 8.45 s. Freezing the bed
(`BedUpd = false`) still failed, so it is the transport computation and not the
bed update. Withholding sediment under the canopy cured the concentration
blow-up, taking the maximum from 222 to 22.8 kg/m³, better than the old
control's 28.9, and the run still aborted at 0.085 s.

So the driving stress, not the sediment supply, is the binding constraint.

## Four problems, largest first

### 1. The sand transport formula, and where it gets its roughness

`TraFrm = -2` is **Van Rijn (2007) / TRANSPOR2004**. Read that from the `.dia`,
which prints both the name and the code:

```
Formula name           : Van Rijn (2007): TRANSPOR2004
Transport formula used : -2
```

The negative codes do not follow the ordering one might guess, and an earlier
draft of this file asserted that -2 was Engelund-Hansen, which is wrong. `-1` is
Van Rijn (1993). Always read the name back rather than trusting the number.

What actually matters is the next line in the same block:

```
Standard option: Rc from Flow, Rw=RWAVE*0.025 : 1
```

That is `IopKCW = 1`: the current-related roughness the transport formula uses
is taken **from the flow module**, which with trachytopes active is the canopy
roughness. So the meadow's form drag enters the transport formula directly.
Setting `IopKCW = 0` substitutes the given `RDC` and `RDW` instead, decoupling
the transport roughness from the flow roughness. That is the Zhu et al.
principle expressed through a standard Delft3D keyword.

Measured, six simulated hours off the same original with the corrected `.arl`:

| sand formula | result | lagoon max \|Δbl\| | max conc |
|---|---|---|---|
| Van Rijn (2007), `TraFrm = -2` | aborts, 16 breaks | **20.2 m** in 45 min | 15.7 kg/m³ |
| Van Rijn (1993), `TraFrm = -1` | completes, dt 8.45 s | 0.47 m | 6.5 kg/m³ |

For reference the old `.arl` control gives 0.40 m and 4.0 kg/m³, so Van Rijn
(1993) with the full meadow lands close to the previous behaviour while Van Rijn
(2007) does not. Why the two differ under the same `IopKCW` is not established
here; TRANSPOR2004's reference-concentration formulation is the obvious place to
look, but that is a hypothesis, not a measurement.

The binary also offers Van Rijn (1984), Soulsby / Van Rijn, Van der A et al.
(2013) SANTOSS, Bijker (1971), Meyer-Peter-Müller (1948), Ashida-Michiue (1974)
and Engelund-Hansen (1967).

### 2. Cohesive erosion is driven by the total stress, canopy drag included

FM's `taus` is the total bed shear stress, and with trachytopes active it
carries the vegetation form drag. Feeding that to Partheniades-Krone erodes the
bed with a stress that in reality is exerted on the plants, which is the
opposite of what a Posidonia meadow does.

**The capability to fix this is present and switched off.** The binary contains
`compbsskin.f90`, `compbsskin_module_mp_compbsskin_`, `m_fm_erosed_mp_bsskin_`
and the string `Skin friction Soulsby 2004`, with ripple and dune roughness
heights (`ksr`, `ksd`, `rksr`, `rksd`). That is the `BsSkin` keyword in the
`.mor` file.

**It goes in the `.sed`, not the `.mor`.** `strings` puts `BsSkin` next to
`KsSand`, `KsSilt`, `PmCrit` and `SC_mudfactor`, which is the sand-mud
interaction group under `[SedimentOverall]`. Placed in the `.mor` it is read by
nothing: FM's morphological echo never mentions it, no error is raised, and the
run comes out numerically identical to one without it. Only the identical
numbers gave it away. Placed correctly, the `.dia` confirms it:

```
Skin friction Soulsby 2004
Kssilt  :  0.000010
Kssand  :  0.000050
```

And it does **not** rescue Van Rijn (2007). Accepted and active, the run still
aborts on 16 breaks, and the bed-change warnings rise from 73 to 337. Whatever
the sand-mud skin friction does here, it is not the binding constraint.

### 3. `TcrSed = TcrEro = 0.1 N/m²`, and no flocculation

Equal thresholds leave the mud with no quiescent band: it is always either
eroding or depositing. Separately, `SalMax = 0` with `WS0 = WSM = 5e-4 m/s`
disables salinity-dependent settling in a lagoon that runs 38 to 51 psu
(Mancuso 2023 Table 2).

Note the ordering constraint: a threshold only means something relative to the
stress that drives it. Changing `TcrEro` before fixing items 1 and 2 is tuning
blind.

### 4. The canopy parameters are on the rigid side

`trachytopes.ttd` class 3, Posidonia: Baptist formula 153 with h_v = 0.50 m,
mD = 5.0 m⁻¹, C_D = 0.80, C_b = 45. Class 2, Cymodocea: h_v = 0.15 m, mD = 3.2,
C_D = 1.00.

Two anchors exist for this very lagoon:

| source | model | calibrated value | Manning equivalent |
|---|---|---|---|
| Ingrassia et al. 2024 | MIKE21 2DH | Ks = 20 m^⅓/s, uniform over the lagoon | **0.050** |
| De Marchis et al. 2012 | PANORMUS 3D | Posidonia ks = 0.10 m | ≈ 0.026 |
| | | Cymodocea ks = 0.30 m | ≈ 0.032 |
| this model, corrected `.arl` | FM Baptist | measured `mesh2d_cftrt` | **0.081 mean, 0.28 max** |

We sit 1.6× above the value Ingrassia calibrated for the Stagnone and roughly
3× above De Marchis for Posidonia. Ingrassia's is a bulk value for the whole
lagoon rather than per species, so it is a sanity bound rather than a target,
but being above it by that margin is a signal.

The physical reason is that C_D = 0.80 treats Posidonia as rigid cylinders.
Flume measurements of bulk drag on flexible seagrass give much smaller
coefficients, because blades reconfigure and shed drag as velocity rises. Zhu
et al. (2021) use C_D = 0.4 for *Zostera*.

## The closest published analogue

**Zhu, Q., Wiberg, P. L., & Reidenbach, M. A. (2021).** Quantifying seasonal
seagrass effects on flow and sediment dynamics in a back-barrier bay. *JGR
Oceans*, 126, e2020JC016547. https://doi.org/10.1029/2020JC016547

Why it matters here: Delft3D coupled to SWAN, Baptist vegetation module,
seagrass, mean depth ~1.0 m. Almost our configuration. And they solve our exact
problem the way FM allows, obtaining the skin bed shear stress for sediment
transport by subtracting the vegetation drag from the total shear stress.

Their parameters:

| quantity | value |
|---|---|
| transport, sand | Van Rijn et al. (2001) |
| transport, mud | Partheniades-Krone |
| sand d50 | 125 µm |
| mud fraction 1 | 32-64 µm, w_s = 3.6 mm/s |
| mud fraction 2 | < 32 µm, w_s = 0.75 mm/s |
| critical shear, cohesive | **0.03 N/m²** |
| canopy height, summer | 0.4 m |
| stem diameter | 0.4 cm |
| shoot density | 400 shoots/m² |
| C_D flow / wave | 0.4 / 3.0 |

Their cohesive threshold is *lower* than ours precisely because the stress
driving it is the skin stress rather than the total.

## The site-specific canopy source, and the link to RQ9

**Ciraolo, G., Ferreri, G. B., & La Loggia, G. (2006).** Flow resistance of
*Posidonia oceanica* in shallow water. *Journal of Hydraulic Research*, 44(2),
189-202.

Also relevant from the same group: Ciraolo & Ferreri (2007), log velocity
profile and bottom displacement over a very flexible submerged canopy; and
Ciraolo, Ferreri & La Loggia (2008), influence of meadow density on flow
resistance.

The reason C_D = 0.80 is too high is the same reason trachytope formula 156
(Järvelä 2014) exists: flexible blades do not have a constant drag coefficient.
Ciraolo's velocity exponent is what goes into `expchistem` in formula 156. So
the RQ9 experiment is not a separate line of work, it is the physically correct
form of this fix. See [[rq9_ciraolo_state_and_plan]].

Caveat already recorded there: FM's λ is a momentum sink per metre while
Ciraolo's λ is a dimensionless Darcy-Weisbach factor. Only the velocity scaling
transfers; the magnitude still needs anchoring.

## Other sources consulted

**Le Bouteiller, C., & Venditti, J. G. (2015).** Sediment transport and shear
stress partitioning in a vegetated flow. *Water Resources Research*, 51(4).
https://doi.org/10.1002/2014WR015825 — the general theory for splitting total
stress into skin friction and plant form drag, extending the bedform
partitioning framework to vegetation.

**Amos, C. L., et al. (2010).** The erosion rates of cohesive sediments in
Venice lagoon, Italy. *Continental Shelf Research*, 30(8), 859-870.
https://doi.org/10.1016/j.csr.2009.12.001 — in-situ Sea Carousel measurements,
erosion thresholds and first-order erosion rates, with a clear intertidal versus
subtidal difference. **Not yet read in full.** From secondary sources I could
only confirm the qualitative intertidal/subtidal split and a deposition
threshold of 1 Pa attributed to Amos et al. (2004). The τce and erosion-rate
values need the full text before being quoted.

**van Rijn, L. C., & Walstra, D. J. R.** Modelling of sand transport in Delft3D.
https://open.rijkswaterstaat.nl/publish/pages/81574/modelling_of_sand_transport_in_delftd.pdf

**Environmental evolution of the Marsala Sound, Sicily, during the last 6000
years** — modern Stagnone sediments are mainly **muddy sands**, with well-sorted
sand restricted to the Tramontana Channel and the front of southern Punta dello
Stagnone. That supports a two-fraction sand + mud setup like ours, and says the
clean-sand end member belongs to the channel rather than the basin.

**Ingrassia et al. (2024),** MDPI Water — Stagnone hydrodynamic calibration with
spatially variable roughness in MIKE21. See [[ingrassia_2024_vr_calibration]].

**De Marchis et al. (2012),** PANORMUS 3D — Nikuradse roughness heights per
species for the Stagnone. Same memory entry.

## Results so far

Harness: `scripts/test_vr_dens_stability_variants.sh`, six simulated hours off
the `v04AE_vr_dens` original with the corrected `.arl`, roughly two wall minutes
each. The control with the old `.arl` completes at mean dt 8.45 s.

| variant | change | result | mean dt |
|---|---|---|---|
| (baseline) | corrected `.arl` only | aborts, 16 breaks, 73 bed-change | — |
| `cfl` | CFLMax 0.7 → 0.5 | aborts, 16 breaks | — |
| `dtmax` | dtMax 30 → 10 s | aborts, 16 breaks | — |
| `trtmnh` | TrtMnH = 0.3 m | aborts, 16 breaks | — |
| `meadow` | no sediment under the canopy | aborts, but conc 222 → 22.8 kg/m³ | — |
| `nosed` | Sedimentmodelnr = 0 | **completes** | 8.45 s |
| `morstt` | morphology deferred | **completes** | 8.45 s |
| `nobedupd` | BedUpd = false, transport on | aborts | — |
| `bsskin` | BsSkin in the `.mor`, VR2007 | aborts; setting silently ignored | — |
| `bsskin2` | BsSkin in the `.sed`, VR2007 | accepted and active, still aborts, bed-change 73 → 337 | — |
| `iopkcw` | IopKCW = 0 + RDC/RDW, VR2007 | aborts; setting silently ignored | — |
| `vanrijn` | TraFrm -2 → -1 | **completes**, 0 bed-change | 8.45 s |
| `vrbs` | Van Rijn (1993) + BsSkin (`.mor`, ignored) | **completes**, identical to `vanrijn` | 7.38 s |

| `trt154` | trachytope formula 153 → 154 | **completes**, 0 breaks, 0 bed-change, VR2007 kept | 7.38 s |

## The separation is in the trachytope formula, not the sediment module

This is the answer, and it makes the Van Rijn (1993) result a workaround rather
than a fix. From `trtrou.f90`:

```fortran
! 153
ch_icode = 1/sqrt( 1/(cbed*cbed) + (drag*densit*vheigh)/(2*ag) )

! 154
hk       = max(1, depth/vheigh)
ch_icode = cbed + sqrt(ag)/vonkar*log(hk)*sqrt(1 + (drag*densit*vheigh*cbed**2)/(2*ag))
rttfu(nm,1) = rttfu(nm,1) + fraccu*drag*densit/hk*(cbed*cbed)/(ch_icode*ch_icode)
```

**153 lumps** the bed friction and the canopy drag into a single representative
Chézy. `taus` follows from that lumped value, so the canopy drag arrives at the
transport formula as though it were stress on the grains.

**154 separates them.** The bed Chézy stays the bed Chézy and the canopy is
carried as an independent momentum sink, λ, in `rttfu`. That is precisely the
subtraction Zhu et al. describe, available natively.

Formulas 155 and 156 follow 154's pattern, so the RQ9 move to Järvelä inherits
it for free.

### What 154 does, measured

At a matched instant, six simulated hours, corrected `.arl` throughout:

| variant | max conc | mean `taus` | lagoon \|Δbl\| p99 | max | vegetated `cftrt` mean | max |
|---|---|---|---|---|---|---|
| old `.arl`, 153 | 4.00 | 0.748 | 4.99 cm | 39.9 cm | 0.0688 | 0.284 |
| corrected `.arl`, 153 | 15.67 | 1.764 | 4.68 cm | **2017 cm** | 0.0737 | 0.284 |
| corrected `.arl`, 153, VR1993 | 6.46 | 1.136 | 3.38 cm | 47.1 cm | 0.0745 | 0.283 |
| **corrected `.arl`, 154** | **4.03** | **0.626** | 4.57 cm | **36.1 cm** | **0.0257** | **0.028** |

Three things to notice. Bed shear is now *lower* than the old control, which is
the physically right direction: a meadow shelters the bed rather than scouring
it. Bed change is the most conservative of the four. And the bed roughness on
vegetated links collapses to 0.0257 mean, 0.028 max, because the canopy is no
longer inside the Chézy.

That last number lands on an independent, site-specific value: De Marchis et al.
(2012) give Posidonia ks = 0.10 m for the Stagnone, n ≈ 0.026. Nothing was tuned
to reach it.

### What this does not settle

153 is a legitimate Baptist variant, not a bug, so the three `_arlfix` members
that completed are not invalidated — but they ran on 153, and 154 changes the
hydrodynamics, so their water-level and drifter numbers belong to 153. Moving
the ensemble to 154 is a scope decision with a real re-run cost.

Superseded by the above: an earlier reading here concluded that FM offered no
route to a skin stress, on the grounds that `IopKCW`/`RDC`/`RDW` are not read
under `TraFrm = -2` and `BsSkin` acts elsewhere. Both of those observations
hold; the conclusion drawn from them was wrong, because the route is upstream in
the trachytope formula.

Two readings that the tests overturned, recorded because they were wrong in a
way that was easy to believe:

- The Courant limiters (`mesh2d_Numlimdt`) looked like they pointed at specific
  Egadi cells. They do not discriminate: the passing and failing runs have the
  same limiting cells and near-identical totals, 643 / 708 / 622 events.
- `BedUpd = false` still fails, so the bed-change limiter was a symptom. It is
  the transport computation, not the bed update.

## Test order from here

1. `iopkcw` — keep Van Rijn (2007) but set `IopKCW = 0` with `RDC` / `RDW`, so
   the transport roughness stops following the flow roughness. If this works it
   is preferable to falling back to the 1993 formula, because it fixes the
   actual coupling rather than avoiding it.
2. Then `TcrEro` / `TcrSed`, against whatever stress basis wins. A threshold
   only means something relative to the stress that drives it, which is why it
   is not tested earlier.
3. Then `C_D` and `h_v`, preferably already via formula 156.

Related: [[arl_needs_9_decimals_1cm_tolerance]],
[[v04AE_dmorph_validated_but_uncalibrated]], [[dmorph_spatial_restriction]],
[[rq9_ciraolo_state_and_plan]], [[ingrassia_2024_vr_calibration]].
