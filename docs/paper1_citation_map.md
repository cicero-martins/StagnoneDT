# Mapa de citações do Paper 1 (manuscript_v3)

Cada referência citada no corpo e no Material Suplementar aparece com a frase
que a cita, sua posição no PDF compilado e o trecho da fonte que sustenta a
afirmação, com a página do PDF da pasta `reference/papers/`. As posições do
corpo são página e número de linha do `lineno` de `manuscript_v3/main.pdf`, no
início da frase. O suplementar não tem numeração de linhas, então a posição é
página e seção de `supplementary.pdf`. As posições valem para a compilação de
25 nov. 2026.

Todos os DOIs do `references.bib` foram conferidos no Crossref (título, ano,
volume, páginas e primeiro autor). Scripts:
`scratchpad/cite_sentences.py` (frases e posições) e
`scratchpad/crossref_check.py` (DOIs), ambos descartáveis.

Legenda de situação:

- **OK**: o trecho citado sustenta a afirmação como escrita.
- **Parcial**: a fonte sustenta o tema, mas não toda a afirmação.
- **Não verificado**: não há PDF na pasta `reference/papers/`. O DOI foi
  conferido no Crossref.

## Pontos de atenção

1. **Corrigidos em 25 nov. 2026, no `.bib`.**
   - Carrasco et al. 2016: o DOI `10.1016/j.earscirev.2015.11.001` resolvia
     para Bentley et al., sobre o sistema do Mississippi. O correto é
     `10.1016/j.earscirev.2015.11.007`.
   - Ciraolo, Ferreri e La Loggia 2006: o DOI `…2006.9521674` resolvia para
     Liang et al., sobre advecção caótica. O correto é `…2006.9521675`.
   - Ingrassia et al. 2024: o primeiro autor é Emanuele, não Elisa (PDF e
     Crossref).
   - La Loggia et al. 2004 ganhou o DOI `10.1080/02757540410001689786`.
   - Kjerfve 1994 saiu. Em seu lugar entrou Newton et al. 2018 (DOI
     `10.1016/j.jnc.2018.02.009`, conferido no Crossref), que sustenta pesca e
     biodiversidade. O PDF, de acesso aberto, está em
     `reference/papers/Newton2018_ecosystemServicesCoastalLagoons.pdf`.
2. **Corrigidos em 25 nov. 2026, no texto.**
   - Os "2200 ha" de Ciraolo e De Marchis 2009 são a área da **reserva
     natural**, não da laguna. A Área de Estudo agora dá cerca de 20 km², a
     soma das sub-bacias de La Loggia et al. 2004 (14 e 6 km²).
   - La Loggia 2004 dá excursão de maré de 30 cm, não amplitude, e não fala de
     constituintes. A dominância semidiurna vem de De Marchis et al. 2012.
   - Ciraolo e De Marchis 2009 põem Santa Maria no norte, não no centro. Os
     atóis de *P. oceanica* ficam na sub-bacia norte, segundo La Loggia 2004.
   - Umgiesser et al. 2014 dizem que o vento contribui para a troca só em
     lagunas com mais de uma boca. O texto dizia que o vento "consistently
     drives" a troca.
   - Di Marca 2009 é experimento de campo, e Ciraolo et al. 2009a é rastreamento
     de partículas sobre dossel artificial em flume. Os dois apareciam como
     "estudos numéricos do Stagnone".
   - Ingrassia et al. 2024 não testam "cenários de vegetação". Calibram um
     coeficiente de Gauckler–Strickler uniforme contra nível e velocidade.
   - Liu e Weisberg 2011 e Révelard et al. 2021 não afirmam que o nível
     restringe pouco o transporte. A atribuição saiu da Introdução e do §5.3.
   - Infantes et al. 2012 mediram a 6,5–16,5 m de profundidade. O "at this
     scale" do §5.2 sugeria a escala da laguna e saiu.
   - Ciraolo et al. 2006: a espessura do dossel defletido vai de cerca de 0,2 a
     0,65 da profundidade, e as corridas mais rasas chegam a encher a coluna
     (S4).
   - §5.4: os parâmetros de *P. oceanica* vêm de flumes com **plantas
     artificiais** (Ciraolo 2006; Prinos 2010), não de "outras pradarias".
   - Turschwell et al. 2021 associam as perdas rápidas a pesca demersal
     destrutiva e qualidade da água, não a desenvolvimento costeiro (que é o
     fator mais citado em Dunic et al. 2021). A Introdução agora diz "destructive
     demersal fishing and degraded water quality".
   - Mogé et al. 2019 dão como regra prática **mais de ~25 000 células por
     partição** (p. 15), contadas sobre as camadas nos casos 3D, e um limite de
     escalabilidade do PETSc abaixo de ~20 000 incógnitas (p. 4). O S1 dizia que
     3000 células por partição ficavam "acima de alguns milhares". Agora diz
     que as ~30 000 células por partição nas dez camadas ficam acima da regra
     prática, e que o sistema de nível d'água, com ~3000 incógnitas por partição,
     fica abaixo do limite do PETSc.
   - §5.2: Morote-Sánchez et al. 2025 só sustentam ressuspensão por ondas em
     tempestades. O "waves govern bed stress and sediment resuspension" virou
     "wind waves set the bed stress over the flats and resuspend sediment during
     storms", que cobre Carniello (planícies de maré) e Morote (tempestades).
3. **Ainda em aberto.**
   - §5.1 (p. 17, l. 257): Nepf 2012 sustenta que o perfil sobre leito rugoso
     ou dossel esparso continua logarítmico. O limite da razão
     superfície/fundo "well below the values obtained here" é inferência do
     manuscrito, não de Nepf.
   - De Marchis et al. 2012: o Crossref registra 2011 (publicação online), e o
     volume 12 é de 2012. O `.bib` mantém 2012, o ano do volume.
4. **Conferidos só pelo resumo:** Dunic 2021, Turschwell 2021, Nepf e Vivoni
   2000, Luhar e Nepf 2011 e Booij 1999.
5. **Conferido por fonte secundária:** Battjes e Stive 1985 não está na
   pasta (o arquivo `BattjesStive1985_...pdf` contém Battjes e Janssen 1978). O
   γ = 0,73 foi conferido na documentação técnica do SWAN, que o atribui a
   Battjes e Stive.

## Por referência

### Basso et al. 2008

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 3, l. 54 | "...salt pans occupy both margins, on Isola Grande and along the mainland shore facing Mothia" | p. 1: "channels, now closed by saltworks, that cut the present-day Isola Grande into islets"; p. 3: "one of the saltworks bordering the SM" | Parcial (a margem continental em frente a Mothia não é nomeada) |
| p. 4, l. 66 | "...annual values spanning 33–46" | p. 2: "high annual variability of both temperature and salinity, ranging respectively from 12C to 29C and from 33 to 46" | OK |

### Battjes e Janssen 1978

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 6, l. 101 | "...with depth-induced breaking" | título: "Energy loss and set-up due to breaking of random waves" | OK |
| S p. 3, S2 (tabela) | "Depth-induced breaking, Battjes and Janssen (1978), α = 1.0" | idem | OK |

### Battjes e Stive 1985

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| S p. 3, S2 (tabela) | "γ = 0.73 [...] the mean value of Battjes and Stive (1985) over laboratory and field data" | sem o artigo; documentação técnica do SWAN (Cycle III 40.51), p. 31: "Battjes and Stive (1985) re-analyzed wave data of a number of laboratory and field experiments and found values for the breaker parameter varying between 0.6 and 0.83 [...] with an average of 0.73" | OK (por fonte secundária) |

### Beudin et al. 2017

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 17, l. 263 | "...three-dimensional models that resolve the drag over the plant height have reproduced the same partition [...] in coupled wave, flow and vegetation systems" | título: "Development of a coupled wave-flow-vegetation interaction model"; p. 5: "The flow structure displays an S-shape with an inflection point near the top of the canopy" | OK |

### Booij, Ris e Holthuijsen 1999

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 6, l. 101 | "Waves were computed with SWAN" | resumo: "A third-generation numerical wave model to compute random, short-crested waves in coastal regions with shallow water and ambient currents (Simulating Waves Nearshore (SWAN))" | OK (resumo) |

### Bouws e Komen 1983

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| S p. 3, S2 (tabela) | "JONSWAP bottom friction, 0.067 m² s⁻³ [...] value for wind sea rather than the lower value appropriate to swell" | p. 1656: "c₂ = 0.067 m² s⁻³ [...] nearly twice as large as the mean JONSWAP value (0.038)"; p. 1655: 0,038 é "the JONSWAP result for swell dissipation" (PDF escaneado, lido como imagem) | OK |

### Carniello et al. 2011

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 3, l. 32 | "Waves, which in comparably shallow Mediterranean lagoons alter bed stress and mobilise sediment" | título: "Modeling wind waves and tidal flows in shallow micro-tidal basins"; resumo: "sediment resuspension over tidal flats is mainly caused by wind-wave induced shear stresses"; caso: laguna de Veneza | OK |
| p. 18, l. 286 | "...wind waves set the bed stress over the flats and resuspend sediment during storms" | idem | OK |
| p. 19, l. 334 | "Waves govern the sediment dynamics of comparably shallow micro-tidal basins" | idem; resumo: "the crucial role of wind waves in shallow tidal basins" | OK |

### Carrasco et al. 2016

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 1 | "Coastal lagoons occupy roughly 13% of the global shoreline and concentrate fisheries and biodiversity" | p. 2: "About 32,000 lagoons are reported along 13% of the world's coastline" | OK para os 13% (pesca e biodiversidade vêm de Newton et al. 2018) |

### Cancemi et al. 2002

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 8 (Tabela 1) | "...with the shoot density also bracketed by" | resumo: "shoot density (the latter, between 925 ± 323 and 1925 ± 267 shoots m⁻²)" | OK |
| S p. 8, S4 | "...the Mediterranean field range of 925 to 1925 m⁻²" | idem | OK |

### Ciraolo et al. 2009a

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 27 | "...particle tracking through the flow measured over an artificial P. oceanica canopy has shown that gaps in a meadow can trap suspended particles" | resumo: "the flow field measured in past experiments is used for studying the behaviour of a gap in an artificial Posidonia oceanica canopy"; "These discontinuities [...] can actually act as particle traps" | OK (PDF sem camada de texto; lido na página renderizada) |
| p. 4, l. 74 | "P. oceanica reaches 1000–1200 plants m⁻² in Mediterranean meadows of this type" | resumo: "the meadow areal density can reach 1000–1200 plants per square metre" | OK |

### Ciraolo e De Marchis 2009

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 3, l. 50 | "...the mean depth of the whole being about 0.95 m" | resumo: "shallow water (the mean depth is about 95 cm)" | OK |
| p. 3, l. 54 | "Mothia [...] in the centre, Santa Maria in the north" | p. 3: "Two main islands, Motia and Santa Maria, are located in the center and in the northern part of the lagoon respectively" | OK |
| p. 4, l. 60 | Dimensões das bocas, canal dragado e a boca sul como via principal | p. 2: "The northern mouth (400 m wide, 0.3–0.4 m deep)"; p. 3: "a 20 m wide, 1 m deep channel was dredged"; "the southern mouth, [...] about 2900 m and depth of about 1.0–1.50 m, ensures the transport of mass" | OK |
| p. 4, l. 64 | "Wind drives the east–west circulation within the basin and tidal exchange its north–south component" | resumo: "the tidal forces dominate in the North-South direction, whereas wind plays a fundamental role in the East-West water currents" | OK |
| p. 4, l. 70 | "P. oceanica occupying the central and southern basin and C. nodosa the north" | p. 3: "the northern part is characterized by the presence of Cymodocea nodosa, while the central-southern region is covered by Posidonia oceanica" | OK |

### Ciraolo, Ferreri e La Loggia 2006

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 8 (Tabela 1) | Valores de *P. oceanica* exceto altura de dossel | p. 3: plantas de "six strips [...] 1 cm wide"; densidade de 682 plantas/m², "within the range of the most frequent values met in nature (500–1000 plants/m²)" | OK |
| p. 19, l. 314 | "...flume experiments with artificial plants built to reproduce its leaves, the first of them undertaken for this lagoon" | p. 2: "several field studies [...] in particular studying the 'Stagnone' at Marsala [...] Within these studies a special experimental research on flow resistance of P. oceanica has been started"; "a flume where the plants were artificially reproduced by plastic strips" | OK |
| p. 19, l. 325 | "The reconfiguration measured [...] is expressed as a friction factor" | resumo: "a simple flow resistance law [...] expresses Darcy–Weisbach's friction factor as a function only of a particular Reynolds number" | OK |
| S p. 7, S4 | "...about six leaves per shoot" | p. 3: plantas artificiais de seis tiras | OK |
| S p. 7, S4 | "...deflected canopy thickness between about 0.2 and 0.65 of the water depth, apart from the shallowest runs" | Tabela 1, coluna k/h₁: 0,12 a 1,00, a maioria entre 0,18 e 0,65; 0,89–1,00 nas corridas 5, 14, 15 e 19 | OK |

### Ciraolo, Cox, La Loggia e Maltese 2006

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 4, l. 75 | "The submerged vegetation was first mapped from airborne hyperspectral imagery" | resumo: "to use hyperspectral MIVIS data to map the Posidonia oceanica prairies in a coastal lagoon (Stagnone di Marsala)" | OK ("first" não está na fonte, mas não há mapeamento anterior citado) |

### Dagestad et al. 2018

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 8, l. 151 | "...advected with OpenDrift" | resumo: "OpenDrift is an open-source Python-based framework for Lagrangian particle modelling" | OK (o artigo descreve Runge–Kutta de 2ª ordem, p. 6; o de 4ª ordem usado é de versão posterior do código, e a frase não o atribui ao artigo) |

### Dalrymple et al. 1984

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 6, l. 107 | "...the vegetation dissipation of Dalrymple et al. (1984)" | resumo: "a friction model for a spatial distribution of rigid vertical cylinders"; introdução: "large stands of seaweed [...] submerged trees" (PDF escaneado) | OK |
| S p. 4, S2 | "Dissipation follows Dalrymple et al. (1984) in the implementation of Suzuki et al. (2012)" | idem | OK |

### De Marchis et al. 2012

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 22 | "...resolved the vertical and found that wind drives a recirculation with a near-bed return flow even at sub-metre depths, the meadow entering through Nikuradse roughness heights assigned by seagrass class" | resumo: "the fundamental role of the wind [...] producing a strong vertical recirculation pattern"; p. 9: "three different Nikuradse roughness coefficients ks", ponderados pela cobertura de cada espécie | OK |
| p. 3, l. 50 | "The basin extends about 11 km north–south and 2.5 km east–west" | p. 3: "The lagoon is about 11 km long (in the north-south direction) and about 2.5 km width" | OK |
| p. 3, l. 54 | "...the small island of Scuola between them" | Fig. 1: "Scola island" entre Mothia e Santa Maria | OK |
| p. 4, l. 63 | "...dominated by the semi-diurnal constituent with a diurnal contribution" | p. 12: "tidal oscillations are dominated by the semi-diurnal constituent (12.4 h) with supplementary contribution of the diurnal constituent (24 h)" | OK |
| p. 4, l. 64 | Vento no eixo leste–oeste, maré no norte–sul | p. 13: "north-south velocities are quite higher than east-west ones when tide effects only are considered"; o vento aumenta a componente leste–oeste | OK |
| p. 17, l. 267 | "...established a wind-driven three-dimensional circulation with a near-bed return flow" | idem p. 2 | OK |

### Deltares 2025 (Manual de Referência Técnica do D-Flow FM)

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| S p. 8, S5 | "...with the time step limited also by the vertical fluxes" | manual da instalação (`bin/D-Flow_FM_Technical_Reference_Manual.pdf`, versão 2025, revisão 80505, a mesma do `.bib`), p. 87: "For explicit vertical advection, the time step must also be restricted by vertical transport velocities" | OK |

### Di Marca 2009

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 19 | "...measured the share of resuspension over the meadow and of lateral advection in the turbidity of the water column" | p. 2: "the effect of vegetation coverage on water column behaviour was studied with a long-continuous experiment [...] exploring the relative importance of resuspension throughout the water column in comparison of a lateral advective transport" | OK |

### Dunic et al. 2021

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 10 | "...has fallen in all seven bioregions, by 19.1% of the surveyed area since 1880" | resumo: "We found an overall trajectory of decline in all seven bioregions with a global net loss of 5602 km² (19.1% of surveyed meadow area) occurring since 1880" | OK (resumo) |

### Infantes et al. 2012

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 7 | "...whose canopies attenuate incident wave energy" | resumo: "Wave attenuation induced by the seagrass Posidonia oceanica is evaluated using field data" | OK |
| p. 18, l. 286 | "Meadows of P. oceanica attenuate waves in the field, at depths of 6.5 to 16.5 m" | p. 5: "mooring 1 (16.5 m depth); mooring 2 (12.5 m); mooring 3 (10 m) and mooring 4 (6.5 m)" | OK |

### Ingrassia, Nasello e Ciraolo 2024

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 22 | "...calibrated a depth-averaged model against water level and velocity with a uniform Gauckler–Strickler coefficient" | resumo: "a 2DH [...] unstructured mesh model, calibrated with data collected during the 2006 field campaign"; "NSE values up to 0.92 and 0.79 are reached with a Gauckler–Strickler coefficient equal to 20 m^1/3/s related to water depth and the Vy velocity component" | OK |
| p. 7, l. 132 | "...the Gauckler–Strickler coefficient of 20 m^1/3 s⁻¹ calibrated for this lagoon" | idem | OK |
| p. 17, l. 267 | "...calibrated a depth-averaged model in which an equivalent bed roughness is the consistent representation of the canopy" | idem | OK |

### Kernkamp et al. 2011

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 6, l. 89 | "...an unstructured finite-volume solver for the three-dimensional shallow-water equations" | resumo: "a shallow-water flow solver is presented, based on the finite-volume method on unstructured grids [...] estuaries, lakes and shelf breaks (3D)" | OK |

### La Loggia et al. 2004

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 19 | "...related the production of P. oceanica to water exchange computed with a depth-averaged model" | título: "Influence of hydrodynamic conditions on the production and fate of Posidonia oceanica"; p. 4: "this allows a two-dimensional hydrodynamic depth-averaged model to be applied" | OK |
| p. 3, l. 50 | Sub-bacias de 14 e 6 km², 1 e 2 m, separadas por recife | p. 3: "The northern sub-basin (14 km², mean depth 1 m) and the southern sub-basin (6 km², mean depth 2 m) are separated by a P. oceanica barrier reef" | OK |
| p. 4, l. 63 | "The tidal excursion is about 0.30 m" | p. 4: "in the Stagnone lagoon, the tidal excursion is about 30 cm" | OK |
| p. 4, l. 71 | Atóis na sub-bacia norte e substituição por *C. nodosa* e *Caulerpa* | p. 4: "P. oceanica are present in the northern sub-basin: 'atoll' patterns (10–20 m in diameter) gradually closing in reef formations"; "Where hydrodynamic conditions and sediment composition worsen for P. oceanica, the seagrass meadow is partially replaced by Cymodocea nodosa [...] and Caulerpa prolifera" | OK |

### Liu e Weisberg 2011

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 3, l. 35 | "...where drifter trajectories offer a measure of transport with skill metrics of its own" | resumo: "A new skill score is proposed based on the cumulative Lagrangian separation distances normalized by the associated cumulative trajectory lengths" | OK |
| p. 8, l. 156 | "...normalises the cumulative separation between modelled and observed positions by the observed path length" | idem | OK |

### Luhar e Nepf 2011

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 19, l. 322 | "...flexible blades reduce their effective length, and with it their drag, as the velocity increases" | resumo: "When the hydrodynamic forcing exceeds the restoring forces, the blades are pushed over by the flow, and the quadratic drag law no longer applies"; Beudin et al. 2017, p. 3, atribui a Luhar e Nepf o comprimento efetivo de lâmina | OK (resumo) |

### Maltese et al. 2025

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 4, l. 77 | "...a reduction of about 75% in the extent of the atoll and cordon formations between 2003 and 2024" | resumo: "a substantial decline in the extent of atolls and cordons, with satellite observations revealing a reduction of approximately 75% over the study period" (2003–2024) | OK |
| p. 8, l. 141 | "...following the depth-invariant approach of Maltese et al." | p. 3: "attenuation adjustments for water column effects using the Lyzenga Depth Invariant Index (DII)" | OK |
| S p. 8, S4 | "...their gradient-boosted classifier on 2 m WorldView, QuickBird and Pleiades" | p. 1: "Light Gradient Boosting Machine classification"; "WorldView, QuickBird, and Pleiades"; p. 2: "spatial resolution of 2 meters" | OK |

### Mancuso et al. 2023

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 4, l. 66 | "...summer maxima reaching about 48, the northern sub-basin being saltier than the southern" | "in summer, the lagoon can reach hypersaline conditions, with salinity reaching maximum values of about 48 psu [...] with the north sub-basin being saltier than the south sub-basin" | OK |

### Mogé et al. 2019

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| S p. 2, S1 | "...about 30 000 over the ten layers, which is above the 25 000 cells per partition [...] rule of thumb for good parallel efficiency" | p. 15: "As a rule-of-thumb, partitions should have more than ~25000 cells to get good parallel efficiency"; p. 2: o caso North_Sea_3D tem 25 vezes as células do 2D | OK |
| S p. 2, S1 | "...below the 20 000 under which they report that the linear solver stops scaling" | p. 4: "a known scaling limit of PETSc [...] for local problem sizes smaller than ~20,000 unknowns" | OK |

### Morote-Sánchez et al. 2025

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 3, l. 32 | "Waves, which in comparably shallow Mediterranean lagoons alter bed stress and mobilise sediment" | título: "Waves in a temperate, microtidal and restricted Mediterranean coastal lagoon" (Mar Menor); resumo: "wave-induced orbital velocities can mobilize sediment resuspension during extreme events" | OK |
| p. 18, l. 286 | "...resuspend sediment during storms" | resumo: "sediment resuspension is most significant during storms" | OK |

### Morris et al. 2008

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 8 (Tabela 1) | Valores de *C. nodosa* | p. 3: "width 3.8 ± 0.4 × 10⁻³ [...] the number of leaves per shoot 3.5 ± 1.1"; p. 5: altura de dossel "0.17 ± 0.02 m" | OK |
| p. 19, l. 314 | "...a flume study of plants collected in a tidal lagoon near Cádiz" | p. 2: plantas "collected from Santibáñez, Cádiz"; "a sheltered tidal lagoon" | OK |
| S p. 8, S4 | "...collected in a sheltered tidal lagoon" | idem | OK |

### Nepf 2012

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 7 | "...a drag that modifies near-bed turbulence and the vertical velocity structure" | p. 4: "the production of turbulence by the canopy exceeds the production by the bed shear over most of the flow depth" | OK |
| p. 3, l. 31 | "...acts on the shape of the velocity profile as well as on its magnitude" | p. 7: "the velocity within the canopy is always less than that over a bare bed" | OK |
| p. 7, l. 125 | "...drag per unit volume in the quadratic form of Nepf (2012)" | p. 3: "often represented by a quadratic drag law" | OK |
| p. 17, l. 257 | "A rougher bed acts through a logarithmic profile, whose surface-to-bed ratio is bounded well below the values obtained here" | resumo: "Near sparse submerged canopies, the bed roughness and near-bed turbulence are enhanced, but the velocity profile remains logarithmic" | Parcial (o limite da razão é inferência do manuscrito) |
| p. 17, l. 263 | "The reduced flow within a submerged canopy and the faster flow above it are established in laboratory flows" | p. 7, idem l. 31 | OK |

### Nepf e Vivoni 2000

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 17, l. 263 | "The reduced flow within a submerged canopy and the faster flow above it are established in laboratory flows" | resumo: flume com vegetação modelo; na parte inferior do dossel, "the momentum budget is a simple balance of vegetative drag and pressure gradient", e no topo do dossel submerso aparece uma "vertical exchange zone" com produção de turbulência por cisalhamento | Parcial (o resumo não descreve o perfil de velocidade; Nepf 2012, co-citado, sustenta a frase) |

### Newton et al. 2018

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 1 | "Coastal lagoons occupy roughly 13% of the global shoreline and concentrate fisheries and biodiversity" | resumo: lagunas "support important habitats such as wetlands, mangroves, salt-marshes and seagrass meadows, as well as a rich biodiversity"; p. 1: "Coastal lagoons occur along 13% of the coastlines of all continents"; "economic sectors such as fisheries and aquaculture" | OK |

### Niedda e Greppi 2007

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 3 | "...the balance among tide, wind stress and seiches varies from one lagoon to another" | resumo: "a free-surface oscillation with a semidiurnal period (tide) and a second order oscillation [...] (seiche). The wind has a local effect on these oscillations" | OK |

### Prinos et al. 2010

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 8 (Tabela 1) | Altura de dossel de *P. oceanica* | p. 2: plantas artificiais de "1 pair 35cm and 1 pair 55cm long" | OK |
| p. 18, l. 286 | "...and in large-scale flume experiments" | título: "Wave propagation over Posidonia oceanica: large scale experiments" | OK |
| p. 19, l. 314 | "...flume experiments with artificial plants" | p. 2: "A seagrass meadow was constructed (10.70 m long) by artificial polypropylene plants" | OK |
| S p. 7, S4 | "...adopt submergence ratios of 0.323, 0.423 and 0.500" | p. 2: "three submergence ratios hs/D equal to 0.5, 0.423 and 0.323" | OK |

### Révelard et al. 2021

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 3, l. 35 | "...skill metrics of its own" | resumo: "The Skill Score (SS), based on the Normalized Cumulative Lagrangian Separation [...] is a commonly used metric" | OK |
| p. 8, l. 156 | "...whose sensitivity to the normalisation in coastal applications is discussed" | título: "Sensitivity of Skill Score Metric to Validate Lagrangian Simulations in Coastal Areas" | OK |

### Suzuki et al. 2012

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 6, l. 107; S p. 4, S2 | "...as implemented in SWAN by Suzuki et al. (2012)" | resumo: "the implementation of the Mendez and Losada formulation in a full spectrum model SWAN, with an extension to include a vertical layer schematization for the vegetation" | OK |

### Temmerman et al. 2005

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 17, l. 263 | "...have reproduced the same partition in tidal marshes" | resumo: modelo 3D que inclui "three-dimensional (3-D) effects of vegetation on the flow (drag and turbulence)"; p. 12, §29: "we can distinguish two vertical zones (Figure 4a): (1) within the vegetation canopy, flow velocities are reduced owing to friction; and (2) once the water level exceeds the height of the vegetation canopy, maximum flow velocities are simulated above the canopy" (PDF impresso da página web, lido como imagem) | OK |

### Turschwell et al. 2021

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 11 | "...the most rapid declines are associated with destructive demersal fishing and degraded water quality" | resumo: "Rapidly declining trajectories of seagrass meadow extent (>25% loss from 2000 to 2010) were most strongly associated with high pressures from destructive demersal fishing and poor water quality" | OK (resumo) |

### Umgiesser et al. 2014

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 3 | "Mediterranean lagoons are microtidal [...] wind adding to the exchange with the sea, and through it to the renewal time, where a lagoon has more than one inlet" | p. 2: "the 10 studied lagoons can be all defined microtidal"; resumo: "Water exchange depends mainly on the inlet shape and tidal range, but also on the wind regimes in the case of multi-inlet lagoons" | OK |

### Waycott et al. 2009

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 10 | "Global seagrass extent has fallen in all seven bioregions" | p. 3: "Our analysis included data from all 6 global seagrass bioregions"; resumo: "29% of the known areal extent has disappeared since seagrass areas were initially recorded in 1879" | Parcial (seis biorregiões e 29%; as sete biorregiões e os 19,1% vêm de Dunic, co-citado) |

### Baptist et al. 2007

PDF em `reference/papers/Baptist_etal2007EquationsforvegetationresistanceJHR.pdf`.
As páginas são as do periódico (J. Hydraul. Res. 45(4), 435–450).

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 7, l. 132 | "The bed-roughness representation of vegetation (Baptist et al., 2007) [...] was not used, since a roughness acts at the bed" | p. 444, eq. 74: Cr = (1/Cb² + CD m D k/2g)^(-1/2) + (√g/κ) ln(h/k), um Chézy representativo que soma a resistência do fluxo dentro da vegetação ao perfil logarítmico acima dela; p. 435: "the description of vegetation-induced roughness" | OK |
| p. 15, l. 236 | "...through the trachytope formulation of Baptist et al. (2007)" | eq. 74, como acima; o manual do usuário do D-Flow FM (versão 2025, revisão 80596) implementa essa expressão como eq. 13.32, fórmula de trachytope 153 (p. 236–238), e o manual técnico descreve a segunda implementação, a 154 (p. 154) | OK |

O manual do D-Flow FM atribui as fórmulas 153 e 154 à tese de Baptist (2005),
*Modelling floodplain biogeomorphology*, TU Delft, que também foi conferida
(`reference/papers/Baptist2005_PhDthesis_floodplainBiogeomorphology.pdf`). A
eq. 4.143 da tese (§4.6.8) é a eq. 74 do artigo, e as duas derivam do mesmo
trabalho de programação genética de Rodríguez Uthurburu (2004), coautor do
artigo. Citar o artigo de 2007 é consistente com o manual.

A tese não tem DOI (não aparece no Crossref nem na DataCite). Identificadores:
ISBN 90-407-2582-9 e
https://resolver.tudelft.nl/uuid:b2739720-e2f6-40e2-b55f-1560f434cbee. O
registro uuid:c79bd6f3-… do mesmo repositório está fora do ar (HTTP 403).
