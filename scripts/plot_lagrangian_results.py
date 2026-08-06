"""Figure for Section 4.2: the Lagrangian result, shown rather than described.

(a) Liu-Weisberg skill for every drifter under every member. The point of the
    strip is that the members overlap heavily at drifter level, so the ordering
    of the means rests on paired comparison rather than on separated groups.
(b) The wave contrast deployment by deployment, which is the question a reader
    will ask about a mean effect of -0.035: does it hold, or is it a couple of
    deployments dragging the average? Twenty-eight of thirty-five drifters and
    ten of twelve deployments are worse with waves.
(c) Transport rate. Mean speed along each member's own track against the
    observed 0.143 m/s, which is the quantity that sets path length.

vr is drawn in colour and the other four in grey throughout, because the
finding is that one member separates from a cluster of four.

Output: figures/lagrangian_results.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

SURFACE = '#ffffff'
INK = '#1b1b1b'
MUTED = '#6b6b6b'
GRID = '#e8e7e4'
BASE = '#9a9892'
ACCENT = '#4a3aa7'
WORSE = '#eb6834'
BETTER = '#1baf7a'

MEMBERS = [('nowaves', 'v04AE_nowaves', 'no waves'),
           ('nodm', 'v04AE_nodm', 'waves'),
           ('nodm_vr', 'v04AE_nodm_vr', '+ roughness'),
           ('bl', 'v04AE', '+ morph.'),
           ('vr', 'v04AE_vr', 'full')]


def hav(lo1, la1, lo2, la2):
    R = 6371000.0
    p1, p2 = np.radians(la1), np.radians(la2)
    dp, dl = np.radians(la2 - la1), np.radians(lo2 - lo1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def track_speeds(obs):
    vo = []
    for _, g in obs.groupby(['deploy', 'source']):
        g = g.sort_values('time')
        d = hav(g['lon'].values[:-1], g['lat'].values[:-1],
                g['lon'].values[1:], g['lat'].values[1:]).sum()
        dt = (g['time'].iloc[-1] - g['time'].iloc[0]).total_seconds()
        if dt > 0:
            vo.append(d / dt)
    v_sim = {}
    for key, tag, _ in MEMBERS:
        sim = pd.read_csv(PROC / f'drifter_sim_{tag}.csv', parse_dates=['time'])
        vs = []
        for (dp, did), g in sim.groupby(['deploy', 'drifter_id']):
            o = obs[(obs['deploy'] == dp) & (obs['source'] == did)]
            if o.empty:
                continue
            g = g[(g['time'] >= o['time'].min()) &
                  (g['time'] <= o['time'].max())].sort_values('time')
            if len(g) < 2:
                continue
            d = hav(g['lon'].values[:-1], g['lat'].values[:-1],
                    g['lon'].values[1:], g['lat'].values[1:]).sum()
            dt = (g['time'].iloc[-1] - g['time'].iloc[0]).total_seconds()
            if dt > 0:
                vs.append(d / dt)
        v_sim[key] = float(np.mean(vs))
    return float(np.mean(vo)), v_sim


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#c9c7c1')


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    rng = np.random.default_rng(3)

    met = {k: pd.read_csv(PROC / f'drifter_metrics_{tag}.csv')
           for k, tag, _ in MEMBERS}
    obs = pd.read_csv(PROC / 'drifter_tracks_Jul2025.csv', parse_dates=['time'])
    v_obs, v_sim = track_speeds(obs)

    fig = plt.figure(figsize=(11.0, 4.3), dpi=300)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.45, 0.85], wspace=0.30,
                          left=0.06, right=0.98, top=0.87, bottom=0.17)
    fig.patch.set_facecolor(SURFACE)

    # (a) skill per drifter
    ax = fig.add_subplot(gs[0, 0])
    for i, (k, _, lab) in enumerate(MEMBERS):
        v = met[k]['LW_skill'].values
        c = ACCENT if k == 'vr' else BASE
        ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=13, color=c,
                   alpha=0.55, linewidths=0, zorder=3)
        ax.plot([i - 0.32, i + 0.32], [v.mean()] * 2, '-', color=c, lw=2.6,
                zorder=4, solid_capstyle='round')
    ax.set_xticks(range(len(MEMBERS)))
    ax.set_xticklabels([m[2] for m in MEMBERS], rotation=30, ha='right',
                       fontsize=8)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_title('(a) Skill, all 35 drifters', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    style(ax)

    # (b) wave contrast per deploy
    ax = fig.add_subplot(gs[0, 1])
    a = met['nodm'].merge(met['nowaves'], on=['deploy', 'drifter_id'],
                          suffixes=('_on', '_off'))
    a['d'] = a['LW_skill_on'] - a['LW_skill_off']
    deps = sorted(a['deploy'].unique())
    for i, dp in enumerate(deps):
        sub = a[a['deploy'] == dp]
        m = sub['d'].mean()
        c = WORSE if m < 0 else BETTER
        ax.bar(i, m, width=0.62, color=c, edgecolor='white', lw=0.6, zorder=3)
        ax.scatter([i] * len(sub) + rng.uniform(-0.13, 0.13, len(sub)),
                   sub['d'], s=12, color=INK, alpha=0.55, linewidths=0, zorder=5)
    ax.axhline(0, color=INK, lw=1.0, zorder=4)
    ax.axhline(a['d'].mean(), color=MUTED, ls='--', lw=1.3, zorder=4)
    ax.text(0.5, a['d'].mean() - 0.004, f"mean {a['d'].mean():+.3f}",
            fontsize=7.5, color=MUTED, va='top', ha='left')
    ax.set_xticks(range(len(deps)))
    ax.set_xticklabels([str(int(d)) for d in deps], fontsize=8)
    ax.set_xlabel('Deployment', fontsize=8.5, color=MUTED)
    ax.set_ylabel('$\\Delta$ skill from wave coupling', fontsize=8.5,
                  color=MUTED)
    ax.set_title('(b) Wave coupling, deployment by deployment', loc='left',
                 fontsize=9.5, color=INK, pad=7)
    style(ax)
    ax.legend(handles=[
        Line2D([0], [0], marker='s', ls='', mfc=WORSE, mec='none', ms=8,
               label='waves worse (10 of 12)'),
        Line2D([0], [0], marker='s', ls='', mfc=BETTER, mec='none', ms=8,
               label='waves better (2 of 12)'),
        Line2D([0], [0], marker='o', ls='', mfc=INK, mec='none', ms=4,
               alpha=0.55, label='individual drifter')],
        fontsize=7.5, frameon=False, loc='lower left', ncol=1)

    # (c) transport rate
    ax = fig.add_subplot(gs[0, 2])
    ys = np.arange(len(MEMBERS))[::-1]
    for y, (k, _, lab) in zip(ys, MEMBERS):
        c = ACCENT if k == 'vr' else BASE
        ax.plot([0, v_sim[k]], [y, y], '-', color=c, lw=3.0, zorder=3,
                solid_capstyle='round')
        ax.plot([v_sim[k]], [y], 'o', ms=8, mfc=c, mec='white', mew=1.2,
                zorder=4)
        ax.text(v_sim[k] + 0.004, y, f'{v_sim[k] / v_obs:.2f}', fontsize=7.5,
                color=INK if k == 'vr' else MUTED, va='center')
    ax.axvline(v_obs, color=INK, ls='--', lw=1.4, zorder=2)
    ax.text(v_obs, len(MEMBERS) - 0.3, ' observed', fontsize=7.5, color=INK,
            ha='left', va='center')
    ax.set_yticks(ys)
    ax.set_yticklabels([m[2] for m in MEMBERS], fontsize=8)
    ax.set_xlim(0, max(v_obs, max(v_sim.values())) * 1.42)
    ax.set_ylim(-0.6, len(MEMBERS) - 0.4)
    ax.set_xlabel('Speed along own track (m s$^{-1}$)', fontsize=8.5,
                  color=MUTED)
    ax.set_title('(c) Transport rate', loc='left', fontsize=9.5, color=INK,
                 pad=7)
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'lagrangian_results.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)

    # the table Section 4.2 needs
    print('\n=== member, LW, EP, path ratio, speed ratio ===')
    for k, tag, lab in MEMBERS:
        d = met[k]
        print(f'{lab:14s} {d["LW_skill"].mean():.3f}  {d["endpoint_sep_m"].mean():4.0f}  '
              f'{d["path_ratio"].mean():.2f}  {v_sim[k] / v_obs:.2f}')


if __name__ == '__main__':
    main()
