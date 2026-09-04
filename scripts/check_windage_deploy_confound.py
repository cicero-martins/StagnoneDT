"""Are deployment position and wind speed confounded?

The optimal windage found in the 2026-05 sweep varies with where the drifter was
released, the south-edge deployments preferring 0.005 where the interior prefers
0.02. A later speculation is that it varies with wind speed instead, the wind
having risen from about 5 to 8 m/s on the afternoon of 9 July.

Those two explanations are separable only if the southern deployments did not
happen to fall in the windy hours. This checks that, and nothing else. It fits
no windage and tests no mechanism.

The wind is AltaVilaEst, which is the right series to use: the eight ensemble
members carry the AE-only blend, and with a single station inside the inner
radius the blended field is spatially uniform over the lagoon.

    python scripts/check_windage_deploy_confound.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
sys.path.insert(0, str(ROOT / 'scripts'))

# Lagoon centre, from the wind-blending notebook. Used only to say how far south
# each release sat, so "south edge" is a number rather than an impression.
LAT_CENTRE = 37.867

# From the 2026-05 sweep: the deployments whose drifters wanted a low windage.
LOW_WINDAGE = {11, 12}


def load():
    rel = pd.read_csv(PROC / 'drifter_releases_Jul2025.csv', parse_dates=['t0'])
    trk = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    wind = pd.read_csv(PROC / 'insitu_2025-26' / 'AE_wind_UTC.csv',
                       parse_dates=['time'])
    return rel, trk, wind


def main():
    rel, trk, wind = load()

    # The window each deployment was actually in the water.
    span = trk.groupby('deploy')['time'].agg(['min', 'max'])
    first = rel.groupby('deploy').agg(t0=('t0', 'min'),
                                      lat=('lat0', 'mean'),
                                      lon=('lon0', 'mean'),
                                      n=('drifter_id', 'size'))
    d = first.join(span).sort_values('t0')

    w = wind.set_index('time')['speed'].sort_index()
    rows = []
    for dep, r in d.iterrows():
        seg = w.loc[r['min']:r['max']]
        rows.append({
            'deploy': dep,
            'inicio': r['t0'],
            'h': (r['max'] - r['min']).total_seconds() / 3600,
            'n': int(r['n']),
            'lat': r['lat'],
            'dist_S_km': (LAT_CENTRE - r['lat']) * 111.0,
            'vento_med': seg.mean(),
            'vento_max': seg.max(),
        })
    t = pd.DataFrame(rows)

    print(f'{len(t)} deployments, vento de AltaVilaEst na janela de cada um\n')
    print(f"{'dep':>4s} {'inicio (UTC)':16s} {'h':>5s} {'n':>3s} "
          f"{'sul do centro':>13s} {'vento med':>10s} {'max':>6s}")
    print('-' * 68)
    for _, r in t.iterrows():
        mark = '  <- windage baixo' if r['deploy'] in LOW_WINDAGE else ''
        print(f"{int(r['deploy']):4d} {r['inicio']:%Y-%m-%d %H:%M} "
              f"{r['h']:5.2f} {int(r['n']):3d} {r['dist_S_km']:11.2f} km "
              f"{r['vento_med']:10.2f} {r['vento_max']:6.2f}{mark}")

    low = t[t['deploy'].isin(LOW_WINDAGE)]
    rest = t[~t['deploy'].isin(LOW_WINDAGE)]
    print(f"\n{'':22s}{'vento medio':>12s}{'sul do centro':>15s}")
    print(f"  windage baixo (11,12) {low['vento_med'].mean():12.2f}"
          f"{low['dist_S_km'].mean():12.2f} km")
    print(f"  os outros            {rest['vento_med'].mean():12.2f}"
          f"{rest['dist_S_km'].mean():12.2f} km")

    print('\n=== o vento do dia 9 ===')
    d9 = w.loc['2025-07-09']
    if len(d9):
        manha = d9.between_time('06:00', '12:00')
        tarde = d9.between_time('12:00', '19:00')
        print(f'  manha  06-12  media {manha.mean():.2f}  max {manha.max():.2f}')
        print(f'  tarde  12-19  media {tarde.mean():.2f}  max {tarde.max():.2f}')
    for dia in sorted(set(t['inicio'].dt.date)):
        seg = w.loc[str(dia)]
        print(f'  {dia}  media {seg.mean():.2f}  max {seg.max():.2f}')

    print('\n=== confundimento entre posicao e vento ===')
    r = np.corrcoef(t['dist_S_km'], t['vento_med'])[0, 1]
    print(f'  correlacao entre "quao ao sul" e "vento medio" -> {r:+.3f}')
    print('  |r| alto significaria posicao e vento confundidos e inseparaveis')

    # The sweep itself, rather than the summary of it: which windage maximises
    # mean skill for each deployment, and does that track the wind?
    sw = pd.read_csv(PROC / 'drifter_windage_sweep_v04.csv')
    per = (sw.groupby(['deploy', 'windage'])['LW_skill'].mean()
             .rename('skill').reset_index())
    best = (per.loc[per.groupby('deploy')['skill'].idxmax()]
              .set_index('deploy')[['windage', 'skill']])
    t = t.join(best, on='deploy')

    print('\n=== windage otimo por deploy, do sweep ===')
    print(f"{'dep':>4s} {'w otimo':>8s} {'skill':>7s} {'vento med':>10s} "
          f"{'sul':>9s}")
    print('-' * 45)
    for _, r_ in t.sort_values('vento_med', ascending=False).iterrows():
        print(f"{int(r_['deploy']):4d} {r_['windage']:8.3f} {r_['skill']:7.3f} "
              f"{r_['vento_med']:10.2f} {r_['dist_S_km']:7.2f} km")

    ok = t.dropna(subset=['windage'])
    print(f'\n  correlacao windage otimo x vento medio -> '
          f'{np.corrcoef(ok["vento_med"], ok["windage"])[0, 1]:+.3f}')
    print(f'  correlacao windage otimo x "quao ao sul" -> '
          f'{np.corrcoef(ok["dist_S_km"], ok["windage"])[0, 1]:+.3f}')
    print('  negativo no primeiro apoiaria a hipotese do vento')

    t.to_csv(PROC / 'windage_deploy_confound.csv', index=False,
             float_format='%.3f')
    print(f"\nSaved {PROC / 'windage_deploy_confound.csv'}")


if __name__ == '__main__':
    main()
