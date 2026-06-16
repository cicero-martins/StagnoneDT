# Research Questions — Status and Publication Roadmap
*Stagnone di Marsala Digital Twin — PhD, UNIPA*
*Updated: 2026-06-16*

---

| # | Research question | Status | Key evidence in hand | Paper | Target journal |
|---|---|---|---|---|---|
| RQ1 | What is the three-dimensional wind-driven flow structure in a sub-metre-deep vegetated lagoon, and how does it differ from depth-averaged dynamics? | **Answerable** | v04AE 9-day validated run; WL corr 0.98/0.90/0.82 at BN/BS/AE; pronounced vertical shear confirmed in 3D output | **Paper 1** | *Estuarine, Coastal and Shelf Science* |
| RQ2 | Do wave–current coupling and spatially distributed seagrass roughness improve Lagrangian transport prediction in a shallow lagoon, and what is the relative contribution of each? | **Answerable** | 4-member ensemble (baseline / VR only / waves only / full); Liu–Weisberg skill 0.570 vs 0.377 baseline; endpoint proximity; v04AE_vr | **Paper 1** | *Estuarine, Coastal and Shelf Science* |
| RQ3 | Is Lagrangian drifter validation more discriminating than water-level metrics for evaluating competing model configurations in a micro-tidal coastal lagoon? | **Answerable** | Skill scores across ensemble clearly differentiate configurations where WL metrics cannot; GPS drifter dataset Jul 2025 | **Paper 1** | *Estuarine, Coastal and Shelf Science* |
| RQ4 | What are the long-term (2003–2024) trends in *Posidonia oceanica* meadow geometry and cover in the Stagnone, and can multi-sensor high-resolution satellite imagery quantify these changes reliably? | **Largely answered** (Maltese et al. 2025 published); our contribution = 2025 epoch extension and linkage to hydrodynamic forcing | Maltese et al. 2025 LGBM classification (WorldView/QuickBird/Pleiades, 2 m); our RF/PlanetScope 2023 + 2025 classification; ~75% decline quantified | **Paper 2** | *Remote Sensing of Environment* / *ISPRS J. Photogrammetry* |
| RQ5 | Can satellite-derived bathymetry (SDB) detect morphological change in an ultra-shallow vegetated lagoon between 2023 and 2025? | **In progress** | Stumpf log-ratio and Lyzenga SDB scripts; Aug 2023 and Aug 2025 PlanetScope composites; ELC normalisation applied; radiometric offset identified as dominant signal | **Paper 2** | *Remote Sensing of Environment* / *Estuarine, Coastal and Shelf Science* |
| RQ6 | How do residence time distributions and near-bed current exposure respond to changes in seagrass canopy cover, and what are the implications for meadow connectivity and recovery? | **Partial** — model infrastructure ready; scenario runs not yet executed | v04AE_vr (2023 cover); Maltese 2025 multi-epoch maps available for boundary conditions; Baptist trachytope framework reusable | **Paper 2** or **Paper 3** | *Estuarine, Coastal and Shelf Science* / *Marine Ecology Progress Series* |
| RQ7 | Can the calibrated coupled model support skillful operational short-range forecasts of water level, surface currents, and wave exposure, and be served through a web interface suitable for lagoon management? | **Prototype** — forecast chain operational; skill assessment pending against independent observations | WetWise portal (Leaflet, 30-min resolution, coarse/fine pyramid); CMEMS *anfc* boundary chain; v04AE_d10d12 continuation run validated (corr 0.98/0.90/0.36 BN/BS/AE) | **Paper 3** | *Environmental Modelling & Software* / *Ocean & Coastal Management* |

---

## Notes

- **Paper 1** target submission: ECSS special issue or regular track; §1 Introduction and §2 Study Area drafted (Jun 2026).
- **Paper 2** depends on whether RQ5 (SDB) yields a publishable change signal; if not, can be restructured around RQ4 + RQ6 only.
- **Paper 3** requires a formal forecast skill evaluation against withheld observations; WetWise architecture is the main contribution, not the skill numbers alone.
- RQ1–RQ3 are jointly addressed by Paper 1's four-member ensemble design. Splitting them into separate papers is not recommended.
- The [REF-wave-current-lagoon] placeholder in Paper 1 §5 (gap statement) remains unresolved — a Mediterranean lagoon wave–current interaction study is needed.
