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
   - Kjerfve 1994: o título do capítulo é "Coastal Lagoons". "Coastal Lagoon
     Processes" é o título do livro.
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
3. **Ainda em aberto.**
   - "all seven bioregions" (Introdução, p. 2, l. 10): Waycott et al. 2009
     usam **seis** biorregiões. O "sete" só pode vir de Dunic et al. 2021, que
     não tem PDF na pasta. Conferir em Dunic antes da submissão.
   - "concentrate fisheries and biodiversity" (p. 2, l. 1): Carrasco 2016 só
     sustenta os 13% da linha de costa. O resto depende de Kjerfve 1994, sem
     PDF.
   - §5.1 (p. 17, l. 257): Nepf 2012 sustenta que o perfil sobre leito rugoso
     ou dossel esparso continua logarítmico. O limite da razão
     superfície/fundo "well below the values obtained here" é inferência do
     manuscrito, não de Nepf.
   - De Marchis et al. 2012: o Crossref registra 2011 (publicação online), e o
     volume 12 é de 2012. O `.bib` mantém 2012, o ano do volume.
4. **Sem PDF na pasta:** Kjerfve 1994, Dunic 2021, Turschwell 2021, Carniello
   2011, Morote-Sánchez 2025, Nepf e Vivoni 2000, Temmerman 2005, Beudin 2017,
   Luhar e Nepf 2011, Baptist 2007, Booij 1999, Battjes e Stive 1985, Bouws e
   Komen 1983, Dalrymple 1984, Suzuki 2012, Kernkamp 2011, Dagestad 2018,
   Mogé 2019 e Deltares 2025. Os seis últimos são citações de método,
   software ou manual.

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

### Carrasco et al. 2016

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 1 | "Coastal lagoons occupy roughly 13% of the global shoreline and concentrate fisheries and biodiversity" | p. 2: "About 32,000 lagoons are reported along 13% of the world's coastline" | Parcial (pesca e biodiversidade não aparecem) |

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

### De Marchis et al. 2012

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 22 | "...resolved the vertical and found that wind drives a recirculation with a near-bed return flow even at sub-metre depths, the meadow entering through Nikuradse roughness heights assigned by seagrass class" | resumo: "the fundamental role of the wind [...] producing a strong vertical recirculation pattern"; p. 9: "three different Nikuradse roughness coefficients ks", ponderados pela cobertura de cada espécie | OK |
| p. 3, l. 50 | "The basin extends about 11 km north–south and 2.5 km east–west" | p. 3: "The lagoon is about 11 km long (in the north-south direction) and about 2.5 km width" | OK |
| p. 3, l. 54 | "...the small island of Scuola between them" | Fig. 1: "Scola island" entre Mothia e Santa Maria | OK |
| p. 4, l. 63 | "...dominated by the semi-diurnal constituent with a diurnal contribution" | p. 12: "tidal oscillations are dominated by the semi-diurnal constituent (12.4 h) with supplementary contribution of the diurnal constituent (24 h)" | OK |
| p. 4, l. 64 | Vento no eixo leste–oeste, maré no norte–sul | p. 13: "north-south velocities are quite higher than east-west ones when tide effects only are considered"; o vento aumenta a componente leste–oeste | OK |
| p. 17, l. 267 | "...established a wind-driven three-dimensional circulation with a near-bed return flow" | idem p. 2 | OK |

### Di Marca 2009

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 19 | "...measured the share of resuspension over the meadow and of lateral advection in the turbidity of the water column" | p. 2: "the effect of vegetation coverage on water column behaviour was studied with a long-continuous experiment [...] exploring the relative importance of resuspension throughout the water column in comparison of a lateral advective transport" | OK |

### Dunic et al. 2021

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 10 | "...has fallen in all seven bioregions, by 19.1% of the surveyed area since 1880" | sem PDF | Não verificado (ver ponto de atenção 3) |

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

### Umgiesser et al. 2014

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 3 | "Mediterranean lagoons are microtidal [...] wind adding to the exchange with the sea, and through it to the renewal time, where a lagoon has more than one inlet" | p. 2: "the 10 studied lagoons can be all defined microtidal"; resumo: "Water exchange depends mainly on the inlet shape and tidal range, but also on the wind regimes in the case of multi-inlet lagoons" | OK |

### Waycott et al. 2009

| Manuscrito | Frase | Fonte | Situação |
| --- | --- | --- | --- |
| p. 2, l. 10 | "Global seagrass extent has fallen in all seven bioregions" | p. 3: "Our analysis included data from all 6 global seagrass bioregions"; resumo: "29% of the known areal extent has disappeared since seagrass areas were initially recorded in 1879" | Parcial (seis biorregiões; os 19,1% são de Dunic) |

### Referências sem PDF

O DOI de cada uma confere com o Crossref em título, ano, volume e páginas. As
afirmações não foram conferidas no texto.

| Referência | Posição | Uso |
| --- | --- | --- |
| Kjerfve 1994 | p. 2, l. 1 | Lagunas, pesca e biodiversidade |
| Dunic et al. 2021 | p. 2, l. 10 | 19,1% da área perdida desde 1880 |
| Turschwell et al. 2021 | p. 2, l. 10 | Perdas mais rápidas onde há desenvolvimento costeiro |
| Carniello et al. 2011 | p. 3, l. 32; p. 18, l. 286; p. 19, l. 334 | Ondas, tensão no fundo e ressuspensão em bacias rasas |
| Morote-Sánchez et al. 2025 | p. 3, l. 32; p. 18, l. 286 | Idem, laguna mediterrânea micromareal |
| Nepf e Vivoni 2000 | p. 17, l. 263 | Escoamento reduzido no dossel e acelerado acima, em laboratório |
| Temmerman et al. 2005 | p. 17, l. 263 | Modelo 3D com arrasto de vegetação em marisma |
| Beudin et al. 2017 | p. 17, l. 263 | Modelo acoplado onda–corrente–vegetação |
| Luhar e Nepf 2011 | p. 19, l. 322 | Reconfiguração de lâminas flexíveis com a velocidade |
| Baptist et al. 2007 | p. 7, l. 132; p. 15, l. 236 | Representação da vegetação por rugosidade (trachytope) |
| Booij et al. 1999 | p. 6, l. 101 | SWAN |
| Battjes e Stive 1985 | S p. 3, S2 | γ = 0,73 |
| Bouws e Komen 1983 | S p. 3, S2 | Atrito JONSWAP para mar de vento |
| Dalrymple et al. 1984 | p. 6, l. 107; S p. 4, S2 | Dissipação por vegetação |
| Suzuki et al. 2012 | p. 6, l. 107; S p. 4, S2 | Implementação no SWAN |
| Kernkamp et al. 2011 | p. 6, l. 89 | D-Flow FM |
| Dagestad et al. 2018 | p. 8, l. 151 | OpenDrift |
| Mogé 2019 | S p. 2, S1 | Partições e custo de comunicação |
| Deltares 2025 | S p. 8, S5 | Limite de passo pelos fluxos verticais |
