#!/bin/bash
# Disparado por launchd (WatchPaths) cuando hay cambios en datos/originales/
# Espera 30s para que el archivo termine de copiarse y luego corre el pipeline completo.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

mkdir -p logs
LOG="$HERE/logs/watcher.log"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] 📂 Cambio detectado en datos/originales/" >> "$LOG"

# Debounce: si llegan múltiples eventos en ráfaga (típico al copiar un archivo
# grande), evitamos correr el pipeline una vez por evento.
sleep 30

# Verificar si otro pipeline está corriendo — el lock dentro de pipeline_diario.sh
# también lo maneja, pero acá lo chequeamos para no log-spamear.
if [ -f "$HERE/.pipeline.lock" ]; then
    OLD_PID=$(cat "$HERE/.pipeline.lock" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date +'%H:%M:%S')] Pipeline ya activo (PID $OLD_PID) — saltando" >> "$LOG"
        exit 0
    fi
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] ▶ Disparando pipeline_diario.sh por archivo nuevo" >> "$LOG"
bash "$HERE/pipeline_diario.sh" >> "$LOG" 2>&1
echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✓ Pipeline finalizado" >> "$LOG"

# Notificación macOS
osascript -e 'display notification "Pipeline ejecutado por nuevo archivo en datos/originales/" with title "Comunidad VIP"' 2>/dev/null || true
