"""Generate per-month figures comparing Marettimo in-situ WL (10-min) with
CMEMS zos (daily-mean) at the nearest cell. Highlighted months chosen for
seasonal contrast:
  - 2025-02: annual minimum (obs and δ)
  - 2025-07: run reference window (v03d)
  - 2025-08: zos summer peak (smaller δ)
  - 2026-01: obs winter peak (largest δ)

Output: figures/marettimo_offset_monthly_<YYYY-MM>.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OBS_FILE = PROJECT_ROOT / 'data' / 'raw' / 'insitu' / 'marettimo_wl_2025_2026_10min.csv'
ZOS_FILE = (PROJECT_ROOT / 'data' / 'raw' / 'cmems' / 'zos_marettimo_anchor'
            / 'cmems_zos_marettimo_2025-01-01_2026-01-20.nc')
FIG_DIR = PROJECT_ROOT / 'figures'

MARETTIMO_LON = 12.0766
MARETTIMO_LAT = 37.9662

HIGHLIGHT_MONTHS = [
    ('2025-02', 'Annual minimum (winter, obs lowest)'),
    ('2025-07', 'Reference run window (v03d)'),
    ('2025-08', 'CMEMS zos summer peak (smallest delta)'),
    ('2026-01', 'Obs winter peak (largest delta, partial)'),
]


def load_data():
    obs = pd.read_csv(OBS_FILE)
    obs['t'] = pd.to_datetime(obs['Time(UTC)'])
    obs = obs.set_index('t')['wl_m'].sort_index()

    ds = xr.open_dataset(ZOS_FILE)
    if 'longitude' in ds.coords:
        ds = ds.rename({'longitude': 'lon', 'latitude': 'lat'})
    zos = ds['zos'].sel(lon=MARETTIMO_LON, lat=MARETTIMO_LAT, method='nearest')
    zos_series = zos.to_pandas()
    zos_series.index = pd.DatetimeIndex(zos_series.index)
    return obs, zos_series, float(zos.lon), float(zos.lat)


def plot_month(month: str, label: str, obs: pd.Series,
               zos: pd.Series, zlon: float, zlat: float) -> Path:
    t0 = pd.Timestamp(month + '-01')
    t1 = (t0 + pd.offsets.MonthBegin(1))
    obs_m = obs.loc[t0:t1 - pd.Timedelta('1s')]
    zos_m = zos.loc[t0:t1 - pd.Timedelta('1s')]

    obs_mean = obs_m.mean()
    zos_mean = zos_m.mean()
    delta = obs_mean - zos_mean

    fig, ax = plt.subplots(1, 1, figsize=(13, 5.2))

    # Obs at 10-min in light blue, daily mean overlaid
    ax.plot(obs_m.index, obs_m.values, color='#3a7bd5', lw=0.6, alpha=0.55,
            label=f'Marettimo gauge 10-min (n={len(obs_m)})')
    obs_daily = obs_m.resample('1D').mean()
    ax.plot(obs_daily.index + pd.Timedelta('12h'), obs_daily.values, 'o',
            color='#1530a0', ms=4, label='Marettimo daily mean')

    # CMEMS zos daily-mean
    ax.plot(zos_m.index + pd.Timedelta('12h'), zos_m.values, 's-',
            color='#d96b0d', ms=4, lw=1.2,
            label=f'CMEMS zos @ ({zlon:.3f}, {zlat:.3f}) daily')

    # Monthly mean horizontals
    ax.axhline(obs_mean, color='#1530a0', ls='--', lw=1.0, alpha=0.7,
               label=f'mean(obs) = {obs_mean:+.3f} m')
    ax.axhline(zos_mean, color='#d96b0d', ls='--', lw=1.0, alpha=0.7,
               label=f'mean(zos) = {zos_mean:+.3f} m')

    # Delta annotation
    mid_t = t0 + (t1 - t0) / 2
    ax.annotate('', xy=(mid_t, obs_mean), xytext=(mid_t, zos_mean),
                arrowprops=dict(arrowstyle='<->', color='black', lw=1.4))
    ax.text(mid_t + pd.Timedelta('12h'), (obs_mean + zos_mean) / 2,
            f' δ = {delta:+.3f} m',
            ha='left', va='center', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor='gray', alpha=0.85))

    ax.set_xlim(t0, t1)
    ax.set_ylabel('Water level [m]')
    ax.set_title(f'Marettimo — {month}: {label}\n'
                 f'mean(obs) = {obs_mean:+.4f} m, mean(zos) = {zos_mean:+.4f} m, '
                 f'δ = obs − zos = {delta:+.4f} m')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.legend(loc='upper left', fontsize=9, ncol=2)

    fig.tight_layout()
    out = FIG_DIR / f'marettimo_offset_monthly_{month}.png'
    fig.savefig(out, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return out


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    obs, zos, zlon, zlat = load_data()
    saved = []
    for month, label in HIGHLIGHT_MONTHS:
        out = plot_month(month, label, obs, zos, zlon, zlat)
        saved.append((month, label, out))
        print(f'  saved {out.relative_to(PROJECT_ROOT)}')

    # Annual overview: top = WL series, bottom = monthly delta bars
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(14, 6.5), sharex=True,
        gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.08},
    )
    obs_d = obs.resample('1D').mean()
    ax_top.plot(obs_d.index, obs_d.values, '-', color='#3a7bd5', lw=1.1,
                label='Marettimo daily mean (obs)')
    ax_top.plot(zos.index, zos.values, '-', color='#d96b0d', lw=1.1,
                label=f'CMEMS zos daily @ ({zlon:.3f}, {zlat:.3f})')
    ax_top.axhline(0, color='gray', lw=0.5)
    ax_top.set_ylabel('Water level [m]')
    ax_top.set_title('Marettimo gauge vs CMEMS zos — 2025-01 to 2026-01')
    ax_top.grid(True, alpha=0.3)
    ax_top.legend(loc='lower left', fontsize=9)

    # Monthly delta bars (bottom) — daily delta aggregated by month
    delta_daily = (obs_d.reindex(zos.index.normalize(), method='nearest')
                   - zos.values)
    delta_daily_s = pd.Series(delta_daily, index=zos.index.normalize())
    delta_monthly = delta_daily_s.resample('1ME').mean()
    bar_x = delta_monthly.index - pd.Timedelta(days=14)
    bar_w = 22
    annual_mean = float(delta_daily_s.mean())
    bars = ax_bot.bar(bar_x, delta_monthly.values, width=bar_w,
                      color='#3aa83a', edgecolor='#1f5d1f', alpha=0.85,
                      align='center')
    ax_bot.axhline(annual_mean, color='black', ls='--', lw=1.0,
                   label=f'annual mean δ = {annual_mean:+.4f} m')
    for b, v in zip(bars, delta_monthly.values):
        ax_bot.text(b.get_x() + b.get_width() / 2, v + 0.005,
                    f'{v:+.3f}', ha='center', va='bottom', fontsize=8)
    ax_bot.set_ylabel('δ = obs − zos [m]')
    ax_bot.set_xlabel('')
    ax_bot.grid(True, alpha=0.3, axis='y')
    ax_bot.legend(loc='lower right', fontsize=9, framealpha=0.92)
    ax_bot.set_ylim(min(delta_monthly.min(), annual_mean) - 0.015,
                    max(delta_monthly.max(), annual_mean) + 0.04)
    ax_bot.xaxis.set_major_locator(mdates.MonthLocator())
    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax_bot.xaxis.get_majorticklabels(), rotation=30, ha='right')

    fig.tight_layout()
    out_annual = FIG_DIR / 'marettimo_offset_annual_2025.png'
    fig.savefig(out_annual, dpi=120, bbox_inches='tight')
    plt.close(fig)
    saved.append(('annual', 'Full 13-month overview', out_annual))
    print(f'  saved {out_annual.relative_to(PROJECT_ROOT)}')

    # Append figures section to the markdown report
    report = PROJECT_ROOT / 'docs' / 'marettimo_offset_anchor_2025.md'
    if report.exists():
        existing = report.read_text(encoding='utf-8')
        # Strip any pre-existing Figures section to keep this idempotent
        marker = '\n## Figures\n'
        if marker in existing:
            existing = existing.split(marker)[0].rstrip() + '\n'
        block = ['\n## Figures\n']
        block.append('\n### Annual overview\n\n')
        block.append(f'![annual]({Path("..") / "figures" / out_annual.name})\n\n')
        block.append('Daily-mean obs (blue) vs CMEMS zos (orange), δ overlay (green, '
                     'right axis). δ varies seasonally between ~+0.36 m (Feb) and '
                     '~+0.51 m (Jan/26).\n')
        block.append('\n### Highlighted months\n\n')
        for month, label, path in saved[:-1]:
            block.append(f'#### {month} — {label}\n\n')
            block.append(f'![{month}]({Path("..") / "figures" / path.name})\n\n')
        report.write_text(existing + ''.join(block), encoding='utf-8')
        print(f'  appended Figures section to {report.relative_to(PROJECT_ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
