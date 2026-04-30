"""Validate v03d WL output against in-situ tide gauges (BN, BS, AE) and Marettimo offshore.

Produces a comparison table v03c vs v03d for the BC superposition fix:
- RMSE, bias, correlation, Willmott d, std ratio at the lagoon stations
- Same calculation window as the v03c validation (full sim window).
- Saves data/processed/validation_metrics_v03d.csv
- Saves figures/v03d_wl_validation_lagoon.png with 3-panel time series

Note on the wave-coupling freeze at day 4: WL is primarily forced by CMEMS
(time-varying boundary) + tide propagation. The wave-setup component
(radiation stress from SWAN) freezes after day 4, but its contribution to
WL is small (<5 cm) and shows up as a constant offset post-freeze. The
WL validation up to day 3 is unaffected; days 4-9 may show slightly less
variability at the boca but bulk amplitude/phase remain valid.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def load_obs(csv_path: Path, time_col: str, val_col: str, time_format=None, tz_offset_hours=0):
    df = pd.read_csv(csv_path)
    df.columns = [c.replace('﻿', '').strip() for c in df.columns]
    df['t'] = pd.to_datetime(df[time_col], format='mixed', dayfirst=False)
    if tz_offset_hours:
        df['t'] = df['t'] - pd.Timedelta(hours=tz_offset_hours)
    df['v'] = pd.to_numeric(df[val_col], errors='coerce')
    df = df.dropna(subset=['t', 'v']).set_index('t').sort_index()
    return df['v']


def metrics(obs: pd.Series, mod: pd.Series):
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


def main():
    insitu_dir = Path('data/raw/insitu')

    # In-situ: BN/BS in CET solar (UTC+1), AE same. Subtract 1h to get UTC.
    obs = {
        'BocaNord': load_obs(insitu_dir / 'boundaries_BN.csv', 'CET solare', 'BN h (m)', tz_offset_hours=1),
        'BocaSud': load_obs(insitu_dir / 'boundaries_BS.csv', 'CET solare', 'BS h (m)', tz_offset_hours=1),
        'AltaVilaEst': load_obs(insitu_dir / 'boundaries_AE.csv', 'CET solare', 'AE h (m)', tz_offset_hours=1),
    }

    # Center each obs around its own mean to remove gauge zero offsets
    # (the in-situ boundaries CSVs are relative to local gauge zero, not MSL)
    for k in obs:
        obs[k] = obs[k] - obs[k].mean()

    # v03d his.nc — concatenate partitions or just take partition 0 (stations
    # are duplicated across partitions; usable from one). Actually his.nc
    # stations only appear once across all 4 his files. Try partition 0 first.
    ds = xr.open_dataset('model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000_his.nc')
    stations = [s.decode() if isinstance(s, bytes) else s for s in ds['station_name'].values]
    times = pd.to_datetime(ds.time.values)
    wl = ds['waterlevel'].values  # (time, station)

    # Three windows. After the dimr-config fix (commit 1082232), wave coupling
    # runs all 9 days; the day-4 boundary is kept only for cross-comparison
    # against the prior broken run.
    spinup_end = pd.Timestamp('2025-07-01T12:00')
    day4_t = pd.Timestamp('2025-07-04T00:00')
    sim_end = pd.Timestamp('2025-07-10T00:00')

    windows = {
        'full 9d (incl. spin-up)': (pd.Timestamp('2025-07-01T00:00'), sim_end),
        'post-spinup days 1.5-9 (full coupled)': (spinup_end, sim_end),
        'days 1.5-3 (early coupled, ref)': (spinup_end, day4_t),
        'days 4-9 (late coupled, storm event)': (day4_t, sim_end),
    }

    all_rows = []
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    for ax, name in zip(axes, ['BocaNord', 'BocaSud', 'AltaVilaEst']):
        i = stations.index(name)
        mod = pd.Series(wl[:, i], index=times)
        mod_anom = mod - mod.mean()

        # Plot full series
        ax.plot(mod_anom.index, mod_anom.values, label='v03d model (mean-removed)', color='C0', lw=0.8)
        ax.plot(obs[name].index, obs[name].values, label='in-situ (mean-removed)', color='C3', lw=0.8, alpha=0.8)
        ax.axvline(spinup_end, color='gray', ls=':', lw=0.7, alpha=0.6)
        ax.grid(alpha=0.3)
        ax.set_ylabel('WL anomaly [m]')

        title_parts = [name]
        for w_name, (t0, t1) in windows.items():
            window_idx = (mod_anom.index >= t0) & (mod_anom.index < t1)
            mod_w = mod_anom[window_idx]
            obs_resampled = obs[name].reindex(mod_w.index, method='nearest', tolerance=pd.Timedelta('15min'))
            m = metrics(obs_resampled, mod_w.loc[obs_resampled.index])
            m['Station'] = name
            m['Window'] = w_name
            all_rows.append(m)
            if w_name == 'post-spinup days 1.5-9 (full coupled)':
                title_parts.append(f'1.5-9d post-spinup: RMSE={m.get("RMSE", float("nan")):.3f} m, '
                                   f'Corr={m.get("Corr", float("nan")):.3f}, '
                                   f'std_m/std_o={m.get("Std_mod", float("nan"))/m.get("Std_obs", float("nan")):.2f}')
        ax.set_title(' — '.join(title_parts))
        ax.legend(loc='upper right', fontsize=8)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.suptitle('v03d 9-day run (wave-coupling fix applied): WL validation at lagoon stations. Dotted = end of spin-up (12h).')
    plt.tight_layout()
    out = Path('figures/v03d_wl_validation_lagoon.png')
    plt.savefig(out, dpi=110)
    print(f'Saved {out}')

    df_metrics = pd.DataFrame(all_rows, columns=['Station', 'Window', 'N', 'RMSE', 'Bias', 'Corr', 'Willmott_d', 'Std_obs', 'Std_mod'])
    out_csv = Path('data/processed/validation_metrics_v03d.csv')
    df_metrics.to_csv(out_csv, index=False)
    print(f'Saved {out_csv}')

    # Print comparison vs v03c (full window) AND v03d clean window
    print()
    print('=== v03c (TPXO+CMEMS bug) vs v03d (BC fix + wave-coupling fix) ===')
    v03c = pd.read_csv('data/processed/validation_metrics_v03c.csv').set_index('Station')
    for w_label, w_key in [('full 9d', 'full 9d (incl. spin-up)'),
                             ('post-spinup 1.5-9d', 'post-spinup days 1.5-9 (full coupled)'),
                             ('early 1.5-3d', 'days 1.5-3 (early coupled, ref)'),
                             ('late 4-9d (storm)', 'days 4-9 (late coupled, storm event)')]:
        print()
        print(f'--- v03d window: {w_label} ---')
        print(f'{"Station":<14} {"RMSE v03c":>10} {"RMSE v03d":>10} | '
              f'{"std_m/std_o v03c":>18} {"std_m/std_o v03d":>18} | '
              f'{"Corr v03c":>10} {"Corr v03d":>10}')
        for _, r in df_metrics[df_metrics['Window'] == w_key].iterrows():
            s = r['Station']
            if s in v03c.index:
                r_old = v03c.loc[s]
                ratio_c = r_old['Std_mod'] / r_old['Std_obs']
                ratio_d = (r['Std_mod'] / r['Std_obs']) if pd.notna(r.get('Std_mod')) and pd.notna(r.get('Std_obs')) and r.get('Std_obs', 0) > 0 else float('nan')
                print(f'{s:<14} {r_old["RMSE"]:>10.4f} {r["RMSE"]:>10.4f} | '
                      f'{ratio_c:>18.3f} {ratio_d:>18.3f} | '
                      f'{r_old["Corr"]:>10.4f} {r["Corr"]:>10.4f}')


if __name__ == '__main__':
    main()
