"""Fetch sea-level time series for the Marettimo tide gauge (ISPRA, device 658)
from the JRC webcritech API for a given date range.

The gauge is at 37.966238N, 12.076653E and falls inside the FM mesh used by
the StagnoneDT project, so its data can be compared directly against model
output at the nearest mesh node. Wave data is NOT available at this station.

Endpoint: https://webcritech.jrc.ec.europa.eu/TAD_server/api/Data/Get/658
Query params: tMin, tMax (YYYY-MM-DD HH:MM:SS), nRec, mode=CSV

Usage:
    python scripts/download_marettimo_wl.py  # default: 2025-07-01 to 2025-07-10
    python scripts/download_marettimo_wl.py --t-min "2025-08-01 00:00:00" \\
        --t-max "2025-08-10 00:00:00"

Output: data/raw/insitu/marettimo_wl_raw.csv (appended/overwritten).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote_plus
import urllib.request
import urllib.error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_raw.csv'

API_BASE = 'https://webcritech.jrc.ec.europa.eu/TAD_server/api/Data/Get/658'
DEFAULT_T_MIN = '2025-07-01 00:00:00'
DEFAULT_T_MAX = '2025-07-10 00:00:00'
# API returns ~300 rows/day for ~5-min avg resolution; 20000 covers ~60 days.
DEFAULT_N_REC = 20000


def build_url(t_min: str, t_max: str, n_rec: int) -> str:
    return (f'{API_BASE}?tMin={quote_plus(t_min)}&tMax={quote_plus(t_max)}'
            f'&nRec={n_rec}&mode=CSV')


def fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'StagnoneDT/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code} from {url}: {e.reason}')
    except urllib.error.URLError as e:
        sys.exit(f'Could not reach {url}: {e.reason}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--t-min', default=DEFAULT_T_MIN,
                    help=f'Start datetime UTC (default: {DEFAULT_T_MIN})')
    ap.add_argument('--t-max', default=DEFAULT_T_MAX,
                    help=f'End datetime UTC (default: {DEFAULT_T_MAX})')
    ap.add_argument('--n-rec', type=int, default=DEFAULT_N_REC,
                    help=f'Max records (default: {DEFAULT_N_REC})')
    ap.add_argument('--out', default=str(OUT_PATH),
                    help=f'Output CSV (default: {OUT_PATH.relative_to(PROJECT_ROOT)})')
    args = ap.parse_args()

    url = build_url(args.t_min, args.t_max, args.n_rec)
    print(f'Fetching: {url}')
    text = fetch(url)

    lines = text.strip().splitlines()
    if not lines or not lines[0].lower().startswith('time'):
        sys.exit(f'Unexpected response (no CSV header):\n{text[:400]}')

    n_rows = len(lines) - 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print(f'Wrote {n_rows} rows to {out.relative_to(PROJECT_ROOT)}')

    if n_rows >= args.n_rec - 1:
        print(f'  [warn] Row count == nRec; response may be truncated. '
              f'Increase --n-rec or split into smaller windows.')

    # Quick sanity: first and last timestamp
    first = lines[1].split(',', 1)[0] if n_rows else '<empty>'
    last = lines[-1].split(',', 1)[0] if n_rows else '<empty>'
    print(f'  first: {first}')
    print(f'  last : {last}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
