# Research questions and publication plan

*Stagnone di Marsala model, PhD project, Università degli Studi di Palermo. State of 30 October 2026.*

## Research questions

| # | Research question | Status | Evidence in hand | Paper |
|---|---|---|---|---|
| RQ1 | What is the three-dimensional wind-driven flow structure in a sub-metre-deep vegetated lagoon, and how does it differ from depth-averaged dynamics? | Addressed | Process ensemble from the stratified start; the canopy raises the surface-to-bottom speed ratio over the meadow from 1.9 to 4.5, which an equivalent bed roughness does not reproduce | P1 |
| RQ2 | Do wave–current coupling and spatially distributed seagrass canopy improve Lagrangian transport prediction, and what is the relative contribution of each? | Addressed | Complete 2 × 2 × 2 factorial; on the fixed bed the canopy raises Liu–Weisberg skill by 0.120 and 0.114 and wave coupling changes it by −0.022 and −0.028 (35 drifters, twelve deployments) | P1 |
| RQ3 | Is Lagrangian drifter validation more discriminating than water-level metrics for evaluating competing model configurations in a micro-tidal lagoon? | Addressed | Water level separates the canopy treatments only at AltaVilaEst, by 26 and 27 mm in anomaly RMSE, against at most 4 mm near the inlets | P1 |
| RQ4 | How has the decline of *Posidonia oceanica* (2003–2025) altered wave attenuation, near-bed current exposure and water residence time, and what are the consequences of projected further cover loss? | Partial | Cover maps of Maltese et al. (2025) for 2003–2024 and the PlanetScope classification of 2023 and 2025; canopy parameters from published measurements in the `[veg]` module; paired cover scenarios not run | P2 |
| RQ5 | Can satellite-derived bathymetry capture bathymetric change accompanying seagrass decline (2023–2025) and constrain the sediment calibration? | In progress | Stumpf and Lyzenga pipelines on the August 2023 and August 2025 composites; the difference is dominated by radiometric offset, so several scenes per year are needed | P4 (supporting) |
| RQ6 | Can the coupled model support short-range forecasts served through a web interface for lagoon management? | Prototype | Portal on EDITO serving the hindcast; continuation runs on the CMEMS analysis and forecast boundary (`v04AE_d10d12`); no scheduled forecast | P3 |
| RQ7 | Are wave events capable of mobilising lagoon sediment, and how much do fine-sediment inputs from the Trapani canal system (airport and saltpan drainage) contribute to lagoon siltation? | In progress | D-Morphology with sand (150 µm) and silt (30 µm); the present parameters give implausible suspended load under waves, and a plausibility sweep of the deposition threshold and skin friction is running; canal tracer not quantified | P4 |
| RQ8 | What would be the hydrodynamic and environmental impact of reopening the historic channel at Isola Grande, restoring exchange between the northern sub-basin and the open sea? | Exploratory | Mesh with the reopened channel (`net_nodm_choke_opened/`); no coupled run | P3 |
| RQ9 | Does a velocity-dependent *P. oceanica* resistance following the flume law of Ciraolo and Ferreri (2006), S_f ∝ U^0.44, improve hydrodynamic skill and alter the simulated response to cover change relative to a fixed canopy drag? | Experimental | `scripts/build_ciraolo_roughness_dynamic.py` builds the static field; trachytope formulas 155 and 156 exist in kernel 1.2.184, but their canopy momentum sink does not reach the solution, so the comparison has to go through the `[veg]` module | P2 |

## Publication plan

| Paper | Research questions | Contribution | Target journal | Status |
|---|---|---|---|---|
| P1 | RQ1–RQ3 | Relative effects of seagrass canopy, wave coupling and bed mobility on transport, validated against tide gauges and surface drifters | *Estuarine, Coastal and Shelf Science* | Manuscript revised on 27 October 2026 with a Supplementary Material (`manuscript_v2/`); internal review of the revised version pending; the bed-change figure of the mobile-bed arm still to be added |
| P2 | RQ4, RQ9 | Hydrodynamic and environmental response to *P. oceanica* decline under 2003 and 2025 cover, with the velocity-dependent canopy resistance | *Estuarine, Coastal and Shelf Science* / *Marine Ecology Progress Series* | Cover maps and canopy parameters available; scenario runs pending |
| P3 | RQ6, RQ8 | Forecast chain on CMEMS, the WetWise portal, and the Isola Grande channel scenario | *Environmental Modelling & Software* / *Ocean & Coastal Management* | Portal published; channel mesh exists; no forecast chain and no channel run |
| P4 | RQ5, RQ7 | Wave-driven resuspension and canal fine-sediment input, with the sediment calibration constrained by satellite-derived bathymetry | *Continental Shelf Research* / *Geomorphology* | Plausibility sweep running; calibration not constrained |

## Notes

- P2 takes the classification of Maltese et al. (2025) as the input cover scenario. Its contribution is the propagation of the decadal cover loss into hydrodynamic and environmental change, with the automated PlanetScope classification extending the series to 2025.
- RQ9 belongs to P2 because a resistance scaling with U^0.44 changes the simulated wave attenuation and near-bed exposure under the two cover states more than a fixed drag does.
- P3 groups the forecast chain with the channel scenario, since both concern the use of the model for lagoon management.
- P4 is the most data-constrained of the four, depending on the sediment calibration and on the canal sediment load.
