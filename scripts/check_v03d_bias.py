"""Compute residual bias of v03d WL output after the +0.4208 m offset.

The validation script uses mean-removed signals (apples-to-apples amplitude/
phase). To assess whether the +0.4208 m offset itself needs adjustment, we
need the absolute-mean comparison (NO mean removal).

For each lagoon station + Marettimo offshore, computes:
  - mean_model = time-mean of model WL over the post-spinup window
  - mean_obs   = time-mean of in-situ WL over the same window
  - residual_bias = mean_model - mean_obs

A residual_bias near 0 means the +0.4208 m offset is well-calibrated.
A consistent non-zero bias would suggest adjusting the offset.
A bias that varies wildly across stations would suggest gauge-datum issues
that a single offset cannot solve.

Caveat: this assumes the gauge zero ≈ MSL. Italian gauges (ISPRA-RMN) use
IGM95/IGM2008 which can differ from MSL by tens of cm. So a residual bias
might be a gauge-datum artefact, not a true model error.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import netCDF4


def load_obs(path: Path, time_col: str, val_col: str, tz_offset_hours: int = 0):
    df = pd.read_csv(path)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]
    df['t'] = pd.to_datetime(df[time_col], format='mixed', dayfirst=False)
    if tz_offset_hours:
        df['t'] = df['t'] - pd.Timedelta(hours=tz_offset_hours)
    df['v'] = pd.to_numeric(df[val_col], errors='coerce')
    return df.dropna(subset=['t', 'v']).set_index('t').sort_index()['v']


def load_marettimo():
    df = pd.read_csv('data/raw/insitu/marettimo_wl_raw.csv')
    df['t'] = pd.to_datetime(df['Time(UTC)'], format='%d %b %Y %H:%M:%S')
    df['v'] = pd.to_numeric(df['Level'], errors='coerce')
    return df.dropna(subset=['t', 'v']).set_index('t').sort_index()['v']


def main():
    insitu = Path('data/raw/insitu')
    obs = {
        'BocaNord': load_obs(insitu / 'boundaries_BN.csv', 'CET solare', 'BN h (m)', tz_offset_hours=1),
        'BocaSud': load_obs(insitu / 'boundaries_BS.csv', 'CET solare', 'BS h (m)', tz_offset_hours=1),
        'AltaVilaEst': load_obs(insitu / 'boundaries_AE.csv', 'CET solare', 'AE h (m)', tz_offset_hours=1),
        'Marettimo (ISPRA)': load_marettimo(),
    }

    # v03d his.nc (lagoon stations)
    ds = xr.open_dataset('model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000_his.nc')
    stations = [s.decode() if isinstance(s, bytes) else s for s in ds['station_name'].values]
    times = pd.to_datetime(ds.time.values)
    wl_lag = ds['waterlevel'].values

    # v03d map.nc (Marettimo cell, partition 2 idx 1744 from earlier diagnostic)
    nc = netCDF4.Dataset('model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0002_map.nc')
    fx = nc.variables['mesh2d_face_x'][:]
    fy = nc.variables['mesh2d_face_y'][:]
    bl = nc.variables['mesh2d_flowelem_bl'][:]
    wet = bl < 0
    d2 = (fx - 12.06) ** 2 + (fy - 37.97) ** 2
    idx_mar = int(np.argmin(np.where(wet, d2, np.inf)))
    t_map = pd.to_datetime('2025-01-01') + pd.to_timedelta(nc.variables['time'][:], 's')
    wl_mar = pd.Series(nc.variables['mesh2d_s1'][:, idx_mar], index=t_map)
    nc.close()

    spinup_end = pd.Timestamp('2025-07-01T12:00')
    sim_end = pd.Timestamp('2025-07-10T00:00')

    print('=' * 90)
    print(f'{"Station":<22} {"mean_model":>12} {"mean_obs":>12} {"bias (m-o)":>12} {"to-zero residual":>20}')
    print('=' * 90)
    biases = []
    for name in ['BocaNord', 'BocaSud', 'AltaVilaEst']:
        i = stations.index(name)
        mod = pd.Series(wl_lag[:, i], index=times)
        mod_post = mod[(mod.index >= spinup_end) & (mod.index < sim_end)]
        obs_resampled = obs[name].reindex(mod_post.index, method='nearest', tolerance=pd.Timedelta('15min'))
        common = pd.concat([mod_post.rename('mod'), obs_resampled.rename('obs')], axis=1).dropna()
        m_mean = common['mod'].mean()
        o_mean = common['obs'].mean()
        bias = m_mean - o_mean
        biases.append(bias)
        print(f'{name:<22} {m_mean:>+12.4f} {o_mean:>+12.4f} {bias:>+12.4f} {-bias:>+20.4f}')

    # Marettimo: extract model WL at the Marettimo cell, compare absolute to in-situ
    mod_post_mar = wl_mar[(wl_mar.index >= spinup_end) & (wl_mar.index < sim_end)]
    obs_mar_resampled = obs['Marettimo (ISPRA)'].reindex(mod_post_mar.index, method='nearest', tolerance=pd.Timedelta('30min'))
    common_mar = pd.concat([mod_post_mar.rename('mod'), obs_mar_resampled.rename('obs')], axis=1).dropna()
    m_mean = common_mar['mod'].mean()
    o_mean = common_mar['obs'].mean()
    bias = m_mean - o_mean
    biases.append(bias)
    print(f'{"Marettimo (ISPRA)":<22} {m_mean:>+12.4f} {o_mean:>+12.4f} {bias:>+12.4f} {-bias:>+20.4f}')
    print('=' * 90)

    # Summary
    print()
    print(f'Mean bias across 4 stations: {np.mean(biases):+.4f} m')
    print(f'Std  bias across 4 stations: {np.std(biases):.4f} m')
    print(f'Range: [{min(biases):+.4f}, {max(biases):+.4f}]')
    print()
    print('Interpretation:')
    print(f'  - Current offset: +0.4208 m (set in v01 from BN/BS/AE bias only)')
    print(f'  - Residual bias mean = {np.mean(biases):+.4f} m')
    print(f'  - To zero out the residual: +0.4208 + ({-np.mean(biases):+.4f}) = +{0.4208 + (-np.mean(biases)):.4f} m')


if __name__ == '__main__':
    main()
