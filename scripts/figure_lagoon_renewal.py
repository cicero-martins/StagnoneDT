"""Figures of the renewal of the lagoon, after figure_harbour_renewal.py of MaltaDT.

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

Usage:
    python figure_lagoon_renewal.py [--tag veg_ic3d_0701_0710]
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
from matplotlib.colors import ListedColormap

from renewal_common import BASINS

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
WIND = ROOT / "model" / "dflowfm_v04AE_nowaves"
# the D-WAQ run of the flux-corrected scheme 24, less diffusive than the upwind scheme 15
WAQ = "waq_s24"
COLOR = {"southern": "#2a78d6", "central": "#eb6834", "northern": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="veg_ic3d_0701_0710")
    args = ap.parse_args(argv)
    d = ROOT / "outputs" / "renewal" / args.tag
    FIG.mkdir(exist_ok=True)
    setup(d, FIG)
    remaining(d, FIG)
    maps(d, FIG)
    local_residence(d, FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
