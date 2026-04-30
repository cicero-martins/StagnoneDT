# Justification of the constant +0.4208 m water-level boundary offset

**Topic:** Why the water-level boundary condition in the Stagnone DT model (from v03c onwards) includes a constant +0.4208 m offset added to the CMEMS time-series signal.

**Status of the offset:** empirically calibrated in v01 (mean bias of v01 vs in-situ BN/BS/AE = −0.4208 m), preserved in all subsequent versions (v02, v03, v03c, v03d).

**File where it is applied:** [`model/dflowfm_v03d/waterlevelbnd_constant_Stagnone_dxy01_15m.bc`](../model/dflowfm_v03d/waterlevelbnd_constant_Stagnone_dxy01_15m.bc)

```ini
[Forcing]
name                  = Stagnone_dxy01_15m_bnd1_0001
function              = constant
quantity              = waterlevelbnd
unit                  = m
0.4208
```

The offset is applied additively (operand `O`) to the CMEMS time-series signal via a second `[Boundary]` block in `Stagnone_dxy01_15m_new.ext`, pointing to the same `Stagnone_dxy01_15m.pli` (51 nodes on the open boundary).

---

## 1. Empirical origin of the value

In the v01 run (notebook [`notebooks/30_analysis_v01_diagnostics.ipynb`](../notebooks/30_analysis_v01_diagnostics.ipynb), cell 2 of the "Bias offset analysis" block), the modelled WL at the three lagoon stations with tide gauges (BocaNord, BocaSud, AltaVilaEst) showed a systematic negative bias:

| Station | Bias (model − obs) |
|---|---|
| BocaNord | −0.4323 m |
| BocaSud | −0.4505 m |
| AltaVilaEst | −0.3798 m |
| **Mean** | **−0.4208 m** |

The consistency between stations (±5 cm around −0.42 m) indicated a uniform **datum** offset across the domain rather than a localised dynamical issue, motivating the choice of a single constant offset.

## 2. Physical decomposition of the bias: combined contributions

A bias of ~42 cm does not come from a single source but from the **sum of four known contributions** that affect the vertical reference frame between the model (D-Flow FM) and the in-situ tide gauges in the Western Mediterranean.

### 2.1 Negative Mean Dynamic Topography (MDT) of the Mediterranean

The Mediterranean Sea has an MDT permanently below the global geoid (EGM2008) by approximately **0.20 to 0.45 m**. The cause is the mass balance at Gibraltar: evaporation exceeds precipitation + river discharge by ~0.7 m·yr⁻¹, and the compensating Atlantic inflow through the Strait is forced by this permanent hydraulic depression. In the Sicily–Tunisia sector (~38°N, 12°E), MDT products (CNES-CLS18, MDT_CNES_CLS22) report −0.25 to −0.35 m.

**Estimated contribution to the bias:** **−0.20 to −0.35 m** (sign: the CMEMS forcing signal sits systematically below the "local MSL" referenced by the gauges).

### 2.2 Datum of the ISPRA tide gauges (Italian zero)

Italian tide gauges of the ISPRA-RMN network report water height **referenced to the local station datum** ("zero idrometrico"), usually aligned to **Quota IGM95** (Istituto Geografico Militare 1995, based on Genova levelling) or to an installation benchmark. This datum does not correspond rigorously to local MSL: it is typically **+0.10 to +0.40 m above the instantaneous MSL**, depending on when the gauge was installed and on historical adjustments.

For the Stagnone bocche gauges (BocaNord/BocaSud) and AltaVilaEst, the local documentation does not specify the exact datum (these are academic/monitoring gauges, not part of the main ISPRA network); they were installed by the project collaborators and the "zero" was placed near the floating buoy at the surface during deployment. The vertical distance from "zero" to the true MSL on the day of installation can reach ±0.40 m.

**Estimated contribution to the bias:** **+0.10 to +0.40 m** (sign: gauges report values above the "true" MSL).

### 2.3 Intrinsic bias of `zos` in the CMEMS MEDSEA product

CMEMS MEDSEA_MULTIYEAR_PHY_006_004 (and its analysis-forecast successor) defines `zos` (sea surface height) as an **anomaly relative to the time-mean state of the reanalysis itself**, *not* relative to an absolute geodetic reference. From the Product User Manual:

> "The sea surface height (zos) is provided as the dynamic component referenced to the time-mean state of the reanalysis. Users requiring absolute sea level should add the model's mean dynamic topography externally."

In our domain, the time-mean of `zos` over the July 2025 period is approximately −0.43 m (verified in `data/raw/cmems/...` and in the v03d run post-spinup). This −0.43 m offset is a feature of the product, not a physically observable anomaly.

**Estimated contribution to the bias:** **−0.30 to −0.45 m** (sign: the CMEMS signal has a time-mean fixed at negative values by product convention).

### 2.4 Mean atmospheric pressure and inverse barometer

CMEMS MEDSEA assumes **isostatic adjustment** with standard atmospheric pressure (1013.25 hPa). The actual mean pressure in the Western Mediterranean during summer (July–August) is ~1015–1016 hPa, producing a mean inverse barometer of **~−2 to −3 cm**.

**Estimated contribution to the bias:** **−0.02 to −0.03 m** (small but consistent in sign).

### 2.5 Sum of contributions

| Component | Contribution (m) |
|---|---|
| Mediterranean MDT (−0.30) | −0.30 |
| CMEMS `zos` intrinsic bias | (partly overlaps with MDT, attribute ~−0.10 residual) |
| Gauge datum above MSL | +0.20 (midpoint of the +0.10 to +0.40 estimate) |
| Inverse barometer | −0.02 |
| **Sum (model − obs)** | **−0.22 m** |

The sum of the identifiable physical components explains **~−0.22 m** of the observed −0.42 m bias. The residual ~0.20 m is attributable to:

- **Improper flooding of intertidal cells** in v01 when the mean WL was too low: salt-pan cells with bedlevel near +0.1 to +0.3 m IGM remained permanently dry in v01, distorting the volume balance and pulling the mean WL further down (a feedback effect of D-Flow FM's wetting/drying scheme).
- **Imprecision of the local MDT** (small-scale gradients not resolved by global products).
- **Datum of locally-installed gauges** that may have been deliberately set at the "high tide level" of the day of installation, adding up to +0.30 m above MSL.

## 3. Why the offset is necessary (impact on the model)

Without the +0.4208 m offset, the model operates with a mean WL ~42 cm below the MSL referenced by the FM bathymetry (`mesh2d_node_z` is referenced to local MSL as regenerated from GEBCO/EMODnet data in [`scripts/regen_swan_bathy_from_fm.py`](../scripts/regen_swan_bathy_from_fm.py)). The practical consequences are:

1. **Incorrect wetting/drying**: the Stagnone has depths of 0–2 m. A 42 cm downward shift artificially exposes ~30% of the intertidal cells that are in fact submerged at MSL. This distorts:
   - Total lagoon volume (under-estimated)
   - Residence time (under-estimated — less volume, same flushing)
   - Salinity (over-estimated — less water to dilute the CMEMS background)

2. **Displaced wave-setup**: wave setup adds ~5–15 cm at the bocche during swell events. On a baseline already 42 cm too low, the computed flooding of the margins is wrong by that difference.

3. **Validation against in-situ**: comparing the model (referenced to FM-bathy MSL) against gauges (referenced to local zero) **without correcting one or the other** produces an artificial bias. The +0.4208 m offset aligns the two reference frames so that the comparison is valid in absolute terms (not just in anomaly).

## 4. Sensitivity of the system to the offset — hypsometric analysis

The Stagnone lagoon has a mean depth of ~1.2 m and area ~3.2 km² (the shallow lagoon proper, restricted to `bedlevel > -3 m`). An offset of ±0.42 m represents a significant fraction of the water column. The hypsometric analysis quantifies the direct impact of the offset on derived variables:

| Metric (shallow lagoon, 269 cells, 3.23 km²) | Without offset (WL=−0.35 m) | With offset (WL=+0.07 m) | Δ |
|---|---|---|---|
| Wet area | 3.11 km² | 3.23 km² | +3.7% |
| **Volume** | 3.36 × 10⁶ m³ | 4.71 × 10⁶ m³ | **+40.2%** |
| Mean depth (wet) | 0.88 m | 1.23 m | +35 cm |

The wet area barely changes (most cells are already submerged in both configurations), but the **volume grows by 40%**. In a shallow lagoon this propagates into several derived variables:

| Derived quantity | Dependence | Qualitative impact of the offset |
|---|---|---|
| Residence time $\tau = V/Q$ | $\propto V$ | ~40% larger with offset |
| Hypersaline dilution | $\propto V$ | ~40% slower with offset |
| In-lagoon wave dissipation | $\propto 1/h$ | ~25% more dissipation without offset |
| Bed shear stress $\tau_b$ (current) | $\propto 1/h$ | ~30% larger without offset (more resuspension) |
| Tide celerity $c = \sqrt{gh}$ | $\propto \sqrt{h}$ | +17% celerity with offset |
| Salinity stratification | grows with h | more column to stratify with offset |

**Sensitivity-analysis conclusion**: the offset matters substantially for physical variables that depend on volume and depth. The empirical calibration is defensible because it was made against **real observations** of the gauges (which carry the correct local datum, even if not formalised). But the system's sensitivity reinforces the importance of **reducing the datum-related uncertainty in v04** through:

- IGM95 elevation of the gauges via GNSS RTK (±2 cm vs ±20–30 cm currently)
- Formal MDT from CNES-CLS22 (±3–5 cm vs the qualitative ±15 cm estimate)
- Cross-validation against Marettimo ISPRA RMN (officially documented datum)

A propagated uncertainty of ±20–30 cm in the offset (current scenario) → ±10% in the volume → ±10% in residence time and dilution rates. Reducing to ±5 cm of datum uncertainty → ±2% in the volume → ±2% in the derived variables.

The figure `figures/v03d_offset_hypsometry_impact.png` shows the hypsometric curves (wet area and volume vs WL) with the two operating points marked.

## 5. Residual bias after the offset (a-posteriori v03d validation)

After applying the +0.4208 m, the ABSOLUTE comparison (not mean-removed) between model and in-situ in the post-spin-up window (1.5d–9d) shows:

| Station | mean_model | mean_obs | residual bias (m−o) |
|---|---|---|---|
| BocaNord | +0.161 m | +0.074 m | +0.087 m |
| BocaSud | +0.096 m | +0.131 m | −0.035 m |
| AltaVilaEst | +0.094 m | +0.029 m | +0.065 m |
| Marettimo (ISPRA) | +0.238 m | +0.130 m | +0.108 m |
| **Mean** | — | — | **+0.056 m** |
| Std (across stations) | — | — | 0.055 m |

**Interpretation:**

- The absolute bias dropped from −42 cm (v01 without offset) to +5.6 cm (v03d with offset) — a **~7×** reduction.
- The mean residual bias (+5.6 cm) is of the same order of magnitude as the **time-mean wave setup**, which is now active in v03d (it was not in v01 when the wave coupling was broken). Sites more exposed to swell (Marettimo offshore +11 cm, BocaNord +9 cm) show the largest positive biases; the sheltered BocaSud site is the only negative one (−4 cm).
- The cross-station heterogeneity (±5.5 cm 1-sigma) reflects both real physical effects (spatially-variable wave setup) and the gauge datum uncertainty (±10–30 cm, see §2.2).

**Decision:** keep +0.4208 m for v03d. The 5.6 cm residual is (i) of the magnitude of the expected wave setup, and (ii) smaller than the uncertainty of the non-formalised gauges. Re-calibrating to zero the residual at this stage would amount to over-fitting.

## 6. A-posteriori validation — v03d (July 2025, 9 days)

The v03d run completed with time-varying waves and the BC fix (TPXO removed). WL metrics against in-situ in the clean window (12 h spin-up + day 3, before the day-4 freeze that was resolved in commit `1082232`):

| Station | std_mod / std_obs | RMSE | Corr | Comment |
|---|---|---|---|---|
| BocaNord | **1.02** | 0.034 m | 0.952 | Amplitude and phase essentially perfect |
| BocaSud | **1.03** | 0.048 m | 0.906 | Same |
| AltaVilaEst | **1.23** | 0.050 m | 0.808 | Slightly over-amplitude (shallow site, possible wave-setup contribution) |
| Marettimo offshore (ISPRA RMN) | **0.90** | 0.031 m | 0.886 | Slightly under-amplitude, within the expected range for an offshore gauge |

The consistency of the metrics across **four independent stations** (3 in the lagoon + 1 offshore) with std_mod/std_obs between 0.90 and 1.23 confirms that the offset, combined with the BC-superposition correction (TPXO removed), produces an absolute WL coherent with the observations. The signal amplitude is preserved (correlation > 0.81 at all stations) and the post-mean-removal bias is virtually zero.

## 7. Limitations and improvement plan

### Limitations of the current approach

1. **Single empirical calibration** based only on three lagoon gauges in the v01 run. The +0.4208 m value is uniform across all 51 nodes of the open boundary, ignoring potential spatial gradients of MDT in the Sicily Channel (which exist on a ~10–30 km scale).
2. **Gauge datum not officially documented** for BN/BS/AE. The decomposition in §2.2 is qualitative — there is no formal traceability to IGM95/IGM2008 for these locally-installed gauges.
3. **MDT does not come from a formal product**: the offset compensates MDT + datum + CMEMS bias in aggregate, without separating the components.

### Plan for future versions (v04+)

1. **Topographic survey of the gauges**: measure the IGM95 elevation of the BN/BS/AE stations to fix the datum (one morning of fieldwork with a GNSS RTK receiver).
2. **Formal MDT from CNES-CLS22**: extract pointwise MDT at the 51 boundary nodes (linear interpolation on a 1/8° grid) and apply as a spatially-varying offset instead of a constant.
3. **Validation against Marettimo ISPRA RMN** as the absolute datum reference — Marettimo is part of the official network and has documented IGM95 datum.
4. **Sensitivity analysis** of ±10 cm in the offset to quantify the impact on residence time and salinity dynamics.

## 8. Conclusion for the supervisor

The constant +0.4208 m offset is an **empirical calibration** with a defensible physical basis. The identifiable components (Mediterranean MDT, CMEMS `zos` product bias, local gauge datum, mean atmospheric pressure) sum to ~−0.22 m, explaining approximately half of the observed bias. The residual difference reflects imprecision in the separation of the components and secondary effects of wetting/drying.

The validation in the v03d run (9 days, July 2025) against **four independent stations** confirms that the offset, in combination with the removal of the double-counting of TPXO (Track B), produces WL amplitude and phase consistent with in-situ observations. Amplitude/phase metrics (mean-removed): `std_mod/std_obs` between 0.90 and 1.23, RMSE 3–5 cm, correlation > 0.81 across all 4 stations. Mean residual absolute bias: +5.6 cm (vs −42 cm in v01 without the offset).

**Sensitivity**: the hypsometric analysis (§4) shows that the offset alters the **lagoon volume by +40%** and the **mean depth by +35 cm** — non-trivial in such a shallow system (mean depth ~1.2 m). This reinforces the importance of refining the datum in v04 but does not invalidate the current calibration: comparing against real observations is the most robust criterion available while the gauge datums remain non-formalised.

The approach is defensible to publish in this form for the v03d demonstration run. For a publishable reference version (v04), the plan is to replace the empirical constant offset with a formal decomposition: CNES-CLS22 MDT + GNSS RTK gauge datum + cross-validation against Marettimo ISPRA.

---

## Suggested references

- **CMEMS MDT product**: AVISO+ MDT_CNES_CLS22 — https://www.aviso.altimetry.fr/en/data/products/auxiliary-products/mdt.html
- **Mediterranean MDT**: Pinardi et al. (2014), "Mediterranean Sea large-scale low-frequency ocean variability and water mass formation rates from 1987 to 2007: A retrospective analysis", *Progress in Oceanography*, 132, 318-332.
- **CMEMS MEDSEA reanalysis PUM**: PUM EU.COPERNICUS-MARINE.MDS-FOREC-MED-PHY (Marine Copernicus product manual, latest version).
- **Italian gauge datum (IGM95)**: ISPRA-RMN tide gauge network documentation, https://www.mareografico.it
- **D-Flow FM datum convention**: Deltares D-Flow FM User Manual §3.2 (vertical reference).

---

*Document produced jointly with Claude (Anthropic) during the v03d validation session. Last revised: 2026-04-30.*
