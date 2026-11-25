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
| October 2023 to December 2024 | +0.24 to +0.42 m |
| 2025, the anchor year | +0.36 and +0.37 m in January and February, +0.42 to +0.49 m afterwards |

From October 2023 to January 2026 the difference rises by 0.11 m per year, and
January and February 2025 lie on that trend. The low values of early 2025 are
therefore not a winter departure but the low end of a drift of the gauge
datum. A longer averaging period would mix levels of a gauge whose datum has
not been held, so the anchor remains the mean over the year that contains the
simulation, +0.449 m, which also entered the forcing of every member. Over
the simulated window the difference is +0.469 m, 0.020 m above the anchor, and
excluding January and February 2025 would give +0.464 m.

Figure S3 now has two panels, (a) the 384 days of the anchor as before and (b)
the reanalysis-based difference from October 2023 to January 2026 with its
trend, and Section S3 states the comparison, the fault and the drift.

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
