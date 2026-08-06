"""Process attribution across the five-member ensemble (Paper 1, RQ2/RQ3).

Four panels, each answering a question the summary table cannot:

(a) Does the effect of seagrass roughness depend on whether the bed can
    respond? Two non-parallel lines mean an interaction, which is exactly what
    the numbers suggest and what a table of five means hides.
(b) The same for endpoint proximity, an independent Lagrangian measure that
    does not share the skill score's normalisation.
(c) Effect sizes with bootstrap confidence intervals. A contrast whose interval
    crosses zero has not been demonstrated, however large its point estimate.
(d) Are the two headline effects consistent across deploys, or carried by a
    handful of them? Paired per-drifter differences, so each point is one
    drifter compared against itself under two configurations.

Colour: only two or three categorical slots are ever on screen at once, taken
from the validated all-pairs trio (orange, aqua, violet). Members are otherwise
distinguished by position, not hue, which keeps the five-member comparison
clear of the three-slot cap that scatter-like forms carry.

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
C_FIXED = '#eb6834'   # fixed bed
C_MORPH = '#4a3aa7'   # active morphodynamics
C_WAVE = '#1baf7a'    # the wave contrast in panel (d)

MEMBERS = {
    'nowaves': 'v04AE_nowaves',
    'nodm':    'v04AE_nodm',
    'nodm_vr': 'v04AE_nodm_vr',
    'bl':      'v04AE',
    'vr':      'v04AE_vr',
}
NBOOT = 4000


def load():
    frames = []
    for key, tag in MEMBERS.items():
        p = PROC / f'drifter_metrics_{tag}.csv'
        df = pd.read_csv(p)[['deploy', 'drifter_id', 'LW_skill', 'endpoint_sep_m']]
        df = df.rename(columns={'LW_skill': f'LW_{key}',
                                'endpoint_sep_m': f'EP_{key}'})
        frames.append(df)
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=['deploy', 'drifter_id'], how='inner')
    return out


def boot_ci(v, rng, n=NBOOT):
    v = np.asarray(v, dtype=float)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    means = v[idx].mean(axis=1)
    return np.percentile(means, [2.5, 97.5])


def panel_interaction(ax, d, prefix, ylabel, invert=False):
    """Mean metric at (roughness off/on) for fixed bed and active morphodynamics."""
    rng = np.random.default_rng(7)
    xs = [0, 1]
    series = [('Fixed bed', ['nodm', 'nodm_vr'], C_FIXED, 'o'),
              ('Active morphodynamics', ['bl', 'vr'], C_MORPH, 's')]
    for label, keys, colour, mk in series:
        m = [d[f'{prefix}_{k}'].mean() for k in keys]
        ci = [boot_ci(d[f'{prefix}_{k}'], rng) for k in keys]
        err = np.array([[m[i] - ci[i][0], ci[i][1] - m[i]] for i in range(2)]).T
        ax.errorbar(xs, m, yerr=err, color=colour, marker=mk, ms=8, lw=2,
                    capsize=4, capthick=1.4, mec='white', mew=1.2,
                    label=label, zorder=4)

    nw = d[f'{prefix}_nowaves']
    lo, hi = boot_ci(nw, rng)
    ax.axhspan(lo, hi, color=MUTED, alpha=0.13, zorder=1)
    ax.axhline(nw.mean(), color=MUTED, ls='--', lw=1.4, zorder=2)
    ax.text(1.04, nw.mean(), 'no waves', fontsize=7.5, color=MUTED,
            va='center', ha='left', transform=ax.get_yaxis_transform())

    ax.set_xticks(xs)
    ax.set_xticklabels(['Uniform', 'Distributed'], fontsize=8.5)
    ax.set_xlabel('Seagrass roughness', fontsize=8.5, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.28, 1.28)
    if invert:
        ax.invert_yaxis()
    style(ax)


def panel_effects(ax, d):
    rng = np.random.default_rng(11)
    contrasts = [
        ('Wave coupling',            'LW_nodm',    'LW_nowaves'),
        ('Roughness | fixed bed',    'LW_nodm_vr', 'LW_nodm'),
        ('Morphodynamics | uniform', 'LW_bl',      'LW_nodm'),
        ('Roughness | morph. on',    'LW_vr',      'LW_bl'),
        ('Morphodynamics | rough.',  'LW_vr',      'LW_nodm_vr'),
    ]
    ys = np.arange(len(contrasts))[::-1]
    for y, (lab, a, b) in zip(ys, contrasts):
        x = (d[a] - d[b]).dropna()
        m = x.mean()
        lo, hi = boot_ci(x, rng)
        p = wilcoxon(x).pvalue
        crosses = lo <= 0 <= hi
        ax.plot([lo, hi], [y, y], '-', color=INK if not crosses else MUTED,
                lw=2.2, alpha=0.85 if not crosses else 0.45, zorder=3,
                solid_capstyle='round')
        ax.plot([m], [y], marker='o' if not crosses else 'o', ms=8,
                mfc=INK if not crosses else SURFACE, mec=INK, mew=1.6,
                zorder=4, ls='')
        ax.text(0.335, y, f'p = {p:.3f}' if p >= 0.001 else 'p < 0.001',
                fontsize=7.5, color=MUTED, va='center', ha='right')
    ax.axvline(0, color=INK, lw=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels([c[0] for c in contrasts], fontsize=8.5)
    ax.set_xlabel('Change in Liu--Weisberg skill', fontsize=8.5, color=MUTED)
    ax.set_xlim(-0.10, 0.345)
    ax.set_ylim(-0.6, len(contrasts) - 0.4)
    style(ax)
    ax.text(0.0, -0.19, 'filled = interval clear of zero; open = not demonstrated',
            transform=ax.transAxes, fontsize=7.2, color=MUTED, ha='left')


def panel_perdeploy(ax, d):
    dep = sorted(d['deploy'].unique())
    w = 0.19
    pairs = [('Morphodynamics + roughness\n(vr - nodm_vr)', 'LW_vr', 'LW_nodm_vr',
              C_MORPH, -w),
             ('Wave coupling\n(nodm - nowaves)', 'LW_nodm', 'LW_nowaves',
              C_WAVE, w)]
    for lab, a, b, colour, off in pairs:
        xs, vs = [], []
        for i, dp in enumerate(dep):
            sub = d[d['deploy'] == dp]
            xs.append(i + off)
            vs.append((sub[a] - sub[b]).mean())
        ax.bar(xs, vs, width=w * 1.7, color=colour, edgecolor='white',
               linewidth=0.6, label=lab, zorder=3)
    ax.axhline(0, color=INK, lw=1.0, zorder=4)
    ax.set_xticks(range(len(dep)))
    ax.set_xticklabels([str(int(x)) for x in dep], fontsize=8)
    ax.set_xlabel('Deployment', fontsize=8.5, color=MUTED)
    ax.set_ylabel('Change in LW skill', fontsize=8.5, color=MUTED)
    style(ax)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + 0.30 * (hi - lo))
    ax.legend(fontsize=7.5, frameon=False, loc='upper right', ncol=2,
              handlelength=1.2, columnspacing=1.0)


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis='both', color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    for sp in ['left', 'bottom']:
        ax.spines[sp].set_color('#c9c7c1')


def main():
    mpl.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
    d = load()
    print(f'{len(d)} drifters common to all five members, '
          f'{d["deploy"].nunique()} deploys')
    for k in MEMBERS:
        print(f'  {k:9s} LW {d[f"LW_{k}"].mean():.3f}   EP {d[f"EP_{k}"].mean():4.0f} m')

    fig = plt.figure(figsize=(10.2, 7.4), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.30,
                          left=0.08, right=0.965, top=0.93, bottom=0.09)

    ax_a = fig.add_subplot(gs[0, 0])
    panel_interaction(ax_a, d, 'LW', 'Liu--Weisberg skill')
    ax_a.set_title('(a) Skill: the two factors interact', loc='left',
                   fontsize=9.5, color=INK, pad=8)
    ax_a.legend(fontsize=7.5, frameon=False, loc='upper left')

    ax_b = fig.add_subplot(gs[0, 1])
    panel_interaction(ax_b, d, 'EP', 'Endpoint separation (m)', invert=True)
    ax_b.set_title('(b) Endpoint proximity, same pattern', loc='left',
                   fontsize=9.5, color=INK, pad=8)

    ax_c = fig.add_subplot(gs[1, 0])
    panel_effects(ax_c, d)
    ax_c.set_title('(c) Effect sizes, paired, 95% bootstrap CI', loc='left',
                   fontsize=9.5, color=INK, pad=8)

    ax_d = fig.add_subplot(gs[1, 1])
    panel_perdeploy(ax_d, d)
    ax_d.set_title('(d) Per-deployment consistency', loc='left',
                   fontsize=9.5, color=INK, pad=8)

    for ext in ('png', 'pdf'):
        p = FIG / f'ensemble_attribution.{ext}'
        fig.savefig(p, bbox_inches='tight', facecolor=SURFACE)
        print(f'Saved {p}')
    plt.close(fig)


if __name__ == '__main__':
    main()
