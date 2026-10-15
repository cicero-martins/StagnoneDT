# Paper 1, internal review of Sections 1 to 3.1

Observations of M. De Marchis on the review-mode draft, read as far as
Section 3.1, against the changes carried into the manuscript. The revised
manuscript is [`paper1_revised_2026-10-15.pdf`](paper1_revised_2026-10-15.pdf),
and the full record of each item, with the evidence behind it, is in
[`paper1_internal_review.md`](paper1_internal_review.md).

## Observations received

| # | Observation | Planned | Carried out | Where |
|---|---|---|---|---|
| 1 | Co-authorship of Nasello and Maltese | Add both, settle order, affiliation and CRediT roles | Both added. Order Martins Jr., De Marchis, Ciraolo, Nasello, Maltese. CRediT roles drafted on the pattern of the supervising co-authors, with Methodology for Maltese | Frontmatter, CRediT statement |
| 2 | Lagoon geometry repeated in the Introduction | Remove the figures that Section 2 already carries | Extent, area, inlet geometry and shoot density removed. The sub-metre mean depth and the 75% decline of *P. oceanica* (2003–2024) kept, since they carry the argument | Section 1 |
| 3 | Age of the reference set | Forward-citation search from the older works | Dunic et al. (2021) and Turschwell et al. (2021) beside Waycott et al. (2009), and Mogé et al. (2019) for the partition count. Formulation sources (Booij, Baptist, Kernkamp, Liu and Weisberg) retained as primary | Section 1, bibliography |
| 4 | Panel sizes in Figure 1 | Remove the margin in panel (a) | Panel (a) limits taken from the mesh, and the width ratio computed from the two extents, which equalises the map heights | Figure 1 |
| 5 | Grounds for the numerical choices in Section 3.1 | State the constraint behind each choice, and state that mesh and layer count were not tested | Each choice carries its constraint. Mesh and layer count were tested instead of declared untested (see the next table). Partition count grounded on cells per partition (Mogé et al., 2019), with the wall time on the server where all members ran | Sections 3.1, 3.6, 4.6, 5.4 |

## Sensitivity to the discretisation

The tests behind item 5 were run on the uncoupled fixed-bed configuration
without canopy, under a Courant limit of 0.5. Skill is the mean Liu–Weisberg
score over the 35 drifters.

| Test | Levels | Water level at the gauges | Drifter skill |
|---|---|---|---|
| Horizontal, quadtree meshes in the lagoon | 60, 30, 15 m | < 1 mm in bias, ≤ 1.5 mm in anomaly RMSE | 0.553 ± 0.004, no monotonic trend; present mesh 0.555 |
| Vertical, uniform sigma layers, horizontal momentum filter | 10, 20, 40 | ≤ 6 mm in bias, ≤ 1.3 mm in anomaly RMSE | +0.014 to +0.028 from 10 to 40, depending on the sampled depth (top layer, upper 0.04 m, upper 0.2 m) |
| Host and decomposition, present mesh | 8 partitions on the server, 4 on a second computer | not compared | 0.034 lower on the second computer, all 35 drifters; no difference on the 60 m quadtree mesh |

The horizontal resolution does not limit the reported quantities. The
vertical dependence and the host dependence are an order of magnitude below
the canopy contrasts (0.087 to 0.256) and comparable to the smaller contrasts
of the vegetated arm (0.010 to 0.018). All members share the 10-layer
discretisation, the server and the decomposition, and Section 5.4 states this
as a limitation. The layer runs required the momentum filter above 10 layers,
which the ensemble does not use, and the same set without the filter is
running.

## Points arising from the journal criteria

| # | Criterion | Carried out |
|---|---|---|
| A | Four tables against the limit of three (ECSS Guide for Authors) | The table of ensemble members replaced by the three-slot member code defined in Section 3.6. Section 4.6 adds a table, which returns the count to four |
| B | Limitations in the abstract (Elsevier reviewer guidance) | Erosion threshold and single nine-day window stated; 248 words against 250 |
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
| Partition count without physical meaning | Solution depends on host and decomposition on the present mesh (table above) |

## Open items

| Item | State |
|---|---|
| Author order, affiliations, CRediT roles | Require the agreement of every author before submission |
| Reference set | Kjerfve (1994), Niedda and Greppi (2007) and Umgiesser et al. (2014) still the only sources for their claims |
| Table count | Four against the limit of three after Section 4.6 |
| Vertical test without the filter | Runs in progress, to be added to Section 4.6 |
| Language editing, graphical abstract, funding identifier | Not yet done |
| Review of Sections 3.2 onward | Awaited |
