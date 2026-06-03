#!/usr/bin/env bash
#
# Encadear próxima iteração N-2 a partir do rst da iteração anterior.
#
# Modelo operacional (per [[restart_chain_n_minus_2_workflow]]):
#   Cada publish day requer 48h sim (rst @ N-2 → run até N).
#   O rst @ N-2 do publish day seguinte = rst @ (N-1) do publish day atual,
#   que foi escrito 24h dentro do run atual.
#
# Uso: bash chain_next_n2.sh <publish_day>
# Ex.: bash chain_next_n2.sh 2025-07-11
#   → Verifica que o run d2025-07-10_n2 completou clean
#   → Usa rst @ 2025-07-09 desse output como input
#   → Cria runs/forecast/d2025-07-11_n2 e lança
#
# Pré-req: setup_continuation_simple.sh aceita RST_SRC env override.

set -euo pipefail

PUBLISH_DAY="${1:?Usage: $0 <publish_day YYYY-MM-DD>}"
ROOT="${ROOT:-$HOME/StagnoneDT}"

# Dia anterior (publish - 1)
PREV_PUBLISH=$(date -u -d "$PUBLISH_DAY - 1 day" +%Y-%m-%d)
# rst date = publish - 2 (N-2)
RST_DATE=$(date -u -d "$PUBLISH_DAY - 2 days" +%Y-%m-%d)
RST_NOSEP=$(date -u -d "$RST_DATE" +%Y%m%d)

PREV_DIR="$ROOT/runs/forecast/d${PREV_PUBLISH}_n2"
PREV_OUT="$PREV_DIR/DFM_OUTPUT_Stagnone_dxy01_15m"
PREV_LOG_DIR="$PREV_DIR/diag"

echo "=== chain_next_n2 ==="
echo "  publish target : $PUBLISH_DAY"
echo "  rst date       : $RST_DATE (= N-2)"
echo "  prev iter dir  : $PREV_DIR"
echo ""

# 1. Verifica que o prev iter existe
if [[ ! -d "$PREV_DIR" ]]; then
    echo "ERROR: prev iter dir não existe: $PREV_DIR"
    echo "Lance primeiro: bash setup_continuation_simple.sh $PREV_PUBLISH 2"
    exit 1
fi

# 2. Verifica que o prev iter completou clean
PREV_LOG=$(ls -t "$PREV_LOG_DIR"/run_d${PREV_PUBLISH}_*.log 2>/dev/null | head -1)
if [[ -z "$PREV_LOG" ]]; then
    echo "ERROR: nenhum run_log em $PREV_LOG_DIR"
    exit 2
fi
echo "  prev log       : $PREV_LOG"

if ! grep -q "Computation finished" "$PREV_LOG"; then
    echo "ERROR: prev iter NÃO completou (sem 'Computation finished' no log):"
    tail -5 "$PREV_LOG" | sed 's/^/    /'
    exit 3
fi

if grep -qE 'FATAL|Segmentation fault|SIGSEGV|SIGKILL' "$PREV_LOG"; then
    echo "ERROR: prev iter tem FATAL/SIGSEGV no log:"
    grep -E 'FATAL|Segmentation|SIGSEGV|SIGKILL' "$PREV_LOG" | head -3 | sed 's/^/    /'
    exit 4
fi
echo "  prev iter status: PASS (Computation finished, no FATAL)"

# 3. Verifica rst @ RST_DATE existe no prev output
RST_COUNT=$(ls "$PREV_OUT"/Stagnone_dxy01_15m_*_${RST_NOSEP}_000000_rst.nc 2>/dev/null | wc -l)
if [[ "$RST_COUNT" -ne 8 ]]; then
    echo "ERROR: expected 8 rst @ ${RST_DATE} em $PREV_OUT, found $RST_COUNT"
    echo "Available rst files:"
    ls "$PREV_OUT"/Stagnone_dxy01_15m_*_rst.nc 2>/dev/null | sed 's/^/  /'
    exit 5
fi
echo "  8 rst @ $RST_DATE confirmados em $PREV_OUT"
echo ""

# 4. Lança próxima iteração com RST_SRC apontando para prev output
echo "=== Lançando próxima iter via setup_continuation_simple.sh ==="
RST_SRC="$PREV_OUT" bash "$ROOT/scripts/setup_continuation_simple.sh" "$PUBLISH_DAY" 2
