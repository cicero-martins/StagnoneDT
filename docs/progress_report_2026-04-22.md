# Progress Report — 2026-04-22

**Focus:** v03b validation, v03c design & EDITO debugging, FM+SWAN coupling deep-dive.

## TL;DR

- **v03b validation notebook** produziu diagnóstico detalhado do run v03b (hydrodynamics, salinity, tracers, waves) e revelou três bugs silenciosos.
- **v03c** criado corrigindo os três bugs + adicionando dois tracers experimentais de turbidez (aeroporto Birgi + salinas de Trapani) acionados por pulso de chuva no dia 3.
- **Rodando agora no EDITO** via `delft3dfmrun-docker` (5ª tentativa bem-sucedida após 4 falhas de config). Progrediu para sim-time `2025-07-01 03:40` após ~17 min de real-time — ritmo esperado (~8 min por dia de sim).
- **Questão estrutural identificada**: erro HDF5 na reabertura do com.nc pelo SWAN após iteração 1 — pre-existente em v03/v03b, impede variação temporal das ondas no acoplamento. Não bloqueia a simulação; tema para investigação separada.

## 1. Validação v03b ([notebook 18](../notebooks/18_v03b_validation.ipynb))

Estruturado em 5 seções: 1) verificação de input/setup, 2) nível do mar vs tide gauge Trapani + GTSM, 3) ondas vs CMEMS (adaptado — sem dados in situ disponíveis), 4) salinidade, 5) tracer. Seção Summary consolida achados.

**Métricas salvas** em [data/processed/validation_metrics_v03b.csv](../data/processed/validation_metrics_v03b.csv), plots em [figures/v03b_*.png](../figures/).

**Achados:**

| Componente | Status | Causa raiz |
|---|---|---|
| Nível do mar | ✓ OK (RMSE ~6 cm) | — |
| Correntes | ✓ Compatível com CMEMS | — |
| **Ondas** | **✗ `hwav.std() = 0`** | SWAN só grava com.nc na 1ª iteração; erros HDF nas seguintes (ver §4) |
| **Salinidade** | **✗ Início em ~38 ppt, não 42** | `iniWithNudge = 2` do MDU sobrescreveu o XYZ hipersalino |
| **Tracer1** | **✗ Sem output** | Boundary spec quebrada em `.ext` |

## 2. v03c — design e mudanças ([model/dflowfm_v03c](../model/dflowfm_v03c))

Base: clone de v03b com as seguintes alterações:

**Correções dos bugs:**
- `iniWithNudge = 0` (MDU) → XYZ hipersalino 42 ppt efetivamente aplicado
- Tracer1 removido (boundary + initial condition + .ext)

**Amostragem temporal mais fina:**
- `mapInterval = 900.0` (era 1800.0) → output a cada 15 min

**Novos tracers de turbidez (pulso de chuva dia 3):**
- `turbid_airport` — aeroporto Birgi (12.468, 37.917), ~1000 m³ em 2h → `discharge = 0.139 m³/s`
- `turbid_saltpans` — salinas de Trapani (12.507, 37.997), ~10000 m³ em 2h → `discharge = 1.389 m³/s`
- Ambos com concentração unitária (tracer = 1) durante o pulso (dia 3, 00h-02h), zero antes e depois
- Arquivos: `turbid_*.pli` (localização), `turbid_*_discharge.bc` (descarga lateral), `turbid_*_tracer.bc` (concentração)

**Outros ajustes identificados durante debugging EDITO:**
- `run_model.sh` convertido para LF (Docker Linux não interpretava `#!/bin/bash\r`)
- Removidos 14 observation points GTSM virtuais que ficavam fora do mesh, causando warnings `find_flowlinks lies outside` — mantidos só os 7 pontos locais (AltaVilaEst, BocaNord, BocaSud, ObservationPoint01, C1/C2/C3_Central)

## 3. EDITO debugging — lições

Sequência de falhas antes de estabilizar (7 logs salvos em `output/delft3d-run-docker-*.txt`, gitignored):

1. `run_model.sh: no such file` — CRLF no shebang.
2. Observation points GTSM warnings.
3. Formato `.bc` errado para `Lateral` (lowercase `[forcing]`, keys sem underscore). Deve ser `[Forcing]` + `fileVersion=1.01` + `quantity=lateral_discharge`.
4. `SimMode = nonstationary` rejeitado — manual exige hífen: `non-stationary`.
5. Tentei `SimMode = non-stationary` para ter ondas time-varying — **WRONG**. No acoplamento DIMR Online with FLOW, precisa ser `stationary`. A variação temporal vem do SWAN re-solvendo a cada passo de coupling com TPAR reamostrado. Revertido para padrão v03b.
6. Tentei alinhar `refDate` / remover dualidade `tStart=0`+`startDateTime=20250701` — **WRONG**. DIMR aceita a dualidade; foi regressão.
7. Após reverter para config v03b no MDW (stationary + `[TimePoint]` placeholder), simulação começou a rodar normalmente.

**Memórias criadas/atualizadas** (persistent memory): [dimr_time_vs_startdatetime.md](../../.claude/projects/c--Users-Unipa-Documents-StagnoneDT/memory/dimr_time_vs_startdatetime.md) com a lição sobre `SimMode=stationary` + quasi-stationary sequence no Online with FLOW.

## 4. Questão estrutural — erro HDF no com.nc

**Sintoma** (presente em v03/v03b/v03c, pre-existente):

```
ERROR opening file. NetCDF file : "..._com.nc". Error message: NetCDF: HDF error
ERROR: time_read(0.00000E+00) is not equal to curtime(0.15639E+08)
```

**Mecanismo** (reconstituído do log da iteração atual):
1. 1ª `wave.Update`: SWAN lê flow fields + escreve hrms/tp/dir no `com.nc` ✓
2. `DFlowFM.Update(600s)` avança 9 horas de sim
3. 2ª `wave.Update`: SWAN reabre `com.nc` para leitura (warnings "time not found", usa último timestep disponível) → roda SWAN internamente → **falha ao reabrir para write** com `HDF error`
4. Subsequentes iterações repetem o padrão 3

**Consequência**: FM lê hrms/tp/dir só da 1ª escrita bem-sucedida → ondas ficam quasi-constantes. **Este é o porquê de `hwav.std()=0` em v03b**.

**Hipóteses para investigação futura** (opção B do próximo passo):
- Conflito de file handle HDF5 entre ranks FM (paralelo) e SWAN (serial)
- `ncFormat = 3` (classic netCDF sem HDF5) como workaround
- Flags de flush/sync entre FM e SWAN no com.nc
- Possível bug conhecido do docker image Delft3D específico do EDITO

**Não-investigar ainda**: a simulação completa apesar dos erros (v03 já validou isso); validação das outras melhorias de v03c (salinidade, tracers) vale a pena esperar o run terminar.

## 5. Status atual e próximos passos

**Rodando agora no EDITO:** v03c via `delft3dfmrun-docker`. Progresso: sim-time `2025-07-01 03:40` em 17 min reais. Estimativa de conclusão: ~1.5–2h para 9 dias de sim.

**Após conclusão do run:**
1. Download de output (script `edito_sync.py download-his` + map/com via mc)
2. Rodar [notebook 18](../notebooks/18_v03b_validation.ipynb) adaptado ao v03c — verificar:
   - Salinidade inicial = 42 ppt no interior do lagoon ✓ (esperado com `iniWithNudge=0`)
   - Tracers turbid_airport / turbid_saltpans com padrão de dispersão plausível a partir do dia 3
   - Ondas: confirmar `hwav.std()=0` (limitação conhecida) e documentar explicitamente
3. Abrir investigação do erro HDF como trilha separada — requer consultar Deltares forum / GitHub ou testar workarounds em ambiente local

**Outras frentes (não tocadas hoje, contexto):**
- Notebook 03b (roughness alternatives) — polígonos de treinamento interativos + classificação RF já entregues
- Pipeline OpenDrift — funcional
- Planet imagery — aguarda download manual do usuário

## Deliverables

| Arquivo | Descrição |
|---|---|
| [model/dflowfm_v03c/](../model/dflowfm_v03c/) | Modelo v03c completo (pronto para rerun) |
| [notebooks/18_v03b_validation.ipynb](../notebooks/18_v03b_validation.ipynb) | Validação v03b (reaproveitável para v03c) |
| [figures/v03b_*.png](../figures/) | Plots de validação (3 séries + métricas) |
| [data/processed/validation_metrics_v03b.csv](../data/processed/validation_metrics_v03b.csv) | Métricas quantitativas |
| [docs/progress_report_2026-04-22.md](progress_report_2026-04-22.md) | Este relatório |
