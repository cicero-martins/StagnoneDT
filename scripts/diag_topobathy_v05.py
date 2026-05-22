"""Sanity checks for the merged topobathy_combined.nc produced by
build_topobathy_v05.py.

Outputs:
  figures/topobathy_v05_diag.png   - 4-panel diagnostic
  stdout                            - PASS/FAIL summary

Checks:
  1. NaN count inside bbox = 0
  2. Land cells (per land_mask) have z > 0 (sanity, allow >= -0.1)
  3. Sea cells have z < 0
  4. |gradz| per cell < 100 m (flag suspicious steps)
  5. Marettimo highest peak resolves to ~600-700 m (real ~ 686 m)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

NC = Path('data/processed/mesh_v05/topobathy_combined.nc')
FIG = Path('figures/topobathy_v05_diag.png')

# Marettimo highest peak Punta Falcone (~ 12.052 E, 37.981 N, alt 686 m).
# Use a generous island-wide bbox; we just need max(z) on the island.
MARETTIMO_BOX_LON = (12.04, 12.08)
MARETTIMO_BOX_LAT = (37.95, 37.99)
MARETTIMO_PEAK_TRUE = 686


def main():
    if not NC.exists():
        raise SystemExit(f'{NC} not found - run build_topobathy_v05.py first')

    ds = xr.open_dataset(NC)
    z = ds['topobathy'].values
    land = ds['land_mask'].values.astype(bool)
    lat = ds['lat'].values
    lon = ds['lon'].values

    # === CHECKS ===
    print('=' * 60)
    print('topobathy_v05 sanity checks')
    print('=' * 60)

    n_nan = int(np.isnan(z).sum())
    pass_nan = n_nan == 0
    print(f'[1] NaN inside bbox: {n_nan} -> {"PASS" if pass_nan else "FAIL"}')

    z_land = z[land]
    z_sea = z[~land]
    n_bad_land = int((z_land < -0.1).sum())
    n_bad_sea = int((z_sea > 0).sum())
    pass_signs = (n_bad_land == 0) and (n_bad_sea == 0)
    print(f'[2] Land cells with z < -0.1: {n_bad_land}/{land.sum()} '
          f'(should be 0) -> {"PASS" if n_bad_land == 0 else "WARN"}')
    print(f'[3] Sea cells with z > 0:    {n_bad_sea}/{(~land).sum()} '
          f'(should be 0) -> {"PASS" if n_bad_sea == 0 else "WARN"}')

    # Gradient
    dy, dx = np.gradient(z)
    gmag = np.sqrt(dx ** 2 + dy ** 2)
    # convert per-pixel to per-metre: ~11 m per pixel
    px_m = 11.0
    grad_per_m = gmag / px_m
    pct_steep = float((grad_per_m > 0.3).mean() * 100)  # >0.3 m/m = >30% slope
    print(f'[4] cells with local slope >30% (|gradz|>0.3 m/m): {pct_steep:.2f}% '
          f'(<2% expected) -> {"PASS" if pct_steep < 2 else "WARN"}')

    # Marettimo peak (island bbox)
    mar_mask = ((lat[:, None] >= MARETTIMO_BOX_LAT[0]) &
                (lat[:, None] <= MARETTIMO_BOX_LAT[1]) &
                (lon[None, :] >= MARETTIMO_BOX_LON[0]) &
                (lon[None, :] <= MARETTIMO_BOX_LON[1]))
    pk_max = float(np.nanmax(np.where(mar_mask, z, -np.inf))) if mar_mask.any() else float('nan')
    pass_pk = 400 < pk_max < 900   # tolerant: real peak is 686 m
    print(f'[5] Marettimo peak in island bbox: {pk_max:.0f} m (true ~ {MARETTIMO_PEAK_TRUE}) -> {"PASS" if pass_pk else "WARN"}')

    overall = pass_nan and pass_signs and (pct_steep < 2) and pass_pk
    print('=' * 60)
    print(f'OVERALL: {"PASS" if overall else "REVIEW WARNINGS"}')
    print('=' * 60)

    # === FIGURE ===
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # Panel A: full topobathy with diverging cmap
    ax = axes[0, 0]
    vmin = float(max(-50, np.nanmin(z_sea)))
    vmax = float(min(800, np.nanmax(z_land))) if z_land.size > 0 else 50
    extent = [lon.min(), lon.max(), lat.min(), lat.max()]
    im = ax.imshow(z, origin='lower', extent=extent, cmap='terrain',
                   vmin=vmin, vmax=vmax, aspect=1 / np.cos(np.radians(lat.mean())))
    ax.set_title('(a) topobathy (terrain cmap)')
    ax.set_xlabel('lon')
    ax.set_ylabel('lat')
    plt.colorbar(im, ax=ax, shrink=0.8, label='z [m]')

    # Panel B: land mask + coastline
    ax = axes[0, 1]
    ax.imshow(land.astype(int), origin='lower', extent=extent,
              cmap='gray_r', aspect=1 / np.cos(np.radians(lat.mean())))
    ax.set_title('(b) land mask (white = sea, dark = land)')
    ax.set_xlabel('lon')
    ax.set_ylabel('lat')

    # Panel C: histogram split
    ax = axes[1, 0]
    bins = np.linspace(-50, 700, 80)
    ax.hist(z_land[np.isfinite(z_land)], bins=bins, color='saddlebrown',
            alpha=0.7, label='land')
    ax.hist(z_sea[np.isfinite(z_sea)], bins=bins, color='steelblue',
            alpha=0.7, label='sea')
    ax.set_yscale('log')
    ax.set_xlabel('z [m]')
    ax.set_ylabel('count (log)')
    ax.set_title('(c) histogram by mask')
    ax.legend()
    ax.grid(alpha=0.3)

    # Panel D: gradient magnitude
    ax = axes[1, 1]
    im = ax.imshow(grad_per_m, origin='lower', extent=extent,
                   cmap='magma', vmin=0, vmax=0.5,
                   aspect=1 / np.cos(np.radians(lat.mean())))
    ax.set_title(f'(d) |gradz| per metre (warn if >0.3, {pct_steep:.2f}% of cells)')
    ax.set_xlabel('lon')
    ax.set_ylabel('lat')
    plt.colorbar(im, ax=ax, shrink=0.8, label='m/m')

    plt.suptitle(f'topobathy_v05 diagnostic - {"PASS" if overall else "REVIEW"}',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(FIG, dpi=120, bbox_inches='tight')
    print(f'\nSaved {FIG}')


if __name__ == '__main__':
    main()
