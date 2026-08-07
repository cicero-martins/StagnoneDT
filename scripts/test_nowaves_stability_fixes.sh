#!/bin/bash
# Three diagnostic clones of nowaves_vrdm, testing two candidate fixes and their
# combination. vrdm is the harder of the two failing members: it reaches
# 43.42 m/s against 26.96 for dm, so a pass here is meaningful.
#
# Both candidates target the region where the runaway actually is, which the
# crashed output puts offshore, spread over the western sector around the Egadi,
# median depth 34 m, with no cell inside the lagoon and none above the datum.
#
#   dens  MorFile DensIn = false
#         Suspended sediment currently feeds the density field and therefore the
#         baroclinic pressure gradient. In a deep cell with no erodible thickness
#         that is the only path by which sediment can move momentum, which would
#         explain why capping erodible thickness below 20 m changed nothing.
#
#   cst   MDU cstbnd = 1
#         Technical Reference 6.4.3, Algorithm 29: with cstbnd = 0 the ghost cell
#         at a boundary face receives (uc_R . n) n, the interior velocity
#         projected onto the boundary normal, so the tangential component is
#         discarded and an artificial shear is created along every open boundary.
#         With cstbnd = 1 the full interior vector is copied. We prescribe
#         uxuyadvectionvelocitybnd, that is full velocity vectors with tangential
#         components, so cstbnd = 0 is inconsistent with our own boundary data.
#         The FM property list describes this option as being for small coastal
#         models, which is what this is.
#
#   both  the two together, as insurance against each being necessary but not
#         sufficient
set -e
cd "$HOME/StagnoneDT/model"
SRC=dflowfm_v04AE_nowaves_vrdm

for tag in dens cst both; do
  dst="${SRC}_${tag}"
  rm -rf "$dst"; mkdir -p "$dst"
  rsync -a \
    --exclude 'DFM_OUTPUT_*' \
    --exclude '*_000?.mdu' \
    --exclude '*_000?_net.nc' \
    --exclude 'DFM_interpreted_*' \
    --exclude '*.bak*' \
    --exclude 'diag/' \
    --exclude '*.log' \
    --exclude 'wave/' \
    "$SRC/" "$dst/"
  mkdir -p "$dst/diag"

  case $tag in
    dens|both) sed -i -E 's|^([[:space:]]*DensIn[[:space:]]*=).*|\1 false|I' "$dst"/*.mor ;;
  esac
  case $tag in
    cst|both)  sed -i -E 's|^([[:space:]]*cstBnd[[:space:]]*=)[^#]*|\1 1      |I' "$dst"/*.mdu ;;
  esac

  printf '%-38s DensIn=%-6s cstBnd=%s\n' "$dst" \
    "$(grep -ioP 'DensIn\s*=\s*\K\S+' "$dst"/*.mor | head -1)" \
    "$(grep -ioP 'cstBnd\s*=\s*\K\S+' "$dst"/*.mdu | head -1)"
done

source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
for tag in dens cst both; do
  d="${SRC}_${tag}"
  cd "$HOME/StagnoneDT/model/$d"
  nohup bash -c "
    export PATH='$PATH'
    export LD_LIBRARY_PATH='$LD_LIBRARY_PATH'
    cd '$HOME/StagnoneDT/model/$d'
    exec run_dimr.sh -c 8 -m dimr_config.xml
  " > diag/run.log 2>&1 &
  echo "launched $d  pid $!"
  disown
done

echo
echo "24 MPI ranks on 96 cores. The previous concurrency was never the problem:"
echo "the aborts are the velocity cap, deterministic to the bit."
