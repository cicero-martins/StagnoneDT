#!/bin/bash
# Is D-Flow FM's native vegetation module live, the way the trachytope momentum
# sink is not?
#
# The trachytope path was settled by measurement: with formula 154, changing
# C_D from 0.00 to 0.80 -- which under a clamped canopy changes ONLY the
# momentum sink, by 4.0 1/m over 16359 links -- gave a bit-identical solution
# over 48 frames and 27901 cells. FM computes rttfu and never reads it.
#
# FM's own vegetation lives elsewhere: [veg], Vegetationmodelnr, m_vegetation,
# setbaptist.f90, producing cfuveg on links. Before building anything on it,
# the same question has to be asked of it, because the lesson of the trachytope
# result is that "implemented" and "reaches the momentum equation" are separate
# claims.
#
# Two clones, identical but for one line:
#
#   C  Vegetationmodelnr = 0     vegetation off
#   D  Vegetationmodelnr = 1     Baptist DFM, same fields present on disk
#
# Trachytopes are switched off in both, so the roughness field is the plain
# uniform Manning 0.023 and vegetation is the only thing that can differ.
#
# A null result is ambiguous on its own -- inert module, or fields that never
# loaded -- so check mesh2d_stemheight in D's map.nc before reading anything
# into it. FM carries ID_VEG_STEMHEIGHT as a map output for exactly this.
#
#   bash setup_veg_module_test.sh [--launch]
set -e

BASE=~/StagnoneDT/model
SRC=dflowfm_v04AE_nowaves_vr_154
VEG=/tmp/vegfields
START=20250708
STOP=20250709000000
LAUNCH=$1

for v in C D; do
    if [ "$v" = "C" ]; then nr=0; else nr=1; fi
    dst=$BASE/_veg_$v
    echo "=== variant $v : Vegetationmodelnr = $nr ==="

    bash ~/StagnoneDT/scripts/setup_restart_segment.sh "$SRC" "_veg_$v" \
        "$START" "$STOP" > /dev/null

    cp "$VEG"/veg_stemheight.xyz "$VEG"/veg_stemdensity.xyz \
       "$VEG"/veg_stemdiameter.xyz "$dst/"

    # Spatial vegetation properties are parameters, not initial conditions, so
    # they go in [Parameter] blocks rather than the [Initial] ones already in
    # the file. Quantity names are FM's own: stemheight, stemdensity,
    # stemdiameter.
    for q in stemheight stemdensity stemdiameter; do
        cat >> "$dst/initialFields.ini" <<EOF

[Parameter]
    quantity              = $q
    dataFile              = veg_$q.xyz
    dataFileType          = sample
    interpolationMethod   = averaging
    averagingType         = mean
    operand               = O
EOF
    done

    # Every partition MDU, not just the base one: FM reads the rank's file.
    for m in "$dst"/Stagnone_dxy01_15m.mdu "$dst"/Stagnone_dxy01_15m_0[0-9][0-9][0-9].mdu; do
        [ -f "$m" ] || continue
        sed -i 's|^\( *trtRou *= *\)Y|\1N|I' "$m"
        cat >> "$m" <<EOF

[veg]
Vegetationmodelnr         = $nr
Cdveg                     = 0.8
Clveg                     = 0.0
Rhoveg                    = 0.0
StemheightConvention      = upward_from_bed
EOF
    done

    printf '  trtRou now: %s\n' "$(grep -ioE '^ *trtRou *= *[YN]' "$dst"/Stagnone_dxy01_15m.mdu | awk '{print $NF}')"
    printf '  [veg] in %s of %s mdu files\n' \
        "$(grep -l '^\[veg\]' "$dst"/*.mdu | wc -l)" "$(ls "$dst"/*.mdu | wc -l)"
    printf '  Parameter blocks: %s   xyz present: %s\n' \
        "$(grep -c '^\[Parameter\]' "$dst/initialFields.ini")" \
        "$(ls "$dst"/veg_*.xyz | wc -l)"
done

[ "$LAUNCH" = "--launch" ] || { echo; echo "re-run with --launch to start."; exit 0; }

echo; echo "=== launching ==="
for v in C D; do
    cd "$BASE/_veg_$v"
    nohup bash -c "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1;
                   export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64;
                   export PATH=\$DELFT3D_HOME/bin:\$PATH;
                   export LD_LIBRARY_PATH=\$DELFT3D_HOME/lib:\$LD_LIBRARY_PATH;
                   run_dimr.sh -c 8 -m dimr_config.xml" \
          > ~/154_logs/_veg_$v.log 2>&1 &
    echo "  $v -> pid $!"
done
