"""Diagnose whether mesh v05 has eliminated the structural choke at the former
cell 13162 (offshore NW of Marettimo).

Compares v04AE_nodm (legacy, has choke) vs v05 in the strip:
    lat  in  [37.95, 38.07], lon  in  [12.02, 12.10]

Three quantitative checks + PASS/FAIL summary:

  [1] Cell density along the meridian - sharp transition near Marettimo NE
      shoulder indicates structural choke. v05 should be smooth.
  [2] |gradbl| (bedlevel gradient) - flag cells with |gradbl| > 3 m/cell.
  [3] Edge length ratio to nearest neighbours - flag cells with ratio > 3.

Pass criteria for v05:
  - max |gradbl| in corridor < 3 m/cell
  - no cell with edge ratio > 3
  - cell density transition gradual (no >2x step between adjacent latitudes)

Outputs:
  figures/mesh_v05_choke_diagnostic.png
  stdout PASS/FAIL summary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

DEFAULT_V04 = 'data/processed/net_nodm_orig/Stagnone_dxy01_15m_*_net.nc'
DEFAULT_V05 = 'data/processed/mesh_v05/Stagnone_v05_net.nc'
DEFAULT_FIG = 'figures/mesh_v05_choke_diagnostic.png'

CORRIDOR_LON = (12.02, 12.10)
CORRIDOR_LAT = (37.95, 38.07)
CENTER_LON, CENTER_LAT = 12.0434, 38.0003   # former cell 13162

GRAD_THRESHOLD = 3.0       # m per cell
EDGE_RATIO_THRESHOLD = 3.0
DENSITY_STEP_THRESHOLD = 2.0


def load_net_files(pattern_or_path):
    """Load mesh from either a glob pattern (partitioned) or a single net.nc.
    Returns (face_x, face_y, face_z, edge_x_pairs, edge_y_pairs) - flat arrays.
    """
    paths = sorted(Path('.').glob(pattern_or_path) if any(c in pattern_or_path for c in '*?[]')
                   else [Path(pattern_or_path)])
    if not paths or (len(paths) == 1 and not paths[0].exists()):
        return None
    all_fx, all_fy, all_fz = [], [], []
    all_ex0, all_ey0, all_ex1, all_ey1 = [], [], [], []
    for p in paths:
        ds = xr.open_dataset(p)
        # Tolerant to different variable names
        for name in ('mesh2d_face_x', 'mesh2d_face_x'):
            if name in ds.variables:
                fx = ds[name].values
                break
        fy = ds['mesh2d_face_y'].values
        fz = ds['mesh2d_face_z'].values if 'mesh2d_face_z' in ds.variables else np.full_like(fx, np.nan)
        # If partitioned, restrict to own cells
        if 'mesh2d_netelem_domain' in ds.variables:
            rank = int(p.stem.split('_')[-2])
            dom = ds['mesh2d_netelem_domain'].values
            own = dom == rank
            fx, fy, fz = fx[own], fy[own], fz[own]
        all_fx.append(fx); all_fy.append(fy); all_fz.append(fz)
        # edge endpoints
        if 'mesh2d_edge_x' in ds.variables and 'mesh2d_edge_y' in ds.variables:
            # mesh2d_edge_nodes: (n_edges, 2) -> node indices
            if 'mesh2d_edge_nodes' in ds.variables:
                en = np.ma.asarray(ds['mesh2d_edge_nodes'].values)
                nx = np.asarray(ds['mesh2d_node_x'].values)
                ny = np.asarray(ds['mesh2d_node_y'].values)
                # Drop rows with any masked / fill value, then zero-index
                if np.ma.isMaskedArray(en):
                    bad = np.ma.getmaskarray(en).any(axis=1)
                    en = np.asarray(en.filled(-1))
                else:
                    bad = np.zeros(en.shape[0], dtype=bool)
                bad |= (en < 0).any(axis=1)
                en_keep = en[~bad].astype(np.int64)
                if en_keep.size:
                    en0 = en_keep - en_keep.min()
                    ex0 = nx[en0[:, 0]]; ey0 = ny[en0[:, 0]]
                    ex1 = nx[en0[:, 1]]; ey1 = ny[en0[:, 1]]
                    all_ex0.append(ex0); all_ey0.append(ey0); all_ex1.append(ex1); all_ey1.append(ey1)
        ds.close()
    fx = np.concatenate(all_fx); fy = np.concatenate(all_fy); fz = np.concatenate(all_fz)
    if all_ex0:
        ex0 = np.concatenate(all_ex0); ey0 = np.concatenate(all_ey0)
        ex1 = np.concatenate(all_ex1); ey1 = np.concatenate(all_ey1)
    else:
        ex0 = ey0 = ex1 = ey1 = None
    return fx, fy, fz, ex0, ey0, ex1, ey1


def in_corridor(fx, fy):
    return ((fx >= CORRIDOR_LON[0]) & (fx <= CORRIDOR_LON[1]) &
            (fy >= CORRIDOR_LAT[0]) & (fy <= CORRIDOR_LAT[1]))


def cell_density_profile(fx, fy):
    """Cells per 0.005deg lat bin within the corridor lon range."""
    mask = in_corridor(fx, fy)
    bins = np.arange(CORRIDOR_LAT[0], CORRIDOR_LAT[1] + 0.005, 0.005)
    counts, _ = np.histogram(fy[mask], bins=bins)
    centers = 0.5 * (bins[1:] + bins[:-1])
    return centers, counts


def local_gradients(fx, fy, fz):
    """For each cell in corridor, find nearest 4 neighbours and compute max |dz/d_metric|."""
    from scipy.spatial import cKDTree
    mask = in_corridor(fx, fy)
    idx_in = np.where(mask)[0]
    if len(idx_in) < 5:
        return idx_in, np.zeros(len(idx_in))
    tree = cKDTree(np.column_stack([fx, fy]))
    grads = np.zeros(len(idx_in))
    for k, i in enumerate(idx_in):
        d, j = tree.query([fx[i], fy[i]], k=5)
        # ignore self at index 0
        z_i = fz[i]
        if not np.isfinite(z_i):
            continue
        dz = np.abs(fz[j[1:]] - z_i)
        valid = np.isfinite(dz)
        if valid.any():
            grads[k] = np.nanmax(dz[valid])
    return idx_in, grads


def edge_lengths(ex0, ey0, ex1, ey1, lat_ref):
    mlat = 111000 * np.cos(np.radians(lat_ref))
    dx = (ex1 - ex0) * mlat
    dy = (ey1 - ey0) * 111000
    return np.sqrt(dx ** 2 + dy ** 2)


def edge_ratio_in_corridor(ex0, ey0, ex1, ey1):
    if ex0 is None:
        return None, None
    ex_mid = 0.5 * (ex0 + ex1)
    ey_mid = 0.5 * (ey0 + ey1)
    mask = ((ex_mid >= CORRIDOR_LON[0]) & (ex_mid <= CORRIDOR_LON[1]) &
            (ey_mid >= CORRIDOR_LAT[0]) & (ey_mid <= CORRIDOR_LAT[1]))
    lens = edge_lengths(ex0[mask], ey0[mask], ex1[mask], ey1[mask], CENTER_LAT)
    if len(lens) < 2:
        return lens, None
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([ex_mid[mask], ey_mid[mask]]))
    ratios = np.zeros(len(lens))
    for k in range(len(lens)):
        d, j = tree.query([ex_mid[mask][k], ey_mid[mask][k]], k=5)
        nb_lens = lens[j[1:]]
        if len(nb_lens) > 0 and nb_lens.min() > 0:
            ratios[k] = max(lens[k] / nb_lens.min(), nb_lens.max() / lens[k])
    return lens, ratios


def summarize(label, fx, fy, fz, ex0, ey0, ex1, ey1):
    print(f'\n=== {label} ===')
    n_total = len(fx)
    in_corr = in_corridor(fx, fy)
    n_corr = int(in_corr.sum())
    print(f'  total cells: {n_total}; cells in corridor: {n_corr}')

    # [1] density transitions
    centers, counts = cell_density_profile(fx, fy)
    nonzero = counts > 0
    if nonzero.sum() >= 2:
        cz = counts[nonzero]
        steps = np.maximum(cz[1:] / np.maximum(cz[:-1], 1),
                           cz[:-1] / np.maximum(cz[1:], 1))
        max_step = float(steps.max()) if len(steps) else 0.0
    else:
        max_step = 0.0
    print(f'  [1] density max step ratio: {max_step:.2f} (target < {DENSITY_STEP_THRESHOLD}) '
          f'-> {"PASS" if max_step < DENSITY_STEP_THRESHOLD else "FAIL"}')

    # [2] gradient
    idx_in, grads = local_gradients(fx, fy, fz)
    if len(grads) == 0:
        max_grad = 0.0
        pct_steep = 0.0
    else:
        max_grad = float(np.nanmax(grads))
        pct_steep = float((grads > GRAD_THRESHOLD).mean() * 100)
    print(f'  [2] max |dz| to nearest neighbour: {max_grad:.2f} m  '
          f'(target < {GRAD_THRESHOLD}) -> {"PASS" if max_grad < GRAD_THRESHOLD else "FAIL"}')
    print(f'      cells with |dz|>{GRAD_THRESHOLD}: {pct_steep:.1f}%')

    # [3] edge length ratio
    lens, ratios = edge_ratio_in_corridor(ex0, ey0, ex1, ey1)
    if ratios is None:
        max_ratio = float('nan')
    else:
        max_ratio = float(np.nanmax(ratios))
    print(f'  [3] max edge-length ratio: {max_ratio:.2f} '
          f'(target < {EDGE_RATIO_THRESHOLD}) -> '
          f'{"PASS" if (np.isnan(max_ratio) or max_ratio < EDGE_RATIO_THRESHOLD) else "FAIL"}')

    pass_overall = (max_step < DENSITY_STEP_THRESHOLD and
                    max_grad < GRAD_THRESHOLD and
                    (np.isnan(max_ratio) or max_ratio < EDGE_RATIO_THRESHOLD))
    print(f'  --> {label} corridor: {"PASS" if pass_overall else "FAIL"}')
    return {
        'label': label, 'centers': centers, 'counts': counts,
        'idx_in': idx_in, 'grads': grads, 'lens': lens, 'ratios': ratios,
        'max_step': max_step, 'max_grad': max_grad, 'max_ratio': max_ratio,
        'pass_overall': pass_overall, 'fx': fx, 'fy': fy, 'fz': fz,
    }


def plot_diagnostic(stats_v04, stats_v05, out_path):
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))

    # row 0: v04, row 1: v05
    for row, stats in enumerate((stats_v04, stats_v05)):
        label = stats['label']
        # Panel: cell density vs lat
        ax = axes[row, 0]
        ax.barh(stats['centers'], stats['counts'], height=0.004,
                color='steelblue' if row == 0 else 'forestgreen')
        ax.set_title(f'{label} - cell density (corridor)')
        ax.set_xlabel('cells per 0.005deg lat bin')
        ax.set_ylabel('latitude')
        ax.axhline(CENTER_LAT, color='red', ls='--', lw=1, alpha=0.7)
        ax.text(0.95, 0.05, f'max step: {stats["max_step"]:.2f}',
                transform=ax.transAxes, ha='right', va='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Panel: cells colored by bedlevel
        ax = axes[row, 1]
        fx, fy, fz = stats['fx'], stats['fy'], stats['fz']
        m = in_corridor(fx, fy)
        sc = ax.scatter(fx[m], fy[m], c=fz[m], s=15, cmap='terrain',
                        vmin=-30, vmax=10, edgecolor='none')
        ax.scatter(CENTER_LON, CENTER_LAT, marker='X', s=200, c='red',
                   edgecolor='white', lw=1.5, zorder=5)
        ax.set_aspect(1 / np.cos(np.radians(CENTER_LAT)))
        ax.set_title(f'{label} - bedlevel + former cell 13162')
        ax.set_xlabel('lon'); ax.set_ylabel('lat')
        plt.colorbar(sc, ax=ax, shrink=0.85, label='bl [m]')

        # Panel: |dz| distribution
        ax = axes[row, 2]
        if len(stats['grads']) > 0:
            ax.hist(stats['grads'], bins=40, color='salmon',
                    edgecolor='black', alpha=0.8)
            ax.axvline(GRAD_THRESHOLD, color='red', ls='--', label=f'thresh {GRAD_THRESHOLD}')
            ax.set_yscale('log')
            ax.set_xlabel('|dz| to nearest neighbour [m]')
            ax.set_ylabel('count (log)')
            ax.set_title(f'{label} - gradient hist, max={stats["max_grad"]:.1f}')
            ax.legend()
        else:
            ax.text(0.5, 0.5, 'no data', transform=ax.transAxes, ha='center')

    plt.suptitle(
        f'choke diagnostic - corridor lon{CORRIDOR_LON} lat{CORRIDOR_LAT}\n'
        f'v04 {"PASS" if stats_v04["pass_overall"] else "FAIL"}  -  '
        f'v05 {"PASS" if stats_v05["pass_overall"] else "FAIL"}',
        fontsize=14, fontweight='bold')
    plt.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=130, bbox_inches='tight')
    print(f'\nSaved {out_path}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--v04', default=DEFAULT_V04,
                   help='v04 net.nc (single or glob pattern for partitioned)')
    p.add_argument('--v05', default=DEFAULT_V05, help='v05 net.nc')
    p.add_argument('--fig', default=DEFAULT_FIG)
    args = p.parse_args()

    print(f'Loading v04 baseline from {args.v04}')
    v04 = load_net_files(args.v04)
    if v04 is None:
        print('  [skip] v04 not found - will plot v05 only.')
        stats_v04 = None
    else:
        stats_v04 = summarize('v04AE_nodm', *v04)

    print(f'\nLoading v05 from {args.v05}')
    v05 = load_net_files(args.v05)
    if v05 is None:
        print(f'  ERROR: v05 net.nc not found at {args.v05}. Run scripts/build_mesh_v05.py first.')
        sys.exit(1)
    stats_v05 = summarize('v05', *v05)

    if stats_v04 is not None:
        plot_diagnostic(stats_v04, stats_v05, args.fig)
    else:
        # plot v05 only as a degenerate diagnostic
        plot_diagnostic(stats_v05, stats_v05, args.fig)

    print('\n' + '=' * 60)
    if stats_v05['pass_overall']:
        print('OVERALL v05 corridor: PASS - proceed to bathy interp + partition.')
    else:
        print('OVERALL v05 corridor: FAIL - iterate refine_basegrid params before partition.')
    print('=' * 60)


if __name__ == '__main__':
    main()
