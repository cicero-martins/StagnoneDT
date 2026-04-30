"""Plot hwav across all 7 stations for the full 9-day v03d run (after fix).

Shows that the wave coupling now operates throughout the simulation, capturing
the swell event in the second half of the window (days 7-9 in offshore).
"""
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def main():
    ds = xr.open_dataset('model/dflowfm_v03d/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000_his.nc')
    stations = [s.decode() if isinstance(s, bytes) else s for s in ds['station_name'].values]
    times = pd.to_datetime(ds.time.values)
    hwav = ds['hwav'].values

    fig, (ax_off, ax_lag) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Offshore station — separate panel because it has much larger amplitude
    i = stations.index('ObservationPoint01')
    ax_off.plot(times, hwav[:, i], color='tab:purple', lw=0.7, label=f'ObservationPoint01 (offshore, max {hwav[:, i].max():.2f} m)')
    ax_off.set_ylabel('Hwav offshore [m]')
    ax_off.set_title('Significant wave height — offshore reference (storm event captured days 7-9)')
    ax_off.legend(loc='upper left', fontsize=9)
    ax_off.grid(alpha=0.3)

    # Lagoon stations
    palette = ['tab:red', 'tab:orange', 'tab:green', 'tab:blue', 'tab:cyan', 'tab:olive']
    lagoon_names = ['BocaNord', 'BocaSud', 'AltaVilaEst', 'C1_Central', 'C2_NorthCenter', 'C3_SouthCenter']
    for color, name in zip(palette, lagoon_names):
        i = stations.index(name)
        ax_lag.plot(times, hwav[:, i], color=color, lw=0.7,
                    label=f'{name} (max {hwav[:, i].max():.2f} m)')
    ax_lag.set_ylabel('Hwav lagoon [m]')
    ax_lag.set_xlabel('time')
    ax_lag.set_title('Significant wave height — lagoon stations (BocaNord shows incoming swell)')
    ax_lag.legend(loc='upper left', fontsize=8, ncol=2)
    ax_lag.grid(alpha=0.3)
    ax_lag.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %Hh'))

    # Mark the day where the freeze used to happen
    for ax in [ax_off, ax_lag]:
        ax.axvline(pd.Timestamp('2025-07-04T00:00'), color='gray', ls=':', lw=0.6, alpha=0.6)

    plt.suptitle('v03d 9-day run — wave-coupling fix validated. hwav time-varying through full simulation.\nGray dotted line: where the previous run had silently frozen due to dimr_config <time> end (now fixed).')
    plt.tight_layout()
    plt.savefig('figures/v03d_hwav_9day_full.png', dpi=110)
    print('Saved figures/v03d_hwav_9day_full.png')
    ds.close()


if __name__ == '__main__':
    main()
