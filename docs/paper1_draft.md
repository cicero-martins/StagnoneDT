# Paper 1 — Working Draft

**Working title:** Wind-driven three-dimensional circulation in a shallow vegetated lagoon: model validation with Lagrangian drifters and the influence of seagrass roughness and wave coupling

**Target journal:** Estuarine, Coastal and Shelf Science (ECSS)

**Citation style:** Author–year (Harvard)

---

## 1. Introduction

Coastal lagoons are among the most productive coastal environments on Earth: their shallow, semi-enclosed geometry concentrates fisheries and biodiversity along roughly 13% of the global shoreline (Carrasco et al., 2016; Kjerfve, 1994), while making these systems acutely sensitive to the atmospheric and tidal forcing that drives water exchange and renewal. In the Mediterranean basin, where tidal amplitudes rarely exceed 0.3 m, the balance among tidal oscillations, wind stress, and seiche phenomena varies considerably among systems, yet wind consistently emerges as a significant driver of horizontal exchange and a key modulator of the residence times and salinity gradients that condition benthic habitat (Niedda and Greppi, 2007; Umgiesser et al., 2014). The presence of dense submerged vegetation, principally *Posidonia oceanica* (L.) Delile and *Cymodocea nodosa* (Ucria) Ascherson along Mediterranean shores, introduces a further layer of complexity: seagrass canopies attenuate incident wave energy (Infantes et al., 2012) and extract momentum from the mean flow through canopy drag, modifying near-bed turbulence and the vertical velocity structure (Nepf, 2012). As global seagrass extent continues to decline at accelerating rates (Waycott et al., 2009), understanding how circulation controls residence times, dispersal, and habitat connectivity in vegetated coastal systems has become an urgent scientific and management priority. Addressing it requires circulation models that accurately reproduce transport pathways rather than water levels alone, and this distinction makes Lagrangian validation essential: by tracking the cumulative separation between simulated and observed drifter trajectories over time, the Lagrangian skill score provides a direct and discriminating measure of model accuracy that conventional scalar metrics cannot replicate (Liu and Weisberg, 2011; Révelard et al., 2021).

The *Stagnone di Marsala*, on the north-western coast of Sicily, offers a natural laboratory for these questions. The lagoon extends approximately 11 km in the north–south direction and 2.5 km east–west, enclosing a surface area of roughly 2200 ha between the mainland and the elongated Isola Grande (De Marchis et al., 2012). Its mean water depth is approximately 0.95 m, ranging from a few tens of centimetres over the northern intertidal flats to a maximum of about 3 m near the southern inlet, placing it firmly in the class of very shallow coastal systems in which the depth-averaging assumption is, a priori, difficult to justify. Hydrodynamic exchange with the open Mediterranean is mediated by two mouths of strongly contrasting geometry: a narrow northern inlet (~400 m wide, 0.30–0.40 m deep) whose shallow sill severely restricts tidal exchange, partially mitigated by a historically dredged channel, and a wide southern inlet (~2900 m wide, 1.0–1.5 m deep) that controls the bulk of mass transfer (De Marchis et al., 2012; Ciraolo and De Marchis, 2009). The lagoon supports no significant freshwater input, and its bottom is colonised by *P. oceanica* in the central and southern basin and by *C. nodosa* in the shallower northern reaches, with shoot densities reaching 500–1200 plants m⁻² (Ciraolo et al., 2009a). Designated as a *Riserva Naturale Orientata* and a Natura 2000 site, the Stagnone hosts recognised populations of protected flora and fauna. Despite this status, long-term satellite monitoring has documented a 75% reduction in *P. oceanica* meadow extent over the past two decades (Maltese et al., 2025), underscoring the need to understand the hydrodynamic processes that govern conditions within this enclosed basin.

The tidal regime is microtidal, with free-surface amplitudes of the order of 0.25 m dominated by semi-diurnal harmonics (Di Marca et al., 2009). In the absence of riverine input and with weak tidal forcing, circulation is driven almost exclusively by tidal oscillations and wind stress. Field experiments and 3D numerical modelling conducted by De Marchis et al. (2012) during a July 2006 campaign showed that tidal action dominates north–south exchange, while wind is the controlling agent of east–west currents and, critically, generates pronounced vertical recirculation structures entirely absent in tide-only simulations. This established that vertical velocity shear between wind-driven surface drift and near-bed return flow is quantitatively significant even at sub-metre depths, and that the tendency towards hypersaline conditions in summer (La Loggia et al., 2004) adds a baroclinic component that reinforces stratification in the vertical.

Prior numerical investigations of the Stagnone have employed both depth-averaged and three-dimensional approaches, each appropriate to the research objective pursued. La Loggia et al. (2004) and Di Marca et al. (2009) applied 2D depth-averaged models to characterise tidal flushing, residence times, and turbidity dynamics, yielding useful insight into the basin-scale water budget and the role of biological productivity in light attenuation. Ciraolo et al. (2009a) demonstrated through particle tracking the sensitivity of simulated trajectories to the assumed velocity field, highlighting the importance of current accuracy for transport prediction. De Marchis et al. (2012) showed that resolving the vertical dimension is necessary to reproduce wind-driven recirculation: their 3D non-hydrostatic finite-volume model, validated against simultaneous velocity and water-level measurements at multiple stations, achieved substantially better agreement with observed east–west currents than any depth-averaged simulation. More recently, Ingrassia et al. (2024) returned to a 2D unstructured-mesh framework (MIKE 21) and conducted systematic sensitivity tests of bed friction, varying the Gauckler–Strickler coefficient uniformly across the lagoon for different vegetation scenarios; the value Ks = 20 m^(1/3) s⁻¹ was identified as most representative for the vegetated basin, yielding Nash–Sutcliffe efficiencies up to 0.92 for water level. The authors noted that the 2D approximation remains adequate for large-scale water-level budgeting while acknowledging reduced predictive skill for horizontal velocity, particularly in the northern, shallower sub-basin.

Building on these foundations, the present study addresses two aspects that have not yet been incorporated jointly into a Stagnone circulation model. The first is wave–current coupling: spectral ocean waves generated in the western Sicilian channel can penetrate both inlets and interact with the mean flow, altering near-bed turbulence and the effective drag experienced by the seagrass canopy; this mechanism has been shown to be non-negligible in comparably shallow Mediterranean lagoons [REF-wave-current-lagoon] but has not been included in previous Stagnone simulations. The second is the combined use of spatially distributed vegetation roughness derived directly from satellite imagery, rather than assumed uniform, and Lagrangian drifter observations as a validation target. Together, these extensions allow the relative contributions of three-dimensional dynamics, wave forcing, and seagrass heterogeneity to transport skill to be quantified within a controlled process-attribution framework.

We apply the three-dimensional unstructured-mesh hydrodynamic solver Delft3D Flexible Mesh (D-Flow FM; Kernkamp et al., 2011) coupled online with the spectral wave model SWAN (Booij et al., 1999), driven by ERA5 reanalysis meteorological forcing and CMEMS Mediterranean physical reanalysis boundary conditions, over a nine-day period in July 2025. Spatially variable seagrass resistance is parametrised through Baptist (2007) trachytopes derived from a supervised random-forest classification of PlanetScope multispectral imagery acquired in August 2023, following the mapping methodology of Maltese et al. (2025). Model performance is assessed against in-situ water level time series at four stations and against GPS surface drifter trajectories from a field campaign concurrent with the simulation period, using the Liu–Weisberg Lagrangian skill score and endpoint proximity as metrics. A four-member ensemble (baseline with uniform roughness and no morphodynamics; seagrass roughness only; waves only; full physics) attributes the observed improvements in Lagrangian skill to individual physical mechanisms.

The paper is organised as follows. Section 2 describes the study area and its hydrodynamic setting. Section 3 presents the observational datasets, the modelling framework, and the seagrass mapping and drifter validation methodology. Section 4 reports validation results for water level and Lagrangian trajectories and the process-attribution experiment. Section 5 discusses the implications for wind-driven vertical structure and seagrass–flow interaction. Section 6 provides conclusions.

---

## 2. Study Area

The *Stagnone di Marsala* is located on the north-western coast of Sicily, sheltered from the western Sicilian channel by Isola Grande, an elongated barrier island running parallel to the mainland coast (Fig. 1). The enclosed basin extends approximately 11 km in the north–south direction and 2.5 km east–west, enclosing a total surface area of roughly 2200 ha (De Marchis et al., 2012). Two geomorphologically distinct sub-basins are separated by a *Posidonia oceanica* barrier reef (La Loggia et al., 2004): the northern sub-basin, with a mean depth of approximately 1 m and extensive intertidal flats, and the deeper southern sub-basin, with a mean depth of approximately 2 m and a maximum of about 3 m near the main inlet. Three islands punctuate the interior: the Phoenician archaeological site of Mothia in the south-central basin, and the smaller islands of Santa Maria and Scola in the central reaches (Ciraolo and De Marchis, 2009). Salt pans (*saline*) are present on both margins of the lagoon: extensive historic saltworks occupy the western barrier island (Isola Grande), with additional pans along the eastern mainland shore in the area facing Mothia (Basso et al., 2008); they constitute a distinctive shallow intertidal habitat within the lagoon system.

Hydrodynamic exchange with the open sea occurs through two morphologically distinct inlets. The northern inlet (approximately 400 m wide, 0.30–0.40 m deep) is a highly restricted passage whose tidal prism is severely limited by its shallow sill; a historically dredged channel (20 m wide, 1 m deep) partially compensates this restriction (Ciraolo and De Marchis, 2009). The wide southern inlet (approximately 2900 m wide, 1.0–1.5 m deep) provides the primary pathway for mass transport and water mixing between the lagoon and the open sea (Ciraolo and De Marchis, 2009). The tidal regime is microtidal, with free-surface amplitudes of approximately 0.30 m dominated by semi-diurnal harmonics (La Loggia et al., 2004). In the absence of riverine input, weak tidal exchange combined with high summer evaporation drives a pronounced salinity gradient: annual lagoon-wide salinity spans 33–46 psu (Basso et al., 2008), with peak summer values approaching 48 psu in the more confined northern sub-basin, contrasting with near-marine conditions near the southern inlet (Mancuso et al., 2023). Wind forcing dominates east–west circulation within the basin, while tidal exchange controls the north–south component (Ciraolo and De Marchis, 2009; De Marchis et al., 2012).

The seagrass mosaic covers the majority of the lagoon floor. *Posidonia oceanica* occupies the central and southern portions of the basin, forming both continuous meadows and characteristic atoll patterns (10–20 m in diameter) that grade into reef formations oriented along the north–south axis; *Cymodocea nodosa* prevails in the shallower northern reaches, with *Caulerpa prolifera* replacing *P. oceanica* locally where hydrodynamic and sediment conditions deteriorate (La Loggia et al., 2004; Ciraolo and De Marchis, 2009). In Mediterranean meadows of this type, *P. oceanica* areal densities typically range from 500 to 1200 plants m⁻² (Ciraolo et al., 2009a). The spatial distribution of submerged vegetation was mapped from satellite imagery by Ciraolo and Maltese (2006); the roughness parametrisation in this study uses the updated classification by Maltese et al. (2025) as the base map, applied to the 2023 epoch (see Section 3.4). The lagoon is designated both as a *Riserva Naturale Orientata* and as a Natura 2000 site, reflecting the conservation importance of these meadows, which have nevertheless declined by approximately 75% in extent over the past two decades (Maltese et al., 2025).

The observational dataset used in this study was collected during July 2025 (Fig. 1). Water level was recorded at three stations: BocaNord (BN) at the northern inlet, BocaSud (BS) near the southern inlet, and AltaVilaEst (AE) on the eastern flank of the central basin. Wind speed and direction and atmospheric pressure were measured at two stations: AE (which also carries a water-level gauge and a water temperature sensor) and Mulino, a dedicated meteorological station located near the salt pans in the central-northern area. Water levels at BN, BS, and AE serve as the primary validation targets for the hydrodynamic model (Section 3.5). Open-sea boundary conditions are prescribed from CMEMS Mediterranean physical reanalysis products (Section 3.3). Offshore model performance is assessed against the tidal gauge on Marettimo island (JRC TAD 658), approximately 15 km to the west, which provides a free-surface reference uninfluenced by lagoonal dynamics. GPS-tracked surface drifters were released in the lagoon interior over a sub-period coinciding with the simulation window; their trajectories form the basis of the Lagrangian validation (Section 3.5).

---

## 3. Data and Methods

### 3.1 Hydrodynamic model

*(to be drafted)*

### 3.2 Wave model and coupling

*(to be drafted)*

### 3.3 Boundary and atmospheric forcing

*(to be drafted)*

### 3.4 Seagrass roughness parametrisation

*(to be drafted)*

### 3.5 Observational data and validation metrics

*(to be drafted)*

---

## 4. Results

### 4.1 Water level validation

*(to be drafted)*

### 4.2 Lagrangian drifter validation

*(to be drafted)*

### 4.3 Process attribution experiment

*(to be drafted)*

### 4.4 Three-dimensional flow structure

*(to be drafted)*

---

## 5. Discussion

*(to be drafted)*

---

## 6. Conclusions

*(to be drafted)*

---

## References (working list)

### Confirmed

- Basso, D., Bernasconi, M.P., Robba, E., Marozzo, S. (2008). Environmental evolution of the Marsala Sound, Sicily, during the last 6000 years. *Journal of Coastal Research*, 24(1), 177–197. doi:10.2112/05-0619.1
- Baptist, M.J., Babovic, V., Rodríguez Uthurburu, J., Keijzer, M., Uittenbogaard, R.E., Mynett, A., Verwey, A. (2007). On inducing equations for vegetation resistance. *Journal of Hydraulic Research*, 45(4), 435–450.
- Booij, N., Ris, R.C., Holthuijsen, L.H. (1999). A third-generation wave model for coastal regions. *Journal of Geophysical Research: Oceans*, 104(C4), 7649–7666.
- Carrasco, A.R., Ferreira, O., Roelvink, D. (2016). Coastal lagoons and rising sea level: a review. *Earth-Science Reviews*, 154, 356–368. doi:10.1016/j.earscirev.2015.11.001 *(verify DOI)*
- Ciraolo, G. and De Marchis, M. (2009). Wind- and tide-induced currents in the Stagnone Lagoon (Sicily). *13th Workshop on Physical Processes in Natural Waters*, Palermo, 1–4 September 2009.
- Ciraolo, G. *et al.* (2009a). *(particle tracking paper — full citation to be confirmed from Ciraolo2009_PartTrackingAquaticVegMeadow.pdf)*
- De Marchis, M., Ciraolo, G., Nasello, C., Napoli, E. (2012). Wind- and tide-induced currents in the Stagnone lagoon (Sicily). *Environmental Fluid Mechanics*, 12(1), 1–20. doi:10.1007/s10652-011-9225-0
- Di Marca, A. *et al.* (2009). *(turbidity/Stagnone paper — full citation to be confirmed from DiMarca2009_TurbidityStagnone.pdf)*
- Infantes, E., Orfila, A., Simarro, G., Luhar, M., Terrados, J., Nepf, H. (2012). Effect of a seagrass (*Posidonia oceanica*) meadow on wave propagation. *Marine Ecology Progress Series*, 456, 63–72. doi:10.3354/meps09754
- Ingrassia, E., Nasello, C., Ciraolo, G. (2024). Hydrodynamic modelling in a Mediterranean coastal lagoon — the case of the Stagnone Lagoon, Marsala. *Water*, 16(18), 2602. doi:10.3390/w16182602
- Kernkamp, H.W.J., Van Dam, A., Stelling, G.S., de Goede, E.D. (2011). Efficient scheme for the shallow water equations on unstructured grids with application to the Continental Shelf. *Ocean Dynamics*, 61(8), 1175–1188.
- La Loggia, G. *et al.* (2004). *(full citation to be confirmed from LaLoggia2004 PDF)*
- Liu, Y., Weisberg, R.H. (2011). Evaluation of trajectory modeling in different dynamic regions using normalized cumulative Lagrangian separation. *Journal of Geophysical Research: Oceans*, 116, C09013. doi:10.1029/2010JC006837
- Mancuso, F.P., Bernardeau-Esteller, J., Spinelli, M., Sarà, G., Ruiz, J.M., Calvo, S., Tomasello, A. (2023). Life on the edge: Adaptations of *Posidonia oceanica* to hypersaline conditions in a Mediterranean lagoon system. *Environmental and Experimental Botany*, 210, 105320. doi:10.1016/j.envexpbot.2023.105320
- Maltese, A. *et al.* (2025). *(SPIE 2025 — full citation to be confirmed from 1366602_SPIE_2025.pdf)*
- Nepf, H.M. (2012). Flow and transport in regions with aquatic vegetation. *Annual Review of Fluid Mechanics*, 44, 123–142. doi:10.1146/annurev-fluid-120710-101048
- Niedda, M., Greppi, M. (2007). Tidal, seiche and wind dynamics in a small lagoon in the Mediterranean Sea. *Estuarine, Coastal and Shelf Science*, 74, 21–30. doi:10.1016/j.ecss.2007.03.022
- Révelard, A., Reyes, E., Mourre, B., Hernández-Carrasco, I., Rubio, A., Lorente, P., De Lera Fernández, C., Mader, J., Álvarez-Fanjul, E., Tintoré, J. (2021). Sensitivity of skill score metric to validate Lagrangian simulations in coastal areas: recommendations for search and rescue applications. *Frontiers in Marine Science*. doi:10.3389/fmars.2021.630388
- Umgiesser, G., Ferrarin, C., Cucco, A., De Pascalis, F., Bellafiore, D., Ghezzo, M., Bajo, M. (2014). Comparative hydrodynamics of ten Mediterranean lagoons by means of numerical modeling. *Journal of Geophysical Research: Oceans*, 119, 2212–2226. doi:10.1002/2013JC009512
- Waycott, M. *et al.* (2009). Accelerating loss of seagrasses across the globe threatens coastal ecosystems. *Proceedings of the National Academy of Sciences*, 106(30), 12377–12381. doi:10.1073/pnas.0905620106
