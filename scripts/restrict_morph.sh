#!/bin/bash
# Confine morphodynamics to depths where waves can move the modelled sediment.
#
# IniSedThick becomes a sample file instead of the 0.5 m scalar: full thickness
# above 15 m depth, tapering to zero at 20 m. The threshold comes from the
# model's own orbital velocity, which falls from 0.185 m/s at 2-5 m to 0.030 at
# 15-20 m and 0.016 at 20-30 m.
#
# Old outputs are renamed rather than deleted, so the unrestricted results stay
# recoverable while the new ones are validated.
set -e
cd "$HOME/StagnoneDT/model"
STAMP=bak_unrestricted_morph

for d in dflowfm_v04AE dflowfm_v04AE_vr dflowfm_v04AE_nowaves_vrdm; do
  echo "=== $d ==="
  cd "$HOME/StagnoneDT/model/$d"

  # sediment field, built on this member's own mesh
  python "$HOME/StagnoneDT/scripts/build_sedthick_field.py" \
      Stagnone_dxy01_15m_net.nc sedthick_lagoon.xyz 2>&1 | sed 's/^/  /'

  # patch the .sed, keeping the original
  [ -f sediment.sed.orig ] || cp sediment.sed sediment.sed.orig
  sed -i 's|IniSedThick      = 5.0000000e-001|IniSedThick      = sedthick_lagoon.xyz|' sediment.sed
  echo "  IniSedThick now: $(grep -m1 IniSedThick sediment.sed | cut -d= -f2 | tr -d ' ')"

  # archive any previous output so the new run writes clean
  for o in DFM_OUTPUT_Stagnone_dxy01_15m; do
    if [ -d "$o" ] && [ ! -d "$o.$STAMP" ]; then
      mv "$o" "$o.$STAMP"
      echo "  archived $o -> $o.$STAMP"
    fi
  done
  rm -rf diag && mkdir -p diag

  # partitions must be regenerated after any input change
  rm -f Stagnone_dxy01_15m_000?_net.nc Stagnone_dxy01_15m_000?.mdu
  sed -i 's|\(<process.*>\)[^<>]*\(</process.*\)|\10 1 2 3 4 5 6 7\2|' dimr_config.xml
  run_dflowfm.sh --partition:ndomains=8:icgsolver=6 Stagnone_dxy01_15m.mdu > /tmp/part_$d.log 2>&1
  echo "  partitions: $(ls Stagnone_dxy01_15m_000?_net.nc 2>/dev/null | wc -l)"
  echo
done
echo "prontos para lancar"
