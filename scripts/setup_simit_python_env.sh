#!/usr/bin/env bash
# Install miniforge + dfm_tools_env on simit-server.
# Run once. Idempotent: skips if already installed.
#
# After this, $HOME/miniforge3/envs/dfm_tools_env/bin/python has all deps
# needed by the Phase B orchestrator: xarray, netcdf4, copernicusmarine,
# cdsapi, dfm_tools, hydrolib-core, etc.

set -euo pipefail

INSTALL_DIR="$HOME/miniforge3"
ENV_NAME="dfm_tools_env"

echo "=== [1/4] miniforge installer ==="
if [[ -d "$INSTALL_DIR" ]]; then
    echo "  miniforge already at $INSTALL_DIR — skipping install"
else
    cd /tmp
    URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
    echo "  Downloading $URL"
    curl -fsSLo Miniforge3.sh "$URL"
    bash Miniforge3.sh -b -p "$INSTALL_DIR"
    rm -f Miniforge3.sh
    echo "  Installed to $INSTALL_DIR"
fi

# Source conda for this shell
# shellcheck disable=SC1091
source "$INSTALL_DIR/etc/profile.d/conda.sh"

echo "=== [2/4] Create env $ENV_NAME (if missing) ==="
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "  env $ENV_NAME already exists — skipping create"
else
    # Core scientific stack via conda (fast & reliable)
    conda create -y -n "$ENV_NAME" \
        python=3.11 \
        numpy pandas scipy xarray netcdf4 matplotlib \
        requests pyyaml \
        -c conda-forge
fi

# Activate the env
conda activate "$ENV_NAME"

echo "=== [3/4] pip extras (copernicusmarine, cdsapi, dfm_tools, hydrolib-core) ==="
# These are pip-only or have better pip releases
python -m pip install --upgrade pip
python -m pip install \
    'copernicusmarine>=2.0' \
    'cdsapi>=0.7' \
    'dfm_tools==0.45.0' \
    'hydrolib-core==1.0.0' \
    'xugrid' \
    'pip-system-certs'    # required for SSL on some RHEL setups; harmless if not needed

echo "=== [4/4] Smoke test ==="
python -c "
import sys, xarray, numpy, pandas, netCDF4, dfm_tools, hydrolib.core, copernicusmarine, cdsapi
print(f'Python      : {sys.version.split()[0]}')
print(f'xarray      : {xarray.__version__}')
print(f'pandas      : {pandas.__version__}')
print(f'netCDF4     : {netCDF4.__version__}')
print(f'dfm_tools   : {dfm_tools.__version__}')
print(f'hydrolib    : {hydrolib.core.__version__}')
print(f'copernicus  : {copernicusmarine.__version__}')
print(f'cdsapi      : {cdsapi.__version__}')
print()
print(f'env python  : {sys.executable}')
"

echo ""
echo "Done. Activate with:"
echo "  source $INSTALL_DIR/etc/profile.d/conda.sh && conda activate $ENV_NAME"
echo ""
echo "For non-interactive scripts (cron, nohup), call python directly:"
echo "  $INSTALL_DIR/envs/$ENV_NAME/bin/python ..."
echo ""
echo "Credentials: copy ~/.cdsapirc + ~/.copernicusmarine/.copernicusmarine-credentials from local."
