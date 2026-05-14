#!/bin/bash
# Setup del pipeline VIP en una Mac de producción.
# Uso (desde el directorio procesados/):
#   ./setup_produccion.sh
#
# Hace:
#  1) Verifica Python y openpyxl (instala si falta)
#  2) Pide credenciales GHL y crea .env con permisos 600 (si no existe)
#  3) Instala launchd plist con la ruta absoluta correcta
#  4) Carga la rutina en launchd
#  5) Hace un primer "Run now" para verificar

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

LABEL="com.masterescala.comunidad-vip"
PLIST_SRC="$HERE/launchd/com.masterescala.comunidad-vip.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

LABEL_DB="com.masterescala.comunidad-vip-dashboard"
PLIST_SRC_DB="$HERE/launchd/com.masterescala.comunidad-vip-dashboard.plist.template"
PLIST_DST_DB="$HOME/Library/LaunchAgents/$LABEL_DB.plist"

LABEL_WT="com.masterescala.comunidad-vip-watcher"
PLIST_SRC_WT="$HERE/launchd/com.masterescala.comunidad-vip-watcher.plist.template"
PLIST_DST_WT="$HOME/Library/LaunchAgents/$LABEL_WT.plist"

LABEL_PB="com.masterescala.comunidad-vip-publish"
PLIST_SRC_PB="$HERE/launchd/com.masterescala.comunidad-vip-publish.plist.template"
PLIST_DST_PB="$HOME/Library/LaunchAgents/$LABEL_PB.plist"

# Carpeta a vigilar (originales — donde tu equipo arrastra los Excel mensuales)
ORIGINALES_DIR="$(cd "$HERE/../originales" && pwd)"

echo "════════════════════════════════════════════════════"
echo "  Setup producción · Comunidad VIP Iván Caicedo"
echo "════════════════════════════════════════════════════"
echo

# ── 1) Python deps ──────────────────────────────────────
echo "▶ [1/5] Verificando Python + dependencias"
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ python3 no encontrado. Instala con: xcode-select --install  o  brew install python"
  exit 1
fi
PY=$(command -v python3)
if ! $PY -c "import openpyxl" 2>/dev/null; then
  echo "  ⊕ Instalando openpyxl…"
  $PY -m pip install --user openpyxl
fi
echo "  ✓ Python $($PY --version) listo"
echo

# ── 2) .env ─────────────────────────────────────────────
echo "▶ [2/5] Credenciales GHL (.env)"
if [ -f .env ]; then
  echo "  ✓ .env ya existe — no se sobreescribe"
else
  read -rp "  GHL_TOKEN (pit-...): " TOK
  read -rp "  GHL_LOCATION: " LOC
  cat > .env <<EOF
GHL_TOKEN=$TOK
GHL_LOCATION=$LOC
EOF
  chmod 600 .env
  echo "  ✓ .env creado con permisos 600"
fi
echo

# ── 2.5) Worktree gh-pages para publicar ────────────────
echo "▶ [2.5/5] Worktree gh-pages para publicar dashboard"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"
PUBLISH_DIR="$PROJECT_ROOT/_publish"
if git -C "$PROJECT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  if [ -d "$PUBLISH_DIR/.git" ] || [ -f "$PUBLISH_DIR/.git" ]; then
    echo "  ✓ Worktree _publish/ ya existe"
  else
    git -C "$PROJECT_ROOT" fetch origin gh-pages 2>/dev/null || true
    if git -C "$PROJECT_ROOT" worktree add "$PUBLISH_DIR" gh-pages >/dev/null 2>&1; then
      echo "  ✓ Worktree _publish/ creado en rama gh-pages"
    else
      echo "  ⚠ No se pudo crear worktree gh-pages — publish job no funcionará"
      echo "    (revisá que la rama gh-pages exista en el remoto)"
    fi
  fi
else
  echo "  ⚠ Este directorio no es repo git — publish job no funcionará"
fi
echo

# ── 3) launchd plists ───────────────────────────────────
echo "▶ [3/5] Generando 4 launchd plists (writeback + dashboard + watcher + publish)"
mkdir -p "$HOME/Library/LaunchAgents" logs
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC" > "$PLIST_DST"
chmod 644 "$PLIST_DST"
echo "  ✓ Writeback plist: $PLIST_DST"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_DB" > "$PLIST_DST_DB"
chmod 644 "$PLIST_DST_DB"
echo "  ✓ Dashboard plist: $PLIST_DST_DB"
sed -e "s|__INSTALL_DIR__|$HERE|g" -e "s|__ORIGINALES_DIR__|$ORIGINALES_DIR|g" "$PLIST_SRC_WT" > "$PLIST_DST_WT"
chmod 644 "$PLIST_DST_WT"
echo "  ✓ Watcher plist:  $PLIST_DST_WT (vigila $ORIGINALES_DIR)"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_PB" > "$PLIST_DST_PB"
chmod 644 "$PLIST_DST_PB"
echo "  ✓ Publish plist:  $PLIST_DST_PB (09:00 y 14:00 hora local)"
echo

# ── 4) Cargar en launchd ────────────────────────────────
echo "▶ [4/5] Cargando rutinas en launchd"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"
launchctl unload "$PLIST_DST_DB" 2>/dev/null || true
launchctl load -w "$PLIST_DST_DB"
launchctl unload "$PLIST_DST_WT" 2>/dev/null || true
launchctl load -w "$PLIST_DST_WT"
launchctl unload "$PLIST_DST_PB" 2>/dev/null || true
launchctl load -w "$PLIST_DST_PB"
launchctl list | grep -q "$LABEL"    && echo "  ✓ Writeback cargado (cada 10 min)"        || echo "  ⚠ Writeback no se ve"
launchctl list | grep -q "$LABEL_DB" && echo "  ✓ Dashboard cargado (cada 90 segundos)"    || echo "  ⚠ Dashboard no se ve"
launchctl list | grep -q "$LABEL_WT" && echo "  ✓ Watcher cargado  (instantáneo al subir Excel)" || echo "  ⚠ Watcher no se ve"
launchctl list | grep -q "$LABEL_PB" && echo "  ✓ Publish cargado  (09:00 y 14:00)"       || echo "  ⚠ Publish no se ve"
echo

# ── 5) Run-now de prueba ────────────────────────────────
echo "▶ [5/5] ¿Ejecutar el pipeline AHORA para verificar? [y/N]"
read -r RESP
if [[ "$RESP" =~ ^[Yy]$ ]]; then
  launchctl start "$LABEL"
  echo "  ✓ Disparado. Mira los logs en: $HERE/logs/"
  sleep 5
  ls -t logs/ 2>/dev/null | head -3
fi

# ── Verificación de Full Disk Access ────────────────────
echo
echo "▶ Verificando permisos macOS (Full Disk Access)"
sleep 8   # esperar que la primera corrida del dashboard se ejecute
if [ -f logs/launchd-dashboard.err.log ] && grep -q "Operation not permitted" logs/launchd-dashboard.err.log 2>/dev/null; then
  echo "  ⚠️  PROBLEMA DETECTADO: macOS bloquea launchd al acceder a este directorio."
  echo "     Esto pasa cuando el proyecto vive dentro de ~/Documents/."
  echo
  echo "  📋 Para arreglarlo (1 vez):"
  echo "     1. Abre System Settings → Privacy & Security → Full Disk Access"
  echo "     2. Click '+' y agrega /bin/bash (usa Cmd+Shift+G en el diálogo y escribe /bin/bash)"
  echo "     3. Activa el toggle"
  echo "     4. Repite con /usr/bin/python3 (mismo path)"
  echo "     5. Recarga las rutinas:"
  echo "          launchctl unload $PLIST_DST_DB && launchctl load -w $PLIST_DST_DB"
  echo "          launchctl unload $PLIST_DST    && launchctl load -w $PLIST_DST"
  echo
  echo "  💡 ALTERNATIVA: mover el proyecto fuera de Documents (ej. ~/CommunidadVIP/)"
  echo "     y re-correr este setup desde la nueva ubicación."
else
  echo "  ✓ Sin problemas de permisos detectados"
fi

echo
echo "════════════════════════════════════════════════════"
echo "  ✅ Setup completo"
echo "════════════════════════════════════════════════════"
echo
echo "Para ver el estado:    launchctl list | grep $LABEL"
echo "Para detener:          launchctl unload $PLIST_DST"
echo "Para correr manual:    launchctl start $LABEL"
echo "Para ver logs:         ls -t $HERE/logs/ | head"
