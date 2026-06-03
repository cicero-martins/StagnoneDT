"""Quick validation of smoke nodm Jul 1-10 vs in-situ AE/BN/BS.

Replicates the May 19 validation per [[v04AE_d10d12_first_continuation_run]]:
  - Drop spinup day (Jul 1)
  - Resample 10-min model vs 10-min in-situ
  - Compute bias, RMSE, RMSE_anom (anomaly), corr (raw + tide-free)

Output: data/processed/validate_smoke_v04AE_nodm.csv + brief print.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
HIS = ROOT / 'model' / 'dflowfm_v04AE_nodm' / 'DFM_OUTPUT_Stagnone_dxy01_15m' / 'Stagnone_dxy01_15m_0000_his.nc'

# In-situ files (10-min interval, UTC)
INSITU = {
    'AltaVilaEst': ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'AE_wl_UTC.csv',
    'BocaNord':    ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BN_wl_UTC.csv',
    'BocaSud':     ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BS_wl_UTC.csv',
}

# Drop spinup day
T_VALID_START = pd.Timestamp('2025-07-02 00:00')
T_VALID_END   = pd.Timestamp('2025-07-10 00:00')


def detide(series, period_hours=12.42):
    """Crude detide via running-mean of 25h (=2*M2 period)."""
    win = 25 * 6  # 25h in 10-min steps
    return series - series.rolling(win, center=True, min_periods=1).mean()


def main():
    ds = xr.open_dataset(HIS)
    stn_dim = 'station'
    names_arr = [str(s.values).replace("b'", "").replace("'", "").replace("np.bytes_(", "").replace(")", "").strip()
                 for s in ds.station_name]
    print(f'Stations in his.nc: {names_arr}')

    rows = []
    for model_stn, insitu_path in INSITU.items():
        if model_stn not in names_arr:
            print(f'  SKIP {model_stn}: not in model his.nc')
            continue
        idx = names_arr.index(model_stn)
        mod_wl = ds.waterlevel.isel({stn_dim: idx}).to_pandas()
        mod_wl.index = pd.DatetimeIndex(mod_wl.index)
        # Slice validation window
        mod_wl = mod_wl[T_VALID_START:T_VALID_END]

        if not insitu_path.exists():
            print(f'  SKIP {model_stn}: in-situ file {insitu_path.name} missing')
            continue
        obs = pd.read_csv(insitu_path)
        tcol = [c for c in obs.columns if 'time' in c.lower()][0]
        wlcol = [c for c in obs.columns if c.lower() in ('h_m','wl','wl_m','waterlevel','h') or 'level' in c.lower()][0]
        obs[tcol] = pd.to_datetime(obs[tcol])
        obs = obs.set_index(tcol)[wlcol]
        obs = obs[T_VALID_START:T_VALID_END]

        # Align on common time index (10-min)
        common = mod_wl.resample('10min').mean().dropna()
        obs_r = obs.resample('10min').mean().dropna()
        idx_join = common.index.intersection(obs_r.index)
        if len(idx_join) < 100:
            print(f'  SKIP {model_stn}: only {len(idx_join)} matched timesteps')
            continue
        m = common.loc[idx_join]
        o = obs_r.loc[idx_join]

        # Metrics
        bias = (m - o).mean()
        rmse = np.sqrt(((m - o) ** 2).mean())
        corr_raw = m.corr(o)
        m_anom = detide(m)
        o_anom = detide(o)
        rmse_anom = np.sqrt(((m_anom - o_anom) ** 2).mean())
        corr_anom = m_anom.corr(o_anom)

        rows.append({
            'station': model_stn,
            'n': len(idx_join),
            'bias_mm': bias * 1000,
            'rmse_mm': rmse * 1000,
            'rmse_anom_mm': rmse_anom * 1000,
            'corr_raw': corr_raw,
            'corr_anom': corr_anom,
            'obs_range_m': float(o.max() - o.min()),
            'mod_range_m': float(m.max() - m.min()),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        print('No valid stations matched.')
        return
    print('\n=== WL validation smoke v04AE_nodm Jul 2-10 (drop spinup day) ===')
    print(df.to_string(index=False, float_format='%+.3f'))

    out_csv = ROOT / 'data' / 'processed' / 'validate_smoke_v04AE_nodm.csv'
    df.to_csv(out_csv, index=False)
    print(f'\nCSV: {out_csv}')

    # Compare with May 19 baseline (per memory v04AE_d10d12_first_continuation_run):
    # | Station | bias | RMSE | RMSE_anom | corr (sem maré) | corr (com maré)
    # | AE  | +36 mm | 98 mm | 91 mm | +0.08 | +0.27
    # | BN  | -15 mm | 73 mm | 71 mm | -0.01 | +0.77
    # | BS  | -56 mm | 91 mm | 71 mm | +0.27 | +0.71
    # NOTE: May 19 metrics were for d10d12 (Jul 10-12 continuation), not Jul 1-10 nodm.
    # For Jul 1-10 nodm baseline see commit fc6e268 (Marettimo offshore WL preserved)
    print('\nBaseline comparison (v04AE_d10d12 Jul 10-12 was Jul 1-10 NOT validated this way directly):')
    print('  This run is Jul 2-10 nodm cold-start; expect similar magnitudes')


if __name__ == '__main__':
    main()
