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

Usage:
    python figure_lagoon_renewal_seasonal.py summer|winter
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "summer"))
