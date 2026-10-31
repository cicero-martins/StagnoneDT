"""Definitions shared by the renewal computations of the lagoon.

The lagoon is the set of faces where the lagoon_tracer of FM starts at 1
(lagoon_tracer_init.xyz), closed at the southern mouth by the meridian of
12.4395 E and at the northern mouth at the head of the channel. It is divided
into three working sub-basins by latitude, the southern basin below the narrows
at 37.848 N, the central basin up to the latitude of Mozia, 37.875 N, and the
northern basin beyond it.

The measures of renewal follow the particle study of the Valletta harbours in
the MaltaDT repository (docs/harbour_renewal_particles.md). The remaining
fraction r(t) of a marked volume gives the time tau at which r first falls
below 1/e, the mean residence time of Takeoka (1984) truncated at the end of
the window, and an exponential fitted to ln r after the first day, extrapolated
to the times of 95 and 99 per cent renewal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASINS = {1: "southern", 2: "central", 3: "northern"}
BASIN_LAT = (37.848, 37.875)      # southern | central | northern


def lagoon_faces(model_dir, lon: np.ndarray, lat: np.ndarray, max_dist: float = 150.0) -> np.ndarray:
    """True where the nearest sample of lagoon_tracer_init.xyz, within max_dist m, is 1.

    The samples are the centres of the lagoon faces, some 100 m apart in the
    southern basin, so that 150 m reaches every point of a grid of 50 m.

    The sample file rather than the tracer at the first output, since a member
    restarted later carries a tracer already flushed.
    """
    from scipy.spatial import cKDTree
    s = np.loadtxt(f"{model_dir}/lagoon_tracer_init.xyz")
    k = np.cos(np.radians(37.86)) * 111320.0
    lon, lat = np.asarray(lon), np.asarray(lat)
    dist, j = cKDTree(np.c_[s[:, 0] * k, s[:, 1] * 110540.0]).query(
        np.c_[lon.ravel() * k, lat.ravel() * 110540.0])
    return ((s[j, 2] > 0.5) & (dist < max_dist)).reshape(lon.shape)


def basin_id(lat: np.ndarray, lagoon: np.ndarray) -> np.ndarray:
    """0 outside the lagoon, 1 to 3 for the southern, central and northern basins."""
    b = np.where(lat < BASIN_LAT[0], 1, np.where(lat < BASIN_LAT[1], 2, 3))
    return np.where(lagoon, b, 0).astype(np.int8)


def summary(r: pd.Series, fit_from_days: float = 1.0) -> dict:
    """tau at 1/e, truncated theta, and the exponential fitted after the first day."""
    t = (r.index - r.index[0]).total_seconds() / 86400
    below = np.flatnonzero(r.values < np.exp(-1))
    tau = float(t[below[0]]) if below.size else None
    late = (t >= fit_from_days) & (r.values > 0)
    b, a = np.polyfit(t[late], np.log(r.values[late]), 1) if late.sum() > 2 else (0.0, 0.0)
    tau_fit = -1 / b if b < 0 else None
    t95 = tau_fit * np.log(np.exp(a) / 0.05) if tau_fit else None
    t99 = tau_fit * np.log(np.exp(a) / 0.01) if tau_fit else None
    return dict(tau_days=tau, theta_truncated_days=float(np.trapezoid(r.values, t)),
                r_end=float(r.values[-1]), tau_fit_days=tau_fit,
                t95_days=t95, t99_days=t99, window_days=float(t[-1]))
