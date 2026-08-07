"""Process attribution over the six-member ensemble.

The ensemble covers six of the eight cells of a waves x roughness x bed-mobility
factorial. The two missing cells are no-waves with a mobile bed, in either
roughness treatment. Neither is attainable: both abort on the velocity cap,
before and after morphodynamics was confined to depths above 20 m.

(a) Skill for every drifter under every member.
(b) The wave penalty measured on BOTH roughness axes, deployment by deployment.
    This is what a single-axis measurement could not show: the penalty is the
    same size and the same consistency whether roughness is uniform or
    distributed, so it does not depend on the roughness treatment.
(c) Paired effect sizes with bootstrap intervals. Marker fill encodes whether
    the interval clears zero, so a large point estimate with a crossing
    interval cannot be misread as a result.
(d) The interaction: roughness does nothing on a fixed bed and a great deal on
    a mobile one.

Output: figures/ensemble_attribution.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
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

MEMBERS = [('nowaves', 'v04AE_nowaves', 'no waves'),
           ('nowaves_vr', 'v04AE_nowaves_vr', 'no waves\n+ rough.'),
           ('nodm', 'v04AE_nodm', 'waves'),
           ('nodm_vr', 'v04AE_nodm_vr', 'waves\n+ rough.'),
           ('bl', 'v04AE', 'waves\n+ morph.'),
           ('vr', 'v04AE_vr', 'full')]

CONTRASTS = [
    ('Waves | uniform, fixed bed',      'nodm',       'nowaves'),
    ('Waves | distributed, fixed bed',  'nodm_vr',    'nowaves_vr'),
    ('Roughness | no waves, fixed bed', 'nowaves_vr', 'nowaves'),
    ('Roughness | waves, fixed bed',    'nodm_vr',    'nodm'),
    ('Bed mobility | uniform',          'bl',         'nodm'),
    ('Roughness | waves, mobile bed',   'vr',         'bl'),
    ('Bed mobility | distributed',      'vr',         'nodm_vr'),
]


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

    fig = plt.figure(figsize=(11.0, 7.6), dpi=300)
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
    ax.set_xticklabels([m[2] for m in MEMBERS], fontsize=7.5)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_title('(a) Skill, all 35 drifters', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    style(ax)

    # (b) wave penalty on both roughness axes
    ax = fig.add_subplot(gs[0, 1])
    deps = sorted(d['deploy'].unique())
    pairs = [('uniform roughness', 'nodm', 'nowaves', C_UNIF, -0.19),
             ('distributed roughness', 'nodm_vr', 'nowaves_vr', C_FIXED, 0.19)]
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
    ax.set_ylabel('$\\Delta$ skill from waves', fontsize=8.5, color=MUTED)
    ax.set_title('(b) The wave penalty on both roughness axes', loc='left',
                 fontsize=9.5, color=INK, pad=7)
    style(ax)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + 0.35 * (hi - lo))
    ax.legend(fontsize=7.5, frameon=False, loc='upper right', ncol=1)

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
        ax.text(0.30, y, 'p < 0.001' if p < 0.001 else f'p = {p:.3f}',
                fontsize=7.2, color=MUTED, va='center', ha='right')
    ax.axvline(0, color=INK, lw=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels([c[0] for c in CONTRASTS], fontsize=8)
    ax.set_xlabel('Change in Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.12, 0.31)
    ax.set_ylim(-0.6, len(CONTRASTS) - 0.4)
    ax.set_title('(c) Effect sizes, paired, 95% bootstrap CI', loc='left',
                 fontsize=9.5, color=INK, pad=7)
    style(ax)
    ax.text(0.0, -0.17, 'filled = interval clear of zero',
            transform=ax.transAxes, fontsize=7.2, color=MUTED, ha='left')

    # (d) interaction
    ax = fig.add_subplot(gs[1, 1])
    series = [('Fixed bed', ['nodm', 'nodm_vr'], C_FIXED, 'o'),
              ('Mobile bed', ['bl', 'vr'], ACCENT, 's')]
    for lab, keys, col, mk in series:
        m = [d[k].mean() for k in keys]
        ci = [boot_ci(d[k], rng) for k in keys]
        err = np.array([[m[i] - ci[i][0], ci[i][1] - m[i]] for i in range(2)]).T
        ax.errorbar([0, 1], m, yerr=err, color=col, marker=mk, ms=8, lw=2,
                    capsize=4, capthick=1.4, mec='white', mew=1.2, label=lab,
                    zorder=4)
    nw = [d['nowaves'].mean(), d['nowaves_vr'].mean()]
    ax.plot([0, 1], nw, ':', color=MUTED, lw=1.8, marker='^', ms=6,
            mfc=MUTED, mec='white', label='No waves, fixed bed', zorder=3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Uniform', 'Distributed'], fontsize=8.5)
    ax.set_xlabel('Seagrass roughness', fontsize=8.5, color=MUTED)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.3, 1.3)
    ax.set_title('(d) Roughness matters only on a mobile bed', loc='left',
                 fontsize=9.5, color=INK, pad=7)
    ax.legend(fontsize=7.5, frameon=False, loc='upper left')
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'ensemble_attribution.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
