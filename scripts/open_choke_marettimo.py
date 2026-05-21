"""Open the choke point NE of Marettimo: replace bl=+10m land cells with bl=-2m
(shallow but wet) in the gap between cell 13162 and Marettimo's NE corner.

Approach: identify cells with bl > +5m that are within 1km of cell 13162 and
latitude range covering the NE Marettimo gap. Replace their bl with -2m.
Keeps Marettimo's main bulk as land; only opens the constricted gap.

Usage:
    python scripts/open_choke_marettimo.py \
        --in-dir data/processed/net_nodm_orig \
        --out-dir data/processed/net_nodm_choke_opened
"""
import argparse
import shutil
from pathlib import Path

import numpy as np
import netCDF4 as nc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CENTER_LON, CENTER_LAT = 12.0434, 38.0003   # cell 13162 location
TARGET_RADIUS_M = 1500.0   # distance from cell 13162 to consider
LAT_MIN, LAT_MAX = 37.990, 38.000   # NE corner of Marettimo gap
BL_LAND_THRESH = 5.0       # cells with bl > +5m are "land"
NEW_BL = -2.0              # value to set "opened" cells to


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--in-dir', required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--plot', default='figures/choke_opened.png')
    args = p.parse_args()

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Aggregate all owned cells globally (for inspection + global decision)
    all_fx, all_fy, all_z, all_rank, all_gnr, all_local = [], [], [], [], [], []
    files = sorted(in_dir.glob('Stagnone_dxy01_15m_000*_net.nc'))
    print(f'Found {len(files)} per-rank files')
    for f in files:
        r = int(f.stem.split('_')[-2])
        ds = nc.Dataset(f, 'r')
        fx = np.asarray(ds.variables['mesh2d_face_x'][:])
        fy = np.asarray(ds.variables['mesh2d_face_y'][:])
        bl = np.asarray(ds.variables['mesh2d_face_z'][:])
        dom = np.asarray(ds.variables['mesh2d_netelem_domain'][:])
        gnr = np.asarray(ds.variables['mesh2d_netelem_globalnr'][:])
        own = dom == r
        all_fx.append(fx[own]); all_fy.append(fy[own]); all_z.append(bl[own])
        all_gnr.append(gnr[own])
        all_rank.append(np.full(own.sum(), r))
        all_local.append(np.where(own)[0])
        ds.close()
    all_fx = np.concatenate(all_fx); all_fy = np.concatenate(all_fy)
    all_z = np.concatenate(all_z); all_rank = np.concatenate(all_rank)
    all_gnr = np.concatenate(all_gnr); all_local = np.concatenate(all_local)
    print(f'Total owned cells: {len(all_fx)}')

    # Find target cells: bl > +5m AND within 1.5km of 13162 AND in lat band 37.99-38.00
    mlat = 111000 * np.cos(np.radians(CENTER_LAT))
    dx_m = (all_fx - CENTER_LON) * mlat
    dy_m = (all_fy - CENTER_LAT) * 111000
    dist_m = np.sqrt(dx_m**2 + dy_m**2)

    target = (
        (all_z > BL_LAND_THRESH) &
        (dist_m < TARGET_RADIUS_M) &
        (all_fy >= LAT_MIN) &
        (all_fy <= LAT_MAX)
    )
    print(f'Target cells (bl>{BL_LAND_THRESH}m, dist<{TARGET_RADIUS_M}m, lat [{LAT_MIN}, {LAT_MAX}]): {target.sum()}')
    if target.sum() == 0:
        print('No cells match — aborting')
        return

    # Build a set of global node numbers to modify
    target_gnr_set = set(int(g) for g in all_gnr[target])
    print(f'  unique globalnr: {len(target_gnr_set)}')

    # Plot before
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    # Subset 2km for plotting
    near = dist_m < 2000
    sc = axes[0].scatter(all_fx[near], all_fy[near], c=all_z[near], s=20,
                          cmap='RdBu_r', vmin=-25, vmax=15, edgecolor='k', linewidth=0.1)
    axes[0].scatter(CENTER_LON, CENTER_LAT, marker='X', s=200, c='lime',
                     edgecolor='black', linewidth=2, label='cell 13162')
    # Mark target cells
    axes[0].scatter(all_fx[target], all_fy[target], facecolor='none',
                     edgecolor='red', s=60, linewidth=1.5,
                     label=f'to be opened ({target.sum()})')
    axes[0].legend()
    axes[0].set_title('Before: red circles will be set to bl=-2m')
    axes[0].set_aspect(1 / np.cos(np.radians(CENTER_LAT)))
    axes[0].set_xlabel('lon'); axes[0].set_ylabel('lat')
    plt.colorbar(sc, ax=axes[0], shrink=0.85, label='bl [m]')

    # After view (simulate)
    new_z_plot = all_z.copy()
    new_z_plot[target] = NEW_BL
    sc2 = axes[1].scatter(all_fx[near], all_fy[near], c=new_z_plot[near], s=20,
                           cmap='RdBu_r', vmin=-25, vmax=15, edgecolor='k', linewidth=0.1)
    axes[1].scatter(CENTER_LON, CENTER_LAT, marker='X', s=200, c='lime',
                     edgecolor='black', linewidth=2)
    axes[1].set_title(f'After: opened cells now bl={NEW_BL}m (shallow but wet)')
    axes[1].set_aspect(1 / np.cos(np.radians(CENTER_LAT)))
    axes[1].set_xlabel('lon'); axes[1].set_ylabel('lat')
    plt.colorbar(sc2, ax=axes[1], shrink=0.85, label='bl [m]')
    plt.tight_layout()
    plt.savefig(args.plot, dpi=140, bbox_inches='tight')
    print(f'Saved {args.plot}')

    # Apply modifications to each rank file
    for f in files:
        out_f = out_dir / f.name
        shutil.copy(f, out_f)
        ds = nc.Dataset(out_f, 'r+')
        gnr = np.asarray(ds.variables['mesh2d_netelem_globalnr'][:])
        fz = np.asarray(ds.variables['mesh2d_face_z'][:])
        modified = 0
        for li in range(len(gnr)):
            if int(gnr[li]) in target_gnr_set:
                fz[li] = NEW_BL
                modified += 1
        ds.variables['mesh2d_face_z'][:] = fz
        ds.close()
        print(f'  {f.name}: modified {modified} cells')


if __name__ == '__main__':
    main()
