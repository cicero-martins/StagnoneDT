#!/usr/bin/env bash
#
# Chain operational: simula fluxo digital twin diário.
# Loop começando em START_DAY, terminando em END_DAY (inclusive). A cada iter:
#   1. Espera o iter anterior terminar (Computation finished marker no log)
#   2. Verifica clean (no FATAL/SIGSEGV)
#   3. Roda chain_next_n2.sh <publish_day> que:
#       - usa rst @ (publish-2) do output do iter anterior
#       - cria runs/forecast/d<publish>_n2 e lança nohup
#   4. PID + log do novo iter capturados
#   5. próximo dia
#
# Pré-req:
#   - O primeiro iter da chain (publish=START_DAY) precisa de prev_dir existente
#     em runs/forecast/d<START_DAY - 1 day>_n2 (e ele tem que ter terminado clean).
#   - Forcings em d10d12 cobrem [START_DAY-2, END_DAY] (ver extend_d10d12_forcings_to_jul22.py)
#
# Uso (foreground): bash chain_operational.sh 2025-07-13 2025-07-20
# Uso (nohup):      nohup bash chain_operational.sh 2025-07-13 2025-07-20 > _ops.log 2>&1 &
#                   disown
#
# Wall estimado: ~16 min/iter × N dias

set -uo pipefail

START_DAY="${1:?Usage: $0 <start_publish YYYY-MM-DD> <end_publish YYYY-MM-DD> [poll_sec]}"
END_DAY="${2:?Usage: $0 <start_publish YYYY-MM-DD> <end_publish YYYY-MM-DD> [poll_sec]}"
POLL_SEC="${3:-60}"  # check log every 60s

ROOT="${ROOT:-$HOME/StagnoneDT}"
RUNS="$ROOT/runs/forecast"
MASTER_LOG="$RUNS/_chain_operational_$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$RUNS"

log() {
    local ts=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    echo "[$ts] $*" | tee -a "$MASTER_LOG"
}

log "=========================================================="
log " CHAIN OPERATIONAL"
log " Window: $START_DAY -> $END_DAY (publish days, N-2 continuation each)"
log " Poll interval: ${POLL_SEC}s"
log " Master log: $MASTER_LOG"
log "=========================================================="

PUBLISH="$START_DAY"
ITER=0

while [[ "$PUBLISH" < "$(date -u -d "$END_DAY + 1 day" +%Y-%m-%d)" ]]; do
    ITER=$((ITER+1))
    PREV_PUBLISH=$(date -u -d "$PUBLISH - 1 day" +%Y-%m-%d)
    PREV_DIR="$RUNS/d${PREV_PUBLISH}_n2"
    log ""
    log "===== ITER $ITER: publish=$PUBLISH (prev=$PREV_PUBLISH) ====="

    # 1. Esperar prev iter terminar
    PREV_LOG=$(ls -t "$PREV_DIR/diag/run_d${PREV_PUBLISH}_"*.log 2>/dev/null | head -1)
    if [[ -z "$PREV_LOG" ]]; then
        log "  ERROR: prev iter log NÃO ENCONTRADO em $PREV_DIR/diag/"
        log "         (precisa do iter d${PREV_PUBLISH}_n2 existindo + ter sido lançado antes)"
        exit 11
    fi
    log "  watching: $PREV_LOG"

    WAITED=0
    MAX_WAIT=$((60 * 60))  # 60 min cap por iter
    while ! grep -q "Computation finished" "$PREV_LOG" 2>/dev/null; do
        # Aborto: se algum FATAL/SIGSEGV no log, parar
        if grep -qE 'FATAL|Segmentation fault|SIGSEGV|SIGKILL|Abort\(' "$PREV_LOG" 2>/dev/null; then
            log "  FATAL detected in $PREV_LOG; stopping chain:"
            grep -E 'FATAL|Segmentation|SIGSEGV|SIGKILL|Abort\(' "$PREV_LOG" | head -3 | sed 's/^/    /' | tee -a "$MASTER_LOG"
            exit 12
        fi
        if (( WAITED >= MAX_WAIT )); then
            log "  TIMEOUT: prev iter rodando há $WAITED s sem terminar. Abort."
            exit 13
        fi
        sleep "$POLL_SEC"
        WAITED=$((WAITED + POLL_SEC))
        if (( WAITED % 300 == 0 )); then  # log a cada 5 min
            # tenta extrair sim time atual do .dia
            local_dia=$(ls "$PREV_DIR/DFM_OUTPUT_Stagnone_dxy01_15m/Stagnone_dxy01_15m_0000.dia" 2>/dev/null)
            simh="?"
            if [[ -n "$local_dia" ]]; then
                simh=$(grep -E 'simulation period\s*\(h\)' "$local_dia" 2>/dev/null | tail -1 | awk '{print $(NF)}')
            fi
            log "  ...still running ($WAITED s waited, sim_h_acc=${simh:-?})"
        fi
    done
    log "  prev iter Computation finished (after ${WAITED}s)."

    # 2. Verificar clean
    if grep -qE 'FATAL|Segmentation|SIGSEGV|SIGKILL|Abort\(' "$PREV_LOG"; then
        log "  prev iter FAILED (FATAL/SIGSEGV detected, NOT chaining further):"
        grep -E 'FATAL|Segmentation|SIGSEGV|SIGKILL|Abort\(' "$PREV_LOG" | head -3 | sed 's/^/    /' | tee -a "$MASTER_LOG"
        exit 14
    fi
    log "  prev iter clean. Lançando próximo (publish=$PUBLISH)..."

    # 3. Lançar próximo via chain_next_n2.sh
    NEXT_OUT=$(bash "$ROOT/scripts/chain_next_n2.sh" "$PUBLISH" 2>&1)
    echo "$NEXT_OUT" >> "$MASTER_LOG"
    if ! echo "$NEXT_OUT" | grep -q "=== Launching dimr ==="; then
        log "  ERROR: chain_next_n2.sh para $PUBLISH não chegou ao launch. Output:"
        echo "$NEXT_OUT" | tail -20 | sed 's/^/    /' | tee -a "$MASTER_LOG"
        exit 15
    fi
    NEW_PID=$(echo "$NEXT_OUT" | grep -oP 'PID: \K[0-9]+' | head -1)
    NEW_LOG=$(echo "$NEXT_OUT" | grep -oP 'log: \K\S+' | head -1)
    log "  launched: PID=$NEW_PID, log=$NEW_LOG"

    # 4. Advance
    PUBLISH=$(date -u -d "$PUBLISH + 1 day" +%Y-%m-%d)
done

# Último iter: esperar ele terminar também
log ""
log "===== Waiting for LAST iter to finish ====="
LAST_PUBLISH=$(date -u -d "$PUBLISH - 1 day" +%Y-%m-%d)
LAST_DIR="$RUNS/d${LAST_PUBLISH}_n2"
LAST_LOG=$(ls -t "$LAST_DIR/diag/run_d${LAST_PUBLISH}_"*.log 2>/dev/null | head -1)
if [[ -n "$LAST_LOG" ]]; then
    WAITED=0
    while ! grep -q "Computation finished" "$LAST_LOG" 2>/dev/null; do
        if grep -qE 'FATAL|Segmentation|SIGSEGV|SIGKILL|Abort\(' "$LAST_LOG" 2>/dev/null; then
            log "  FATAL no LAST iter:"
            grep -E 'FATAL|Segmentation|SIGSEGV|SIGKILL|Abort\(' "$LAST_LOG" | head -3 | sed 's/^/    /' | tee -a "$MASTER_LOG"
            exit 16
        fi
        sleep "$POLL_SEC"
        WAITED=$((WAITED + POLL_SEC))
    done
    log "  LAST iter Computation finished after ${WAITED}s"
fi

log ""
log "=========================================================="
log " CHAIN OPERATIONAL COMPLETO"
log " Iters realizados: $ITER"
log " Last publish: $LAST_PUBLISH"
log "=========================================================="
