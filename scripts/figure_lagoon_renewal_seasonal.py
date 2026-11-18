"""Figures and table of the repeated D-WAQ releases of the seasonal renewal runs.

Reads the remaining fractions written by renewal_waq_member.py for each release
of a seasonal case (waq_<yyyymmdd>_remaining.csv under outputs/renewal/<case>)
and the blended wind of the forcing of the season at the centre of the lagoon.
The time scales of each release follow renewal_common.summary, the e-folding
time measured where r falls below 1/e and the exponential fitted after the
first day. The wind of each release is averaged over its first 14 days, as
speed and as the component from the north, the direction of the wind that
emptied the lagoon in July (docs/lagoon_renewal.md, Section 7).

Writes
    figures/renewal_<season>_releases.png  wind of the season with the release
        dates, and the remaining fraction of the lagoon and of each basin
        against the days since release
    outputs/renewal/<case>/releases_summary.csv  time scales and wind by release
    figures/renewal_<season>_particles.gif  with --gif, the particles of the first
        release of renewal_lagoon_opendrift.py every 12 hours, by basin of release,
        with the wind and the remaining fraction of each basin by the particles
        and by D-WAQ
    figures/renewal_<season>_waq.gif  with --gif, the water of each basin in the
        column by D-WAQ for the same release, from the frames written every
        12 hours by renewal_waq_member.py --frame-hours 12

Usage:
    python figure_lagoon_renewal_seasonal.py summer|winter [--gif]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from renewal_common import BASINS, summary

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
CASES = {"summer": ("veg_summer_0608_0915", "forcing_summer2025", "20250607to20250917"),
         "winter": ("veg_winter_1108_0115", "forcing_winter2025", "20251107to20260117")}
WIND_DAYS = 14
RETENTION_DAYS = 30.0   # window common to every release
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"

plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.5, "axes.spines.top": False,
                     "axes.spines.right": False, "legend.frameon": False})


def wind(forcing: str, span: str) -> pd.DataFrame:
    d = ROOT / "data" / "processed" / forcing
    p = dict(latitude=37.86, longitude=12.46, method="nearest")
    u = xr.open_dataset(d / f"wind_blendedAE_u10n_{span}.nc").u10n.sel(**p).to_series()
    v = xr.open_dataset(d / f"wind_blendedAE_v10n_{span}.nc").v10n.sel(**p).to_series()
    return pd.DataFrame({"u": u, "v": v, "speed": np.hypot(u, v)})


def main(season: str) -> int:
    case, forcing, span = CASES[season]
    d = ROOT / "outputs" / "renewal" / case
    files = sorted(d.glob("waq_*_remaining.csv"))
    if not files:
        raise SystemExit(f"no release in {d}")
    rel = {pd.Timestamp(f.stem.split("_")[1]): pd.read_csv(f, index_col=0, parse_dates=True)
           for f in files}
    w = wind(forcing, span)

    rows = []
    for t0, r in rel.items():
        ww = w[(w.index >= t0) & (w.index < t0 + pd.Timedelta(days=WIND_DAYS))]
        row = {"release": t0.date(), "wind_speed": ww.speed.mean(), "wind_from_north": -ww.v.mean()}
        for k in ["lagoon", *BASINS.values()]:
            s = summary(r[k])
            row.update({f"{k}_{m}": s[m] for m in ("r_end", "tau_days", "theta_truncated_days",
                                                    "tau_fit_days")})
            row[f"{k}_window"] = s["window_days"]
            # renewal time extended by the fitted exponential, theta_W + r(W) tau_fit
            row[f"{k}_theta_extended_days"] = (s["theta_truncated_days"] + s["r_end"] * s["tau_fit_days"]
                                               if s["tau_fit_days"] else np.nan)
            # fraction left after 30 days, the shortest window common to every release
            day = (r.index - r.index[0]) / pd.Timedelta(days=1)
            row[f"{k}_r30"] = float(np.interp(30, day, r[k].values)) if day[-1] >= 30 else np.nan
        row["sum_departure_max"] = float(r["sum_departure_max"].max())
        # the particles of renewal_lagoon_opendrift.py, when run for the release
        f_od = d / f"remaining_kzmodel_{t0:%Y%m%d}.csv"
        if f_od.exists():
            od = pd.read_csv(f_od, index_col=0, parse_dates=True)
            day = (od.index - od.index[0]) / pd.Timedelta(days=1)
            for k in ["lagoon", *BASINS.values()]:
                s = summary(od[k])
                row[f"od_{k}_r30"] = float(np.interp(30, day, od[k].values)) if day[-1] >= 30 else np.nan
                row[f"od_{k}_tau_days"] = s["tau_days"]
                row[f"od_{k}_theta_extended_days"] = (s["theta_truncated_days"] + s["r_end"] * s["tau_fit_days"]
                                                      if s["tau_fit_days"] else np.nan)
        rows.append(row)
    tab = pd.DataFrame(rows).set_index("release")
    tab.to_csv(d / "releases_summary.csv", float_format="%.3f")
    with pd.option_context("display.width", 200, "display.max_columns", 40):
        print(tab.round(2).T)

    cmap = plt.get_cmap("viridis")
    col = {t0: cmap(i / max(len(rel) - 1, 1) * 0.9) for i, t0 in enumerate(rel)}
    fig = plt.figure(figsize=(7.2, 7.4), constrained_layout=True)
    gs = fig.add_gridspec(3, 3, height_ratios=[0.8, 1.3, 1])
    a = fig.add_subplot(gs[0, :])
    day = w.speed.resample("1D").mean()
    a.plot(day.index, day.values, color=MUTED, lw=1.0)
    q = w.resample("1D").mean()
    a.quiver(q.index, np.full(len(q), day.max() * 1.15), q.u, q.v, color=INK, width=0.0015,
             scale=150, headwidth=3)
    for t0 in rel:
        a.axvline(t0, color=col[t0], lw=1.4)
    a.set_ylim(0, day.max() * 1.35); a.set_ylabel("wind (m/s), daily mean")
    a.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    a.set_title("(a) wind at 10 m over the lagoon, arrows toward which it blows, and release dates",
                loc="left")

    b = fig.add_subplot(gs[1, :])
    for t0, r in rel.items():
        t = (r.index - t0) / pd.Timedelta(days=1)
        b.plot(t, r.lagoon, color=col[t0], lw=1.1, label=t0.strftime("%d %b"))
    b.axhline(np.exp(-1), color=MUTED, ls=":", lw=0.8)
    b.set_ylim(0, 1.02); b.set_xlim(0, None)
    b.set_xlabel("days since release"); b.set_ylabel("remaining fraction")
    b.set_title("(b) lagoon", loc="left")
    b.legend(loc="upper right", fontsize=7, ncol=2, title="release", title_fontsize=7)

    for i, name in enumerate(BASINS.values()):
        c = fig.add_subplot(gs[2, i], sharey=b)
        for t0, r in rel.items():
            c.plot((r.index - t0) / pd.Timedelta(days=1), r[name], color=col[t0], lw=0.9)
        c.axhline(np.exp(-1), color=MUTED, ls=":", lw=0.8)
        c.set_xlim(0, None); c.set_xlabel("days since release")
        c.set_title(f"({'cde'[i]}) {name} basin", loc="left")
        if i:
            c.tick_params(labelleft=False)
        else:
            c.set_ylabel("remaining fraction")
    out = FIG / f"renewal_{season}_releases.png"
    fig.savefig(out, dpi=200)
    print(out)
    return 0


def particles_gif(season: str, every_hours: int = 12) -> None:
    """Particles of the first release of the season, by basin of release, with the wind
    and the remaining fraction of each basin by the particles and by D-WAQ."""
    from figure_lagoon_renewal import (ASPECT, COLOR, LAND, basin_cuts, coast, draw_coast,
                                       gif_frames, map_axes, particles_at)
    case, forcing, span = CASES[season]
    d = ROOT / "outputs" / "renewal" / case
    files = sorted(d.glob("particles_kzmodel_*.nc"))
    if not files:
        print(f"no particles in {d}")
        return
    sfx = files[0].stem.replace("particles_kzmodel", "")
    with xr.open_dataset(files[0]) as p:
        run = {"time": pd.to_datetime(p.time.values).values, "lon": p.lon.values, "lat": p.lat.values,
               "basin": np.load(d / f"seeds_kzmodel{sfx}.npz")["basin"]}
    r_od = pd.read_csv(d / f"remaining_kzmodel{sfx}.csv", index_col=0, parse_dates=True)
    r_wq = pd.read_csv(d / f"waq{sfx}_remaining.csv", index_col=0, parse_dates=True)
    w = wind(forcing, span)
    t = pd.date_range(pd.Timestamp(run["time"][0]), pd.Timestamp(run["time"][-1]), freq=f"{every_hours}h")
    lines = coast()

    fig = plt.figure(figsize=(6.4, 7.6), dpi=90)
    gs = fig.add_gridspec(2, 1, height_ratios=[4.2, 1.3], hspace=0.22,
                          left=0.12, right=0.97, top=0.93, bottom=0.07)
    ax = fig.add_subplot(gs[0])
    x0, y0 = particles_at(run, t[0].to_datetime64())
    sc = ax.scatter(x0, y0, s=0.6, c=[COLOR[BASINS[b]] for b in run["basin"]], lw=0, zorder=2)
    map_axes(ax); ax.set_facecolor(LAND); draw_coast(ax, lines); basin_cuts(ax)
    for n in BASINS.values():
        ax.scatter([], [], s=20, color=COLOR[n], label=n)
    ax.legend(loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none",
              title="basin of release", title_fontsize=7)
    wtext = ax.text(12.405, 37.902, "", fontsize=7, color=INK, zorder=8)
    arrow = [None]
    bx = fig.add_subplot(gs[1])
    for n in BASINS.values():
        bx.plot(r_od.index, r_od[n], color=COLOR[n], lw=1.1)
        bx.plot(r_wq.index, r_wq[n], color=COLOR[n], lw=0.9, ls="--")
    bx.plot([], [], color=INK, lw=1.1, label="particles"); bx.plot([], [], color=INK, lw=0.9, ls="--", label="D-WAQ")
    bx.axhline(np.exp(-1), color=MUTED, lw=0.6, ls=":")
    now = bx.axvline(t[0], color=INK, lw=0.8)
    bx.set_ylim(0, 1.02); bx.set_xlim(t[0], t[-1]); bx.set_ylabel("r(t), own water", fontsize=8)
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%d %b")); bx.tick_params(labelsize=7)
    bx.legend(loc="upper right", fontsize=7, ncol=2)
    sup = fig.suptitle("", x=0.12, ha="left", fontsize=9.5)
    t0 = pd.Timestamp(run["time"][0])

    def update(i):
        sc.set_offsets(np.c_[particles_at(run, t[i].to_datetime64())])
        if arrow[0] is not None:
            arrow[0].remove()
        u, v = w.reindex([t[i]], method="nearest").iloc[0][["u", "v"]]
        arrow[0] = ax.annotate("", xy=(12.418 + 0.0012 * u * ASPECT, 37.915 + 0.0012 * v),
                               xytext=(12.418, 37.915), zorder=8,
                               arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
        wtext.set_text(f"wind {np.hypot(u, v):.0f} m/s")
        now.set_xdata([t[i], t[i]])
        sup.set_text(f"Particles released {t0:%d %B %Y}, Kz of the model, {t[i]:%d %b %H:%M} UTC")

    gif_frames(fig, update, t.size, FIG / f"renewal_{season}_particles.gif", duration=150)


def waq_gif(season: str, every_hours: int = 12) -> None:
    """Water of each basin in the column by D-WAQ for the first release of the season.

    A face takes the colour of the basin whose tracer dominates the column, faded to
    white with the share of sea water, from the column means
    written by renewal_waq_member.py --frame-hours.
    """
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import to_rgb
    from figure_lagoon_renewal import (ASPECT, COLOR, LAND, basin_cuts, coast, draw_coast,
                                       gif_frames, map_axes, polygons)
    case, forcing, span = CASES[season]
    d = ROOT / "outputs" / "renewal" / case
    files = sorted(d.glob(f"waq_*_frames{every_hours}h.npz"))
    if not files:
        print(f"no frames in {d}")
        return
    sfx = files[0].stem.split("_")[1]
    f = np.load(files[0])
    with xr.open_dataset(d / "Stagnone_dxy01_15m_waqgeom.nc") as g:
        fn = g.mesh2d_face_nodes.values
        fn = np.where(np.isfinite(fn), fn, 0).astype(int) - int(g.mesh2d_face_nodes.attrs.get("start_index", 0))
        fn[~np.isfinite(g.mesh2d_face_nodes.values)] = -1
        nx, ny = g.mesh2d_node_x.values, g.mesh2d_node_y.values
        if not np.allclose(g.mesh2d_face_x.values, f["cx"]):
            raise SystemExit("faces of the geometry differ from those of the frames")
    t = pd.to_datetime(f["times"])
    inside = (f["cx"] > 12.395) & (f["cx"] < 12.505) & (f["cy"] > 37.795) & (f["cy"] < 37.93)
    pb = polygons(nx, ny, fn[inside])
    conc = f["conc"][:3, :, inside]                                   # basin tracers (tracer, time, face)
    rgb = np.array([to_rgb(COLOR[n]) for n in BASINS.values()])
    r_wq = pd.read_csv(d / f"waq_{sfx}_remaining.csv", index_col=0, parse_dates=True)
    w = wind(forcing, span)
    lines = coast()

    fig = plt.figure(figsize=(6.4, 7.6), dpi=90)
    gs = fig.add_gridspec(2, 1, height_ratios=[4.2, 1.3], hspace=0.22,
                          left=0.12, right=0.97, top=0.93, bottom=0.07)
    ax = fig.add_subplot(gs[0])
    pc = PolyCollection(pb, facecolors=np.ones((len(pb), 3)), edgecolors="face", linewidths=0.1, zorder=1)
    ax.add_collection(pc)
    map_axes(ax); ax.set_facecolor(LAND); draw_coast(ax, lines); basin_cuts(ax)
    for n in BASINS.values():
        ax.scatter([], [], s=30, marker="s", color=COLOR[n], label=n)
    ax.scatter([], [], s=30, marker="s", color="white", edgecolors=MUTED, linewidths=0.5, label="sea water")
    ax.legend(loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none",
              title="water in the column", title_fontsize=7)
    wtext = ax.text(12.405, 37.902, "", fontsize=7, color=INK, zorder=8)
    arrow = [None]
    bx = fig.add_subplot(gs[1])
    for n in BASINS.values():
        bx.plot(r_wq.index, r_wq[n], color=COLOR[n], lw=1.1, label=n)
    bx.plot(r_wq.index, r_wq["lagoon"], color=INK, lw=1.3, label="lagoon")
    bx.axhline(np.exp(-1), color=MUTED, lw=0.6, ls=":")
    now = bx.axvline(t[0], color=INK, lw=0.8)
    bx.set_ylim(0, 1.02); bx.set_xlim(t[0], r_wq.index[-1]); bx.set_ylabel("r(t), D-WAQ", fontsize=8)
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%d %b")); bx.tick_params(labelsize=7)
    bx.legend(loc="upper right", fontsize=7, ncol=4)
    sup = fig.suptitle("", x=0.12, ha="left", fontsize=9.5)

    def update(i):
        c = np.nan_to_num(conc[:, i]).clip(0, 1)
        lag = c.sum(0).clip(0, 1)
        top = rgb[np.argmax(c, axis=0)]           # basin whose water dominates the column
        pc.set_facecolor((top * lag[:, None] + (1 - lag[:, None])).clip(0, 1))
        if arrow[0] is not None:
            arrow[0].remove()
        u, v = w.reindex([t[i]], method="nearest").iloc[0][["u", "v"]]
        arrow[0] = ax.annotate("", xy=(12.418 + 0.0012 * u * ASPECT, 37.915 + 0.0012 * v),
                               xytext=(12.418, 37.915), zorder=8,
                               arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
        wtext.set_text(f"wind {np.hypot(u, v):.0f} m/s")
        now.set_xdata([t[i], t[i]])
        sup.set_text(f"D-WAQ release of {t[0]:%d %B %Y}, scheme 24, {t[i]:%d %b %H:%M} UTC")

    gif_frames(fig, update, t.size, FIG / f"renewal_{season}_waq.gif", duration=150)


def retention(season: str, days: float = RETENTION_DAYS) -> pd.DataFrame:
    """Days of the first `days` after release that the particles of each seeded column
    spend inside the lagoon and inside their basin of release, averaged over the
    particles of the column with their volumes as weights and over the releases.

    The basin of a position is read on the grid of the currents (basin_grid.npz,
    saved from currents_3d.nc), and a particle that has left the box counts as
    outside.
    """
    case = CASES[season][0]
    d = ROOT / "outputs" / "renewal" / case
    g = np.load(d / "basin_grid.npz")
    glon, glat, b = g["lon"], g["lat"], g["basin"]
    cols = []
    for f in sorted(d.glob("particles_kzmodel_*.nc")):
        sfx = f.stem.replace("particles_kzmodel", "")
        s = np.load(d / f"seeds_kzmodel{sfx}.npz")
        with xr.open_dataset(f) as p:
            t = pd.to_datetime(p.time.values)
            n = int(np.searchsorted(t, t[0] + pd.Timedelta(days=days)))
            lon, lat = p.lon.values[:, :n], p.lat.values[:, :n]
        dt = (t[1] - t[0]) / pd.Timedelta(days=1)
        i = np.rint((lon - glon[0]) / (glon[1] - glon[0]))
        j = np.rint((lat - glat[0]) / (glat[1] - glat[0]))
        ok = np.isfinite(i) & np.isfinite(j) & (i >= 0) & (i < glon.size) & (j >= 0) & (j < glat.size)
        where = np.full(lon.shape, -1, np.int8)
        where[ok] = b[j[ok].astype(int), i[ok].astype(int)]
        c = pd.DataFrame({"x": s["lon"], "y": s["lat"], "basin": s["basin"], "w": s["w"],
                          "lagoon": (where > 0).sum(1) * dt, "own": (where == s["basin"][:, None]).sum(1) * dt})
        c = c.groupby(["x", "y", "basin"]).apply(
            lambda q: pd.Series({k: np.average(q[k], weights=q.w) for k in ("lagoon", "own")}),
            include_groups=False).reset_index()
        c["release"] = sfx[1:]
        cols.append(c)
    allc = pd.concat(cols)
    mean = allc.groupby(["x", "y", "basin"])[["lagoon", "own"]].mean().reset_index()
    mean.to_csv(d / "retention_columns.csv", index=False, float_format="%.3f")
    return mean


def retention_map(days: float = RETENTION_DAYS) -> None:
    """Map of the mean retention by seeded column in summer and in winter."""
    from matplotlib.colors import ListedColormap
    from figure_lagoon_renewal import COLOR, LAND, basin_cuts, coast, draw_coast, map_axes
    lines = coast()
    cmap = ListedColormap(plt.get_cmap("Blues")(np.linspace(0.12, 1, 12)))
    res = {s: retention(s, days) for s in CASES}
    fig, ax = plt.subplots(2, 2, figsize=(7.2, 8.6), constrained_layout=True)
    for i, (key, what) in enumerate([("lagoon", "inside the lagoon"), ("own", "inside the basin of release")]):
        for j, s in enumerate(CASES):
            a = ax[i, j]; m = res[s]
            sc = a.scatter(m.x, m.y, c=m[key], s=7, marker="s", lw=0, cmap=cmap, vmin=0, vmax=days, zorder=2)
            map_axes(a); a.set_facecolor(LAND); draw_coast(a, lines); basin_cuts(a)
            n = len(list((ROOT / "outputs" / "renewal" / CASES[s][0]).glob("particles_kzmodel_*.nc")))
            a.set_title(f"({'abcd'[2 * i + j]}) {s}, {n} releases,\n days {what}", loc="left", fontsize=8)
            if j:
                a.tick_params(labelleft=False)
        fig.colorbar(sc, ax=ax[i, :], shrink=0.8, label=f"days of the first {days:.0f} after release")
    out = FIG / "renewal_seasonal_retention.png"
    fig.savefig(out, dpi=200)
    print(out)
    for s, m in res.items():
        print(s, m.groupby("basin")[["lagoon", "own"]].describe(percentiles=[0.1, 0.5, 0.9]).round(1).T)


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else "summer"
    if s == "retention":
        retention_map()
        raise SystemExit(0)
    main(s)
    if "--gif" in sys.argv:
        particles_gif(s)
        waq_gif(s)
    raise SystemExit(0)
