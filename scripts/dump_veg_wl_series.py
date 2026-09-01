"""Freeze the vegetated members' water level series into tracked CSV.

The vegetated members and the restart control were run on the server and their
map.nc set is 40 GB, so only the his.nc came back. Those five files are 27 MB of
binary and do not belong in the repository, but Table 4.1 rests on them and the
server will not always be reachable.

This writes one small CSV holding the three interior stations for every member
that lives in the his cache, so the water level table stays re-derivable on any
window from tracked data alone.

    python scripts/dump_veg_wl_series.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_wl_ensemble import read_his, HIS_CACHE, STATIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'processed' / 'wl_series_server_members.csv'


def main():
    files = sorted(HIS_CACHE.glob('*_his.nc'))
    if not files:
        print(f'nothing in {HIS_CACHE}')
        return
    rows = []
    for f in files:
        tag = f.name.replace('_his.nc', '')
        d = read_his(str(f))
        keep = ['time'] + [s for s in STATIONS if s in d.columns]
        d = d[keep].melt(id_vars='time', var_name='station', value_name='wl_m')
        d['member_tag'] = tag
        rows.append(d)
        print(f'{tag:28s} {len(d):6d} rows  '
              f'{d.time.min()} -> {d.time.max()}')
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(OUT, index=False, float_format='%.4f')
    print(f'\nSaved {OUT}  ({OUT.stat().st_size / 1024:.0f} kB)')


if __name__ == '__main__':
    main()
