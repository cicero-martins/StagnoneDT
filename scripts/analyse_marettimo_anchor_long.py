"""The Marettimo anchor of the boundary offset over 2023-2026, not 2025 alone.

The co-author found the negative departure of January and February 2025 in
Figure S3 odd and asked for a longer record. The anchor that entered the
forcing is the mean of gauge minus CMEMS analysis-forecast sea surface height
over 384 days from January 2025, +0.449 m, and the analysis-forecast product
starts in November 2024, so it cannot be extended back. The MED reanalysis
(cmems_mod_med_phy-ssh_my_4.2km_P1D-m) covers 2023 onward, but its rest state
differs, so gauge minus reanalysis is shifted by the mean of analysis-forecast
minus reanalysis over the days both exist. Since

    gauge - anfc = (gauge - reanalysis) - (anfc - reanalysis),

the shifted series sits on the level of the anchor wherever the difference
between the two products is steady, which the overlap measures.

Inputs
    data/raw/insitu/marettimo_wl_2023_2024_10min.csv, marettimo_wl_2025_2026_10min.csv
    data/raw/cmems/zos_marettimo_anchor/cmems_zos_marettimo_2025-01-01_2026-01-20.nc (anfc)
    data/raw/cmems/zos_marettimo_anchor/cmems_zos_my_marettimo_2023-01-01_2026-01-20.nc
Output
    data/processed/marettimo_anchor_long_daily.csv, and the statistics printed.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
INSITU = ROOT / 'data' / 'raw' / 'insitu'
CMEMS = ROOT / 'data' / 'raw' / 'cmems' / 'zos_marettimo_anchor'
OUT = ROOT / 'data' / 'processed' / 'marettimo_anchor_long_daily.csv'
PT = dict(lon=12.0766, lat=37.9662)        # as in compute_marettimo_offset_anchor.py
ANCHOR = 0.449


def zos(path):
    ds = xr.open_dataset(path)
    if 'longitude' in ds.coords:
        ds = ds.rename({'longitude': 'lon', 'latitude': 'lat'})
    z = ds['zos'].sel(**PT, method='nearest').to_pandas()
    z.index = pd.DatetimeIndex(z.index).normalize()
    return z


def gauge():
    parts = []
    for f in ('marettimo_wl_2023_2024_10min.csv', 'marettimo_wl_2025_2026_10min.csv'):
        d = pd.read_csv(INSITU / f)
        parts.append(d.set_index(pd.to_datetime(d['Time(UTC)']))['wl_m'])
    s = pd.concat(parts).sort_index()
    s = s[~s.index.duplicated()]
    # a day counts only with at least 18 h of record, so a daily mean is not a
    # partial tide
    cnt = s.resample('1D').count()
    d = s.resample('1D').mean()[cnt >= 108]
    d.index = pd.DatetimeIndex(d.index).normalize()
    return d


def main():
    obs = gauge()
    an = zos(CMEMS / 'cmems_zos_marettimo_2025-01-01_2026-01-20.nc')
    my = zos(CMEMS / 'cmems_zos_my_marettimo_2023-01-01_2026-01-20.nc')
    df = pd.concat([obs.rename('obs'), an.rename('anfc'), my.rename('my')], axis=1)

    ov = df[['anfc', 'my']].dropna()
    shift = float((ov.anfc - ov.my).mean())
    print(f'overlap anfc/reanalysis: {len(ov)} days, mean anfc - reanalysis {shift:+.4f} m, '
          f'std {float((ov.anfc - ov.my).std()):.4f} m')

    df['d_anfc'] = df.obs - df.anfc
    df['d_my'] = df.obs - df.my - shift
    a = df.d_anfc.dropna()
    print(f'gauge - anfc: {len(a)} days, mean {a.mean():+.4f} (anchor used {ANCHOR:+.3f})')
    m = df.d_my.dropna()
    print(f'gauge - reanalysis (shifted): {len(m)} days, {m.index[0].date()} to {m.index[-1].date()}, '
          f'mean {m.mean():+.4f}')
    for y in sorted(set(m.index.year)):
        v = m[m.index.year == y]
        print(f'  {y}: {len(v):3d} days, mean {v.mean():+.4f}')
    mon = m.resample('1ME').agg(['mean', 'count'])
    print('\nmonthly mean of the shifted series (days):')
    for t, r in mon.iterrows():
        if r['count']:
            print(f'  {t:%Y-%m}  {r["mean"]:+.3f}  ({int(r["count"])})')
    clim = m.groupby(m.index.month).mean()
    print('\ncalendar-month mean over all years:')
    print('  ' + '  '.join(f'{k:02d}:{v:+.3f}' for k, v in clim.items()))
    jf = m[m.index.month.isin([1, 2])]
    print(f'\nwithout January and February of every year: mean {m[~m.index.month.isin([1, 2])].mean():+.4f}')
    a_nojf = a[~((a.index.year == 2025) & a.index.month.isin([1, 2]))]
    print(f'anfc anchor without Jan-Feb 2025: {a_nojf.mean():+.4f} over {len(a_nojf)} days')
    df.to_csv(OUT, float_format='%.5f')
    print(f'\nsaved {OUT}')


if __name__ == '__main__':
    main()
