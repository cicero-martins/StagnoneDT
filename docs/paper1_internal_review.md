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

Alignment of the subplot sizes in Figure 1.

The figure is built by `scripts/plot_study_area_paper1.py` as three panels: the
modelled domain including the Egadi archipelago, a narrow panel over the
lagoon, and an Italy locator inset placed in the lower-left corner of the first
panel. The lagoon is about 11 km by 2.5 km against a domain spanning roughly
0.6° by 0.36°, so the two map panels carry very different aspect ratios and the
panel heights do not currently match.

Options differ in what they cost. Equal panel heights with each panel keeping
its own geographic aspect leaves unequal widths. Equal widths force the lagoon
panel to a scale that wastes most of its area. A third route is a shared height
with the lagoon panel rotated or cropped to a window closer to the domain
panel's aspect.

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

## Pending

Items from Section 3.2 onward.
