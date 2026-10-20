# Paper 1, internal review of Sections 1 to 3.1

M. De Marchis reviewed the review-mode draft as far as Section 3.1, and each
observation is paired with the change carried into the manuscript. The revised
manuscript is [`paper1_revised_2026-10-20.pdf`](paper1_revised_2026-10-20.pdf),
and the full record of each item, with the evidence behind it, is in
[`paper1_internal_review.md`](paper1_internal_review.md).

## Observations received

| # | Observation | Planned | Carried out | Where |
|---|---|---|---|---|
| 1 | Co-authorship of Nasello and Maltese | Add both, settle order, affiliation and CRediT roles | Both added. Order Martins Jr., De Marchis, Ciraolo, Nasello, Maltese. CRediT roles drafted on the pattern of the supervising co-authors, with Methodology for Maltese | Frontmatter, CRediT statement |
| 2 | Lagoon geometry repeated in the Introduction | Remove the figures that Section 2 already carries | Extent, area, inlet geometry and shoot density removed. The sub-metre mean depth and the 75% decline of *P. oceanica* (2003–2024) kept, since they carry the argument | Section 1 |
| 3 | Age of the reference set | Forward-citation search from the older works | Dunic et al. (2021) and Turschwell et al. (2021) beside Waycott et al. (2009), and Mogé et al. (2019) for the partition count. Formulation sources (Booij, Baptist, Kernkamp, Liu and Weisberg) retained as primary | Section 1, bibliography |
| 4 | Panel sizes in Figure 1 | Remove the margin in panel (a) | Panel (a) limits taken from the mesh, and the width ratio computed from the two extents, which equalises the map heights | Figure 1 |
| 5 | Grounds for the numerical choices in Section 3.1 | State the constraint behind each choice, and state that mesh and layer count were not tested | Each choice carries its constraint. Mesh, layer count, time-step limit, host and initial condition were tested (see the next section). Partition count grounded on cells per partition (Mogé et al., 2019), with the wall time on the server where all members ran | Sections 3.1, 3.6, 4.6, 5.4 |

## Sensitivity to the discretisation and the initial condition

Skill is the mean Liu–Weisberg score over the 35 drifters, with the paired
difference between runs and its standard error or 95% bootstrap interval.

| Test | Configuration | Water level at the gauges | Drifter skill |
|---|---|---|---|
| Horizontal resolution, quadtree meshes in the lagoon, 60, 30, 15 m | uncoupled, fixed bed, no canopy, Courant 0.5 | < 1 mm in bias, ≤ 1.5 mm in anomaly RMSE | 0.553 ± 0.004, no monotonic trend; present mesh 0.555 |
| Vertical resolution, 10 and 20 uniform sigma layers | as above, stratified start, time step limited also by vertical fluxes | ≤ 2.4 mm in bias, ≤ 1.6 mm in anomaly RMSE | 0.619 at both, +0.0003 ± 0.0036 |
| Time-step limit by vertical fluxes, 10 layers | as above, uniform start | < 0.3 mm | +0.0007 ± 0.0007 |
| Host and decomposition, 8 partitions on the server against 4 on a second computer | uncoupled member, Courant 0.7 (ensemble) | not compared | 0.034 lower on the second computer, all 35 drifters |
| Same | Courant 0.5 | identical to 0.1 mm | +0.002 ± 0.001; no difference on the 60 m quadtree mesh |
| Initial condition, stratified against uniform offshore column | ensemble configuration, member `---` | mean level 2 to 8 cm lower; anomaly RMSE within 3 mm | 0.619 against 0.539, +0.080 (CI +0.041 to +0.119), 31 of 35 better |
| Same | member `-V-` | mean level lower; anomaly RMSE unchanged | +0.005 (CI −0.003 to +0.011) |

Neither the horizontal nor the vertical resolution limits the reported
quantities, the layer test having started from the stratified condition, the
CMEMS profiles of temperature and salinity at the start time, because above 10
layers the start from a uniform column is unstable next to the open boundary.
The initial condition is the one choice with an effect of the order of the
ensemble contrasts. From the stratified start the canopy contrast on the uncoupled fixed
bed is +0.120 (CI +0.061 to +0.180) against +0.195 from the uniform start, still
clear of zero, and its water-level signature at AltaVilaEst is unchanged. The
uniform start lowers the skill of the bare member and leaves the vegetated
member nearly unaffected. Sections 3.3, 3.6, 4.6 and 5.4 and the abstract state
this, and the ensemble numbers in the present version remain those of the
uniform start.

The full ensemble is being rerun from the stratified condition, with the
configuration otherwise unchanged, for the submitted version.

## Points arising from the journal criteria

| # | Criterion | Carried out |
|---|---|---|
| A | Four tables against the limit of three (ECSS Guide for Authors) | The table of ensemble members replaced by the three-slot member code defined in Section 3.6; three tables |
| B | Limitations in the abstract (Elsevier reviewer guidance) | Single nine-day window, uncalibrated bed mobility and uniform initial state stated, in an abstract of about 245 words written in impersonal construction |
| C | Introduction closing on objectives | Roadmap paragraph replaced by three objectives |
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
| Initial conditions represented the observed summer state | Uniform 24 °C and salinity 37.5 outside the lagoon, 42 inside |
| Ensemble runs completed in about twelve hours on a 64-core workstation | All members ran on a 48-core Linux server, 4.5 to 6 h for a coupled nine-day member |

## Open items

| Item | State |
|---|---|
| Author order, affiliations, CRediT roles | Require the agreement of every author before submission |
| Reference set | Kjerfve (1994), Niedda and Greppi (2007) and Umgiesser et al. (2014) still the only sources for their claims |
| Ensemble from the stratified initial condition | Runs in progress on the server; all numbers of Sections 4 and 5, the abstract and the conclusions to be updated from them |
| Language editing, graphical abstract, funding identifier | Not yet done |
| Review of Sections 3.2 onward | Awaited |
