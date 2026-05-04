"""Fetch the long Marettimo sea-level series from JRC webcritech (device 658)
to use as a multi-month statistical anchor for the BC offset.

Period: 2025-01-01 to 2026-01-20. Pulls one chunk per month (avoids API row caps),
saves the raw API CSV per month, then downsamples to 10-min and writes a single
combined CSV.

Usage:
    python scripts/download_marettimo_wl_long.py
    python scripts/download_marettimo_wl_long.py --t-min 2025-01-01 --t-max 2026-01-20

Outputs:
    data/raw/insitu/marettimo_2025_2026/marettimo_wl_YYYY-MM.csv  (raw per-month)
    data/raw/insitu/marettimo_wl_2025_2026_10min.csv              (combined, 10-min)

Notes:
- The Marettimo gauge went offline approximately 2026-01 (per the project log);
  later monthly chunks may return zero rows. The script reports per-month counts.
- Native sampling is ~5-min, so a monthly chunk has up to ~9000 rows. nRec is
  set to 20000 per chunk for headroom.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote_plus
import urllib.request
import urllib.error

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_2025_2026'
COMBINED_OUT = PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'

API_BASE = 'https://webcritech.jrc.ec.europa.eu/TAD_server/api/Data/Get/658'
N_REC = 20000
DEFAULT_T_MIN = '2025-01-01'
DEFAULT_T_MAX = '2026-01-20'


def build_url(t_min: str, t_max: str) -> str:
    return (f'{API_BASE}?tMin={quote_plus(t_min)}&tMax={quote_plus(t_max)}'
            f'&nRec={N_REC}&mode=CSV')


def fetch(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'StagnoneDT/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        print(f'  HTTP {e.code} from {url}: {e.reason}', file=sys.stderr)
        return ''
    except urllib.error.URLError as e:
        print(f'  URLError {url}: {e.reason}', file=sys.stderr)
        return ''


def parse_chunk_csv(text: str) -> pd.DataFrame:
    """Parse JRC TAD CSV: header line 'Time(UTC),Level' then rows."""
    if not text:
        return pd.DataFrame(columns=['t', 'v'])
    lines = text.strip().splitlines()
    if not lines or not lines[0].lower().startswith('time'):
        print(f'  WARNING: unexpected header: {lines[0][:80] if lines else "<empty>"}',
              file=sys.stderr)
        return pd.DataFrame(columns=['t', 'v'])
    df = pd.DataFrame([line.split(',', 1) for line in lines[1:]],
                      columns=['Time(UTC)', 'Level'])
    df['t'] = pd.to_datetime(df['Time(UTC)'], format='%d %b %Y %H:%M:%S',
                             errors='coerce')
    df['v'] = pd.to_numeric(df['Level'], errors='coerce')
    return df.dropna(subset=['t', 'v'])[['t', 'v']].sort_values('t')


def month_windows(t_min: str, t_max: str) -> list[tuple[str, str, str]]:
    """Return list of (label, t_start, t_stop) per month, half-open intervals."""
    start = pd.Timestamp(t_min)
    stop = pd.Timestamp(t_max)
    windows = []
    cur = start.replace(day=1)
    while cur < stop:
        nxt = (cur + pd.offsets.MonthBegin(1)).normalize()
        ws = max(cur, start)
        we = min(nxt, stop)
        windows.append((f'{cur.year}-{cur.month:02d}',
                        ws.strftime('%Y-%m-%d %H:%M:%S'),
                        we.strftime('%Y-%m-%d %H:%M:%S')))
        cur = nxt
    return windows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--t-min', default=DEFAULT_T_MIN)
    ap.add_argument('--t-max', default=DEFAULT_T_MAX)
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f'Marettimo WL long-period download')
    print(f'  Window: {args.t_min} to {args.t_max}')
    print(f'  Output dir: {RAW_DIR.relative_to(PROJECT_ROOT)}')
    print()

    all_dfs = []
    for label, ws, we in month_windows(args.t_min, args.t_max):
        url = build_url(ws, we)
        out_path = RAW_DIR / f'marettimo_wl_{label}.csv'
        print(f'  [{label}] {ws} -> {we}')

        if out_path.exists():
            text = out_path.read_text(encoding='utf-8')
            print(f'    cached ({len(text)} bytes)')
        else:
            text = fetch(url)
            if text:
                out_path.write_text(text, encoding='utf-8')

        df = parse_chunk_csv(text)
        if len(df):
            print(f'    rows={len(df):5d}  {df["t"].iloc[0]} -> {df["t"].iloc[-1]}'
                  f'  mean={df["v"].mean():+.4f} m  std={df["v"].std():.4f}')
        else:
            print(f'    rows=    0  (empty / sensor offline)')
        all_dfs.append(df)

    if not all_dfs or all(len(d) == 0 for d in all_dfs):
        print('\nNo data fetched. Aborting.')
        return 1

    combined = pd.concat(all_dfs, ignore_index=True).drop_duplicates('t').sort_values('t')
    combined = combined.set_index('t')

    # Resample to 10-min mean
    resampled = combined['v'].resample('10min').mean().dropna()
    resampled.name = 'wl_m'

    out = resampled.reset_index()
    out.columns = ['Time(UTC)', 'wl_m']
    COMBINED_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(COMBINED_OUT, index=False, date_format='%Y-%m-%d %H:%M:%S')

    print()
    print(f'Combined 10-min series: {len(out)} rows')
    print(f'  range: {out["Time(UTC)"].iloc[0]} -> {out["Time(UTC)"].iloc[-1]}')
    print(f'  mean:  {out["wl_m"].mean():+.4f} m')
    print(f'  std:   {out["wl_m"].std():.4f} m')
    print(f'  saved: {COMBINED_OUT.relative_to(PROJECT_ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
