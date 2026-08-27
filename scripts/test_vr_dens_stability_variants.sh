#!/bin/bash
# Find a setting that lets v04AE_vr_dens run with the corrected roughness.
#
# test_vr_dens_arl_control.sh established the cause: two clones of the same
# original, identical but for one file, and the 6-decimal .arl completed six
# simulated hours while the 9-decimal one broke on MinTimestepBreak. So the
# question is no longer what triggers it but what absorbs it.
#
# What the diagnosis rules out. The velocity field is not blowing up: at the
# same instant the corrected run is slower than the original everywhere
# (p50 0.208 vs 0.291 m/s, max 2.92 vs 2.84). Sediment is confined to the
# lagoon by sedthick_lagoon.xyz and morphology only starts at 24 h, long after
# the failure. The limiting cells rove between attempts, all in the Egadi, so
# there is no single geometric defect to repair.
#
# What it points at. The corrected field reaches Manning 0.28, and the 536
# links above 0.15 all sit in water 0.18 to 0.75 m deep inside the lagoon.
# That is Baptist dividing by depth, which is the formula behaving as written
# rather than a placement error, but it makes the friction term stiff exactly
# where the water is thinnest.
#
# Variants, cheapest and least invasive first:
#   cfl     CFLMax 0.7 -> 0.5      purely numerical, no physics touched
#   dtmax   dtMax 30 -> 10 s       purely numerical
#   trtmnh  TrtMnH = 0.3 m         stops Baptist below 30 cm of water; a small
#                                  physics change, and arguably toward realism,
#                                  since a canopy formulation has little meaning
#                                  in water shallower than the plants
#   meadow  no sediment under the canopy
#
# The first three all failed identically, 16 timestep breaks each, which is what
# sent the diagnosis to the .dia. There it was: 73 "Bed change exceeds 5.0 % of
# waterdepth" warnings against zero in the old-.arl control. The limiter is
# morphological, not Courant, which is exactly why no numerical knob moved it.
# Lagoon bed shear at the same instant went from 0.75 to 1.76 N/m2 mean and 14.4
# to 33.8 max, because FM's taus carries the trachytope drag into the transport
# formula. The meadow variant removes the cause rather than the symptom: the
# sediment field is rebuilt with thickness scaled by the bare fraction, so the
# canopy no longer erodes a bed it does not have.
#
# Six simulated hours, the same window the control used, roughly two wall
# minutes each.
#
#   bash test_vr_dens_stability_variants.sh [variant ...]     default: all three
set -e

BASE=~/StagnoneDT/model
SRC=$BASE/dflowfm_v04AE_vr_dens
ARL=~/StagnoneDT/data/processed/planet2023_rf_v3/stagnone_trachytopes_v3.arl
SEDTHICK_MEADOW=~/StagnoneDT/data/processed/sedthick_meadow.xyz
LOGDIR=~/arlfix_logs
STOP=20250701060000

VARIANTS=${*:-"cfl dtmax trtmnh"}
mkdir -p "$LOGDIR"

for v in $VARIANTS; do
    dst=$BASE/_trt_test_stab_$v
    rm -rf "$dst"; mkdir -p "$dst"
    # Excludes as in setup_arlfix_reruns.sh: partition patterns anchored with a
    # leading '/' so they cannot eat wave/TMP_ESMF_..._0001.nc, and hot_*.nc
    # dropped because a stale one segfaults when sim time hits its filename.
    rsync -a --exclude='DFM_OUTPUT_*' --exclude='/*_0[0-9][0-9][0-9].*' \
        --exclude='/*_0[0-9][0-9][0-9]_*' --exclude='hot_*.nc' \
        --exclude='*.bak*' --exclude='*.dia' --exclude='swn-diag.*' \
        --exclude='diag/' "$SRC/" "$dst/"
    cp "$ARL" "$dst/stagnone_trachytopes_v3.arl"

    M=$dst/Stagnone_dxy01_15m.mdu
    sed -i "s|^\(stopDateTime *= *\)[0-9]*|\1$STOP|I" "$M"
    sed -i 's|^\(wrimap_numLimdt *= *\)[0-9]*|\11|I' "$M"
    case $v in
        cfl)    sed -i 's|^\(CFLMax *= *\)[0-9.]*|\10.5|I' "$M" ;;
        dtmax)  sed -i 's|^\(dtMax *= *\)[0-9.]*|\110.0|I' "$M" ;;
        trtmnh) sed -i '/^trtMxR/a trtMnH = 0.3   # minimum water depth for trachytopes' "$M" ;;
        meadow) cp "$SEDTHICK_MEADOW" "$dst/sedthick_lagoon.xyz"
                # The .sed already points IniSedThick at this filename for both
                # fractions, so replacing the file is the whole change.
                z=$(awk '$3==0' "$dst/sedthick_lagoon.xyz" | wc -l)
                echo "  meadow: sedthick nodes at zero = $z of $(wc -l < "$dst/sedthick_lagoon.xyz")" ;;

        # Diagnostics rather than candidate fixes. meadow cut the bed-change
        # warnings from 73 to 42 and still broke, and every variant so far
        # breaks between 35 and 52 simulated minutes regardless of the setting.
        # A failure time that stubborn points at a switch, not at an accumulation.
        nosed)  sed -i 's|^\(Sedimentmodelnr *= *\)[0-9]*|\10|I' "$M"
                echo "  nosed: $(grep -i '^Sedimentmodelnr' "$M" | tr -s ' ')" ;;
        nobedupd) sed -i 's|^\( *BedUpd *= *\).*|\1false|' "$dst/morphology.mor"
                # transport still computed, bed frozen: separates "updating the
                # bed breaks it" from "computing the transport breaks it"
                echo "  nobedupd: $(grep -i 'BedUpd' "$dst/morphology.mor" | tr -s ' ')" ;;
        morstt) sed -i 's|^\( *MorStt *= *\).*|\1100000.0|' "$dst/morphology.mor"
                # MorStt is minutes by the Delft3D convention, so 1440 should be
                # 24 h and morphology should be dormant at the failure. If it is
                # read as seconds it is 24 min, which lands just before every
                # abort. Pushing it far out settles which.
                echo "  morstt: $(grep -i 'MorStt' "$dst/morphology.mor" | tr -s ' ')" ;;

        # --- candidate calibrations, from the literature rather than tuned ---
        #
        # vanrijn  TraFrm -2 -> -1. -2 is Engelund-Hansen, a river total-load
        #          formula with no threshold of motion and transport going as
        #          tau^2.5, so doubling the stress multiplies transport by 5.7.
        #          Van Rijn carries a mobility threshold and derives its own
        #          grain-related stress from d50, so it does not inherit the
        #          canopy roughness the way Engelund-Hansen does. Zhu et al.
        #          (2021, JGR Oceans), the closest published analogue -- Delft3D
        #          with SWAN, Baptist canopy, 1 m mean depth -- use van Rijn for
        #          sand and Partheniades-Krone for mud.
        #
        #          The number is verified from the .dia, not assumed: FM echoes
        #          "Formula name", and the negative TraFrm codes are easy to
        #          misremember.
        #
        # bsskin   FM computes the erosion stress for mud from the total bed
        #          shear stress, which with trachytopes active carries the
        #          canopy form drag. BsSkin switches it to Soulsby (2004) skin
        #          friction from a ripple roughness height. The capability is in
        #          this binary: compbsskin.f90, m_fm_erosed_mp_bsskin_, and the
        #          string "Skin friction Soulsby 2004". RksR = 0.01 m is a
        #          conventional ripple height for fine sand.
        #
        # vrbs     both together, which is the configuration the literature
        #          actually supports.
        #
        # TcrEro and TcrSed are deliberately NOT tested yet. A threshold only
        # means something relative to the stress that drives it, so changing it
        # before the stress basis is right would be tuning blind.
        vanrijn) sed -i 's|^\( *TraFrm *= *\).*|\1-1|' "$dst/sediment.sed"
                echo "  vanrijn: $(grep -i 'TraFrm' "$dst/sediment.sed" | tr -s ' ')" ;;
        # WRONG PLACEMENT, kept as the record of a silent failure. BsSkin in the
        # .mor is not read: FM's morphological echo never mentions it and the
        # run is numerically identical to one without it. strings on the binary
        # puts BsSkin next to KsSand, KsSilt, PmCrit and SC_mudfactor, which is
        # the sand-mud interaction group in the .sed, not the .mor. See bsskin2.
        bsskin) sed -i '/^\[Morphology\]/a\    BsSkin               = true\n    RksR                 = 1.0000000e-002' "$dst/morphology.mor"
                echo "  bsskin: $(grep -iE 'BsSkin|RksR' "$dst/morphology.mor" | tr -s ' ' | paste -sd'; ')" ;;

        # bsskin2  The same intent in the right file. [SedimentOverall] in the
        #          .sed, with Nikuradse roughness heights for the skin friction
        #          rather than a ripple height. KsSand 5e-5 m is roughly 2.5
        #          grain diameters for our 150 um sand.
        #
        #          Verify from the .dia. The .mor attempt failed silently and
        #          only the identical numbers gave it away.
        bsskin2) sed -i '/^\[SedimentOverall\]/a\    BsSkin           = true\n    KsSand           = 5.0000000e-005\n    KsSilt           = 1.0000000e-005' "$dst/sediment.sed"
                echo "  bsskin2: $(grep -iE 'BsSkin|KsSand|KsSilt' "$dst/sediment.sed" | tr -s ' ' | paste -sd'; ')" ;;
        # iopkcw  The .dia settles what -2 actually is, and it is not what I
        #         assumed: "Formula name : Van Rijn (2007): TRANSPOR2004,
        #         Transport formula used : -2". -1 is Van Rijn (1993). Both
        #         echo "Standard option: Rc from Flow" (IopKCW = 1), meaning the
        #         current-related roughness the transport formula uses is taken
        #         from the flow module, which with trachytopes active is the
        #         canopy roughness.
        #
        #         IopKCW = 0 substitutes the given RDC and RDW instead, which
        #         decouples the transport roughness from the flow roughness.
        #         That is the Zhu et al. principle through the standard Delft3D
        #         knob, and it would keep the newer formula rather than falling
        #         back to the 1993 one. RDC 0.01 m and RDW 0.02 m are the values
        #         FM already echoes as defaults for Van Rijn (1993).
        #
        #         Verify from the .dia that IopKCW came through as 0: unknown
        #         keys in the .sed are a silent-failure risk.
        iopkcw) sed -i '/SedTyp *= *sand/a\    IopKCW           = 0\n    RDC              = 1.0000000e-002\n    RDW              = 2.0000000e-002' "$dst/sediment.sed"
                echo "  iopkcw: $(grep -iE 'IopKCW|RDC|RDW' "$dst/sediment.sed" | tr -s ' ' | paste -sd'; ')" ;;
        # trt154  The separation is in the trachytope formula, not the sediment
        #         module. From trtrou.f90:
        #
        #           153  ch = 1/sqrt( 1/cbed^2 + drag*densit*vheigh/(2g) )
        #                lumps bed friction and canopy drag into ONE Chezy, and
        #                taus follows from that, so the canopy drag reaches the
        #                transport formula.
        #
        #           154  ch = cbed + sqrt(g)/kappa*log(hk)*sqrt(1+...)
        #                rttfu(nm,1) += fraccu*drag*densit/hk*(cbed/ch)^2
        #                keeps the bed Chezy as the bed Chezy and carries the
        #                canopy as a separate momentum sink, lambda.
        #
        #         155 and 156 follow 154's pattern, so the RQ9 move to Jarvela
        #         would inherit this for free.
        #
        #         Same four parameters in both, so only the formula number
        #         changes. This also alters the hydrodynamics, since 154 is
        #         Baptist's full log-layer form rather than the quadrature one:
        #         that is the point, not a side effect, but it means the
        #         roughness field is not the same field.
        trt154) sed -i 's|^\( *[23] *\)153|\1154|' "$dst/trachytopes.ttd"
                echo "  trt154: $(grep -E '^ +[0-9]+ +15[0-9]' "$dst/trachytopes.ttd" | tr -s ' ' | paste -sd'; ')" ;;
        vrbs)   sed -i 's|^\( *TraFrm *= *\).*|\1-1|' "$dst/sediment.sed"
                sed -i '/^\[Morphology\]/a\    BsSkin               = true\n    RksR                 = 1.0000000e-002' "$dst/morphology.mor"
                echo "  vrbs: $(grep -i 'TraFrm' "$dst/sediment.sed" | tr -s ' ') + $(grep -iE 'BsSkin|RksR' "$dst/morphology.mor" | tr -s ' ' | paste -sd'; ')" ;;
    esac
    case $v in
        cfl|dtmax|trtmnh)
            echo "  $v: $(grep -iE '^(CFLMax|dtMax|trtMnH)' "$M" | tr -s ' ' | paste -sd'; ')" ;;
    esac
done

echo
for v in $VARIANTS; do
    dst=$BASE/_trt_test_stab_$v
    cd "$dst"
    # ~/.bashrc sources oneAPI only for interactive shells.
    bash -c "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1;
             export DELFT3D_HOME=$HOME/Scaricati/delft3dfm/lnx64;
             export PATH=\$DELFT3D_HOME/bin:\$PATH;
             export LD_LIBRARY_PATH=\$DELFT3D_HOME/lib:\$LD_LIBRARY_PATH;
             bash run_model.sh" > "$LOGDIR/stab_$v.log" 2>&1 || true
    d=$dst/DFM_OUTPUT_Stagnone_dxy01_15m
    fin=$(grep -l 'Computation finished' "$d"/*.dia 2>/dev/null | wc -l || true)
    brk=$(grep -c 'below threshold' "$LOGDIR/stab_$v.log" 2>/dev/null || true)
    dt=$(grep -oE '[0-9.]+$' "$d"/*_0000.dia 2>/dev/null | tail -1)
    # Every count needs "|| true": grep exits 1 on no match, and under set -e a
    # command substitution that fails kills the script. A clean run has zero
    # bed-change warnings, so this killed the driver on the first variant that
    # actually worked -- the success case was the one that crashed the harness.
    bc=$(cat "$d"/*.dia 2>/dev/null | grep -c 'Bed change exceeds' || true)
    # Which transport formula did FM actually select? The negative TraFrm codes
    # are easy to get wrong and a wrong one would fail silently as a plausible
    # result, so read it back rather than trust the edit.
    frm=$(cat "$d"/*_0000.dia 2>/dev/null | grep -ioE '(Engelund-Hansen|Van Rijn|Meyer-Peter|Bijker|Ackers|Soulsby)[^,]{0,14}' | head -1 || true)
    printf '%-8s partitions_finished=%s  timestep_breaks=%s  bed_change=%s  mean_dt=%s  formula=%s\n' \
        "$v" "$fin" "$brk" "$bc" "${dt:-n/a}" "${frm:-not echoed}"
done
