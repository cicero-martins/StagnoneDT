# Roadmap — post-v03c (2026-04-23)

Plano de trabalho consolidado após validação do v03c. Quatro trilhas
ortogonais convergem em **v03d** como próximo major.

## Trilha A — Tracers via buffer inicial

**Escopo:** substituir laterals + tracer .bc pelo padrão `lagoon_tracer_init.xyz`
(init via XYZ + `initialFields.ini`). Remove a complexidade de lateral + .pli
que falhou para o ponto do aeroporto.

**Implementação:**

1. Script utilitário em `scripts/make_tracer_buffers.py` — recebe (lon, lat, radius_m, name), gera XYZ com valor 1.0 nas células do mesh FM dentro do buffer circular (via shapely + pyproj em UTM 33N). Saída: `model/dflowfm_v03d/turbid_airport_init.xyz` e `turbid_saltpans_init.xyz`.
2. Buffers de 500 m de raio, centrados em `(12.468, 37.917)` airport e `(12.507, 37.997)` saltpans.
3. No `initialFields.ini` do v03d, adicionar duas entradas `[Initial]` referenciando os XYZs com `operand = A`, `averagingType = mean`, seguindo o padrão de `lagoon_tracer_init.xyz`.
4. **Remover** do `new.ext`: blocos `[Lateral]` + `[Boundary]` tracerbnd de turbid_airport e turbid_saltpans. Remover `turbid_*.pli`, `turbid_*_discharge.bc`, `turbid_*_tracer.bc` do diretório v03d.
5. Validação mínima: `lateral_geom_node_count` some do his.nc (não há mais lateral); `turbid_airport.max()` e `turbid_saltpans.max()` no t=0 devem ser 1.0.

**Cenário físico resultante:** plume pré-existente desde sim-start (mais limpo que o pulso). Útil para medir espalhamento controlado.

## Trilha B — Validação offshore (Marettimo)

**Escopo:** comparar WL + Hs/Tp/Dir offshore em Marettimo (Egadi, ~12.05°E, 37.96°N) com output v03c.

**Implementação:**

1. Localizar estação: RON (Rete Ondametrica Nazionale, ISPRA) tem boia em Marettimo? Verificar também Copernicus CMEMS in-situ marine (`INSITU_MED_PHYBGCWAV_DISCRETE_MYNRT_013_035`). URL esperada: ispra.gov.it/en/topics/sea/wave-meter-national-network.
2. Confirmar que o ponto Marettimo cai dentro do domínio SWAN outer (que vai ~11.95°E–12.57°E). Adicionar observation point no Marettimo no `.xyn` do v03c (requer rerun para extrair his time-series naquela estação) OU extrair via map.nc offline.
3. Novo notebook `23_valid_v03c_offshore.ipynb` — carrega obs Marettimo, interpola modelo no ponto, calcula RMSE/bias/Willmott/corr para WL e para Hs/Tp separadamente.
4. Adicionar resultado na tabela validation_metrics_v03c.csv existente (ou criar v03c_offshore.csv separada).

**Critério de sucesso:** RMSE(WL) < 10 cm offshore; Hs bias dentro de ±20 cm.

## Trilha C — Morfologia (investigação + provisionamento)

**Parte C1 — investigação (antes de v03d)**:

1. `scripts/compute_uorb_from_map.py` — lê `41_util_edito_map_subset` output (hwav, twav, waterdepth), calcula u_orb = π Hs / (T sinh(kh)) nos pontos centrais do lagoon. Reporta % do tempo u_orb > 0.10 m/s (threshold resuspensão sand fino).
2. Notebook `31_analysis_resuspension_feasibility.ipynb`:
   - Seção 1: u_orb time series nos 7 stations (a partir do his.nc v03c, que já tem uorb).
   - Seção 2: série temporal turbidez Sentinel-2 L2A (nominalIIR / CHL_NN) 2025-06-01 a 2025-08-01, extraída do mesmo bbox.
   - Seção 3: cross-correlação de turbidez com ERA5 wind speed (já temos local) + CMEMS Hs.
   - Decisão: se turbidez correlaciona com Hs e u_orb excede threshold > 5% do tempo → morph vale a pena.
3. Memória a atualizar com os números encontrados.

**Parte C2 — provisionamento v03d**:

Se C1 for positivo:
- Habilitar D-Morphology no MDU do v03d: `[Morphology]` section + referência a `sediment.sed` + `morphology.mor`.
- Sediment: 2 frações. Fração 1 = sand fino (d50 ≈ 150 µm), fração 2 = silt (d50 ≈ 30 µm).
- Manning baseline preservado; D-Morph adiciona bed shear stress do wave orbital.
- Initial bed: uniforme (sem variação espacial na primeira iteração; refinar depois se sentido).
- `morfac = 1` (real-time, sem aceleração morfológica — runs curtos).

Se C1 for negativo: documenta no roadmap e pula C2. v03d fica sem morph.

**XBeach fora**: já decidido — é modelo de surf zone, não aplicável a lagoon sheltered.

**Resultado C1 (2026-04-23)**: morph **aprovado** para v03d. Ver [notebook 31_analysis_resuspension_feasibility](../notebooks/31_analysis_resuspension_feasibility.ipynb). Evidências: (a) iter-1 SWAN já reporta u_orb = 0.186 m/s em BocaNord (acima do fine-sand threshold 0.14); (b) offshore peak Hs = 2.05 m (2025-07-09) → inlet u_orb 0.7-1.7 m/s — excede sand threshold >30% do tempo mesmo com atenuação 30%; (c) S2 scene 2025-10-06 mostra evento de ressuspensão visualmente confirmado (PI). Interior marginal mas mobiliza silt + clay. **C2 segue**: habilitar `[Morphology]` + 2 frações (sand d50 150µm, silt d50 30µm).

## Trilha D — HDF5 coupling debug (local)

**Escopo:** destravar a limitação de ondas constantes no acoplamento FM+SWAN Online with FLOW.

**Implementação (local, sem EDITO):**

1. **Run baseline** do v03c local completo (full 9 dias) para reproduzir o erro localmente e ter baseline de comparação.
2. **Teste 1 — `ncFormat = 3`**: clonar v03c como `v03c_test1_nc3`, mudar `ncFormat = 4 → 3` no MDU, rerun. Checar se os errors HDF somem e se hwav.std() > 0 agora.
3. **Teste 2 — serial run (`nPart = 1`)**: clonar como `v03c_test2_serial`, mudar run_model para nPart=1, rerun. Checar mesmo critério.
4. **Teste 3 — combo**: se T1 e T2 isolados falharem, combinar ambos.
5. **Pesquisa**: Deltares OSS forum (`oss.deltares.nl/web/delft3d/forum`) + GitHub `Deltares/dflowfm-repo` issues. Procurar por "HDF error com.nc SWAN online FLOW".
6. **Escalação**: se tudo falhar, abrir thread no forum Deltares com MDU/MDW anonimizado + log + versão exata.

**Deliverable**: memória `hdf5_coupling_resolution.md` com o workaround (ou confirmação de bug conhecido).

## Trilha E — v03d consolidation

Puxa de A + C2 (se positivo) + D (se resolveu):

Build em `model/dflowfm_v03d/` (notebook `14_build_v03d.ipynb`):
- A: buffer tracers + remoção de laterals
- ERA5 evaporation forcing (adicionar `era5_e_2025...nc` + referência no ext)
- C2: sediment + morph se C1 positivo
- D: ncFormat=3 ou setup serial se D resolveu

## Trilha F — v03d validation

Notebook `24_valid_v03d.ipynb` (reaproveita estrutura do `22_valid_v03c`):
- Stations padrão (7 + Marettimo offshore)
- Hipersalinidade (agora esperada persistir com evap)
- Tracers (dispersão pré-existente)
- Ondas (time-varying, se D resolveu)
- Sedimento (se C2 habilitado)

## Sequência recomendada

| # | Trilha | Duração | Dependência |
|---|---|---|---|
| 1 | **B — Marettimo** | 4-6 h | map.nc local |
| 2 | **D — HDF5 local** | 4-8 h | ambiente local Delft3D |
| 3 | **C1 — morph investigation** | 3-4 h | his.nc + map subset + Sentinel-2 |
| 4 | **A — tracer buffer script** | 2 h | independente |
| 5 | **E — v03d build** | 4 h | A, C2 (se aplicável), D |
| 6 | **F — v03d validation** | 3 h | v03d run no EDITO (~12 h clock time) |

Total estimado ~24 h de trabalho + 12 h de clock para o run v03d.

## Out of scope (para depois)

- SWAN nested grid extension (memória `swan_grid_extension`) — fica para v04.
- Tier 2 / Tier 3 do dt_scaling_roadmap.
- Paper drafts.
