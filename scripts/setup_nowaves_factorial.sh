#!/bin/bash
# Complete the 2x2x2 factorial by adding the three missing no-wave members.
#
# Base is dflowfm_v04AE_nowaves, which already has Wavemodelnr=0,
# flowWithoutWaves=1 and the maxVelocity 25 fix. Clone it three times and turn
# on the treatments, so the only difference from the existing no-wave member is
# the treatment itself.
#
# DtTrt is set to 300 s in the roughness members to match v04AE_vr, not the 60 s
# the base carries, because in the base TrtRou=N makes it inert.
set -e
cd "$HOME/StagnoneDT/model"
SRC=dflowfm_v04AE_nowaves
ARL=dflowfm_v04AE_vr/stagnone_trachytopes_v3.arl

clone () {
  local dst=$1
  rm -rf "$dst"
  mkdir -p "$dst"
  # Exclude outputs, partition artefacts, backups and runtime logs, per the
  # project cloning convention. Partitions are machine-bound and must be
  # regenerated anyway.
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
}

set_key () {   # set_key <file> <key> <value>
  local f=$1 k=$2 v=$3
  if grep -qiE "^[[:space:]]*$k[[:space:]]*=" "$f"; then
    sed -i -E "s|^([[:space:]]*$k[[:space:]]*=)[^#]*|\1 $v                    |I" "$f"
  else
    echo "  WARNING: key $k not found in $f" >&2
  fi
}

for name in nowaves_vr nowaves_dm nowaves_vrdm; do
  dst="dflowfm_v04AE_$name"
  echo "=== $dst ==="
  clone "$dst"
  MDU="$dst/Stagnone_dxy01_15m.mdu"

  case $name in
    nowaves_vr|nowaves_vrdm)
      cp "$ARL" "$dst/"
      set_key "$MDU" TrtRou Y
      set_key "$MDU" TrtDef trachytopes.ttd
      set_key "$MDU" TrtL   stagnone_trachytopes_v3.arl
      set_key "$MDU" DtTrt  300.0
      ;;
  esac
  case $name in
    nowaves_dm|nowaves_vrdm)
      set_key "$MDU" Sedimentmodelnr 4
      ;;
  esac

  printf '  %-18s %s\n' Wavemodelnr     "$(grep -im1 '^[[:space:]]*Wavemodelnr[[:space:]]*=' "$MDU" | sed 's/#.*//' | cut -d= -f2 | tr -d ' ')"
  printf '  %-18s %s\n' Sedimentmodelnr "$(grep -im1 '^[[:space:]]*Sedimentmodelnr[[:space:]]*=' "$MDU" | sed 's/#.*//' | cut -d= -f2 | tr -d ' ')"
  printf '  %-18s %s\n' TrtRou          "$(grep -im1 '^[[:space:]]*TrtRou[[:space:]]*=' "$MDU" | sed 's/#.*//' | cut -d= -f2 | tr -d ' ')"
  printf '  %-18s %s\n' TrtL            "$(grep -im1 '^[[:space:]]*TrtL[[:space:]]*=' "$MDU" | sed 's/#.*//' | cut -d= -f2 | tr -d ' ')"
  printf '  %-18s %s\n' stopDateTime    "$(grep -im1 '^[[:space:]]*stopDateTime[[:space:]]*=' "$MDU" | sed 's/#.*//' | cut -d= -f2 | tr -d ' ')"
  echo
done
echo "clones prontos"
