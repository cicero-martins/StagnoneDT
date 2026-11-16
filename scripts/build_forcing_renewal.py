"""FM-ready forcing of the seasonal renewal runs.

Two seasons, each window carrying one day of margin at each end of the run:
  summer  run 8 June to 15 September 2025, forcing 7 June to 17 September;
  winter  run 8 November 2025 to 15 January 2026, forcing 7 November to
          17 January.
Inputs from download_forcing_renewal.py, output to
data/processed/forcing_<season><year>/. Each step follows the script that built
the same file for the nine days of 1 to 10 July 2025:

  era5      era5_{mer,msl,chnk,u10n,v10n}_<tag>_ERA5.nc, with mer in mm/day and
            evaporation negative, as the file of 1 to 10 July;
  wind      wind_blendedAE_{u10n,v10n}_<tag>.nc, the AE-only blend of
            prepare_v04AE_jul13jul20_ae_blend.py (AE anemometer within 3 km of
            the lagoon centre, ERA5 beyond 8 km, linear taper between);
  bc        waterlevelbnd, salinitybnd and temperaturebnd from CMEMS through
            dfm_tools, as build_cmems_bc_v04AE_jul13jul20.py, and
            uxuyadvectionvelocitybnd in t3d form, as
            build_uxuy_bc_v04AE_d10d12_extended.py;
  nudge     nudge_salinity_temperature_<first day>_00-00-00.nc, the daily CMEMS
            Mediterranean salinity and temperature over the whole window, the
            target of the relaxation at sea;
  ic        ic3d_{temperature,salinity}_profile.pli, the mean CMEMS profiles over
            the sea points at the start of the run, applied over the whole
            domain, the lagoon included, which therefore starts at the salinity
            of the sea;
  laterals  the two turbid discharges and their tracer at zero over the window.

The tag is the forcing window, 20250607to20250917 in summer and
20251107to20260117 in winter. The per-node offset of the water level is
constant and is copied from the model directory with the remaining static files.

Usage:
    python build_forcing_renewal.py summer|winter [era5 wind bc nudge ic laterals]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
RAW_ERA5 = ROOT / 'data/raw/era5_v04AE_d10d12'
PLI = ROOT / 'model/dflowfm_v04AE/Stagnone_dxy01_15m.pli'
AE_CSV = ROOT / 'data/processed/insitu_2025-26/AE_wind_UTC.csv'
REFDATE = pd.Timestamp('2025-01-01 00:00')   # refDate of the MDU, both seasons
Z_MAX = 800.0

# forcing window (first and last day) and start of the run, per season
SEASONS = {
    'summer': dict(d0='2025-06-07', d1='2025-09-17', start='2025-06-08'),
    'winter': dict(d0='2025-11-07', d1='2026-01-17', start='2025-11-08'),
}


def raw_cmems_dir(season):
    return ROOT / 'data/raw' / f'cmems_{season}{SEASONS[season]["d0"][:4]}'


def configure(season):
    """Set the window, the tag, the ERA5 months and the directories of one season."""
    global SEASON, D0, D1, TAG, T_START, MONTHS, RAW_CMEMS, OUT
    s = SEASONS[season]
    SEASON, D0, D1 = season, s['d0'], s['d1']
    TAG = f'{D0.replace("-", "")}to{D1.replace("-", "")}'
    T_START = pd.Timestamp(s['start'])
    MONTHS = tuple(pd.period_range(D0, D1, freq='M').strftime('%Y-%m'))
    RAW_CMEMS = raw_cmems_dir(season)
    OUT = ROOT / 'data/processed' / f'forcing_{season}{D0[:4]}'


def era5():
    attrs = {
        'mer': dict(standard_name='rainfall_rate', long_name='rainfall_rate', units='mm day-1'),
        'msl': dict(standard_name='air_pressure_at_mean_sea_level',
                    long_name='Mean sea level pressure', units='Pa'),
        'chnk': dict(standard_name='unknown', long_name='Charnock', units='Numeric'),
        'u10n': dict(standard_name='unknown', long_name='10 metre u-component of neutral wind',
                     units='m s**-1'),
        'v10n': dict(standard_name='unknown', long_name='10 metre v-component of neutral wind',
                     units='m s**-1'),
    }
    for var in attrs:
        parts = []
        for m in MONTHS:
            ds = xr.open_dataset(RAW_ERA5 / f'era5_{var}_{m}.nc')
            if 'valid_time' in ds.dims or 'valid_time' in ds.coords:
                ds = ds.rename({'valid_time': 'time'})
            names = list(ds.data_vars)
            if var not in names:
                ds = ds.rename({names[0]: var})
            parts.append(ds.drop_vars([c for c in ('expver', 'number') if c in ds.coords]))
        ds = xr.concat(parts, 'time').sortby('time')
        ds = ds.sel(time=slice(D0, D1 + 'T00:00'))
        ds = ds.sel(time=~ds.get_index('time').duplicated())
        if var == 'mer':
            # avg_ie in kg m-2 s-1, positive downward, to mm/day with evaporation negative,
            # the conversion of dfm_tools behind the validated file of 1 to 10 July
            ds['mer'] = ds['mer'] * 86400.0
        ds[var].attrs = attrs[var]
        ds.attrs = {k: v for k, v in ds.attrs.items() if not k.startswith('GRIB_')}
        step = np.unique(np.diff(ds.time.values).astype('timedelta64[m]'))
        out = OUT / f'era5_{var}_{TAG}_ERA5.nc'
        ds.to_netcdf(out, encoding={var: {'zlib': True, 'complevel': 4}})
        print(f'{out.name}: {len(ds.time)} times {str(ds.time.values[0])[:16]} to '
              f'{str(ds.time.values[-1])[:16]}, steps {step}', flush=True)


def wind():
    from scipy.interpolate import RegularGridInterpolator
    centre, r_in, r_out, dxy = (12.462, 37.867), 3.0, 8.0, 0.005
    eu = xr.open_dataset(OUT / f'era5_u10n_{TAG}_ERA5.nc')
    ev = xr.open_dataset(OUT / f'era5_v10n_{TAG}_ERA5.nc')
    lat, lon = eu.latitude.values, eu.longitude.values
    times = pd.to_datetime(eu.time.values)
    ae = pd.read_csv(AE_CSV, index_col=0, parse_dates=True)[['u10', 'v10']].resample('1h').mean()
    ae = ae.reindex(times, method='nearest', tolerance=pd.Timedelta('30min'))
    print(f'AE hourly valid {ae.notna().all(axis=1).sum()} of {len(times)}', flush=True)
    lat_o = np.arange(lat.min(), lat.max() + dxy / 2, dxy)
    lon_o = np.arange(lon.min(), lon.max() + dxy / 2, dxy)
    LON, LAT = np.meshgrid(lon_o, lat_o)
    d = np.hypot((LON - centre[0]) * 111 * np.cos(np.radians((LAT + centre[1]) / 2)),
                 (LAT - centre[1]) * 111)
    w = np.clip((r_out - d) / (r_out - r_in), 0.0, 1.0)
    flip = lat[0] > lat[-1]
    lat_a = lat[::-1] if flip else lat
    pts = np.column_stack([LAT.ravel(), LON.ravel()])
    res = {}
    for name, ds, var, col in (('u10n', eu, 'u10n', 'u10'), ('v10n', ev, 'v10n', 'v10')):
        a = ds[var].values
        if flip:
            a = a[:, ::-1]
        o = np.empty((len(times),) + LAT.shape, dtype=np.float32)
        for it in range(len(times)):
            f = RegularGridInterpolator((lat_a, lon), a[it], bounds_error=False, fill_value=None)
            e5 = f(pts).reshape(LAT.shape)
            v = ae[col].iloc[it]
            o[it] = e5 if np.isnan(v) else (1 - w) * e5 + w * v
        res[name] = o
    for name, std in (('u10n', 'eastward_wind'), ('v10n', 'northward_wind')):
        ds = xr.Dataset(
            {name: (('time', 'latitude', 'longitude'), res[name],
                    {'standard_name': std, 'units': 'm s-1',
                     'long_name': f'10 m {std.split("_")[0]} wind, AE-only blend'})},
            coords={'time': times,
                    'latitude': ('latitude', lat_o, {'units': 'degrees_north', 'standard_name': 'latitude'}),
                    'longitude': ('longitude', lon_o, {'units': 'degrees_east', 'standard_name': 'longitude'})},
            attrs={'Conventions': 'CF-1.8',
                   'source': f'ERA5 and the AE anemometer, AE weight 1 within {r_in} km of the lagoon '
                             f'centre, 0 beyond {r_out} km',
                   'history': f'scripts/build_forcing_renewal.py {SEASON}'})
        out = OUT / f'wind_blendedAE_{name}_{TAG}.nc'
        ds.to_netcdf(out, encoding={name: {'zlib': True, 'complevel': 4, '_FillValue': np.float32(np.nan)}})
        print(f'{out.name}: {out.stat().st_size / 1e6:.0f} MB', flush=True)


def bc():
    import dfm_tools as dfmt
    import hydrolib.core.dflowfm as hcdfm
    if not hasattr(hcdfm, 'VectorQuantityUnitPairs'):   # absent from hydrolib-core 1.0.0
        from typing import Any, List
        from pydantic import BaseModel

        class _Stub(BaseModel):
            vectorname: str
            elementname: List[str]
            quantityunitpair: List[Any]

            def __iter__(self):
                return iter(self.quantityunitpair)
        hcdfm.VectorQuantityUnitPairs = _Stub
    dfmt.cmems_nc_to_bc(ext_new=hcdfm.ExtModel(),
                        list_quantities=['waterlevelbnd', 'salinitybnd', 'temperaturebnd'],
                        tstart=pd.Timestamp(D0), tstop=pd.Timestamp(D1), file_pli=str(PLI),
                        dir_pattern=str(RAW_CMEMS / 'cmems_{ncvarname}_*.nc'), dir_output=str(OUT),
                        refdate_str=f'minutes since {REFDATE:%Y-%m-%d %H:%M:%S} +00:00')
    uxuy()
    for f in sorted(OUT.glob('*.bc')):
        print(f'{f.name}: {f.stat().st_size / 1e3:.0f} kB', flush=True)


def read_pli(path):
    rows = [ln.split() for ln in path.read_text().splitlines() if ln.strip()]
    name, n = rows[0][0], int(rows[1][0])
    return name, [(float(r[0]), float(r[1]), r[2] if len(r) > 2 else None) for r in rows[2:2 + n]]


def uxuy():
    uo = xr.open_dataset(next(RAW_CMEMS.glob('cmems_uo_*.nc')))['uo']
    vo = xr.open_dataset(next(RAW_CMEMS.glob('cmems_vo_*.nc')))['vo']
    z = ' '.join(f'{-d:.6f}' for d in uo.depth.values.astype(float))
    tmin = ((pd.to_datetime(uo.time.values) - REFDATE).total_seconds() / 60.0).values
    name, pts = read_pli(PLI)
    out = OUT / 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'
    with open(out, 'w') as f:
        f.write('[General]\nfileVersion = 1.01\nfileType    = boundConds\n')
        for k, (x, y, pn) in enumerate(pts, start=1):
            u = np.nan_to_num(uo.interp(longitude=x, latitude=y).values, nan=0.0)
            v = np.nan_to_num(vo.interp(longitude=x, latitude=y).values, nan=0.0)
            f.write(f'\n[Forcing]\nname              = {pn or f"{name}_{k:04d}"}\n'
                    'function          = t3d\noffset            = 0.0\nfactor            = 1.0\n'
                    f'vertPositions     = {z}\nvertInterpolation = linear\nvertPositionType  = ZDatum\n'
                    'timeInterpolation = linear\nquantity          = time\n'
                    f'unit              = minutes since {REFDATE:%Y-%m-%d %H:%M:%S} +00:00\n'
                    'vector            = uxuyadvectionvelocitybnd:ux,uy\n')
            for iz in range(1, u.shape[1] + 1):
                f.write(f'quantity          = ux\nunit              = m s-1\nvertPositionIndex = {iz}\n'
                        f'quantity          = uy\nunit              = m s-1\nvertPositionIndex = {iz}\n')
            for it in range(len(tmin)):
                f.write(f'{tmin[it]:.6f} ' + ' '.join(f'{a:.6f} {b:.6f}' for a, b in zip(u[it], v[it])) + '\n')


def nudge():
    so = xr.open_dataset(next(RAW_CMEMS.glob('cmems_so_*.nc')))['so']
    th = xr.open_dataset(next(RAW_CMEMS.glob('cmems_thetao_*.nc')))['thetao']
    ds = xr.Dataset({'so': so.astype('float32'), 'thetao': th.astype('float32')},
                    attrs={'Conventions': 'CF-1.8',
                           'source': 'CMEMS MEDSEA_MULTIYEAR_PHY_006_004, daily means',
                           'history': f'scripts/build_forcing_renewal.py {SEASON}'})
    ds['so'].attrs = {'standard_name': 'sea_water_salinity', 'long_name': 'Salinity', 'units': 'ppt'}
    ds['thetao'].attrs = {'standard_name': 'sea_water_potential_temperature',
                          'long_name': 'Sea water potential temperature', 'units': 'degree_Celsius'}
    out = OUT / f'nudge_salinity_temperature_{D0}_00-00-00.nc'
    enc = {v: {'zlib': True, 'complevel': 4, '_FillValue': np.float32(-32767.0)} for v in ('so', 'thetao')}
    ds.to_netcdf(out, encoding=enc)
    print(f'{out.name}: {dict(ds.sizes)}, {out.stat().st_size / 1e6:.1f} MB', flush=True)


def ic():
    def write_pli(path, name, z, v):
        with open(path, 'w') as f:
            f.write(f'{name}\n    {len(z)}    2\n')
            for a, b in zip(z, v):
                f.write(f'{a:12.3f} {b:10.4f}\n')
    prof = {}
    for v in ('thetao', 'so'):
        a = xr.open_dataset(next(RAW_CMEMS.glob(f'cmems_{v}_*.nc')))[v].interp(time=T_START)
        m = a.mean(('latitude', 'longitude'), skipna=True)
        n = a.notnull().sum(('latitude', 'longitude'))
        keep = (a.depth.values <= Z_MAX) & (n.values > 0)
        z = -a.depth.values[keep][::-1]
        prof[v] = np.r_[m.values[keep][::-1][0], m.values[keep][::-1], m.values[keep][::-1][-1]]
    z = np.r_[-1000.0, z, 0.0]
    write_pli(OUT / 'ic3d_temperature_profile.pli', 'ic3d_temperature', z, prof['thetao'])
    write_pli(OUT / 'ic3d_salinity_profile.pli', 'ic3d_salinity', z, prof['so'])
    print(f'IC on {T_START}: surface T {prof["thetao"][-1]:.2f} C, S {prof["so"][-1]:.3f}; '
          f'at {z[1]:.0f} m T {prof["thetao"][1]:.2f} C, S {prof["so"][1]:.3f}', flush=True)


def laterals():
    tmin = int((pd.Timestamp(D1) - pd.Timestamp(D0)).total_seconds() / 60)
    for src in ('airport', 'saltpans'):
        for kind, q, unit in (('discharge', 'lateral_discharge', 'm3/s'),
                              ('tracer', f'tracerbndturbid_{src}', '-')):
            out = OUT / f'turbid_{src}_{kind}.bc'
            out.write_text('[General]\nfileVersion           = 1.01\nfileType              = boundConds\n\n'
                           f'[Forcing]\nname                  = turbid_{src}\nfunction              = timeseries\n'
                           'timeInterpolation     = linear\nquantity              = time\n'
                           f'unit                  = minutes since {D0} 00:00:00\n'
                           f'quantity              = {q}\nunit                  = {unit}\n'
                           f'0        0.0\n{tmin}    0.0\n')
    print('turbid laterals at zero', flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in SEASONS:
        sys.exit(f'usage: build_forcing_renewal.py {"|".join(SEASONS)} [steps]')
    configure(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    steps = {'era5': era5, 'wind': wind, 'bc': bc, 'nudge': nudge, 'ic': ic, 'laterals': laterals}
    for s in sys.argv[2:] or list(steps):
        print(f'=== {s}', flush=True)
        steps[s]()
