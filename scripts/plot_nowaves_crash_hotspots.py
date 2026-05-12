"""
Localize where in the mesh the v04AE_nowaves variant explodes.

The crash trigger is in the LAGOON intertidal zone (not offshore — offshore is calm
even at the crash sim-time). To find candidate problem cells we map two things at
the crash moment 2025-07-01T11:30Z using the COUPLED v04AE output that did stay
stable through that instant:

  - ucmag in the LAGOON area (zoomed), where the wave-drag suppresses what would
    otherwise be a runaway intertidal cell;
  - bedlevel + mesh geometry (cell area, neighbor depth gradient) in the same
    zoom, to spot fragile intertidal slivers.

Output: figs/nowaves_crash_hotspots.png with:
  - panel 1: full domain ucmag (context)
  - panel 2: lagoon zoom, ucmag colored, intertidal cells circled
  - panel 3: lagoon zoom, bedlevel colored; cells with bedlevel in [-0.3, +0.3]
             outlined (intertidal candidates for instability)
  - panel 4: lagoon zoom, log10(cell area) — small/sliver cells are red flags
"""
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

MODEL_DIR = Path(r"C:/Users/Unipa/Documents/StagnoneDT/model/dflowfm_v04AE/DFM_OUTPUT_Stagnone_dxy01_15m")
OUT_DIR = Path(r"C:/Users/Unipa/Documents/StagnoneDT/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CRASH_TIME = np.datetime64("2025-07-01T11:30:00")

# Lagoon bbox (Stagnone di Marsala — narrow strip on west coast)
LAG_X = (12.42, 12.47)
LAG_Y = (37.81, 37.91)

INTERTIDAL_LO = -0.3   # m
INTERTIDAL_HI = +0.3   # m


def load_at_crash():
    """Load and concat surface-layer ucmag, cell coords, bedlevel, area across 8 parts."""
    xs, ys, ucs, bls, areas = [], [], [], [], []
    snap_t = None
    for p in range(8):
        ds = xr.open_dataset(MODEL_DIR / f"Stagnone_dxy01_15m_{p:04d}_map.nc")
        idx = int(np.argmin(np.abs(ds.time.values - CRASH_TIME)))
        snap_t = ds.time.values[idx]
        snap = ds.isel(time=idx)
        ucx = snap["mesh2d_ucx"]
        ucy = snap["mesh2d_ucy"]
        if "mesh2d_nLayers" in ucx.dims:
            ucx = ucx.isel(mesh2d_nLayers=-1)
            ucy = ucy.isel(mesh2d_nLayers=-1)
        ucmag = np.sqrt(ucx.values ** 2 + ucy.values ** 2)
        xs.append(snap["mesh2d_face_x"].values)
        ys.append(snap["mesh2d_face_y"].values)
        ucs.append(ucmag)
        bls.append(snap["mesh2d_flowelem_bl"].values)
        areas.append(snap["mesh2d_flowelem_ba"].values if "mesh2d_flowelem_ba" in snap.variables
                     else np.full_like(ucmag, np.nan))
    return (np.concatenate(xs), np.concatenate(ys),
            np.concatenate(ucs), np.concatenate(bls),
            np.concatenate(areas), snap_t)


def main():
    x, y, uc, bl, area, t_snap = load_at_crash()
    print(f"Snapshot:  {t_snap}")
    print(f"Cells:     {len(x)} total; lagoon zoom bbox {LAG_X}, {LAG_Y}")

    # masks
    in_lag = (x >= LAG_X[0]) & (x <= LAG_X[1]) & (y >= LAG_Y[0]) & (y <= LAG_Y[1])
    intertidal = (bl > INTERTIDAL_LO) & (bl < INTERTIDAL_HI)
    lag_intertidal = in_lag & intertidal

    print(f"In lagoon zoom:       {in_lag.sum()}")
    print(f"Intertidal (any):     {intertidal.sum()}")
    print(f"Intertidal in lagoon: {lag_intertidal.sum()}")
    print(f"Lagoon ucmag max:     {uc[in_lag].max():.3f} m/s")

    # Top-N ucmag cells INSIDE the lagoon zoom
    i_lag = np.where(in_lag)[0]
    order = i_lag[np.argsort(uc[i_lag])[::-1]]
    n_top = 15
    i_topN = order[:n_top]

    print(f"\nTop-{n_top} hotspots inside the lagoon zoom:")
    for k, i in enumerate(i_topN):
        print(f"  #{k+1:2d}  x={x[i]:9.5f}  y={y[i]:8.5f}  ucmag={uc[i]:6.3f}  bl={bl[i]:7.3f}  area={area[i]:.1f}")

    fig, axes = plt.subplots(2, 2, figsize=(15, 14))

    # ---- 1: full-domain ucmag for context
    ax = axes[0, 0]
    sc = ax.scatter(x, y, c=uc, s=3, cmap="magma", vmin=0, vmax=2.5)
    # show the lagoon zoom bbox
    ax.plot([LAG_X[0], LAG_X[1], LAG_X[1], LAG_X[0], LAG_X[0]],
            [LAG_Y[0], LAG_Y[0], LAG_Y[1], LAG_Y[1], LAG_Y[0]],
            color="cyan", lw=1.2, label="lagoon zoom")
    ax.set_title(f"v04AE COUPLED ucmag (surface) @ {str(t_snap)[:16]}\n"
                 f"(moment the nowaves variant crashes)")
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.legend(loc="upper right", fontsize=9)
    plt.colorbar(sc, ax=ax, label="ucmag [m/s]")
    ax.set_aspect("equal", adjustable="box")

    # ---- 2: lagoon zoom — ucmag, intertidal cells circled
    ax = axes[0, 1]
    sc = ax.scatter(x[in_lag], y[in_lag], c=uc[in_lag], s=14, cmap="magma",
                    vmin=0, vmax=max(uc[in_lag].max(), 0.5))
    ax.scatter(x[lag_intertidal], y[lag_intertidal], facecolors="none",
               edgecolors="cyan", s=22, linewidths=0.7,
               label=f"intertidal (bl∈[{INTERTIDAL_LO},{INTERTIDAL_HI}])"
                     f"\nn={lag_intertidal.sum()}")
    ax.scatter(x[i_topN], y[i_topN], marker="x", color="red", s=70,
               linewidths=1.5, label=f"top {n_top} ucmag in lagoon")
    ax.set_title("Lagoon zoom — ucmag in coupled (where wave drag damps it)")
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.legend(loc="upper right", fontsize=8)
    plt.colorbar(sc, ax=ax, label="ucmag [m/s]")
    ax.set_aspect("equal", adjustable="box")

    # ---- 3: lagoon zoom — bedlevel
    ax = axes[1, 0]
    sc = ax.scatter(x[in_lag], y[in_lag], c=bl[in_lag], s=14, cmap="terrain_r",
                    vmin=-3, vmax=1.5)
    ax.scatter(x[lag_intertidal], y[lag_intertidal], facecolors="none",
               edgecolors="red", s=22, linewidths=0.5,
               label="intertidal candidates")
    ax.set_title("Lagoon zoom — bedlevel\n(intertidal in red — instability suspects)")
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.legend(loc="upper right", fontsize=8)
    plt.colorbar(sc, ax=ax, label="bedlevel [m]")
    ax.set_aspect("equal", adjustable="box")

    # ---- 4: lagoon zoom — log10 cell area
    ax = axes[1, 1]
    larea = np.log10(np.where(area > 0, area, np.nan))
    sc = ax.scatter(x[in_lag], y[in_lag], c=larea[in_lag], s=14, cmap="viridis")
    # highlight any cells SMALLER than median * 0.3 (potential slivers)
    if np.isfinite(area[in_lag]).any():
        med = np.nanmedian(area[in_lag])
        sliver = in_lag & (area > 0) & (area < med * 0.3)
        if sliver.any():
            ax.scatter(x[sliver], y[sliver], facecolors="none",
                       edgecolors="red", s=40, linewidths=1.2,
                       label=f"area < 0.3×median, n={sliver.sum()}")
    ax.set_title("Lagoon zoom — log10(cell area)\n(small cells = numerical fragility)")
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.legend(loc="upper right", fontsize=8)
    plt.colorbar(sc, ax=ax, label="log10(area) [m²]")
    ax.set_aspect("equal", adjustable="box")

    plt.tight_layout()
    out_png = OUT_DIR / "diag_v04AE_nowaves_crash_hotspots.png"
    plt.savefig(out_png, dpi=140, bbox_inches="tight")
    print(f"\nSaved {out_png}")


if __name__ == "__main__":
    main()
