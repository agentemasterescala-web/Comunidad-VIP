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

# Consolidar (python DIRECTO, no bash): lee los Excel de Google Drive y reconstruye
# el maestro. Va en su propio agente porque macOS TCC no da acceso a Drive cuando
# launchd lanza un wrapper bash (binario responsable = /bin/bash, de plataforma Apple).
LABEL_CS="com.masterescala.comunidad-vip-consolidar"
PLIST_SRC_CS="$HERE/launchd/com.masterescala.comunidad-vip-consolidar.plist.template"
PLIST_DST_CS="$HOME/Library/LaunchAgents/$LABEL_CS.plist"

# Taggear IG (python directo): detecta desde qué IG escribió un contacto y le
# agrega el tag (ig-ivan-caicedo o ig-escala-academy) según meta.ig.pageId.
LABEL_IG="com.masterescala.comunidad-vip-taggear-ig"
PLIST_SRC_IG="$HERE/launchd/com.masterescala.comunidad-vip-taggear-ig.plist.template"
PLIST_DST_IG="$HOME/Library/LaunchAgents/$LABEL_IG.plist"

# Taggear WA (python directo): detecta desde qué número WA escribió el contacto
# (from/to en mensajes TYPE_WHATSAPP) y le agrega tag wa-<últimos 4 dígitos>.
LABEL_WA="com.masterescala.comunidad-vip-taggear-wa"
PLIST_SRC_WA="$HERE/launchd/com.masterescala.comunidad-vip-taggear-wa.plist.template"
PLIST_DST_WA="$HOME/Library/LaunchAgents/$LABEL_WA.plist"

# Extraer pagos (python directo): lee notas de GHL 'Pago recibido App Master
# Escala' y genera pagos.json que consume el dashboard.
LABEL_EP="com.masterescala.comunidad-vip-extraer-pagos"
PLIST_SRC_EP="$HERE/launchd/com.masterescala.comunidad-vip-extraer-pagos.plist.template"
PLIST_DST_EP="$HOME/Library/LaunchAgents/$LABEL_EP.plist"

# Publish LIGHT (bash): reclasifica + genera dashboard + push a gh-pages cada
# 10 min, con change detection. NO refresca GHL (eso ya lo hace el pipeline).
# Permite que los cambios lleguen al dashboard público en ≤10 min.
LABEL_PL="com.masterescala.comunidad-vip-publish-light"
PLIST_SRC_PL="$HERE/launchd/com.masterescala.comunidad-vip-publish-light.plist.template"
PLIST_DST_PL="$HOME/Library/LaunchAgents/$LABEL_PL.plist"

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
echo "▶ [3/5] Generando 9 launchd plists (writeback + dashboard + watcher + publish + consolidar + taggear-ig + taggear-wa + extraer-pagos + publish-light)"
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
echo "  ✓ Publish plist:  $PLIST_DST_PB (09:00, 10:15, 14:00 y 18:00 hora local)"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_CS" > "$PLIST_DST_CS"
chmod 644 "$PLIST_DST_CS"
echo "  ✓ Consolidar plist: $PLIST_DST_CS (cada 10 min, python directo → lee Drive)"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_IG" > "$PLIST_DST_IG"
chmod 644 "$PLIST_DST_IG"
echo "  ✓ Taggear-IG plist: $PLIST_DST_IG (cada 10 min, python directo → GHL API)"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_WA" > "$PLIST_DST_WA"
chmod 644 "$PLIST_DST_WA"
echo "  ✓ Taggear-WA plist: $PLIST_DST_WA (cada 10 min, python directo → GHL API)"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_EP" > "$PLIST_DST_EP"
chmod 644 "$PLIST_DST_EP"
echo "  ✓ Extraer-Pagos plist: $PLIST_DST_EP (cada 10 min, python directo → notas GHL)"
sed "s|__INSTALL_DIR__|$HERE|g" "$PLIST_SRC_PL" > "$PLIST_DST_PL"
chmod 644 "$PLIST_DST_PL"
echo "  ✓ Publish-Light plist: $PLIST_DST_PL (cada 10 min, reclasifica + genera + push si cambió)"
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
launchctl unload "$PLIST_DST_CS" 2>/dev/null || true
launchctl load -w "$PLIST_DST_CS"
launchctl unload "$PLIST_DST_IG" 2>/dev/null || true
launchctl load -w "$PLIST_DST_IG"
launchctl unload "$PLIST_DST_WA" 2>/dev/null || true
launchctl load -w "$PLIST_DST_WA"
launchctl unload "$PLIST_DST_EP" 2>/dev/null || true
launchctl load -w "$PLIST_DST_EP"
launchctl unload "$PLIST_DST_PL" 2>/dev/null || true
launchctl load -w "$PLIST_DST_PL"
launchctl list | grep -q "$LABEL"    && echo "  ✓ Writeback cargado (cada 10 min)"        || echo "  ⚠ Writeback no se ve"
launchctl list | grep -q "$LABEL_DB" && echo "  ✓ Dashboard cargado (cada 90 segundos)"    || echo "  ⚠ Dashboard no se ve"
launchctl list | grep -q "$LABEL_WT" && echo "  ✓ Watcher cargado  (instantáneo al subir Excel)" || echo "  ⚠ Watcher no se ve"
launchctl list | grep -q "$LABEL_PB" && echo "  ✓ Publish cargado  (09:00, 10:15, 14:00 y 18:00)" || echo "  ⚠ Publish no se ve"
launchctl list | grep -q "$LABEL_CS" && echo "  ✓ Consolidar cargado (cada 10 min, lee Drive)" || echo "  ⚠ Consolidar no se ve"
launchctl list | grep -q "$LABEL_IG" && echo "  ✓ Taggear-IG cargado (cada 10 min, GHL API)" || echo "  ⚠ Taggear-IG no se ve"
launchctl list | grep -q "$LABEL_WA" && echo "  ✓ Taggear-WA cargado (cada 10 min, GHL API)" || echo "  ⚠ Taggear-WA no se ve"
launchctl list | grep -q "$LABEL_EP" && echo "  ✓ Extraer-Pagos cargado (cada 10 min, notas GHL)" || echo "  ⚠ Extraer-Pagos no se ve"
launchctl list | grep -q "$LABEL_PL" && echo "  ✓ Publish-Light cargado (cada 10 min, push si cambió)" || echo "  ⚠ Publish-Light no se ve"
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

# ── Verificación de Full Disk Access (acceso a Google Drive) ────────────────
echo
echo "▶ Verificando acceso a Google Drive desde launchd (Full Disk Access)"
sleep 8   # esperar que la primera corrida del agente consolidar se ejecute
PY_REAL="$(/usr/bin/python3 -c 'import sys; print(sys.executable)' 2>/dev/null)"
if [ -f logs/launchd-consolidar.out.log ] && grep -q "0 registros leídos" logs/launchd-consolidar.out.log 2>/dev/null; then
  echo "  ⚠️  PROBLEMA: el agente consolidar lee 0 Excels desde Google Drive."
  echo "     macOS TCC no le da a launchd acceso a ~/Library/CloudStorage/ sin permiso."
  echo
  echo "  📋 Para arreglarlo (1 vez):"
  echo "     1. Abre Ajustes → Privacidad y seguridad → Acceso total al disco"
  echo "     2. Click '+'. En el diálogo pulsa la tecla '/' (abre 'Ir a:') y pega EXACTO:"
  echo "          $PY_REAL"
  echo "     3. Selecciónalo y deja el toggle ACTIVADO"
  echo "     4. Recarga el agente consolidar:"
  echo "          launchctl bootout gui/\$(id -u)/$LABEL_CS"
  echo "          launchctl bootstrap gui/\$(id -u) $PLIST_DST_CS"
  echo
  echo "  ⚠️  OJO: NO sirve dar el permiso a /bin/bash. Es un binario de plataforma"
  echo "     de Apple que no retiene el permiso como proceso responsable de TCC."
  echo "     Por eso 'consolidar' corre como python DIRECTO (no vía bash)."
else
  echo "  ✓ Acceso a Drive OK (consolidar leyó los Excels)"
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
