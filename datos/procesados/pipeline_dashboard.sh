#!/bin/bash
# Pipeline ligero: solo refresca contactos GHL y regenera dashboard.html
# (NO escribe a GHL — eso lo hace pipeline_diario.sh cada 10 min)
# Diseñado para correr cada 60-90 segundos y mantener el dashboard "en vivo".

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Lock para evitar solapamiento
mkdir -p logs
LOCKFILE="$HERE/.dashboard.lock"
if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        exit 0   # silencioso — otra corrida activa
    fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

if [ -f .env ]; then
    set -a; source .env; set +a
fi

# 1. Refrescar contactos GHL (~16 sec)
# 2. Reclasificar (~1 sec)
# 3. Regenerar dashboard (~1 sec)
# Total: ~20 sec por corrida

/usr/bin/python3 refrescar_contactos_ghl.py > /dev/null 2>&1 || exit 1
/usr/bin/python3 reclasificar.py > /dev/null 2>&1 || exit 1
/usr/bin/python3 generar_dashboard.py > /dev/null 2>&1 || exit 1

echo "[$(date +'%Y-%m-%d %H:%M:%S')] dashboard refreshed" >> logs/dashboard_refresh.log
