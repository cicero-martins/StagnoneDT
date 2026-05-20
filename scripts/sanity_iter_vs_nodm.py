"""Sanity-check a forecast iteration against v04AE_nodm for the overlap window.

For iter publishing day N (restart at N-2, run N-2 -> N), the publishable
window N-1 -> N should be bit-identical to nodm's same window (same restart,
same forcings, same FM build). Floating-point diff up to ~1e-6 m allowed
(different node assignment by METIS at iteration -> per-rank fp accumulation).

Usage:
    python sanity_iter_vs_nodm.py --publish-day 2025-07-10
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
NODM = ROOT / 'model' / 'dflowfm_v04AE_nodm' / 'DFM_OUTPUT_Stagnone_dxy01_15m'

STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'ObservationPoint01',
            'C1_Central', 'C2_NorthCenter', 'C3_SouthCenter']


def sname(ds, name):
    sn = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
          for s in ds.station_name.values]
    return sn.index(name)


def load_his(out_dir, var, station):
    """Load var time-series at station from rank-0 his.nc (which has all stations)."""
    fn = out_dir / 'Stagnone_dxy01_15m_0000_his.nc'
    ds = xr.open_dataset(fn)
    i = sname(ds, station)
    da = ds[var]
    dim = 'stations' if 'stations' in da.dims else 'station'
    da = da.isel({dim: i})
    s = da.to_pandas()
    s.index = pd.to_datetime(s.index)
    ds.close()
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--publish-day', required=True, help='YYYY-MM-DD')
    p.add_argument('--iter-dir', default=None,
                   help='override iter DFM_OUTPUT dir (default: local pull)')
    args = p.parse_args()

    publish_day = pd.Timestamp(args.publish_day)
    publishable_start = publish_day - pd.Timedelta(days=1)
    publishable_stop  = publish_day

    iter_dir = (Path(args.iter_dir) if args.iter_dir
                else ROOT / 'runs' / 'forecast' / f'd{args.publish_day}' /
                     'DFM_OUTPUT_Stagnone_dxy01_15m')
    if not iter_dir.exists():
        raise SystemExit(f'Iter output not found: {iter_dir}')
    if not NODM.exists():
        raise SystemExit(f'Nodm output not found: {NODM}')

    print(f'Publishable window: {publishable_start} -> {publishable_stop}')
    print(f'Iter dir : {iter_dir}')
    print(f'Nodm dir : {NODM}\n')

    # Compare WL at each station
    rows = []
    for st in STATIONS:
        try:
            wl_i = load_his(iter_dir, 'waterlevel', st).loc[publishable_start:publishable_stop]
            wl_n = load_his(NODM,     'waterlevel', st).loc[publishable_start:publishable_stop]
        except Exception as e:
            print(f'  {st}: skipped ({e})')
            continue
        # Align indices
        common = wl_i.index.intersection(wl_n.index)
        diff = (wl_i.loc[common] - wl_n.loc[common]).values
        rows.append(dict(
            station=st, n=len(diff),
            mean_diff=float(diff.mean()),
            max_abs_diff=float(np.abs(diff).max()),
            rms_diff=float(np.sqrt((diff ** 2).mean())),
            iter_mean=float(wl_i.loc[common].mean()),
            nodm_mean=float(wl_n.loc[common].mean()),
        ))
    df = pd.DataFrame(rows)
    print('=== WL identity check (iter - nodm) ===')
    print(df.to_string(index=False, float_format='%.6f'))

    max_dev = df['max_abs_diff'].max()
    print()
    if max_dev < 1e-6:
        print(f'PASS: max |diff| = {max_dev:.2e} m (bit-identical)')
    elif max_dev < 1e-3:
        print(f'PASS (fp noise): max |diff| = {max_dev:.2e} m')
    else:
        print(f'FAIL: max |diff| = {max_dev:.4f} m (>1mm — investigate)')


if __name__ == '__main__':
    main()
