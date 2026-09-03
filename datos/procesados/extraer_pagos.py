#!/usr/bin/env python3
"""
extraer_pagos.py
═══════════════════════════════════════════════════════════════════════
Recorre contactos de GHL buscando notas con título 'Pago recibido App
Master Escala', parsea sus campos (Tipo, Nombre del plan, Créditos,
Bruto USD, Comisión Stripe USD, Neto USD, Stripe charge ID) y escribe
pagos.json usado por el dashboard.

El 'Stripe charge ID' (id de la transacción en Stripe, ej. 'ch_3Ab…') se
lee de la nota si la automatización Stripe→GHL lo incluye como una línea
'Stripe charge ID: ch_…' en el cuerpo; si la nota no lo trae, queda ''.

Cada fila del JSON = una nota (una transacción). Incluye info del
contacto: email, nombre, si es estudiante (tag 'estudiante') y su
programa (Master Escala / Iniciación Escala / Ambos / Sin programa,
según tags 'escala'/'iniciacion').

Modos:
  DEFAULT (incremental) · procesa contactos con dateUpdated < N horas
                          (default 2). Apto para launchd cada 10 min.
  --backfill            · procesa TODOS los contactos del dump local.
                          Solo primera vez (2-3h por rate limits).
  --contact CID         · un contacto puntual (pruebas).
  --limit N             · corta a N contactos.
  --skip N              · salta los primeros N (para reanudar).
  --hours N             · ventana modo incremental (default 2).

El script SIEMPRE actualiza pagos.json de forma no destructiva:
  · Backfill → reescribe completo.
  · Incremental → merge: mantiene registros previos, agrega/actualiza los
    de contactos vistos en esta corrida. Dedup por (contactId, noteId).
"""
import os, sys, json, time, argparse, re, urllib.request, urllib.error, threading
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(_HERE, ".env")
if os.path.isfile(_ENV):
    for line in open(_ENV):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        v = v.strip()
        if v and v[0] not in ('"', "'"):
            hp = v.find(" #")
            if hp >= 0: v = v[:hp].rstrip()
        os.environ.setdefault(k.strip(), v.strip('"').strip("'"))

TOK = os.environ.get("GHL_TOKEN")
LOC = os.environ.get("GHL_LOCATION")
if not TOK or not LOC:
    print("ERROR: falta GHL_TOKEN o GHL_LOCATION en .env"); sys.exit(1)

RAW = os.path.join(_HERE, "ghl_contacts_raw.json")
OUT_PAGOS = os.path.join(_HERE, "pagos.json")

NOTE_TITLE = "Pago recibido App Master Escala"

TAG_MASTER = "escala"
TAG_INICIACION = "iniciacion"
TAG_ESTUDIANTE = "estudiante"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def http(method, url, retries=4):
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method, headers={
            "Authorization": f"Bearer {TOK}",
            "Version": "2021-04-15",
            "Accept": "application/json",
            "User-Agent": UA,
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            code = e.code
            body_err = e.read().decode(errors="replace")[:400]
            if code == 429 or 500 <= code < 600:
                time.sleep(2 ** attempt); continue
            raise RuntimeError(f"HTTP {code}: {body_err}")
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Reintentos agotados: {method} {url}")


def get_notes(cid):
    r = http("GET", f"https://services.leadconnectorhq.com/contacts/{cid}/notes")
    return r.get("notes", []) if isinstance(r, dict) else []


def search_contacts_by_tag(tag, page_limit=100):
    """Consulta la API GHL para listar contactos con el tag exacto (case-insensitive).
    Retorna lista de contactos (dict con al menos id, email, tags). Paginado."""
    all_contacts = []
    search_after = None
    while True:
        body = {
            "locationId": LOC,
            "pageLimit": page_limit,
            "filters": [{"field": "tags", "operator": "contains", "value": tag.lower()}],
            "sort": [{"field": "dateAdded", "direction": "asc"}],
        }
        if search_after:
            body["searchAfter"] = search_after
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://services.leadconnectorhq.com/contacts/search/",
            data=data, method="POST", headers={
                "Authorization": f"Bearer {TOK}",
                "Version": "2021-04-15",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": UA,
            })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.load(r)
        except urllib.error.HTTPError as e:
            time.sleep(2)
            continue
        page = res.get("contacts", [])
        if not page: break
        all_contacts.extend(page)
        # Cursor
        last = page[-1]
        search_after = last.get("searchAfter") or [last.get("dateAdded"), last.get("id")]
        if len(page) < page_limit: break
    return all_contacts


def to_float(s):
    try: return float(str(s).replace(",", "").strip())
    except: return 0.0


def parse_nota_body(text):
    """Parsea bodyText tipo 'Campo: valor\\n\\n' y devuelve dict."""
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line: continue
        if ":" not in line: continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def charge_id_from_campos(campos):
    """Extrae el 'Stripe charge ID' de la nota. Tolerante a variantes de la
    etiqueta (mayúsculas/espacios): 'Stripe charge ID', 'Charge ID',
    'Stripe charge', 'stripe_charge_id'… Devuelve '' si la nota no lo trae."""
    low = {k.lower().strip(): (v or "").strip() for k, v in campos.items()}
    for key in ("stripe charge id", "charge id", "stripe charge",
                "stripe_charge_id", "charge"):
        v = low.get(key)
        if v:
            return v
    return ""


def programa_from_tags(tags):
    tags_l = [t.lower() for t in (tags or [])]
    has_m = TAG_MASTER in tags_l
    has_i = TAG_INICIACION in tags_l
    if has_m and has_i: return "Ambos"
    if has_m:          return "Master Escala"
    if has_i:          return "Iniciación Escala"
    return "Sin programa"


def es_estudiante(tags):
    return TAG_ESTUDIANTE in [t.lower() for t in (tags or [])]


def procesar_contacto(c):
    """Devuelve lista de dicts (una por nota de pago) para este contacto,
    o [] si no tiene ninguna. Puede lanzar RuntimeError (API)."""
    cid = c["id"]
    notes = get_notes(cid)
    out = []
    for n in notes:
        if (n.get("title") or "").strip() != NOTE_TITLE: continue
        campos = parse_nota_body(n.get("bodyText") or "")
        # Los campos vienen así en la nota:
        # Tipo, Nombre del plan, Créditos, Bruto USD, Comisión Stripe USD, Neto USD
        tipo_raw = (campos.get("Tipo") or "").lower()
        tipo = "Top-up" if "topup" in tipo_raw else ("Nueva suscripción" if "subscription" in tipo_raw else campos.get("Tipo",""))
        out.append({
            "note_id":         n.get("id"),
            "contact_id":      cid,
            "fecha":           n.get("dateAdded"),
            "email":           (c.get("email") or "").lower(),
            "nombre":          c.get("contactName") or "",
            "telefono":        c.get("phone") or "",
            "estudiante":      es_estudiante(c.get("tags")),
            "programa":        programa_from_tags(c.get("tags")),
            "tipo":            tipo,
            "tipo_raw":        campos.get("Tipo",""),
            "descripcion":     campos.get("Nombre del plan",""),
            "creditos":        int(to_float(campos.get("Créditos","0"))),
            "bruto_usd":       to_float(campos.get("Bruto USD","0")),
            "comision_usd":    to_float(campos.get("Comisión Stripe USD","0")),
            "neto_usd":        to_float(campos.get("Neto USD","0")),
            "stripe_charge_id": charge_id_from_campos(campos),
        })
    return out


def load_local_dump():
    if not os.path.isfile(RAW):
        print(f"ERROR: falta {RAW}. Corre refrescar_contactos_ghl.py primero."); sys.exit(1)
    return json.load(open(RAW))


def parse_iso(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except: return None


def load_existing_pagos():
    if not os.path.isfile(OUT_PAGOS): return []
    try: return json.load(open(OUT_PAGOS))
    except: return []


def save_pagos(items):
    # Escritura atómica
    tmp = OUT_PAGOS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, OUT_PAGOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="Todos los contactos (barrido total)")
    ap.add_argument("--vip-candidates", action="store_true", help="Solo contactos con tag del ecosistema VIP (10× más rápido). Merge no destructivo con pagos.json existente.")
    ap.add_argument("--tag", help="Filtra contactos con el tag dado (via API GHL, en vivo). Ej: --tag 'app master escala'. Merge no destructivo.")
    ap.add_argument("--contact", help="CID puntual")
    ap.add_argument("--hours", type=int, default=2, help="Ventana incremental (default 2h)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0, help="Salta los primeros N (para reanudar)")
    ap.add_argument("--threads", type=int, default=1, help="Threads paralelos (default 1). Máximo recomendado 10 para no exceder rate limit GHL.")
    args = ap.parse_args()

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"extraer_pagos_{datetime.now().strftime('%Y-%m-%d_%H%M')}.log")
    log = open(log_path, "w")
    def out(s): print(s); log.write(s + "\n"); log.flush()

    modo = "BACKFILL" if args.backfill else ("PUNTUAL" if args.contact else f"INCREMENTAL {args.hours}h")
    out(f"═══ extraer_pagos · {modo} · log: {log_path}")

    if args.contact:
        dump = load_local_dump()
        target = next((c for c in dump if c.get("id") == args.contact),
                      {"id": args.contact, "contactName": "(no-en-dump)", "tags": []})
        universe = [target]
    elif args.tag:
        out(f"Consultando GHL API por contactos con tag '{args.tag}'...")
        universe = search_contacts_by_tag(args.tag)
        out(f"Contactos con tag '{args.tag}': {len(universe)}")
    elif args.vip_candidates:
        # Filtro por tags del ecosistema VIP. Los pagadores conocidos siempre tienen
        # alguno de estos (evidencia empírica al inspeccionar 5+ pagadores).
        VIP_TAGS = {
            "estudiante", "escala", "iniciacion",
            "comunidad vip new", "vip sin form", "vip sin clasificar", "sin form",
            "vip plata", "vip oro", "vip bronce", "vip platino", "vip diamante",
        }
        dump = load_local_dump()
        universe = [c for c in dump if VIP_TAGS & {t.lower() for t in (c.get("tags") or [])}]
        out(f"Candidatos VIP (tag del ecosistema): {len(universe)} contactos")
    elif args.backfill:
        universe = load_local_dump()
        out(f"Backfill total: {len(universe)} contactos")
    else:
        # Modo incremental: unión de dos criterios (más robusto)
        #  (a) dateUpdated en las últimas N horas
        #  (b) contactos con tag 'app master escala' (aplicado por el workflow Stripe;
        #      cubre casos donde el add-tag no bumpea el dateUpdated del contacto).
        dump = load_local_dump()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        seen_cid = set()
        universe = []
        for c in dump:
            du = parse_iso(c.get("dateUpdated") or "")
            has_tag = any(t.lower() == "app master escala" for t in (c.get("tags") or []))
            if (du and du >= cutoff) or has_tag:
                if c["id"] not in seen_cid:
                    seen_cid.add(c["id"]); universe.append(c)
        out(f"Contactos elegibles (dateUpdated <{args.hours}h ∪ tag 'app master escala'): {len(universe)}")

    if args.skip:
        out(f"Saltando primeros {args.skip} (de {len(universe)})")
        universe = universe[args.skip:]
    if args.limit and len(universe) > args.limit:
        out(f"Limitado a {args.limit} (de {len(universe)})")
        universe = universe[:args.limit]

    # Cargar existing (para merge). Solo backfill total reescribe desde cero.
    # vip-candidates y modo incremental hacen merge no destructivo.
    reset_all = args.backfill and not args.vip_candidates and not args.tag
    existing = [] if reset_all else load_existing_pagos()
    if existing:
        out(f"Cargados {len(existing)} pagos previos (merge)")

    stats = {"con-pagos": 0, "sin-pagos": 0, "error": 0}
    new_items = []   # notas encontradas en esta corrida
    touched_cids = set()   # contactos procesados (para saber qué reemplazar del existing)
    done = [0]       # contador mutable para el modo paralelo
    lock = threading.Lock()

    def _handle_result(c, items, err):
        """Actualiza stats + log + autosave. Debe llamarse dentro del lock (o
        sin concurrencia)."""
        done[0] += 1
        if err is not None:
            # NO agregar a touched_cids en error: así merge_pagos CONSERVA los
            # pagos existentes del contacto. (Antes se agregaba siempre, y un
            # error 429 borraba los pagos del contacto → pagos.json se decimaba.)
            log.write(f"  ✗ {c.get('id','?')} error: {err}\n"); stats["error"] += 1
        else:
            touched_cids.add(c["id"])   # solo contactos procesados OK
            if items:
                stats["con-pagos"] += 1
                new_items.extend(items)
                for it in items:
                    log.write(f"  ✓ {c['id']} · {it['fecha'][:10] if it['fecha'] else '?'} · {it['tipo']:<20} · {it['descripcion'][:40]:<40} · {it['neto_usd']} USD\n")
            else:
                stats["sin-pagos"] += 1
        if done[0] % 100 == 0:
            out(f"  · procesados {done[0]}/{len(universe)} · {stats} · pagos nuevos: {len(new_items)}")
        if done[0] % 500 == 0 and (args.backfill or args.hours >= 24):
            merged = merge_pagos(existing, new_items, touched_cids)
            save_pagos(merged)
            log.write(f"    [auto-save: {len(merged)} pagos totales]\n"); log.flush()

    if args.threads <= 1:
        # Camino serial
        for c in universe:
            try:
                items = procesar_contacto(c); err = None
            except Exception as e:
                items, err = None, e
            _handle_result(c, items, err)
    else:
        # Camino paralelo. Cada worker es I/O bound (llamada HTTP a GHL);
        # threads bastan (no hace falta multiprocessing).
        out(f"Modo paralelo: {args.threads} threads")
        def worker(c):
            try:
                return c, procesar_contacto(c), None
            except Exception as e:
                return c, None, e
        with ThreadPoolExecutor(max_workers=args.threads) as exe:
            futures = [exe.submit(worker, c) for c in universe]
            for fut in as_completed(futures):
                c, items, err = fut.result()
                with lock:
                    _handle_result(c, items, err)

    merged = merge_pagos(existing, new_items, touched_cids)
    save_pagos(merged)

    out("")
    out(f"══════════ RESUMEN ══════════")
    for k, v in stats.items(): out(f"  {k:<12}: {v}")
    out(f"  pagos nuevos/actualizados: {len(new_items)}")
    out(f"  pagos totales en {OUT_PAGOS}: {len(merged)}")
    # Distribución rápida
    from collections import Counter
    tipos = Counter(x["tipo"] for x in merged)
    out(f"  distribución tipo: {dict(tipos)}")
    total_bruto = sum(x["bruto_usd"] for x in merged)
    total_neto = sum(x["neto_usd"] for x in merged)
    out(f"  totales: bruto ${total_bruto:.2f} · neto ${total_neto:.2f}")


def merge_pagos(existing, nuevos, touched_cids):
    """Combina: mantiene todos los pagos de contactos NO tocados en esta corrida
    + reemplaza completamente los pagos de los contactos TOCADOS con los nuevos.
    Esto asegura que si una nota fue borrada de GHL, también sale del JSON."""
    kept = [p for p in existing if p.get("contact_id") not in touched_cids]
    return kept + nuevos


if __name__ == "__main__":
    main()
