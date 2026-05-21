"""Smooth bathymetry locally around cell 13162 (offshore NW shelf step) in
all 8 per-rank net.nc files. Goal: damp the -19m -> -9m gradient that
causes velocity propagation in continuation runs.

Approach:
  - Aggregate face_z + face_x/y from all 8 rank net.nc into a global map
    (using mesh2d_netelem_globalnr)
  - For cells in TARGET_RADIUS (1000m) around (12.0434, 38.0003): replace
    face_z with a Gaussian-weighted average of all global cells within
    SMOOTH_RADIUS (300m), sigma SIGMA_M (100m)
  - Write back to per-rank net.nc (in-place on a copy)

After running, upload the modified net files to the server's model dir.

Usage:
    python scripts/smooth_bathy_local.py \\
        --in-dir data/processed/net_nodm_orig \\
        --out-dir data/processed/net_nodm_smoothed
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
TARGET_RADIUS_M = 1000.0   # cells to modify (full offshore NW shelf zone)
SMOOTH_RADIUS_M = 300.0    # neighbors used for local median
SIGMA_M = 200.0            # Gaussian sigma (controls smoothing intensity)
USE_MEDIAN = True          # if True: use median; else Gaussian average


def m_per_deg_lon(lat_deg):
    return 111000 * np.cos(np.radians(lat_deg))


def aggregate_global(in_dir):
    """Collect global cell info from all 8 ranks. Returns global_x, global_y,
    global_z (1D arrays indexed by globalnr, NaN for cells not seen)."""
    in_dir = Path(in_dir)
    net_files = sorted(in_dir.glob('Stagnone_dxy01_15m_000*_net.nc'))
    print(f'Found {len(net_files)} per-rank net files')

    # Pass 1: determine max globalnr
    max_g = 0
    for f in net_files:
        ds = nc.Dataset(f, 'r')
        gnr = np.asarray(ds.variables['mesh2d_netelem_globalnr'][:])
        max_g = max(max_g, int(gnr.max()))
        ds.close()
    n_global = max_g + 1
    print(f'  global cells: {n_global}')

    global_x = np.full(n_global, np.nan)
    global_y = np.full(n_global, np.nan)
    global_z = np.full(n_global, np.nan)

    for f in net_files:
        ds = nc.Dataset(f, 'r')
        fx = np.asarray(ds.variables['mesh2d_face_x'][:])
        fy = np.asarray(ds.variables['mesh2d_face_y'][:])
        fz = np.asarray(ds.variables['mesh2d_face_z'][:])
        gnr = np.asarray(ds.variables['mesh2d_netelem_globalnr'][:])
        # globalnr is 1-based in some Deltares conventions; let's just use as index
        # Some cells appear in multiple ranks (halo). Last write wins (same value anyway).
        for li, gi in enumerate(gnr):
            gi = int(gi)
            global_x[gi] = fx[li]
            global_y[gi] = fy[li]
            global_z[gi] = fz[li]
        ds.close()
    valid = ~np.isnan(global_x)
    print(f'  cells with valid x: {valid.sum()} / {n_global}')
    return global_x, global_y, global_z


def find_target_and_smooth(global_x, global_y, global_z):
    """Identify cells in TARGET_RADIUS, compute Gaussian-smoothed face_z."""
    mlat = m_per_deg_lon(CENTER_LAT)
    dx_m = (global_x - CENTER_LON) * mlat
    dy_m = (global_y - CENTER_LAT) * 111000
    dist_m = np.sqrt(dx_m ** 2 + dy_m ** 2)

    target_mask = (dist_m < TARGET_RADIUS_M) & ~np.isnan(global_z)
    smooth_mask = (dist_m < TARGET_RADIUS_M + SMOOTH_RADIUS_M) & ~np.isnan(global_z)
    print(f'  target cells (within {TARGET_RADIUS_M}m): {target_mask.sum()}')
    print(f'  smoothing pool cells (within {TARGET_RADIUS_M + SMOOTH_RADIUS_M}m): {smooth_mask.sum()}')

    # Coordinates in m relative to center
    pool_x = dx_m[smooth_mask]
    pool_y = dy_m[smooth_mask]
    pool_z = global_z[smooth_mask]

    # Restrict to offshore cells only (bl < -5m), and pool to similar regime
    offshore_mask = global_z < -5.0
    target_mask = target_mask & offshore_mask

    # Re-build pool with offshore filter
    pool_offshore = offshore_mask[smooth_mask]
    pool_x_o = pool_x[pool_offshore]
    pool_y_o = pool_y[pool_offshore]
    pool_z_o = pool_z[pool_offshore]

    DELTA_CLIP = 4.0  # max absolute change in bl

    new_z = global_z.copy()
    n_clipped = 0
    for gi in np.where(target_mask)[0]:
        cx, cy = dx_m[gi], dy_m[gi]
        d2 = (pool_x_o - cx) ** 2 + (pool_y_o - cy) ** 2
        within = d2 < SMOOTH_RADIUS_M ** 2
        if within.sum() < 3:
            continue
        if USE_MEDIAN:
            target_z = float(np.median(pool_z_o[within]))
        else:
            w = np.exp(-d2[within] / (2 * SIGMA_M ** 2))
            w /= w.sum()
            target_z = float(np.dot(w, pool_z_o[within]))
        # Clip delta
        orig_z = global_z[gi]
        if abs(target_z - orig_z) > DELTA_CLIP:
            target_z = orig_z + np.sign(target_z - orig_z) * DELTA_CLIP
            n_clipped += 1
        new_z[gi] = target_z
    print(f'  cells with |Δbl| clipped to {DELTA_CLIP}m: {n_clipped}/{target_mask.sum()}')
    return new_z, target_mask, smooth_mask


def write_back(in_dir, out_dir, new_global_z):
    in_dir, out_dir = Path(in_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(in_dir.glob('Stagnone_dxy01_15m_000*_net.nc')):
        out_f = out_dir / f.name
        shutil.copy(f, out_f)
        ds = nc.Dataset(out_f, 'r+')
        gnr = np.asarray(ds.variables['mesh2d_netelem_globalnr'][:])
        fz = np.asarray(ds.variables['mesh2d_face_z'][:])
        # Update fz from new global z
        for li, gi in enumerate(gnr):
            gi = int(gi)
            if not np.isnan(new_global_z[gi]):
                fz[li] = new_global_z[gi]
        ds.variables['mesh2d_face_z'][:] = fz
        ds.close()
        print(f'  wrote {out_f.name}')


def plot_before_after(global_x, global_y, global_z, new_global_z, target_mask, out_png):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    delta = new_global_z - global_z
    mlat = m_per_deg_lon(CENTER_LAT)
    dx_m = (global_x - CENTER_LON) * mlat
    dy_m = (global_y - CENTER_LAT) * 111000

    valid = ~np.isnan(global_z)
    in_zone = (dx_m ** 2 + dy_m ** 2) < (TARGET_RADIUS_M + SMOOTH_RADIUS_M) ** 2

    for ax, data, title, cmap, vmin, vmax in [
        (axes[0], global_z[valid & in_zone], 'Before', 'terrain_r', -25, -5),
        (axes[1], new_global_z[valid & in_zone], 'After (smoothed)', 'terrain_r', -25, -5),
        (axes[2], delta[valid & in_zone], 'Delta (after - before)', 'RdBu_r', -3, 3),
    ]:
        m = valid & in_zone
        sc = ax.scatter(global_x[m], global_y[m], c=data, s=30,
                        cmap=cmap, vmin=vmin, vmax=vmax, edgecolor='k', linewidth=0.2)
        ax.scatter(CENTER_LON, CENTER_LAT, marker='X', s=200, c='lime', edgecolor='k', linewidth=1.5)
        ax.set_xlabel('lon')
        ax.set_ylabel('lat')
        ax.set_title(title)
        ax.set_aspect(1/np.cos(np.radians(CENTER_LAT)))
        plt.colorbar(sc, ax=ax, shrink=0.8)
    plt.tight_layout()
    plt.savefig(out_png, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'  saved diagnostic plot {out_png}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--in-dir', required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--plot', default='figures/bathy_smoothing.png')
    args = p.parse_args()

    print('== aggregating per-rank net.nc files ==')
    gx, gy, gz = aggregate_global(args.in_dir)

    print('== smoothing target region ==')
    new_gz, target_mask, smooth_mask = find_target_and_smooth(gx, gy, gz)

    # Summary statistics
    diff = new_gz - gz
    diff_target = diff[target_mask]
    print(f'  Δbl stats in target zone: '
          f'mean={diff_target.mean():+.3f}  '
          f'max={np.abs(diff_target).max():.3f}  '
          f'min={diff_target.min():+.3f}  max={diff_target.max():+.3f}')
    print(f'  cell 13162 before: bl={gz[13162]:.3f}, after: bl={new_gz[13162]:.3f} '
          f'(Δ {new_gz[13162]-gz[13162]:+.3f})')

    print('== plotting before/after ==')
    plot_before_after(gx, gy, gz, new_gz, target_mask, args.plot)

    print('== writing modified net.nc files ==')
    write_back(args.in_dir, args.out_dir, new_gz)

    print('\nDone.')


if __name__ == '__main__':
    main()
