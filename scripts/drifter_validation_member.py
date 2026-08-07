"""Drifter validation for any ensemble member.

Replaces the family of near-identical drifter_validation_v04AE*.py scripts with
one parameterised version.

Usage:
    python drifter_validation_member.py <tag>
    python drifter_validation_member.py v04AE_vr

Reads data/processed/<tag>_surface_current.nc, seeds particles at the observed
release positions, advects with OpenDrift, and scores against the observations
over the interval each drifter was actually in the water.

Windage is 0.02 for every member by design. The July 2025 sweep found no single
optimal value, but varying it between members would confound process
attribution with a tuning difference.

Scoring is restricted to [obs_t.min(), obs_t.max()] per drifter. OpenDrift
advects every particle to the end of the forcing, which for these deployments
means 12 to 41 hours against 0.5 to 7.2 hours observed; anything that consumes
drifter_sim_*.csv for plotting must clip the same way.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from opendrift.readers.reader_netCDF_CF_generic import Reader as GenericReader
from opendrift.models.oceandrift import OceanDrift

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
WINDAGE = 0.02


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def liu_weisberg_skill(olon, olat, slon, slat):
    d = haversine_m(olon, olat, slon, slat)
    step = haversine_m(olon[:-1], olat[:-1], olon[1:], olat[1:])
    L = np.cumsum(np.concatenate([[0.0], step]))
    valid = L > 0
    if not valid.any():
        return np.nan
    return max(0.0, 1.0 - (d[valid] / L[valid]).sum() / valid.sum())


def main(tag):
    regrid = PROC / f'{tag}_surface_current.nc'
    assert regrid.exists(), f'missing {regrid}'
    print(f'=== {tag} ===')
    print(f'  reader: {regrid.name} ({regrid.stat().st_size / 1e6:.1f} MB)')

    releases = pd.read_csv(PROC / 'drifter_releases_Jul2025.csv', parse_dates=['t0'])
    tracks = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])

    reader = GenericReader(str(regrid))
    o = OceanDrift(loglevel=40)
    o.add_reader(reader)
    o.set_config('drift:horizontal_diffusivity', 0.1)
    o.set_config('drift:advection_scheme', 'runge-kutta4')
    o.set_config('general:coastline_action', 'previous')

    rv = releases[(releases['t0'] >= pd.Timestamp(reader.start_time)) &
                  (releases['t0'] <= pd.Timestamp(reader.end_time) -
                   pd.Timedelta(hours=1))].reset_index(drop=True)
    for _, r in rv.iterrows():
        o.seed_elements(lon=r['lon0'], lat=r['lat0'], time=r['t0'].to_pydatetime(),
                        number=1, z=0, wind_drift_factor=WINDAGE)
    print(f'  seeded {o.num_elements_scheduled()} of {len(releases)} releases')

    out_nc = PROC / f'opendrift_{tag}.nc'
    o.run(end_time=pd.Timestamp(reader.end_time).to_pydatetime(),
          time_step=300, time_step_output=600, outfile=str(out_nc))

    od = xr.open_dataset(out_nc)
    rows = []
    for traj in range(od.sizes['trajectory']):
        lon = od.lon.isel(trajectory=traj).values
        lat = od.lat.isel(trajectory=traj).values
        ts = pd.to_datetime(od.time.values)
        ok = ~np.isnan(lon) & ~np.isnan(lat)
        if ok.sum() < 2:
            continue
        r = rv.iloc[traj]
        rows.append(pd.DataFrame({'time': ts[ok], 'lon': lon[ok], 'lat': lat[ok],
                                  'deploy': r['deploy'], 'drifter_id': r['drifter_id']}))
    sim = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    sim.to_csv(PROC / f'drifter_sim_{tag}.csv', index=False)

    metrics = []
    for (dep, did), s in sim.groupby(['deploy', 'drifter_id']):
        s = s.sort_values('time').reset_index(drop=True)
        obs = tracks[(tracks['deploy'] == dep) &
                     (tracks['source'] == did)].sort_values('time')
        if len(obs) < 3:
            continue
        ot = obs['time'].values.astype('datetime64[s]').astype(float)
        st = s['time'].values.astype('datetime64[s]').astype(float)
        m = (st >= ot.min()) & (st <= ot.max())
        if m.sum() < 3:
            continue
        t = st[m]
        olon = np.interp(t, ot, obs['lon'].values)
        olat = np.interp(t, ot, obs['lat'].values)
        slon, slat = s['lon'].values[m], s['lat'].values[m]
        op = haversine_m(olon[:-1], olat[:-1], olon[1:], olat[1:]).sum()
        sp = haversine_m(slon[:-1], slat[:-1], slon[1:], slat[1:]).sum()
        metrics.append({'deploy': dep, 'drifter_id': did, 'n_steps': int(m.sum()),
                        'endpoint_sep_m': haversine_m(olon[-1], olat[-1],
                                                      slon[-1], slat[-1]),
                        'obs_path_m': op, 'sim_path_m': sp,
                        'path_ratio': sp / op if op > 0 else np.nan,
                        'LW_skill': liu_weisberg_skill(olon, olat, slon, slat)})
    md = pd.DataFrame(metrics)
    md.to_csv(PROC / f'drifter_metrics_{tag}.csv', index=False)
    print(f'  scored {len(md)} drifters | LW {md["LW_skill"].mean():.3f}  '
          f'EP {md["endpoint_sep_m"].mean():.0f} m  '
          f'path {md["path_ratio"].mean():.2f}')


if __name__ == '__main__':
    main(sys.argv[1])
