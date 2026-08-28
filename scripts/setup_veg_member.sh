#!/bin/bash
# Build any factorial member on FM's native vegetation module instead of
# trachytopes, over the drifter window.
#
# Why the native module rather than trachytopes. Measured this session, each by
# a bit-identical control pair:
#
#   the trachytope momentum sink (formulas 154/155/156) is computed and never
#   read by the solver, so 154 delivered only its bed Chezy and modelled the
#   meadow SMOOTHER than bare sand (lagoon cftrt 0.018 against 0.023);
#
#   the [veg] module is live and local -- 20625 bare offshore cells move by
#   0.2% while vegetated lagoon cells go to 0.26 of the control;
#
#   and it shelters the bed the way a meadow should: taus falls by a factor 11
#   over the meadow, where a bed roughness of equivalent magnitude RAISES it.
#   That last one is why the mobile-bed arm belongs here and not on 153, whose
#   canopy-as-bed-roughness drove the spurious 51 cm of bed change.
#
# Parameters are literature throughout, none tuned against observations:
#   stemdensity  Ciraolo et al. (2006), 500 plants/m2 x 6 leaves, x cover
#   stemdiameter 0.01 m, same source
#   stemheight   0.40 m -- CANOPY height, not leaf length. Prinos et al. (2010)
#                run h_s/D of 0.323-0.500, Ciraolo's measured deflected
#                thickness k/h sits at 0.2-0.6, and field observation in this
#                lagoon agrees that Posidonia rarely reaches the surface.
#   Rhoveg       900 kg/m3, Prinos Table 1 (natural leaf 800-1020)
#   Cdveg        0.8, rigid-cylinder, NOT fitted
#
# Held out and never consulted while choosing any of the above: the three tide
# gauges and the 35 drifters.
#
#   bash setup_veg_member.sh <src_model_dir> <dst_name> [--launch]
set -e

SRC_NAME=$1; DST_NAME=$2; LAUNCH=$3
[ -n "$DST_NAME" ] || { sed -n '40,42p' "$0"; exit 1; }

B=~/StagnoneDT/model
REF=$B/_veg_hv040          # carries the fields and the [veg] block
START=${START:-20250707}
STOP=${STOP:-20250710000000}

[ -d "$B/$SRC_NAME" ] || { echo "missing $B/$SRC_NAME"; exit 1; }
[ -d "$REF" ] || { echo "missing reference $REF"; exit 1; }

cd ~/StagnoneDT
bash scripts/setup_restart_segment.sh "$SRC_NAME" "$DST_NAME" "$START" "$STOP" > /dev/null
d=$B/$DST_NAME

cp "$REF"/veg_stemheight.xyz "$REF"/veg_stemdensity.xyz \
   "$REF"/veg_stemdiameter.xyz "$REF"/initialFields.ini "$d/"
for m in "$d"/*.mdu; do
    # Trachytopes off: the .arl/.ttd would otherwise add a second, redundant
    # roughness on top of the canopy, and its sink is dead anyway.
    sed -i 's|^\( *trtRou *= *\)Y|\1N|I' "$m"
    sed -n '/^\[veg\]/,$p' "$REF"/Stagnone_dxy01_15m.mdu >> "$m"
done

echo "=== $DST_NAME (de $SRC_NAME) ==="
printf '  janela %s -> %s   mapInterval %s\n' \
    "$(grep -ioE '^startDateTime *= *[0-9]+' "$d"/Stagnone_dxy01_15m_0000.mdu | awk '{print $NF}')" \
    "$(grep -ioE '^stopDateTime *= *[0-9]+' "$d"/Stagnone_dxy01_15m_0000.mdu | awk '{print $NF}')" \
    "$(grep -ioE '^ *mapInterval *= *[0-9.]+' "$d"/Stagnone_dxy01_15m.mdu | awk '{print $NF}')"
printf '  trtRou %s   [veg] em %s/%s mdu   Rhoveg %s  Cdveg %s  h_v max %s\n' \
    "$(grep -ihoE '^ *trtRou *= *[YN]' "$d"/Stagnone_dxy01_15m.mdu | awk '{print $NF}')" \
    "$(grep -l '^\[veg\]' "$d"/*.mdu | wc -l)" "$(ls "$d"/*.mdu | wc -l)" \
    "$(grep -ihoE '^Rhoveg *= *[0-9.]+' "$d"/Stagnone_dxy01_15m.mdu | awk '{print $NF}')" \
    "$(grep -ihoE '^Cdveg *= *[0-9.]+' "$d"/Stagnone_dxy01_15m.mdu | awk '{print $NF}')" \
    "$(awk '{print $3}' "$d"/veg_stemheight.xyz | sort -g | tail -1)"
printf '  restart %s/8   esmf %s   hot velhos %s   sedimento %s\n' \
    "$(ls "$d"/restart_input/*.nc 2>/dev/null | wc -l)" \
    "$(ls "$d"/wave/TMP_ESMF*.nc 2>/dev/null | wc -l)" \
    "$(ls "$d"/wave/hot_*.nc "$d"/hot_*.nc 2>/dev/null | wc -l)" \
    "$(grep -ihoE '^ *(MorFile|SedFile) *= *\S+' "$d"/Stagnone_dxy01_15m.mdu | wc -l)"

[ "$LAUNCH" = "--launch" ] || { echo "  (re-rode com --launch para iniciar)"; exit 0; }

cd "$d"
nohup bash -c 'source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
               export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64
               export PATH=$DELFT3D_HOME/bin:$PATH
               export LD_LIBRARY_PATH=$DELFT3D_HOME/lib:$LD_LIBRARY_PATH
               run_dimr.sh -c 8 -m dimr_config.xml' \
    > ~/154_logs/$DST_NAME.log 2>&1 &
echo "  lancado pid $!"
