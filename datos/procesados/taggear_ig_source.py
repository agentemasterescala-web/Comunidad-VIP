#!/usr/bin/env python3
"""
taggear_ig_source.py
═══════════════════════════════════════════════════════════════════════
Detecta la cuenta de Instagram desde la que un contacto escribió y le
agrega el tag correspondiente. Se basa en meta.ig.pageId de sus mensajes.

Mapeo:
  · pageId 17841401623994096 · "Iván Caicedo"    → tag 'ig-ivan-caicedo'
  · pageId 17841429658695623 · "Escala Academy"  → tag 'ig-escala-academy'

Idempotente y no destructivo:
  · Si el contacto ya tiene el tag → no hace nada.
  · NUNCA quita tags. Si un contacto tiene ambos ig-* (raro, requiere match por
    email/tel entre las dos IGs), se respetan los dos.

Modos:
  DRY-RUN (default) · loguea qué haría, no toca GHL.
  --live            · aplica los cambios (POST /contacts/{cid}/tags).
  --backfill        · barrido inicial: itera todas las conversations IG del
                      location, dedup por contactId, procesa cada uno.
  (sin --backfill)  · procesa solo contactos con dateUpdated < 2h en el dump
                      local (ghl_contacts_raw.json). Modo apto para launchd
                      cada 10 min.
  --contact CID     · procesa un contacto puntual (útil para pruebas).
  --limit N         · corta el procesamiento a N contactos.
"""
import os, sys, json, time, argparse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

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

# Mapeo pageId → tag. Los pageIds vienen de meta.ig.pageId en los mensajes.
IG_TAGS = {
    "17841401623994096": "ig-ivan-caicedo",     # Iván Caicedo
    "17841429658695623": "ig-escala-academy",   # Escala Academy
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

def http(method, url, body=None, retries=4):
    data = None if body is None else json.dumps(body).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {TOK}",
            "Version": "2021-04-15",
            "Accept": "application/json",
            "Content-Type": "application/json",
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
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {code}: {body_err}")
        except urllib.error.URLError as e:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Reintentos agotados: {method} {url}")

def get_conversations(cid):
    r = http("GET", f"https://services.leadconnectorhq.com/conversations/search?locationId={LOC}&contactId={cid}")
    return r.get("conversations", []) if isinstance(r, dict) else []

def get_messages(conv_id, limit=25):
    r = http("GET", f"https://services.leadconnectorhq.com/conversations/{conv_id}/messages?limit={limit}")
    return r.get("messages", {}).get("messages", []) if isinstance(r, dict) else []

def add_tags(cid, tags):
    return http("POST", f"https://services.leadconnectorhq.com/contacts/{cid}/tags", {"tags": list(tags)})

def detect_ig_pageids_of_contact(cid):
    """Devuelve el set de pageIds IG encontrados en las conversaciones del contacto."""
    ids = set()
    convs = get_conversations(cid)
    for conv in convs:
        # Filtro rápido: descartar si no hay indicio de IG
        lmt = conv.get("lastMessageType") or ""
        typ = conv.get("type") or ""
        if "INSTAGRAM" not in lmt and "IG" not in lmt.upper() and typ != "TYPE_PHONE":
            # TYPE_PHONE puede contener IG también según ejemplo real; no descartamos por type.
            continue
        msgs = get_messages(conv["id"], limit=25)
        for m in msgs:
            if m.get("messageType") != "TYPE_INSTAGRAM": continue
            meta = m.get("meta") or {}
            ig = meta.get("ig") or {}
            pid = ig.get("pageId")
            if pid: ids.add(str(pid))
    return ids

def needed_tags_for_contact(contact_tags, page_ids):
    """Tags IG que HAY que agregar (que corresponden a page_ids y no están ya)."""
    current = set(contact_tags or [])
    want = {IG_TAGS[pid] for pid in page_ids if pid in IG_TAGS}
    return want - current

def process_contact(c, live, log):
    cid = c["id"]
    nombre = c.get("contactName") or c.get("firstName") or "(sin nombre)"
    page_ids = detect_ig_pageids_of_contact(cid)
    if not page_ids:
        return "no-ig"  # sin conversación IG
    unknown = [p for p in page_ids if p not in IG_TAGS]
    if unknown:
        log.write(f"  ⚠ pageIds desconocidos en {cid}: {unknown}\n")
    to_add = needed_tags_for_contact(c.get("tags") or [], page_ids)
    if not to_add:
        return "already-tagged"
    log.write(f"  {'✓' if live else '·'} {cid} · {nombre[:30]:<30} · add tags: {sorted(to_add)}\n")
    if live:
        try:
            add_tags(cid, to_add)
            time.sleep(0.15)  # rate limit soft
            return "tagged"
        except Exception as e:
            log.write(f"     ✗ error: {e}\n")
            return "error"
    return "would-tag"

def load_local_dump():
    if not os.path.isfile(RAW):
        print(f"ERROR: falta {RAW}. Corre refrescar_contactos_ghl.py primero."); sys.exit(1)
    return json.load(open(RAW))

def parse_iso(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: return None

def iter_backfill():
    """Itera TODAS las conversaciones del location, filtrando IG, y devuelve contactIds únicos."""
    seen = set()
    start_after = None
    page = 0
    while True:
        page += 1
        url = f"https://services.leadconnectorhq.com/conversations/search?locationId={LOC}&sortBy=last_message_date&limit=100"
        if start_after:
            url += f"&startAfterDate={start_after}"
        r = http("GET", url)
        convs = r.get("conversations", []) if isinstance(r, dict) else []
        if not convs: break
        for conv in convs:
            lmt = conv.get("lastMessageType") or ""
            if "INSTAGRAM" not in lmt.upper(): continue
            cid = conv.get("contactId")
            if cid: seen.add(cid)
        last_date = convs[-1].get("lastMessageDate") or convs[-1].get("dateUpdated")
        if not last_date or last_date == start_after: break
        start_after = last_date
        print(f"  backfill: página {page} · convs vistas hasta ahora, {len(seen)} contactos IG únicos")
        if len(convs) < 100: break
    return seen

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Aplica cambios (por defecto dry-run)")
    ap.add_argument("--backfill", action="store_true", help="Procesa todos los contactos con conv IG (itera conversations globalmente)")
    ap.add_argument("--ig-candidates", action="store_true", help="Backfill eficiente: procesa contactos sin email/phone (típicos IG-only)")
    ap.add_argument("--contact", help="CID puntual")
    ap.add_argument("--hours", type=int, default=2, help="Ventana para modo periódico (default 2h)")
    ap.add_argument("--limit", type=int, default=0, help="Corta a N contactos (0=sin límite)")
    args = ap.parse_args()

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"taggear_ig_{datetime.now().strftime('%Y-%m-%d_%H%M')}.log")
    log = open(log_path, "w")
    def out(s): print(s); log.write(s + "\n"); log.flush()

    out(f"═══ taggear_ig_source · {'LIVE' if args.live else 'DRY-RUN'} · log: {log_path}")

    # Elegir universo de contactos
    if args.contact:
        # Modo puntual: no requiere dump local; llama API para verificar
        dump = load_local_dump() if os.path.isfile(RAW) else []
        target = next((c for c in dump if c.get("id") == args.contact), {"id": args.contact, "contactName": "(no-en-dump)", "tags": []})
        universe = [target]
    elif args.ig_candidates:
        dump = load_local_dump()
        universe = [c for c in dump
                    if not (c.get("email") or "").strip()
                    and not (c.get("phone") or "").strip()]
        out(f"Candidatos IG-only (sin email + sin phone): {len(universe)}")
    elif args.backfill:
        out("Backfill: barriendo conversations IG del location...")
        cids = iter_backfill()
        out(f"  {len(cids)} contactIds únicos con conv IG")
        dump = load_local_dump()
        by_id = {c["id"]: c for c in dump}
        universe = [by_id.get(cid, {"id": cid, "contactName": "(no-en-dump)", "tags": []}) for cid in cids]
    else:
        # Modo periódico: contactos con dateUpdated < N horas
        dump = load_local_dump()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        universe = []
        for c in dump:
            du = parse_iso(c.get("dateUpdated"))
            if du and du >= cutoff:
                universe.append(c)
        out(f"Contactos actualizados en las últimas {args.hours}h: {len(universe)}")

    if args.limit and len(universe) > args.limit:
        out(f"Limitado a {args.limit} contactos (de {len(universe)})")
        universe = universe[:args.limit]

    stats = {"no-ig": 0, "already-tagged": 0, "would-tag": 0, "tagged": 0, "error": 0}
    for i, c in enumerate(universe, 1):
        res = process_contact(c, args.live, log)
        stats[res] += 1
        if i % 25 == 0:
            out(f"  · procesados {i}/{len(universe)} · {stats}")

    out("")
    out(f"══════════ RESUMEN ══════════")
    for k, v in stats.items():
        out(f"  {k:<16}: {v}")
    if not args.live and (stats["would-tag"] > 0):
        out(f"\n⚠ DRY-RUN. Para aplicar los {stats['would-tag']} tags: agrega --live")

if __name__ == "__main__":
    main()
