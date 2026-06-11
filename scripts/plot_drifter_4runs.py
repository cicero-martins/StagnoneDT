"""
4-run drifter comparison: bl / nodm / vr / nodm_vr
Panels: per-deploy LW skill bar chart + global summary + deploy map
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'

RUNS = {
    'bl':       ('v04AE (D-Morph ON,  VR OFF)', '#2563eb'),
    'nodm':     ('v04AE_nodm (D-Morph OFF, VR OFF)', '#16a34a'),
    'vr':       ('v04AE_vr (D-Morph ON,  VR ON)',  '#dc2626'),
    'nodm_vr':  ('v04AE_nodm_vr (D-Morph OFF, VR ON)', '#ea580c'),
}

dfs = {}
for run in RUNS:
    f = PROC / f'drifter_metrics_v04AE{"_"+run if run!="bl" else ""}.csv'
    if not f.exists():  # try alternate name
        f = PROC / f'drifter_metrics_{run}.csv'
    if f.exists():
        dfs[run] = pd.read_csv(f)

# global means
means = {r: {'LW': df['LW_skill'].mean(), 'EP': df['endpoint_sep_m'].mean(), 'n': len(df)}
         for r, df in dfs.items()}

# per-deploy LW
dep_lw = {r: df.groupby('deploy')['LW_skill'].mean() for r, df in dfs.items()}
deploys = sorted(dep_lw['bl'].index)
n_dep = len(deploys)

# -------------------------------------------------------------------
# Figure 1: per-deploy bar + global bar
# -------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 6),
                          gridspec_kw={'width_ratios': [3, 1]})

ax = axes[0]
x = np.arange(n_dep)
width = 0.18
offsets = [-1.5, -0.5, 0.5, 1.5]
for (run, (label, color)), offset in zip(RUNS.items(), offsets):
    vals = [dep_lw[run].get(d, np.nan) for d in deploys]
    ax.bar(x + offset * width, vals, width, color=color, alpha=0.85,
           label=f'{run} ({means[run]["LW"]:.3f})')
ax.axhline(0, color='k', lw=0.5)
ax.set_xticks(x)
ax.set_xticklabels([f'D{d}' for d in deploys], fontsize=8)
ax.set_ylabel('L&W skill', fontsize=10)
ax.set_title('LW skill per deploy', fontsize=10)
ax.legend(fontsize=7.5, loc='lower right')
ax.set_ylim(-0.15, 1.05)
ax.grid(True, axis='y', alpha=0.3)

# global summary bar
ax2 = axes[1]
run_keys = list(RUNS.keys())
colors   = [RUNS[r][1] for r in run_keys]
lw_vals  = [means[r]['LW'] for r in run_keys]
ep_vals  = [means[r]['EP'] for r in run_keys]

ax2b = ax2.twinx()
bars = ax2.bar(np.arange(4) - 0.15, lw_vals, 0.28, color=colors, alpha=0.85, label='LW skill')
bars2 = ax2b.bar(np.arange(4) + 0.15, ep_vals, 0.28, color=colors, alpha=0.4, hatch='//', label='EP (m)')
ax2.set_ylabel('LW skill', fontsize=9)
ax2b.set_ylabel('Endpoint sep (m)', fontsize=9)
ax2.set_xticks(range(4))
ax2.set_xticklabels(run_keys, fontsize=8, rotation=20, ha='right')
ax2.set_title('Global means', fontsize=10)
ax2.set_ylim(0, 0.85)
ax2b.set_ylim(0, 850)
for i, (lw, ep) in enumerate(zip(lw_vals, ep_vals)):
    ax2.text(i - 0.15, lw + 0.01, f'{lw:.3f}', ha='center', fontsize=7.5, fontweight='bold')
    ax2b.text(i + 0.15, ep + 5,   f'{ep:.0f}', ha='center', fontsize=7, color='grey')
ax2.grid(True, axis='y', alpha=0.3)

fig.suptitle('Drifter LW skill — 4-run VR comparison (Jul 7-10, 35 drifters, 12 deploys)',
             fontsize=11)
fig.tight_layout()
out1 = FIG / 'drifter_4runs_lw.png'
fig.savefig(out1, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f'Fig 1 -> {out1}')

# -------------------------------------------------------------------
# Figure 2: delta matrix (change vs bl and vs nodm)
# -------------------------------------------------------------------
fig2, axes2 = plt.subplots(1, 2, figsize=(12, 5))

for ax, ref_run, ref_label in zip(axes2, ['bl', 'nodm'],
                                   ['bl (D-Morph ON, VR OFF)', 'nodm (D-Morph OFF, VR OFF)']):
    ref_vals = [dep_lw[ref_run].get(d, np.nan) for d in deploys]
    x = np.arange(n_dep)
    for i, (run, (label, color)) in enumerate(RUNS.items()):
        if run == ref_run:
            continue
        deltas = [dep_lw[run].get(d, np.nan) - dep_lw[ref_run].get(d, np.nan) for d in deploys]
        ax.bar(x + (i-1.5)*0.22, deltas, 0.22, color=color, alpha=0.85,
               label=f'{run} (mean {np.nanmean(deltas):+.3f})')
    ax.axhline(0, color='k', lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f'D{d}' for d in deploys], fontsize=8)
    ax.set_ylabel('Delta LW skill', fontsize=9)
    ax.set_title(f'Delta vs {ref_label}', fontsize=9)
    ax.legend(fontsize=7.5)
    ax.grid(True, axis='y', alpha=0.3)

fig2.suptitle('LW skill change relative to reference runs', fontsize=10)
fig2.tight_layout()
out2 = FIG / 'drifter_4runs_delta.png'
fig2.savefig(out2, dpi=150, bbox_inches='tight')
plt.close(fig2)
print(f'Fig 2 -> {out2}')

# -------------------------------------------------------------------
# Print summary table
# -------------------------------------------------------------------
print('\n=== Summary ===')
print(f'{"run":<14} {"LW":>6} {"EP_m":>7}  {"dLW vs bl":>10}  {"dLW vs nodm":>12}')
for run in RUNS:
    m = means[run]
    dlw_bl   = m['LW'] - means['bl']['LW']
    dlw_nodm = m['LW'] - means['nodm']['LW']
    print(f'{run:<14} {m["LW"]:>6.3f} {m["EP"]:>7.0f}  {dlw_bl:>+10.3f}  {dlw_nodm:>+12.3f}')

print('\nDecomposition:')
print(f'  D-Morph effect on drifters (bl - nodm):  {means["bl"]["LW"] - means["nodm"]["LW"]:+.3f} LW')
print(f'  VR clean effect (nodm_vr - nodm):         {means["nodm_vr"]["LW"] - means["nodm"]["LW"]:+.3f} LW')
print(f'  VR+DM combined (vr - nodm):               {means["vr"]["LW"] - means["nodm"]["LW"]:+.3f} LW')
print(f'  VR over D-Morph (vr - bl):                {means["vr"]["LW"] - means["bl"]["LW"]:+.3f} LW')
print('Done.')
