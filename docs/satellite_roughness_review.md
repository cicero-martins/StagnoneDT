# Literature Review: Satellite-Derived Roughness Alternatives for Shallow Lagoon Hydrodynamic Modeling

**Project**: Stagnone di Marsala Digital Twin  
**Date**: 2026-04-20  
**Scope**: 2020–2025 (state-of-the-art) + key classics pre-2020  

---

## 1. Current Approach and Limitations

The current implementation (`notebooks/03_satellite_roughness.ipynb`) uses:
- Single Sentinel-2 L2A scene (Sep 2024, 10 m)
- Threshold classification on Green/Blue ratio + NDVI → 4 classes
- Fixed Manning n per class: bare sand (0.020), sparse Cymodocea (0.035), dense Posidonia (0.050), rock (0.028)
- Output: XYZ file for D-Flow FM (65k points, ~30 m spacing)
- **Not yet activated** in model (uniform n=0.023)

Key limitations: no ground truth, no water column correction, no depth-dependent drag, no temporal dynamics, generic Manning values.

---

## 2. Paper Review by Research Axis

### Axis 1 — SAV Mapping with Machine Learning

| # | Authors (Year) | Journal | Sensor | Method | Accuracy | Med? | Code? | Relevance |
|---|---|---|---|---|---|---|---|---|
| 1 | Traganos & Reinartz (2018) | Mar. Poll. Bull. | S2 | SVM/RF + Lyzenga WCC | OA 72.6% | Yes | No | **Very High** — *P. oceanica* + *C. nodosa*, Med |
| 2 | Traganos et al. (2018) | Remote Sensing | S2 / GEE | RF on GEE | OA 72–82% | Yes | GEE partial | **High** — Aegean seagrass, scalable |
| 3 | Poursanidis et al. (2019) | J. Appl. Earth Obs. | S2 | RF + WCC + coastal aerosol | OA ~82% | Yes | No | **Very High** — *P. oceanica*, Crete |
| 4 | Ha et al. (2020) | Remote Sensing | S2 | RF vs GBM comparison | OA 86–90%, κ 0.82–0.87 | No | No | **Medium** — rigorous ML comparison |
| 5 | Traganos et al. (2022) | Front. Mar. Sci. | S2 / GEE | ML, Med-wide | PA 95.3% / UA 99.5% | Yes | GEE | **Very High** — entire Med coverage |
| 6 | Languille et al. (2023)* | Remote Sens. Environ. | S2 + aerial | U-Net deep learning | F1 0.85–0.90 | Yes | Verify | **Very High** — DL for *P. oceanica* |
| 7 | Martin et al. (2022)* | Ecol. Indicators | S2 / WV | CNN + transfer learning | OA >85%, F1 ~0.80 | No | Verify | **Medium** — transfer learning demo |
| 8 | Ventura et al. (2018) | Remote Sensing | UAV | OBIA | OA >90% | Yes | No | **High** — *P. oceanica* validation source |

*Papers marked with \* need DOI verification.*

**Key findings — Axis 1:**
- RF remains the workhorse for Med seagrass mapping (Traganos, Poursanidis)
- Deep learning (U-Net, CNN) emerging but still rare for Med seagrass — **publication gap**
- Water column correction (Lyzenga DII) is a prerequisite for accurate classification
- Accuracies range from 72% (basic threshold) to 95% (optimized RF/ML on GEE)

### Axis 2 — Water Column Correction and Optical Bathymetry

| # | Authors (Year) | Journal | Sensor | Method | Key Finding | Code? | Relevance |
|---|---|---|---|---|---|---|---|
| 9 | **Lyzenga (1978)** | Applied Optics | MSS | Depth-invariant index (DII) | Foundational band-ratio method | N/A | **Essential classic** |
| 10 | **Lyzenga et al. (2006)** | IEEE TGRS | IKONOS | Physics-based SDB | Handles variable bottom + water quality | N/A | **Essential classic** |
| 11 | **Lee et al. (1998)** | Applied Optics | AVIRIS | HOPE semi-analytical model | Simultaneous depth + bottom albedo retrieval | N/A | **Essential classic** |
| 12 | **Lee et al. (1999)** | Applied Optics | AVIRIS | HOPE inversion (LM optimization) | ~10% depth accuracy in clear waters | N/A | **Essential classic** |
| 13 | Caballero & Stumpf (2020) | Remote Sensing | S2 | Multi-temporal SDB compositing | Median error <0.5 m (0–13 m) | GEE-compat. | **High** — routine SDB with S2 |
| 14 | Wei et al. (2020) | Remote Sens. Environ. | S2 / VIIRS | Temporal-variation physics-based | Exploits water clarity changes | No | **High** — multi-date approach |
| 15 | Wang et al. (2024) | ISPRS J. P&RS | S2 + ICESat-2 | LSBR benthic reflectance | Bottom reflectance without lidar | No | **High** — benthic reflectance from S2 alone |

**Key findings — Axis 2:**
- Lyzenga DII (1978/2006) remains the standard empirical approach; Lee HOPE for semi-analytical
- Multi-temporal compositing (Caballero 2020) improves SDB in variable turbidity — directly applicable to Stagnone
- Wang (2024) LSBR model could provide spatially continuous bottom reflectance from S2 alone
- Stagnone's 0.5–2.5 m depth range is ideal for these optical methods

### Axis 3 — Multi-temporal PlanetScope Approaches

| # | Authors (Year) | Journal | Sensor | Method | Accuracy | Code? | Relevance |
|---|---|---|---|---|---|---|---|
| 16 | Wicaksono & Lazuardi (2018) | Int. J. Remote Sensing | PS 3 m | OBIA + pixel classification | OA 56–70% (species) | No | **Med-High** — PS seagrass baseline |
| 17 | Fauzan et al. (2021) | ISPRS Archives | PS 3 m | Regression (biomass) | R² 0.5–0.7 | No | **Medium** — PS biomass → drag proxy |
| 18 | Kovacs et al. (2022) | Remote Sens. Letters | S2/WV3/L8/ZY3 | RF multi-sensor comparison | OA 68–88% | No | **Med-High** — sensor trade-off analysis |
| 19 | Carlson et al. (2023)* | Remote Sens. Environ. | PS time series | NDVI phenology | R² >0.7 vs field | Verify | **Med-High** — PS temporal for aquatic veg |
| 20 | Lyons et al. (2020) | Remote Sens. Ecol. Conserv. | PS + S2 fusion | Hierarchical classification | OA 70–85% | Allen Coral Atlas | **Med-High** — multi-sensor fusion framework |
| 21 | Li et al. (2021) | Remote Sensing | S2 / GEE | Automated SDB pipeline | RMSE 0.5–1.5 m | GEE code | **Med-High** — bathymetry pre-processing |

*Papers marked with \* need DOI verification.*

**Key findings — Axis 3:**
- **Major gap**: very few papers use PlanetScope specifically for Mediterranean seagrass — strong publication opportunity
- PS 3 m resolves individual Posidonia matte patches (~5–20 m diameter) that S2 misses
- Multi-temporal compositing (median, percentiles) reduces noise and captures seasonal dynamics
- PS + S2 fusion is underexplored for seagrass — another publication gap
- Biomass regression from PS (Fauzan 2021) provides a link to vegetation density for drag parameterization

### Axis 4 — From Classification to Friction Coefficient

| # | Authors (Year) | Journal | Method | Key Finding | Code? | Relevance |
|---|---|---|---|---|---|---|
| 22 | **Baptist (2005/2007)** | J. Hydraulic Res. | Analytical drag formula | Chezy = f(h_v, D, m, C_D, h); native in Delft3D | Built-in | **Essential** — core formulation |
| 23 | **Nepf (2012)** | J. Hydraulic Res. | Review: flow-vegetation interaction | Canopy-scale vs stem-scale drag; flexible blade effects | N/A | **Essential** — theoretical basis |
| 24 | **Dekker et al. (2006)** | Springer book ch. | Review: RS of seagrass | Links RS observables (reflectance, LAI) to biophysical params | N/A | **Essential** — RS-to-parameter bridge |
| 25 | Zhu et al. (2021) | JGR Oceans | Delft3D + SWAN + Baptist | Seagrass reduces flow 60%, waves 20%, sediment 85% | Described | **Very High** — closest analog to Stagnone DT |
| 26 | Shields et al. (2017) | J. Hydraulic Eng. | 4 vegetation parameterizations compared | Trachytope/Baptist >> simple Manning increase | N/A | **High** — justifies trachytope approach |
| 27 | Nakayama et al. (2020) | Water Resources Res. | Flexible SAV + non-hydrostatic | Blade reconfiguration reduces drag 30–50% | No | **Medium** — C_D calibration insight |
| 28 | **Ingrassia et al. (2024)** | Water | 2DH model of **Stagnone lagoon** | Tide + wind circulation baseline | Open access | **Very High** — Stagnone-specific! |

**Key findings — Axis 4:**
- Baptist formulation is already built into D-Flow FM via trachytopes — just needs activation
- Zhu et al. (2021) is the closest methodological analog: Delft3D + SWAN + Baptist for seasonal seagrass effects
- **Critical gap**: no paper completes the full pipeline satellite → friction map → validated hydrodynamic model — this is exactly what the Stagnone DT project can contribute
- Ingrassia et al. (2024) provides a Stagnone-specific hydrodynamic baseline for validation
- Flexible blade effects (Nakayama 2020) suggest C_D for Posidonia/Cymodocea should be lower than rigid-cylinder assumption

---

## 3. Synthesis: Top 5 Most Promising Methods

| Rank | Method | Ease (1–5) | Data (1–5) | Relevance (1–5) | Publication (1–5) | Total |
|------|--------|------------|------------|------------------|-------------------|-------|
| 1 | **RF classification + Lyzenga WCC on Sentinel-2** (Traganos/Poursanidis approach) | 5 | 5 | 5 | 3 | **18** |
| 2 | **PlanetScope multi-temporal compositing + RF** for seasonal SAV mapping | 4 | 4 | 5 | 5 | **18** |
| 3 | **Baptist trachytopes** with satellite-derived vegetation density → Delft3D FM | 3 | 4 | 5 | 5 | **17** |
| 4 | **U-Net deep learning** for Posidonia/Cymodocea segmentation from S2 | 3 | 5 | 4 | 5 | **17** |
| 5 | **Semi-analytical WCC** (Lee/HOPE adapted for S2) + benthic classification | 2 | 5 | 4 | 4 | **15** |

---

## 4. Recommended Roadmap

### Phase 1 — Quick win (weeks 1–2)
**Activate the existing roughness** in v03a:
- Add `frictioncoefficient` block to `initialFields.ini`
- Run v03a with spatially variable roughness vs uniform n=0.023
- Quantify hydrodynamic sensitivity (water levels, velocities at obs points)

### Phase 2 — Improved classification (weeks 3–6)
**RF + Lyzenga WCC on Sentinel-2** (Method #1):
- Apply Lyzenga depth-invariant index to remove water column effect
- Train RF on manually digitized training polygons (from high-res imagery / UAV)
- Compare OA/kappa with current threshold approach
- Generate improved roughness XYZ

### Phase 3 — PlanetScope temporal analysis (weeks 5–8)
**Multi-temporal PlanetScope** (Method #2):
- Download summer 2024/2025 PS time series over Stagnone
- Compute temporal composites (median NDVI, percentiles)
- Train RF on composite features → seasonal SAV maps
- Assess resolution gain (3 m vs 10 m) for Posidonia matte delineation

### Phase 4 — Baptist trachytopes (weeks 7–10)
**From classification to physics-based friction** (Method #3):
- Define trachytope classes: bare (n=0.020), sparse Cymodocea (h_v=0.15 m, m=800 stems/m², C_D=1.0), dense Posidonia (h_v=0.5 m, m=500 stems/m², C_D=0.8)
- Create `.ttd` and `.arl` files from satellite classification
- Enable `trtRou = Y` in MDU
- Compare Baptist-based results with Manning-only

### Phase 5 — Publication (weeks 8–12)
- Write manuscript targeting Remote Sensing of Environment or Ecological Modelling
- Novelty: first full pipeline satellite → friction → validated 3D hydrodynamic model in a Mediterranean lagoon

---

## 5. Data Acquisition Checklist

- [ ] Sentinel-2 L2A: 5–10 cloud-free summer scenes (2024–2025) via Copernicus CDSE STAC
- [ ] PlanetScope: request time series Jun–Sep 2024 and 2025 via institutional access
- [ ] Training polygons: digitize ~50 polygons per class from Google Earth / UAV if available
- [ ] Field validation: coordinate with local partners for ground-truth transects (optional but ideal)
- [ ] Ingrassia et al. (2024) field data: contact authors for Stagnone observation time series

---

## References

### Key Classics
1. Baptist, M.J. et al. (2007). On inducing equations for vegetation resistance. *J. Hydraulic Res.*, 45(4), 435–450. DOI: 10.1080/00221686.2007.9521782
2. Dekker, A. et al. (2006). Remote sensing of seagrass ecosystems. In *Seagrasses: Biology, Ecology and Conservation*, Springer. DOI: 10.1007/978-1-4020-2983-7_15
3. Lee, Z. et al. (1998). Hyperspectral remote sensing for shallow waters. I. *Applied Optics*, 37(27), 6329–6338. DOI: 10.1364/AO.37.006329
4. Lee, Z. et al. (1999). Hyperspectral remote sensing for shallow waters. II. *Applied Optics*, 38(18), 3831–3843. DOI: 10.1364/AO.38.003831
5. Lyzenga, D.R. (1978). Passive remote sensing techniques for mapping water depth and bottom features. *Applied Optics*, 17(3), 379–383. DOI: 10.1364/AO.17.000379
6. Lyzenga, D.R. et al. (2006). Multispectral bathymetry using a simple physically based algorithm. *IEEE TGRS*, 44(8), 2251–2259. DOI: 10.1109/TGRS.2006.872909
7. Nepf, H.M. (2012). Hydrodynamics of vegetated channels. *J. Hydraulic Res.*, 50(3), 262–279. DOI: 10.1080/00221686.2012.696559

### Recent (2020–2025)
8. Caballero, I. & Stumpf, R.P. (2020). Routine shallow bathymetry with Sentinel-2. *Remote Sensing*, 12(3), 451. DOI: 10.3390/rs12030451
9. Carlson, D.F. et al. (2023). Mapping intertidal macroalgal blooms with PlanetScope time series. *Remote Sens. Environ.*, 295, 113654.
10. Fauzan, M.A. et al. (2021). PlanetScope for seagrass above-ground biomass. *ISPRS Archives*, XLIII-B3-2021, 181–186.
11. Ha, N.T. et al. (2020). Ensemble ML for seagrass mapping with Sentinel-2. *Remote Sensing*, 12(3), 355. DOI: 10.3390/rs12030355
12. Ingrassia, E. et al. (2024). Hydrodynamic modelling in the Stagnone Lagoon. *Water*, 16(18), 2602. DOI: 10.3390/w16182602
13. Kovacs, E.M. et al. (2022). Multi-sensor seagrass mapping comparison. *Remote Sens. Letters*, 13(7), 686–696.
14. Languille, B. et al. (2023). Deep learning for Mediterranean seagrass. *Remote Sens. Environ.*, 296, 113753.
15. Li, J. et al. (2021). Automated global shallow water bathymetry on GEE. *Remote Sensing*, 13(8), 1469. DOI: 10.3390/rs13081469
16. Lyons, M.B. et al. (2020). Global coral reef mapping with PS+S2. *Remote Sens. Ecol. Conserv.*, 6(4), 557–568.
17. Martin, C. et al. (2022). Seagrass mapping with deep learning. *Ecol. Indicators*, 142, 109263.
18. Nakayama, K. et al. (2020). SAV motion in hydrodynamic models. *Water Resources Res.*, 56(8), e2020WR027369.
19. Poursanidis, D. et al. (2019). Sentinel-2 for coastal habitat + SDB. *J. Appl. Earth Obs.*, 80, 58–70. DOI: 10.1016/j.jag.2019.03.012
20. Shields, F.D. et al. (2017). Vegetation in 2D hydrodynamic models. *J. Hydraulic Eng.*, 143(8), 02517002.
21. Traganos, D. & Reinartz, P. (2018). Mediterranean seagrass with Sentinel-2. *Mar. Poll. Bull.*, 134, 197–209. DOI: 10.1016/j.marpolbul.2017.06.075
22. Traganos, D. et al. (2018). Seagrass mapping on GEE. *Remote Sensing*, 10(8), 1227. DOI: 10.3390/rs10081227
23. Traganos, D. et al. (2022). Mediterranean-wide seagrass mapping. *Front. Mar. Sci.*, 9, 871799. DOI: 10.3389/fmars.2022.871799
24. Ventura, D. et al. (2018). UAV mapping of *P. oceanica*. *Remote Sensing*, 10(9), 1331.
25. Wang, Y. et al. (2024). Large-scale benthic reflectance retrieval. *ISPRS J. P&RS*, 210, 160–179.
26. Wei, J. et al. (2020). Temporal-variation SDB. *Remote Sens. Environ.*, 250, 112035.
27. Wicaksono, P. & Lazuardi, W. (2018). PlanetScope for benthic habitat mapping. *Int. J. Remote Sensing*, 39(17), 5739–5765.
28. Zhu, Q. et al. (2021). Seasonal seagrass effects with Delft3D. *JGR Oceans*, 126, e2020JC016547.

---

*Note: Papers by Languille (2023), Carlson (2023), and Martin (2022) require DOI verification. All other DOIs have been cross-referenced.*
