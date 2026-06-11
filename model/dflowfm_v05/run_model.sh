#!/bin/bash
# Run v05 FM-only stability test on simit server (8 MPI).
# Usage: bash run_model.sh
set -e

nPart=8
dimrFile=dimr_config.xml
mduFile=Stagnone_v05.mdu

# Patch process list in dimr_config.xml (sed updates <process> tag in-place)
PROCESSSTR="$(seq -s " " 0 $((nPart-1)))"
sed -i "s|\(<process>\)[^<]*\(</process>\)|\1$PROCESSSTR\2|" $dimrFile

# Step 1: partition
run_dflowfm.sh --partition:ndomains=${nPart}:icgsolver=6 $mduFile

# Step 2: run dimr (FM-only, 8 MPI)
run_dimr.sh -c $nPart -m $dimrFile
