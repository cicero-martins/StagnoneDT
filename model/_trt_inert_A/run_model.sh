#!/bin/bash
# v04AE_nowaves: FM-only Linux variant. nPart=8 (matches coupled v04AE).
# Lowered from 16 on 2026-05-12 after crash via maxVelocity trigger; nPart=8
# also keeps cells/partition above WP284 sweet spot (~3150 > 3000).
# Auto-rewrites <process> in dimr_config.xml to match nPart.
set -e
nPart=8
dimrFile=dimr_config.xml
mduFolder=.
PROCESSSTR="$(seq -s " " 0 $((nPart-1)))"
sed -i "s/\(<process.*>\)[^<>]*\(<\/process.*\)/\1$PROCESSSTR\2/" $dimrFile
mduFile=Stagnone_dxy01_15m.mdu

if [ "$nPart" == "1" ]; then
    run_dimr.sh -m $dimrFile
else
    pushd $mduFolder
        run_dflowfm.sh --partition:ndomains=$nPart:icgsolver=6 $mduFile
    popd
    run_dimr.sh -c $nPart -m $dimrFile
fi
