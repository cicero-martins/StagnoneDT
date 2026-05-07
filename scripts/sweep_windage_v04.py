"""
Sweep WIND_DRIFT_FACTOR for OpenDrift on v04 surface currents and report
per-deploy mean L&W skill + endpoint separation per windage value.

Outputs:
  data/processed/drifter_windage_sweep_v04.csv  - long-form per-drifter metrics
  data/processed/drifter_windage_sweep_v04_summary.csv - mean per (windage, deploy)
  prints a comparison table at the end

Each windage takes ~30 s of OpenDrift run for 35 particles over ~60 h, so the
full sweep is a few minutes.

Run:
    python scripts/sweep_windage_v04.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import timedelta

import warnings
warnings.filterwarnings('ignore', category=UserWarning)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'

# Sweep values
WIND_FACTORS = [0.005, 0.01, 0.02, 0.03, 0.04]


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


def liu_weisberg_skill(obs_lon, obs_lat, sim_lon, sim_lat):
    d = haversine_m(obs_lon, obs_lat, sim_lon, sim_lat)
    step = haversine_m(obs_lon[:-1], obs_lat[:-1], obs_lon[1:], obs_lat[1:])
    L = np.cumsum(np.concatenate([[0.0], step]))
    valid = L > 0
    if not valid.any():
        return np.nan
    c = (d[valid] / L[valid]).sum() / valid.sum()
    return max(0.0, 1.0 - c)


def main():
    import xarray as xr
    from opendrift.readers.reader_netCDF_CF_generic import Reader as GenericReader
    from opendrift.models.oceandrift import OceanDrift

    releases = pd.read_csv(PROC / 'drifter_releases_Jul2025.csv',
                           parse_dates=['t0'])
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv',
                      parse_dates=['time'])
    print(f'Releases: {len(releases)}; observed positions: {len(obs)}')

    regridded_nc = PROC / 'v04_surface_current.nc'
    assert regridded_nc.exists(), f'Missing {regridded_nc}'

    all_metrics = []
    for wf in WIND_FACTORS:
        print(f'\n=== WIND_DRIFT_FACTOR = {wf} ===')
        reader = GenericReader(str(regridded_nc))
        o = OceanDrift(loglevel=40)
        o.add_reader(reader)
        o.set_config('drift:horizontal_diffusivity', 0.1)
        o.set_config('drift:advection_scheme', 'runge-kutta4')
        o.set_config('general:coastline_action', 'previous')

        rv = releases[
            (releases['t0'] >= pd.Timestamp(reader.start_time)) &
            (releases['t0'] <= pd.Timestamp(reader.end_time) - pd.Timedelta(hours=1))
        ].reset_index(drop=True)

        for _, row in rv.iterrows():
            o.seed_elements(
                lon=row['lon0'], lat=row['lat0'],
                time=row['t0'].to_pydatetime(),
                number=1, z=0,
                wind_drift_factor=wf,
            )

        run_end = pd.Timestamp(reader.end_time).to_pydatetime()
        out_nc = PROC / f'opendrift_v04_wf{int(wf*1000):03d}.nc'
        o.run(end_time=run_end, time_step=300, time_step_output=600,
              outfile=str(out_nc))
        print(f'  ran {o.num_elements_active()} active, {o.num_elements_deactivated()} deactivated')

        # Score
        od = xr.open_dataset(out_nc)
        for ti in range(od.sizes['trajectory']):
            sim_lon = od.lon.isel(trajectory=ti).values
            sim_lat = od.lat.isel(trajectory=ti).values
            sim_t = pd.to_datetime(od.time.values)
            valid = ~np.isnan(sim_lon) & ~np.isnan(sim_lat)
            if valid.sum() < 3:
                continue
            row = rv.iloc[ti]
            dep, drift_id = int(row['deploy']), row['drifter_id']
            obs_g = obs[(obs['deploy'] == dep) & (obs['source'] == drift_id)].sort_values('time')
            if len(obs_g) < 3:
                continue
            obs_lon_arr = obs_g['lon'].values
            obs_lat_arr = obs_g['lat'].values
            obs_tarr = obs_g['time'].values.astype('datetime64[s]').astype(float)
            sim_t_f = sim_t.values.astype('datetime64[s]').astype(float)
            mask = (sim_t_f >= obs_tarr.min()) & (sim_t_f <= obs_tarr.max()) & valid
            if mask.sum() < 3:
                continue
            stf = sim_t_f[mask]
            ol = np.interp(stf, obs_tarr, obs_lon_arr)
            oa = np.interp(stf, obs_tarr, obs_lat_arr)
            sl = sim_lon[mask]
            sa = sim_lat[mask]
            ep = haversine_m(ol[-1], oa[-1], sl[-1], sa[-1])
            op = haversine_m(ol[:-1], oa[:-1], ol[1:], oa[1:]).sum()
            sp = haversine_m(sl[:-1], sa[:-1], sl[1:], sa[1:]).sum()
            sk = liu_weisberg_skill(ol, oa, sl, sa)
            all_metrics.append({
                'windage': wf, 'deploy': dep, 'drifter_id': drift_id,
                'n_steps': int(mask.sum()),
                'endpoint_sep_m': ep, 'obs_path_m': op, 'sim_path_m': sp,
                'path_ratio': sp / op if op > 0 else np.nan,
                'LW_skill': sk,
            })
        od.close()

    df_m = pd.DataFrame(all_metrics)
    df_m.to_csv(PROC / 'drifter_windage_sweep_v04.csv', index=False)
    print(f'\nWrote {PROC / "drifter_windage_sweep_v04.csv"} ({len(df_m)} rows)')

    # Summary: mean per (windage)
    summary = df_m.groupby('windage').agg(
        n=('LW_skill', 'size'),
        mean_endpoint_sep_m=('endpoint_sep_m', 'mean'),
        median_endpoint_sep_m=('endpoint_sep_m', 'median'),
        mean_path_ratio=('path_ratio', 'mean'),
        mean_LW_skill=('LW_skill', 'mean'),
        median_LW_skill=('LW_skill', 'median'),
        n_skill_above_05=('LW_skill', lambda s: (s > 0.5).sum()),
    ).round(3)
    print('\n=== Sweep summary ===')
    print(summary.to_string())
    summary.to_csv(PROC / 'drifter_windage_sweep_v04_summary.csv')

    # Per (windage, deploy) mean
    per_dep = df_m.groupby(['windage', 'deploy']).agg(
        mean_endpoint_sep_m=('endpoint_sep_m', 'mean'),
        mean_LW_skill=('LW_skill', 'mean'),
    ).round(2)
    print('\n=== Mean LW_skill per (windage, deploy) ===')
    print(per_dep.unstack(level='deploy')['mean_LW_skill'].to_string())


if __name__ == '__main__':
    main()
