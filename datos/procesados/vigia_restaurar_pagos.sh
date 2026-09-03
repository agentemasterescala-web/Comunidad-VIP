#!/bin/zsh
# vigia_restaurar_pagos.sh
# Espera a que se libere el cupo diario de GHL y restaura pagos.json con un
# barrido por tag (merge NO destructivo, gracias al fix touched_cids). Se
# autotermina tras UNA restauracion exitosa (pagos.json >= 100). Idempotente.
#
# Lanzar detached:   nohup ./vigia_restaurar_pagos.sh >/dev/null 2>&1 &
# Ver progreso:      tail -f logs/vigia_restaurar_pagos.log
# Matar:             kill "$(cat .vigia_restaurar.lock)"
set -u

HERE="/Users/masterescala/ComunidadVIP/datos/procesados"
LOG="$HERE/logs/vigia_restaurar_pagos.log"
LOCK="$HERE/.vigia_restaurar.lock"
cd "$HERE" || exit 1

log(){ echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }

# Lock: un solo vigia a la vez
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  log "ya hay un vigia activo (PID $(cat "$LOCK")); salgo."
  exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# Credenciales GHL desde .env
GHL_TOKEN=$(grep -E '^GHL_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d "\"'")
GHL_LOCATION=$(grep -E '^GHL_LOCATION=' .env | head -1 | cut -d= -f2- | tr -d "\"'")

THRESHOLD=5000      # cupo minimo para lanzar (la restauracion usa ~239+ llamadas)
POLL=150            # segundos entre sondeos
MAX_HOURS=8
DEADLINE=$(( $(date +%s) + MAX_HOURS*3600 ))

log "=== vigia armado (PID $$) · espera cupo GHL >= ${THRESHOLD} para restaurar pagos ==="

while :; do
  if [ "$(date +%s)" -gt "$DEADLINE" ]; then
    log "TIMEOUT tras ${MAX_HOURS}h sin cupo suficiente; abandono."
    exit 1
  fi

  REM=$(curl -s -D - -o /dev/null \
        "https://services.leadconnectorhq.com/contacts/?locationId=${GHL_LOCATION}&limit=1" \
        -H "Authorization: Bearer ${GHL_TOKEN}" -H "Version: 2021-07-28" \
        | awk 'tolower($1)=="x-ratelimit-daily-remaining:"{print $2}' | tr -d '\r')
  case "$REM" in (''|*[!0-9]*) REM=0 ;; esac
  log "cupo diario restante: ${REM}"

  if [ "$REM" -ge "$THRESHOLD" ]; then
    log "cupo suficiente; lanzo restauracion: extraer_pagos.py --tag 'app master escala' --threads 6"
    /usr/bin/python3 "$HERE/extraer_pagos.py" --tag "app master escala" --threads 6 >> "$LOG" 2>&1
    N=$(/usr/bin/python3 -c "import json;print(len(json.load(open('$HERE/pagos.json'))))" 2>/dev/null)
    case "$N" in (''|*[!0-9]*) N=0 ;; esac
    log "restauracion terminada · pagos.json ahora: ${N}"
    if [ "$N" -ge 100 ]; then
      log "OK (${N} >= 100). Vigia cumplido; salgo."
      exit 0
    fi
    log "pagos aun bajos (${N}); reintento en proximo ciclo (posible 429 parcial)."
  fi

  sleep "$POLL"
done
