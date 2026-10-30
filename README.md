# Panel Comunidad VIP — Iván Caicedo

Pipeline automatizado que clasifica miembros VIP de la comunidad de Iván Caicedo en niveles (Bronce → Diamante) según pedidos generados en Dropi, y mantiene un dashboard ejecutivo + escritura de vuelta a GoHighLevel (GHL).

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│  ENTRADA (mensual): Excel de Dropi por país                     │
│  ↓                                                              │
│  consolidar_excel.py    → maestro_emails.xlsx                   │
│  refrescar_contactos_ghl.py → ghl_contacts_raw.json             │
│  reclasificar.py        → clasificacion_usuarios.xlsx           │
│  escribir_a_ghl.py      → actualiza tags + campos + historial    │
│  generar_dashboard.py   → dashboard.html (local)                │
└─────────────────────────────────────────────────────────────────┘
```

## Reglas de clasificación

| Nivel | Pedidos/mes mínimo | Meses requeridos | Sumatoria mínima |
|-------|-------------------|------------------|------------------|
| 💎 Diamante | 5.000+ | 3 activos | 15.000 |
| 💠 Platino | 1.000+ | 3 activos | 3.000 |
| 🥇 Oro | 300+ | 3 activos | 900 |
| 🥈 Plata | 100+ | 3 activos | 300 |
| 🥉 Bronce | 30+ | 2 activos | 60 |
| Sin nivel | <30 o solo 1 mes | — | — |

- **Ingreso**: top-2 de los 5 meses más recientes ≥ 60 pedidos
- **Bronce**: 2 meses con ventas son suficientes
- **Plata-Diamante**: 3 meses con ventas + sumatoria top-3 según rango
- **Eliminación**: 3 meses consecutivos sin pedidos (con actividad previa)

## Setup en una Mac (producción)

```bash
# 1. Clonar el repo
git clone git@github.com:Diegoforerog/<nombre-repo>.git
cd <nombre-repo>

# 2. Crear estructura de datos
mkdir -p "datos/originales" "datos/procesados/logs"

# 3. Configurar credenciales (NO subir al repo)
cd datos/procesados
cp .env.example .env
# Editar .env con GHL_TOKEN y GHL_LOCATION reales
chmod 600 .env

# 4. Instalar dependencias Python
pip3 install --user openpyxl

# 5. Subir Excels de Dropi mensuales a datos/originales/<MesAño>/
#    Ej: datos/originales/Mayo2026/Informe mayo 2026 paises.xlsx

# 6. Correr el setup (instala 3 rutinas launchd)
./setup_produccion.sh
```

## Rutinas launchd que se instalan

| Rutina | Frecuencia | Qué hace |
|--------|-----------|----------|
| `comunidad-vip` (pipeline_diario) | cada 10 min | refrescar GHL + reclasificar + escribir GHL + dashboard (NO consolida — ver nota) |
| `comunidad-vip-consolidar` | cada 10 min | **python directo** — lee los Excel de Drive y reconstruye `maestro_emails.xlsx` |
| `comunidad-vip-dashboard` | cada 90 seg | Solo refresca contactos + reclasifica + dashboard (sin escritura a GHL) |
| `comunidad-vip-watcher` | ⚡ instantáneo | Detecta archivo nuevo en `datos/originales/` y dispara pipeline |
| `comunidad-vip-publish` | 09:00 / 10:15 / 14:00 / 18:00 | Publica el dashboard al repo de GitHub Pages |
| `comunidad-vip-taggear-ig` | cada 10 min · python directo | Detecta desde qué IG escribió cada contacto (via `meta.ig.pageId`) y le agrega `ig-ivan-caicedo` o `ig-escala-academy`. Idempotente y no destructivo. |
| `comunidad-vip-taggear-wa` | cada 10 min · python directo | Detecta desde qué número de WhatsApp del negocio escribió el contacto (`from`/`to` en mensajes `TYPE_WHATSAPP`) y le agrega tag `wa-<últimos-4-dígitos>`. Idempotente y no destructivo. |
| `comunidad-vip-extraer-pagos` | cada 10 min · python directo | Lee notas GHL con título `Pago recibido App Master Escala`, parsea Tipo/Plan/Créditos/Bruto/Comisión/Neto y escribe `pagos.json` que consume la pestaña App Master Escala del dashboard. |
| `comunidad-vip-publish-light` | cada 10 min · bash | Reclasifica + genera dashboard + pushea a `gh-pages` si el contenido cambió. **NO refresca GHL** (usa el dump que otras rutinas mantienen fresco). Con `.dashboard_content_hash` para change detection — evita commits basura. Complementa el `publish` full (09/10:15/14/18h) manteniendo la versión pública ≤10 min de rezago. |

### ⚠️ Full Disk Access (acceso a Google Drive)

`consolidar` lee `datos/originales/` → symlink a `~/Library/CloudStorage/GoogleDrive-…`, una
ruta protegida por TCC. macOS solo concede el acceso al **proceso responsable**, que es el
binario que **launchd** lanza. Por eso `consolidar` corre en su **propio agente como python
directo** (no dentro de `pipeline_diario.sh`): un wrapper `/bin/bash` no funciona porque
`/bin/bash` es binario de plataforma de Apple y no retiene el permiso.

Hay que dar Full Disk Access **una vez** al binario real de python (Ajustes → Privacidad y
seguridad → Acceso total al disco → `+` → tecla `/` → pegar la ruta):

```
/Library/Developer/CommandLineTools/usr/bin/python3
```

(ese es el `sys.executable` real detrás de `/usr/bin/python3`). Si falta el permiso,
`consolidar` lee 0 registros y **no sobrescribe** el maestro (guarda anti-borrado), así que
no se pierden datos; simplemente deja de actualizarse hasta que se conceda el permiso.

## Mantenimiento mensual

```bash
# Tu equipo arrastra el Excel del nuevo mes a:
datos/originales/<MesAño>/    # ej. Mayo2026/

# El watcher launchd detecta el cambio y corre todo automáticamente.
# Al día siguiente las clasificaciones están actualizadas en GHL.
```

## Dashboard

```bash
# Abrir el dashboard local (se regenera cada 90 segundos):
open datos/procesados/dashboard.html
```

Funciones:
- **Categoría 🏆 VIP** — 7 tabs: Resumen, Clasificación, Top 100, Alertas, País, Reglas, Consulta
- **Categoría 📈 Métricas** — 4 tabs: No están en VIP, Master vs Iniciación, En Dropi sin GHL, Posibles duplicados
- Filtros por nivel, programa, país, multi-país
- Ficha individual de cada miembro (click en su nombre)
- Botón **🔄 Actualizar** manual (sin auto-refresh disruptivo)
- Persistencia de pestaña y scroll entre recargas
- Estadísticas en tiempo real con charts (Chart.js)

## Concurso — MASTER ESCALA GAMES

Ranking público en vivo del concurso de la comunidad. Temporada **oct 2026 – mar 2027** (6 meses). Gana el **TOP-3 por número de ÓRDENES ENTREGADAS** acumuladas (bolsa 130 M → 1º 100 M / 2º 20 M / 3º 10 M). **Desempate** por **% de efectividad = entregadas ÷ (entregadas + devoluciones)**. Un único ranking acumulado; se anuncia al cierre (31-mar-2027, en abril).

- **Cómputo (en este repo):** `concurso_compute.py` → `concurso_ranking.json`.
  - Participantes = contactos VIP con ventas en la ventana, **agrupados por persona**: union-find sobre el correo de ventas → cada correo cuenta **una sola vez** (evita filas dobles cuando una persona tiene varios contactos GHL que comparten tienda). Nombres normalizados (title-case, sin correos/handles como nombre).
  - Ordena por `entregadas`; expone también `devoluciones` y `ventas` (neto) por periodo.
  - Config editable: `concurso_config.json` (nombre, premios, fechas, políticas/reglas) — **gitignored**; `concurso_ranking.json` también es artefacto generado (gitignored). Se regenera en `pipeline_dashboard.sh`.
- **Fecha de corte:** el Excel de Dropi no trae fecha → la carpeta fija el corte con el sufijo `-C<DD>` (ej. `Octubre2026-C23` = corte al 23-oct). Concurso y panel VIP muestran "a corte del [fecha]".
- **Métrica vs VIP:** ambos salen de Dropi. VIP titula con **pedidos = entregadas + devoluciones**; el concurso con **entregadas**. Las *entregadas* del concurso coinciden exactamente con las de la ficha VIP (fila del mes); `% Efect.` solo desempata. (La regla del ganador por entregadas vino del dueño/PDF; el "neto" fue provisional y se descartó.)
- **Página pública:** vive en el repo **Dashboard_GC** (`backend/app/reto.html`), servida en `/concurso` — landing horizontal de 5 pantallas, responsive (móvil/tablet/PC sin scroll). Lee `/api/concurso/ranking` (público, sin PII); el equipo logueado usa `/api/concurso/ranking-full` y, desde el ranking, abre la ficha VIP completa del participante.

## Archivos del proyecto

```
.
├── README.md
├── .gitignore
└── datos/
    ├── originales/                ← Excels de Dropi (NO en git, datos sensibles)
    └── procesados/
        ├── .env                   ← Credenciales (NO en git)
        ├── .env.example           ← Template
        ├── consolidar_excel.py    ← Consolida Excels en maestro
        ├── refrescar_contactos_ghl.py  ← Baja contactos de GHL
        ├── reclasificar.py        ← Aplica reglas y genera reporte
        ├── escribir_a_ghl.py      ← Escribe tags + campos en GHL
        ├── generar_dashboard.py   ← Genera dashboard.html
        ├── concurso_compute.py    ← Ranking del concurso → concurso_ranking.json
        ├── pipeline_diario.sh     ← Orquestador full
        ├── pipeline_dashboard.sh  ← Orquestador ligero
        ├── pipeline_archivo_nuevo.sh  ← Disparado por watcher
        ├── setup_produccion.sh    ← Instala las rutinas launchd
        └── launchd/               ← Templates de plists
```

## Seguridad

- `.env` con `chmod 600` (solo tu usuario lo puede leer)
- Token GHL nunca se commitea (excluido en `.gitignore`)
- Datos personales (emails, teléfonos) excluidos del repo
- Si el token se filtra, rotarlo en GHL → Settings → Private Integration Tokens

## Stack

- Python 3 + openpyxl (procesamiento)
- Bash (orquestación)
- macOS launchd (scheduling + file watching)
- HTML + Tailwind CSS via CDN + Chart.js (dashboard, sin build step)
- GHL API v2 (lectura + escritura)
