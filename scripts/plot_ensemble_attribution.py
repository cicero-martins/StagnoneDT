"""Process attribution over the closed eight-member factorial.

The design covers all eight cells of waves x roughness x bed mobility. It was
six until DensIn=false let the two no-wave mobile-bed members run, and the two
new cells reverse what the earlier version reported: measured on a fixed bed
alone, wave coupling looked like a small penalty.

(a) Skill for every drifter under every member.
(b) The wave contrast deployment by deployment, on a fixed and on a mobile bed.
    The sign flips. This is the panel a six-member ensemble could not draw.
(c) All twelve single-factor contrasts, four per factor, one for each
    combination of the other two. Marker fill encodes whether the bootstrap
    interval clears zero, so a large point estimate with a crossing interval
    cannot be misread as a result.
(d) The interaction stated directly: waves and bed mobility each cost skill
    alone and pay only together.

Output: figures/ensemble_attribution.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import MEMBERS as ENS, KEYS, TAG, LABEL, CONTRASTS, MODELDIR
from matplotlib.lines import Line2D
from scipy.stats import wilcoxon

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
C_FIXED = '#eb6834'
C_UNIF = '#1baf7a'
NBOOT = 4000

MEMBERS = [(k, TAG[k], LABEL[k]) for k in KEYS]



def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    return np.percentile(v[idx].mean(axis=1), [2.5, 97.5])


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
    rng = np.random.default_rng(17)

    d = None
    for key, tag, _ in MEMBERS:
        m = pd.read_csv(PROC / f'drifter_metrics_{tag}.csv')[
            ['deploy', 'drifter_id', 'LW_skill']].rename(
                columns={'LW_skill': key})
        d = m if d is None else d.merge(m, on=['deploy', 'drifter_id'])
    print(f'{len(d)} drifters, {d["deploy"].nunique()} deploys')

    fig = plt.figure(figsize=(11.4, 8.4), dpi=300)
    gs = fig.add_gridspec(2, 2, hspace=0.48, wspace=0.28,
                          left=0.07, right=0.97, top=0.93, bottom=0.08)

    # (a) skill per drifter
    ax = fig.add_subplot(gs[0, 0])
    for i, (k, _, lab) in enumerate(MEMBERS):
        v = d[k].values
        c = ACCENT if k == 'vr' else BASE
        ax.scatter(i + rng.uniform(-0.17, 0.17, len(v)), v, s=11, color=c,
                   alpha=0.5, linewidths=0, zorder=3)
        ax.plot([i - 0.3, i + 0.3], [v.mean()] * 2, '-', color=c, lw=2.6,
                zorder=4, solid_capstyle='round')
    ax.set_xticks(range(len(MEMBERS)))
    # the eight labels collide when written horizontally; a compact three-slot
    # code (waves / roughness / bed) reads faster than wrapped words anyway
    code = {'nowaves': '---', 'nowaves_vr': '-R-', 'nodm': 'W--',
            'nodm_vr': 'WR-', 'nowaves_dm': '--M', 'nowaves_vrdm': '-RM',
            'bl': 'W-M', 'vr': 'WRM'}
    ax.set_xticklabels([code[m[0]] for m in MEMBERS], fontsize=8.5,
                       family='DejaVu Sans Mono')
    ax.text(0.0, -0.19, 'W wave coupling   R distributed roughness   '
            'M mobile bed', transform=ax.transAxes, fontsize=7.2, color=MUTED)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_title('(a) Skill, all 35 drifters', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    style(ax)

    # (b) the wave contrast on a fixed and on a mobile bed
    ax = fig.add_subplot(gs[0, 1])
    deps = sorted(d['deploy'].unique())
    pairs = [('on a fixed bed', 'nodm_vr', 'nowaves_vr', C_FIXED, -0.19),
             ('on a mobile bed', 'vr', 'nowaves_vrdm', ACCENT, 0.19)]
    for lab, a, b, col, off in pairs:
        xs, vs = [], []
        for i, dp in enumerate(deps):
            sub = d[d['deploy'] == dp]
            xs.append(i + off)
            vs.append((sub[a] - sub[b]).mean())
        ax.bar(xs, vs, width=0.34, color=col, edgecolor='white', lw=0.6,
               label=lab, zorder=3)
    ax.axhline(0, color=INK, lw=1.0, zorder=4)
    ax.set_xticks(range(len(deps)))
    ax.set_xticklabels([str(int(x)) for x in deps], fontsize=8)
    ax.set_xlabel('Deployment', fontsize=8.5, color=MUTED)
    ax.set_ylabel('$\Delta$ skill from wave coupling', fontsize=8.5,
                  color=MUTED)
    ax.set_title('(b) Waves cost skill on a fixed bed and gain it on a mobile one',
                 loc='left', fontsize=9.5, color=INK, pad=7)
    style(ax)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + 0.30 * (hi - lo))
    ax.legend(fontsize=7.5, frameon=False, loc='upper left', ncol=2)

    # (c) effect sizes
    ax = fig.add_subplot(gs[1, 0])
    ys = np.arange(len(CONTRASTS))[::-1]
    for y, (lab, a, b) in zip(ys, CONTRASTS):
        x = (d[a] - d[b]).dropna()
        m = x.mean()
        lo_, hi_ = boot_ci(x, rng)
        p = wilcoxon(x).pvalue
        crosses = lo_ <= 0 <= hi_
        ax.plot([lo_, hi_], [y, y], '-', color=MUTED if crosses else INK,
                lw=2.2, alpha=0.45 if crosses else 0.85, zorder=3,
                solid_capstyle='round')
        ax.plot([m], [y], 'o', ms=8, mfc=SURFACE if crosses else INK, mec=INK,
                mew=1.6, zorder=4, ls='')
        ax.axvline(0, color=INK, lw=1.0, zorder=2)
    for yy in (len(CONTRASTS) - 4.5, len(CONTRASTS) - 8.5):
        ax.axhline(yy, color=GRID, lw=1.0, zorder=1)
    ax.set_yticks(ys)
    ax.set_yticklabels([c[0] for c in CONTRASTS], fontsize=7.2)
    ax.set_xlabel('Change in Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.12, 0.36)
    ax.set_ylim(-0.6, len(CONTRASTS) - 0.4)
    ax.set_title('(c) All twelve single-factor contrasts, 95% bootstrap CI', loc='left',
                 fontsize=9.5, color=INK, pad=7)
    style(ax)
    ax.text(0.0, -0.17, 'filled = interval clear of zero',
            transform=ax.transAxes, fontsize=7.2, color=MUTED, ha='left')

    # (d) the interaction that the closed design exposes
    ax = fig.add_subplot(gs[1, 1])
    series = [('No wave coupling', ['nowaves_vr', 'nowaves_vrdm'], C_FIXED, 'o'),
              ('Wave coupling', ['nodm_vr', 'vr'], ACCENT, 's')]
    for lab, keys, col, mk in series:
        m = [d[k].mean() for k in keys]
        ci = [boot_ci(d[k], rng) for k in keys]
        err = np.array([[m[i] - ci[i][0], ci[i][1] - m[i]] for i in range(2)]).T
        ax.errorbar([0, 1], m, yerr=err, color=col, marker=mk, ms=8, lw=2,
                    capsize=4, capthick=1.4, mec='white', mew=1.2, label=lab,
                    zorder=4)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Fixed', 'Mobile'], fontsize=8.5)
    ax.set_xlabel('Bed', fontsize=8.5, color=MUTED)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.3, 1.3)
    ax.set_title('(d) Waves and bed mobility pay only together',
                 loc='left', fontsize=9.5, color=INK, pad=7)
    ax.legend(fontsize=7.5, frameon=False, loc='upper left')
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'ensemble_attribution.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
