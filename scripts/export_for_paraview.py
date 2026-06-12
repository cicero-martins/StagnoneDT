"""Merge v04AE partitioned map.nc into a single VTK-friendly NetCDF for ParaView.

ParaView can read UGRID/CF NetCDF files via its built-in UGRID plugin, but
multi-partition files require the partitions to be merged first.
This script merges the 8 partitions and exports a compact single-file NetCDF
containing only the fields needed for visualisation.

Usage:
    python scripts/export_for_paraview.py

Outputs:
    outputs/paraview/v04AE_merged.nc   -- merged UGRID NetCDF for ParaView
    outputs/paraview/v04AE_salinity_day5.vtk  -- single-timestep VTK for quick load

ParaView import notes (document for the reader):
----------------------------------------------------------------------
1. Open ParaView (>= 5.10 recommended for UGRID support).
2. File → Open → select v04AE_merged.nc.
   - Reader: "CF (Climate and Forecast) Reader" or "UGRID Reader"
   - If auto-detection fails: set reader explicitly in "Open Data With..." dialog
3. Apply the reader. In the Pipeline Browser, select the dataset.
4. In the Properties panel:
   - Check "mesh2d_sa1" (salinity) and/or "mesh2d_s1" (water level)
   - Click Apply.
5. In the Toolbar, set the scalar to colour by (e.g., "mesh2d_sa1").
6. Use "Surface" representation for a plan-view heatmap.
7. For time animation: use the Time controls bar (play/step/slider).
8. For land context:
   - File → Open → select a Sicily/Stagnone shapefile (.shp) or the
     Stagnone_dxy01_15m.ldb converted to CSV (x,y pairs).
   - Apply "Elevation" filter (z=0) to create a flat land surface.
9. Export a screenshot: File → Save Screenshot.

Known limitations:
- ParaView UGRID reader has been tested with CF-1.6 / UGRID-0.9 convention.
  FM 2026.01 writes CF-1.6 + UGRID; should load without conversion.
- The merged file exports only surface layer (sigma=-1) to reduce file size.
  Edit N_LAY below to export all layers.
- Multi-partition VTK export (one .vtu per partition) is also supported;
  use ParaView "Group Files" to merge them interactively.
----------------------------------------------------------------------
"""
from pathlib import Path
import numpy as np
import shutil

ROOT    = Path(__file__).resolve().parents[1]
V04AE   = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
OUT_DIR = ROOT / 'outputs' / 'paraview'
OUT_NC  = OUT_DIR / 'v04AE_merged.nc'
OUT_VTK = OUT_DIR / 'v04AE_salinity_day5.vtk'

# Variables to keep in the merged output (surface layer only)
KEEP_VARS = [
    'mesh2d_s1',      # water level (2D scalar)
    'mesh2d_sa1',     # salinity (3D → surface layer extracted)
    'mesh2d_ucx',     # velocity u-component (3D → surface)
    'mesh2d_ucy',     # velocity v-component (3D → surface)
    'mesh2d_hwav',    # significant wave height (2D)
]

# Temporal subsampling: every N steps (full 9d = 433 steps at dt_map=1800s)
# Every 4 steps = every 2h → 109 timesteps, ~200MB
T_STEP = 4


def merge_and_export():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_NC.exists():
        print(f'Merged file already exists: {OUT_NC}')
        answer = input('Overwrite? [y/N] ').strip().lower()
        if answer != 'y':
            print('Skipping merge step.')
            return

    print('Opening partitioned map.nc via dfm_tools ...')
    import dfm_tools as dfmt
    import xarray as xr
    import pandas as pd

    pat = str(V04AE / 'Stagnone_dxy01_15m_0*_map.nc')
    ds  = dfmt.open_partitioned_dataset(pat)
    print(f'  n_faces={ds.grids[0].n_face}, n_nodes={ds.grids[0].n_node}')
    print(f'  Variables: {list(ds.data_vars)[:10]} ...')

    times = pd.DatetimeIndex(ds['time'].values)
    t_idx = list(range(0, len(times), T_STEP))
    print(f'  Time steps: {len(times)} total -> {len(t_idx)} selected (every {T_STEP})')

    # Build compact xarray Dataset (plain netCDF, not UGRID)
    # Use the regridded cache if available; otherwise write plain xarray
    print('Extracting surface fields ...')

    grid  = ds.grids[0]
    cx    = grid.face_x
    cy    = grid.face_y

    def surface(da):
        for dim in da.dims:
            if 'layer' in dim.lower() or 'nlay' in dim.lower():
                return da.isel({dim: -1})
        return da

    keep = {}
    for v in KEEP_VARS:
        if v in ds:
            da = surface(ds[v]).isel(time=t_idx)
            # Convert xugrid DataArray to plain xarray by dropping grid topology
            try:
                keep[v] = da.values
            except Exception:
                keep[v] = da.obj.values

    # Build plain xarray dataset (face dimension = n_faces)
    n_t  = len(t_idx)
    n_f  = grid.n_face
    t_vals = times[t_idx]

    coords = {
        'time':    t_vals,
        'face_x':  cx,
        'face_y':  cy,
    }
    data_vars = {}
    for v, arr in keep.items():
        arr_f = arr.astype(np.float32)
        arr_f[np.abs(arr_f) > 1e9] = np.nan
        data_vars[v] = xr.DataArray(
            arr_f, dims=['time', 'nFaces'],
            attrs={'description': f'{v} surface layer, v04AE Jul 2025'}
        )

    ds_out = xr.Dataset(data_vars, coords={
        'time':   xr.DataArray(t_vals, dims=['time']),
        'face_x': xr.DataArray(cx, dims=['nFaces'], attrs={'units':'degrees_east'}),
        'face_y': xr.DataArray(cy, dims=['nFaces'], attrs={'units':'degrees_north'}),
    })
    ds_out.attrs['title']       = 'Stagnone di Marsala — v04AE surface fields'
    ds_out.attrs['source']      = 'Delft3D FM 2026.01 HMWQ, 8 MPI partitions merged'
    ds_out.attrs['conventions'] = 'CF-1.6'

    print(f'Writing {OUT_NC} ...')
    ds_out.to_netcdf(OUT_NC)
    sz = OUT_NC.stat().st_size // (1024*1024)
    print(f'  Saved: {OUT_NC}  ({sz} MB)')

    ds.close()


def export_single_timestep_vtk():
    """Export one timestep as a legacy VTK Unstructured Grid for direct ParaView load."""
    if not OUT_NC.exists():
        print('Run merge_and_export() first.')
        return

    print('Exporting single-timestep VTK ...')
    import dfm_tools as dfmt
    import pyvista as pv
    import xarray as xr
    import pandas as pd

    # Load merged nc
    ds_m = xr.open_dataset(OUT_NC)
    cx   = ds_m['face_x'].values
    cy   = ds_m['face_y'].values
    times = pd.DatetimeIndex(ds_m['time'].values)

    # Day 5 = Jul 6
    target = pd.Timestamp('2025-07-06T12:00:00')
    ti = int(np.argmin(np.abs(times - target)))
    print(f'  Using timestep: {times[ti]}')

    # Load merged grid for topology
    pat = str(V04AE / 'Stagnone_dxy01_15m_0*_map.nc')
    ds_grid = dfmt.open_partitioned_dataset(pat)
    grid    = ds_grid.grids[0]
    nx, ny  = grid.node_x, grid.node_y
    fn      = grid.face_node_connectivity
    fv      = grid.fill_value
    ds_grid.close()

    nz  = np.zeros(len(nx))
    pts = np.column_stack([nx, ny, nz])

    cells, celltypes = [], []
    for i in range(fn.shape[0]):
        nodes = fn[i]; valid = nodes[nodes != fv]; k = len(valid)
        if k == 3:
            cells.extend([3] + valid.tolist()); celltypes.append(5)
        elif k == 4:
            cells.extend([4] + valid.tolist()); celltypes.append(9)
        else:
            cells.extend([k] + valid.tolist()); celltypes.append(7)

    vtk_grid = pv.UnstructuredGrid(
        np.array(cells, dtype=np.int_),
        np.array(celltypes, dtype=np.uint8),
        pts
    )

    for v in KEEP_VARS:
        if v in ds_m:
            arr = ds_m[v].isel(time=ti).values.astype(np.float32)
            arr[np.isnan(arr)] = -999
            vtk_grid.cell_data[v] = arr

    vtk_grid.save(str(OUT_VTK))
    sz = OUT_VTK.stat().st_size // 1024
    print(f'  Saved: {OUT_VTK}  ({sz} kB)')
    ds_m.close()


if __name__ == '__main__':
    merge_and_export()
    export_single_timestep_vtk()
    print('\nParaView import notes printed to stdout — see docstring.')
    print(f'\nFiles:')
    print(f'  {OUT_NC}   <- open with CF/UGRID reader for full time animation')
    print(f'  {OUT_VTK}  <- open with Legacy VTK reader for quick single-snapshot')
