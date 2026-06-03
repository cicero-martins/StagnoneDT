"""Validate 4 continuation runs vs in-situ AE/BN/BS.

Inputs (his.nc files rsynced from simit):
  data/processed/continuation_validation/
    d2025-07-10_his.nc         (N-3 nodm: Jul 7 -> Jul 10)
    d2025-07-10_n2_his.nc      (N-2 nodm: Jul 8 -> Jul 10)
    d2025-07-11_n2_his.nc      (N-2 chained: Jul 9 -> Jul 11, rst from d2025-07-10_n2)
    d2025-07-12_n2_his.nc      (N-2 chained: Jul 10 -> Jul 12, rst from d2025-07-11_n2)

Validation window per run: drop first 12h (transient), use second day for N-2 runs
(per [[restart_chain_n_minus_2_workflow]] convention).

Outputs:
  - data/processed/continuation_validation/metrics.csv
  - stdout: nice table per station per run
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
VAL_DIR = ROOT / 'data' / 'processed' / 'continuation_validation'
INSITU = {
    'AltaVilaEst': ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'AE_wl_UTC.csv',
    'BocaNord':    ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BN_wl_UTC.csv',
    'BocaSud':     ROOT / 'data' / 'processed' / 'insitu_2025-26' / 'BS_wl_UTC.csv',
}

RUNS = [
    ('N3_nodm',  'd2025-07-10_his.nc',    pd.Timestamp('2025-07-07'), pd.Timestamp('2025-07-10')),
    ('N2_nodm',  'd2025-07-10_n2_his.nc', pd.Timestamp('2025-07-08'), pd.Timestamp('2025-07-10')),
    ('N2_chain', 'd2025-07-11_n2_his.nc', pd.Timestamp('2025-07-09'), pd.Timestamp('2025-07-11')),
    ('N2_chain', 'd2025-07-12_n2_his.nc', pd.Timestamp('2025-07-10'), pd.Timestamp('2025-07-12')),
]

SPINUP_HOURS = 12  # discard first 12h of each window


def detide(s, win_steps=25*6):
    return s - s.rolling(win_steps, center=True, min_periods=1).mean()


def station_names(ds):
    arr = ds.station_name.values
    out = []
    for s in arr:
        if isinstance(s, np.ndarray) or isinstance(s, list):
            # char array
            out.append(b''.join([c if isinstance(c, bytes) else c.encode() for c in s]).decode().strip())
        else:
            out.append(str(s).replace("b'", "").replace("'", "").strip())
    return out


def main():
    rows = []
    for run_label, fname, t0, t1 in RUNS:
        nc = VAL_DIR / fname
        if not nc.exists():
            print(f'[skip] {fname} not found')
            continue
        ds = xr.open_dataset(nc)
        names = station_names(ds)
        t_valid_start = t0 + pd.Timedelta(hours=SPINUP_HOURS)
        t_valid_end = t1

        for stn, csv_path in INSITU.items():
            if stn not in names:
                continue
            idx = names.index(stn)
            mod = ds.waterlevel.isel(station=idx).to_pandas()
            mod.index = pd.DatetimeIndex(mod.index)
            mod = mod[t_valid_start:t_valid_end]

            obs = pd.read_csv(csv_path)
            tcol = [c for c in obs.columns if 'time' in c.lower()][0]
            wlcol = [c for c in obs.columns if c.lower() in ('h_m', 'wl', 'wl_m', 'waterlevel', 'h') or 'level' in c.lower()][0]
            obs[tcol] = pd.to_datetime(obs[tcol])
            obs = obs.set_index(tcol)[wlcol]
            obs = obs[t_valid_start:t_valid_end]

            m10 = mod.resample('10min').mean().dropna()
            o10 = obs.resample('10min').mean().dropna()
            common = m10.index.intersection(o10.index)
            if len(common) < 60:
                print(f'  SKIP {fname} {stn}: only {len(common)} matched timesteps')
                continue
            m = m10.loc[common]
            o = o10.loc[common]

            bias = (m - o).mean()
            rmse = np.sqrt(((m - o) ** 2).mean())
            corr_raw = m.corr(o)
            ma = detide(m)
            oa = detide(o)
            rmse_anom = np.sqrt(((ma - oa) ** 2).mean())
            corr_anom = ma.corr(oa)

            rows.append({
                'run': fname.replace('_his.nc', ''),
                'kind': run_label,
                'station': stn,
                'n_steps': len(common),
                'bias_mm': bias * 1000,
                'rmse_mm': rmse * 1000,
                'rmse_anom_mm': rmse_anom * 1000,
                'corr_raw': corr_raw,
                'corr_anom': corr_anom,
            })
        ds.close()

    df = pd.DataFrame(rows)
    if df.empty:
        print('No matching stations. Check his.nc structure + insitu paths.')
        return
    print('\n=== Continuation chain validation (drop first 12h spinup) ===')
    print(df.to_string(index=False, float_format='%+.3f'))

    out = VAL_DIR / 'metrics.csv'
    df.to_csv(out, index=False, float_format='%.4f')
    print(f'\nCSV: {out}')


if __name__ == '__main__':
    main()
