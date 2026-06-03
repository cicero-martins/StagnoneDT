"""
Optimize Wind and Pressure NetCDF files by reducing spatial resolution and applying compression.
Targets files in model/dflowfm_v05/
"""
import sys
try:
    import xarray as xr
    import numpy as np
    import scipy
except ImportError:
    print("\nERRO: Bibliotecas necessárias não encontradas.")
    print("Por favor, instale-as executando: pip install xarray netcdf4 scipy")
    sys.exit(1)
from pathlib import Path

def optimize_wind_file(input_path: Path, res_deg: float = 0.03):
    """
    Reduces resolution, converts to float32 and saves with compression.
    res_deg: 0.03 degrees is approx 3km.
    """
    output_path = input_path.with_name(input_path.stem + "_optimized.nc")
    
    if not input_path.exists():
        print(f"Aviso: Arquivo nao encontrado: {input_path.name}")
        return

    print(f"Lendo {input_path.name}...")
    # Usamos chunks={} para abrir de forma lazy se o arquivo for muito grande
    ds = xr.open_dataset(input_path)
    
    # Detectar nomes das dimensões (podem ser longitude/latitude ou lon/lat)
    lon_name = 'longitude' if 'longitude' in ds.dims else 'lon'
    lat_name = 'latitude' if 'latitude' in ds.dims else 'lat'

    # 1. Definir nova grade mais esparsa
    lons = ds[lon_name].astype(np.float32).values
    lats = ds[lat_name].astype(np.float32).values

    # Detectar resolucao atual
    current_res = abs(lons[1] - lons[0]) if len(lons) > 1 else 1.0

    # Se o arquivo for MSL (pressao), usamos uma resolucao bem mais esparsa (ex: 0.05 deg ~= 5km)
    # ja que a pressao varia muito pouco no espaco em relacao ao vento.
    if "msl" in input_path.name.lower():
        target_res = max(res_deg, 0.05)
    else:
        target_res = res_deg

    # NUNCA fazer upsampling (aumentar resolucao) para economizar espaco.
    # Se a grade ja for mais grossa que o alvo, mantemos a original.
    if target_res <= current_res * 1.05:
        print(f"  Pulando interpolacao: resolucao atual ({current_res:.4f}) ja e adequada.")
        ds_small = ds
        new_lons, new_lats = lons, lats
    else:
        print(f"  Reduzindo grade de {len(lons)}x{len(lats)} para uma grade de ~{target_res:.4f} deg...")
        new_lons = np.arange(lons.min(), lons.max() + target_res/2, target_res)
        new_lats = np.arange(lats.min(), lats.max() + target_res/2, target_res)
        interp_dict = {lon_name: new_lons, lat_name: new_lats}
        ds_small = ds.interp(**interp_dict, method="linear")

    # 2. Limpar encodings e converter para float32
    # Xarray guarda metadados de escala originais que podem inflar o arquivo ao salvar
    ds_small.encoding = {}
    for var in ds_small.data_vars:
        ds_small[var] = ds_small[var].astype(np.float32)
        ds_small[var].encoding = {}

    for coord in ds_small.coords:
        if coord != 'time':
            ds_small[coord].encoding = {}
        
    # 3. Configurar compressao zlib
    encoding = {}
    # Aplicar compressao em variaveis e coordenadas espaciais
    vars_to_encode = list(ds_small.data_vars) + [lon_name, lat_name]
    for v in vars_to_encode:
        encoding[v] = {
            "zlib": True,
            "complevel": 4,
        }
        if v in ds_small.data_vars:
            encoding[v]["dtype"] = "float32"
            encoding[v]["_FillValue"] = -9999.0
    
    print(f"  Salvando... Grade final: {len(new_lons)}x{len(new_lats)}")
    ds_small.to_netcdf(output_path, encoding=encoding, format="NETCDF4")
    
    orig_size = input_path.stat().st_size / 1e6
    new_size = output_path.stat().st_size / 1e6
    print(f"  Sucesso! {orig_size:.2f}MB -> {new_size:.2f}MB (Redução de {100*(1-new_size/orig_size):.1f}%)")
    return output_path

def main():
    base_dir = Path(r"C:\Users\Unipa\Documents\StagnoneDT\model\dflowfm_v05")
    
    # Arquivos identificados na versão v05
    files_to_process = [
        "wind_blendedAE_u10n_20250701to20250713.nc",
        "wind_blendedAE_v10n_20250701to20250713.nc",
        "era5_msl_20250701to20250713_ERA5.nc"
    ]
    
    print("Iniciando otimização de arquivos atmosféricos...")
    for fname in files_to_process:
        fpath = base_dir / fname
        optimize_wind_file(fpath, res_deg=0.03) # 3km de resolução

    print("\nConcluído. Lembre-se de atualizar o arquivo .ext para usar os arquivos '_optimized.nc'.")

if __name__ == "__main__":
    main()