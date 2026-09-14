# De Navier-Stokes ao que o D-Flow FM realmente resolve

Registro da cadeia de hipóteses e modificações que levam das equações de Navier-Stokes ao
sistema discreto integrado pelo kernel `dflowfm 1.2.184`, e de quais dessas hipóteses ficam
apertadas no regime do Stagnone.

Levantado em 2026-09-14 a partir dos manuais da instalação local.

## Fontes

Ambos em `C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\bin\`:

- **UM** = `D-Flow_FM_User_Manual.pdf`, versão 2025, rev. 80505. Capitulo 3, "Conceptual
  description of hydrodynamic equations", p. 8-32. A secao 3.9 (p. 31) e a lista canonica
  de hipoteses.
- **TRM** = `D-Flow_FM_Technical_Reference_Manual.pdf`, versão 2025, rev. 80505. Capitulo 6,
  "Numerical approach", p. 38-138 (2D). Capitulo 7, "Numerical schemes for three-dimensional
  flows", p. 139-164.

Atencao a uma armadilha de citacao: o capitulo 5 do TRM ("Conceptual description") esta quase
todo vazio, marcado `[yet empty]`, **exceto** a secao 5.5 (Turbulence), que carrega as equacoes
(5.1) e (5.2) da composicao da viscosidade turbilhonar. Esse mesmo texto aparece no UM secao
3.3.5 mas **sem numeracao de equacao**. Ao citar a decomposicao de viscosidade, citar TRM 5.5.

O codigo-fonte Fortran nao acompanha a instalacao (so binarios). Os manuais nomeiam as rotinas
reais, o que da o mapa direto para o repositorio aberto (secao "Mapa manual -> rotina" abaixo).

---

## Parte 1 - A cadeia de reducoes fisicas

O UM secao 3.3 (p. 9) declara o ponto de partida sem rodeios:

> D-Flow FM solves the Navier Stokes equations for an incompressible fluid, under the shallow
> water and the Boussinesq assumptions. In the vertical momentum equation the vertical
> accelerations are neglected, which leads to the hydrostatic pressure equation.

A lista completa esta na secao 3.9. A cadeia, em ordem de severidade:

### 1.1 Incompressibilidade

$\nabla \cdot \mathbf{u} = 0$. O termo $\partial \rho / \partial t$ sai da continuidade, que
deixa de ser equacao de evolucao e vira restricao cinematica. A continuidade 2D (UM eq. 3.3)
resulta de integrar $\nabla \cdot \mathbf{u} = 0$ na vertical, aplicando as condicoes
cinematicas na superficie livre e no fundo:

$$\frac{\partial h}{\partial t} + \frac{\partial (Uh)}{\partial x} + \frac{\partial (Vh)}{\partial y} = Q$$

com $Q$ (UM eq. 3.4) agregando fontes e sumidouros locais mais precipitacao $P$ e evaporacao $E$:

$$Q = \int_0^h (q_{in} - q_{out})\, dz + P - E$$

Esta e a equacao onde entra o forcante ERA5 de evaporacao do v04. Ver a memoria
`fm_evaporation_convention` para a convencao de sinal do `QUANTITY=rainfall_rate`.

### 1.2 Media de Reynolds

A malha nao resolve as flutuacoes turbulentas, entao as equacoes sao promediadas e aparecem as
tensoes de Reynolds, fechadas pelo conceito de viscosidade turbilhonar. O UM secao 3.9 e
honesto sobre o status disso:

> The equations of D-Flow FM are capable of resolving the turbulent scales (large eddy
> simulation), but usually the hydrodynamic grids are too coarse to resolve the fluctuations.
> Therefore, the basic equations are Reynolds-averaged introducing so-called Reynolds stresses.

Nas equacoes de momento isso aparece como as forcas $F_x$ e $F_y$, descritas como "the
unbalance of horizontal Reynolds stresses".

### 1.3 Boussinesq

Variacao de densidade entra **apenas** no termo de pressao. Em todo o resto $\rho = \rho_0$.
O UM repete a frase em 3.3.1.1 e 3.3.2.1: *"Density variations are neglected, except in the
baroclinic pressure terms."*

No nosso MDU isso e o `rhomean = 1023.0`. E o que permite manter a continuidade em forma
incompressivel mesmo com a estratificacao salina forte do Stagnone.

### 1.4 Hidrostatica (a reducao mais violenta)

A equacao de momento **vertical** e descartada inteira e substituida por (UM eq. 3.8,
TRM eq. 7.92):

$$\frac{\partial P}{\partial z} = -\rho g$$

Consequencias em cascata:

- **$w$ deixa de ser prognostica.** Passa a ser diagnosticada da continuidade (UM eq. 3.7),
  descrita como "the velocity associated with up- or downwelling motions".
- **Aceleracoes verticais nao existem no modelo.** UM 3.3.3: *"Vertical accelerations due to
  buoyancy effects and due to sudden variations in the bed topography are not taken into
  account."* A secao 3.9 tira a conclusao operacional: a aplicacao fica *"restricted to
  mid-field and far-field dispersion simulations of discharged water"*.
- **Coriolis fica truncada.** Nas eqs. 3.5/3.6 restam so os termos $-fv$ e $+fu$, ou seja, so
  a componente vertical de $\boldsymbol{\Omega}$. A componente que acoplaria com $w$ foi embora
  junto com a equacao vertical. (Leitura das equacoes, nao citacao literal do manual.) Em
  coordenadas cartesianas, UM 3.9: *"the Coriolis parameter is assumed to be uniform unless
  specifically specified otherwise"*, ou seja f-plane.

### 1.5 Segunda promediacao, agora sobre as ondas

Ponto que costuma passar batido e que e central no acoplamento com o SWAN. UM secao 3.9,
primeiro item:

> The pressure is hydrostatic and the model is not capable of resolving the scales of short
> waves. Therefore, the basic equations are averaged in analogy with turbulence introducing
> so called radiation stresses.

O mesmo truque de Reynolds e aplicado uma segunda vez, na escala de onda. As radiation stresses
entram como $M_x$, $M_y$, termos fonte de momento, nao como fisica resolvida. O UM descreve
$M_x, M_y$ como *"contributions due to external sources or sinks of momentum (external forces
by hydraulic structures, discharge or withdrawal of water, wave stresses, etc.)"*.

Implicacao direta: no nosso setup acoplado, tudo que o SWAN devolve ao FM entra por esse canal
de termo fonte. Nao ha onda resolvida na hidrodinamica.

### 1.6 Anisotropia da viscosidade

TRM secao 5.5, eqs. (5.1) e (5.2):

$$\nu_H = \nu_{SGS} + \nu_V + \nu_{Hback}$$
$$\nu_V = \nu_{mol} + \max(\nu_{3D}, \nu_{Vback})$$

Sao coeficientes de naturezas diferentes carregando o mesmo nome. O horizontal absorve
turbulencia sub-grid mais tudo que a malha nao resolve; o vertical vem do modelo de fechamento.
No nosso MDU, `vicouv = 0.1` contra `vicoww = 1e-4`, tres ordens de grandeza, e o k-epsilon
(`turbulenceModel = 3`) so alimenta a parte vertical.

O UM 3.3.5 (p. 12) acrescenta um detalhe operacional importante: o default para a viscosidade
horizontal e **Smagorinsky**, integrado explicitamente, com criterio de passo de tempo que
**reduz o coeficiente por link** quando violado, emitindo `** WARNING: Viscosity coefficient
was limited for N links.` Ver Parte 3 para o que isso esta fazendo no v04AE.

### 1.7 Integracao em camadas (3D)

No 3D o TRM nao trabalha com a equacao pontual. A secao 7.1 parte de uma formulacao de volume
de controle **movel** (eq. 7.1), integra entre interfaces de camada $z_1$ e $z_2$ e chega a
eq. 7.5 para $\phi = u$. Subtraindo a continuidade em camadas (eq. 7.3) obtem-se a forma
primitiva, eq. 7.6.

Assimetria estrutural que vale reter: **a continuidade e integrada em toda a coluna** (eq. 7.4),
**o momento nao**. E isso que permite reduzir o sistema a uma unica equacao 2D de nivel d'agua
mesmo em modo 3D (ver 2.5 abaixo).

---

## Parte 2 - As modificacoes numericas

Aqui o TRM e incomumente honesto sobre os proprios limites. Vale ler os *Remarks* com atencao,
porque varios sao admissoes de nao-conservacao.

### 2.1 Forma conservativa -> forma primitiva, e o "storage term"

O TRM cap. 6 abre com a forma conservativa (eqs. 6.1-6.2), aplica regra do produto (eq. 6.5)

$$\frac{\partial (h\mathbf{u})}{\partial t} = h\frac{\partial \mathbf{u}}{\partial t} + \mathbf{u}\frac{\partial h}{\partial t}$$

substitui a continuidade e chega a eq. 6.7:

$$\frac{\partial \mathbf{u}}{\partial t} + \frac{1}{h}\left[\nabla \cdot (h\mathbf{u}\mathbf{u}) - \mathbf{u}\,\nabla \cdot (h\mathbf{u})\right] = -g\nabla\zeta + \frac{1}{h}\nabla \cdot \left(h\nu(\nabla\mathbf{u} + \nabla\mathbf{u}^T)\right) + \frac{1}{h}(\boldsymbol{\tau}_b + \boldsymbol{\tau}_w)$$

O termo $-\mathbf{u}\,\nabla \cdot (h\mathbf{u})$ **nao existe na fisica**. E o *storage term*,
residuo puro da conversao para variaveis primitivas. TRM p. 47: *"It originates from the
substitution of the continuity equation in the conservatively formulated momentum equation."*

Ele e a origem da maior parte das sutilezas seguintes, e e o que diferencia todos os esquemas
de adveccao disponiveis.

### 2.2 Malha staggered nao-estruturada: so a componente normal existe

Nivel d'agua nos **circuncentros** das celulas, velocidade **normal** nas faces. O momento so e
resolvido na direcao normal a face. TRM p. 46:

> The difficulty with the staggered layout on unstructured meshes is that we only solve the
> momentum equation in face-normal direction. We could, in principle, formulate a control
> volume for each face-normal velocity, but are unable to define conservative fluxes, as we do
> not solve for the whole momentum vector.

### 2.3 A construcao de Perot (2000)

Em vez de conservar na face, conserva-se o vetor reconstruido no **centro** da celula. Sequencia:

1. Discretiza a adveccao nos centros como se o arranjo fosse colocado (eq. 6.29):
   $$\mathbf{a}_k = \frac{1}{A(k)} \sum_{j \in J(k)} \mathbf{uu}_j\, q_j\, s_{j,k}$$
2. Interpola de volta para as faces e projeta na normal (eq. 6.28):
   $$\nabla \cdot (h\mathbf{u}\mathbf{u})|_j \cdot \mathbf{n}_j \approx \left[\phi_j \mathbf{a}_{L(j)} + (1-\phi_j)\mathbf{a}_{R(j)}\right] \cdot \mathbf{n}_j$$

A reconstrucao centro-de-celula sai de uma identidade de divergencia (eq. 6.42), discretizada
com pesos geometricos (eqs. 6.44-6.45, rotina `setlinktocenterweights`):

$$\mathbf{wc}_{Lj} = \frac{\phi_j \Delta x_j \mathbf{n}_j wu_j}{A(L(j))}, \qquad \mathbf{wc}_{Rj} = \frac{(1-\phi_j) \Delta x_j \mathbf{n}_j wu_j}{A(R(j))}$$

**Tres ressalvas que o proprio manual faz, e que importam para nos:**

- *Remark 6.2.8*: aproximacao de segunda ordem **se** o ponto central estiver perto do centro de
  massa. O FM usa o **circuncentro**, *"which can deviate considerably from the mass center for
  irregular meshes"*.
- *Remark 6.2.6*: **"It's fair to say that, formally speaking, none of the momentum advection
  schemes in D-Flow FM is conservative in the sense of Perot (2000)."**
- *Remark 6.2.9*: celulas cortadas pela interface seco/molhado **nao recebem tratamento
  especial**. Faces secas entram na reconstrucao com velocidade zero assumida, e *"cell centered
  velocity vectors near the dry-wet interface may be inconsistent with the local flow"*.

O ultimo ponto e literalmente o mecanismo por tras da patologia das celulas intertidais. Ver
Parte 3.

### 2.4 `advecType = 33` especificamente

A Tabela 6.1 (TRM p. 51) lista os esquemas por `iadv`. As linhas **3 e 33 compartilham a mesma
linha da tabela**: conjunto de faces $J$, fluxos $qa_l$, $\lambda = 0$, $u_{\{L,R\}j} = u_j$,
pesos $A_{Lj} = \phi_j / [\phi_j V_{L(j)} + (1-\phi_j) V_{R(j)}]$ e o simetrico para $A_{Rj}$.

Ou seja: **33 e a implementacao rapida do 3, nao uma formulacao diferente.** O rotulo do MDU
("Perot q(uio-u) fast") bate com a tabela. O que varia entre os esquemas listados e precisamente
o tratamento das sutilezas do storage term apontadas por Borsboom (2013).

### 2.5 Nao-conservacao temporal, assumida

*Remark 6.2.7*: os fluxos no storage term ficam no nivel de tempo **antigo** ($q_j^n$), enquanto
os da continuidade estao no **novo** ($q_j^{n+1}$). Logo:

> advection in D-Flow FM is non-conservative for non-stationary flows and $\theta > 0$.

Com `teta0 = 0.55` no nosso MDU, isso se aplica. O manual explica que a discretizacao implicita
do storage term seria necessaria para conservacao discreta, mas *"in D-Flow FM the storage term
is always discretized explicitly in time"*.

### 2.6 Theta-method semi-implicito e a reducao a uma equacao so em zeta

Discretizacao temporal (eq. 6.121): atrito de fundo e a parte implicita da adveccao $A_i$ ficam
implicitos, o resto explicito. O truque esta em escrever a atualizacao de velocidade como funcao
**afim** do gradiente de nivel (eq. 6.122):

$$u_j^{n+1} = -fu_j^n \left(\zeta_{R(j)}^{n+1} - \zeta_{L(j)}^{n+1}\right) + ru_j^n$$

$fu$ e $ru$ saem de uma iteracao de ponto fixo com no maximo **4 passos** e tolerancia $10^{-2}$
(`Algorithm 16: furu`).

Substituindo na continuidade discreta (eq. 6.123), **a velocidade some** e sobra um sistema
linear so em $\zeta^{n+1}$ (eq. 6.126). Como $V(\zeta)$ e nao-linear, resolve-se por Newton
linearizando o volume pela area molhada (eq. 6.129):

$$V_k^{n+1(p+1)} = V_k^{n+1(p)} + A_k^{n+1(p)}\left(\zeta_k^{n+1(p+1)} - \zeta_k^{n+1(p)}\right)$$

E esse sistema que o `icgSolver = 4` (sobekGS + Saadilud) ataca.

*Remark 6.3.1*: a area de escoamento da face $Au_j$ **sempre** aparece explicitamente na
continuidade. Nunca e implicitada.

### 2.7 No 3D, o mesmo truque vira um perfil vertical

TRM secao 7.6. A horizontal fica explicita camada a camada; a adveccao e difusao **verticais**
sao tratadas implicitamente. O resultado (eq. 7.22) e tridiagonal em $l$:

$$a_l u_{j,l-1}^{n+1} + b_l u_{j,l}^{n+1} + c_l u_{j,l+1}^{n+1} = d_l - \frac{g\theta_j}{\Delta x_j}\left(\zeta_{R(j)}^{n+1} - \zeta_{L(j)}^{n+1}\right)$$

Como a relacao $u = -fu \cdot \Delta\zeta + ru$ precisa valer para **qualquer** campo de nivel, o
sistema se separa em dois tridiagonais, um para $ru$ e outro para $fu$ (eqs. 7.29-7.30),
resolvidos por Thomas (`Algorithm 54: tridag`).

Ou seja: $fu$ e $ru$ deixam de ser escalares por face e passam a ser **perfis verticais** por
face. A equacao global de nivel d'agua continua sendo a mesma, 2D. E por isso que `kmx` encarece
o passo de tempo muito menos do que se esperaria de um solver 3D completo.

**Duas admissoes da secao 7.6 que valem anotar:**

- *Remark 7.6.1*: o termo $\nabla_H \sigma \cdot \nabla u$ da difusao vertical e
  **negligenciado** por simplificacao. O manual avisa: *"this term becomes important when the
  layer-level gradient is large, and neglecting this term may cause large error."*
- *Remark 7.6.2*: `javau = 4` (esquema central na vertical) *"may lead to instabilities"*.
- *Remark 7.6.3*: desligar a adveccao vertical (`javau = 0`) *"may lead to non-physical results"*.

### 2.8 Atrito de fundo em 3D nao usa a forma original

TRM secao 7.4.2.3, textual: *"unlike the 2D case, this term is not discretized in its original
form."* Em vez do quadratico com Chezy, ajusta-se uma **lei logaritmica de parede integrada**
sobre a primeira camada sigma (eqs. 7.15-7.18, rotina `getustbcfuhi`):

$$u_* = \frac{\kappa}{\ln\left(\frac{zu_{j,1} + \beta z_0}{e\, z_0}\right)} U_{j,1} = U_{j,1}\sqrt{c_f}$$

com $\kappa$ a constante de von Karman, $z_0$ a altura de rugosidade e $\beta$ igual a 1 ou 9.
Ha seis variantes de lei log selecionaveis (`m = 0..5`, default `m = 1`).

*Remark 7.4.1*, importante: *"The log-law wall function is valid for fully developed flow. [...]
Therefore, Equation (7.18) underestimates the bed friction for unsteady flows."*

### 2.9 Pressao baroclinica

Integrada **analiticamente** supondo densidade linear dentro de cada celula (eqs. 7.93-7.96,
rotina `addbaroc2`). Com $\rho(z) = \rho_2 + \alpha z$:

$$F(z) = P_2 \Delta z_l + \tfrac{1}{2} g \rho_2 \Delta z_l^2 + \tfrac{1}{6} g \alpha \Delta z_l^3$$

Integrada no tempo por **Adams-Bashforth** (eq. 7.97), com Euler explicito no primeiro passo:

$$\text{baroc}^{n+1} = \left(1 + \tfrac{1}{2}f_{\Delta t}\right)\text{baroc}^n - \tfrac{1}{2}f_{\Delta t}\,\text{baroc}^{n-1}$$

E o unico termo com esse tratamento. Todo o resto e theta ou explicito.

### 2.10 O erro de coordenada sigma

TRM secao 7.11 e UM 3.3.3. Problema classico: a transformacao sigma introduz uma derivada
vertical dentro do gradiente horizontal, e em declive forte isso gera **mistura artificial**. O
FM aplica o tratamento de Stelling e Van Kester (1994). UM 3.3.3:

> In estuaries and coastal seas the vertical grid may deteriorate strongly in case of steep bed
> slopes. In order to avoid artificial flow the numerical approximation of the baroclinic
> pressure terms requires a special numerical approach.

O TRM 7.11 observa que em coordenadas sigma **os fluxos advectivos nao introduzem erro de
truncamento grande**; o problema esta nos fluxos difusivos.

### 2.11 Seco/molhado

`epsHu` define face molhada. Uma celula entra no sistema de continuidade se pelo menos uma face
vizinha estiver molhada (`Algorithm 18: setkfs`):

$$kfs(k) = \begin{cases} 0, & hu_j = 0 \;\; \forall j \in J(k) \\ 1, & \text{caso contrario} \end{cases}$$

UM 3.9 registra como hipotese assumida, nao como bug: *"the drying and flooding procedure leads
to a discontinuous movement of the closed boundaries at tidal flats"* e *"A continuity cell is
set dry when all surrounding velocity points at the grid cell faces are dry or when the actual
water depth at the cell centre is below zero (negative volume)."*

---

## Parte 3 - Quais hipoteses apertam no regime do Stagnone

Onde a teoria acima encosta no que ja observamos no modelo.

### 3.1 Celulas intertidais: *Remark 6.2.9* e o mecanismo, nao a consequencia

A laguna tem ~3,2% de celulas intertidais e ja registramos blowup de sal ali
(`v04_salt_blowup_silent_stall`, mitigado com `saliMax = 80`). O *Remark 6.2.9* da o mecanismo
numerico: na interface seco/molhado, faces secas entram na reconstrucao de Perot com velocidade
zero assumida, e o vetor de velocidade no centro da celula **pode ser inconsistente com o
escoamento local**. Isso corrompe a adveccao de momento, que por sua vez alimenta o transporte.

Nao e um bug do nosso setup. E uma limitacao declarada da construcao de Perot sobre malha
staggered com wetting/drying. Vale citar assim no paper, em vez de tratar como instabilidade
generica.

### 3.2 Declive nas bocas: *Remark 7.6.1* mais o erro sigma

Rodamos `layerType = 1` (todas sigma), `kmx = 10`, `stretchType = -1` (uniforme). Nas bocas
(Boca Nord / Boca Sud) o gradiente de nivel de camada e grande por causa do declive. Duas coisas
se somam ali:

1. O termo $\nabla_H \sigma \cdot \nabla u$ da difusao vertical esta **negligenciado** por
   escolha de implementacao, e o manual diz que o erro fica grande exatamente nessa condicao.
2. O erro de mistura artificial da coordenada sigma, mitigado mas nao eliminado por Stelling e
   Van Kester.

Ambos empurram na direcao de mistura vertical excessiva, que e o sinal oposto ao que precisamos
para sustentar hipersalinidade. Conecta com `v03c_validation_findings` (hipersalinidade erode em
12 h sem evaporacao ERA5): parte da erosao pode ser numerica, nao so falta de forcante.

**A investigar:** rodar um caso com `layerType = 2` (z-layers) na mesma janela isolaria a
contribuicao do erro sigma. z-layers nao tem gradiente de nivel de camada, entao o Remark 7.6.1
deixa de morder.

### 3.3 Atrito de fundo subestimado em escoamento nao-estacionario

*Remark 7.4.1* diz que a lei log de parede subestima o atrito de fundo em escoamento nao
desenvolvido. Regime de mare em laguna rasa e nao-estacionario por definicao, com reversao a
cada semi-ciclo.

Isso e relevante para a calibracao de rugosidade variavel: parte do que estamos compensando com
`Ks`/Manning pode estar cobrindo esse vies estrutural do esquema 3D, nao so rugosidade fisica.
Ver `ingrassia_2024_vr_calibration` e `baptist_153_vs_154_tradeoff`.

### 3.4 Trachytope 154 em 3D: o manual desaconselha explicitamente

TRM secao 7.4.2.4 (p. 143), sobre trachytopes em 3D:

> The second implementation of the Baptist vegetation formula (154) splits its effect over the
> bed roughness term and a flow resistance term (this approach is copied to a number of
> undocumented trachytope formulas related to vegetation still under development).
>
> The velocity effect and the vegetation resistance term **have not yet been properly validated
> in 3D**. As long as trachytope formulas 103, 104, and 154 (or similar formulas under
> development) are not used, the trachytopes can be applied for both 2D and 3D.

Ou seja: o manual desaconselha 103, 104 e 154 em 3D. Isso bate com o que ja derivamos
empiricamente em `baptist_153_vs_154_tradeoff` e `fm_veg_2d_vs_3d_paths`. Vale citar o manual no
paper como respaldo independente da observacao.

### 3.5 Limitador de Smagorinsky esta disparando no v04AE

Verificado em 2026-09-14 nos `.dia` particionados de
`model/dflowfm_v04AE/DFM_OUTPUT_Stagnone_dxy01_15m/`:

```
** WARNING: Viscosity coefficient was limited for 10 links.
** WARNING: Viscosity coefficient was limited for 40 links.
** WARNING: Viscosity coefficient was limited for 247 links.
[...]
** INFO   : Viscosity coefficient/Horizontal transport flux were limited on some links in the
            course of computation.
```

Magnitudes pequenas (dezenas a ~250 links por ocorrencia). **Porem**: o UM 3.3.5 avisa que o
manual para de escrever essas linhas **depois de dez avisos** por arquivo, para nao inflar o
`.dia`. Confirmado, 4-5 ocorrencias por particao antes do corte. Logo **o `.dia` nao mostra a
extensao real** do limitador ao longo da simulacao, so que ele comecou a agir.

Nao e alarmante na escala observada, mas fica registrado: a viscosidade horizontal efetiva em
alguns links **nao e** a que o Smagorinsky pediu, e sim a que o criterio de estabilidade
permitiu. Se algum dia investigarmos dissipacao horizontal anomala, este e um suspeito.

**Causa identificada (2026-09-14).** Rodamos `transportAutoTimestepDiff = 0`, documentado como
"lim diff, no lim Dt". A secao 6.3.2 do TRM explica o que isso significa: *"the horizontal
diffusion coefficient is probably reduced in order to satisfy the stability condition"*, em vez
de reduzir o passo de tempo. A mensagem do `.dia` e exatamente essa opcao agindo como projetada,
nao uma anomalia. As alternativas sao `= 1` (preserva a difusao, reduz $\Delta t$, fica mais
caro) e `= 3` (integracao implicita da difusao horizontal, **so 2D**, portanto indisponivel para
nos com `kmx = 10`).

### 3.6 Nao-conservacao de momento com `teta0 = 0.55`

*Remark 6.2.7* garante que a adveccao e nao-conservativa para escoamento nao-estacionario com
$\theta > 0$. Rodamos `teta0 = 0.55`. Em balanco de massa de volume isso nao aparece (a
continuidade e conservativa por construcao), mas em **balanco de momento** sim.

Implicacao para o trabalho lagrangeano: parte do erro de transporte que atribuimos a windage ou
resolucao de regrid pode ter componente de nao-conservacao de momento do esquema. Conecta com
`windage_wind_speed_hypothesis` e `regrid_grid_resolution_untested`, que fecharam as outras duas
frentes sem explicar tudo.

### 3.7 Intertidal: o mecanismo completo esta na secao 6.6, nao so no Remark 6.2.9

A secao 3.1 acima atribuia a patologia intertidal ao *Remark 6.2.9* (faces secas entram na
reconstrucao de Perot com velocidade zero assumida). A leitura da secao 6.6 do TRM mostra que
esse e so um dos seis mecanismos empilhados na mesma regiao. Detalhe completo na Parte 6.11.
Em resumo, nas celulas intertidais atuam simultaneamente:

1. Reconstrucao de Perot inconsistente perto da interface (*Remark 6.2.9*).
2. Adveccao de momento, atrito de fundo e fluxos viscosos **zerados** em faces secas (6.6.2).
3. Amortecimento de $A_e$ por `chkadv`, que o proprio manual **nao sabe justificar**
   (*Remarks 6.6.2 e 6.6.3*).
4. Coriolis limitada **duas vezes**, por `chkadv` e por `trshcorio` (*Remark 6.6.4*).
5. Operadores espaciais e temporais aplicados **fora das condicoes em que sao validos**, com a
   admissao explicita do *Remark 6.6.6*: *"they are not allowed to be applied without
   modification. However, they are."*
6. Velocidade normal residual nao nula em faces que secaram durante o passo, usada na avaliacao
   de adveccao e difusao do passo seguinte (*Remark 6.6.7*).

Para o paper isso melhora bastante o argumento. Em vez de "instabilidade numerica nas celulas
intertidais", da para escrever que a regiao intertidal acumula seis aproximacoes declaradas pelo
proprio manual, duas delas sem justificativa fisica assumida pelos autores. Conecta com
`v04_salt_blowup_silent_stall` e com a mitigacao por `saliMax = 80`.

Uma nota de precisao: o *Remark 6.6.1* (area de leito molhada de celula parcialmente molhada
calculada incorretamente) **nao se aplica ao nosso setup**. Ele vale so no caso nao-linear, e
rodamos `nonlin2D = 0`, alem de `bedLevType = 1` e `conveyance2D = -1`, o que o torna
duplamente inerte. No nosso regime a celula esta inteiramente molhada ou inteiramente seca, que
e o "discontinuous movement of the closed boundaries" declarado no UM 3.9.

---

## Parte 4 - Mapa manual -> rotina

O fonte nao esta na instalacao, mas os manuais nomeiam as rotinas. Para confrontar com o
repositorio aberto do Deltares:

| Bloco | Equacoes | Rotina |
|---|---|---|
| Niveis de fundo por `bedLevType` | TRM 6.9-6.11 | `setbobs` |
| Reconstrucao Perot centro de celula | TRM 6.42-6.49 | `setlinktocenterweights`, `setucxucyucxuucyu` |
| Adveccao $A_i$/$A_e$ (`advi`/`adve`) | TRM 6.33-6.41 | `advec` |
| Limitadores de reconstrucao | TRM Tab. 6.2, Alg. 11-12 | (ver `advec`) |
| Interpolacao nodal (difusao, conveyance) | TRM 6.51 | (Alg. 9-10) |
| `fu`/`ru` 2D | TRM 6.121-6.122 | `furu` |
| Montagem da matriz de nivel | TRM 6.126-6.128 | `s1ini`, `pack_matrix`, `setkfs` |
| Camadas nas faces (3D) | TRM 7.12, Alg. 50 | `sethu` |
| Perfil vertical `fu`/`ru` | TRM 7.29-7.31 | `vertical_profile_u0`, `tridag` |
| Atrito de fundo log-law 3D | TRM 7.15-7.18 | `getustbcfuhi` |
| Pressao baroclinica | TRM 7.93-7.97 | `addbaroc2` |
| Estiramento de camadas sigma | TRM 7.10-7.11, Alg. 49 | `flow_allocflow` |
| Passo completo (orquestracao) | TRM Alg. 34, Tab. 6.3 | `flow_single_timestep` |
| Fase preditora | TRM Alg. 35 | `flow_initimestep` |
| Coriolis, viscosidade, vel. nodais | TRM Alg. 36 | `setumod`, `setcornervelocities` |
| Forcas externas + limitador `chkadv` | TRM Alg. 39 | `setextforcechkadvec` |
| Volume e area molhada (nao-linear) | TRM 6.213-6.215, Alg. 38 | `volsur` |
| Transporte com LTS | TRM 7.19, Alg. 52 | `transport` |
| Fluxos verticais | TRM 7.38-7.39, Alg. 57 | `u1q1` |
| Turbulencia k-eps / k-tau | TRM 7.43-7.44, Alg. 58-60 | `update_verticalprofiles` |
| Solver da eq. de nivel | TRM 6.141-6.142, Alg. 25-26 | `solve_matrix`, `conjugategradient` |
| Preparo Min-degree + Gauss | TRM 4.2.1 | `prepare` |
| Passo paralelo | TRM Alg. 65-66 | `parallel step_reduce`, `parallel u1q1` |

---

## Parte 5 - Para aprofundar

Estado em 2026-09-14. Os pontos 2, 4 e 5 foram fechados na Parte 6.

1. **Conferir a Tabela 6.1 no PDF renderizado.** A extracao por `pdftotext` embaralhou a tabela
   (colunas fora de ordem). A leitura de que 3 e 33 compartilham linha esta correta mas vale
   confirmar visualmente antes de citar em publicacao. **Em aberto.**
2. ~~**Secao 6.6.3** (`chkadv`, `trshcorio`)~~ **Fechado**, ver Parte 6.11 e 3.7. A hipotese
   estava certa: e o complemento direto do *Remark 6.2.9* para o caso intertidal, e rende mais
   do que se esperava (cluster de sete *Remarks*, 6.6.1 a 6.6.7).
3. **Secao 6.4.3** (`jacstbnd`) e a memoria `densin_false_fixes_nowaves_morph`, que registra
   `cstbnd` como inerte, confirmado duas vezes. Vale ler a secao para entender **por que** e
   inerte no nosso setup. **Em aberto.**
4. ~~**Secao 7.8.3/7.8.4**, k-epsilon e k-tau~~ **Fechado**, ver Parte 6.6.
5. ~~**Secao 7.5**, equacao de transporte, e secao 6.3.2~~ **Fechado**, ver Parte 6.5 e 6.9.
6. **Teste z-layers** proposto em 3.2, para isolar o erro de coordenada sigma. **Em aberto.**
7. **Fonte Fortran.** Baixar do repositorio aberto do Deltares e confrontar `advec` e
   `vertical_profile_u0` com as eqs. 6.33-6.41 e 7.29-7.31, especialmente o tratamento de faces
   secas na reconstrucao. **Em aberto.**

Novos pontos abertos pela Parte 6:

8. **Justificar `limTypMom = 4` / `limTypSa = 4` em vez de 3.** O valor 3 (Koren) aparece no
   comentario do MDU mas **nao consta da Tabela 6.2**. O 4 esta documentado. Se um revisor
   perguntar, 4 e defensavel e 3 nao.
9. **Avaliar `AutoTimestep = 5`.** A secao 6.3.3 diz que e o unico criterio com estabilidade
   observada em modelos 3D com sal, mas custa ~4x. Vale medir quanto custa de fato na nossa
   malha antes de descartar por reputacao.
10. **Rastrear a origem dos fluxos verticais** dado o *Remark 7.7.1* (fechamento nao nulo na
    superficie). Interage com 3.2 e com o transporte de sal.

## Parte 6 - Catalogo de esquemas numericos

Levantado em 2026-09-14. Aviso de navegacao antes de tudo: a **secao 4.1 do TRM, "Time
integration", esta literalmente vazia**, so um `...` no lugar do texto. Quem procura os esquemas
pelo sumario nao acha. Eles estao dispersos em 6.2, 6.3, 6.6, 7.4-7.8 e 8.1.5.

### 6.1 Integracao no tempo: quem e implicito e quem nao e

Esquema global e um **theta-method semi-implicito**, `0.5 < teta0 < 1`. A escolha do que fica
implicito nao e uniforme, e e isso que define custo e estabilidade.

| Termo | Tratamento | Referencia |
|---|---|---|
| Gradiente de nivel (barotropico) | Implicito, peso $\theta$ | TRM 6.121 |
| Atrito de fundo | Implicito | TRM 6.121, via `frj` em `furu` |
| Adveccao horizontal de momento | **Explicito** (`A_e`), com parcela implicita `A_i` | TRM 6.33-6.34 |
| Adveccao vertical de momento | Escolha do usuario (`javau`) | TRM 7.21 |
| Difusao vertical | Implicito | TRM 7.21 |
| Difusao horizontal | Explicito por default | TRM 6.3.2 |
| Storage term | **Sempre explicito** | TRM p. 48 |
| Pressao baroclinica | Adams-Bashforth 2a ordem | TRM 7.97 |
| Coriolis | Adams-Bashforth 2a ordem | TRM 5.12.1.2.2 |
| Transporte (sal, temp, tracador) | Horizontal explicito com LTS, difusao vertical implicita | TRM 7.5 |
| Turbulencia (k, epsilon ou tau) | Horizontal explicito, vertical implicito | `turbulenceAdvection = 3` |

O ponto estrutural: **a adveccao horizontal e explicita**, e e ela quem limita o passo de tempo.
Todo o resto do desenho gira em torno disso.

### 6.2 Adveccao de momento: a familia Perot

Tabela 6.1 do TRM (p. 51), controlada por `advecType` (`iadv`). Duas familias, Wenneker e Perot,
que diferem no tratamento do storage term.

| `advecType` | Esquema |
|---|---|
| 0 | sem adveccao |
| 1, 2 | Wenneker |
| **3, 33** | Perot `q(uio-u)`, sendo **33 a implementacao rapida do 3** |
| 4, 5 | Perot `q(ui-u)`, com 5 excluindo a propria face |
| 6, 8 | variantes sobre o conjunto de fluxos entrantes $J_i$ |
| 7, 9, 11 / 8, 10, 12 | $\lambda$ fixo em 1 |
| 30, 31, 34, 36, 37, 38, 333 | variantes de peso e de velocidade reconstruida |

Cinco coisas mudam entre linhas: o conjunto de faces ($J$ ou so as entrantes $J_i$), qual fluxo
entra ($q_l$ ou $qa_l$), o coeficiente $\lambda$, qual velocidade e usada, e os pesos
$A_{Lj}$/$A_{Rj}$. O $\lambda$ sai de um numero de Courant por face (eqs. 6.37-6.39).

### 6.3 Limitadores

Tabela 6.2, valendo para `limtypmom`, `limtypsa` e `limtyphu`.

| Valor | Limitador | $\psi(r)$ |
|---|---|---|
| 0 | upwind de 1a ordem | $0$ |
| 1, 5, 15 | minmod | $\max(\min(r,1),0)$ |
| 2 | Van Leer | $\dfrac{r+\lvert r\rvert}{1+\lvert r\rvert}$ |
| 4, 14 | monotonized central | $\max\left(\min\left(\min\left(2r,\tfrac{1+r}{2}\right),2\right),0\right)$ |

**Duas observacoes operacionais:**

- O valor **3 (Koren) aparece no comentario do MDU mas nao consta da Tabela 6.2**. Ver ponto 8
  da Parte 5.
- A eq. 6.68 multiplica a correcao de alta ordem por
  $\max\left(1 - \tfrac{\Delta t \lvert u_j \rvert}{\Delta x_j}, 0\right)$. Ou seja, **o esquema
  degrada sozinho para upwind de 1a ordem quando o Courant local se aproxima de 1**, qualquer
  que seja o limitador escolhido. A ordem efetiva nao e propriedade fixa do setup, varia com o
  campo de escoamento.

*Remark 6.2.15*: os limitadores 1 a 4 sao formulados usando a propriedade de simetria
$\psi(r) = r\,\psi(1/r)$.

### 6.4 Adveccao vertical de momento

`vertAdvTypMom` (`javau`): 3 = upwind implicito, 6 = upwind centrado explicito, 0 = desligado,
4 = central.

- *Remark 7.6.2*: o esquema central *"may lead to instabilities"*.
- *Remark 7.6.3*: desligar *"may lead to non-physical results"*.
- Secao 6.3.3, preferencia declarada da Deltares: *"We prefer the explicit vertical advection
  scheme over the implicit vertical advection scheme, because it is less prone to
  checkerboarding."*

### 6.5 Transporte: o unico bloco com local time stepping

Secao 7.5, o esquema mais elaborado do codigo. A equacao (TRM 7.19):

$$\frac{\partial (Vc)}{\partial t} = -\nabla \cdot (Qc) + \nabla \cdot (\Gamma \nabla c) + h(S_{sour} - S_{sink}c)$$

Decisoes de projeto:

- Adveccao horizontal e vertical discretizadas com **monotonized central**.
- Horizontal e adveccao vertical **explicitas**; difusividade vertical **implicita**.
- **Fontes explicitas, sumidouros implicitos**, textualmente *"for guaranteeing positive
  solutions"*.
- **LTS (local time stepping)** seguindo Sanders (2008). Cada celula recebe seu proprio numero
  de sub-passos a partir de um Courant local, para que celulas grandes nao paguem o passo da
  menor celula da malha.
- Fechadas as contribuicoes explicitas, cada coluna d'agua vira um sistema **tridiagonal**
  resolvido por Thomas (`Algorithm 52: transport`, mais `Algorithm 54: tridag`).

O manual encerra dizendo que ao final do LTS todas as celulas avancaram um $\Delta t$ completo
*"in a fully conservative fashion"*. Ver 6.10 para a tensao entre essa frase e o *Remark 7.7.1*.

**Contraste que vale reter: transporte e conservativo, momento nao e.**

### 6.6 Turbulencia: quatro fechamentos, todos tridiagonais

`turbulenceModel` 0 a 4.

| Valor | Modelo | Caracteristica |
|---|---|---|
| 0 | nenhum | |
| 1 | constante | manual avisa que da perfil vertical **parabolico, como laminar** |
| 2 | algebrico | $L = \kappa z (1 - z/h)$, $\nu_V = L u_*$, sem equacao de transporte |
| 3 | k-epsilon | duas equacoes de transporte |
| 4 | k-tau | $\tau = k/\varepsilon$, $\nu_V = c_\mu k \tau$, com $c_\mu = 0{,}09$ |

k-epsilon e k-tau sao montados como sistemas tridiagonais por coluna e resolvidos pelo mesmo
`tridag` (Algorithms 59 e 60, rotina `update_verticalprofiles`). A producao $P_k$ usa **apenas
gradientes verticais** da velocidade horizontal, coerente com a hipotese declarada no UM 3.9.
A flutuabilidade entra por $B_k = -g\frac{\nu_V}{\sigma_\rho}\frac{\partial \rho}{\partial z}$,
com a parte positiva tratada implicitamente e a negativa explicitamente.

### 6.7 Pressao baroclinica e Coriolis: Adams-Bashforth

Ambos usam Adams-Bashforth de 2a ordem, e sao os unicos termos com esse tratamento.

Baroclinico (eq. 7.97), com Euler explicito no primeiro passo. Coriolis (secao 5.12.1.2.2),
ativo com `Newcorio = 1` e `0 < Icoriolistype < 40`, com `Corioadamsbashfordfac` tipicamente
0,5.

*Remark 5.12.2*, gotcha com relevancia para restart: o teste que detecta o primeiro passo
verifica se $F_c(u^{n-1}) = 0$, mas **esse teste tambem passa quando a velocidade inicial e
zero**, rebaixando desnecessariamente para Euler de 1a ordem. Interage com
`restart_chain_n_minus_2_workflow`. Parte do motivo de dropar as primeiras 24 h pode estar
absorvendo esse rebaixamento, alem do ramp-up fisico.

### 6.8 Solvers lineares

A equacao de nivel d'agua e a unica equacao global que resta. Resolvida em tres etapas
(`Algorithm 25: solve_matrix`):

1. **Minimum degree** reordena e reduz o sistema. A permutacao e calculada so na inicializacao.
2. **Eliminacao de Gauss** resolve os nos de grau ate `maxDegree` (`maxdgr`).
3. **Gradiente conjugado precondicionado** resolve o resto (`Algorithm 26`), com precondicionador
   diagonal ou Cholesky incompleta.

Recomendacao de calibracao do capitulo 4 que raramente e citada: o mais rapido **em numero de
iteracoes** e `maxdgr` tao grande quanto a memoria permitir com precondicionamento LUD, **mas o
mais rapido em tempo de parede** e um `maxdgr` moderado, tal que cerca de **50% dos pontos**
sejam eliminados por Gauss, combinado com Jacobi pontual. Rodamos `maxDegree = 6`.

Em paralelo (secao 8.1.5) ha duas opcoes, a versao paralelizada do CG sequencial ou PETSc
(Balay et al., 2013). `icgSolver = 4` e sobekGS mais Saad-ILUD.

*Remark 6.3.2*: o criterio de parada e baseado **apenas no residuo** $r^{(p)}$, nao no residuo
precondicionado, embora o manual registre que gostaria da segunda opcao.

**Nested Newton** (secao 6.10), Casulli e Stelling (2013), substitui a fenda de Preissmann para
escoamento pressurizado. O manual diz que o algoritmo *"is changed for 1d models"*. Logo o
`EpsMaxlevM` do nosso MDU esta **inerte** num modelo puramente 2D/3D.

### 6.9 Passo de tempo automatico, e a secao mais honesta do manual

A secao 6.3.3 nao usa CFL literal. O criterio e razao entre volume e fluxos de saida:

$$\Delta t^{n+1} = \mathrm{CFL} \cdot \min_{k}\left(\frac{V_k^n}{squh_k^n}\right)$$

onde $squh$ soma os fluxos horizontais **de saida** da celula. A motivacao declarada nao e
estabilidade pura, e **evitar que o solve implicito produza nivel abaixo do fundo local**, o que
obrigaria a remover a celula do sistema e resolver de novo.

Opcoes de `AutoTimestep`: 1 (2D), 3 (3D horizontal), 5 (3D com fluxos verticais, $squhv$), 8
(como 5 ignorando a camada de topo, para z-layers).

E entao, sobre modelos 3D com transporte de sal:

> Because we have an explicit treatment of baroclinic terms, there is even more reason to apply
> the time step criterion involving the vertical fluxes `AutoTimestep=5` [...] If we do so, we
> never encountered instabilities so far. However [...] the resulting time step is about four
> times smaller than is allowed for accuracy. Hence, **in practice, we never apply
> `AutoTimestep=5` simply because it is too expensive.** We apply `AutoTimestep=3`, in
> combination with `Dtmax` [...] For now, we **live with non-guaranteed stability** of
> `AutoTimestep=3` in combination with `Dtmax`.

Rodamos exatamente `autoTimestep = 3` com `dtMax = 30.0`. Estamos na configuracao que a propria
Deltares usa e descreve como estabilidade nao garantida. Nao e defeito do nosso setup, e o
estado da arte declarado, e e uma frase citavel quando um revisor perguntar por que o modelo as
vezes trava. Conecta com `v04_salt_blowup_silent_stall` e `nowaves_dm_killed_not_unstable`.

### 6.10 As admissoes de nao-conservacao, reunidas

Aparecem em capitulos distantes. Vale te-las juntas:

| Remark | O que diz |
|---|---|
| 6.2.6 | Nenhum esquema de adveccao de momento e conservativo no sentido de Perot |
| 6.2.7 | Adveccao e nao-conservativa para escoamento nao-estacionario com $\theta > 0$ |
| 6.6.1 | A area de leito molhada de uma celula **parcialmente molhada e calculada incorretamente** (falta a integral ao longo da fronteira seco/molhado interna a celula). Vale so no caso nao-linear |
| **7.7.1** | Na marcha dos fluxos verticais do fundo para o topo, o fluxo na superficie **nao fecha em zero**. O erro *"is supposed to be small, and it is neglected. Hence, the procedure is not fully mass conservative"* |

Note a tensao entre 7.7.1 e a secao 7.5, que afirma que o transporte avanca *"in a fully
conservative fashion"*. As duas frases estao no mesmo capitulo, a nove paginas de distancia. A
leitura consistente e que o **esquema** de transporte conserva em relacao aos fluxos que recebe,
mas os **fluxos verticais que ele recebe** ja carregam o erro de fechamento da secao 7.7.

### 6.11 Profundidades pequenas: o cluster de Remarks da secao 6.6

Complemento direto do *Remark 6.2.9* para o caso intertidal, e rende mais do que se esperava.

Faces secas afetam quatro coisas (secao 6.6.2): areas de leito molhadas e volumes, adveccao de
momento (zerada), atrito de fundo (zerado) e fluxos viscosos (zerados).

**Limitacao de `Ae` por `chkadv`** (`Algorithm 39: setextforcechkadvec`). Para profundidades
pequenas, $A_{ej}$ e amortecido por $\min(h/h_{chkadv}, 1)$ quando ha desnivel forte entre as
celulas vizinhas. Os dois *Remarks* seguintes sao notaveis:

- *Remark 6.6.2*: **"It is unclear why the term $A_{ej}$ needs to be limited to zero for
  vanishing water depths."**
- *Remark 6.6.3*: **"It is unclear why only the term $A_{ej}$ is limited, and not the other
  terms. In the first place $A_{ij}$, but also the remaining terms."**

Ou seja, o proprio manual nao sabe justificar o limitador que o codigo aplica.

**Limitacao de Coriolis por `trshcorio`** (`Algorithm 40`), com $h_{trshcorio} = 1$ m de default.
A forca de Coriolis normal e multiplicada por $\min(h_{min}/h_{trshcorio}, 1)$. *Remark 6.6.4*
observa que Coriolis acaba limitada **duas vezes**, por 6.39 e por 6.40.

**Discretizacao temporal perto da fronteira** (secao 6.6.4). Se a face esta seca no inicio do
passo, assume-se fluxo nulo e $u_j^n = 0$. Tres *Remarks*:

- *Remark 6.6.5*: essa hipotese **impoe uma limitacao de passo de tempo**.
- *Remark 6.6.6*: **"Setting the face-normal velocities in the dry area to zero does not seem to
  obey a moving wet/dry boundary condition. Hence, the spatial operators and temporal
  discretization are not allowed to be applied without modification. However, they are."**
- *Remark 6.6.7*: uma face que estava molhada e seca **durante** o passo mantem velocidade normal
  nao nula no nivel de tempo antigo, e essa velocidade **e usada na avaliacao de adveccao e
  difusao no inicio do passo seguinte**, embora a face esteja seca. Faces ja secas desde o passo
  anterior tem velocidade zero.

O *Remark 6.6.6* e o mais forte do manual inteiro. E uma declaracao de que os operadores estao
sendo aplicados fora das condicoes em que sao validos, seguida de "no entanto, sao".

### 6.12 Ordem de execucao de um passo

`Algorithm 34: flow_single_timestep`, com as fases 35 e 36. Util para saber o que ja esta
atualizado quando cada termo e avaliado:

1. `flow_initimestep` (fase preditora): calcula $h_k^n$, atualiza contornos em $\hat{t}^{n+1}$,
   `sethu` (alturas nas faces), `setau` (areas de escoamento), `setumod` (reconstroi $uc_k$,
   $uq_k$, velocidades tangenciais, **Coriolis**, velocidades nodais, **fluxos viscosos**),
   coeficientes de atrito, **calcula o passo de tempo**, `advec` (adveccao), e
   `setextforcechkadvec` (forcas externas mais o limitador de profundidade pequena).
2. `step_reduce` (fase corretora): monta e resolve o sistema de nivel d'agua com iteracao de
   Newton, calcula volumes e areas molhadas, e so entao obtem $u_j^{n+1}$, $q_j^{n+1}$,
   $qa_j^{n+1}$.

Note que **Coriolis e viscosidade sao avaliados antes da adveccao**, e ambos entram somando em
$A_e$. A Tabela 6.3 do TRM traduz cada simbolo para o nome da variavel no codigo (`s0`, `s1`,
`u0`, `u1`, `q1`, `qa`, `vol1`, `A1`, `dts`, `adve`, `advi`, `ucx`, `ucy`, `hu`, `Au`, `hs`).

### 6.13 O que o nosso setup seleciona

Do `model/dflowfm_v04AE/Stagnone_dxy01_15m.mdu`:

| Keyword | Valor | Esquema selecionado |
|---|---|---|
| `teta0` | 0,55 | theta-method quase Crank-Nicolson |
| `advecType` | 33 | Perot `q(uio-u)`, implementacao rapida |
| `limTypMom` / `limTypSa` | 4 / 4 | monotonized central (ver ponto 8 da Parte 5) |
| `limTypHu` | 0 | sem limitador na profundidade da continuidade |
| `vertAdvTypMom` | 6 | upwind centrado **explicito** (preferido pela Deltares) |
| `vertAdvTypSal` | 4 | theta implicito |
| `turbulenceModel` | 3 | k-epsilon |
| `turbulenceAdvection` | 3 | horizontal explicito, vertical implicito |
| `icgSolver` | 4 | sobekGS + Saad-ILUD |
| `maxDegree` | 6 | corte da eliminacao de Gauss |
| `autoTimestep` | 3 | 3D horizontal, **estabilidade nao garantida** por 6.3.3 |
| `dtMax` | 30,0 s | teto por acuracia |
| `CFLMax` | 0,7 | default do FM |
| `transportAutoTimestepDiff` | 0 | **limita a difusao**, nao o passo (ver 3.5) |
| `nonlin2D` | 0 | sem iteracao nao-linear de volume, logo *Remark 6.6.1* nao se aplica |
| `epsHu` | 1e-4 | limiar de face molhada |
| `EpsMaxlevM` | 1e-8 | Nested Newton, **inerte** em modelo 2D/3D |

## Referencias citadas pelos manuais

- Perot, B. (2000). Conservation properties of unstructured staggered mesh schemes.
- Kramer, S.C. e Stelling, G.S. (2008). Aplicacao as equacoes de aguas rasas.
- Kleptsova, O. et al. (2010). Idem.
- Borsboom, M. (2013). Sutilezas na discretizacao da adveccao em formulacao primitiva.
- Stelling, G.S. e Van Kester, J.A.T.M. (1994). Mistura artificial em coordenadas sigma.
- Rodi, W. (1984). Conceito de viscosidade turbilhonar.
- Uittenbogaard, R. et al. (1992). Parte "3D-turbulence" da viscosidade horizontal.
- Sanders, B.F. (2008). Local time stepping para equacoes de aguas rasas, base do esquema de
  transporte da secao 7.5.
- Casulli, V. e Stelling, G.S. (2013). Nested Newton, escoamento pressurizado (so 1D).
- Preissmann, A. e Cunge, J.A. (1961). A fenda de Preissmann, que o Nested Newton substitui.
- Balay, S. et al. (2013). PETSc, solver paralelo alternativo.
- Bruaset, A.M. (1995). Propriedades de convergencia de CG com eliminacao previa.
- Sweers, H.E. (1976). Coeficiente de troca de calor no modelo de excesso de temperatura.
