#!/bin/bash
# publicar_dashboard_light.sh
# ─────────────────────────────────────────────────────────────
# Publish "ligero" que corre cada 10 min:
#   reclasificar.py + generar_dashboard.py + push a gh-pages
# NO refresca contactos GHL (eso lo hace el pipeline_diario cada 10 min).
# Con change detection: solo pushea si el contenido del dashboard cambió
# (excluyendo el timestamp "generated_iso" que siempre cambia).
# ─────────────────────────────────────────────────────────────

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"
PUBLISH_DIR="$PROJECT_ROOT/_publish"
HASH_PATH="d-57748dbdaaf0"
DEST_DIR="$PUBLISH_DIR/$HASH_PATH"
LOG="$HERE/logs/publish_light_$(date +'%Y-%m-%d_%H%M').log"

cd "$HERE"
mkdir -p logs

# 1. Lock propio · evita overlap consigo mismo
LOCKFILE="$HERE/.publish_light.lock"
if [ -f "$LOCKFILE" ]; then
    OLD_PID=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date +'%F %T')] Publish-light activo (PID $OLD_PID), salgo." >> "$LOG"
        exit 0
    fi
fi

# 2. Cede el turno al publish FULL si está corriendo (evita conflictos git)
FULL_LOCK="$HERE/.publish.lock"
if [ -f "$FULL_LOCK" ]; then
    OLD_PID=$(cat "$FULL_LOCK" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date +'%F %T')] Publish FULL activo (PID $OLD_PID), cedo turno." >> "$LOG"
        exit 0
    fi
fi

echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT
exec >> "$LOG" 2>&1

echo "════════════════════════════════════════════"
echo "[$(date +'%F %T')] Publish LIGHT (cada 10 min)"
echo "════════════════════════════════════════════"

PY=$(command -v python3 || echo /usr/bin/python3)

echo "▶ reclasificar.py"
$PY reclasificar.py >/dev/null || { echo "✗ reclasificar falló"; exit 1; }
echo "▶ generar_dashboard.py"
$PY generar_dashboard.py >/dev/null || { echo "✗ generar falló"; exit 1; }

if [ ! -f "$HERE/dashboard.html" ]; then
    echo "✗ dashboard.html no se generó"
    exit 1
fi

# 3. Change detection: hash del contenido EXCLUYENDO timestamps que cambian siempre
#    (generated_iso y generated). Si el contenido "real" no cambió, no pusheamos
#    (evita miles de commits basura en gh-pages).
HASH_FILE="$HERE/.dashboard_content_hash"
CURRENT_HASH=$(
    sed -E 's/"generated_iso"[[:space:]]*:[[:space:]]*"[^"]*"//g;
            s/"generated"[[:space:]]*:[[:space:]]*"[^"]*"//g' \
        "$HERE/dashboard.html" | shasum -a 256 | awk '{print $1}'
)
LAST_HASH=$(cat "$HASH_FILE" 2>/dev/null || echo "")

if [ "$CURRENT_HASH" = "$LAST_HASH" ]; then
    echo "▶ Sin cambios en el contenido (hash $CURRENT_HASH). No pusheo."
    echo "[$(date +'%F %T')] FIN (sin push)"
    exit 0
fi

echo "▶ Cambio detectado — hash antes: ${LAST_HASH:-<vacío>}"
echo "                    hash ahora:  $CURRENT_HASH"

# 4. Verificar worktree
if [ ! -e "$PUBLISH_DIR/.git" ]; then
    echo "✗ $PUBLISH_DIR no es worktree git"; exit 1
fi

cd "$PUBLISH_DIR"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "gh-pages" ]; then
    echo "✗ worktree en $CURRENT_BRANCH, no gh-pages"; exit 1
fi

git pull --rebase origin gh-pages >/dev/null 2>&1 || true

mkdir -p "$DEST_DIR"
cp "$HERE/dashboard.html" "$DEST_DIR/index.html"
[ -f "$HERE/escalafon.json" ] && cp "$HERE/escalafon.json" escalafon.json
touch .nojekyll

VSTAMP=$(date +%Y%m%d%H%M%S)
cat > "$PUBLISH_DIR/index.html" <<EOF
<!doctype html><meta charset="utf-8"><title>Comunidad VIP</title>
<meta http-equiv="refresh" content="0; url=./$HASH_PATH/?v=$VSTAMP">
EOF

git add index.html "$HASH_PATH/index.html" escalafon.json .nojekyll 2>/dev/null || true

if git diff --cached --quiet; then
    echo "▶ Sin diff en git a pesar del hash. Guardo hash y salgo."
    echo "$CURRENT_HASH" > "$HASH_FILE"
else
    STAMP=$(date +'%Y-%m-%d %H:%M')
    git -c user.email="agentemasterescala@gmail.com" -c user.name="masterescala" \
        commit -m "Auto-publish light $STAMP" >/dev/null
    if git push origin gh-pages >/dev/null; then
        echo "✓ Publicado light · GitHub Pages propaga en ~30-60s"
        echo "$CURRENT_HASH" > "$HASH_FILE"
    else
        echo "✗ push falló — no guardo hash (reintenta la siguiente corrida)"
        exit 1
    fi
fi

echo "[$(date +'%F %T')] FIN"
