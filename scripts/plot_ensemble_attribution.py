"""Process attribution over the closed eight-member factorial.

The design covers all eight cells of waves x canopy x bed mobility. The
roughness arm changed on 2026-08-31: it used to be the trachytope members,
which were not resisting the flow, and is now FM's vegetation module with
every parameter taken from published measurement. That change reverses the
reading of the whole figure.

The canopy is now the largest single effect in the design, +0.087 to +0.256,
and it is the only factor whose four contrasts all clear zero in the same
direction. The waves/bed-mobility interaction that the earlier version made
the central result survives only in the bare-bed arm: with the canopy present
the wave contrast on a mobile bed is -0.014 (p=0.61) and the bed contrast with
waves is +0.018 (p=0.19), against +0.155 and +0.119 without it.

(a) Skill for every drifter under every member.
(b) The wave contrast on a mobile bed, deployment by deployment, with and
    without the canopy. The gain is confined to the bare bed.
(c) All twelve single-factor contrasts, four per factor, one for each
    combination of the other two. Marker fill encodes whether the bootstrap
    interval clears zero, so a large point estimate with a crossing interval
    cannot be misread as a result.
(d) The interaction drawn in both arms. The bare-bed lines cross; the
    vegetated ones run flat and high.

Output: figures/ensemble_attribution.{png,pdf}
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensemble import (MEMBERS as ENS, KEYS, TAG, LABEL, CONTRASTS,
                       MODELDIR, FACTORS, scored)
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
    d = scored(d).reset_index(drop=True)
    print(f'{len(d)} drifters, {d["deploy"].nunique()} deploys')

    fig = plt.figure(figsize=(11.4, 8.4), dpi=300)
    gs = fig.add_gridspec(2, 2, hspace=0.48, wspace=0.28,
                          left=0.07, right=0.97, top=0.93, bottom=0.08)

    # (a) skill per drifter
    ax = fig.add_subplot(gs[0, 0])
    for i, (k, _, lab) in enumerate(MEMBERS):
        v = d[k].values
        # the whole vegetated arm is highlighted, not just the full member:
        # what the panel has to show is that the four sit above the four
        c = ACCENT if FACTORS[k]['roughness'] == 'vegetated' else BASE
        ax.scatter(i + rng.uniform(-0.17, 0.17, len(v)), v, s=11, color=c,
                   alpha=0.5, linewidths=0, zorder=3)
        ax.plot([i - 0.3, i + 0.3], [v.mean()] * 2, '-', color=c, lw=2.6,
                zorder=4, solid_capstyle='round')
    ax.set_xticks(range(len(MEMBERS)))
    # the eight labels collide when written horizontally; a compact three-slot
    # code (waves / roughness / bed) reads faster than wrapped words anyway
    code = {'nowaves': '---', 'nowaves_veg': '-V-', 'nodm': 'W--',
            'nodm_veg': 'WV-', 'nowaves_dm': '--M', 'nowaves_vegdm': '-VM',
            'bl': 'W-M', 'veg': 'WVM'}
    ax.set_xticklabels([code[m[0]] for m in MEMBERS], fontsize=8.5,
                       family='DejaVu Sans Mono')
    ax.text(0.0, -0.19, 'W wave coupling   V seagrass canopy   '
            'M mobile bed', transform=ax.transAxes, fontsize=7.2, color=MUTED)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_title(f'(a) Skill, all {len(d)} drifters', loc='left', fontsize=9.5,
                 color=INK, pad=7)
    style(ax)

    # (b) the wave contrast on a mobile bed, with and without the canopy. This
    # is the panel that carries the result: the wave gain a bare bed shows is
    # not reproduced once the meadow is there to resist the flow.
    ax = fig.add_subplot(gs[0, 1])
    deps = sorted(d['deploy'].unique())
    pairs = [('bare bed', 'bl', 'nowaves_dm', C_FIXED, -0.19),
             ('with canopy', 'veg', 'nowaves_vegdm', ACCENT, 0.19)]
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
    ax.set_ylabel(r'$\Delta$ skill from wave coupling', fontsize=8.5,
                  color=MUTED)
    ax.set_title('(b) On a mobile bed, waves pay only where the canopy is absent',
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

    # (d) the interaction, drawn in both arms. Colour is the canopy treatment,
    # line style the wave treatment: the bare-bed lines cross, the vegetated
    # ones run flat and high, so the crossing is a property of the bare bed and
    # not of the basin.
    ax = fig.add_subplot(gs[1, 1])
    series = [('Bare bed, no waves', ['nowaves', 'nowaves_dm'], C_FIXED, 'o', '--'),
              ('Bare bed, waves', ['nodm', 'bl'], C_FIXED, 's', '-'),
              ('Canopy, no waves', ['nowaves_veg', 'nowaves_vegdm'], ACCENT, 'o', '--'),
              ('Canopy, waves', ['nodm_veg', 'veg'], ACCENT, 's', '-')]
    for lab, keys, col, mk, ls in series:
        m = [d[k].mean() for k in keys]
        ci = [boot_ci(d[k], rng) for k in keys]
        err = np.array([[m[i] - ci[i][0], ci[i][1] - m[i]] for i in range(2)]).T
        ax.errorbar([0, 1], m, yerr=err, color=col, marker=mk, ms=7, lw=2,
                    ls=ls, capsize=4, capthick=1.4, mec='white', mew=1.2,
                    label=lab, zorder=4)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Fixed', 'Mobile'], fontsize=8.5)
    ax.set_xlabel('Bed', fontsize=8.5, color=MUTED)
    ax.set_ylabel('Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.3, 1.45)
    ax.set_title('(d) The crossing belongs to the bare bed, not to the basin',
                 loc='left', fontsize=9.5, color=INK, pad=7)
    ax.legend(fontsize=7.2, frameon=False, loc='lower left')
    style(ax)

    for ext in ('png', 'pdf'):
        p = FIG / f'ensemble_attribution.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
