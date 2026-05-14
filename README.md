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
| `pipeline_diario` | cada 10 min | Pipeline completo (consolidar + refrescar GHL + reclasificar + escribir GHL + dashboard) |
| `pipeline_dashboard` | cada 90 seg | Solo refresca contactos + reclasifica + dashboard (sin escritura a GHL) |
| `pipeline_watcher` | ⚡ instantáneo | Detecta archivo nuevo en `datos/originales/` y dispara pipeline completo |

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

## Envío de correos desde el dashboard

Desde la pestaña **📈 Métricas → 👥 No están en Comunidad VIP** puedes seleccionar contactos y enviarles un correo personalizado usando Gmail SMTP (tu cuenta de Workspace).

```bash
# 1. Configurar credenciales Gmail (una sola vez)
nano datos/procesados/.env
# Agregar:
#   GMAIL_FROM=tu-correo@tudominio.com
#   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
#   GMAIL_FROM_NAME=Iván Caicedo

# 2. Arrancar el servidor local cuando quieras enviar
cd datos/procesados
python3 servidor_local.py

# 3. Abrir el dashboard en http://localhost:8888
#    (no en file:// — el envío requiere el servidor)
```

El servidor escucha en `localhost:8888`, sirve el dashboard y expone `POST /api/send-email`. Soporta variables `{nombre}`, `{email}`, `{programa}`, `{telefono}` en la plantilla.

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
        ├── servidor_local.py      ← Servidor local + endpoint Gmail SMTP
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
