# Observation on the modelbuilder boundary-condition workflow

**Suggested subject:** D-Flow FM modelbuilder example — could the waterlevel BC section flag the constant + tide + CMEMS combination as user-choice?

**From:** Cicero Martins Jr / Università degli Studi di Palermo (cicero.martinsjr@unipa.it)

---

While reproducing the public modelbuilder example notebook (`modelbuilder_example.ipynb`, Section 4 — Generate boundary conditions) for the Stagnone di Marsala / western Sicily case, I noticed that three different convenience functions of `dfm_tools` each append a `[Boundary] quantity = waterlevelbnd` block, in turn, to the same `ExtModel` and the same `file_pli`:

| Cell | Function | Result in `ext_new` |
|---|---|---|
| §4.2 | `dfmt.constant_to_bc(ext_new, file_pli=poly_file, constant=0.00)` | `[Boundary]` waterlevelbnd, `function = constant` |
| §4.3 | `dfmt.interpolate_tide_to_bc(ext_new, tidemodel='tpxo80_opendap', file_pli=poly_file)` | `[Boundary]` waterlevelbnd, `function = astronomic` (TPXO components) |
| §4.4 | `dfmt.cmems_nc_to_bc(ext_new, list_quantities=['waterlevelbnd', ...], file_pli=poly_file)` | `[Boundary]` waterlevelbnd, `function = timeSeries` (CMEMS reanalysis) |

D-Flow FM combines multiple `[Boundary]` blocks of the same quantity on the same `locationFile` additively. For a Mediterranean configuration this produces a measurable double-counting of the tide, because the CMEMS `MEDSEA_*PHY*` `zos` (sea surface height) field already contains the tidal forcing applied by the Mediterranean Forecast System. Empirically, in our nine-day July 2025 run the boundary node next to `bnd1_0022` showed peak-to-peak water level of ~0.5 m, while the prescribed CMEMS time series at that node has ~0.24 m. The TPXO astronomical contribution (~0.26 m peak-to-peak, dominated by M2) and the CMEMS tidal component are largely in phase, so they sum coherently and approximately double the amplitude. This pattern propagates inward and shows up downstream as a roughly 1.8× over-amplification of the tidal range relative to in-situ tide gauges, including offshore at the ISPRA Marettimo station.

The notebook follows the user-friendly Deltares pattern of presenting all common boundary forcings side by side, which makes the example useful as a menu of options. We initially adopted all three blocks unchanged (preserving them across our v01–v03c iterations), assuming the example illustrated a self-consistent setup. Once we identified the superposition we removed the TPXO block in v03d and the boundary amplitude returned to the expected range.

A small addition to the modelbuilder notebook could prevent this in future user models. A few non-invasive options:

1. **An inline note** in §4 stating that the three functions are alternative or complementary entry points and that the user should choose either:
    - **(A)** `cmems_nc_to_bc(...)` alone for `waterlevelbnd` (CMEMS reanalysis already contains tide and surge for Mediterranean and similar regions), with `constant_to_bc` for an optional datum offset; or
    - **(B)** `interpolate_tide_to_bc(...)` for the astronomical tide plus a CMEMS *anomaly* (CMEMS minus its tidal component) for the non-tidal residual.
2. **A docstring warning** in `cmems_nc_to_bc(..., list_quantities=['waterlevelbnd', ...])` noting that several CMEMS regional products include tidal forcing, and that combining the function's output with `interpolate_tide_to_bc` will double-count tide unless the CMEMS series is preprocessed to remove its tidal part.
3. **A defensive check inside `cmems_nc_to_bc`** that emits a warning when an `ExtModel` already contains a `waterlevelbnd` block referencing the same `locationFile` — the user can still proceed but is alerted to the choice.

Either of the first two has a minor cost (a comment block) and would help users in the regional-model case where the CMEMS reanalysis is the only practical source of mean sea level + storm surge but happens to ship the tide along with it. We could of course also contribute a pull request with such a comment; the documentation itself is the higher-leverage place since it is the first thing a new user reads.

This is independent from but tangentially related to the HDF5 coupling issue reported separately. Both observations come from the same v03 family of runs.

Thank you for your time.

---

## Local artefacts

- Affected configuration: `model/dflowfm_v03c/Stagnone_dxy01_15m_new.ext` lines 7–20 (the three `[Boundary]` waterlevelbnd blocks).
- Fix applied in v03d: TPXO block removed; CMEMS + constant offset retained. See `model/dflowfm_v03d/Stagnone_dxy01_15m_new.ext` and the commit log of this repository.
- Empirical evidence: time series at point 11132 (~0.5 m amplitude) vs CMEMS prescribed series (~0.24 m) and TPXO components (M2 = 0.072 m, S2 = 0.019 m, K1 = 0.030 m, …) plus the Marettimo offshore validation in `notebooks/23_valid_v03c_offshore.ipynb`.
- Original Deltares notebook examined: `reference/modelbuilder_example.ipynb` (cells 19, 21, 23, 25).
