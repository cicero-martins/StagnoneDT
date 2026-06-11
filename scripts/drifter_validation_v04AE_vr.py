"""Drifter validation for v04AE_vr (Jul 1-10 D-Morph ON, VR ON), end-to-end.

Mirror of [drifter_validation_v04AE.py] with paths/labels swapped. Compares
LW skill + endpoint sep + path ratio against the previous baseline v04AE
(memory v04AE_new_drifter_baseline: LW 0.570, EP 566 m globally).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

from opendrift.readers.reader_netCDF_CF_generic import Reader as GenericReader
from opendrift.models.oceandrift import OceanDrift

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
REGRID = PROC / 'v04AE_vr_surface_current.nc'

WINDAGE = 0.02


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
    assert REGRID.exists(), f'Missing {REGRID} — run regrid_v04AE_vr_for_opendrift.py first'
    print(f'Regrid file: {REGRID} ({REGRID.stat().st_size / 1e6:.1f} MB)')

    releases = pd.read_csv(PROC / 'drifter_releases_Jul2025.csv', parse_dates=['t0'])
    print(f'Releases: {len(releases)} drifters across {releases["deploy"].nunique()} deploys')

    tracks = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    print(f'Obs tracks: {len(tracks)} positions')

    reader = GenericReader(str(REGRID))
    print(f'Reader: time {reader.start_time} -> {reader.end_time}')

    o = OceanDrift(loglevel=30)
    o.add_reader(reader)
    o.set_config('drift:horizontal_diffusivity', 0.1)
    o.set_config('drift:advection_scheme', 'runge-kutta4')
    o.set_config('general:coastline_action', 'previous')

    releases_valid = releases[
        (releases['t0'] >= pd.Timestamp(reader.start_time)) &
        (releases['t0'] <= pd.Timestamp(reader.end_time) - pd.Timedelta(hours=1))
    ].reset_index(drop=True)
    print(f'Valid releases inside reader window: {len(releases_valid)} / {len(releases)}')

    chk = xr.open_dataset(REGRID)

    def _on_water(lon, lat):
        iy = int(np.argmin(np.abs(chk.lat.values - lat)))
        ix = int(np.argmin(np.abs(chk.lon.values - lon)))
        return not np.isnan(chk['x_sea_water_velocity'].isel(time=0, lat=iy, lon=ix).values)

    n_land = sum(1 for _, r in releases_valid.iterrows() if not _on_water(r['lon0'], r['lat0']))
    print(f'Releases on (regrid) land cells: {n_land}')
    chk.close()

    for _, row in releases_valid.iterrows():
        o.seed_elements(
            lon=row['lon0'], lat=row['lat0'],
            time=row['t0'].to_pydatetime(),
            number=1, z=0,
            wind_drift_factor=WINDAGE,
        )
    print(f'Seeded {o.num_elements_scheduled()} particles')

    out_nc = PROC / 'opendrift_v04AE_vr.nc'
    run_end = pd.Timestamp(reader.end_time).to_pydatetime()
    print(f'Running OpenDrift until {run_end}...')
    o.run(end_time=run_end, time_step=300, time_step_output=600, outfile=str(out_nc))
    print(f'Done - {o.num_elements_active()} active, {o.num_elements_deactivated()} deactivated')

    od = xr.open_dataset(out_nc)
    sim_rows = []
    for traj in range(od.sizes['trajectory']):
        lons = od.lon.isel(trajectory=traj).values
        lats = od.lat.isel(trajectory=traj).values
        ts = pd.to_datetime(od.time.values)
        valid = ~np.isnan(lons) & ~np.isnan(lats)
        if valid.sum() < 2:
            continue
        row = releases_valid.iloc[traj]
        sim_rows.append(pd.DataFrame({
            'time': ts[valid], 'lon': lons[valid], 'lat': lats[valid],
            'deploy': row['deploy'], 'drifter_id': row['drifter_id'],
        }))
    sim_df = pd.concat(sim_rows, ignore_index=True) if sim_rows else pd.DataFrame()
    sim_csv = PROC / 'drifter_sim_v04AE_vr.csv'
    sim_df.to_csv(sim_csv, index=False)
    print(f'Saved {sim_csv} ({len(sim_df)} rows)')

    metrics = []
    for (dep, drift_id), sim in sim_df.groupby(['deploy', 'drifter_id']):
        sim = sim.sort_values('time').reset_index(drop=True)
        obs = tracks[(tracks['deploy'] == dep) & (tracks['source'] == drift_id)] \
                .sort_values('time').reset_index(drop=True)
        if len(obs) < 3:
            continue
        obs_t = obs['time'].values.astype('datetime64[s]').astype(float)
        sim_t = sim['time'].values.astype('datetime64[s]').astype(float)
        mask = (sim_t >= obs_t.min()) & (sim_t <= obs_t.max())
        if mask.sum() < 3:
            continue
        st = sim_t[mask]
        obs_lon = np.interp(st, obs_t, obs['lon'].values)
        obs_lat = np.interp(st, obs_t, obs['lat'].values)
        sim_lon = sim['lon'].values[mask]
        sim_lat = sim['lat'].values[mask]
        endpoint_sep = haversine_m(obs_lon[-1], obs_lat[-1], sim_lon[-1], sim_lat[-1])
        obs_path = haversine_m(obs_lon[:-1], obs_lat[:-1], obs_lon[1:], obs_lat[1:]).sum()
        sim_path = haversine_m(sim_lon[:-1], sim_lat[:-1], sim_lon[1:], sim_lat[1:]).sum()
        metrics.append({
            'deploy': dep, 'drifter_id': drift_id, 'n_steps': int(mask.sum()),
            'endpoint_sep_m': endpoint_sep,
            'obs_path_m': obs_path, 'sim_path_m': sim_path,
            'path_ratio': sim_path / obs_path if obs_path > 0 else np.nan,
            'LW_skill': liu_weisberg_skill(obs_lon, obs_lat, sim_lon, sim_lat),
        })
    metrics_df = pd.DataFrame(metrics)
    metrics_csv = PROC / 'drifter_metrics_v04AE_vr.csv'
    metrics_df.to_csv(metrics_csv, index=False)
    print(f'\nScored {len(metrics_df)} tracks. Saved {metrics_csv}')

    if len(metrics_df):
        print(f'\nv04AE_vr summary:')
        print(f'  Mean endpoint sep: {metrics_df["endpoint_sep_m"].mean():.0f} m')
        print(f'  Mean path ratio:   {metrics_df["path_ratio"].mean():.3f}')
        print(f'  Mean L&W skill:    {metrics_df["LW_skill"].mean():.3f}')

        # Compare against v04AE (the previous baseline)
        rows = []
        for label, fn in [('v04AE', 'drifter_metrics_v04AE.csv'),
                          ('v04rAE', 'drifter_metrics_v04rAE.csv')]:
            p = PROC / fn
            if p.exists():
                tmp = pd.read_csv(p)[['deploy', 'drifter_id', 'endpoint_sep_m', 'LW_skill']]
                tmp = tmp.rename(columns={'endpoint_sep_m': f'EP_{label}',
                                          'LW_skill': f'LW_{label}'})
                rows.append(tmp)
        cmp = metrics_df.rename(columns={'endpoint_sep_m': 'EP_v04AE_vr',
                                          'LW_skill': 'LW_v04AE_vr'})
        cmp = cmp[['deploy', 'drifter_id', 'EP_v04AE_vr', 'LW_v04AE_vr']]
        for tmp in rows:
            cmp = cmp.merge(tmp, on=['deploy', 'drifter_id'], how='left')

        per = cmp.groupby('deploy').agg({
            c: 'mean' for c in cmp.columns
            if c.startswith(('EP_', 'LW_'))
        }).round(2)
        cols = sorted([c for c in per.columns if c.startswith('LW_')]) + \
               sorted([c for c in per.columns if c.startswith('EP_')])
        per = per[cols]
        print('\n=== Per-deploy mean: LW skill + endpoint sep [m] ===')
        print(per.to_string())

        print('\n=== Global means ===')
        for label in ['v04rAE', 'v04AE', 'v04AE_vr']:
            col = f'LW_{label}'; ep_col = f'EP_{label}'
            if col in cmp.columns:
                print(f'  {label:11s}: LW={cmp[col].mean():.3f}  '
                      f'EP={cmp[ep_col].mean():.0f} m  '
                      f'n={cmp[col].notna().sum()}')

        for ref in ['v04AE', 'v04rAE']:
            ref_lw = f'LW_{ref}'
            if ref_lw in cmp.columns:
                dlw = cmp['LW_v04AE_vr'].mean() - cmp[ref_lw].mean()
                dep = cmp['EP_v04AE_vr'].mean() - cmp[f'EP_{ref}'].mean()
                print(f'  Delta v04AE_vr vs {ref:7s}: LW {dlw:+.3f}  EP {dep:+.0f} m')

        cmp_csv = PROC / 'drifter_compare_v04AE_vr.csv'
        cmp.to_csv(cmp_csv, index=False, float_format='%.4f')
        print(f'\nSaved comparison: {cmp_csv}')


if __name__ == '__main__':
    main()
