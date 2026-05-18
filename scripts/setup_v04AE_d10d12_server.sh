#!/usr/bin/env bash
#
# Setup v04AE_d10d12 on simit-server: clone v04AE, wire Jul 10 restart,
# update meteo forçantes (Jul 1-13), patch MDU + ext + dimr_config.
#
# Run AFTER transferring new meteo .nc files into ~/StagnoneDT/d10d12_drop/
# (which contains: era5_*_20250701to20250713_ERA5.nc x5,
#                  wind_blendedAE_{u10n,v10n}_20250701to20250713.nc x2,
#                  wind_era5raw_{u10n,v10n}_20250701to20250713.nc x2).
#
# Idempotent: safe to re-run. Existing v04AE_d10d12 is NOT overwritten.

set -euo pipefail

V04AE="${V04AE:-$HOME/StagnoneDT/model/dflowfm_v04AE}"
NEW="${NEW:-$HOME/StagnoneDT/model/dflowfm_v04AE_d10d12}"
DROP="${DROP:-$HOME/StagnoneDT/d10d12_drop}"

# Sanity checks
[[ -d "$V04AE" ]] || { echo "ERROR: $V04AE not found"; exit 2; }
[[ -d "$DROP"  ]] || { echo "ERROR: $DROP not found (transfer new meteo files first)"; exit 2; }

# 0. Verify Jul 10 restart files exist in source
echo "=== [0/8] Verifying source state ==="
src_rst=("$V04AE"/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_000{0,1,2,3,4,5,6,7}_20250710_000000_rst.nc)
for f in "${src_rst[@]}"; do
  [[ -f "$f" ]] || { echo "ERROR: missing $f"; exit 3; }
done
echo "  8/8 Jul 10 restart files found ✓"

# 1. Clone v04AE → v04AE_d10d12 (exclude bulky outputs)
echo "=== [1/8] Cloning v04AE → v04AE_d10d12 ==="
if [[ -d "$NEW" ]]; then
  echo "  Target already exists at $NEW — backing up to $NEW.bak.$(date +%Y%m%d_%H%M%S)"
  mv "$NEW" "$NEW.bak.$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$NEW"
# rsync excluding DFM_OUTPUT, backups, large logs
rsync -a \
  --exclude='DFM_OUTPUT_Stagnone_dxy01_15m/' \
  --exclude='DFM_OUTPUT_*.bak.*' \
  --exclude='*.cache' \
  --exclude='run_phaseA_*.log' \
  --exclude='wave/BOTNOW' --exclude='wave/CURNOW' --exclude='wave/WNDNOW' \
  --exclude='wave/PRINT-*' --exclude='wave/swan_omp.exe' \
  "$V04AE"/ "$NEW"/
echo "  Cloned $(du -sh $NEW | cut -f1)"

# 2. Set up restart_input/ with Jul 10 rst files
echo "=== [2/8] Setting up restart_input/ ==="
mkdir -p "$NEW/restart_input"
for n in 0 1 2 3 4 5 6 7; do
  rank=$(printf "%04d" $n)
  cp "$V04AE/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_${rank}_20250710_000000_rst.nc" \
     "$NEW/restart_input/"
done
ls -la "$NEW/restart_input/" | head -10

# 3. Replace meteo forçantes + CMEMS BC .bc with new versions
echo "=== [3/8] Replacing meteo forçantes (Jul 1-13) + CMEMS BCs (rebuilt) ==="
# Remove old Jul 1-10 versions
rm -f "$NEW"/era5_*_20250701to20250710_ERA5.nc
rm -f "$NEW"/wind_blendedAE_*_20250701to20250710.nc
rm -f "$NEW"/wind_era5raw_*_20250701to20250710.nc
# Install new Jul 1-13 meteo from drop
cp -v "$DROP"/era5_*_20250701to20250713_ERA5.nc       "$NEW/"
cp -v "$DROP"/wind_blendedAE_*_20250701to20250713.nc   "$NEW/"
cp -v "$DROP"/wind_era5raw_*_20250701to20250713.nc     "$NEW/" 2>/dev/null || true
# Install rebuilt CMEMS .bc files (waterlevel, salinity, temperature have fresh Jul 1-13;
# uxuy + offset_pernode + constant are copies from v04AE as fallback - see build script).
# Overwrite the v04AE versions cloned in [1/8].
for bc in waterlevelbnd_CMEMS_Stagnone_dxy01_15m.bc \
          salinitybnd_CMEMS_Stagnone_dxy01_15m.bc \
          temperaturebnd_CMEMS_Stagnone_dxy01_15m.bc \
          uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc \
          waterlevelbnd_offset_pernode_Stagnone_dxy01_15m.bc \
          waterlevelbnd_constant_Stagnone_dxy01_15m.bc; do
  if [[ -f "$DROP/$bc" ]]; then
    cp -v "$DROP/$bc" "$NEW/"
  fi
done

# 4. Patch ext file to point to new file names (replace 20250710 -> 20250713)
echo "=== [4/8] Patching Stagnone_dxy01_15m_new.ext ==="
EXT="$NEW/Stagnone_dxy01_15m_new.ext"
cp "$EXT" "$EXT.bak"
sed -i 's|_20250701to20250710\.nc|_20250701to20250713.nc|g' "$EXT"
echo "  Updated meteo refs in $EXT (diff vs .bak):"
diff "$EXT.bak" "$EXT" | head -20 || true

# 5. Patch master MDU: time window + restart + ensure caps active
echo "=== [5/8] Patching master MDU ==="
MDU="$NEW/Stagnone_dxy01_15m.mdu"
cp "$MDU" "$MDU.bak"
# Time window
sed -i 's/^tStop\s*=.*/tStop                   = 172800.0       # Continuation: 2 days Jul 10->12 2025/' "$MDU"
sed -i 's/^startDateTime\s*=.*/startDateTime           = 20250710000000 # d10d12: warm-start Jul 10 00:00/' "$MDU"
sed -i 's/^stopDateTime\s*=.*/stopDateTime            = 20250712000000 # d10d12: stop Jul 12 00:00/' "$MDU"
# Restart (generic path; FM will insert _NNNN_ at partition step — BUT we skip partition,
# so we'll set explicit per-partition paths in step 6 instead)
sed -i 's|^restartFile\s*=.*|restartFile     = restart_input/Stagnone_dxy01_15m_20250710_000000_rst.nc|' "$MDU"
sed -i 's|^restartDateTime\s*=.*|restartDateTime = 20250710000000|' "$MDU"
# Crash insurance caps (re-enable in case master has them disabled)
sed -i 's/^maxVelocity\s*=\s*0\.0.*/maxVelocity               = 10.0/' "$MDU"
sed -i 's/^saliMax\s*=\s*-999\.0.*/saliMax                        = 80.0/' "$MDU"

grep -E "^(tStop|startDateTime|stopDateTime|restartFile|restartDateTime|maxVelocity|saliMax)" "$MDU"

# 6. Patch per-partition MDUs with rank-specific restart path
echo "=== [6/8] Patching per-partition MDUs (rank-specific restart) ==="
for n in 0 1 2 3 4 5 6 7; do
  rank=$(printf "%04d" $n)
  PMDU="$NEW/Stagnone_dxy01_15m_${rank}.mdu"
  [[ -f "$PMDU" ]] || { echo "WARN: $PMDU not found, skipping"; continue; }
  cp "$PMDU" "$PMDU.bak"
  # Same time window
  sed -i 's/^tStop\s*=.*/tStop                   = 172800.0/' "$PMDU"
  sed -i 's/^startDateTime\s*=.*/startDateTime           = 20250710000000/' "$PMDU"
  sed -i 's/^stopDateTime\s*=.*/stopDateTime            = 20250712000000/' "$PMDU"
  # Restart: rank-specific
  sed -i "s|^restartFile\s*=.*|restartFile     = restart_input/Stagnone_dxy01_15m_${rank}_20250710_000000_rst.nc|" "$PMDU"
  sed -i 's|^restartDateTime\s*=.*|restartDateTime = 20250710000000|' "$PMDU"
  # Caps
  sed -i 's/^maxVelocity\s*=\s*0\.0.*/maxVelocity               = 10.0/' "$PMDU"
  sed -i 's/^saliMax\s*=\s*-999\.0.*/saliMax                        = 80.0/' "$PMDU"
done
echo "  Rank 0 sample:"
grep -E "^(tStop|startDateTime|stopDateTime|restartFile)" "$NEW/Stagnone_dxy01_15m_0000.mdu"

# 7. Patch dimr_config.xml
echo "=== [7/8] Patching dimr_config.xml ==="
DIMR="$NEW/dimr_config.xml"
cp "$DIMR" "$DIMR.bak"
# Wave coupling time: 0 600 <tStop>
sed -i 's|<time>0 600 [0-9]\+</time>|<time>0 600 172800</time>|' "$DIMR"
# Ensure process list has 8 ranks (in case master has different N)
PROCESSSTR="$(seq -s ' ' 0 7)"
sed -i "s|\(<process.*>\)[^<>]*\(<\/process.*\)|\1$PROCESSSTR\2|" "$DIMR"
grep -E "(time|process)>" "$DIMR" | head -5

# 8. Stale com.nc protection + final summary
echo "=== [8/8] Cleanup + Summary ==="
rm -f "$NEW"/*.cache "$NEW"/DFM_OUTPUT_Stagnone_dxy01_15m/*.cache 2>/dev/null || true
# wave/swaninit may carry Windows paths, clean it
rm -f "$NEW/wave/swaninit"

echo ""
echo "Setup complete. To run:"
echo "  cd $NEW"
echo "  ./run_model.sh --skip-partition  # OR if run_model.sh missing, see below"
echo ""
if [[ ! -x "$NEW/run_model.sh" ]]; then
  echo "Note: $NEW does not have an executable run_model.sh. Run manually:"
  echo "  export OMP_NUM_THREADS=8 KMP_HW_SUBSET=8c,1t"
  echo "  export PATH=\$HOME/Scaricati/delft3dfm/lnx64/bin:\$PATH"
  echo "  export LD_LIBRARY_PATH=\$HOME/Scaricati/delft3dfm/lnx64/lib:\$LD_LIBRARY_PATH"
  echo "  run_dimr.sh -c 8 -m dimr_config.xml"
fi
