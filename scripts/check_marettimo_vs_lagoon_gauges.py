"""Does the Marettimo gauge hold its datum over the year of the anchor?

The lagoon gauges (North Mouth, South Mouth, AltaVilaEst) record from April
2025 to early 2026, which covers the last level of the Marettimo record
(docs/marettimo_gauge_record_2023_2026.md). Their datums are local and differ
from Marettimo's, but each is a fixed installation, so a steady daily
difference between Marettimo and a lagoon gauge over that period indicates
that neither moved. Daily means remove the tide; the remaining difference
carries the wind and pressure set-up between the open sea and the lagoon,
which averages out over months but not over days.

Prints monthly means of each difference and the linear trend over the common
period, and writes figures/marettimo/marettimo_vs_lagoon_gauges.png.
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LAG = ROOT / 'data' / 'processed' / 'insitu_2025-26'
MAR = ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'
FIG = ROOT / 'figures' / 'marettimo'
FIG.mkdir(parents=True, exist_ok=True)
NAMES = {'BN': 'North Mouth', 'BS': 'South Mouth', 'AE': 'AltaVilaEst'}
COL = {'BN': '#eb6834', 'BS': '#1baf7a', 'AE': '#4a3aa7'}


def daily(s, min_frac=0.75):
    """Daily mean, only for days with at least min_frac of the usual count."""
    n = s.resample('1D').count()
    full = n.median()
    return s.resample('1D').mean()[n >= min_frac * full]


def main():
    m = pd.read_csv(MAR)
    m = daily(m.set_index(pd.to_datetime(m['Time(UTC)']))['wl_m'].sort_index())
    diffs = {}
    for k in NAMES:
        d = pd.read_csv(LAG / f'{k}_wl_UTC.csv', parse_dates=['time']).set_index('time')['h_m']
        d = daily(d.sort_index())
        x = (m - d).dropna()
        x = x[(x - x.rolling(15, center=True, min_periods=5).median()).abs() <= 0.15]
        diffs[k] = x

    print('Marettimo minus lagoon gauge, daily means')
    for k, x in diffs.items():
        t = (x.index - x.index[0]).days.values
        p = np.polyfit(t, x.values, 1)
        mon = x.resample('1ME').mean()
        print(f'\n{NAMES[k]}: {len(x)} days, {x.index[0].date()} to {x.index[-1].date()}, '
              f'trend {p[0] * 365:+.3f} m per year, std of daily {x.std():.3f} m, '
              f'std of monthly {mon.std():.3f} m')
        print('  ' + '  '.join(f'{i:%b%y} {v:+.3f}' for i, v in mon.items()))

    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9.5})
    fig, ax = plt.subplots(figsize=(11, 4.2))
    for k, x in diffs.items():
        a = x - x.mean()
        ax.plot(a.index, a.values, color=COL[k], lw=0.7, alpha=0.5)
        mon = a.resample('1ME').mean()
        ax.plot(mon.index - pd.Timedelta(days=15), mon.values, 'o-', color=COL[k], ms=5, lw=1.6,
                label=f'Marettimo minus {NAMES[k]}')
    ax.axhline(0, color='#1b1b1b', lw=0.8)
    ax.axvspan(pd.Timestamp('2025-07-01'), pd.Timestamp('2025-07-10'), color='#d9d6cf', zorder=0)
    ax.set_ylabel('Departure from the mean difference (m)')
    ax.set_title('Daily and monthly difference between Marettimo and the lagoon gauges, '
                 'each about its own mean', loc='left')
    ax.legend(frameon=False, fontsize=8.5, loc='lower left', ncol=3)
    ax.grid(color='#e8e7e4', lw=0.7)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    fig.savefig(FIG / 'marettimo_vs_lagoon_gauges.png', dpi=200, bbox_inches='tight')


if __name__ == '__main__':
    main()
