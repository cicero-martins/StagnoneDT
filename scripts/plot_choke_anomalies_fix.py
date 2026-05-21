"""Comprehensive figure of the choke opening: 4 panels.
- (a) wide regional view with Marettimo + .pli + cell 13162 marked
- (b) zoom before (with anomalies bl=+10m marked)
- (c) zoom after (anomalies set to bl=-2m)
- (d) delta map (cells changed, color shows magnitude of change)
"""
import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

CENTER_LON, CENTER_LAT = 12.0434, 38.0003
PLI = 'data/processed/d2025-07-13_inputs_for_review/Stagnone_dxy01_15m.pli'


def load_globals(in_dir):
    all_fx, all_fy, all_z, all_rank, all_gnr = [], [], [], [], []
    for r in range(8):
        ds = nc.Dataset(f'{in_dir}/Stagnone_dxy01_15m_{r:04d}_net.nc')
        fx = np.asarray(ds.variables['mesh2d_face_x'][:])
        fy = np.asarray(ds.variables['mesh2d_face_y'][:])
        bl = np.asarray(ds.variables['mesh2d_face_z'][:])
        dom = np.asarray(ds.variables['mesh2d_netelem_domain'][:])
        gnr = np.asarray(ds.variables['mesh2d_netelem_globalnr'][:])
        own = dom == r
        all_fx.append(fx[own]); all_fy.append(fy[own]); all_z.append(bl[own])
        all_rank.append(np.full(own.sum(), r)); all_gnr.append(gnr[own])
        ds.close()
    return (np.concatenate(all_fx), np.concatenate(all_fy),
            np.concatenate(all_z), np.concatenate(all_rank), np.concatenate(all_gnr))


orig = load_globals('data/processed/net_nodm_orig')
mod = load_globals('data/processed/net_nodm_choke_opened')

fx, fy, z_orig, rank, gnr = orig
_, _, z_mod, _, _ = mod
delta = z_mod - z_orig

# pli nodes
pli_nodes = []
with open(PLI) as f:
    lines = [l.strip() for l in f if l.strip() and not l.startswith('*')]
i = 0
while i < len(lines):
    name = lines[i]; i += 1
    n = int(lines[i].split()[0]); i += 1
    for j in range(n):
        parts = lines[i].split(); i += 1
        pli_nodes.append((float(parts[0]), float(parts[1])))
pli_nodes = np.array(pli_nodes)

modified = np.abs(delta) > 0.1
print(f'cells modified: {modified.sum()}')

fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(2, 2, hspace=0.25, wspace=0.18)

# ===== (a) WIDE REGIONAL =====
ax_a = fig.add_subplot(gs[0, :])
near_wide = (fx > 11.9) & (fx < 12.55) & (fy > 37.7) & (fy < 38.1)
sc = ax_a.scatter(fx[near_wide], fy[near_wide], c=z_orig[near_wide], s=1.5,
                   cmap='terrain', vmin=-50, vmax=10)
ax_a.plot(pli_nodes[:, 0], pli_nodes[:, 1], 'k-', lw=0.5, alpha=0.6)
ax_a.scatter(pli_nodes[:, 0], pli_nodes[:, 1], c='black', s=15, marker='.', label='.pli boundary')
ax_a.scatter(CENTER_LON, CENTER_LAT, c='red', s=120, marker='X',
              edgecolor='white', linewidth=1.5, label='cell 13162 (choke point)', zorder=5)
# Annotations
ax_a.annotate('N open boundary\n(WL inflow)', xy=(12.10, 38.063), xytext=(12.10, 38.085),
              fontsize=9, ha='center',
              arrowprops=dict(arrowstyle='->', color='black'))
ax_a.annotate('Marettimo\n(land mass)', xy=(12.06, 37.97), xytext=(12.05, 37.93),
              fontsize=9, ha='center', color='darkred',
              arrowprops=dict(arrowstyle='->', color='darkred'))
ax_a.annotate('Stagnone lagoon', xy=(12.45, 37.86), fontsize=10, ha='center', style='italic')
# Zoom box
ax_a.add_patch(Rectangle((12.025, 37.985), 0.05, 0.030,
                         fill=False, edgecolor='red', lw=1.5, linestyle='--'))
ax_a.set_title('(a) Regional context — flow path from N boundary squeezes past Marettimo through cell 13162', fontsize=11)
ax_a.set_xlabel('longitude (°E)')
ax_a.set_ylabel('latitude (°N)')
ax_a.set_aspect(1 / np.cos(np.radians(37.9)))
ax_a.legend(loc='upper right', fontsize=8)
ax_a.grid(alpha=0.25)
plt.colorbar(sc, ax=ax_a, shrink=0.75, label='bedlevel [m]  (red = land/shallow)')

# ===== (b) ZOOM BEFORE =====
ax_b = fig.add_subplot(gs[1, 0])
near = (fx > 12.025) & (fx < 12.075) & (fy > 37.985) & (fy < 38.015)
sc_b = ax_b.scatter(fx[near], fy[near], c=z_orig[near], s=25,
                     cmap='RdBu_r', vmin=-25, vmax=15, edgecolor='k', linewidth=0.15)
ax_b.scatter(CENTER_LON, CENTER_LAT, c='lime', s=180, marker='X',
              edgecolor='black', linewidth=1.5, zorder=5)
land = near & (z_orig > 5)
ax_b.scatter(fx[land], fy[land], facecolor='none', edgecolor='red',
              s=80, linewidth=1.5, label=f'{modified.sum()} anomalous bl=+10m cells')
ax_b.set_title('(b) BEFORE: choke point — red circles = land cells (bl=+10m) blocking flow', fontsize=10)
ax_b.set_xlabel('longitude (°E)')
ax_b.set_ylabel('latitude (°N)')
ax_b.set_aspect(1 / np.cos(np.radians(37.9)))
ax_b.legend(loc='lower left', fontsize=8)
plt.colorbar(sc_b, ax=ax_b, shrink=0.85, label='bedlevel [m]')

# ===== (c) ZOOM AFTER =====
ax_c = fig.add_subplot(gs[1, 1])
sc_c = ax_c.scatter(fx[near], fy[near], c=z_mod[near], s=25,
                     cmap='RdBu_r', vmin=-25, vmax=15, edgecolor='k', linewidth=0.15)
ax_c.scatter(CENTER_LON, CENTER_LAT, c='lime', s=180, marker='X',
              edgecolor='black', linewidth=1.5, zorder=5)
# Highlight modified cells
mod_near = near & modified
ax_c.scatter(fx[mod_near], fy[mod_near], facecolor='none', edgecolor='green',
              s=80, linewidth=1.5, label=f'opened cells (bl=+10m → -2m)')
ax_c.set_title('(c) AFTER: opened cells (bl=-2m, shallow but wet) — flow can spread', fontsize=10)
ax_c.set_xlabel('longitude (°E)')
ax_c.set_ylabel('latitude (°N)')
ax_c.set_aspect(1 / np.cos(np.radians(37.9)))
ax_c.legend(loc='lower left', fontsize=8)
plt.colorbar(sc_c, ax=ax_c, shrink=0.85, label='bedlevel [m]')

plt.suptitle('Choke point opening: replace bl=+10m artifacts NE of Marettimo with bl=-2m\n'
             f'Total modified: {modified.sum()} cells in rank 4 partition',
             y=0.99, fontsize=12, fontweight='bold')

import os
os.makedirs('figures', exist_ok=True)
plt.savefig('figures/choke_fix_comprehensive.png', dpi=140, bbox_inches='tight')
print('Saved figures/choke_fix_comprehensive.png')
