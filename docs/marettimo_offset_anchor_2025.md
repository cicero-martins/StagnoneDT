# Marettimo statistical offset anchor — 2025-2026

**Computed:** 2026-05-04 from `data\raw\insitu\marettimo_wl_2025_2026_10min.csv` and `data\raw\cmems\zos_marettimo_anchor\cmems_zos_marettimo_2025-01-01_2026-01-20.nc`.

**Method:**
- CMEMS dataset: `cmems_mod_med_phy-ssh_anfc_4.2km_P1D-m` (MED-MFC analysis-forecast SSH daily mean, NEMO 4.2)
- `zos` linearly interpolated to Marettimo gauge coords (12.0766, 37.9662)
- Marettimo obs from JRC TAD 658, 10-min sampled, daily-averaged
- Window: 2025-01-01 00:00:00 to 2026-01-19 00:00:00 (384 aligned daily samples)

**Anchor:**

| Quantity | Value (m) |
|---|---|
| mean(obs_Marettimo) | +0.0905 |
| mean(zos_CMEMS @ Marettimo) | -0.3584 |
| **delta(Marettimo) = obs - zos** | **+0.4489** |
| Current empirical offset | +0.4208 |
| Difference (anchor - current) | +0.0281 |

**Monthly breakdown:**

| Month | obs (m) | zos (m) | delta (m) |
|---|---|---|---|
| 2025-01 | -0.0108 | -0.3717 | +0.3609 |
| 2025-02 | -0.0411 | -0.4117 | +0.3706 |
| 2025-03 | +0.0947 | -0.3956 | +0.4903 |
| 2025-04 | +0.0741 | -0.4136 | +0.4876 |
| 2025-05 | +0.0510 | -0.3929 | +0.4439 |
| 2025-06 | +0.1047 | -0.3842 | +0.4890 |
| 2025-07 | +0.1345 | -0.3467 | +0.4812 |
| 2025-08 | +0.1190 | -0.3054 | +0.4244 |
| 2025-09 | +0.1229 | -0.3062 | +0.4290 |
| 2025-10 | +0.1094 | -0.3472 | +0.4565 |
| 2025-11 | +0.1448 | -0.3038 | +0.4487 |
| 2025-12 | +0.1209 | -0.3438 | +0.4646 |
| 2026-01 | +0.1747 | -0.3305 | +0.5052 |

## Figures

### Annual overview

![annual](..\figures\marettimo_offset_annual_2025.png)

Daily-mean obs (blue) vs CMEMS zos (orange), δ overlay (green, right axis). δ varies seasonally between ~+0.36 m (Feb) and ~+0.51 m (Jan/26).

### Highlighted months

#### 2025-02 — Annual minimum (winter, obs lowest)

![2025-02](..\figures\marettimo_offset_monthly_2025-02.png)

#### 2025-07 — Reference run window (v03d)

![2025-07](..\figures\marettimo_offset_monthly_2025-07.png)

#### 2025-08 — CMEMS zos summer peak (smallest delta)

![2025-08](..\figures\marettimo_offset_monthly_2025-08.png)

#### 2026-01 — Obs winter peak (largest delta, partial)

![2026-01](..\figures\marettimo_offset_monthly_2026-01.png)

