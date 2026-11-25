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
| Body, sections 1 to 6 (words) | 7978 | 4797 |
| Abstract (words) | 250 | 245 |
| Figures in the body | 9 | 6 |
| Tables in the body | 3 | 5 |
| Supplementary sections | 8 | 7 |

The body count excludes floats, mathematics and comments.

| Section | 12 November | 24 November |
|---|---|---|
| 1 Introduction | 761 | 591 |
| 2 Study area | 592 | 499 |
| 3 Data and methods | 2115 | 1210 |
| 4 Results | 2270 | 991 |
| 5 Discussion | 1725 | 1219 |
| 6 Conclusions | 515 | 287 |

The Introduction states the open problem as what earlier models of the
Stagnone did not represent and gives the objectives in one sentence, and facts
about the basin appear only in the Study Area. Every reference of 12 November
is kept. Data and Methods leaves to the Supplementary Material the details it
already gives in full, the body figures float instead of being held in place,
and Results begin on page 10 of the review-format PDF.

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
| Figure 5, deployments 3 and 4 | Five deployments, 1, 2, 5, 9 and 11, with a first panel numbering their releases and a wider extent on deployment 1. The tracks of all five members in all twelve deployments are a new figure in Section S6 |
| Figure 6 and Section 4.3 | Folded into Section 4.2, see below |
| Figure 7b, "x" on the multipliers | Removed, the axis label giving the ratio |
| Figure S7g, mesh order | 15 m, 30 m, 60 m (the reference, at zero) and the present mesh |

## Process attribution, formerly Section 4.3 and Figure 6

The previous figure gave twelve contrasts of the three-factor design as a column
of intervals, without showing which members were contrasted. In a two-factor
design the mean of each contrast is the difference between two member means of
Table 3, so a separate section and figure repeated that table. What the
contrasts add is their uncertainty. Pairing by drifter removes the difficulty a
drifter presents to every member, which spreads skill from 0.34 to 0.96, and
the wave effect of about −0.02 clears zero only in the paired form, the
intervals of the member means overlapping. The contrasts are therefore Table 4
of Section 4.2, named in member codes (`-V` minus `--`, `WV` minus `W-`, and so
on), and the canopy contrast by deployment is a figure in Section S6. The
sensitivity tests of the former Section 4.5 are Table 5.

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
| `-V` minus `--` | +0.120 | +0.061 to +0.180 | 25 of 35 |
| `WV` minus `W-` | +0.114 | +0.057 to +0.169 | 27 |
| `WVs` minus `W-` | +0.137 | +0.084 to +0.194 | 27 |
| `W-` minus `--` | −0.022 | −0.044 to −0.002 | 14 |
| `WV` minus `-V` | −0.028 | −0.040 to −0.017 | 10 |
| `WVs` minus `-V` | −0.005 | −0.011 to −0.001 | 13 |
| `WVs` minus `WV` | +0.023 | +0.014 to +0.031 | 26 |

## Discussion and Conclusions

The Discussion follows four steps: the findings, their context in other
studies, the limitations and the work they leave open. The wave result has its
own subsection, since the canopy in SWAN shows that most of the wave penalty
under the canopy came from a wave field computed over a bare bed, and it is no
longer listed as a limitation. The leaf-density runs, which are results, move to
Section S4. Four references give the context of canopy flow and reconfiguration:
Nepf and Vivoni (2000), Temmerman et al. (2005), Beudin et al. (2017) and Luhar
and Nepf (2011). The work left open is a canopy momentum sink that varies with
the local velocity in the three-dimensional solver, the canopy in both models in
every vegetated member, and a mobile bed once bed change and turbidity are
observed in the lagoon. The Conclusions answer the three objectives with
numbers and close on one quantified statement.

## Citations checked against their sources

Every citing sentence was read against the source PDF, and every DOI against
Crossref ([`paper1_citation_map.md`](paper1_citation_map.md)). Two DOIs
resolved to other papers (Carrasco et al. 2016 and Ciraolo et al. 2006) and
are corrected, as is the first name of Ingrassia et al. (2024). In the text,
the lagoon area is about 20 km² (La Loggia et al. 2004), the 2200 ha of Ciraolo
and De Marchis (2009) being the natural reserve; the tide is given as an
excursion of 0.30 m; Santa Maria lies in the north and the atolls in the
northern sub-basin; wind adds to exchange in lagoons with more than one inlet
(Umgiesser et al. 2014); and Liu and Weisberg (2011) and Révelard et al. (2021)
are no longer cited for the claim that water level constrains transport
weakly, which they do not make. The parameters of *P. oceanica* are described
as coming from flume experiments with artificial plants.

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
| 3 to 6 and the tracks of Section S6 | `plot_water_level_stations.py`, `plot_lagrangian_results.py`, `plot_drifter_trajectories_paper1.py`, `plot_layer_profile_lagoon.py`, with `STAGNONE_ENSEMBLE=ic3d STAGNONE_BED=fixed` |
| Table 4 and the deployment figure of Section S6 | `plot_attribution_2x2.py` (new), which writes `data/processed/attribution_2x2_ic3d.csv` |
| 1, 2 | `plot_study_area_paper1.py`, `plot_seagrass_classification_paper1.py` |
| S1–S7 | `plot_supplementary_figures.py` |
