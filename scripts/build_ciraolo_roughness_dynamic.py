"""
build_ciraolo_roughness_dynamic.py

Generates a velocity-dependent Chezy roughness map for P. oceanica cells
using the flume resistance law of Ciraolo, Ferreri & La Loggia (JHR 2006):

    lambda = 52e6 * Re_v^(-1.56)     Re_v = U * h_v / nu     (Eq. 22)
    C = sqrt(8 * g / lambda)                                   (Darcy-Weisbach)

Outputs
-------
    data/processed/roughness_ciraolo/
        roughness_ciraolo_mean_chezy.xyz  -- static, time-mean Chezy [m^0.5/s]
                                             in WGS84 XYZ sample format.
                                             Use with unifFrictType = 0 in MDU.
        roughness_ciraolo_bias.nc         -- (C_ciraolo - C_baptist) per face
                                             for diagnostic / paper figures.
        roughness_ciraolo_dynamic.nc      -- EXPERIMENTAL: (time, face) Chezy
                                             for FM updateRoughnessInterval test.

Usage
-----
    conda activate dfm_tools_env
    cd C:/Users/Unipa/Documents/StagnoneDT
    python scripts/build_ciraolo_roughness_dynamic.py

MDU patch for experimental run  (see STEP 4 below):
    unifFrictType  = 0             # switch to Chezy
    unifFrictCoef  = 40.0          # background (non-vegetated)
    FrictionCoeffFile = roughness_ciraolo_mean_chezy.xyz
    updateRoughnessInterval = 3600 # for dynamic netCDF variant
    trtRou = N                     # disable Baptist trachytopes

References
----------
    Ciraolo G., Ferreri G.B. & La Loggia G. (2006). Flow resistance of
    Posidonia oceanica in shallow water. Journal of Hydraulic Research,
    44(2), 189-202.
"""

from __future__ import annotations
import numpy as np
import xarray as xr
import dfm_tools as dfmt
from pathlib import Path

# ── configuration ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent

# Source: use v04AE_vr if DFM_OUTPUT exists, else fall back to v04AE
VR_OUT = ROOT / "model/dflowfm_v04AE_vr/DFM_OUTPUT_Stagnone_dxy01_15m"
AE_OUT = ROOT / "model/dflowfm_v04AE/DFM_OUTPUT_Stagnone_dxy01_15m"
MAP_DIR = VR_OUT if VR_OUT.exists() else AE_OUT
MAP_PAT = str(MAP_DIR / "*_map.nc")

OUT_DIR = ROOT / "data/processed/roughness_ciraolo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── physical constants (Ciraolo 2006, Eq. 22) ────────────────────────────────
G    = 9.81       # m/s^2
NU   = 1.14e-6    # kinematic viscosity seawater at ~25 degC (m^2/s)
H_V  = 1.0        # P. oceanica leaf length in nature [m]
              # Ciraolo lab: 0.49 m; field: 1.0-1.5 m. Conservative choice: 1.0 m.
U_FLOOR = 0.005   # minimum velocity to prevent Re_v -> 0 [m/s]
C_BG    = 40.0    # background Chezy for non-vegetated cells [m^0.5/s]
              # corresponds to Manning n=0.023 at h~1 m
C_VEG_THRESH = C_BG - 3.0   # cells with time-mean Chezy below this are vegetated


def ciraolo_chezy(U_mag, h_v=H_V, nu=NU, g=G, u_floor=U_FLOOR):
    """Ciraolo et al. (2006) Eq. 22 -> Chezy [m^0.5/s].

    lambda = 52e6 * Re_v^(-1.56),  Re_v = U * h_v / nu
    C      = sqrt(8 * g / lambda)

    Clips output to [5, 70] m^0.5/s to avoid unphysical extremes.
    """
    U_eff = np.maximum(U_mag, u_floor)
    Re_v  = U_eff * h_v / nu
    lam   = 52e6 * Re_v ** (-1.56)
    C     = np.sqrt(8.0 * g / lam)
    return np.clip(C, 5.0, 70.0)


# ── STEP 1: load map.nc ──────────────────────────────────────────────────────
print(f"Opening map.nc from: {MAP_DIR}")
ds = dfmt.open_partitioned_dataset(MAP_PAT)
print(f"  time steps: {ds.dims.get('time', '?')}  "
      f"faces: {ds.dims.get('mesh2d_nFaces', '?')}")

# ── STEP 2: depth-averaged velocity magnitude ─────────────────────────────────
# FM 3D sigma: ucx/ucy are per-layer (nLayers dim). Use depth mean if present,
# else average over layers; surface layer (-1) is a fallback.
if "mesh2d_nLayers" in ds["mesh2d_ucx"].dims:
    # sigma layers: weight by layer thickness approximation (uniform here)
    U_layers = np.sqrt(ds["mesh2d_ucx"]**2 + ds["mesh2d_ucy"]**2)
    U_mag = U_layers.mean("mesh2d_nLayers")   # depth-average
else:
    U_mag = np.sqrt(ds["mesh2d_ucx"]**2 + ds["mesh2d_ucy"]**2)
print(f"  U_mag shape: {U_mag.shape}")

# ── STEP 3: vegetated face mask from Baptist Chezy output ────────────────────
if "mesh2d_chezy" in ds:
    C_baptist = ds["mesh2d_chezy"]
    if "mesh2d_nLayers" in C_baptist.dims:
        C_baptist = C_baptist.isel(mesh2d_nLayers=-1)
    C_bap_mean = C_baptist.mean("time")
    veg_mask = C_bap_mean < C_VEG_THRESH
    n_veg = int(veg_mask.sum())
    pct   = 100.0 * n_veg / len(veg_mask)
    print(f"  Vegetated faces: {n_veg:,} ({pct:.1f}%)")
else:
    print("  WARNING: mesh2d_chezy not found in map.nc.")
    print("  Enable wrimap_chezy=1 in MDU, or rerun v04AE_vr first.")
    print("  Proceeding with all faces as vegetated (conservative).")
    C_baptist = None
    C_bap_mean = None
    veg_mask = xr.ones_like(U_mag.isel(time=0), dtype=bool)

# ── STEP 4a: static time-mean Chezy XYZ (guaranteed to work with FM) ─────────
U_mean    = U_mag.mean("time")
C_ciraolo = ciraolo_chezy(U_mean)

# blend: Ciraolo for vegetated, background for non-vegetated
C_static = xr.where(veg_mask, C_ciraolo, C_BG)

# retrieve face centroids from mesh
face_x = ds["mesh2d_face_x"].values   # WGS84 lon
face_y = ds["mesh2d_face_y"].values   # WGS84 lat
C_vals = C_static.values

# write WGS84 XYZ (same format as roughness_satellite.xyz)
xyz_path = OUT_DIR / "roughness_ciraolo_mean_chezy.xyz"
with open(xyz_path, "w") as f:
    for x, y, c in zip(face_x, face_y, C_vals):
        f.write(f"{x:.6f} {y:.6f} {c:.4f}\n")
print(f"Written (static): {xyz_path}  ({len(C_vals):,} points)")
print(f"  C range vegetated: {float(C_ciraolo.where(veg_mask).min()):.1f} - "
      f"{float(C_ciraolo.where(veg_mask).max()):.1f} m^0.5/s")
if C_bap_mean is not None:
    dC = C_static - C_bap_mean
    print(f"  dC (Ciraolo - Baptist) mean: {float(dC.mean()):.2f}  "
          f"  std: {float(dC.std()):.2f} m^0.5/s")

# ── STEP 4b: diagnostic bias netCDF ──────────────────────────────────────────
if C_bap_mean is not None:
    ds_bias = xr.Dataset({
        "C_ciraolo_mean": C_static,
        "C_baptist_mean": C_bap_mean,
        "dC_mean"       : C_static - C_bap_mean,
        "dC_pct"        : (C_static - C_bap_mean) / C_bap_mean * 100.0,
        "U_mean"        : U_mean,
        "veg_mask"      : veg_mask.astype(np.int8),
    })
    for v in ds_bias.data_vars.values():
        v.attrs["coordinates"] = "mesh2d_face_x mesh2d_face_y"
    ds_bias["mesh2d_face_x"] = xr.DataArray(face_x, dims="mesh2d_nFaces")
    ds_bias["mesh2d_face_y"] = xr.DataArray(face_y, dims="mesh2d_nFaces")
    bias_path = OUT_DIR / "roughness_ciraolo_bias.nc"
    ds_bias.to_netcdf(bias_path)
    print(f"Written (bias):   {bias_path}")

# ── STEP 4c: EXPERIMENTAL time-varying Chezy netCDF ──────────────────────────
# Compute hourly-resampled Chezy for FM updateRoughnessInterval = 3600 s.
# This output needs to be tested: FM 2026.01 may or may not accept a time-
# varying roughness netCDF via FrictionCoeffFile. Run the feasibility test
# described in docs/ciraolo_roughness_implementation.md before the full run.
UPDATE_S = 3600   # match updateRoughnessInterval in experimental MDU

# infer map time step in seconds
dt_ns = float(U_mag.time.diff("time").median())
dt_s  = dt_ns / 1e9
n_per = max(1, int(round(UPDATE_S / dt_s)))
print(f"\n  map dt={dt_s:.0f}s -> coarsen by {n_per} for {UPDATE_S}s updates")

C_ciraolo_full = xr.where(veg_mask, ciraolo_chezy(U_mag), C_BG)
C_hourly = C_ciraolo_full.coarsen(time=n_per, boundary="trim").mean()

ds_dyn = xr.Dataset({"frictioncoefficient": C_hourly})
ds_dyn["frictioncoefficient"].attrs.update({
    "units"         : "m0.5 s-1",
    "long_name"     : "Chezy roughness (Ciraolo et al. 2006, velocity-dependent)",
    "coordinates"   : "mesh2d_face_x mesh2d_face_y",
})
ds_dyn["mesh2d_face_x"] = xr.DataArray(face_x, dims="mesh2d_nFaces",
                                        attrs={"units": "degrees_east"})
ds_dyn["mesh2d_face_y"] = xr.DataArray(face_y, dims="mesh2d_nFaces",
                                        attrs={"units": "degrees_north"})
dyn_path = OUT_DIR / "roughness_ciraolo_dynamic.nc"
ds_dyn.to_netcdf(dyn_path)
print(f"Written (dynamic): {dyn_path}  ({len(C_hourly.time)} time steps)")

# ── STEP 5: print MDU patch ───────────────────────────────────────────────────
print("""
=== MDU patch for experimental run v04AE_ciraolo ===

In Stagnone_dxy01_15m.mdu, under [Physics]:

  unifFrictType      = 0       # Chezy (was: 1=Manning)
  unifFrictCoef      = 40.0    # background non-vegetated [m^0.5/s]
  FrictionCoeffFile  = roughness_ciraolo_mean_chezy.xyz   # static variant

Under [Trachytopes]:
  trtRou = N                   # disable Baptist (roughness from file instead)

For the DYNAMIC variant (test first!):
  FrictionCoeffFile  = ../../data/processed/roughness_ciraolo/roughness_ciraolo_dynamic.nc
  updateRoughnessInterval = 3600

Feasibility test: run 24h, check that mesh2d_chezy in map.nc shows
temporal variation matching roughness_ciraolo_dynamic.nc. If it stays
constant, FM 2026.01 does not support time-varying roughness via
FrictionCoeffFile and the static XYZ is the correct path.
""")

print("Done.")
