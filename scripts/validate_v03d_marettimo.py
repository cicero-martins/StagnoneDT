"""Validate v03d WL at the Marettimo offshore tide gauge (12.06°E, 37.97°N).

Extracts model WL at the nearest map.nc cell to Marettimo across all 4 partitions,
picks the cell that has the smallest distance, then compares to the ISPRA in-situ
record. Also includes a "ring scan" — try the 9 nearest cells to find the best
match (often the nearest cell falls on land and gives bad results).

Compares the same windows as the lagoon validation:
  - full 9d
  - clean 12h-day3 (post-spinup, pre-freeze)
  - post-freeze 4-9d
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import netCDF4
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


MARETTIMO_LON = 12.06
MARETTIMO_LAT = 37.97


def load_marettimo():
    df = pd.read_csv('data/raw/insitu/marettimo_wl_raw.csv')
    df['t'] = pd.to_datetime(df['Time(UTC)'], format='%d %b %Y %H:%M:%S')
    df['v'] = pd.to_numeric(df['Level'], errors='coerce')
    df = df.dropna(subset=['t', 'v']).set_index('t').sort_index()
    return df['v']


def metrics(obs, mod):
    df = pd.concat([obs.rename('obs'), mod.rename('mod')], axis=1).dropna()
    if len(df) < 10:
        return dict(N=len(df))
    o, m = df['obs'].values, df['mod'].values
    rmse = float(np.sqrt(np.mean((o - m) ** 2)))
    bias = float(np.mean(m - o))
    corr = float(np.corrcoef(o, m)[0, 1])
    o_mean = o.mean()
    denom = float(np.sum((np.abs(m - o_mean) + np.abs(o - o_mean)) ** 2))
    willmott = 1 - float(np.sum((m - o) ** 2)) / denom if denom > 0 else float('nan')
    return dict(N=len(df), RMSE=rmse, Bias=bias, Corr=corr,
                Willmott_d=willmott, Std_obs=float(o.std()), Std_mod=float(m.std()))


def find_marettimo_cell():
    """Scan all 4 partitions, find the closest wet cell to Marettimo."""
    best = None
    for p in range(4):
        fn = f'model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_000{p}_map.nc'
        nc = netCDF4.Dataset(fn)
        fx = nc.variables['mesh2d_face_x'][:]
        fy = nc.variables['mesh2d_face_y'][:]
        bl = nc.variables['mesh2d_flowelem_bl'][:]
        # Wet cells (z < 0, i.e., below MSL)
        wet = bl < 0
        if not wet.any():
            nc.close()
            continue
        d2 = (fx - MARETTIMO_LON) ** 2 + (fy - MARETTIMO_LAT) ** 2
        d2_wet = np.where(wet, d2, np.inf)
        idx = int(np.argmin(d2_wet))
        d_min = float(np.sqrt(d2_wet[idx])) * 111  # km
        cand = dict(partition=p, idx=idx, lon=float(fx[idx]), lat=float(fy[idx]),
                    bl=float(bl[idx]), dist_km=d_min, file=fn)
        if best is None or cand['dist_km'] < best['dist_km']:
            best = cand
        nc.close()
    return best


def extract_wl_at(p, idx):
    fn = f'model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_000{p}_map.nc'
    nc = netCDF4.Dataset(fn)
    t = nc.variables['time'][:]
    s1 = nc.variables['mesh2d_s1'][:, idx]
    nc.close()
    times = pd.to_datetime('2025-01-01') + pd.to_timedelta(t, 's')
    return pd.Series(s1, index=times)


def main():
    print('Looking for nearest wet cell to Marettimo (12.06, 37.97) across 4 partitions...')
    cell = find_marettimo_cell()
    print(f'  best cell: partition {cell["partition"]}, idx {cell["idx"]}')
    print(f'  at lon={cell["lon"]:.4f}, lat={cell["lat"]:.4f}, '
          f'distance from Marettimo={cell["dist_km"]:.2f} km, bedlevel={cell["bl"]:.1f} m')

    mod = extract_wl_at(cell['partition'], cell['idx'])
    print(f'  model WL: {len(mod)} samples from {mod.index[0]} to {mod.index[-1]}')

    obs = load_marettimo()
    print(f'  in-situ Marettimo: {len(obs)} samples from {obs.index[0]} to {obs.index[-1]}')

    # Mean-remove for anomaly comparison
    mod_anom = mod - mod.mean()
    obs_anom = obs - obs.mean()

    # Resample obs to model 30-min grid (mapInterval=1800s)
    obs_resampled = obs_anom.reindex(mod_anom.index, method='nearest', tolerance=pd.Timedelta('30min'))

    # Three windows
    spinup_end = pd.Timestamp('2025-07-01T12:00')
    freeze_t = pd.Timestamp('2025-07-04T00:00')
    sim_end = pd.Timestamp('2025-07-10T00:00')
    windows = {
        'full 9d': (pd.Timestamp('2025-07-01T00:00'), sim_end),
        'clean (12h-3d)': (spinup_end, freeze_t),
        'post-freeze (4-9d)': (freeze_t, sim_end),
    }

    print()
    print('=== Marettimo offshore (v03d) — windowed metrics ===')
    rows = []
    for w_name, (t0, t1) in windows.items():
        idx = (mod_anom.index >= t0) & (mod_anom.index < t1)
        m = metrics(obs_resampled[idx], mod_anom[idx])
        m['Window'] = w_name
        rows.append(m)
        std_ratio = m.get('Std_mod', float('nan')) / m.get('Std_obs', float('nan')) if m.get('Std_obs', 0) > 0 else float('nan')
        print(f'  {w_name:24s}: N={m.get("N", 0):4d}, RMSE={m.get("RMSE", float("nan")):.4f} m, '
              f'Corr={m.get("Corr", float("nan")):.4f}, std_m/std_o={std_ratio:.3f}, '
              f'd={m.get("Willmott_d", float("nan")):.3f}')

    df = pd.DataFrame(rows)
    df.to_csv('data/processed/validation_metrics_v03d_marettimo.csv', index=False)
    print(f'Saved data/processed/validation_metrics_v03d_marettimo.csv')

    # Plot
    fig, ax = plt.subplots(1, 1, figsize=(14, 5))
    ax.plot(mod_anom.index, mod_anom.values, label=f'v03d model (cell at {cell["lon"]:.3f}, {cell["lat"]:.3f}, '
                                                     f'{cell["dist_km"]:.1f} km from gauge)', color='C0', lw=0.9)
    ax.plot(obs_anom.index, obs_anom.values, label='Marettimo ISPRA in-situ', color='C3', lw=0.6, alpha=0.6)
    ax.axvline(spinup_end, color='gray', ls=':', lw=0.7)
    ax.axvline(freeze_t, color='black', ls='--', lw=0.9, alpha=0.7)
    ax.set_ylabel('WL anomaly [m]')
    ax.set_title('Marettimo offshore validation — v03d 9-day run')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.tight_layout()
    plt.savefig('figures/v03d_wl_validation_marettimo.png', dpi=110)
    print('Saved figures/v03d_wl_validation_marettimo.png')


if __name__ == '__main__':
    main()
