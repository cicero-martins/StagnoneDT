"""Figures of the renewal of the lagoon, after figure_harbour_renewal.py of MaltaDT.

    renewal_case.png       domain of the model with its open boundary, the mesh
                           of the lagoon divided into the three basins, and the
                           stem density of the canopy
    renewal_readings.gif   lagoon water by the online tracer, the water of each
                           basin by D-WAQ and the particles by basin of release,
                           every two hours, with the remaining fraction
    renewal_particles.gif  the particles under the three vertical diffusivities
    renewal_setup.png      depth of the box with the three basins, and the net
                           inflow at the northern mouth in four members
    renewal_remaining.png  wind over the lagoon, and the remaining fraction of the
                           lagoon and of each basin by the three readings
    renewal_maps.png       lagoon water in the column by the online tracer and by
                           D-WAQ, and the particles by basin of release
    renewal_local_residence.png  share of the window that the particles of each
                           seeded column spend in their basin of release

Reads outputs/renewal/<tag>/ as written by renewal_tracer_member.py,
renewal_waq_member.py, renewal_lagoon_opendrift.py and
diagnose_lagoon_throughflow.py.

The case figure and the animations also read frames.npz of
extract_renewal_frames.py, the merged mesh of waqmerge and the stem density and
open boundary of the case, copied into the same directory.

Usage:
    python figure_lagoon_renewal.py [--tag veg_ic3d_0701_0710] [--no-gif]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.dates as mdates
from matplotlib.collections import PolyCollection
from matplotlib.colors import ListedColormap, to_rgb

from plot_drifter_trajectories_paper1 import parse_ldb, split_long_segments
from renewal_common import BASIN_LAT, BASINS

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
WIND = ROOT / "model" / "dflowfm_v04AE_nowaves"
# the D-WAQ run of the flux-corrected scheme 24, less diffusive than the upwind scheme 15
WAQ = "waq_s24"
COLOR = {"southern": "#2a78d6", "central": "#eb6834", "northern": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"
LAND = "#ece9e0"
BOX = (12.38, 12.50, 37.79, 37.93)                    # box of the currents of the particles
KZ_LABEL = {"1e-04": "Kz 10$^{-4}$ m$^2$/s", "model": "Kz of the model",
            "1e-02": "Kz 10$^{-2}$ m$^2$/s"}
ASPECT = 1 / np.cos(np.radians(37.86))
MEMBERS = {"v04AE_nodm": "waves, bare bed", "dflowfm_v04AE_nowaves_ic3d": "no waves, bare bed",
           "_veg_hv040_3d_ic3d": "no waves, canopy (segment from 7 July)",
           "veg_ic3d_0701_0710": "no waves, canopy (renewal case)"}

plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.5, "axes.spines.top": False,
                     "axes.spines.right": False, "legend.frameon": False})


def wind(times: pd.DatetimeIndex) -> pd.DataFrame:
    u = xr.open_dataset(WIND / "wind_blendedAE_u10n_20250701to20250710.nc").u10n
    v = xr.open_dataset(WIND / "wind_blendedAE_v10n_20250701to20250710.nc").v10n
    p = dict(latitude=37.86, longitude=12.46, method="nearest")
    w = pd.DataFrame({"u": u.sel(**p).to_series(), "v": v.sel(**p).to_series()})
    return w[(w.index >= times[0]) & (w.index <= times[-1])]


def map_axes(ax):
    ax.set_xlim(12.40, 12.50); ax.set_ylim(37.80, 37.925)
    ax.set_aspect(ASPECT); ax.grid(False)
    ax.tick_params(labelsize=7)


def setup(d: Path, out: Path):
    c = xr.open_dataset(d / "currents_3d.nc")
    L, A = np.meshgrid(c.lon.values, c.lat.values)
    H = np.where(c.land_binary_mask.values == 0, c.sea_floor_depth_below_sea_level.values, np.nan)
    b = c.basin.values
    fig, ax = plt.subplots(1, 2, figsize=(10, 5.2), gridspec_kw={"width_ratios": [1, 1.5]})
    m = ax[0].pcolormesh(L, A, H, cmap="Blues", vmin=0, vmax=4, shading="nearest")
    for k, name in BASINS.items():
        ax[0].contour(L, A, (b == k).astype(float), levels=[0.5], colors=COLOR[name], linewidths=1.6)
        y, x = np.argwhere(b == k).mean(0)
        ax[0].text(c.lon.values[int(x)] + 0.004, c.lat.values[int(y)], name, color=INK, fontsize=7)
    fig.colorbar(m, ax=ax[0], shrink=0.7, label="bed depth below datum (m)")
    map_axes(ax[0]); ax[0].set_title("(a) basins of the lagoon", loc="left")
    ax[0].annotate("northern mouth", (12.446, 37.898), (12.405, 37.915), fontsize=7, color=MUTED,
                   arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    ax[0].annotate("southern mouth", (12.440, 37.828), (12.402, 37.815), fontsize=7, color=MUTED,
                   arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    # categorical slots not taken by the basins; the two canopy runs share a hue
    shades = ["#e34948", "#6250d6", "#eda100", "#eda100"]
    for (tag, label), col, ls in zip(MEMBERS.items(), shades, ["-", "-", ":", "-"]):
        f = ROOT / "outputs" / "renewal" / tag / "throughflow.csv"
        if not f.exists():
            continue
        q = pd.read_csv(f, index_col=0, parse_dates=True)["sea->N"].resample("6h").mean()
        ax[1].plot(q.index, q.values, color=col, lw=2, ls=ls, label=label)
    ax[1].axhline(0, color=MUTED, lw=0.6)
    ax[1].set_ylabel("net inflow at the northern mouth (m$^3$/s), 6-h mean")
    ax[1].set_title("(b) throughflow from the northern mouth", loc="left")
    ax[1].legend(loc="upper left", fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout(); fig.savefig(out / "renewal_setup.png", dpi=150); plt.close(fig)


def remaining(d: Path, out: Path):
    fm = pd.read_csv(d / "tracer_remaining.csv", index_col=0, parse_dates=True)
    waq = pd.read_csv(d / f"{WAQ}_remaining.csv", index_col=0, parse_dates=True)
    od = {k: pd.read_csv(d / f"remaining_kz{k}.csv", index_col=0, parse_dates=True)
          for k in ("model", "1e-04", "1e-02")}
    w = wind(fm.index)
    fig, ax = plt.subplots(5, 1, figsize=(8, 10), sharex=True,
                           gridspec_kw={"height_ratios": [0.8, 1, 1, 1, 1]})
    s = np.hypot(w.u, w.v)
    ax[0].plot(s.index, s.values, color=MUTED, lw=1.2)
    q = w.iloc[::6]
    ax[0].quiver(q.index, np.full(len(q), s.max() * 1.15), q.u, q.v, color=INK, width=0.002,
                 scale=200, headwidth=4)
    ax[0].set_ylim(0, s.max() * 1.35); ax[0].set_ylabel("wind (m/s)")
    ax[0].set_title("(a) wind at 10 m over the lagoon, arrows toward which it blows", loc="left")
    panels = [("lagoon", INK, "(b) whole lagoon")] + \
             [(n, COLOR[n], f"({'cde'[i]}) {n} basin, own water") for i, n in enumerate(BASINS.values())]
    for a, (col, colour, title) in zip(ax[1:], panels):
        if col == "lagoon":
            a.plot(fm.index, fm[col], color=colour, lw=2, label="FM online tracer")
        a.plot(waq.index, waq[col], color=colour, lw=2, ls="-" if col != "lagoon" else "-.",
               label="D-WAQ tracers, scheme 24")
        a.plot(od["model"].index, od["model"][col], color=colour, lw=2, ls="--",
               label="particles, Kz of the model")
        a.fill_between(od["1e-04"].index, od["1e-04"][col], od["1e-02"][col], color=colour,
                       alpha=0.12, lw=0, label="particles, Kz 10$^{-4}$ to 10$^{-2}$ m$^2$/s")
        a.axhline(np.exp(-1), color=MUTED, lw=0.6, ls=":")
        a.set_ylim(0, 1.05); a.set_ylabel("r(t)")
        a.set_title(title, loc="left"); a.legend(loc="lower left", fontsize=6.5)
    fig.autofmt_xdate()
    fig.tight_layout(); fig.savefig(out / "renewal_remaining.png", dpi=150); plt.close(fig)


def maps(d: Path, out: Path):
    fm = np.load(d / "tracer_daily.npz"); wq = np.load(d / f"{WAQ}_daily.npz")
    # the daily D-WAQ fields end on day 8, the last record of its map being dropped
    days = [3, 6, 8]
    p = xr.open_dataset(d / "particles_kzmodel.nc"); s = np.load(d / "seeds_kzmodel.npz")
    ptimes = pd.to_datetime(p.time.values)
    fig, ax = plt.subplots(3, 3, figsize=(10, 11))
    for j, day in enumerate(days):
        for i, (src, conc, label) in enumerate([(fm, fm["conc"][day], "FM online tracer"),
                                                (wq, wq["conc"][:3, day].sum(0), "D-WAQ, three basin tracers, scheme 24")]):
            sc = ax[i, j].scatter(src["cx"], src["cy"], c=conc, s=1.2, cmap="Blues", vmin=0, vmax=1)
            ax[i, j].set_title(f"{label}, day {day}", loc="left", fontsize=7.5)
        k = np.searchsorted(ptimes, ptimes[0] + pd.Timedelta(days=day))
        k = min(k, ptimes.size - 1)
        for n, name in BASINS.items():
            own = s["basin"] == n
            ax[2, j].scatter(p.lon.values[own, k], p.lat.values[own, k], s=0.3, color=COLOR[name],
                             label=name if j == 0 else None)
        ax[2, j].set_title(f"particles by basin of release, day {day}", loc="left", fontsize=7.5)
    for a in ax.flat:
        map_axes(a)
    ax[2, 0].legend(loc="lower left", markerscale=12, fontsize=7)
    fig.colorbar(sc, ax=ax[:2, :], shrink=0.6, label="fraction of lagoon water in the column")
    fig.savefig(out / "renewal_maps.png", dpi=150, bbox_inches="tight"); plt.close(fig)


def local_residence(d: Path, out: Path):
    c = xr.open_dataset(d / "currents_3d.nc")
    glon, glat, b = c.lon.values, c.lat.values, c.basin.values
    fig, ax = plt.subplots(1, 3, figsize=(10, 4.6))
    for a, kz in zip(ax, ("1e-04", "model", "1e-02")):
        p = xr.open_dataset(d / f"particles_kz{kz}.nc"); s = np.load(d / f"seeds_kz{kz}.npz")
        lon, lat = p.lon.values, p.lat.values
        i = np.rint((lon - glon[0]) / (glon[1] - glon[0])); j = np.rint((lat - glat[0]) / (glat[1] - glat[0]))
        ok = np.isfinite(i) & np.isfinite(j) & (i >= 0) & (i < glon.size) & (j >= 0) & (j < glat.size)
        where = np.full(lon.shape, -1)
        where[ok] = b[j[ok].astype(int), i[ok].astype(int)]
        share = (where == s["basin"][:, None]).mean(1)
        col = pd.DataFrame({"x": s["lon"], "y": s["lat"], "share": share, "w": s["w"]})
        col = col.groupby(["x", "y"])[["share", "w"]].apply(lambda g: np.average(g.share, weights=g.w)).reset_index()
        m = a.scatter(col.x, col.y, c=col[0], s=3, cmap=ListedColormap(plt.get_cmap("Blues")(np.linspace(0.15, 1, 10))),
                      vmin=0, vmax=1, marker="s")
        map_axes(a)
        a.set_title({"model": "Kz of the model", "1e-04": "Kz 10$^{-4}$ m$^2$/s",
                     "1e-02": "Kz 10$^{-2}$ m$^2$/s"}[kz], loc="left")
    fig.colorbar(m, ax=ax, shrink=0.7, label="share of the window in the basin of release")
    fig.savefig(out / "renewal_local_residence.png", dpi=150, bbox_inches="tight"); plt.close(fig)


def coast():
    run = ROOT / "model" / "_veg_hv040_3d"
    return split_long_segments(parse_ldb(run / "Stagnone_dxy01_15m.ldb") + parse_ldb(run / "sicily2.ldb"))


def read_pli(path: Path) -> np.ndarray:
    rows = [ln.split()[:2] for ln in path.read_text().splitlines()[2:] if ln.strip()]
    return np.array(rows, dtype=float)


def polygons(nx, ny, fn) -> list:
    return [np.c_[nx[r[r >= 0]], ny[r[r >= 0]]] for r in fn]


def draw_coast(ax, lines, lw=0.5):
    for p in lines:
        ax.plot(p[:, 0], p[:, 1], color=MUTED, lw=lw, zorder=4)


def basin_cuts(ax, x0=12.405, x1=12.495):
    for lat in BASIN_LAT:
        ax.plot([x0, x1], [lat, lat], color=INK, lw=0.7, ls="--", zorder=5)


def case(d: Path, out: Path):
    g = xr.open_dataset(d / "Stagnone_dxy01_15m_waqgeom.nc")
    nx, ny, nz = g.mesh2d_node_x.values, g.mesh2d_node_y.values, g.mesh2d_node_z.values
    fn = g.mesh2d_face_nodes.values
    fn = np.where(np.isfinite(fn), fn - int(g.mesh2d_face_nodes.attrs["start_index"]), -1).astype(int)
    depth = np.array([-nz[r[r >= 0]].mean() for r in fn])
    f = np.load(d / "frames.npz")
    lines = coast()
    bnd = read_pli(d / "Stagnone_dxy01_15m.pli")

    fig = plt.figure(figsize=(11, 6.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.35, 1, 1], wspace=0.28)
    ax = [fig.add_subplot(gs[0, i]) for i in range(3)]

    # (a) the whole domain, bed depth clipped at 60 m
    pc = PolyCollection(polygons(nx, ny, fn), array=np.clip(depth, 0, 60), cmap="Blues",
                        edgecolors="none", zorder=1)
    pc.set_clim(0, 60)
    ax[0].add_collection(pc)
    draw_coast(ax[0], lines, 0.4)
    ax[0].plot(bnd[:, 0], bnd[:, 1], color="#e34948", lw=2.2, zorder=6, label="open boundary")
    ax[0].plot([BOX[0], BOX[1], BOX[1], BOX[0], BOX[0]], [BOX[2], BOX[2], BOX[3], BOX[3], BOX[2]],
               color=INK, lw=1, ls="--", zorder=6, label="box of the particles")
    ax[0].set_xlim(11.94, 12.57); ax[0].set_ylim(37.69, 38.075)
    ax[0].set_aspect(ASPECT); ax[0].grid(False); ax[0].set_facecolor(LAND)
    ax[0].tick_params(labelsize=7)
    ax[0].legend(loc="lower left", fontsize=7, frameon=True, facecolor="white", edgecolor="none")
    fig.colorbar(pc, ax=ax[0], shrink=0.55, pad=0.02, label="bed depth (m), clipped at 60")
    ax[0].set_title("(a) domain, 25 210 faces", loc="left")
    for name, (lon, lat) in {"Marsala": (12.48, 37.775), "Trapani": (12.48, 38.035),
                             "Marettimo": (12.01, 37.935), "Favignana": (12.26, 37.905),
                             "lagoon": (12.505, 37.86)}.items():
        ax[0].text(lon, lat, name, fontsize=7, color=INK, zorder=7,
                   bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=1))

    # (b) the mesh of the lagoon, faces coloured by basin
    pb = polygons(nx, ny, f["face_nodes"])
    rgb = np.array([[1, 1, 1]] + [to_rgb(COLOR[n]) for n in BASINS.values()])
    face = rgb[f["basin"]]
    face[f["basin"] > 0] = 0.45 * face[f["basin"] > 0] + 0.55
    ax[1].add_collection(PolyCollection(pb, facecolors=face, edgecolors=MUTED, linewidths=0.08, zorder=1))
    draw_coast(ax[1], lines)
    basin_cuts(ax[1])
    for k, name in BASINS.items():
        sel = f["basin"] == k
        vol = {1: 11.9, 2: 6.36, 3: 4.36}[k]
        ax[1].text(f["x"][sel].mean() + 0.012, f["y"][sel].mean(), f"{name}\n{vol} hm$^3$",
                   fontsize=7, color=INK, zorder=7)
    for txt, xy, xyt in (("northern mouth", (12.446, 37.898), (12.405, 37.915)),
                         ("southern mouth", (12.440, 37.828), (12.402, 37.812)),
                         ("Mozia", (12.468, 37.867), (12.478, 37.857))):
        ax[1].annotate(txt, xy, xyt, fontsize=7, color=INK, zorder=7,
                       arrowprops=dict(arrowstyle="-", color=INK, lw=0.6))
    ax[1].text(12.405, 37.851, "37.848 N", fontsize=6.5, color=MUTED)
    ax[1].text(12.405, 37.878, "37.875 N", fontsize=6.5, color=MUTED)
    map_axes(ax[1]); ax[1].set_facecolor(LAND)
    ax[1].set_title("(b) mesh of the lagoon and its basins", loc="left")

    # (c) the canopy, stem density of the [veg] module
    z = np.loadtxt(d / "veg_stemdensity.xyz")
    z = z[z[:, 2] > 0]
    m = ax[2].scatter(z[:, 0], z[:, 1], c=z[:, 2], s=1.2, cmap="Greens", vmin=0, vmax=3000,
                      marker="s", lw=0, zorder=2)
    ax[2].add_collection(PolyCollection(pb, facecolors="none", edgecolors=GRID, linewidths=0.08, zorder=1))
    draw_coast(ax[2], lines)
    basin_cuts(ax[2])
    map_axes(ax[2]); ax[2].set_yticklabels([])
    fig.colorbar(m, ax=ax[2], shrink=0.55, pad=0.02, label="stem density (stems/m$^2$)")
    ax[2].set_title("(c) seagrass canopy", loc="left")
    fig.savefig(out / "renewal_case.png", dpi=150, bbox_inches="tight"); plt.close(fig)


def gif_frames(fig, update, n, path, duration=120):
    from PIL import Image
    frames = []
    for i in range(n):
        update(i)
        fig.canvas.draw()
        img = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba())
        frames.append(img.convert("RGB").quantize(colors=128, method=Image.Quantize.FASTOCTREE))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration, loop=0, optimize=True)
    plt.close(fig)
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB, {n} frames)")


def particles_at(p, t):
    k = int(np.argmin(np.abs(p["time"] - t)))
    return p["lon"][:, k], p["lat"][:, k]


def load_particles(d: Path, kz: str) -> dict:
    with xr.open_dataset(d / f"particles_kz{kz}.nc") as p:
        return {"time": pd.to_datetime(p.time.values).values, "lon": p.lon.values, "lat": p.lat.values,
                "basin": np.load(d / f"seeds_kz{kz}.npz")["basin"]}


def readings_gif(d: Path, out: Path):
    f = np.load(d / "frames.npz")
    t = pd.to_datetime(f["times"])
    inside = (f["x"] > 12.395) & (f["x"] < 12.505) & (f["y"] > 37.795) & (f["y"] < 37.93)
    pb = polygons(f["node_x"], f["node_y"], f["face_nodes"][inside])
    fm, waq = f["fm"][:, inside], f["waq"][:, :, inside]
    rgb = np.array([to_rgb(COLOR[n]) for n in BASINS.values()])
    p = load_particles(d, "model")
    pc = np.array([COLOR[BASINS[b]] for b in p["basin"]])
    r_fm = pd.read_csv(d / "tracer_remaining.csv", index_col=0, parse_dates=True)["lagoon"]
    r_wq = pd.read_csv(d / f"{WAQ}_remaining.csv", index_col=0, parse_dates=True)["lagoon"]
    r_od = pd.read_csv(d / "remaining_kzmodel.csv", index_col=0, parse_dates=True)["lagoon"]
    w = wind(pd.DatetimeIndex([t[0], t[-1]]))
    lines = coast()

    fig = plt.figure(figsize=(10.5, 7.4), dpi=90)
    gs = fig.add_gridspec(2, 3, height_ratios=[4.3, 1], hspace=0.2, wspace=0.05,
                          left=0.06, right=0.99, top=0.92, bottom=0.07)
    ax = [fig.add_subplot(gs[0, j]) for j in range(3)]
    a_fm = PolyCollection(pb, array=fm[0], cmap="Blues", edgecolors="face", linewidths=0.1, zorder=1)
    a_fm.set_clim(0, 1)
    a_wq = PolyCollection(pb, facecolors=np.ones((len(pb), 3)), edgecolors="face", linewidths=0.1, zorder=1)
    ax[0].add_collection(a_fm); ax[1].add_collection(a_wq)
    x0, y0 = particles_at(p, t[0].to_datetime64())
    a_od = ax[2].scatter(x0, y0, s=0.5, c=pc, lw=0, zorder=2)
    titles = ["online tracer of FM,\nlagoon water in the column", "D-WAQ, scheme 24,\nwater of each basin in the column",
              "particles, Kz of the model,\nby basin of release"]
    for j, a in enumerate(ax):
        map_axes(a); a.set_facecolor(LAND)
        draw_coast(a, lines); basin_cuts(a)
        a.set_title(titles[j], loc="left", fontsize=8.5)
        if j:
            a.set_yticklabels([])
    for n, c in zip(BASINS.values(), rgb):
        ax[2].scatter([], [], s=20, color=c, label=n)
    ax[2].legend(loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none")
    wtext = ax[0].text(12.405, 37.902, "", fontsize=7, color=INK, zorder=8)
    arrow = [None]
    bx = fig.add_subplot(gs[1, :])
    bx.plot(r_fm.index, r_fm, color=INK, lw=1.4, label="online tracer of FM")
    bx.plot(r_wq.index, r_wq, color=INK, lw=1.4, ls="-.", label="D-WAQ, scheme 24")
    bx.plot(r_od.index, r_od, color=INK, lw=1.4, ls="--", label="particles, Kz of the model")
    bx.axhline(np.exp(-1), color=MUTED, lw=0.6, ls=":")
    now = bx.axvline(t[0], color="#e34948", lw=1)
    bx.set_ylim(0, 1.02); bx.set_xlim(t[0], t[-1]); bx.set_ylabel("r(t), lagoon", fontsize=8)
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%d %b")); bx.tick_params(labelsize=7)
    bx.legend(loc="lower left", fontsize=7, ncol=3)
    sup = fig.suptitle("", x=0.06, ha="left", fontsize=10)

    def update(i):
        a_fm.set_array(fm[i])
        c = np.nan_to_num(waq[:, i]).clip(0, 1)
        lag = c.sum(0).clip(0, 1)
        mix = (c.T @ rgb) / np.maximum(c.sum(0), 1e-9)[:, None]
        a_wq.set_facecolor((mix * lag[:, None] + (1 - lag[:, None])).clip(0, 1))
        xx, yy = particles_at(p, t[i].to_datetime64())
        a_od.set_offsets(np.c_[xx, yy])
        if arrow[0] is not None:
            arrow[0].remove()
        u, v = w.reindex([t[i]], method="nearest").iloc[0][["u", "v"]]
        arrow[0] = ax[0].annotate("", xy=(12.418 + 0.0012 * u * ASPECT, 37.915 + 0.0012 * v),
                                  xytext=(12.418, 37.915), zorder=8,
                                  arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
        wtext.set_text(f"wind {np.hypot(u, v):.0f} m/s")
        now.set_xdata([t[i], t[i]])
        sup.set_text(f"Renewal of the lagoon from 1 July 2025 00:00 UTC, {t[i]:%d %b %H:%M} UTC")

    gif_frames(fig, update, t.size, out / "renewal_readings.gif")


def particles_gif(d: Path, out: Path, every_hours: int = 2):
    runs = {k: load_particles(d, k) for k in KZ_LABEL}
    rem = {k: pd.read_csv(d / f"remaining_kz{k}.csv", index_col=0, parse_dates=True) for k in KZ_LABEL}
    t = pd.date_range(pd.Timestamp(runs["model"]["time"][0]), pd.Timestamp(runs["model"]["time"][-1]),
                      freq=f"{every_hours}h")
    lines = coast()
    fig = plt.figure(figsize=(10.5, 7.4), dpi=90)
    gs = fig.add_gridspec(2, 3, height_ratios=[4.3, 1], hspace=0.2, wspace=0.05,
                          left=0.06, right=0.99, top=0.92, bottom=0.07)
    ax = [fig.add_subplot(gs[0, j]) for j in range(3)]
    sc = {}
    for j, (a, k) in enumerate(zip(ax, KZ_LABEL)):
        r = runs[k]
        x0, y0 = particles_at(r, t[0].to_datetime64())
        sc[k] = a.scatter(x0, y0, s=0.5, c=[COLOR[BASINS[b]] for b in r["basin"]], lw=0, zorder=2)
        map_axes(a); a.set_facecolor(LAND); draw_coast(a, lines); basin_cuts(a)
        a.set_title(KZ_LABEL[k], loc="left", fontsize=9)
        if j:
            a.set_yticklabels([])
    for n in BASINS.values():
        ax[2].scatter([], [], s=20, color=COLOR[n], label=n)
    ax[2].legend(loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none")
    bx = fig.add_subplot(gs[1, :])
    for n in BASINS.values():
        for k, ls in zip(KZ_LABEL, (":", "-", "--")):
            bx.plot(rem[k].index, rem[k][n], color=COLOR[n], ls=ls, lw=1.1,
                    label=f"{n}, {KZ_LABEL[k]}" if n == "southern" else None)
    bx.axhline(np.exp(-1), color=MUTED, lw=0.6, ls=":")
    now = bx.axvline(t[0], color=INK, lw=0.8)
    bx.set_ylim(0, 1.02); bx.set_xlim(t[0], t[-1]); bx.set_ylabel("r(t), own water", fontsize=8)
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%d %b")); bx.tick_params(labelsize=7)
    bx.legend(loc="lower left", fontsize=6.5, ncol=3)
    sup = fig.suptitle("", x=0.06, ha="left", fontsize=10)

    def update(i):
        for k in KZ_LABEL:
            sc[k].set_offsets(np.c_[particles_at(runs[k], t[i].to_datetime64())])
        now.set_xdata([t[i], t[i]])
        sup.set_text(f"Particles released 1 July 2025 00:00 UTC, {t[i]:%d %b %H:%M} UTC")

    gif_frames(fig, update, t.size, out / "renewal_particles.gif")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="veg_ic3d_0701_0710")
    ap.add_argument("--no-gif", action="store_true")
    args = ap.parse_args(argv)
    d = ROOT / "outputs" / "renewal" / args.tag
    FIG.mkdir(exist_ok=True)
    case(d, FIG)
    setup(d, FIG)
    remaining(d, FIG)
    maps(d, FIG)
    local_residence(d, FIG)
    if not args.no_gif:
        readings_gif(d, FIG)
        particles_gif(d, FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
