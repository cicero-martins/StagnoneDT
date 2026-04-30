"""Quantify the impact of the +0.4208 m boundary offset on lagoon dynamics.

The Stagnone is shallow (0.5-2 m typical), so a 42 cm offset could materially
change wet area, volume, and intertidal exposure. This script computes the
lagoon hypsometric curve (wet area + volume as function of WL) and compares
the operating point WITH offset (v03d mean WL ~+0.07 m) vs WITHOUT (mean WL
would be ~-0.35 m).

Region of interest: the Stagnone lagoon proper, defined as the polygon roughly
lon [12.43, 12.46] x lat [37.85, 37.92] (encloses the actual water body
between Marsala mainland and the barrier islands).
"""
import numpy as np
import pandas as pd
import xarray as xr
import netCDF4
import matplotlib.pyplot as plt


# Lagoon-only bounding box (the actual Stagnone water body)
LAG_LON = (12.43, 12.46)
LAG_LAT = (37.85, 37.92)

# Lagoon mean WL in v03d (with offset)
WL_WITH_OFFSET = +0.07
# What it would be without (subtract 0.4208 m, since offset shifts the BC up)
WL_NO_OFFSET = WL_WITH_OFFSET - 0.4208  # = -0.351 m


def main():
    # Aggregate face-level bedlevel + cell areas from all 4 partitions
    bls, areas, fxs, fys = [], [], [], []
    for p in range(4):
        nc = netCDF4.Dataset(f'model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_000{p}_map.nc')
        fx = nc.variables['mesh2d_face_x'][:]
        fy = nc.variables['mesh2d_face_y'][:]
        bl = nc.variables['mesh2d_flowelem_bl'][:]
        # Compute cell area from face_x_bnd / face_y_bnd if available, else estimate
        if 'mesh2d_flowelem_ba' in nc.variables:
            area = nc.variables['mesh2d_flowelem_ba'][:]
        else:
            # Approximate: 1 deg lon at 38N ~ 88 km, 1 deg lat ~ 111 km
            # average cell area ~ (lat extent * lon extent / N cells) for the lagoon
            area = np.full_like(bl, 1500.0)  # ~38 m x 38 m cell, conservative
        bls.append(bl); areas.append(area); fxs.append(fx); fys.append(fy)
        nc.close()

    bl_all = np.concatenate(bls)
    area_all = np.concatenate(areas)
    fx_all = np.concatenate(fxs)
    fy_all = np.concatenate(fys)

    # Restrict to the SHALLOW lagoon proper (bbox + bedlevel > -3 m, excludes
    # offshore cells west of Mozia that fall in the bbox but are not part of
    # the actual Stagnone water body).
    in_bbox = (
        (fx_all >= LAG_LON[0]) & (fx_all <= LAG_LON[1])
        & (fy_all >= LAG_LAT[0]) & (fy_all <= LAG_LAT[1])
    )
    in_lag = in_bbox & (bl_all > -3.0)  # shallow lagoon only
    bl_lag = bl_all[in_lag]
    area_lag = area_all[in_lag]
    print(f'Shallow lagoon cells (bbox + bedlevel > -3 m): {in_lag.sum()}')
    print(f'Total bbox cells (incl. offshore): {in_bbox.sum()} (excluded {(in_bbox & ~in_lag).sum()} deep cells)')
    print(f'Shallow lagoon area total: {area_lag.sum()/1e6:.2f} km2')
    print(f'Shallow lagoon bedlevel: min {bl_lag.min():.2f}, max {bl_lag.max():.2f}, median {np.median(bl_lag):.2f}, mean {bl_lag.mean():.2f} m')
    print()

    # Hypsometry: wet area + volume as function of WL
    wls = np.linspace(-1.0, 1.0, 201)
    wet_area = np.empty_like(wls)
    volume = np.empty_like(wls)
    for k, wl in enumerate(wls):
        wet = bl_lag <= wl
        wet_area[k] = area_lag[wet].sum()
        depth = np.maximum(wl - bl_lag, 0)  # zero where dry
        volume[k] = (depth * area_lag).sum()

    total_lag_area = area_lag.sum()

    # Operating points
    def at(wl):
        wet = bl_lag <= wl
        wa = area_lag[wet].sum()
        depth = np.maximum(wl - bl_lag, 0)
        vol = (depth * area_lag).sum()
        return wa, vol, np.mean(depth[wet]) if wet.any() else 0.0

    wa_with, vol_with, depth_with = at(WL_WITH_OFFSET)
    wa_no, vol_no, depth_no = at(WL_NO_OFFSET)

    print('=' * 80)
    print(f'WL operating point compare:')
    print(f'  With offset (v03d real, mean WL = +{WL_WITH_OFFSET:.2f} m):')
    print(f'    wet area: {wa_with/1e6:.3f} km2 ({100*wa_with/total_lag_area:.1f}% of bbox)')
    print(f'    volume:   {vol_with/1e6:.3f} 10^6 m^3')
    print(f'    mean depth (wet cells): {depth_with:.2f} m')
    print()
    print(f'  Without offset (counterfactual, mean WL = {WL_NO_OFFSET:.2f} m):')
    print(f'    wet area: {wa_no/1e6:.3f} km2 ({100*wa_no/total_lag_area:.1f}% of bbox)')
    print(f'    volume:   {vol_no/1e6:.3f} 10^6 m^3')
    print(f'    mean depth (wet cells): {depth_no:.2f} m')
    print()
    print(f'  Difference (with vs without offset):')
    print(f'    Δ wet area: {(wa_with - wa_no)/1e6:+.3f} km2 ({100*(wa_with - wa_no)/wa_no:+.1f}%)')
    print(f'    Δ volume:   {(vol_with - vol_no)/1e6:+.3f} 10^6 m^3 ({100*(vol_with - vol_no)/vol_no:+.1f}%)')
    print(f'    Δ mean depth (wet): {(depth_with - depth_no)*100:+.1f} cm')
    print('=' * 80)

    # Check tidal range impact -- the lagoon experiences semi-diurnal WL with ptp ~0.2 m
    # so WL varies between roughly mean-0.1 and mean+0.1
    print()
    print('Tidal-range comparison (mean ± 0.10 m, the lagoon ptp):')
    for label, wl_mean in [('with offset', WL_WITH_OFFSET), ('no offset', WL_NO_OFFSET)]:
        for sign, dwl in [('low tide', -0.10), ('high tide', +0.10)]:
            wa, vol, depth = at(wl_mean + dwl)
            print(f'  {label}, {sign} (WL = {wl_mean+dwl:+.2f} m): wet {wa/1e6:.3f} km2, vol {vol/1e6:.3f} 10^6 m^3')

    # Plot hypsometric curves
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax = axes[0]
    ax.plot(wet_area / 1e6, wls, color='tab:blue', lw=1.4)
    ax.axhline(WL_WITH_OFFSET, color='tab:green', ls='-', lw=1.2, label=f'v03d mean WL with offset: {WL_WITH_OFFSET:+.2f} m')
    ax.axhline(WL_NO_OFFSET, color='tab:red', ls='--', lw=1.2, label=f'counterfactual no-offset: {WL_NO_OFFSET:+.2f} m')
    ax.fill_betweenx([WL_NO_OFFSET, WL_WITH_OFFSET], 0, wet_area.max() / 1e6, color='gray', alpha=0.15)
    ax.set_xlabel('wet area [km2]')
    ax.set_ylabel('water level [m]')
    ax.set_title('Hypsometry — wet area vs WL')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(-1, 1)

    ax = axes[1]
    ax.plot(volume / 1e6, wls, color='tab:purple', lw=1.4)
    ax.axhline(WL_WITH_OFFSET, color='tab:green', ls='-', lw=1.2, label=f'v03d mean WL with offset: {WL_WITH_OFFSET:+.2f} m')
    ax.axhline(WL_NO_OFFSET, color='tab:red', ls='--', lw=1.2, label=f'counterfactual no-offset: {WL_NO_OFFSET:+.2f} m')
    ax.fill_betweenx([WL_NO_OFFSET, WL_WITH_OFFSET], 0, volume.max() / 1e6, color='gray', alpha=0.15)
    ax.set_xlabel('volume [10^6 m^3]')
    ax.set_ylabel('water level [m]')
    ax.set_title('Hypsometry — volume vs WL')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(-1, 1)

    plt.suptitle(f'Stagnone lagoon hypsometry — quantifying offset impact ({in_lag.sum()} cells, {total_lag_area/1e6:.2f} km2 total bbox)')
    plt.tight_layout()
    plt.savefig('figures/v03d_offset_hypsometry_impact.png', dpi=110)
    print()
    print('Saved figures/v03d_offset_hypsometry_impact.png')


if __name__ == '__main__':
    main()
