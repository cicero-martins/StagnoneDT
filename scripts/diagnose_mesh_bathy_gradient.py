"""
Diagnostic A: quantify cell-to-cell bedlevel gradients across the mesh.

Hypothesis: the v04AE_nowaves crash at the south lagoon inlet is caused by
sharp |dbl| > 3 m discontinuities between adjacent cells, an artifact of
the mean-of-nodes interpolation in [make_bathy_xyz_v04.py]. We use
mesh2d_edge_faces (UGRID-2D edge-to-face connectivity, already present in
the net file) to get every neighbor pair, compute |dbl|, and locate the
worst clusters.

Output: figs/mesh_bathy_gradient_diag.png with
  - panel 1: histogram of |dbl| across all interior edges
  - panel 2: full domain — edges colored by |dbl| (highlight > 3 m)
  - panel 3: lagoon zoom — same
  - panel 4: south inlet zoom — same
"""
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

NET = Path(r"C:/Users/Unipa/Documents/StagnoneDT/model/dflowfm_v04AE_nowaves/Stagnone_dxy01_15m_net.nc")
OUT_DIR = Path(r"C:/Users/Unipa/Documents/StagnoneDT/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LAG_X = (12.42, 12.47)
LAG_Y = (37.81, 37.91)
SOUTH_X = (12.42, 12.44)
SOUTH_Y = (37.80, 37.83)

THRESH = 3.0  # m, |dbl| considered problematic


def main():
    ds = xr.open_dataset(NET)
    face_x = ds["mesh2d_face_x"].values
    face_y = ds["mesh2d_face_y"].values
    face_z = ds["mesh2d_face_z"].values         # already stored in net.nc
    edge_x = ds["mesh2d_edge_x"].values
    edge_y = ds["mesh2d_edge_y"].values
    edge_nodes = ds["mesh2d_edge_nodes"].values
    edge_faces = ds["mesh2d_edge_faces"].values  # (n_edges, 2)
    node_x = ds["mesh2d_node_x"].values
    node_y = ds["mesh2d_node_y"].values
    print(f"Mesh: {len(face_x)} faces, {len(edge_x)} edges, {len(node_x)} nodes")
    print(f"face_z range:  [{np.nanmin(face_z):+.2f}, {np.nanmax(face_z):+.2f}]")

    # interior edges have 2 valid faces; boundary edges have one face = fill
    fa = edge_faces.astype(np.int64) - 1  # convert 1-based to 0-based (UGRID convention)
    interior = (fa[:, 0] >= 0) & (fa[:, 1] >= 0) & \
               (fa[:, 0] < len(face_z)) & (fa[:, 1] < len(face_z))
    fi = fa[interior]
    e_x = edge_x[interior]
    e_y = edge_y[interior]
    e_nodes = edge_nodes[interior]

    dbl = np.abs(face_z[fi[:, 0]] - face_z[fi[:, 1]])
    print(f"\nInterior edges: {interior.sum()} ({interior.sum() / len(interior):.1%})")
    print(f"|dbl| stats:  mean={dbl.mean():.3f}  median={np.median(dbl):.3f}  "
          f"95th={np.percentile(dbl, 95):.3f}  max={dbl.max():.3f}")

    for t in [1, 2, 3, 5, 10, 20]:
        n = int((dbl > t).sum())
        print(f"  |dbl| > {t:2d} m :  {n:6d} edges ({n / len(dbl):.2%})")

    # Mark "problematic" edges
    bad = dbl > THRESH
    print(f"\nEdges with |dbl| > {THRESH} m: {int(bad.sum())}")

    # spatial bins for the worst edges
    bad_x = e_x[bad]; bad_y = e_y[bad]
    in_lag = (bad_x > LAG_X[0]) & (bad_x < LAG_X[1]) & \
             (bad_y > LAG_Y[0]) & (bad_y < LAG_Y[1])
    in_south = (bad_x > SOUTH_X[0]) & (bad_x < SOUTH_X[1]) & \
               (bad_y > SOUTH_Y[0]) & (bad_y < SOUTH_Y[1])
    print(f"  ...inside lagoon zoom:      {int(in_lag.sum())}")
    print(f"  ...inside south inlet zoom: {int(in_south.sum())}")

    # build LineCollection segments from edge_nodes for plotting
    en = e_nodes.astype(np.int64) - 1
    en = np.clip(en, 0, len(node_x) - 1)
    seg_x = np.stack([node_x[en[:, 0]], node_x[en[:, 1]]], axis=1)
    seg_y = np.stack([node_y[en[:, 0]], node_y[en[:, 1]]], axis=1)
    segs = np.stack([seg_x, seg_y], axis=2)  # (n_edges, 2 pts, 2 coords)

    # ---- figure
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 13.5))

    # 1: histogram
    ax = axes[0, 0]
    ax.hist(dbl, bins=np.linspace(0, 30, 121), color="steelblue", log=True)
    ax.axvline(THRESH, color="red", ls="--", label=f"threshold {THRESH} m")
    ax.set_xlabel("|dbl| between adjacent cells [m]")
    ax.set_ylabel("count (log)")
    ax.set_title(f"Cell-to-cell |dbl| histogram\n"
                 f"{int(bad.sum())} edges > {THRESH} m  "
                 f"({int(bad.sum()) / len(dbl):.2%})")
    ax.legend()

    # generic plot helper. Use a LOCAL threshold per panel so the lagoon
    # zoom shows the structure even though absolute |dbl| is small there.
    def plot_edges(ax, xlim=None, ylim=None, title="", local_thresh=None):
        mask = np.ones(len(dbl), dtype=bool)
        if xlim is not None:
            mask = mask & (e_x > xlim[0]) & (e_x < xlim[1])
        if ylim is not None:
            mask = mask & (e_y > ylim[0]) & (e_y < ylim[1])
        sub = segs[mask]
        sub_dbl = dbl[mask]
        t = local_thresh if local_thresh is not None else THRESH
        # normal edges in light grey
        lc1 = LineCollection(sub[sub_dbl <= t], colors="lightgrey",
                             linewidths=0.4)
        ax.add_collection(lc1)
        if (sub_dbl > t).any():
            vmax = float(np.percentile(sub_dbl[sub_dbl > t], 95))
            lc2 = LineCollection(sub[sub_dbl > t], cmap="magma_r",
                                 norm=plt.Normalize(t, max(vmax, t * 2)),
                                 linewidths=1.5)
            lc2.set_array(sub_dbl[sub_dbl > t])
            ax.add_collection(lc2)
            plt.colorbar(lc2, ax=ax, label=f"|dbl| (> {t} m) [m]")
        # set limits explicitly so LineCollection doesn't fail autoscale
        if xlim is not None:
            ax.set_xlim(*xlim)
        else:
            ax.set_xlim(node_x.min(), node_x.max())
        if ylim is not None:
            ax.set_ylim(*ylim)
        else:
            ax.set_ylim(node_y.min(), node_y.max())
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title)
        ax.set_xlabel("lon"); ax.set_ylabel("lat")
        return int((sub_dbl > t).sum())

    n_full = plot_edges(axes[0, 1],
                        title=f"Full domain  (threshold {THRESH} m)")
    axes[0, 1].set_title(f"Full domain  ({n_full} edges > {THRESH} m)")

    # for the lagoon and south inlet, use a tighter threshold (1 m) so
    # we can still see whatever structure exists there
    LOCAL_THR = 1.0
    n_lag = plot_edges(axes[1, 0], xlim=LAG_X, ylim=LAG_Y,
                       title=f"Lagoon zoom  (lower threshold {LOCAL_THR} m)",
                       local_thresh=LOCAL_THR)
    axes[1, 0].set_title(f"Lagoon zoom  ({n_lag} edges > {LOCAL_THR} m)")

    n_south = plot_edges(axes[1, 1], xlim=SOUTH_X, ylim=SOUTH_Y,
                         title=f"South inlet zoom  (threshold {LOCAL_THR} m)",
                         local_thresh=LOCAL_THR)
    axes[1, 1].set_title(f"South inlet zoom  ({n_south} edges > {LOCAL_THR} m)")

    plt.tight_layout()
    out = OUT_DIR / "diag_v04AE_nowaves_mesh_gradient.png"
    plt.savefig(out, dpi=140, bbox_inches="tight")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
