#!/bin/bash
set -e
nPart=4
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
