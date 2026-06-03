#!/usr/bin/env bash
#
# Re-enable D-Morph in v04AE_jul13jul20 with physically realistic config.
#
# Hypothesis: maybe the velocity blowup at cell 38616 (Jul 14 04:00, ucmag=15
# m/s with maxVelocity=15 trip + SIGSEGV) can be damped by re-enabling D-Morph
# with sediment transport coupling. Mechanism: suspended/bed-load momentum
# adds inertia, van Rijn roughness adapts to flow regime, slight bathy
# adjustment damps offshore gradients.
#
# Patches vs v04AE master:
#   sediment.sed silt_fine:
#     TcrEro      0.1 -> 0.3 Pa     (realistic cohesive mud consolidated)
#     TcrSed      0.1 -> 0.2 Pa     (hysteresis: deposition threshold < erosion)
#     EroPar      1e-4 -> 5e-5 kg/m^2/s  (less aggressive erosion)
#     IniSedThick 0.5 -> 0.2 m       (smaller mobile mud reservoir)
#   sediment.sed sand_fine: unchanged (van Rijn 2007 handles sand internally)
#   morphology.mor:
#     MorStt 1440 -> 2880 min (48h spin-up before bed updates activate)
#   MDU:
#     Sedimentmodelnr 0 -> 4 (re-enable Morphology module)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="$ROOT/model/dflowfm_v04AE_jul13jul20"
MDU="$DST/Stagnone_dxy01_15m.mdu"
SED="$DST/sediment.sed"
MOR="$DST/morphology.mor"

to_win() { python3 -c "import sys, os; print(os.path.abspath(sys.argv[1]).replace(chr(92),'/'))" "$1" 2>/dev/null || cygpath -w "$1" 2>/dev/null || echo "$1"; }
SED_WIN="$(to_win "$SED")"

# Backup originals
for f in "$MDU" "$SED" "$MOR"; do
    if [[ ! -f "$f.bak_pre_dmorph_phys" ]]; then
        cp "$f" "$f.bak_pre_dmorph_phys"
        echo "  backup: $(basename "$f").bak_pre_dmorph_phys"
    fi
done

echo ""
echo "=== Patch sediment.sed (silt_fine fraction) ==="
sed -i 's/^\(\s*TcrSed\s*=\s*\)1\.0000000e-001/\11.5000000e-001/' "$SED"  # placeholder; will set below
# Apply specific values via python (sed is brittle for floats)
"C:/Users/Unipa/.conda/envs/dfm_tools_env/python.exe" - <<EOF
from pathlib import Path
p = Path(r"$SED_WIN")
text = p.read_text()
# Only target the silt_fine block (after Name=#silt_fine#)
lines = text.splitlines()
out = []
in_silt = False
for line in lines:
    s = line.strip()
    if s.startswith('Name') and 'silt_fine' in s:
        in_silt = True
    elif s.startswith('Name') and 'silt_fine' not in s:
        in_silt = False
    elif s.startswith('[Sediment'):
        in_silt = False
    if in_silt:
        if 'TcrSed' in line:
            out.append('    TcrSed           = 2.0000000e-001  # physical: depo threshold (0.2 Pa)')
            continue
        if 'TcrEro' in line:
            out.append('    TcrEro           = 3.0000000e-001  # physical: erosion threshold (0.3 Pa, consolidated mud)')
            continue
        if 'EroPar' in line:
            out.append('    EroPar           = 5.0000000e-005  # less aggressive erosion rate')
            continue
        if 'IniSedThick' in line:
            out.append('    IniSedThick      = 2.0000000e-001  # smaller mobile mud reservoir')
            continue
    out.append(line)
p.write_text('\n'.join(out))
print('  Patched silt_fine: TcrSed=0.2, TcrEro=0.3, EroPar=5e-5, IniSedThick=0.2 m')
EOF
echo "  silt_fine block after patch:"
awk '/silt_fine/,/^$/' "$SED" | sed 's/^/    /'

echo ""
echo "=== Patch morphology.mor ==="
sed -i 's/^\(\s*MorStt\s*=\s*\)1440.0/\12880.0/' "$MOR"
echo "  MorStt:"
grep -E "^\s*MorStt" "$MOR" | sed 's/^/    /'

echo ""
echo "=== Patch MDU (Sedimentmodelnr 0 -> 4) ==="
sed -i 's/^Sedimentmodelnr\s*=\s*0/Sedimentmodelnr = 4               # D-Morph ON: physical config (TcrEro=0.3 Pa, 48h spin-up)/' "$MDU"
grep -E "^Sedimentmodelnr" "$MDU" | sed 's/^/    /'

echo ""
echo "=== Done. To launch ==="
echo "  cd $DST"
echo "  bash run_model.sh    # on simit"
echo "  run_model.bat 8       # on Workstation"
