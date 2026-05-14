#!/bin/bash
# Pipeline diario de clasificación VIP — Comunidad Iván Caicedo
# Corre: refrescar contactos GHL → consolidar Excels → reclasificar → escribir a GHL
# Notificación nativa de macOS + log en logs/<fecha>.log

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Lock anti-solapamiento (portable macOS/Linux usando PID en archivo).
mkdir -p logs
LOCKFILE="$HERE/.pipeline.lock"
if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Otra corrida activa (PID $OLD_PID) — esta se omite." >> "$HERE/logs/skipped.log"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

mkdir -p logs
LOG="logs/$(date +%Y-%m-%d_%H%M).log"
echo "=================================================="  | tee -a "$LOG"
echo "  Pipeline diario · $(date)"                          | tee -a "$LOG"
echo "==================================================" | tee -a "$LOG"

notify() {
  local title="$1"; local msg="$2"
  osascript -e "display notification \"$msg\" with title \"$title\"" 2>/dev/null || true
}

# Cargar credenciales
if [ ! -f .env ]; then
  echo "ERROR: falta $HERE/.env"                            | tee -a "$LOG"
  notify "Comunidad VIP" "❌ Pipeline falló: falta .env"
  exit 1
fi
set -a; source .env; set +a

run_step() {
  local name="$1"; shift
  echo ""                                                   | tee -a "$LOG"
  echo "▶ $name · $(date +%H:%M:%S)"                        | tee -a "$LOG"
  echo "──────────────────────────────────────────────────" | tee -a "$LOG"
  if "$@" >> "$LOG" 2>&1; then
    echo "✓ $name OK"                                       | tee -a "$LOG"
    return 0
  else
    echo "✗ $name FALLÓ (código $?)"                        | tee -a "$LOG"
    notify "Comunidad VIP" "❌ Falló: $name. Ver $LOG"
    return 1
  fi
}

run_step "Refrescar contactos GHL" /usr/bin/python3 refrescar_contactos_ghl.py || exit 1
run_step "Consolidar Excels"       /usr/bin/python3 consolidar_excel.py        || exit 1
run_step "Reclasificar (reporte)"  /usr/bin/python3 reclasificar.py            || exit 1
run_step "Escribir a GHL"          /usr/bin/python3 escribir_a_ghl.py          || exit 1
run_step "Generar dashboard"       /usr/bin/python3 generar_dashboard.py       || true

# Resumen final (extrae distribución de la última corrida)
echo ""                                                     | tee -a "$LOG"
echo "▶ Resumen distribución por nivel"                     | tee -a "$LOG"
echo "──────────────────────────────────────────────────"   | tee -a "$LOG"
grep -E "^   (Diamante|Platino|Oro|Plata|Bronce|Sin)"  "$LOG" | tail -6 | tee -a "$LOG"

echo ""                                                     | tee -a "$LOG"
echo "✅ Pipeline completado · $(date)"                      | tee -a "$LOG"
notify "Comunidad VIP" "✅ Pipeline diario OK"
