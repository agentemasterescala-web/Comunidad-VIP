#!/bin/bash
# Refresca el dashboard y lo publica en la rama gh-pages del repo.
# GitHub Pages sirve el HTML en una URL estática que se embebe en GHL.
# Disparado por launchd a las 09:00 y 14:00 hora local de la Mac.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"
PUBLISH_DIR="$PROJECT_ROOT/_publish"
HASH_PATH="d-57748dbdaaf0"
DEST_DIR="$PUBLISH_DIR/$HASH_PATH"
LOG="$HERE/logs/publish_$(date +'%Y-%m-%d_%H%M').log"

cd "$HERE"
mkdir -p logs

# Lock para evitar overlap si se dispara dos veces seguidas
LOCKFILE="$HERE/.publish.lock"
if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date +'%F %T')] Otra publicación en curso (PID $OLD_PID), salgo." >> "$LOG"
        exit 0
    fi
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

exec >> "$LOG" 2>&1
echo "════════════════════════════════════════════"
echo "[$(date +'%F %T')] Publish dashboard"
echo "════════════════════════════════════════════"

# 1. Regenerar dashboard.html con datos frescos
#    (consolidar + refrescar GHL + reclasificar + generar) — sin writeback a GHL.
#    Cada script Python carga .env por su cuenta; no sourceamos en bash para
#    evitar errores con comentarios inline o espacios en valores.

PY=$(command -v python3 || echo /usr/bin/python3)

echo "▶ consolidar_excel.py"
$PY consolidar_excel.py >/dev/null || { echo "✗ consolidar falló"; exit 1; }
echo "▶ refrescar_contactos_ghl.py"
$PY refrescar_contactos_ghl.py >/dev/null || { echo "✗ refrescar falló"; exit 1; }
echo "▶ reclasificar.py"
$PY reclasificar.py >/dev/null || { echo "✗ reclasificar falló"; exit 1; }
echo "▶ generar_dashboard.py"
$PY generar_dashboard.py >/dev/null || { echo "✗ generar falló"; exit 1; }

if [ ! -f "$HERE/dashboard.html" ]; then
    echo "✗ dashboard.html no se generó"
    exit 1
fi

# 2. Verificar que el worktree esté en gh-pages
if [ ! -d "$PUBLISH_DIR/.git" ] && [ ! -f "$PUBLISH_DIR/.git" ]; then
    echo "✗ $PUBLISH_DIR no es un worktree git. Re-ejecutá setup_produccion.sh"
    exit 1
fi

cd "$PUBLISH_DIR"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "gh-pages" ]; then
    echo "✗ worktree no está en gh-pages (está en $CURRENT_BRANCH)"
    exit 1
fi

# Sync con remoto antes de publicar (evita conflictos si alguien tocó la rama)
git pull --rebase origin gh-pages >/dev/null 2>&1 || true

# 3. Copiar el dashboard al subpath con hash
mkdir -p "$DEST_DIR"
cp "$HERE/dashboard.html" "$DEST_DIR/index.html"

# Ruta raíz redirige al hash (para que la base sea limpia, pero no expone listado)
cat > "$PUBLISH_DIR/index.html" <<EOF
<!doctype html><meta charset="utf-8"><title>Comunidad VIP</title>
<meta http-equiv="refresh" content="0; url=./$HASH_PATH/">
EOF

# 4. Commit + push si hay cambios
git add index.html "$HASH_PATH/index.html"
if git diff --cached --quiet; then
    echo "▶ Sin cambios en el HTML, no se commitea."
else
    STAMP=$(date +'%Y-%m-%d %H:%M')
    git -c user.email="agentemasterescala@gmail.com" -c user.name="masterescala" \
        commit -m "Update dashboard $STAMP" >/dev/null
    git push origin gh-pages >/dev/null && echo "✓ Publicado · GitHub Pages propagará en ~30-60s"
fi

echo "[$(date +'%F %T')] FIN"
