"""PyVista 3D visualisation of v04AE salinity with land/island context.

Renders a static 3D scene showing:
  - Model mesh cells coloured by surface salinity (day 5 of the 9-day run)
  - Topobathy background surface (WGS84 lat/lon, z = bed elevation)
  - Land mask (z >= -0.1 m cells coloured as grey terrain)

Usage:
    python scripts/pyvista_3d_viz.py

Output:
    figures/pyvista_3d_salinity_day5.png   (1920x1080 PNG)

Two approaches are available; select via APPROACH:
    'ldb'    - simple: flat z=0 land surface from the model .ldb boundary file
    'bathy'  - robust: land mask from bathy_gridded.nc topobathy DEM
"""
from pathlib import Path
import numpy as np
import xarray as xr
import pyvista as pv

ROOT   = Path(__file__).resolve().parents[1]
V04AE  = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
NETFILE = ROOT / 'model' / 'dflowfm_v04AE' / 'Stagnone_dxy01_15m_net.nc'
BATHY_NC = ROOT / 'data' / 'processed' / 'mesh_v05' / 'bathy_gridded.nc'
LDB_FILE = ROOT / 'model' / 'dflowfm_v04AE' / 'sicily2.ldb'
OUT_PNG  = ROOT / 'figures' / 'pyvista_3d_salinity_day5.png'

APPROACH = 'bathy'   # 'ldb' or 'bathy'

# Salinity rendering
SA_VMIN = 36.0
SA_VMAX = 44.0

# Day index (0-based, relative to sim start Jul 1); day 5 = Jul 6
TARGET_DAY = 5
T_HOUR = 12   # 12:00 UTC

# Domain crop for rendering
LON_CROP = (12.30, 12.60)
LAT_CROP = (37.75, 38.00)


def load_salinity_and_grid():
    """Load surface salinity + xugrid merged grid from partitioned map.nc."""
    import dfm_tools as dfmt
    import pandas as pd

    pat = str(V04AE / 'Stagnone_dxy01_15m_0*_map.nc')
    print(f'Opening map.nc: {pat}')
    ds = dfmt.open_partitioned_dataset(pat)
    grid = ds.grids[0]

    # Find surface salinity variable
    sal_var = None
    for v in ['mesh2d_sa1', 'mesh2d_s1']:
        if v in ds:
            sal_var = v
            break
    if sal_var is None:
        raise KeyError(f'No salinity variable found in {list(ds.data_vars)[:15]}')

    # Find timestep closest to TARGET_DAY + T_HOUR
    times = pd.DatetimeIndex(ds['time'].values)
    target = pd.Timestamp(f'2025-07-0{1+TARGET_DAY}T{T_HOUR:02d}:00:00')
    ti = int(np.argmin(np.abs(times - target)))
    print(f'  Selected timestep: {times[ti]}  (target {target})')

    da = ds[sal_var].isel(time=ti)
    for dim in da.dims:
        if 'layer' in dim.lower() or 'nlay' in dim.lower():
            da = da.isel({dim: -1})
            break

    sal = da.values.astype(np.float32)
    sal[sal > 1e9] = np.nan

    # Extract node coords + face-node connectivity from the merged grid
    nx  = grid.node_x.astype(np.float64)
    ny  = grid.node_y.astype(np.float64)
    fn  = grid.face_node_connectivity          # (n_faces, max_nodes_per_face)
    fv  = grid.fill_value                      # typically -999

    ds.close()
    print(f'  Salinity: min={np.nanmin(sal):.2f}  max={np.nanmax(sal):.2f} ppt  '
          f'n_cells={len(sal)}')
    return nx, ny, fn, fv, sal


def mesh_to_pyvista(nx, ny, fn, fill_value, sal):
    """Build PyVista UnstructuredGrid from xugrid node coords + face-node connectivity."""
    print('Building PyVista UnstructuredGrid ...')
    nz = np.zeros(len(nx))
    pts_3d = np.column_stack([nx, ny, nz])

    cells = []
    celltypes = []
    for i in range(fn.shape[0]):
        nodes = fn[i]
        valid = nodes[nodes != fill_value]
        k = len(valid)
        if k == 3:
            cells.extend([3] + valid.tolist())
            celltypes.append(5)   # VTK_TRIANGLE
        elif k == 4:
            cells.extend([4] + valid.tolist())
            celltypes.append(9)   # VTK_QUAD
        else:
            cells.extend([k] + valid.tolist())
            celltypes.append(7)   # VTK_POLYGON

    grid = pv.UnstructuredGrid(
        np.array(cells, dtype=np.int_),
        np.array(celltypes, dtype=np.uint8),
        pts_3d
    )
    grid.cell_data['salinity'] = sal
    return grid


def build_land_from_bathy():
    """Build a PyVista StructuredGrid from the topobathy DEM, land cells coloured grey."""
    print('Loading topobathy DEM ...')
    ds = xr.open_dataset(BATHY_NC)
    lat = ds['lat'].values
    lon = ds['lon'].values
    z   = ds['bathymetry'].values.astype(np.float32)
    ds.close()

    # Crop to rendering domain
    ilon = np.where((lon >= LON_CROP[0]) & (lon <= LON_CROP[1]))[0]
    ilat = np.where((lat >= LAT_CROP[0]) & (lat <= LAT_CROP[1]))[0]
    lon_c = lon[ilon]
    lat_c = lat[ilat]
    z_c   = z[np.ix_(ilat, ilon)]

    # Subsample for performance (~300 m grid is sufficient for land context)
    stride = max(1, int(0.003 / abs(lat[1]-lat[0])))
    lon_s = lon_c[::stride]
    lat_s = lat_c[::stride]
    z_s   = z_c[::stride, ::stride]
    print(f'  Subsampled to {z_s.shape} ({stride}× stride)')

    # Create structured grid (z offset: exaggerate slightly for 3D context)
    z_exag = z_s * 5   # 5× vertical exaggeration for visibility

    # Flatten to points
    lon2, lat2 = np.meshgrid(lon_s, lat_s)
    pts_land = np.column_stack([lon2.ravel(), lat2.ravel(), z_exag.ravel()])

    # Build StructuredGrid
    grid = pv.StructuredGrid()
    grid.dimensions = (len(lon_s), len(lat_s), 1)
    grid.points = pts_land
    grid.point_data['elev'] = z_s.ravel()   # point data: same count as points

    return grid, z_s


def build_land_from_ldb():
    """Build a flat z=0 land polygon from the Sicily .ldb file."""
    print('Loading land boundary .ldb ...')
    pts = []
    with open(LDB_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    x, y = float(parts[0]), float(parts[1])
                    pts.append([x, y, 0.0])
                except ValueError:
                    continue
    if not pts:
        return None
    pts_arr = np.array(pts)
    # Crop
    mask = ((pts_arr[:,0] >= LON_CROP[0]) & (pts_arr[:,0] <= LON_CROP[1]) &
            (pts_arr[:,1] >= LAT_CROP[0]) & (pts_arr[:,1] <= LAT_CROP[1]))
    pts_arr = pts_arr[mask]
    if len(pts_arr) < 3:
        return None
    return pv.PolyData(pts_arr)


def render_scene(model_grid, land_context):
    print('Rendering 3D scene ...')
    pl = pv.Plotter(off_screen=True, window_size=(1920, 1080))
    pl.set_background('#1a1a2e')   # deep navy background

    if land_context is not None:
        if APPROACH == 'bathy':
            grid_land, z_s = land_context
            # Render land (z >= -0.5 m) as terrain, deeper water as dark blue
            elev_flat = z_s.ravel().astype(np.float32)
            colors = np.zeros((len(elev_flat), 3), dtype=np.uint8)
            colors[elev_flat >= -0.5]  = [180, 160, 130]   # sandy/rock beige
            colors[elev_flat < -0.5]   = [20,  60, 100]    # deep water blue
            grid_land.point_data['land_color'] = colors
            pl.add_mesh(grid_land, scalars='land_color', rgb=True,
                        show_scalar_bar=False, label='Topobathy')
        else:
            pl.add_mesh(land_context, color='#8B7355', point_size=2,
                        render_points_as_spheres=True, label='Coast')

    # Model mesh: salinity
    # Clip to lagoon + near-lagoon area
    clip = model_grid.threshold(
        value=[-1e6, 1e6], scalars='salinity', invert=False
    )
    pl.add_mesh(
        clip, scalars='salinity',
        cmap='RdYlBu_r',
        clim=[SA_VMIN, SA_VMAX],
        show_scalar_bar=True,
        scalar_bar_args={
            'title': 'Salinity (ppt)', 'position_x': 0.82,
            'position_y': 0.25, 'height': 0.5, 'width': 0.04,
            'color': 'white', 'label_font_size': 14, 'title_font_size': 14,
        }
    )

    # Camera: isometric view looking at lagoon from NW
    pl.camera_position = [
        (12.20, 37.70, 0.08),   # camera position (lon, lat, z_norm)
        (12.46, 37.88, 0.0),    # focal point (centre of lagoon)
        (0, 0, 1),              # up direction
    ]
    pl.camera.zoom(1.3)

    # Title annotation
    pl.add_text(
        'Stagnone di Marsala — Surface Salinity (ppt)\nv04AE | Jul 6 2025 12:00 UTC | Day 5/9',
        position='upper_left', font_size=14, color='white', font='arial'
    )

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    pl.show(screenshot=str(OUT_PNG))
    print(f'PNG saved: {OUT_PNG}  ({OUT_PNG.stat().st_size//1024} kB)')


def main():
    nx, ny, fn, fv, sal = load_salinity_and_grid()
    model_grid = mesh_to_pyvista(nx, ny, fn, fv, sal)

    if APPROACH == 'bathy':
        land_ctx = build_land_from_bathy()
    else:
        land_ctx = build_land_from_ldb()

    render_scene(model_grid, land_ctx)
    print('Done.')


if __name__ == '__main__':
    main()
