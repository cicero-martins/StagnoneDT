# Paper 1, canopy in the wave model, silt parameters and a satellite constraint on suspended sediment

This summary records the changes made to the manuscript after the version of
27 October ([`paper1_review_summary_2026-10-27.md`](paper1_review_summary_2026-10-27.md)).
The manuscript is [`paper1_revised_2026-11-02.pdf`](paper1_revised_2026-11-02.pdf),
built from `manuscript_v2/`, with its Supplementary Material in
[`paper1_supplementary_2026-11-02.pdf`](paper1_supplementary_2026-11-02.pdf).
Three sets of runs completed between 30 October and 1 November and answer two
limitations that the previous version stated, the canopy acting on the flow but
not on the waves, and the uncalibrated mobile bed. One of them changes a
mechanism the previous version asserted, and that point needs a decision before
submission.

## Runs added

| Set | Members | Purpose |
|---|---|---|
| Canopy in the wave model | `WV-` repeated with the canopy also in SWAN, coded `WV-`ˢ, three-day segment from the same 7 July restart | Effect of wave dissipation by the meadow on transport |
| Silt parameter sets | The eight mobile-bed members under a deposition set (critical shear stress for sedimentation 1000 N/m² in place of 0.1) and an erosion set (the same with critical shear stress for erosion 0.2 in place of 0.1 N/m² and erosion parameter 3 × 10⁻⁵ in place of 10⁻⁴ kg/m²/s); vegetated wave-coupled members with the canopy in SWAN, and the erosion set also with the canopy in the flow alone | A mobile-bed arm whose suspended load is plausible |
| Sentinel-2 retrieval | Nine L2A scenes of 28 June to 13 July 2025, algorithm of Nechad et al. (2010) at 665 nm on the reflectance of B04 less B11 | An observation of suspended sediment, which the previous version lacked |

The canopy enters SWAN through the vegetation dissipation of Dalrymple et al.
(1984) in the implementation of Suzuki et al. (2012), with the stem density,
height (0.34 m), diameter (8.6 mm) and drag coefficient (0.8) of the flow model
averaged onto the inner grid, so no parameter was added. The D-Waves interface
of this release needed three adjustments to pass it to SWAN, described in
Section S2. In a three-day test, significant wave height over the vegetated
points fell to a median of 0.36 of its bare-bed value.

The silt sets were chosen by three-day runs against a target of 1 to 20 mg/l of
silt in the lagoon, with no reference to the drifters or the gauges. The sweep
is Table S2.

## Results

### Canopy in the wave model

| Quantity, 35 drifters | Canopy in the flow only (factorial) | Canopy also in SWAN |
|---|---|---|
| Liu–Weisberg skill of the wave-coupled vegetated member | 0.711 | 0.734 (+0.023, CI +0.014 to +0.032, 26 of 35 better) |
| Canopy contrast with waves | +0.114 (CI +0.056 to +0.170) | +0.137 (CI +0.081 to +0.190) |
| Wave contrast under the canopy | −0.028 (CI −0.040 to −0.017) | −0.005 (CI −0.011 to −0.001) |
| Interaction of waves and canopy | −0.006 | +0.017 (CI −0.001 to +0.037) |
| Anomaly RMSE at AltaVilaEst | 0.021 m, r 0.95 | 0.026 m, r 0.94 |
| Anomaly RMSE at BocaNord | 0.031 m | 0.038 m |

Most of the wave penalty under the canopy came from a wave field computed over
a bare bed, and the canopy contrast with waves grows. The canopy signature at
the interior gauge holds, and at the northern inlet the anomaly RMSE returns to
the value of the uncoupled members.

### Mobile-bed arm under the three silt sets

| Member | Silt set | Canopy | Liu–Weisberg | Anomaly RMSE AltaVilaEst (m) | Surface silt 7 July, median / p95 (mg/l) | 8 July |
|---|---|---|---|---|---|---|
| `W-M` | original | none | 0.708 | 0.040 | 350 / 8318 | 126 / 13 169 |
| | deposition | none | 0.686 | 0.039 | 48 / 365 | 8.9 / 501 |
| | erosion | none | 0.688 | 0.046 | 4.2 / 54 | 0.1 / 68 |
| `WVM` | original | flow | 0.718 | 0.024 | 315 / 13 717 | 89 / 19 464 |
| | erosion | flow | 0.716 | 0.025 | 3.4 / 58 | 0.1 / 88 |
| | deposition | flow and waves | 0.741 | 0.034 | 2.0 / 124 | 0.0 / 52 |
| | erosion | flow and waves | 0.739 | 0.030 | 0.0 / 12 | 0.0 / 5.1 |
| Sentinel-2 | | | | | 5.7 / 16 | 3.0 / 12 |

Over the lagoon the retrieved median stays between 1.9 and 5.7 mg/l and the
95th percentile between 9 and 18 mg/l over the sixteen days, the scenes of 7 to
10 July exceeding the earlier scenes of the same orbit by at most 2 mg/l. The
original parameters exceed the observed 95th percentile by a factor of 500 to
1600 from 5 July. The erosion set brings the median to the observed range and
leaves the 95th percentile three to eight times above it, and the erosion set
with the canopy in SWAN is the one member inside the observation. The
uncoupled mobile-bed members reproduce their fixed-bed counterparts exactly
under both sets. The retrieval includes organic particles and the bright
bottom, so it bounds the mineral concentration from above. The full method is
in [`sentinel2_suspended_matter.md`](sentinel2_suspended_matter.md).

## Source of the bare mobile-bed gain

The previous version attributed the skill of the bare wave-coupled mobile-bed
member, 0.708 against 0.597 on the fixed bed, to the bathymetry reshaped by six
days of implausible erosion. The evidence was a pair of segments restarted on
7 July, 0.710 with the bed updated and 0.707 with the bed held. Under the
erosion set the same member changes the lagoon bed over 2 to 10 July by a
median of 0.8 mm and a 95th percentile of 28 mm, and still scores 0.688, which
is 0.091 (CI +0.041 to +0.140) above `W--`, with 28 of 35 drifters better.
The held segment kept the sediment module active with `BedUpd = false`, so it
did not separate the reshaped bathymetry from the presence of the module under
waves. Without waves the mobile bed reproduces the fixed bed to the third
decimal, so whatever produces the gain needs waves and a bare bed, and with the
canopy the bed contrast is +0.005 to +0.007.

The manuscript now states that the gain is not produced by sediment transport
in the drifter window and that its source is not established. It keeps the
argument of Section 5.3, which rests on the agreement in skill being reached
through a flow unlike the canopy flow (surface-to-bed speed ratio 2.17 against
5.13) and on the interior gauge separating the bare from the vegetated members
under all three silt sets. A segment of `W--` with the sediment module
switched off, started from the 7 July bed of the erosion-set member, is the
test that would separate the two explanations. It takes about 1.5 h on the
server.

## Text changed

| Section | Change |
|---|---|
| Abstract | Wave contrast under the canopy with the canopy in SWAN, −0.005; mobile-bed sentence states the suspended load against Sentinel-2 in place of the reshaped bathymetry. 250 words |
| 3.2 | One paragraph on the canopy in SWAN, details in Section S2 |
| 3.3 | Corrected source of the boundary water level (below) |
| 3.5 | One paragraph on the Sentinel-2 retrieval, details in Section S5 |
| 3.6 | `WV-`ˢ and the two silt sets defined |
| 4.1 | Water level of `WV-`ˢ |
| 4.2 | `WV-`ˢ added to Table 3 |
| 4.3 | Contrasts with the canopy in SWAN |
| 4.5 | Wave height over the meadow with the canopy in SWAN |
| 4.6 | Held-bed segment qualified; silt sets; Sentinel-2 comparison, new Figure 9 |
| 5.3 | Title now "Bare-bed skill under a mobile bed"; mechanism of the gain stated as not established |
| 5.4 | Limitations on wave dissipation and on bed mobility rewritten with the new runs |
| 6 | Canopy-in-SWAN contrasts; mobile-bed compensation restated; bed shear stress factor corrected |
| Highlights, cover letter | Mobile-bed statement restated as above |
| Supplementary S2, S5 | Canopy in SWAN and its adjustments; sweep (Table S2), Sentinel-2 method and maps (Figure S6), arm table (Table S3) |

The body counts 7917 words against the limit of 8000, and the main text keeps
three tables, the arm table having gone to the Supplementary Material.

## Statements corrected against the model files

| As in the version of 27 October | The model |
|---|---|
| Boundary forced with the CMEMS physical reanalysis | Water level from the analysis and forecast product (`cmems_mod_med_phy-ssh_anfc_4.2km_PT15M-i`), whose sea surface height carries the tide; salinity, temperature and velocity from the reanalysis |
| Conclusions: bed shear stress over the meadow lowered by a factor of 14 | Factor of 11 in the stratified ensemble (0.028 to 0.0026 Pa), as Section 4.4 already stated; 14 was the value from the uniform start |

## Decisions needed

| Item | Options |
|---|---|
| Place of the canopy in SWAN | (a) as now, one added member beside the factorial, with the profile and class diagnostics of Sections 4.4 and 4.5 not repeated for it; (b) replace `WV-` by `WV-`ˢ in the factorial, which requires the map-based diagnostics from the server and a `WVM` with the canopy in SWAN under the original silt parameters, about 1.5 h each |
| Source of the bare mobile-bed gain | Run the segment with the sediment module off on the 7 July bed of the erosion-set member before submission, or submit with the mechanism stated as open |
| Silt set of the arm | Keep the original parameters as the arm of record, with the two sets as sensitivity (as now), or make the erosion set with the canopy in SWAN the arm of record, which is the only member inside the satellite bound but carries tuned erosion parameters |
| Sentinel-2 as an observation | Kept as a bound on the mobile-bed arm only, or also as a fourth observation type in the framing of the study |

## Open items carried forward

| Item | State |
|---|---|
| Author order, affiliations, CRediT roles | Require the agreement of every author |
| Bed shear stress and canopy reconfiguration from the stratified start | Done in the version of 27 October (0.028, 0.0026 and 0.043 Pa; velocity ratio 1.030 to 0.842) |
| Reproducibility of the canopy in SWAN | The vegetation map builder and the wrapper that inserts the formulation selector are scripts outside version control (`scripts/_morph_sweep_swanveg.py`, `scripts/_swan_vegfix/run_dimr.sh`); to be added under tracked names before the data deposit |
| Research data (ECSS Option C) | Repository deposit and data availability statement still to be decided |
| Language editing, graphical abstract, funding identifier | Not yet done |

## References

Dalrymple, R.A., Kirby, J.T., Hwang, P.A. (1984). Wave diffraction due to areas of energy dissipation. *Journal of Waterway, Port, Coastal, and Ocean Engineering* 110, 67–79.

Nechad, B., Ruddick, K.G., Park, Y. (2010). Calibration and validation of a generic multisensor algorithm for mapping of total suspended matter in turbid waters. *Remote Sensing of Environment* 114, 854–866.

Suzuki, T., Zijlema, M., Burger, B., Meijer, M.C., Narayan, S. (2012). Wave dissipation by vegetation with layer schematization in SWAN. *Coastal Engineering* 59, 64–71.
