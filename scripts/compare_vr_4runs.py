"""
4-run VR comparison: bl / nodm / vr / nodm_vr
----------------------------------------------
Panels:
  1. WL time series + metrics at BN / BS / AE  (3-panel)
  2. Velocity CDF — isolates D-Morph vs VR effects
  3. Spatial map of VR effect (nodm_vr - nodm), clean isolation

Runs:
  bl      = v04AE       (D-Morph ON,  VR OFF)  -- local his.nc
  nodm    = v04AE_nodm  (D-Morph OFF, VR OFF)  -- local his.nc
  vr      = v04AE_vr    (D-Morph ON,  VR ON)   -- CSV from server
  nodm_vr = v04AE_nodm_vr (D-Morph OFF, VR ON) -- CSV from server
"""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
FIG  = ROOT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

STATIONS = ['BocaNord', 'BocaSud', 'AltaVilaEst']
STATION_LABELS = {'BocaNord': 'BN', 'BocaSud': 'BS', 'AltaVilaEst': 'AE'}
OBS_FILES = {
    'BocaNord':    PROC / 'wl_BocaNord_10min_UTC.csv',
    'BocaSud':     PROC / 'wl_BocaSud_10min_UTC.csv',
    'AltaVilaEst': PROC / 'wl_AltavilaEst_10min_UTC.csv',
}
SPINUP_DAYS = 1.0

RUN_COLORS = {'bl': '#2563eb', 'nodm': '#16a34a', 'vr': '#dc2626', 'nodm_vr': '#ea580c'}
RUN_LABELS = {
    'bl':      'bl (D-Morph ON,  VR OFF)',
    'nodm':    'nodm (D-Morph OFF, VR OFF)',
    'vr':      'vr (D-Morph ON,  VR ON)',
    'nodm_vr': 'nodm_vr (D-Morph OFF, VR ON)',
}

# -------------------------------------------------------------------
# 1. Load WL
# -------------------------------------------------------------------

def load_his_wl(his_dir, station):
    for p in range(8):
        f = his_dir / f'Stagnone_dxy01_15m_{p:04d}_his.nc'
        if not f.exists():
            continue
        ds = xr.open_dataset(f)
        names = [s.decode().strip() if isinstance(s, bytes) else str(s).strip()
                 for s in ds.station_name.values]
        if station not in names:
            ds.close()
            continue
        i = names.index(station)
        dim = 'stations' if 'stations' in ds.waterlevel.dims else 'station'
        wl = ds.waterlevel.isel({dim: i}).to_pandas()
        ds.close()
        return wl
    return None


def load_csv_wl(csv_path, station):
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    if station in df.columns:
        return df[station]
    return None


def load_obs(station):
    f = OBS_FILES[station]
    df = pd.read_csv(f, parse_dates=['datetime_utc'], index_col='datetime_utc')
    return df.iloc[:, 0]


BL_DIR   = ROOT / 'model' / 'dflowfm_v04AE'      / 'DFM_OUTPUT_Stagnone_dxy01_15m'
NODM_DIR = ROOT / 'model' / 'dflowfm_v04AE_nodm'  / 'DFM_OUTPUT_Stagnone_dxy01_15m'
VR_CSV   = PROC / 'wl_vr.csv'
NODMVR_CSV = PROC / 'wl_nodm_vr.csv'

wl = {}
for st in STATIONS:
    wl[('bl',      st)] = load_his_wl(BL_DIR,   st)
    wl[('nodm',    st)] = load_his_wl(NODM_DIR,  st)
    wl[('vr',      st)] = load_csv_wl(VR_CSV,    st)
    wl[('nodm_vr', st)] = load_csv_wl(NODMVR_CSV, st)
    wl[('obs',     st)] = load_obs(st)

# -------------------------------------------------------------------
# 2. Metrics
# -------------------------------------------------------------------

def metrics(sim, obs):
    """Align, drop spinup, compute RMSE/bias/RMSE_anom/corr."""
    df = pd.DataFrame({'sim': sim, 'obs': obs}).dropna()
    if len(df) < 10:
        return dict(n=0, rmse=np.nan, bias=np.nan, rmse_anom=np.nan, corr=np.nan)
    t0 = df.index[0] + pd.Timedelta(days=SPINUP_DAYS)
    df = df[df.index >= t0]
    if len(df) < 10:
        return dict(n=0, rmse=np.nan, bias=np.nan, rmse_anom=np.nan, corr=np.nan)
    diff = df['sim'] - df['obs']
    bias = diff.mean()
    rmse = np.sqrt((diff**2).mean())
    rmse_anom = np.sqrt(rmse**2 - bias**2)
    corr = df['sim'].corr(df['obs'])
    return dict(n=len(df), rmse=rmse, bias=bias, rmse_anom=rmse_anom, corr=corr)


print('\nWL metrics (post-spinup, all runs):')
print(f"{'run':<10} {'station':<14} {'bias':>7} {'RMSE':>7} {'RMSE_a':>7} {'corr':>6}")
print('-' * 55)
all_metrics = {}
for run in ('bl', 'nodm', 'vr', 'nodm_vr'):
    for st in STATIONS:
        sim = wl.get((run, st))
        obs = wl.get(('obs', st))
        if sim is None or obs is None:
            continue
        m = metrics(sim, obs)
        all_metrics[(run, st)] = m
        print(f"{run:<10} {st:<14} {m['bias']:>+7.4f} {m['rmse']:>7.4f} "
              f"{m['rmse_anom']:>7.4f} {m['corr']:>6.3f}")

# -------------------------------------------------------------------
# 3. Figure 1 — WL time series (3-panel)
# -------------------------------------------------------------------

fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
fig.suptitle('Water level — 4-run comparison (Jul 2025)', fontsize=12)

for ax, st in zip(axes, STATIONS):
    obs = wl.get(('obs', st))
    if obs is not None:
        ax.plot(obs.index, obs.values, 'k-', lw=1.2, alpha=0.7, label='obs', zorder=5)
    for run in ('bl', 'nodm', 'vr', 'nodm_vr'):
        s = wl.get((run, st))
        if s is None:
            continue
        ax.plot(s.index, s.values, color=RUN_COLORS[run], lw=1.0,
                alpha=0.85, label=RUN_LABELS[run])
    # metrics annotation
    lines = []
    for run in ('bl', 'nodm', 'vr', 'nodm_vr'):
        m = all_metrics.get((run, st), {})
        if m.get('n', 0) > 0:
            lines.append(f"{run}: b={m['bias']:+.3f} Ra={m['rmse_anom']:.3f} r={m['corr']:.3f}")
    ax.text(0.01, 0.02, '\n'.join(lines), transform=ax.transAxes,
            fontsize=6.5, va='bottom', family='monospace',
            bbox=dict(fc='white', alpha=0.7, pad=2))
    ax.set_ylabel('WL (m)', fontsize=9)
    ax.set_title(STATION_LABELS[st], fontsize=10, loc='left')
    ax.grid(True, alpha=0.3)

axes[0].legend(fontsize=7, ncol=3, loc='upper right')
fig.tight_layout()
out1 = FIG / 'compare_vr_4runs_wl.png'
fig.savefig(out1, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f'\nFig 1 -> {out1}')

# -------------------------------------------------------------------
# 4. Figure 2 — Velocity CDF
# -------------------------------------------------------------------

vel_files = {
    'bl':      PROC / 'vel_lagoon_bl.npz',
    'nodm':    PROC / 'vel_lagoon_nodm.npz',
    'vr':      PROC / 'vel_lagoon_vr.npz',
    'nodm_vr': PROC / 'vel_lagoon_nodm_vr.npz',
}
def load_vel_npz(f):
    d = np.load(f)
    return d['umean']

vel = {}
for run, f in vel_files.items():
    if f.exists():
        u = load_vel_npz(f)
        vel[run] = u
        print(f"  {run}: {len(u)} cells  mean={u.mean():.5f}  p50={np.median(u):.5f}")

print('\nVelocity percent changes (median):')
pairs = [
    ('D-Morph effect (bl vs nodm)',        'bl',      'nodm'),
    ('VR effect clean (nodm_vr vs nodm)',  'nodm_vr', 'nodm'),
    ('VR effect contam (vr vs bl)',        'vr',      'bl'),
    ('Combined D-Morph+VR (vr vs nodm)',   'vr',      'nodm'),
]
for label, a, b in pairs:
    if a in vel and b in vel:
        p_a, p_b = np.median(vel[a]), np.median(vel[b])
        pct = (p_a - p_b) / p_b * 100
        print(f"  {label:<42}: {pct:+.1f}% median  ({p_a:.5f} vs {p_b:.5f})")

fig, ax = plt.subplots(figsize=(8, 5))
pcts = np.linspace(0, 100, 500)
for run in ('bl', 'nodm', 'vr', 'nodm_vr'):
    if run not in vel:
        continue
    vals = np.percentile(vel[run], pcts)
    ax.plot(vals, pcts, color=RUN_COLORS[run], lw=1.8, label=RUN_LABELS[run])

ax.set_xlabel('Time-mean |u| depth-avg (m/s)', fontsize=10)
ax.set_ylabel('Percentile (%)', fontsize=10)
ax.set_title('Velocity CDF — lagoon cells (post-spinup mean)', fontsize=11)
ax.set_xlim(0, 0.30)
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# add annotation boxes
for run, y in [('nodm', 85), ('nodm_vr', 70)]:
    if run in vel:
        m_nodm = np.median(vel['nodm'])
        m_run  = np.median(vel[run])
        pct    = (m_run - m_nodm) / m_nodm * 100
        tag    = 'VR clean' if run == 'nodm_vr' else 'baseline'
        ax.annotate(f'p50={m_run:.4f}', xy=(m_run, 50),
                    xytext=(0.16, y / 100), textcoords='axes fraction',
                    fontsize=8, color=RUN_COLORS[run],
                    arrowprops=dict(arrowstyle='->', color=RUN_COLORS[run], lw=0.8))

fig.tight_layout()
out2 = FIG / 'compare_vr_4runs_vel_cdf.png'
fig.savefig(out2, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f'Fig 2 -> {out2}')

# -------------------------------------------------------------------
# 5. Figure 3 — VR spatial effect map (nodm_vr - nodm)
# -------------------------------------------------------------------

if 'nodm_vr' in vel and 'nodm' in vel:
    d_nodm_vr = np.load(vel_files['nodm_vr'])
    d_nodm    = np.load(vel_files['nodm'])
    fx = d_nodm_vr['face_x'] if 'face_x' in d_nodm_vr else d_nodm_vr['x']
    fy = d_nodm_vr['face_y'] if 'face_y' in d_nodm_vr else d_nodm_vr['y']
    diff = load_vel_npz(vel_files['nodm_vr']) - load_vel_npz(vel_files['nodm'])
    pct_diff = diff / (d_nodm['umean'] + 1e-6) * 100

    vmax = np.percentile(np.abs(pct_diff), 97)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    sc0 = axes[0].scatter(fx, fy, c=diff, cmap='RdBu_r', s=1.5,
                          vmin=-0.05, vmax=0.05)
    plt.colorbar(sc0, ax=axes[0], label='Δ|u| (m/s)  [nodm_vr − nodm]')
    axes[0].set_title('Absolute velocity change (VR ON vs OFF)', fontsize=10)
    axes[0].set_xlabel('Longitude'); axes[0].set_ylabel('Latitude')
    axes[0].set_aspect('equal')

    sc1 = axes[1].scatter(fx, fy, c=pct_diff, cmap='RdBu_r', s=1.5,
                          vmin=-vmax, vmax=vmax)
    plt.colorbar(sc1, ax=axes[1], label='Δ|u| (%)  [nodm_vr − nodm]')
    axes[1].set_title('Relative velocity change (%)', fontsize=10)
    axes[1].set_xlabel('Longitude'); axes[1].set_aspect('equal')

    n_faster = (diff > 0).sum()
    n_slower = (diff < 0).sum()
    fig.suptitle(f'VR spatial effect (clean isolation, D-Morph OFF)  |  '
                 f'faster: {n_faster} cells ({n_faster/len(diff)*100:.0f}%)  '
                 f'slower: {n_slower} cells ({n_slower/len(diff)*100:.0f}%)',
                 fontsize=10)
    fig.tight_layout()
    out3 = FIG / 'compare_vr_spatial_effect.png'
    fig.savefig(out3, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Fig 3 -> {out3}')

print('\nDone.')
