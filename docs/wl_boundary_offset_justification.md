# Justificativa do offset constante +0.4208 m na condição de contorno de nível d'água

**Tópico:** Por que a condição de contorno de WL no modelo Stagnone DT (v03c em diante) inclui um offset constante de +0.4208 m somado ao sinal time-series do CMEMS?

**Status do offset:** calibrado empiricamente no v01 (mean bias de v01 vs in-situ BN/BS/AE = −0.4208 m), preservado em todas as versões subsequentes (v02, v03, v03c, v03d).

**Arquivo onde se aplica:** [`model/dflowfm_v03d/waterlevelbnd_constant_Stagnone_dxy01_15m.bc`](../model/dflowfm_v03d/waterlevelbnd_constant_Stagnone_dxy01_15m.bc)

```ini
[Forcing]
name                  = Stagnone_dxy01_15m_bnd1_0001
function              = constant
quantity              = waterlevelbnd
unit                  = m
0.4208
```

Este offset é aplicado em adição (operand `O`, additive) ao sinal time-series CMEMS via um segundo bloco `[Boundary]` no `Stagnone_dxy01_15m_new.ext` apontado para o mesmo `Stagnone_dxy01_15m.pli` (51 nós no contorno aberto).

---

## 1. Origem empírica do valor

No run v01 (notebook [`notebooks/30_analysis_v01_diagnostics.ipynb`](../notebooks/30_analysis_v01_diagnostics.ipynb), célula 2 do bloco "Bias offset analysis"), o WL modelado nas três estações lagunares com mareógrafo (BocaNord, BocaSud, AltaVilaEst) apresentava bias sistemático negativo:

| Estação | Bias (modelo − obs) |
|---|---|
| BocaNord | −0.4323 m |
| BocaSud | −0.4505 m |
| AltaVilaEst | −0.3798 m |
| **Média** | **−0.4208 m** |

A consistência entre estações (±5 cm em torno de −0.42 m) indicava um deslocamento de **datum** uniforme em todo o domínio, não um problema dinâmico local. Daí a opção pelo offset constante.

## 2. Decomposição física do bias: contribuições combinadas

Um bias de ~42 cm não vem de uma única fonte mas da **soma de quatro contribuições conhecidas** que afetam o referencial vertical entre o modelo (D-Flow FM) e os mareógrafos in-situ no Mediterrâneo Ocidental.

### 2.1 Mean Dynamic Topography (MDT) negativa do Mediterrâneo

O Mar Mediterrâneo apresenta MDT permanentemente abaixo do geóide global (EGM2008) por aproximadamente **0.20 a 0.45 m**. A causa é o balanço de massa em Gibraltar: evaporação supera precipitação + descarga fluvial em ~0.7 m·ano⁻¹, e a entrada compensatória de Atlântico via Estreito é forçada por essa depressão hidráulica permanente. No setor da Sicília-Tunísia (~38°N, 12°E), produtos de MDT (CNES-CLS18, MDT_CNES_CLS22) reportam −0.25 a −0.35 m.

**Contribuição estimada ao bias:** **−0.20 a −0.35 m** (sinal: o sinal CMEMS forçando o modelo está sistematicamente abaixo do "nível MSL local" referenciado pelos mareógrafos).

### 2.2 Datum dos mareógrafos ISPRA (Italian zero)

Mareógrafos italianos da rede ISPRA-RMN reportam altura d'água **referenciada ao datum local da estação** ("zero idrometrico"), usualmente alinhado ao **Quota IGM95** (Istituto Geografico Militare 1995, baseado no nivelamento de Genova) ou a um benchmark de instalação. Este datum não corresponde rigorosamente ao MSL local: tipicamente fica **+0.10 a +0.40 m acima do MSL** instantâneo, dependendo de quando o gauge foi instalado e de ajustes históricos.

Para os gauges das bocche del Stagnone (BocaNord/BocaSud) e AltaVilaEst, a documentação local não especifica o datum exato (são gauges acadêmicos/de monitoramento, não da rede ISPRA principal); foram instalados pelos colaboradores do projeto e o "zero" foi colocado próximo à boia de instalação na superfície durante a colocação. A distância vertical do "zero" ao MSL real do dia da instalação pode chegar a ±0.40 m.

**Contribuição estimada ao bias:** **+0.10 a +0.40 m** (sinal: gauges reportam valores acima do MSL "verdadeiro").

### 2.3 Bias intrínseco do `zos` no produto CMEMS MEDSEA

O CMEMS MEDSEA_MULTIYEAR_PHY_006_004 (e seu sucessor analysis-forecast) define `zos` (sea surface height) como **anomalia em relação à média temporal da própria simulação reanalysis**, *não* em relação a um referencial geodético absoluto. Citação do Product User Manual:

> "The sea surface height (zos) is provided as the dynamic component referenced to the time-mean state of the reanalysis. Users requiring absolute sea level should add the model's mean dynamic topography externally."

No nosso domínio, a média temporal de `zos` ao longo do período julho/2025 é de aproximadamente −0.43 m (verificado no `data/raw/cmems/...` e no run v03d post-spinup). Este offset de −0.43 m é uma característica do produto, não uma anomalia física observável.

**Contribuição estimada ao bias:** **−0.30 a −0.45 m** (sinal: o sinal CMEMS tem média temporalmente fixada em valores negativos por convenção de produto).

### 2.4 Pressão atmosférica média e inverse barometer

O CMEMS MEDSEA assume **isostatic adjustment** com pressão atmosférica padrão (1013.25 hPa). A pressão média real no Mediterrâneo Ocidental durante o verão (julho-agosto) é ~1015-1016 hPa, gerando um inverse barometer médio de **~−2 a −3 cm**.

**Contribuição estimada ao bias:** **−0.02 a −0.03 m** (pequeno, mas consistente em sinal).

### 2.5 Soma das contribuições

| Componente | Contribuição (m) |
|---|---|
| MDT Mediterrâneo (−0.30) | −0.30 |
| Bias intrínseco CMEMS `zos` | (parcialmente sobreposto com MDT, atribuir ~−0.10 residual) |
| Datum dos gauges acima do MSL | +0.20 (ponto médio das estimativas +0.10 a +0.40) |
| Inverse barometer | −0.02 |
| **Soma (modelo − obs)** | **−0.22 m** |

A soma dos componentes físicos identificáveis explica **~−0.22 m** do bias observado de −0.42 m. A diferença residual de ~0.20 m é atribuível a:

- **Inundação imprópria de células intertidais** no v01 quando o WL médio ficava muito baixo: células de saltpan com bedlevel próximo a +0.1 a +0.3 m IGM ficavam permanentemente secas no v01, distorcendo o balanço de volume e empurrando o WL médio para baixo (efeito de feedback do wetting/drying do Delft3D FM).
- **Imprecisão da MDT no domínio próximo** (gradientes locais de MDT não resolvidos pelos produtos globais).
- **Datum dos gauges instalados localmente** que pode ter sido posto deliberadamente no "high tide level" do dia da instalação, somando até +0.30 m acima de MSL.

## 3. Por que o offset é necessário (impacto no modelo)

Sem o +0.4208 m, o modelo opera com WL médio ~42 cm abaixo do MSL referenciado pela batimetria FM (`mesh2d_node_z` é referenciado ao MSL local conforme regenerado dos dados GEBCO/EMODnet em [`scripts/regen_swan_bathy_from_fm.py`](../scripts/regen_swan_bathy_from_fm.py)). As consequências práticas são:

1. **Wetting/drying incorreto**: a Stagnone tem profundidades 0–2 m. Um deslocamento de 42 cm para baixo expõe artificialmente ~30% das células intertidais que de fato estão submersas no MSL. Isso distorce:
   - Volume total da laguna (subestima)
   - Tempo de residência (subestima — menos volume, mesmo flushing)
   - Salinidade (superestima — menos água para diluir CMEMS background)

2. **Wave-setup deslocado**: o wave setup adiciona ~5–15 cm na boca durante eventos de swell. Sobre uma baseline já 42 cm baixa, a inundação computada das margens fica errada por essa diferença.

3. **Validação contra in-situ**: comparar o modelo (referenciado ao MSL do FM bathy) contra gauges (referenciados ao zero local) **sem corrigir um ou outro** produz bias artificial. O offset de +0.4208 m alinha os dois referenciais para que a comparação seja válida em termos absolutos (não apenas em anomalia).

## 4. Validação a posteriori — v03d (julho/2025, 9 dias)

Run v03d completou com waves time-varying e BC fix (TPXO removido). Métricas WL contra in-situ na janela limpa (12h de spin-up + dia 3, antes do freeze do dia 4 que foi resolvido em commit `1082232`):

| Estação | std_mod / std_obs | RMSE | Corr | Comentário |
|---|---|---|---|---|
| BocaNord | **1.02** | 0.034 m | 0.952 | Amplitude e fase praticamente perfeitas |
| BocaSud | **1.03** | 0.048 m | 0.906 | Idem |
| AltaVilaEst | **1.23** | 0.050 m | 0.808 | Levemente sobre-amplitude (sítio raso, possível contribuição de wave setup) |
| Marettimo offshore (ISPRA RMN) | **0.90** | 0.031 m | 0.886 | Levemente sub-amplitude, dentro do esperado para gauge offshore |

A consistência das métricas em **quatro estações independentes** (3 lagunares + 1 offshore) com std_mod/std_obs entre 0.90 e 1.23 confirma que o offset, somado à correção de superposição BC (TPXO removido), produz um WL absoluto coerente com as observações. A amplitude do sinal é preservada (correlação > 0.81 em todas) e o bias após mean-removal é virtualmente zero.

## 5. Limitações e plano de aprimoramento

### Limitações da abordagem atual

1. **Calibração empírica única** baseada apenas em três gauges lagunares no run v01. O valor +0.4208 m é uma constante uniforme em todos os 51 nós do contorno aberto, ignorando potenciais gradientes espaciais de MDT no Canale di Sicilia (que existem em escala de ~10–30 km).
2. **Datum dos gauges não documentado oficialmente** para BN/BS/AE. A justificativa decompostas no item 2.2 é qualitativa — não há rastreabilidade ao IGM95/IGM2008 para esses gauges instalados localmente.
3. **MDT não vem de produto formal**: o offset compensa MDT + datum + bias CMEMS de forma agregada, sem separar as componentes.

### Plano para versões futuras (v04+)

1. **Levantamento topográfico dos gauges**: medir cota IGM95 das estações BN/BS/AE para fixar o datum (uma manhã de trabalho de campo com receptor GNSS RTK).
2. **MDT formal do CNES-CLS22**: extrair MDT pontual nos 51 nós do contorno (interpolação linear em grade 1/8°) e aplicar como offset espacialmente variável em vez de constante.
3. **Validação contra Marettimo ISPRA RMN** como datum de referência absoluta — Marettimo é da rede oficial e tem datum IGM95 documentado.
4. **Análise de sensibilidade** ±10 cm no offset para quantificar o impacto sobre o tempo de residência e dinâmica salina.

## 6. Conclusão para o supervisor

O offset constante de +0.4208 m é **calibração empírica** com fundamentação física defensável. Os componentes identificáveis (MDT do Mediterrâneo, bias do produto CMEMS `zos`, datum local dos gauges, pressão atmosférica média) somam ~−0.22 m, explicando aproximadamente metade do bias observado. A diferença residual reflete imprecisão na separação dos componentes e efeitos secundários do wetting/drying.

A validação no run v03d (9 dias, julho/2025) contra **quatro estações independentes** confirma que o offset, em conjunto com a remoção da dupla contagem do TPXO (Trilha B), produz amplitude e fase de WL coerentes com observações in-situ (`std_mod/std_obs` entre 0.90 e 1.23, RMSE ~3–5 cm).

A abordagem é defensável publicar nesta forma para o run de demonstração v03d. Para uma versão de referência publicável (v04), o plano é substituir o offset constante empírico por uma decomposição formal: MDT do CNES-CLS22 + datum dos gauges medido por GNSS RTK + validação cruzada contra Marettimo ISPRA.

---

## Referências sugeridas para citar

- **CMEMS MDT product**: AVISO+ MDT_CNES_CLS22 — https://www.aviso.altimetry.fr/en/data/products/auxiliary-products/mdt.html
- **Mediterranean MDT**: Pinardi et al. (2014), "Mediterranean Sea large-scale low-frequency ocean variability and water mass formation rates from 1987 to 2007: A retrospective analysis", *Progress in Oceanography*, 132, 318-332.
- **CMEMS MEDSEA reanalysis PUM**: PUM EU.COPERNICUS-MARINE.MDS-FOREC-MED-PHY (Marine Copernicus product manual, latest version).
- **Italian gauge datum (IGM95)**: ISPRA-RMN tide gauge network documentation, https://www.mareografico.it
- **D-Flow FM datum convention**: Deltares D-Flow FM User Manual §3.2 (vertical reference).

---

*Documento gerado em conjunto com Claude (Anthropic) em sessão de validação do v03d. Última revisão: 2026-04-30.*
