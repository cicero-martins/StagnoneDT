# Paper 1, two-factor design on a fixed bed and a shorter text

This summary records the changes made after the review meeting of 24 November
2026 on the version of 12 November
([`paper1_review_summary_2026-11-12.md`](paper1_review_summary_2026-11-12.md)).
The manuscript is [`paper1_revised_2026-11-24.pdf`](paper1_revised_2026-11-24.pdf),
built from `manuscript_v3/`, with its Supplementary Material in
[`paper1_supplementary_2026-11-24.pdf`](paper1_supplementary_2026-11-24.pdf).
The text of 12 November remains in `manuscript_v2/`.

## Structure and length

The mobile-bed arm and Section 4.5 on the response of the seagrass classes are
removed. The design is now the two-factor factorial in wave coupling and canopy
on a fixed bed, with the member carrying the canopy also in SWAN kept beside it,
and the title names those two factors.

| Part | 12 November | 24 November |
|---|---|---|
| Body, sections 1 to 6 (words) | 7978 | 4920 |
| Abstract (words) | 250 | 245 |
| Figures in the body | 9 | 7 |
| Tables in the body | 3 | 3 |
| Supplementary sections | 8 | 7 |

The body count excludes floats, mathematics and comments.

| Section | 12 November | 24 November |
|---|---|---|
| 1 Introduction | 761 | 500 |
| 2 Study area | 592 | 380 |
| 3 Data and methods | 2115 | 1568 |
| 4 Results | 2270 | 1124 |
| 5 Discussion | 1725 | 1033 |
| 6 Conclusions | 515 | 334 |

Removed with the mobile bed are the silt parameter sets, the restart segments
that traced the mobile-bed gain, the Sentinel-2 comparison (body Figure 9,
Supplementary Section S5, Tables S2 and S3 and the map figure), the
mobile-bed rows of Tables 2 and 3, Discussion 5.3 and the corresponding
paragraphs of the abstract, conclusions, highlights and cover letter. The
limitations now state that the bed is fixed in every member because no
repeated survey or turbidity record constrains the sediment parameters.

Section 4.5 is removed because the bare members carry a uniform bed roughness
with no class structure, so a comparison of velocities by seagrass class
between bare and vegetated members has no counterpart on the bare side. The
one result of that section that bears on the wave model, the reduction of
significant wave height over the meadow to a median of 0.36 when the canopy
enters SWAN, moves to Section 4.3.

One number changes with the removal. Under the uniform start the bare members
lose 0.080 and 0.092 in skill, where the earlier range of 0.080 to 0.145
included the mobile-bed members. The canopy contrasts under that start remain
+0.195 and +0.188.

## Requests on figures and text

| Request | Change |
|---|---|
| BocaNord and BocaSud | North Mouth and South Mouth in the text, Table 2 and Figures 1, 3, S1 and S7 (station abbreviations NM and SM in Figure 1) |
| Figure S2, grid scale | Scale bar in the lower right corner of both panels, 10 km and 1 km |
| Figure S3 and anchor, negative departure in early 2025 | *See the section below* |
| Figure S4, surface values | Coloured marker at the adopted surface values, 25.8 °C and 37.5, with the value written beside it |
| Figure 2c, "trachytope" | Panel and caption read "bed cover class per flow link" |
| Section 3.6, member code | "whose slots mark wave coupling (W) and seagrass canopy (V), carrying the letter where the factor is active and a dash where it is not", followed by an example: W- is the member forced by water level, wind, atmospheric pressure and evaporation, with wave coupling active and without a canopy. The code has two slots since the bed slot left with the mobile bed |
| Figure 5, deployments 3 and 4 | A panel on the left numbers the release of each of the twelve deployments over the observed tracks of all 35 drifters. All deployments are kept, since deployment 4 is discussed in the text and in Section S6 |
| Figure 6 and Section 4.3 | Rebuilt, see below |
| Figure 7b, "x" on the multipliers | Removed, the axis label giving the ratio |
| Figure S7g, mesh order | 15 m, 30 m, 60 m (the reference, at zero) and the present mesh |

## Section 4.3 and Figure 6

The previous figure gave twelve contrasts of the three-factor design as a column
of intervals, without showing which members were contrasted. The new figure
has three panels:

- (a) an interaction plot of the mean skill of the four members, canopy on the
  horizontal axis and one line per wave treatment, so that the rise from bare
  bed to canopy is the canopy effect, the gap between lines is the wave effect
  and parallel lines mean no interaction, with the canopy-in-SWAN member beside
  the wave-coupled canopy member;
- (b) the seven single-factor contrasts with their bootstrap intervals;
- (c) the canopy contrast by deployment, with the number of drifters in each.

The contrast and its interval are now defined in Section 3.5. A contrast is the
mean over the 35 drifters of the paired difference in skill between two members
that differ in one factor alone, and the interval is the 95% percentile
bootstrap interval of that mean, from 4000 resamples of the 35 differences.
The phrase "4000 paired resamples" of the earlier text is replaced, since what
is paired is the difference, not the resampling. The interval endpoints differ
from those of 12 November by at most 0.001, which is the Monte Carlo
variability of 4000 resamples with a different random sequence. No point
estimate changes.

| Contrast | Mean | 95% CI | Drifters better |
|---|---|---|---|
| Canopy, no waves | +0.120 | +0.061 to +0.180 | 25 of 35 |
| Canopy, waves | +0.114 | +0.057 to +0.169 | 27 |
| Canopy, waves, canopy in SWAN | +0.137 | +0.084 to +0.194 | 27 |
| Waves, bare | −0.022 | −0.044 to −0.002 | 14 |
| Waves, canopy | −0.028 | −0.040 to −0.017 | 10 |
| Waves, canopy in SWAN | −0.005 | −0.011 to −0.001 | 13 |
| Canopy in SWAN, waves and canopy | +0.023 | +0.014 to +0.031 | 26 |

## Figure S3 and the Marettimo anchor

The gauge record was downloaded for 2023 and 2024, in which it reports every
15 s. The analysis-forecast product used for the anchor starts in November
2024, so the earlier record was compared with the MED reanalysis
(`cmems_mod_med_phy-ssh_my_4.2km_P1D-m`), shifted by +0.060 m, the mean
difference between the two products over the 385 days on which both exist
(standard deviation 0.041 m). Script `analyse_marettimo_anchor_long.py`.

| Period | Gauge minus model, monthly means |
|---|---|
| January to July 2023 | −0.16 to +0.28 m |
| August and September 2023 | Sensor fault, values held at −1.000 m in 13% and 34% of the samples, and a change of level on recovery |
| October 2023 to 1 October 2024 | +0.29 m |
| 2 October 2024 to 10 February 2025 | +0.41 m, then +0.34 m from December, after an intervention on the instrument on 1 October 2024 |
| 11 February 2025 to 19 January 2026 | +0.46 m, trend +0.036 m per year, after a transition of about three weeks |

The difference holds at a succession of levels rather than drifting, and
January and February 2025 belong mainly to the level that preceded the change
of February 2025. The same months of 2024 lie 0.03 and 0.05 m below their own
level, so a winter component of a few centimetres is possible. A longer
averaging period would mix levels of a gauge whose datum has not been held.
The anchor used, +0.449 m over the year that contains the simulation, entered
the forcing of every member. Confined to the last level it would be +0.461 m
(from 11 February 2025) or +0.464 m (from 1 March 2025, the gauge having no
record after 19 January 2026), and over the simulated window the difference is
+0.469 m. The full record is in
[`marettimo_gauge_record_2023_2026.md`](marettimo_gauge_record_2023_2026.md).

Over the year of the anchor, the gauge was also compared with the three lagoon
gauges, which record from 12 April 2025
(`check_marettimo_vs_lagoon_gauges.py`). Each lagoon gauge has its own local
datum, so a steady difference indicates that neither instrument moved.

| Marettimo minus | Days | Trend (m per year) | Std of monthly means (m) |
|---|---|---|---|
| North Mouth | 279 | +0.036 | 0.025 |
| South Mouth | 283 | −0.015 | 0.025 |
| AltaVilaEst | 281 | −0.043 | 0.027 |

No step appears and the trends differ in sign, so Marettimo held its datum
from April 2025 to January 2026, the period that contains the simulation. The
change of February 2025 precedes the lagoon records and remains without an
independent check.

In the manuscript, Figure S3 shows the difference from March 2025, January
and February being left out of the plot as requested, while the anchor line
remains the mean over all 384 days, and Section S3
states that the record before 2025 was not used because of the fault of 2023
and the changes of level that follow interventions on the instrument, gives
the comparison with the lagoon gauges, and bounds the anchor by the values
over parts of 2025, +0.449 to +0.464 m, and over the simulated window,
+0.469 m, all within the residual of 0.07 m. The full record stays in the
document above rather than in the Supplementary Material. The word "seasonal"
leaves the residual of Section 3.3, since the residual is not shown to be
seasonal.

## Figure S2

Panel (b) drew every line of the inner SWAN grid over the lagoon window, which
cut the grid and filled the lagoon with lines. The figure now has three panels:
(a) the whole domain as before, (b) the whole inner grid at every fifth line,
and (c) the North Mouth with every inner line over the faces of the flow mesh,
where the two resolutions can be compared cell by cell. Water faces are drawn
in pale blue, land in white.

## Other corrections

- The restart control of Section S6 is the fixed-bed segment without waves,
  whose skill (0.540 against 0.539) and anomaly RMSE at AltaVilaEst (0.0508 m
  against 0.0510 m) match the continuous member, in place of a segment of the
  mobile-bed member.
- The nudging sentence of Section 3.3 no longer says that the relaxation leaves
  the lagoon free-running. It refers to Section S3, which quantifies the
  relaxation inside the lagoon.
- The bed shear stress of the equivalent-roughness representation, 0.043 Pa,
  is now attributed to a diagnostic run with the trachytope formulation of
  Baptist et al. (2007), which was not introduced in the earlier text.

## Scripts

| Figure | Script |
|---|---|
| 3, 4, 5, 7 | `plot_water_level_stations.py`, `plot_lagrangian_results.py`, `plot_drifter_trajectories_paper1.py`, `plot_layer_profile_lagoon.py`, with `STAGNONE_ENSEMBLE=ic3d STAGNONE_BED=fixed` |
| 6 | `plot_attribution_2x2.py` (new), which also writes `data/processed/attribution_2x2_ic3d.csv` |
| 1, 2 | `plot_study_area_paper1.py`, `plot_seagrass_classification_paper1.py` |
| S1–S7 | `plot_supplementary_figures.py` |
