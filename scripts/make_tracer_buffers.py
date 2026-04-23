"""Generate XYZ tracer initialization files from circular buffers around point sources.

For each (lon, lat, radius_m, name) entry, writes an XYZ file matching the format
of `model/dflowfm_v03c/lagoon_tracer_init.xyz`: one row per FM mesh node, value
`1.0` inside the buffer and `0.0` outside. WGS84 lon/lat columns match the mesh
so FM's `dataFileType=sample` + `averagingType=mean` interpolation picks up the
patch without further adjustments.

Buffer distance is computed in UTM 33N (EPSG:32633), which is accurate to ~1 m
at Stagnone's latitude. The ~100 m error you'd get from `1 deg ~ 111 km` would
matter for a 500 m radius.

Usage:
    python scripts/make_tracer_buffers.py

Outputs are written under `model/dflowfm_v03d/` (directory created if missing).
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import xarray as xr
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MESH_NC = PROJECT_ROOT / 'model' / 'dflowfm_v03c' / 'Stagnone_dxy01_15m_net.nc'
OUT_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v03d'

# (name, lon, lat, radius_m) — one entry per tracer patch.
BUFFERS = [
    ('turbid_airport',  12.468, 37.917, 500.0),
    ('turbid_saltpans', 12.507, 37.997, 500.0),
]


def load_mesh_nodes(nc_path: Path) -> tuple[np.ndarray, np.ndarray]:
    ds = xr.open_dataset(nc_path)
    # UGRID convention for Delft3D FM
    x = np.asarray(ds['mesh2d_node_x'].values, dtype=float)
    y = np.asarray(ds['mesh2d_node_y'].values, dtype=float)
    ds.close()
    if x.shape != y.shape or x.ndim != 1:
        raise RuntimeError(f'Unexpected mesh shape: x={x.shape}, y={y.shape}')
    return x, y


def buffer_mask(lon_nodes: np.ndarray, lat_nodes: np.ndarray,
                center_lon: float, center_lat: float, radius_m: float) -> np.ndarray:
    """Boolean mask of nodes within radius_m of (center_lon, center_lat).

    All geometry in UTM 33N (EPSG:32633). Inputs in WGS84 degrees.
    """
    to_utm = Transformer.from_crs(4326, 32633, always_xy=True)
    cx, cy = to_utm.transform(center_lon, center_lat)
    nx, ny = to_utm.transform(lon_nodes, lat_nodes)
    d2 = (nx - cx) ** 2 + (ny - cy) ** 2
    return d2 <= radius_m * radius_m


def write_xyz(lon: np.ndarray, lat: np.ndarray, values: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Match the formatting of lagoon_tracer_init.xyz: 6 decimals for coords, 3 for value.
    with path.open('w', encoding='ascii') as f:
        for lo, la, v in zip(lon, lat, values):
            f.write(f'{lo:.6f} {la:.6f} {v:.3f}\n')


def main() -> int:
    if not MESH_NC.exists():
        sys.exit(f'Mesh file not found: {MESH_NC}')

    lon, lat = load_mesh_nodes(MESH_NC)
    print(f'Loaded {len(lon)} mesh nodes from {MESH_NC.name}')

    for name, c_lon, c_lat, radius in BUFFERS:
        mask = buffer_mask(lon, lat, c_lon, c_lat, radius)
        n_inside = int(mask.sum())
        if n_inside == 0:
            print(f'  [FAIL] {name}: 0 nodes inside {radius:.0f}-m buffer '
                  f'at ({c_lon}, {c_lat}). Check center coords / mesh coverage.')
        else:
            print(f'  [ok]   {name}: {n_inside} node(s) inside {radius:.0f}-m '
                  f'buffer at ({c_lon}, {c_lat})')
        values = np.where(mask, 1.0, 0.0)
        out_path = OUT_DIR / f'{name}_init.xyz'
        write_xyz(lon, lat, values, out_path)
        print(f'         wrote {out_path.relative_to(PROJECT_ROOT)}  '
              f'({len(lon)} rows)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
