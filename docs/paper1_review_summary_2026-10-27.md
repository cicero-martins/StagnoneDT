# Paper 1, internal review of Sections 1 to 3.1, and the stratified-start ensemble

This summary records what has been applied to the manuscript of the changes
planned in the response of 13 October
([`paper1_review_response_2026-10-13.pdf`](paper1_review_response_2026-10-13.pdf)),
adjusted to the results of the sensitivity reruns that the grounding of the
numerical choices required. Two of those results, the effect of the initial
condition and the implausible state of the mobile bed under waves, changed the
design of the study, and the eight members were rerun from a stratified start.
The manuscript of this version is
[`paper1_revised_2026-10-27.pdf`](paper1_revised_2026-10-27.pdf), built from
`manuscript_v2/`, with its Supplementary Material in
[`paper1_supplementary_2026-10-27.pdf`](paper1_supplementary_2026-10-27.pdf),
which holds the settings and grounds that Section 3 states in one clause. The version of 20 October, with the ensemble started from a
uniform column, remains in `manuscript/` and in
[`paper1_review_summary_2026-10-20.md`](paper1_review_summary_2026-10-20.md).
The full record of each review item, with the evidence behind it, is in
[`paper1_internal_review.md`](paper1_internal_review.md).

## Observations received

| # | Observation | Planned | Carried out | Where |
|---|---|---|---|---|
| 1 | Co-authorship of Nasello and Maltese | Add both, settle order, affiliation and CRediT roles | Both added. Order Martins Jr., De Marchis, Ciraolo, Nasello, Maltese, also in the highlights and the cover letter. CRediT roles drafted on the pattern of the supervising co-authors, with Methodology for Maltese | Frontmatter, CRediT statement |
| 2 | Lagoon geometry repeated in the Introduction | Remove the figures that Section 2 already carries | Extent, area, inlet geometry and shoot density removed. The sub-metre mean depth and the 75% decline of *P. oceanica* (2003–2024) kept, since they carry the argument | Section 1 |
| 3 | Age of the reference set | Forward-citation search from the older works | Dunic et al. (2021) and Turschwell et al. (2021) beside Waycott et al. (2009), and Mogé et al. (2019) for the partition count. Formulation sources (Booij, Baptist, Kernkamp, Liu and Weisberg) retained as primary | Section 1, bibliography |
| 4 | Panel sizes in Figure 1 | Remove the margin in panel (a) | Panel (a) limits taken from the mesh, and the width ratio computed from the two extents, which equalises the map heights | Figure 1 |
| 5 | Grounds for the numerical choices in Section 3.1 | State the constraint behind each choice, and state that mesh and layer count were not tested | Each choice carries its constraint. Initial condition, mesh, layer count, time-step limit and host were tested. Partition count grounded on cells per partition (Mogé et al., 2019), with the wall time on the server where all members ran | Sections 3.1, 3.3, 3.6, 4.6, 5.4 |

## Changes in the design of the study

The sensitivity tests behind item 5 found two dependences large enough to
change the design, and the eight members were rerun.

| Finding | Evidence | Consequence |
|---|---|---|
| The uniform initial column (24 °C, 37.5 outside the lagoon) degrades the bare members and barely affects the vegetated ones | Bare members 0.080 to 0.145 lower in Liu–Weisberg skill, vegetated members 0.005 to 0.018 lower; mean level 2 to 10 cm higher at the gauges | Ensemble rerun from the CMEMS depth profiles at the start time (25.8 °C and 37.5 at the surface to 16.2 °C and 38.3 below 260 m) |
| With waves, the mobile bed is far outside a plausible state of the basin | Suspended sediment near 9 g/l in the lagoon, bed lowered by 12 cm on average and 4 million m³ lost in nine days; without waves the change is negligible | Attribution made on the four fixed-bed members; the mobile-bed arm kept as a sensitivity test |
| The skill of the bare wave-coupled mobile-bed member (0.708, close to the vegetated members) comes from the bathymetry reshaped by that erosion | Segments restarted on 7 July score 0.710 with the bed updated and 0.707 with the bed held, +0.110 above the fixed-bed member | Discussed in Section 5.3 as a compensation that the interior gauge exposes and the drifters do not |

## Results of the stratified-start ensemble

| Quantity | Fixed bed, the attribution | Uniform start, for comparison |
|---|---|---|
| Liu–Weisberg skill, four members | 0.597 to 0.739 (`-V-` best) | 0.505 to 0.735 |
| Canopy contrast, without and with waves | +0.120 (CI +0.061 to +0.180), +0.114 (CI +0.056 to +0.170) | +0.195, +0.188 |
| Wave contrast, without and with canopy | −0.022, −0.028 | −0.035, −0.042 |
| Interaction of waves and canopy | −0.006 | |
| Anomaly RMSE at AltaVilaEst, bare and vegetated | 0.048–0.054 m and 0.021–0.028 m | 0.045–0.051 m and 0.017–0.027 m |
| Water-level bias at the gauges | −0.051 to +0.085 m | −0.021 to +0.176 m |

The canopy remains the first-order control on transport, with half the
previous magnitude and the same effect under both wave treatments. The
interaction of waves and bed mobility that the previous version reported as a
secondary result is an artefact of the mobile bed.

## Sensitivity to the discretisation and the host

| Test | Configuration | Water level at the gauges | Drifter skill |
|---|---|---|---|
| Horizontal resolution, quadtree meshes in the lagoon, 60, 30, 15 m | uncoupled, fixed bed, no canopy, uniform start, Courant 0.5 | < 1 mm in bias, ≤ 1.5 mm in anomaly RMSE | 0.553 ± 0.004, no monotonic trend; present mesh 0.555 |
| Vertical resolution, 10 and 20 uniform sigma layers | as above, stratified start, time step limited also by vertical fluxes | ≤ 2.4 mm in bias, ≤ 1.6 mm in anomaly RMSE | 0.619 at both, +0.0003 ± 0.0036 |
| Time-step limit by vertical fluxes, 10 layers | as above, uniform start | < 0.3 mm | +0.0007 ± 0.0007 |
| Host and decomposition, 8 partitions on the server against 4 on a second computer | uncoupled member, uniform start, Courant 0.7 (ensemble) | not compared | 0.034 lower on the second computer |
| Same | Courant 0.5 | identical to 0.1 mm | +0.002 ± 0.001 |

## Structure, length and Supplementary Material

The grounding of every numerical choice (item 5) and the sensitivity tests had
brought the body of the text to about 9600 words, against the ECSS limit of
8000. The manuscript was restructured so that the main text keeps what the
reported results need, with the ground of each choice in one clause, and the
full settings and grounds moved to the Supplementary Material.

| Change | Where |
|---|---|
| Introduction rewritten in three parts, context, knowledge gap and plan, following the Elsevier paper-writing guidance; the methodological detail moved to Section 3, and the prior studies presented by the question each addressed, with the open aspects stated as building on them | Section 1 |
| Mesh composition, turbulence and time-step grounds, partitions and run times | Section 3.1 → S1 |
| SWAN settings and their grounds, as a table, and the ground of the stationary mode | Section 3.2 → S2, Table S1 |
| Construction of the Marettimo offset and the wind blending choice | Section 3.3 → S3 |
| Provenance of the canopy parameters and detail of the seagrass classification | Section 3.4 → S4 |
| Density and erodible-thickness settings of the mobile bed | Section 3.6 → S5 |
| Design and results of the discretisation and host tests | Sections 3.6 and 4.6 → S6 |
| Restart control and the detail of deployment 4 | Sections 4.1 and 4.3 → S7 |
| Repetitions removed between Sections 4.5 and 5.4, 5.1 and 1, 5.3 and 4.6, and 6 and 5.3 | Sections 4 to 6 |
| Water level table restored to the eight members at each station | Table 2 |
| Closing sentence of the abstract restricted to an inference for shallow meadows of this kind | Abstract |

Section 3 went from about 3600 to 1700 words and the body of the text from
about 9600 to 7000, counted without captions, tables and equations, and the
manuscript from 38 to 31 pages. The grounds listed under Sections 3.2 to 3.6
below are now given in the Supplementary Material, with one clause each in the
main text.

## Points arising from the journal criteria

| # | Criterion | Carried out |
|---|---|---|
| A | Four tables against the limit of three (ECSS Guide for Authors) | The table of ensemble members replaced by the three-slot member code defined in Section 3.6; three tables |
| B | Limitations in the abstract (Elsevier reviewer guidance) | Single nine-day window, stratified initial state and the compensation in the uncalibrated mobile bed stated, in an abstract of 250 words written in impersonal construction, closing on a scoped inference rather than a general prescription |
| C | Introduction closing on objectives | Roadmap paragraph replaced by a short plan and three objectives, with no results and no methodological detail |
| D | Generality of the claims (local interest exclusion) | Introduction states that the second and third objectives are not specific to this basin |
| E | Language editing | Not yet done, external to the manuscript |

## Sections 3.2 to 3.6, ahead of the review

| Section | Point | Carried out |
|---|---|---|
| 3.2 | Six wave settings without stated ground | Each grounded. The 3600 s exchange from the tidal and sea-breeze time scales and the wave model share of the wall time. Stationary mode from the wave crossing time of the basin, about fifteen minutes. Inner grid stated as about half as fine as the flow mesh in the lagoon |
| 3.3 | Marettimo-anchored boundary offset given in five lines | Magnitude, 384-day basis and residual seasonal spread stated |
| 3.4 | Choice of the vegetation module over trachytopes | Physical ground stated |
| 3.5 | Drifter scoring choices | Advection step, scoring window and fixed wind drift factor stated, with the sweep result behind the last |
| 3.6 | Exclusion of suspended sediment from density | Abort of both members at the same cell and instant stated as the ground |

## Statements corrected against the model files

| As drafted | The model |
|---|---|
| Sigma layers with a growth factor of 1.2 towards the bed | Ten uniform layers, a tenth of the column each |
| Time step capped at 30 s | 30 s in the coupled members, 15 s in the uncoupled ones |
| Outer SWAN grid at about 400 m | 69 × 54 points at 800 m |
| Wind drag coefficient of 0.025 | Charnock formulation with the time-varying ERA5 Charnock parameter |
| Partition count without physical meaning | Solution depends on host and decomposition at the Courant limit of 0.7 of the ensemble (table above) |
| Manning coefficient of 0.023 stated as uncalibrated without a source | Default of the solver, standing for the bare substrate; the 0.050 of Ingrassia et al. (2024) is a bulk roughness of the vegetated lagoon and would count the canopy twice in a model that resolves it |
| Initial conditions represented the observed summer state | The earlier ensemble started from a uniform 24 °C and 37.5 outside the lagoon; the present one from the CMEMS depth profiles |
| Ensemble runs completed in about twelve hours on a 64-core workstation | All members ran on a 48-core Linux server, 4.5 to 6 h for a coupled nine-day member |

## Open items

| Item | State |
|---|---|
| Author order, affiliations, CRediT roles | Require the agreement of every author before submission |
| Reference set | Kjerfve (1994), Niedda and Greppi (2007) and Umgiesser et al. (2014) still the only sources for their claims |
| Bed shear stress over the meadow and canopy reconfiguration (Sections 4.4 and 5.4) | Taken from one-day probes started from the uniform column, as the text states; to be recomputed from the stratified start |
| Calibration of the mobile bed | Erosion parameters to be brought to suspended sediment of tens of mg/l before the arm can enter the attribution |
| Language editing, graphical abstract, funding identifier | Not yet done |
| Figures of the Supplementary Material | Seven figures included, on mesh resolution with the northern inlet in detail, SWAN grids, Marettimo offset, wind blending, initial profiles, the discretisation tests with the meshes at the northern inlet, and the web portal of the model output on the EDITO storage (Section S8); the figure of the mobile-bed state awaits the server |
| Research data (ECSS Option C) | Data to be deposited in a repository and cited, with a data availability statement |
| Review of Sections 3.2 onward | Awaited |
