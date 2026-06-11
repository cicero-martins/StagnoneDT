"""
AE station location diagnostic:
  1. Map cells in AE area with bed levels + wet/dry status
  2. Show VR spatial effect (nodm_vr - nodm) zoomed to AE
  3. Find alternative cells closer to the real gauge (12.447, 37.890)
"""
from pathlib import Path
import numpy as np
import xarray as xr
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'
NET  = ROOT / 'model' / 'dflowfm_v04AE' / 'Stagnone_dxy01_15m_net.nc'
HIS  = ROOT / 'model' / 'dflowfm_v04AE' / 'DFM_OUTPUT_Stagnone_dxy01_15m' / 'Stagnone_dxy01_15m_0000_his.nc'

# Gauge locations
AE_GAUGE_REAL  = (12.447, 37.890)    # actual instrument location (notebook 02)
AE_MODEL       = (12.451652, 37.891785)  # current xyn entry
AE_ZOOM = dict(lon=(12.430, 12.475), lat=(37.875, 37.910))

# -------------------------------------------------------------------
# Load mesh face coords + bed levels
# -------------------------------------------------------------------
net = xr.open_dataset(NET)
fx = net['mesh2d_face_x'].values
fy = net['mesh2d_face_y'].values
# bed level: try face_z, then node-average
if 'mesh2d_face_z' in net:
    bl = net['mesh2d_face_z'].values
elif 'mesh2d_node_z' in net:
    # approximate per-face from node_z
    node_z = net['mesh2d_node_z'].values
    face_nodes = net['mesh2d_face_nodes'].values  # (nFaces, maxNodes)
    bl = np.array([node_z[face_nodes[i][face_nodes[i] >= 0]].mean()
                   for i in range(len(fx))])
else:
    bl = np.zeros(len(fx))
net.close()

# Zoom mask
zm = ((fx >= AE_ZOOM['lon'][0]) & (fx <= AE_ZOOM['lon'][1]) &
      (fy >= AE_ZOOM['lat'][0]) & (fy <= AE_ZOOM['lat'][1]))
fxz, fyz, blz = fx[zm], fy[zm], bl[zm]

print(f'Cells in AE zoom: {zm.sum()}')
print(f'Bed level range: {blz.min():.3f} to {blz.max():.3f} m')

# Candidates near real gauge
dist_gauge = np.sqrt((fx - AE_GAUGE_REAL[0])**2 + (fy - AE_GAUGE_REAL[1])**2)
dist_model = np.sqrt((fx - AE_MODEL[0])**2 + (fy - AE_MODEL[1])**2)
idx_sort   = np.argsort(dist_gauge)

print('\n15 nearest cells to REAL gauge (12.447, 37.890):')
print(f"{'#':>3}  {'lon':>9}  {'lat':>9}  {'bl_m':>7}  {'dist_deg':>9}  {'dist_m':>7}")
for k in idx_sort[:15]:
    d_m = dist_gauge[k] * 111000
    print(f"{k:>5}  {fx[k]:>9.5f}  {fy[k]:>9.5f}  {bl[k]:>7.3f}  "
          f"{dist_gauge[k]:>9.5f}  {d_m:>7.0f}")

print(f'\nModel station cell: nearest cell is index {np.argmin(dist_model)} '
      f'at bl={bl[np.argmin(dist_model)]:.3f} m  (dist={dist_model.min()*111000:.0f} m)')

# WL time series comparison at several candidate cells from map.nc
# Use the nodm run to check candidate cells
MAP_DIR = ROOT / 'model' / 'dflowfm_v04AE_nodm' / 'DFM_OUTPUT_Stagnone_dxy01_15m'
print('\nChecking WL correlation at candidate cells from map.nc (nodm run)...')
obs_df = pd.read_csv(PROC / 'insitu_2025-26' / 'AE_wl_UTC.csv',
                     parse_dates=['time'], index_col='time')
obs = obs_df['h_m'].rename('obs')
obs.index = obs.index.tz_localize(None) if obs.index.tzinfo else obs.index

candidates = idx_sort[:8]  # top 8 nearest to real gauge
cell_metrics = []
for k in candidates:
    # find which partition
    for p in range(8):
        mp = MAP_DIR / f'Stagnone_dxy01_15m_{p:04d}_map.nc'
        if not mp.exists():
            continue
        ds = xr.open_dataset(mp)
        pfx = ds['mesh2d_face_x'].values
        pfy = ds['mesh2d_face_y'].values
        pbl = None
        if 'mesh2d_face_z' in ds:
            pbl = ds['mesh2d_face_z'].values
        # find this global cell in partition
        dist_p = np.sqrt((pfx - fx[k])**2 + (pfy - fy[k])**2)
        i_local = np.argmin(dist_p)
        if dist_p[i_local] > 0.001:
            ds.close()
            continue
        # extract WL
        wl_var = 'mesh2d_s1' if 'mesh2d_s1' in ds else None
        if wl_var is None:
            ds.close()
            continue
        wl = ds[wl_var].isel(mesh2d_nFaces=i_local).to_pandas()
        bl_cell = pbl[i_local] if pbl is not None else bl[k]
        ds.close()
        # metrics vs obs
        t0 = wl.index[0] + pd.Timedelta('1D')
        df = pd.DataFrame({'sim': wl, 'obs': obs}).dropna()
        df = df[df.index >= t0]
        if len(df) < 20:
            cell_metrics.append((k, fx[k], fy[k], bl_cell, p, i_local, 0, np.nan, np.nan, np.nan))
        else:
            diff = df['sim'] - df['obs']
            bias = diff.mean()
            rmse_a = np.sqrt((diff**2).mean() - bias**2)
            corr = df['sim'].corr(df['obs'])
            cell_metrics.append((k, fx[k], fy[k], bl_cell, p, i_local, len(df), bias, rmse_a, corr))
        break

print(f"\n{'idx':>6}  {'lon':>9}  {'lat':>9}  {'bl_m':>6}  "
      f"{'n':>5}  {'bias':>7}  {'RMSE_a':>7}  {'corr':>6}")
for row in cell_metrics:
    k, lon, lat, blc, p, iloc, n, bias, rmsa, corr = row
    print(f"{k:>6}  {lon:>9.5f}  {lat:>9.5f}  {blc:>6.3f}  "
          f"{n:>5}  {bias:>+7.4f}  {rmsa:>7.4f}  {corr:>6.3f}")

# -------------------------------------------------------------------
# Figure 1 — VR spatial effect zoomed to AE + station markers
# -------------------------------------------------------------------
d_vr = np.load(PROC / 'vel_lagoon_nodm_vr.npz')
d_nm = np.load(PROC / 'vel_lagoon_nodm.npz')
vfx, vfy = d_vr['face_x'], d_vr['face_y']
vdiff = d_vr['umean'] - d_nm['umean']
vpct  = vdiff / (d_nm['umean'] + 1e-6) * 100

vzm = ((vfx >= AE_ZOOM['lon'][0]) & (vfx <= AE_ZOOM['lon'][1]) &
       (vfy >= AE_ZOOM['lat'][0]) & (vfy <= AE_ZOOM['lat'][1]))

fig, axes = plt.subplots(1, 2, figsize=(13, 6))

# Left: bed level map
vmax_bl = 1.0
sc0 = axes[0].scatter(fxz, fyz, c=np.clip(blz, -2.5, vmax_bl),
                      cmap='terrain_r', s=4, vmin=-2.5, vmax=vmax_bl)
plt.colorbar(sc0, ax=axes[0], label='Bed level (m MSL)', fraction=0.03)
axes[0].set_title('Bathymetry — AE zoom', fontsize=10)

# Right: VR effect
vmax = np.percentile(np.abs(vpct[vzm]), 95) if vzm.sum() > 0 else 50
sc1 = axes[1].scatter(vfx[vzm], vfy[vzm], c=vpct[vzm],
                      cmap='RdBu_r', s=4, vmin=-vmax, vmax=vmax)
plt.colorbar(sc1, ax=axes[1], label='Δ|u| % (nodm_vr − nodm)', fraction=0.03)
axes[1].set_title('VR effect on velocity (%)', fontsize=10)

# Station markers on both panels
for ax in axes:
    ax.plot(*AE_GAUGE_REAL, 'g*', ms=12, zorder=10, label='AE gauge (real)')
    ax.plot(*AE_MODEL, 'r^', ms=9, zorder=10, label='AE model (xyn)')
    ax.annotate('gauge\n(12.447)', AE_GAUGE_REAL,
                xytext=(AE_GAUGE_REAL[0]-0.007, AE_GAUGE_REAL[1]+0.002),
                fontsize=7, color='green',
                arrowprops=dict(arrowstyle='->', color='green', lw=0.7))
    ax.annotate('model\n(12.452)', AE_MODEL,
                xytext=(AE_MODEL[0]+0.003, AE_MODEL[1]-0.004),
                fontsize=7, color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=0.7))
    ax.set_xlim(*AE_ZOOM['lon'])
    ax.set_ylim(*AE_ZOOM['lat'])
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
    ax.set_aspect('equal')
    ax.legend(fontsize=8, loc='lower right')

fig.suptitle('AltaVilaEst station area — bathymetry & VR effect', fontsize=11)
fig.tight_layout()
out1 = FIG / 'ae_station_location_check.png'
fig.savefig(out1, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f'\nFig 1 -> {out1}')
print('Done.')
