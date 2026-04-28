"""Regenerate SWAN .dep bathymetry files from the FM unstructured mesh.

The original outer SWAN bathymetry was sourced from an external dataset (likely
GEBCO or EMODnet) with a 500-m clamp on offshore depths and shows up to ~100 m
disagreement against the FM mesh in the same physical cells. The inner SWAN
bathy was already FM-derived and matches well, but is regenerated here too for
reproducibility and to keep both grids on a single, explicit source.

Both .dep files are written at the cell-corner positions of the existing
SWAN grids (inferred from the .grd headers + extents in the existing .dep
files). FM bathy convention: z is bedlevel, negative below MSL. SWAN
convention: depth, positive below MSL. Cells where FM is above MSL (z > 0)
or where FM does not cover (extrapolation outside hull) are marked with
the SWAN dry/missing flag -99.

Usage:
    python scripts/regen_swan_bathy_from_fm.py <model_dir>

Example:
    python scripts/regen_swan_bathy_from_fm.py model/dflowfm_v03d

Default <model_dir> is model/dflowfm_v03d.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import scipy.interpolate as si
import xarray as xr

# Grid coord conventions, locked to the existing .grd / .dep headers.
# Both grids are spherical (lon, lat) in the WGS84 frame.
GRID_SPECS = {
    'outer': {
        'lon': (11.9500, 12.5688, 70),   # corners: lon_min, lon_max, n_corners
        'lat': (37.6900, 38.0716, 55),
        'dep_filename': 'swan_bathy_outer.dep',
    },
    'inner': {
        'lon': (12.4005, 12.5205, 122),
        'lat': (37.8000, 38.0200, 222),
        'dep_filename': 'swan_bathy.dep',
    },
}

DRY_FLAG = -99.0


def regen_bathy(net_file: Path, model_dir: Path) -> dict[str, dict[str, float]]:
    """Regenerate both SWAN .dep files in model_dir/wave/ from the FM net file.

    Returns a stats dict per grid for downstream reporting.
    """
    print(f'Reading FM mesh from {net_file} ...')
    ds = xr.open_dataset(net_file)
    fmx = ds['mesh2d_node_x'].values
    fmy = ds['mesh2d_node_y'].values
    fmz = ds['mesh2d_node_z'].values
    valid = ~np.isnan(fmz) & ~np.isnan(fmx) & ~np.isnan(fmy)
    fmx, fmy, fmz = fmx[valid], fmy[valid], fmz[valid]
    print(f'  {valid.sum()} valid nodes (dropped {(~valid).sum()} NaN), '
          f'z range [{fmz.min():.2f}, {fmz.max():.2f}], median {np.median(fmz):.2f} m')

    # Linear interpolator over the FM mesh in (lon, lat). Outside the convex
    # hull, the interpolator returns NaN — those cells go to DRY_FLAG.
    interp = si.LinearNDInterpolator(np.column_stack([fmx, fmy]), fmz)

    wave_dir = model_dir / 'wave'
    wave_dir.mkdir(parents=True, exist_ok=True)

    stats = {}
    for grid_name, spec in GRID_SPECS.items():
        lons = np.linspace(*spec['lon'])
        lats = np.linspace(*spec['lat'])
        LON, LAT = np.meshgrid(lons, lats)

        z = interp(LON, LAT)
        depth = -z
        # Dry flag where FM has no data (NaN) or is above MSL (z >= 0 -> depth <= 0)
        depth = np.where(np.isnan(depth) | (depth <= 0), DRY_FLAG, depth)

        out_path = wave_dir / spec['dep_filename']
        write_swan_dep(depth, out_path)

        valid = depth[depth != DRY_FLAG]
        stats[grid_name] = {
            'shape': depth.shape,
            'n_valid': int(len(valid)),
            'n_dry': int((depth == DRY_FLAG).sum()),
            'min_depth': float(valid.min()) if len(valid) else float('nan'),
            'max_depth': float(valid.max()) if len(valid) else float('nan'),
            'median_depth': float(np.median(valid)) if len(valid) else float('nan'),
            'path': str(out_path),
        }
        print(f'  {grid_name} -> {out_path}: shape {depth.shape}, '
              f'{len(valid)} valid, {(depth == DRY_FLAG).sum()} dry, '
              f'depth median {stats[grid_name]["median_depth"]:.2f} m')

    return stats


def write_swan_dep(depth: np.ndarray, path: Path, ncols_per_line: int = 12) -> None:
    """Write a 2D depth array to a SWAN .dep file in the standard 12-col format."""
    ny, nx = depth.shape
    with open(path, 'w') as f:
        for j in range(ny):
            for i in range(nx):
                f.write(f' {depth[j, i]:16.7e}')
                if (i + 1) % ncols_per_line == 0:
                    f.write('\n')
            if nx % ncols_per_line != 0:
                f.write('\n')


def main():
    model_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('model/dflowfm_v03d')
    net_file = model_dir / 'Stagnone_dxy01_15m_net.nc'
    if not net_file.exists():
        raise FileNotFoundError(
            f'FM net file not found at {net_file} — pass the model dir as arg 1.'
        )
    regen_bathy(net_file, model_dir)


if __name__ == '__main__':
    main()
