"""
For each deploy, invert the drifter motion to estimate the wind that would
have driven the observed drift via the standard windage model:
    drift = current + 0.02 * wind
And then solve for the optimal (alpha, beta, gamma) weights on the three
sources (AE, Mulino, ERA5) such that:
    blend_wind = alpha * AE + beta * Mulino + gamma * ERA5
matches the implied wind across all deploys.

We run two flavours:
  (A) Pure-windage model: implied_wind = drift / 0.02 (assumes current = 0)
  (B) Windage + FM current: implied_wind = (drift - current_FM_v04rE5) / 0.02

Outputs:
  data/processed/diag_implied_wind_per_deploy.csv
  figures/diag_implied_wind_vectors.png      per-deploy vector comparison
  figures/diag_implied_wind_weights.png       global weights bar chart
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import nnls

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'

WIND_DRIFT_FACTOR = 0.02


def from_to_uv(speed, dir_from_deg):
    rad = np.radians(dir_from_deg)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def uv_to_speed_dir_to(u, v):
    speed = np.hypot(u, v)
    dir_to = np.degrees(np.arctan2(u, v)) % 360
    return speed, dir_to


# ---- Load drifter tracks + sim from v04rE5 (so we can take current at the right cell) ----
tracks = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
releases = pd.read_csv(PROC / 'drifter_releases_Jul2025.csv', parse_dates=['t0'])

# Stations
ae = pd.read_csv(PROC / 'wind_AE_10min_UTC.csv', index_col=0, parse_dates=True)
mul = pd.read_csv(PROC / 'wind_Mulino_10min_UTC.csv', index_col=0, parse_dates=True)
ae['u'], ae['v'] = from_to_uv(ae.speed_10m, ae.dir_deg)
mul['u'], mul['v'] = from_to_uv(mul.speed_10m, mul.dir_deg)

# ERA5 raw (clean, used by v04rE5)
ds_eu = xr.open_dataset(ROOT / 'model' / 'dflowfm_v04rE5' / 'wind_era5raw_u10n_20250701to20250710.nc')
ds_ev = xr.open_dataset(ROOT / 'model' / 'dflowfm_v04rE5' / 'wind_era5raw_v10n_20250701to20250710.nc')

# v04rE5 surface current
ds_uc = xr.open_dataset(PROC / 'v04rE5_surface_current.nc')


def mean_at_point_time(ds_u, ds_v, lon, lat, t0, t1, u_var='u10n', v_var='v10n'):
    sl = slice(t0, t1)
    u = ds_u[u_var].sel(time=sl).interp(latitude=lat, longitude=lon)
    v = ds_v[v_var].sel(time=sl).interp(latitude=lat, longitude=lon)
    return float(u.values.mean()), float(v.values.mean())


def mean_current_at_point_time(lon, lat, t0, t1):
    sub = ds_uc.sel(time=slice(t0, t1))
    ix = int(np.argmin(np.abs(ds_uc.lon.values - lon)))
    iy = int(np.argmin(np.abs(ds_uc.lat.values - lat)))
    u = sub['x_sea_water_velocity'].isel(lat=iy, lon=ix)
    v = sub['y_sea_water_velocity'].isel(lat=iy, lon=ix)
    return float(np.nanmean(u.values)), float(np.nanmean(v.values))


def mean_station_uv(df, t0, t1):
    s = df.loc[t0:t1, ['u', 'v']]
    return float(s.u.mean()), float(s.v.mean())


# ---- Per-deploy aggregation ----
rows = []
for dep, g in tracks.groupby('deploy'):
    g = g.sort_values(['source', 'time']).reset_index(drop=True)
    t0 = g.time.min()
    t1 = g.time.max()
    # Mean drift velocity from finite-difference, averaged across drifters
    us, vs = [], []
    lons, lats = [], []
    for src, gs in g.groupby('source'):
        gs = gs.sort_values('time').reset_index(drop=True)
        dt_s = gs.time.diff().dt.total_seconds().values
        cos_lat = np.cos(np.radians(gs.lat.mean()))
        u_inst = gs.lon.diff().values * 111000 * cos_lat / dt_s
        v_inst = gs.lat.diff().values * 111000 / dt_s
        us.extend(u_inst.tolist())
        vs.extend(v_inst.tolist())
        lons.append(gs.lon.mean())
        lats.append(gs.lat.mean())
    drift_u = float(np.nanmean(us))
    drift_v = float(np.nanmean(vs))
    lon0 = float(np.nanmean(lons))
    lat0 = float(np.nanmean(lats))

    ae_u, ae_v = mean_station_uv(ae, t0, t1)
    mul_u, mul_v = mean_station_uv(mul, t0, t1)
    e5_u, e5_v = mean_at_point_time(ds_eu, ds_ev, lon0, lat0, t0, t1)
    cur_u, cur_v = mean_current_at_point_time(lon0, lat0, t0, t1)

    # Implied wind, two models
    impA_u, impA_v = drift_u / WIND_DRIFT_FACTOR, drift_v / WIND_DRIFT_FACTOR
    impB_u = (drift_u - cur_u) / WIND_DRIFT_FACTOR
    impB_v = (drift_v - cur_v) / WIND_DRIFT_FACTOR

    spd_d, dir_d = uv_to_speed_dir_to(drift_u, drift_v)
    spd_A, dir_A = uv_to_speed_dir_to(impA_u, impA_v)
    spd_B, dir_B = uv_to_speed_dir_to(impB_u, impB_v)
    spd_ae, dir_ae = uv_to_speed_dir_to(ae_u, ae_v)
    spd_mul, dir_mul = uv_to_speed_dir_to(mul_u, mul_v)
    spd_e5, dir_e5 = uv_to_speed_dir_to(e5_u, e5_v)
    spd_c, dir_c = uv_to_speed_dir_to(cur_u, cur_v)

    rows.append({
        'deploy': int(dep), 't0': t0, 't1': t1, 'lon': lon0, 'lat': lat0,
        'drift_u_ms': drift_u, 'drift_v_ms': drift_v,
        'drift_speed_ms': spd_d, 'drift_dir_to': dir_d,
        'cur_u_ms': cur_u, 'cur_v_ms': cur_v, 'cur_speed_ms': spd_c, 'cur_dir_to': dir_c,
        'implA_u': impA_u, 'implA_v': impA_v, 'implA_speed': spd_A, 'implA_dir_to': dir_A,
        'implB_u': impB_u, 'implB_v': impB_v, 'implB_speed': spd_B, 'implB_dir_to': dir_B,
        'AE_u': ae_u, 'AE_v': ae_v, 'AE_speed': spd_ae, 'AE_dir_to': dir_ae,
        'Mul_u': mul_u, 'Mul_v': mul_v, 'Mul_speed': spd_mul, 'Mul_dir_to': dir_mul,
        'E5_u': e5_u, 'E5_v': e5_v, 'E5_speed': spd_e5, 'E5_dir_to': dir_e5,
    })

df = pd.DataFrame(rows).sort_values('deploy').reset_index(drop=True)
df_out = df[['deploy', 't0', 'lon', 'lat', 'drift_speed_ms', 'drift_dir_to',
             'implA_speed', 'implA_dir_to', 'implB_speed', 'implB_dir_to',
             'AE_speed', 'AE_dir_to', 'Mul_speed', 'Mul_dir_to', 'E5_speed', 'E5_dir_to']]
print('=== Per-deploy implied wind (model A: drift/0.02) vs sources ===')
print(df_out.round(2).to_string(index=False))
df.to_csv(PROC / 'diag_implied_wind_per_deploy.csv', index=False)


# ---- Solve for optimal weights via NNLS ----
def solve_weights(impl_u, impl_v, AE_u, AE_v, Mul_u, Mul_v, E5_u, E5_v, label):
    # Stack components: 2N equations (u and v) for 12 deploys
    A = np.column_stack([
        np.concatenate([AE_u, AE_v]),
        np.concatenate([Mul_u, Mul_v]),
        np.concatenate([E5_u, E5_v]),
    ])
    b = np.concatenate([impl_u, impl_v])
    # Unconstrained least-squares
    coef_lsq, residuals, _, _ = np.linalg.lstsq(A, b, rcond=None)
    # Non-negative least squares
    coef_nnls, rnorm = nnls(A, b)
    # Sum-to-1 constrained least-squares: project NNLS onto simplex
    s = coef_nnls.sum()
    coef_simplex = coef_nnls / s if s > 0 else coef_nnls

    pred = A @ coef_nnls
    rmse = np.sqrt(((b - pred) ** 2).mean())
    pred_simplex = A @ coef_simplex
    rmse_simplex = np.sqrt(((b - pred_simplex) ** 2).mean())

    print(f'\n=== Optimal weights ({label}) ===')
    print(f'  Unconstrained LSQ: AE={coef_lsq[0]:+.3f}, Mul={coef_lsq[1]:+.3f}, E5={coef_lsq[2]:+.3f}, sum={coef_lsq.sum():+.3f}')
    print(f'  NNLS               AE={coef_nnls[0]:+.3f}, Mul={coef_nnls[1]:+.3f}, E5={coef_nnls[2]:+.3f}, sum={coef_nnls.sum():.3f}, rmse={rmse:.3f}')
    print(f'  NNLS->simplex      AE={coef_simplex[0]:+.3f}, Mul={coef_simplex[1]:+.3f}, E5={coef_simplex[2]:+.3f}, sum={coef_simplex.sum():.3f}, rmse_simplex={rmse_simplex:.3f}')
    return coef_lsq, coef_nnls, coef_simplex


resA = solve_weights(df.implA_u.values, df.implA_v.values,
                     df.AE_u.values, df.AE_v.values,
                     df.Mul_u.values, df.Mul_v.values,
                     df.E5_u.values, df.E5_v.values,
                     label='model A: drift/0.02')

resB = solve_weights(df.implB_u.values, df.implB_v.values,
                     df.AE_u.values, df.AE_v.values,
                     df.Mul_u.values, df.Mul_v.values,
                     df.E5_u.values, df.E5_v.values,
                     label='model B: (drift-FM_current)/0.02')


# ---- Visualisation 1: per-deploy vector compass ----
fig, axes = plt.subplots(3, 4, figsize=(16, 12), subplot_kw={'projection': 'polar'})
axes = axes.flatten()
for i, (_, r) in enumerate(df.iterrows()):
    ax = axes[i]
    # Each entry: (label, speed, dir_to, color)
    entries = [
        (f'implA={r.implA_speed:.1f}', r.implA_speed, r.implA_dir_to, 'black'),
        (f'AE={r.AE_speed:.1f}', r.AE_speed, r.AE_dir_to, 'deepskyblue'),
        (f'Mul={r.Mul_speed:.1f}', r.Mul_speed, r.Mul_dir_to, 'steelblue'),
        (f'E5={r.E5_speed:.1f}', r.E5_speed, r.E5_dir_to, 'darkgreen'),
    ]
    for label, spd, dir_to, col in entries:
        if not (np.isfinite(spd) and np.isfinite(dir_to)):
            continue
        ax.annotate('', xy=(np.radians(dir_to), spd), xytext=(0, 0),
                    arrowprops=dict(arrowstyle='->', color=col, lw=1.8))
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(['N', 'E', 'S', 'W'], fontsize=8)
    ax.set_rmax(max(r.implA_speed, r.AE_speed, r.Mul_speed, r.E5_speed) * 1.1)
    ax.tick_params(labelsize=7)
    ax.set_title(f'D{r.deploy} - obs drift {r.drift_speed_ms*100:.1f} cm/s\n'
                 f'TO {r.drift_dir_to:.0f} deg', fontsize=9)
    ax.grid(alpha=0.3)

# Legend
import matplotlib.patches as mpatches
handles = [
    plt.Line2D([0], [0], color='black', lw=2, label='implied wind (= drift/2%)'),
    plt.Line2D([0], [0], color='deepskyblue', lw=2, label='AE station'),
    plt.Line2D([0], [0], color='steelblue', lw=2, label='Mulino station'),
    plt.Line2D([0], [0], color='darkgreen', lw=2, label='ERA5 raw @ deploy'),
]
fig.legend(handles=handles, loc='lower center', ncol=4, fontsize=10,
           bbox_to_anchor=(0.5, 0.0), frameon=True)
fig.suptitle('Wind sources vs implied wind needed to drive observed drift\n'
             '(arrow length = m/s; arrows point in the TO direction)',
             fontsize=12, y=0.995)
plt.tight_layout(rect=[0, 0.03, 1, 0.97])
plt.savefig(FIG / 'diag_implied_wind_vectors.png', dpi=150, bbox_inches='tight')
plt.close()
print(f'\nSaved {FIG / "diag_implied_wind_vectors.png"}')


# ---- Visualisation 2: optimal weights bar chart ----
fig, ax = plt.subplots(figsize=(10, 5))
labels = ['AE', 'Mulino', 'ERA5']
x = np.arange(len(labels))
w = 0.27
ax.bar(x - w, resA[1], w, label='model A: drift/2% (NNLS)', color='steelblue', edgecolor='k')
ax.bar(x, resA[2], w, label='model A: NNLS->simplex (sum=1)', color='deepskyblue', edgecolor='k')
ax.bar(x + w, resB[2], w, label='model B: (drift-current)/2% (simplex)', color='darkgreen', edgecolor='k')
# Reference line at current IDW weights at lagoon centre (for context)
# IDW weights at lagoon centre with stations only: roughly ~0.5 each (depends on dist)
ax.axhline(0.5, color='grey', ls=':', lw=1, alpha=0.6)
ax.text(2.5, 0.51, 'reference 0.5', color='grey', fontsize=8, va='bottom')
ax.set_ylabel('Weight')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend(fontsize=9, loc='upper right')
ax.grid(axis='y', alpha=0.3)
ax.set_title('Optimal weights to match observed drifter motion across 12 deploys\n'
             'NNLS = non-negative least-squares; simplex = NNLS rescaled to sum=1')
plt.tight_layout()
plt.savefig(FIG / 'diag_implied_wind_weights.png', dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved {FIG / "diag_implied_wind_weights.png"}')


# ---- Direction-only summary: which station's direction matches each deploy? ----
def angular_diff(a, b):
    d = (a - b) % 360
    return min(d, 360 - d) if not isinstance(d, np.ndarray) else np.minimum(d, 360 - d)


print('\n=== Direction match (smaller |delta deg| = closer): closest to obs drift TO ===')
ang_ae = np.array([angular_diff(r.drift_dir_to, r.AE_dir_to) for _, r in df.iterrows()])
ang_mul = np.array([angular_diff(r.drift_dir_to, r.Mul_dir_to) for _, r in df.iterrows()])
ang_e5 = np.array([angular_diff(r.drift_dir_to, r.E5_dir_to) for _, r in df.iterrows()])
out = pd.DataFrame({
    'deploy': df.deploy,
    'drift_dir': df.drift_dir_to.round(0),
    'AE_dir': df.AE_dir_to.round(0), 'd_AE': ang_ae.round(0),
    'Mul_dir': df.Mul_dir_to.round(0), 'd_Mul': ang_mul.round(0),
    'E5_dir': df.E5_dir_to.round(0), 'd_E5': ang_e5.round(0),
})
out['winner'] = [['AE', 'Mul', 'E5'][np.argmin([a, m, e])]
                 for a, m, e in zip(ang_ae, ang_mul, ang_e5)]
print(out.to_string(index=False))
print(f'\nWinner counts: AE={(out.winner == "AE").sum()}, '
      f'Mul={(out.winner == "Mul").sum()}, E5={(out.winner == "E5").sum()}')
print(f'Mean |delta deg| - AE: {ang_ae.mean():.0f}, Mul: {ang_mul.mean():.0f}, E5: {ang_e5.mean():.0f}')
