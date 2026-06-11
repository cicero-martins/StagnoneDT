"""Salinity surface animation via pyvista.

Phase 1: top sigma layer salinity on 2D mesh coloured by salinity,
         Z = bed level for 3D bathymetry effect.
Phase 2 (optional): vertical transect if --transect flag is passed.

Output: figures/salt_surface_nodm.mp4  (subsample every TSTEP frames)

Memory strategy: load all partitions once into RAM (sa1 surface layer
only), then loop over time steps rendering frame-by-frame. Total RAM:
~8 partitions x 3700 faces x 433 steps x 4 bytes = ~50 MB.
"""
import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import pyvista as pv
import imageio

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'
MODEL_DIR = ROOT / 'model' / 'dflowfm_v04AE_nodm' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
NPART = 8
TSTEP = 4       # render every Nth time step (4 = 108 frames ~9 s @ 12 fps)
FPS   = 12
SALT_MIN, SALT_MAX = 30.0, 65.0  # ppt range for colorbar
LAG_LON = (12.40, 12.50)
LAG_LAT = (37.81, 37.93)

pv.global_theme.allow_empty_mesh = True


def load_partitions():
    """Load face coords, bed level and surface salinity from all partitions."""
    all_x, all_y, all_bl, all_sa, all_times = [], [], [], [], None
    for p in range(NPART):
        mp = MODEL_DIR / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not mp.exists():
            print(f'  partition {p}: not found')
            break
        ds = xr.open_dataset(mp)
        fx = ds['mesh2d_face_x'].values
        fy = ds['mesh2d_face_y'].values
        # lagoon filter
        lag = ((fx >= LAG_LON[0]) & (fx <= LAG_LON[1]) &
               (fy >= LAG_LAT[0]) & (fy <= LAG_LAT[1]))
        # bed level: use first time step (morphology changes slowly)
        if 'mesh2d_flowelem_bl' in ds:
            bl_var = ds['mesh2d_flowelem_bl']
            bl = (bl_var.isel(time=0) if 'time' in bl_var.dims else bl_var).values[lag]
        elif 'mesh2d_mor_bl' in ds:
            bl_var = ds['mesh2d_mor_bl']
            bl = (bl_var.isel(time=0) if 'time' in bl_var.dims else bl_var).values[lag]
        else:
            bl = np.zeros(lag.sum())
        # surface salinity: top sigma layer (-1)
        sa = ds['mesh2d_sa1'].values[:, lag, -1]  # (time, n_faces_filtered)
        if all_times is None:
            all_times = ds['time'].values
        ds.close()
        all_x.append(fx[lag]); all_y.append(fy[lag])
        all_bl.append(bl);     all_sa.append(sa)
        print(f'  p{p}: {lag.sum()} faces')

    face_x  = np.concatenate(all_x)
    face_y  = np.concatenate(all_y)
    face_bl = np.concatenate(all_bl)
    sa_surf = np.concatenate(all_sa, axis=1)  # (n_time, n_faces_total)
    print(f'Total: {len(face_x)} faces  |  {len(all_times)} time steps')
    print(f'Salinity range: [{sa_surf.min():.1f}, {sa_surf.max():.1f}] ppt')
    return face_x, face_y, face_bl, sa_surf, all_times


def build_surface_mesh(face_x, face_y, face_bl=None):
    """Build pyvista PolyData surface via Delaunay2D on face centres.

    Uses Z=0 (flat top-down view). Bed level is stored as point scalar
    for optional depth-shading but not used as geometry Z.
    """
    print('Building Delaunay2D surface mesh...')
    pts = np.column_stack([face_x, face_y, np.zeros(len(face_x))])
    cloud = pv.PolyData(pts)
    # alpha = max triangle edge in degrees; 0.008 deg ~ 800 m
    surf = cloud.delaunay_2d(alpha=0.008, progress_bar=False)
    if face_bl is not None:
        surf.point_data['bed_level'] = face_bl
    print(f'  Surface: {surf.n_points} points, {surf.n_cells} cells')
    return surf


def fmt_time(np_dt64):
    import pandas as pd
    return pd.Timestamp(np_dt64).strftime('%Y-%m-%d %H:%M UTC')


def render_animation(face_x, face_y, face_bl, sa_surf, times):
    surf = build_surface_mesh(face_x, face_y, face_bl)

    t_indices = range(0, len(times), TSTEP)
    out_mp4 = FIG / 'salt_surface_nodm.mp4'

    pl = pv.Plotter(off_screen=True, window_size=(1200, 800))
    pl.set_background('black')

    # initial scalar
    surf.point_data['salinity_ppt'] = sa_surf[0]
    # auto clim from post-spinup data (skip t0)
    sa_post = sa_surf[48:][sa_surf[48:] > 1]
    clim = [float(np.nanpercentile(sa_post, 2)), float(np.nanpercentile(sa_post, 98))]

    actor = pl.add_mesh(
        surf,
        scalars='salinity_ppt',
        cmap='haline',
        clim=clim,
        show_scalar_bar=True,
        scalar_bar_args=dict(
            title='Salinity\n(ppt)',
            title_font_size=13,
            label_font_size=11,
            color='white',
            n_labels=4,
            position_x=0.85, position_y=0.05,
            width=0.10, height=0.60,
        ),
        lighting=False,
        smooth_shading=False,
    )

    # Camera: orthographic top-down, auto-fit to mesh bounds
    pl.enable_parallel_projection()
    pl.reset_camera()
    pl.camera.zoom(0.92)  # slight padding around the mesh

    # Time label — pyvista 0.48 returns CornerAnnotation; update via SetText(pos, str)
    txt = pl.add_text(fmt_time(times[0]), position='upper_left',
                      font_size=11, color='white')

    t_indices = list(t_indices)
    print(f'Rendering {len(t_indices)} frames -> {out_mp4.name}')
    frames = []
    for i, t in enumerate(t_indices):
        surf.point_data['salinity_ppt'] = sa_surf[t]
        # update time label (CornerAnnotation API: position 2 = upper_left)
        try:
            txt.SetText(2, fmt_time(times[t]))
        except AttributeError:
            pass
        pl.render()
        img = pl.screenshot(return_img=True)
        frames.append(img)
        if i % 20 == 0:
            print(f'  frame {i}/{len(t_indices)}  t={fmt_time(times[t])}')

    pl.close()

    print(f'Writing MP4 ({len(frames)} frames @ {FPS} fps)...')
    writer = imageio.get_writer(str(out_mp4), fps=FPS, codec='libx264',
                                 quality=7, macro_block_size=None)
    for f in frames:
        writer.append_data(f)
    writer.close()
    print(f'Done -> {out_mp4}')


def main():
    print('Loading partitions...')
    face_x, face_y, face_bl, sa_surf, times = load_partitions()
    render_animation(face_x, face_y, face_bl, sa_surf, times)


if __name__ == '__main__':
    main()
