# Paper 1, source of the bare mobile-bed gain, canopy bending and settings read from the model files

This summary records the changes made to the manuscript after the version of
2 November ([`paper1_review_summary_2026-11-02.md`](paper1_review_summary_2026-11-02.md)).
The manuscript is [`paper1_revised_2026-11-12.pdf`](paper1_revised_2026-11-12.pdf),
built from `manuscript_v2/`, with its Supplementary Material in
[`paper1_supplementary_2026-11-12.pdf`](paper1_supplementary_2026-11-12.pdf).
The four decisions left open on 2 November were settled on the option of least
cost, and the one that called for a run was answered by it. Reading the input
files of the members against the text, recorded in
[`model_configuration_summary.md`](model_configuration_summary.md), found
settings that the manuscript did not state, and one of them, the relaxation of
salinity toward the CMEMS fields, was tested by a further run. The abstract,
highlights and cover letter are those of 2 November.

## Decisions taken

| Item | Decision |
|---|---|
| Place of the canopy in SWAN | One added member, `WV-`ˢ, beside the factorial, with the profile and class diagnostics of Sections 4.4 and 4.5 not repeated for it |
| Source of the bare mobile-bed gain | Segment with the sediment module switched off run before submission (next section) |
| Silt set of the arm | Original parameters as the arm of record, the deposition and erosion sets as sensitivity |
| Sentinel-2 | A bound on the suspended load of the mobile-bed arm, not a fourth observation type |

## Source of the bare mobile-bed gain

The bare wave-coupled member under the erosion set was restarted on 7 July with
the sediment module switched off and the bed of that date imposed as a fixed
bed. The solver reads no bed from a restart file when the module is off and
ignores a bed level in the initial fields at the bed level type of these
members, so the bed was written into the face elevations of the partition grid
files.

| Segment, 35 drifters | Liu–Weisberg skill | Difference |
|---|---|---|
| `W--`, fixed bed | 0.597 | |
| `W-M`, erosion set, full member | 0.688 | +0.091 (CI +0.041 to +0.140) over `W--` |
| `W-M`, erosion set, module off on the 7 July bed | 0.689 | +0.092 (CI +0.045 to +0.138) over `W--`, +0.001 (CI −0.003 to +0.005) from the full member |

The gain is carried by the bed and not by sediment transport or by the module.
Inside the lagoon that bed departs from the fixed bed by a median of 0.2 mm and
a 95th percentile of 7 mm, and the change concentrates at the northern inlet,
with deposition up to 0.62 m and a mean of 7.6 cm within 300 m of the BocaNord
gauge. On that bed the interior gauge also improves (correlation 0.79 to 0.83,
bias +0.085 to +0.056 m). Section 4.6 reports the segment, Section 5.3 places
the gain in a deposit at the northern inlet that no survey constrains, and the
conclusions follow it in place of the open mechanism of 2 November.

## Canopy bending

Under the vegetation module of the solver a leaf density of zero holds the
canopy rigid at its full height, with the stem density unchanged. The pair of
runs at 900 and 1020 kg/m³ that Section 5.4 quoted (velocity ratio 1.030 in
the slowest quintile to 0.842 in the fastest 5%) carried the stem fields built
from leaf length, with canopy heights up to 1.0 m and a stem density 2.2 times
that of the ensemble, and so did not describe the ensemble canopy. Three
one-day runs cloned from the vegetated member without waves, restarted from
the stratified state of 8 July and differing only in leaf density, replace
them.

| Quantity, depth-averaged speed over the meadow | Value |
|---|---|
| 900 kg/m³ against rigid canopy, four faster quintiles | 1.08 |
| 900 kg/m³ against rigid canopy, slowest quintile | 1.13 |
| 900 against 1020 kg/m³, slowest quintile | 0.868 |
| 900 against 1020 kg/m³, fastest quintile | 0.847 |
| 900 against 1020 kg/m³, fastest 5% | 0.802 |

The ratio departs from unity at the lowest speeds because the water over the
meadow is close to 1028 kg/m³, which leaves the denser leaf about a sixteenth
of the buoyancy of the lighter one. Section 3.4 now states the bending model
(drag moment about the leaf base against the buoyancy moment, drag reduced to
the height times the cosine of the bending angle, constant drag coefficient).

The canopy height of 0.40 m is justified in Section S4 as the thickness of the
deflected canopy, while the solver bends the leaves further at 900 kg/m³. A
rigid control of the vegetated member without waves, from the same restart,
scores 0.739 as the bending member does (endpoint separation 331 m against
327 m), with the anomaly RMSE of water level within 0.1 mm at the inlet gauges
and 2.4 mm higher at AltaVilaEst, so the added deflection does not alter the
skill. Section S4 reports the control.

## Settings stated against the model files

| Setting in the model | Where stated |
|---|---|
| Smagorinsky term with coefficient 0.2 added to the background horizontal viscosity of 0.1 m²/s | S1 |
| Excess temperature heat model, Stanton and Dalton numbers 0.0013, Secchi depth 2 m | S1 |
| Drying threshold of 0.01 m in the members without wave coupling and 10⁻⁴ m in the coupled ones, so the wave contrasts also carry this difference, unmeasured and confined to the intertidal flats | S1 |
| One particle per drifter, fourth-order Runge–Kutta, no horizontal diffusion; the diffusivity key set in the scripts is accepted and not applied by OpenDrift 1.14, so all published skill is without diffusion | 3.5 |
| Relaxation of salinity and temperature toward the CMEMS fields of the start date with a time scale of 10 days over the whole domain, the lagoon included | S1, S3 |

The relaxation lowers the mean salinity of the lagoon from 42 to 39.4 over the
window, against the hypersaline gradient that S1 cites as a baroclinic term. A
run of the vegetated member without waves with the relaxation removed inside
the lagoon ended the window at 41.2.

| Quantity over the lagoon, 2 to 10 July | Reference | Relaxation removed in the lagoon |
|---|---|---|
| Mean salinity at the end of the window | 39.4 | 41.2 |
| RMS surface speed | 0.04 m/s | |
| RMS difference in surface current from the reference | | 0.003 m/s (8%) |

The circulation evaluated in the paper is therefore nearly unchanged by the
relaxation over nine days, and S3 states the relaxation and this test. Over
the seasonal runs of the renewal study the relaxation would fix the lagoon
salinity near that of the sea, and those runs confine it to the sea
([`lagoon_renewal.md`](lagoon_renewal.md), Section 5).

## Text changed

| Section | Change |
|---|---|
| 2 | Station description moved here from 3.5, AltaVilaEst placed in the northern basin |
| 3.4 | Bending model of the canopy |
| 3.5 | Deterministic advection of the drifters |
| 3.6 | Segment with the sediment module off on the 7 July bed |
| 4.6 | Result of that segment and the inlet deposit; held-bed caveat and repeated bed figures removed |
| 5.3 | Gain placed in the bed at the northern inlet |
| 5.4 | Limitations shortened; reconfiguration paragraph rewritten on the three runs above |
| 6 | Mobile-bed sentence names the deposit at the northern inlet |
| S1 | Smagorinsky term, heat model, drying threshold, reference to the relaxation |
| S3 | Relaxation and the run without it in the lagoon |
| S4 | Rigid canopy control |

The body counts 7978 words against the limit of 8000, after a cut from 8450
words that the sediment-off segment allowed by making the held-bed caveat and
the repeated bed figures redundant. The manuscript has 34 pages and the
Supplementary Material 17.

## Open items carried forward

| Item | State |
|---|---|
| Author order, affiliations, CRediT roles | Require the agreement of every author |
| Reproducibility of the canopy in SWAN | Vegetation map builder and SWAN wrapper still outside version control, to be added under tracked names before the data deposit |
| Research data (ECSS Option C) | Repository deposit and data availability statement still to be decided |
| Direction of the exchange between the inlets | The model carries water from the northern to the southern inlet, which the 2017 salinity of Mancuso et al. (2023) and the BocaNord and BocaSud records may contradict; the paper makes no statement on it, and it is examined in the renewal study |
| Language editing, graphical abstract, funding identifier | Not yet done |

## References

Mancuso, F.P., et al. (2023). Life on the edge: adaptations of *Posidonia oceanica* to hypersaline conditions in a Mediterranean lagoon system. *Environmental and Experimental Botany* 210, 105320.
