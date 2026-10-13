# Internal review of Paper 1

Observations raised by Mauro De Marchis on the review-mode draft of
`manuscript/main.pdf`, read as far as Section 3.1, with items from Section 3.2
onward still to come. Line numbers follow the `lineno` numbering of the
review-mode PDF.

| # | Item | Touches | Status |
|---|------|---------|--------|
| 1 | Co-authorship of Nasello and Maltese | frontmatter, CRediT | open |
| 2 | Lagoon geometry in the Introduction | `01_introduction.tex` | open |
| 3 | Age of the Introduction's reference set | `01_introduction.tex`, `references.bib` | open |
| 4 | Subplot sizing in Figure 1 | `plot_study_area_paper1.py` | open |
| 5 | Justification of the numerical choices in 3.1 | `03_data_methods.tex` | open |

## 1. Co-authorship of Nasello and Maltese

Carmelo Nasello and Antonino Maltese join the author list.

The frontmatter carries three authors, all at Dipartimento di Ingegneria,
Università degli Studi di Palermo. Both proposed authors already appear in the
reference list of this manuscript: Nasello on De Marchis et al. (2012), Ciraolo
and De Marchis (2009), Di Marca et al. (2009) and Ingrassia et al. (2024);
Maltese on Maltese et al. (2025) and Ciraolo and Maltese (2006).

Three details are not settled by the observation itself and need a decision
before the change can be made: position within the author order, affiliation
where it differs from Dipartimento di Ingegneria, and the CRediT roles. The
three current entries follow the pattern used in the `reservoirs_s1_svm`
manuscripts, where supervising co-authors carry Conceptualization,
Supervision, Methodology and Writing (review and editing). Maltese supplied the
seagrass classification method that Section 3.4 builds on, which may warrant a
role beyond that pattern.

Elsevier does not permit authorship changes after acceptance, and changes
before acceptance require written agreement from every author, so the list
should be definitive at submission.

## 2. Lagoon geometry in the Introduction

Removal of the Stagnone geometry figures from the Introduction, at PDF lines
25–34.

The second Introduction paragraph (source lines 31–55) and Section 2 carry the
same quantities:

| Quantity | Introduction | Section 2 |
|---|---|---|
| North–south extent | 11 km | 11 km |
| East–west extent | 2.5 km | 2.5 km |
| Surface area | 2200 ha | 2200 ha |
| Northern inlet | ~400 m wide, 0.30–0.40 m deep | ~400 m wide, 0.30–0.40 m deep |
| Southern inlet | ~2900 m wide, 1.0–1.5 m deep | ~2900 m wide, 1.0–1.5 m deep |
| Shoot density | 1000–1200 plants m⁻² | 1000–1200 plants m⁻² |

The duplication is complete, so the figures can be cut from the Introduction
without loss to the manuscript.

Two elements of that paragraph are not geometry and carry argument rather than
description: the sub-metre mean depth as the ground for rejecting the
depth-averaging assumption, and the 75% reduction in *P. oceanica* extent over
2003–2024 from Maltese et al. (2025), which motivates the vegetated arm of the
design. Whether these stay in the Introduction or move to Section 2 is a
separate question from the geometry.

## 3. Age of the Introduction's reference set

Replacement or supplementation of the older references, found by tracing recent
citations of the works currently used.

Twenty-two of the 29 entries in `references.bib` predate 2015, and the
Introduction draws on nineteen works of which most fall in that group. The
oldest in each role:

| Role in the argument | Current source | Year |
|---|---|---|
| Lagoons on 13% of the global shoreline | Kjerfve (1994) | 1994 |
| SWAN formulation | Booij et al. (1999) | 1999 |
| Stagnone residence time and flushing | La Loggia et al. (2004) | 2004 |
| Canopy resistance formulation | Baptist et al. (2007) | 2007 |
| Mediterranean lagoon wind and seiche | Niedda and Greppi (2007) | 2007 |
| Stagnone particle tracking | Ciraolo et al. (2009) | 2009 |
| Stagnone inlet geometry and exchange | Ciraolo and De Marchis (2009) | 2009 |
| Stagnone turbidity | Di Marca et al. (2009) | 2009 |
| Global seagrass decline | Waycott et al. (2009) | 2009 |
| D-Flow FM solver | Kernkamp et al. (2011) | 2011 |
| Lagrangian skill score | Liu and Weisberg (2011) | 2011 |
| Stagnone 3D wind-driven circulation | De Marchis et al. (2012) | 2012 |
| Seagrass wave attenuation | Infantes et al. (2012) | 2012 |
| Canopy flow and transport | Nepf (2012) | 2012 |
| Ten Mediterranean lagoons compared | Umgiesser et al. (2014) | 2014 |

Several of these are the primary source for a formulation the model uses, and a
newer citation does not replace them: Booij, Baptist, Kernkamp and Liu and
Weisberg are cited because the model implements those specific formulations.
The candidates for refreshment are the framing claims, where a recent synthesis
can stand beside or in place of an older one, and the Mediterranean lagoon
context.

The method the observation proposes is a forward-citation search: for each
older work, the recent papers citing it, filtered to those addressing coastal
lagoon hydrodynamics, seagrass canopy flow or Lagrangian validation.

## 4. Subplot sizing in Figure 1

The map in panel (b) reads as a few millimetres taller than the map in panel
(a). The difference is not in the panels but in a white margin between the map
and the axes frame in panel (a), which neither panel needs.

The figure is built by `scripts/plot_study_area_paper1.py`. Panel (a) sets its
limits from the `DOMAIN` constant while the painted content is the mesh, and
the two do not coincide:

| | Panel (a) limits | Mesh extent | Margin |
|---|---|---|---|
| Longitude | 11.950 to 12.570 | 11.9600 to 12.5581 | 0.0100 west, 0.0119 east |
| Latitude | 37.690 to 38.072 | 37.7000 to 38.0631 | 0.0100 south, 0.0089 north |

Panel (b) sets its limits from `BBOX` and paints the lagoon to the frame, so no
margin appears there. With `set_aspect` applied to both and the axes box free
to adjust, the empty latitude band in panel (a) is drawn inside the frame and
the map it contains ends up shorter than panel (b)'s.

Setting panel (a)'s limits to the mesh extent removes the band. The margin is
about 2.6% of the panel's latitude range, which is consistent with the
millimetre-scale difference observed.

## 5. Justification of the numerical choices in 3.1

Statement of the reasoning behind the mesh resolution, the ten sigma layers,
the eight partitions, and the discretisation method.

Section 3.1 states each choice without the ground for it:

| Choice | Present text | Ground given |
|---|---|---|
| Mesh | 21,188 nodes, 25,212 faces, graded towards the lagoon | resolution required by inlets and intertidal flats, not quantified |
| Vertical | 10 sigma layers, `SigmaGrowthFactor` 1.2 | distributes resolution towards the bed |
| Partitions | eight, under MPI | none |
| Time step | adaptive, Courant 0.7, capped at 30 s | none |
| Discretisation | not stated | none |

The partition count is a throughput choice rather than a physical one, and the
measurements supporting it exist: the 8 MPI + `KMP_HW_SUBSET=16c,1t`
configuration reaching about nine hours per nine simulated days on the
64-core machine, recorded in `hpc_optimization_xeon_64core`. A sentence saying
so removes the implication that eight carries physical meaning.

The discretisation material also exists, in
[`docs/fm_navier_stokes_derivation.md`](fm_navier_stokes_derivation.md), which
documents the path from the Navier–Stokes equations to the discrete system
D-Flow FM solves, together with the scheme catalogue. Section 3.1 can draw on
it without the document being cited.

The mesh resolution and the layer count are the two that may need evidence
rather than reasoning. Neither has a convergence test behind it in this
project. A defensible alternative is to state the constraint each choice
answers, with the note that no sensitivity test was run, rather than to imply a
convergence study that does not exist.

## Anticipated observations from Section 3.2 onward

The five received items are not independent. Four of them express one
criterion, and the remaining one expresses a second:

| Item | Criterion expressed |
|---|---|
| 2, geometry in the Introduction | material belongs where it does work, once |
| 3, reference age | the literature position must be current |
| 5, choices in 3.1 | a value stated is a value to be grounded |
| 1, co-authorship | contribution recognised where it was made |
| 4, subplot sizing | figure craft at the level of the panel |

Items 2, 3 and 5 all reduce to a demand for warrant. The sections not yet read
can be scanned against the same demand, and
[`scripts/audit_methods_justification.py`](../scripts/audit_methods_justification.py)
does so by rule: a sentence asserting a setting is flagged when neither it nor
its neighbour carries a causal clause, a constraint answered, or a citation.

The script flags 11 sentences in Section 3. Two of them are grounded on
re-reading, the evaporation sign convention and the sediment thickness taper,
which the pattern missed. The remaining nine assert a setting with no ground:

| Section | Setting | Value |
|---|---|---|
| 3.1 | Uniform Manning coefficient | 0.023 s m^-1/3 |
| 3.1 | External forcing update interval | 300 s |
| 3.1 | Courant limit, time step cap, growth factor | 0.7, 30 s, 1.1 |
| 3.2 | Spectral discretisation | 24 directions, 24 frequencies, 0.05–1.0 Hz |
| 3.2 | Source term set | third generation, Komen whitecapping, quadruplets, refraction, frequency shifting |
| 3.2 | Processes disabled | triads, wave setup |
| 3.2 | Breaking and bottom friction | Battjes–Janssen α=1.0, γ=0.73; JONSWAP 0.067 m² s⁻³ |
| 3.2 | Minimum depth | 0.05 m |
| 3.2 | Coupling exchange interval | 3600 s |

Six of the nine fall in Section 3.2, which is where the review stopped. The
concentration is not an artefact of the scan: Section 3.2 is a list of SWAN
settings and the only ground it offers anywhere is for `ncFormat = 3`.

Applied to Sections 4 and 5 the same scan returns mostly reported measurements
rather than settings, so its output there carries no weight. The demand for
warrant is a Methods criterion.

### Section 3.2, wave model and coupling

The nine-item list above gives six. Three further points sit in the same
section and would not be caught by a scan for values.

The two nested grids at 400 m and 100 m have no stated relation to the
hydrodynamic mesh they exchange with, which is graded and unstructured. Whether
the 100 m inner grid resolves the inlets, which are 400 m and 2900 m wide, is
the question a reader of Section 3.1 will carry into 3.2.

Stationary mode inside each exchange is stated and explained mechanically, in
that the time variation follows from re-evaluated forcing. The ground for it
being adequate, namely that the wave field equilibrates faster than the hourly
exchange in a fetch-limited basin, is not given.

The 3600 s exchange interval sets the time resolution of the whole coupling and
is the one number in Section 3.2 whose justification a reviewer is most likely
to demand, since the drifter deployments last 0.4 to 7.2 hours.

### Section 3.3, boundary and atmospheric forcing

This section is better grounded than 3.2. The advection velocity boundary, the
CMEMS reference frame correction, the wind blending choice and the nudging
relaxation time each carry a reason.

Two exposures remain. The Charnock drag coefficient of 0.025, stated in 3.1,
appears without source or justification. And the per-node offset anchored at
Marettimo is a substantial methodological construction given in five lines,
with the supporting material in
[`docs/marettimo_offset_anchor_2025.md`](marettimo_offset_anchor_2025.md) and
[`docs/wl_boundary_offset_justification.md`](wl_boundary_offset_justification.md)
not drawn on. A reviewer who doubts the water level results will go to this
paragraph first.

### Section 3.4, seagrass canopy parametrisation

The anticipated question is why FM's vegetation module rather than trachytopes,
given that the trachytope formulation is the one a Delft3D user expects for
vegetation and the one the earlier literature on this lagoon uses. The answer
the project holds is that the trachytope canopy term does not enter the
momentum equation in this build, recorded in `fm_trachytope_sink_inert`. How
much of that belongs in the manuscript is a judgement, but silence invites the
question.

The parameter values carry published sources, which is the section's strength
and should survive the review. The canopy height of 0.40 m is the one value
derived rather than cited, and `veg_calibration_hv_canopy_height` records that
it is a canopy height and not a leaf length.

### Section 3.5, observational data and validation metrics

The drifter scoring carries choices that are not yet visible in the text: the
600 s scoring grid against 300 s observations, the windage treatment, and the
one-day spin-up discard. Each is defensible and none is stated with its ground.

The windage choice is the most exposed, since `windage_wind_speed_hypothesis`
records that no single value is optimal across deployments and that the optimum
tracks wind speed.

### Section 3.6, numerical experiments

The exclusion of the suspended sediment contribution to density is stated as a
property of the design. A reviewer may read it as a parameter tuned to make
runs complete, which is the reading the text is written to avoid but cannot
prevent. The supporting evidence, that the two members abort at the same cell
and the same instant to six decimal places, is in the project record and not in
the manuscript.

Deployment 4 is retained deliberately and the reasoning is recorded in
`scripts/_ensemble.py` rather than in the manuscript. Since removing it would
widen every canopy contrast, a reviewer noticing the outlier without seeing the
reasoning may read the retention as an oversight.

### Sections 4 to 6

Figure craft, following item 4, applies to all eight figures and not only to
Figure 1. The three-slot member code W, R, M introduced for the tables and
reused in the figures is compact but unconventional, and a reviewer may prefer
descriptive labels.

Four tables are present against a journal limit of three, which is treated
under the next chapter.

## Assessment against the journal's review criteria

### Sources

Two sources carry assessable criteria. Elsevier's reviewer guidance for
original research articles sets out what referees are asked to judge, section
by section. The *Estuarine, Coastal and Shelf Science* Guide for Authors, saved
at `reference/guide_ecss.pdf`, sets the journal's scope, article type limits
and the grounds on which a submission falls outside them.

Two further sources were consulted and do not supply assessment criteria.
Borja and Elliott (2024), the editorial by the journal's Editors-in-Chief
saved at `reference/editorial_ECSS.pdf`, concerns the shortage of referees and
the incentives for reviewing. Elsevier's page on what peer review is covers the
review models and the handling process. Each contributes one fact that bears on
this manuscript.

The editorial's Table 1 lists "a poor paper, badly written which is wasting my
time" and "not understandable paper" among the acceptable reasons for a
referee to decline an invitation, alongside conflict of interest and lack of
expertise. Clarity therefore affects whether a manuscript is reviewed at all,
not only how it is judged. The same table records that editors now approach 4
to 10 referees per paper where they once approached 4, so an invitation
declined on those grounds costs weeks.

The Elsevier process page records that a rejected submission may be
transferred to another journal with its reviewer reports attached.

### Measurable compliance

| Limit | Journal | Manuscript | |
|---|---|---|---|
| Abstract | 250 words | 238 | within |
| Body text | 8000 words | 6580 | within |
| Figures | 8 | 8 | at the limit |
| Tables | 3 | 4 | **over** |
| Keywords | 1 to 7 | 6 | within |
| Highlights | 3 to 5 bullets, 85 characters | 5, all within | within |

The table count exceeds the limit:

| | Content | Size |
|---|---|---|
| Table 1 | canopy parameters | 7 rows, 3 columns |
| Table 2 | ensemble members | 9 rows, 4 columns |
| Table 3 | water level by station and member | 25 rows, 7 columns |
| Table 4 | Lagrangian metrics by member | 9 rows, 8 columns |

Smallest is not cheapest. Table 1 is the smallest but holds the published
sources for every canopy parameter, which is what supports the claim that
nothing was fitted, so removing it weakens the section the paper leans on.
Table 2 is reproducible as a sentence plus the member code already defined,
and is the least destructive of the available reductions.

Figures stand exactly at the limit, so any figure added in response to a review
item displaces another.

### Review process

The journal operates single anonymized review with a minimum of two reviewers,
and editors assess suitability before a manuscript reaches them. Two
consequences follow for a manuscript whose scope defence is the live risk.

Rejection can occur before review, on the editors' suitability assessment
alone, which is the stage at which the local interest exclusion applies and the
stage at which only the title, abstract and Introduction have been read.

A rejected submission can be transferred to another Elsevier journal through
the Article Transfer Service, and the reviewer reports travel with it. A
negative report therefore follows the manuscript rather than being discarded
with the submission.

### Criterion by criterion

| Criterion | State | Exposure |
|---|---|---|
| Title describes the content and is searchable | Names the three factors and the ranking the paper delivers | none identified |
| Abstract stands alone, reports results and limitations | Reports the ranking with intervals; carries no limitation | moderate: Elsevier asks for limitations in the abstract |
| Introduction: background current, rationale clear, objectives at the end | Rationale clear; 22 of 29 references predate 2015; closes on a roadmap paragraph rather than on objectives | high, and already raised as item 3 |
| Methods detailed enough to replicate | Model version, mesh, forcing and parameters given; nine settings ungrounded; no convergence test | high, and already raised as item 5 |
| Results: figures and tables present the findings; further analyses needed | Eight figures, four tables; bootstrap intervals throughout; a deployment-level sensitivity exists but is not reported | moderate |
| Discussion: conclusions supported, limitations emphasised | A Limitations subsection is present and names the uncalibrated erosion threshold | low |
| References up to date and relevant | 22 of 29 predate 2015 | high, and already raised as item 3 |
| Language quality | Written by a non-native speaker without professional editing | moderate |
| Novelty and importance to the field | A complete factorial separating canopy, waves and bed mobility, with the canopy as first-order control | see below |

### Scope and the local interest exclusion

The Guide for Authors states that the journal does not accept manuscripts on
data of mainly local interest, and discourages data reports of mainly local and
descriptive nature. This is the one criterion on which a rejection would be
structural rather than correctable in revision.

The manuscript's defence against it is that its claims concern what a class of
validation data can certify and how a factorial behaves when a dominant factor
is omitted, neither of which is specific to this basin. That defence is carried
in Sections 5 and 6 and not in the abstract or the Introduction, where an
editor deciding suitability reads first.

Item 2, removing the geometry from the Introduction, acts in the same direction
as this concern. The Introduction currently spends its second paragraph on the
description of one lagoon.

### Items arising

Points not raised in the received review that follow from the criteria above:

| # | Item | Source of the criterion |
|---|---|---|
| A | Four tables against a limit of three | ECSS Guide for Authors |
| B | Abstract carries no limitation | Elsevier reviewer guidance |
| C | Introduction closes on a roadmap rather than on objectives | Elsevier reviewer guidance |
| D | Generality claim absent from abstract and Introduction | ECSS local interest exclusion |
| E | Language editing before submission | editorial Table 1, referees decline unclear papers |
| F | Deployment-level sensitivity computed but not reported | Elsevier reviewer guidance on further analyses |
