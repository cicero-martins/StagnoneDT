"""
Extract clean time series from data/raw/insitu/dati_2025-26/*.xlsx
into UTC-indexed CSVs under data/processed/insitu_2025-26/.

Variables extracted:
  - Wind AE     (Vest=u_east, Vnord=v_north components, m/s)        -> AE_wind_UTC.csv
  - Wind Mulino                                                     -> Mulino_wind_UTC.csv
  - WL  AE, BN, BS  (h in metres above sensor zero)                 -> {AE,BN,BS}_wl_UTC.csv
  - Atm pressure AE, Mulino (mbar)                                  -> {AE,Mulino}_atm_UTC.csv
  - WaterTemp AE, BN, BS (Celsius)                                  -> {AE,BN,BS}_twater_UTC.csv

Time zone:
  - Source: "CET Solare" = CET with no DST = UTC+1 constant
  - Shift -1 h to convert to UTC.

Convention:
  - Vest (m/s) interpreted as eastward wind component (u10), positive=east.
  - Vnord (m/s) interpreted as northward wind component (v10), positive=north.
  Validated by physical sanity at AE Jul 10 2025 12:00 UTC:
    Vest=+0.74, Vnord=-5.35 -> derived dir_from = 352 deg (north wind), speed=5.4 m/s.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'data' / 'raw' / 'insitu' / 'dati_2025-26'
DST = ROOT / 'data' / 'processed' / 'insitu_2025-26'
DST.mkdir(parents=True, exist_ok=True)

CET_TO_UTC = pd.Timedelta(hours=-1)


def _read_first_sheet(path):
    df = pd.read_excel(path)
    return df


def _to_utc(df, time_col):
    df = df.rename(columns={time_col: 'time'})
    df['time'] = pd.to_datetime(df['time']) + CET_TO_UTC
    return df.set_index('time').sort_index()


def extract_wind(name, time_col, u_col, v_col):
    src = SRC / f'{name}_windEeN.xlsx'
    df = _read_first_sheet(src)
    df = _to_utc(df, time_col)
    out = pd.DataFrame({
        'u10': df[u_col].astype('float32'),
        'v10': df[v_col].astype('float32'),
    }, index=df.index)
    out['speed'] = (out['u10']**2 + out['v10']**2)**0.5
    csv_out = DST / f'{name}_wind_UTC.csv'
    out.to_csv(csv_out, float_format='%.4f')
    print(f'wrote {csv_out}  ({len(out)} rows, {out.index.min()} -> {out.index.max()})')
    return out


def extract_wl(name, time_col, h_col):
    src = SRC / f'{name}_livelli.xlsx'
    df = _read_first_sheet(src)
    df = _to_utc(df, time_col)
    out = pd.DataFrame({'h_m': df[h_col].astype('float32')}, index=df.index)
    csv_out = DST / f'{name}_wl_UTC.csv'
    out.to_csv(csv_out, float_format='%.4f')
    print(f'wrote {csv_out}  ({len(out)} rows, {out.index.min()} -> {out.index.max()})')
    return out


def extract_atm(name, time_col, p_col):
    src = SRC / f'{name}_atm.xlsx'
    df = _read_first_sheet(src)
    df = _to_utc(df, time_col)
    out = pd.DataFrame({'p_mbar': df[p_col].astype('float32')}, index=df.index)
    csv_out = DST / f'{name}_atm_UTC.csv'
    out.to_csv(csv_out, float_format='%.3f')
    print(f'wrote {csv_out}  ({len(out)} rows, {out.index.min()} -> {out.index.max()})')
    return out


def extract_twater(name, time_col, prefer_keyword='Eureka'):
    """Water temp columns vary in encoding ('T Acqua (degC)' with degree sign).
    Match by substring 'Acqua' (water in Italian). If multiple, prefer the one
    containing prefer_keyword (e.g., 'Eureka' sensor)."""
    src = SRC / f'{name}_tempWater.xlsx'
    df = _read_first_sheet(src)
    df = _to_utc(df, time_col)
    candidates = [c for c in df.columns if 'Acqua' in c]
    if not candidates:
        raise ValueError(f'No water-temp column found in {src}. Columns: {list(df.columns)}')
    if len(candidates) > 1:
        preferred = [c for c in candidates if prefer_keyword in c]
        col = preferred[0] if preferred else candidates[0]
    else:
        col = candidates[0]
    out = pd.DataFrame({'t_water_C': pd.to_numeric(df[col], errors='coerce').astype('float32')}, index=df.index)
    csv_out = DST / f'{name}_twater_UTC.csv'
    out.to_csv(csv_out, float_format='%.3f')
    print(f'wrote {csv_out}  ({len(out)} rows, source col: {col!r}, '
          f'{out.index.min()} -> {out.index.max()})')
    return out


if __name__ == '__main__':
    # Wind
    extract_wind('AE',     time_col='CET Solare', u_col='AE Vest (m/s)',     v_col='AE Vnord (m/s)')
    extract_wind('Mulino', time_col='CET solare', u_col='Mulino Vest (m/s)', v_col='Mulino Vnord (m/s)')

    # Water level (h in metres)
    extract_wl('AE', time_col='CET solare', h_col='h(m)')
    extract_wl('BN', time_col='CET Solare', h_col='h (m)')
    extract_wl('BS', time_col='CET Solare', h_col='h (m)')

    # Atmospheric pressure
    extract_atm('AE',     time_col='CET Solare', p_col='pressione (mbar)')
    extract_atm('Mulino', time_col='CET Solare', p_col='pressione (mbar)')

    # Water temperature
    # AE has both T_air and T_water — keep T_water Eureka sensor
    extract_twater('AE', time_col='CET Solare', prefer_keyword='Eureka')
    extract_twater('BN', time_col='CET Solare')
    extract_twater('BS', time_col='CET Solare', prefer_keyword='Eureka')

    print('\nAll extractions complete. Output in', DST)
