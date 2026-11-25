"""The Marettimo gauge record of 2023-2026 against CMEMS, with its breaks.

Figures for docs/marettimo_gauge_record_2023_2026.md. The anchor of the
boundary offset is the mean of gauge minus CMEMS analysis-forecast sea surface
height over January 2025 to January 2026; this script shows the whole record
the gauge offers, so that the level changes behind that choice can be seen.

(1) Overview: (a) range of the raw samples per day, which shows the clipped
    and spiked periods; (b) daily gauge mean against the two CMEMS products
    raised by the anchor; (c) gauge minus CMEMS, daily and monthly, with the
    levels of a piecewise-constant fit and the events found in the record.
(2) Zooms on the three breaks.

Inputs: data/raw/insitu/marettimo_raw_2023_2026.parquet (all raw samples,
written by the inspection of the download) and
data/processed/marettimo_anchor_long_daily.csv (analyse_marettimo_anchor_long.py).
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_raw_2023_2026.parquet'
DAILY = ROOT / 'data' / 'processed' / 'marettimo_anchor_long_daily.csv'
FIG = ROOT / 'figures' / 'marettimo'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE, INK, MUTED, GRID = '#ffffff', '#1b1b1b', '#6b6b6b', '#e8e7e4'
C_GAUGE, C_ANFC, C_MY, C_FIT = '#1b1b1b', '#4a3aa7', '#1baf7a', '#eb6834'
ANCHOR = 0.449
EVENTS = [   # (start, end, label)
    ('2023-08-01', '2023-09-12', 'sensor held at -1.000 m'),
    ('2024-09-21', '2024-10-02', 'gap of 54 h, spike to +8 m on 1 Oct'),
    ('2024-12-10', '2024-12-19', 'gaps of 9 to 178 h'),
    ('2025-01-01', '2025-01-02', 'sampling 15 s to 90 s'),
]
mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9.5})


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'):
        ax.spines[sp].set_color('#c9c7c1')


def segments(x, n_cuts=4, margin=20):
    """Binary segmentation of a piecewise-constant fit, largest gain first."""
    v = x.values
    segs, cuts = [(0, len(v))], []
    for _ in range(n_cuts):
        best = None
        for a, b in segs:
            w = v[a:b]
            if len(w) < 2 * margin:
                continue
            tot = ((w - w.mean()) ** 2).sum()
            for k in range(margin, len(w) - margin):
                l, r = w[:k], w[k:]
                g = tot - ((l - l.mean()) ** 2).sum() - ((r - r.mean()) ** 2).sum()
                if best is None or g > best[0]:
                    best = (g, a, b, a + k)
        g, a, b, k = best
        segs.remove((a, b)); segs += [(a, k), (k, b)]
        cuts.append((x.index[k], g))
    segs.sort()
    return [(x.index[a], x.index[b - 1], float(v[a:b].mean())) for a, b in segs], cuts


def mark_events(ax):
    for s, e, _ in EVENTS:
        ax.axvspan(pd.Timestamp(s), pd.Timestamp(e), color='#f3c7b5', alpha=0.55, lw=0, zorder=1)


def main():
    raw = pd.read_parquet(RAW)['wl_m']
    d = pd.read_csv(DAILY, index_col=0, parse_dates=True)
    shift = float((d.anfc - d.my).dropna().mean())

    rng = raw.resample('1D').agg(['min', 'max', 'mean'])
    diff = d['d_my'].dropna()
    diff = diff[(diff - diff.rolling(15, center=True, min_periods=5).median()).abs() <= 0.3]
    post = diff.loc['2023-10-01':]
    levels, cuts = segments(post)

    fig, axes = plt.subplots(3, 1, figsize=(12.5, 11.2), sharex=True,
                             gridspec_kw=dict(height_ratios=[0.8, 1, 1.1], hspace=0.16))
    ax = axes[0]
    ax.fill_between(rng.index, rng['min'], rng['max'], color='#9b9893', lw=0, step='mid')
    ax.set_ylim(-2.2, 1.6)
    ax.set_ylabel('Raw samples,\ndaily range (m)', color=MUTED)
    ax.set_title('(a) Range of the raw gauge samples per day, clipped at the axis limits',
                 loc='left', color=INK)
    mark_events(ax); style(ax)

    ax = axes[1]
    ax.plot(d.index, d.obs, color=C_GAUGE, lw=1.0, label='Gauge, daily mean')
    ax.plot(d.index, d.my + shift + ANCHOR, color=C_MY, lw=1.0,
            label=f'Reanalysis + {shift:.3f} + {ANCHOR:.3f} m')
    ax.plot(d.index, d.anfc + ANCHOR, color=C_ANFC, lw=1.0, label=f'Analysis-forecast + {ANCHOR:.3f} m')
    ax.set_ylim(-0.7, 0.5)
    ax.set_ylabel('Water level (m)', color=MUTED)
    ax.set_title('(b) Gauge against CMEMS raised by the anchor', loc='left', color=INK)
    ax.legend(loc='lower left', fontsize=8.5, frameon=False, ncol=3)
    mark_events(ax); style(ax)

    ax = axes[2]
    ax.plot(diff.index, diff.values, color='#9b9893', lw=0.8, label='Daily, reanalysis')
    an = d['d_anfc'].dropna()
    ax.plot(an.index, an.values, color=C_ANFC, lw=0.8, alpha=0.8, label='Daily, analysis-forecast')
    mon = diff.resample('1ME').mean()
    ax.plot(mon.index - pd.Timedelta(days=15), mon.values, 'o', color=INK, ms=4.5, label='Monthly mean')
    for s, e, m in levels:
        ax.plot([s, e], [m, m], color=C_FIT, lw=2.4, solid_capstyle='butt', zorder=5)
        ax.text(s + (e - s) / 2, m + 0.03, f'{m:+.3f}', color=C_FIT, ha='center', fontsize=8.5,
                zorder=6, bbox=dict(fc='white', ec='none', alpha=0.7, pad=0.5))
    ax.axhline(ANCHOR, color=C_ANFC, lw=1.4, ls='--', label=f'Anchor used, {ANCHOR:+.3f} m')
    ax.axvspan(pd.Timestamp('2025-07-01'), pd.Timestamp('2025-07-10'), color='#d9d6cf', zorder=0)
    ax.text(pd.Timestamp('2025-07-05'), 0.62, 'simulated\nwindow', ha='center', va='top', fontsize=8,
            color=MUTED)
    ax.set_ylim(-0.35, 0.65)
    ax.set_ylabel('Gauge minus CMEMS (m)', color=MUTED)
    ax.set_title('(c) Gauge minus CMEMS on the level of the analysis-forecast product, with the '
                 'levels of a piecewise-constant fit from October 2023', loc='left', color=INK)
    ax.legend(loc='lower right', fontsize=8.5, frameon=False, ncol=2)
    mark_events(ax); style(ax)
    ax.xaxis.set_major_locator(mpl.dates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mpl.dates.DateFormatter('%b\n%Y'))
    for k, (s, e, lab) in enumerate(EVENTS):
        axes[0].text(pd.Timestamp(s) + (pd.Timestamp(e) - pd.Timestamp(s)) / 2, 1.5, str(k + 1),
                     fontsize=9, color='#a8471f', ha='center', va='top', fontweight='bold',
                     bbox=dict(fc='white', ec='#a8471f', boxstyle='circle,pad=0.2', lw=0.8))
    fig.savefig(FIG / 'marettimo_gauge_record_2023_2026.png', dpi=200, bbox_inches='tight',
                facecolor=SURFACE)
    plt.close(fig)

    zooms = [('2023-07-15', '2023-10-31', '(a) August to October 2023'),
             ('2024-09-01', '2024-11-15', '(b) September to November 2024'),
             ('2024-12-01', '2025-04-15', '(c) December 2024 to April 2025')]
    fig, axes = plt.subplots(3, 2, figsize=(12.5, 10), gridspec_kw=dict(hspace=0.42, wspace=0.22))
    for row, (s, e, title) in enumerate(zooms):
        r = raw.loc[s:e].resample('1h').mean()
        ax = axes[row, 0]
        ax.plot(r.index, r.values, color=C_GAUGE, lw=0.6)
        ax.set_ylim(-1.3, 0.9)
        ax.set_title(f'{title}, gauge hourly mean', loc='left', color=INK, fontsize=10)
        ax.set_ylabel('m', color=MUTED)
        mark_events(ax); style(ax)
        ax = axes[row, 1]
        ax.plot(diff.loc[s:e].index, diff.loc[s:e].values, color='#9b9893', lw=1.0, label='reanalysis')
        if an.loc[s:e].size:
            ax.plot(an.loc[s:e].index, an.loc[s:e].values, color=C_ANFC, lw=1.0, label='analysis-forecast')
        ax.axhline(ANCHOR, color=C_ANFC, lw=1.2, ls='--')
        ax.set_title(f'{title}, gauge minus CMEMS, daily', loc='left', color=INK, fontsize=10)
        ax.set_ylabel('m', color=MUTED)
        ax.legend(fontsize=8, frameon=False, loc='lower left')
        mark_events(ax); style(ax)
        for a in axes[row]:
            a.set_xlim(pd.Timestamp(s), pd.Timestamp(e))
            span = (pd.Timestamp(e) - pd.Timestamp(s)).days
            a.xaxis.set_major_locator(mpl.dates.MonthLocator() if span > 100
                                      else mpl.dates.WeekdayLocator(byweekday=0, interval=2))
            a.xaxis.set_major_formatter(mpl.dates.DateFormatter('%b %Y' if span > 100 else '%d %b'))
    fig.savefig(FIG / 'marettimo_gauge_breaks.png', dpi=200, bbox_inches='tight', facecolor=SURFACE)
    plt.close(fig)

    print('piecewise levels from October 2023:')
    for s, e, m in levels:
        print(f'  {s.date()} to {e.date()}  {m:+.3f}')
    print('cuts in order of gain:', [(str(t.date()), round(g, 3)) for t, g in cuts])
    for lab, s, e in (('Jan 2025 - Jan 2026, used', '2025-01-01', '2026-01-20'),
                      ('Mar 2025 - end of record', '2025-03-01', '2026-03-01'),
                      ('11 Feb 2025 - end of record', '2025-02-11', '2026-03-01'),
                      ('1-10 Jul 2025', '2025-07-01', '2025-07-10')):
        v = an.loc[s:e]
        print(f'{lab:30s} {v.mean():+.4f}  ({len(v)} days, {v.index[0].date()} to {v.index[-1].date()})')


if __name__ == '__main__':
    main()
