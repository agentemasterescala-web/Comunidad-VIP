#!/usr/bin/env python3
"""
taggear_wa_source.py
═══════════════════════════════════════════════════════════════════════
Detecta desde qué número de WhatsApp del negocio escribió cada contacto
(GHL puede tener varios WA conectados) y le agrega un tag `wa-<últimos-4-dígitos>`.

Ejemplo: mensajes con el número del negocio '+573017982739' generan el tag
'wa-2739'.

Idempotente y no destructivo:
  · Si el contacto ya tiene el tag → no hace nada.
  · NUNCA quita tags. Un contacto puede tener varios wa-* si escribió por más
    de un número del negocio (raro pero posible).

Modos:
  DRY-RUN (default) · loguea qué haría, no toca GHL.
  --live            · aplica los cambios (POST /contacts/{cid}/tags).
  --wa-candidates   · backfill eficiente: procesa contactos con phone en el
                      dump local (ghl_contacts_raw.json). Usado en el barrido
                      inicial.
  (sin --wa-candidates) · procesa solo contactos con dateUpdated < N horas
                      (default 2h) → apto para launchd cada 10 min.
  --contact CID     · procesa un contacto puntual (útil para pruebas).
  --limit N         · corta el procesamiento a N contactos.
  --hours N         · ventana para modo periódico (default 2).
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
                time.sleep(2 ** attempt); continue
            raise RuntimeError(f"HTTP {code}: {body_err}")
        except urllib.error.URLError:
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

def tag_for_number(num):
    """Convierte '+573017982739' → 'wa-2739' (últimos 4 dígitos, sin espacios)."""
    digits = "".join(ch for ch in (num or "") if ch.isdigit())
    if len(digits) < 4: return None
    return f"wa-{digits[-4:]}"

def detect_wa_biz_numbers(cid):
    """Devuelve el set de números-negocio WhatsApp encontrados en las
    conversaciones del contacto."""
    nums = set()
    for conv in get_conversations(cid):
        if conv.get("lastMessageType") != "TYPE_WHATSAPP": continue
        for msg in get_messages(conv["id"], limit=25):
            if msg.get("messageType") != "TYPE_WHATSAPP": continue
            biz = (msg.get("from") if msg.get("direction") == "outbound" else msg.get("to")) or ""
            biz = biz.replace(" ", "")
            if biz.startswith("+"): nums.add(biz)
    return nums

def process_contact(c, live, log):
    cid = c["id"]
    nombre = c.get("contactName") or c.get("firstName") or "(sin nombre)"
    try:
        nums = detect_wa_biz_numbers(cid)
    except Exception as e:
        log.write(f"  ✗ {cid} · error API al leer conversaciones: {e}\n")
        return "error"
    if not nums:
        return "no-wa"
    want_tags = {t for t in (tag_for_number(n) for n in nums) if t}
    current = set(c.get("tags") or [])
    to_add = want_tags - current
    if not to_add:
        return "already-tagged"
    log.write(f"  {'✓' if live else '·'} {cid} · {nombre[:30]:<30} · add tags: {sorted(to_add)}\n")
    if live:
        try:
            add_tags(cid, to_add)
            time.sleep(0.15)
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
    except: return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Aplica cambios (default dry-run)")
    ap.add_argument("--wa-candidates", action="store_true", help="Backfill: procesa contactos con phone")
    ap.add_argument("--contact", help="CID puntual")
    ap.add_argument("--hours", type=int, default=2, help="Ventana modo periódico (default 2h)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0, help="Salta los primeros N contactos (para reanudar)")
    args = ap.parse_args()

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"taggear_wa_{datetime.now().strftime('%Y-%m-%d_%H%M')}.log")
    log = open(log_path, "w")
    def out(s): print(s); log.write(s + "\n"); log.flush()

    out(f"═══ taggear_wa_source · {'LIVE' if args.live else 'DRY-RUN'} · log: {log_path}")

    if args.contact:
        dump = load_local_dump() if os.path.isfile(RAW) else []
        target = next((c for c in dump if c.get("id") == args.contact),
                      {"id": args.contact, "contactName": "(no-en-dump)", "tags": []})
        universe = [target]
    elif args.wa_candidates:
        dump = load_local_dump()
        universe = [c for c in dump if (c.get("phone") or "").strip()]
        out(f"Candidatos con phone: {len(universe)}")
    else:
        dump = load_local_dump()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        universe = [c for c in dump
                    if (c.get("phone") or "").strip()
                    and parse_iso(c.get("dateUpdated") or "")
                    and parse_iso(c["dateUpdated"]) >= cutoff]
        out(f"Contactos con phone actualizados en las últimas {args.hours}h: {len(universe)}")

    if args.skip:
        out(f"Saltando los primeros {args.skip} contactos (de {len(universe)})")
        universe = universe[args.skip:]
    if args.limit and len(universe) > args.limit:
        out(f"Limitado a {args.limit} contactos (de {len(universe)})")
        universe = universe[:args.limit]

    stats = {"no-wa": 0, "already-tagged": 0, "would-tag": 0, "tagged": 0, "error": 0}
    for i, c in enumerate(universe, 1):
        res = process_contact(c, args.live, log)
        stats[res] += 1
        if i % 50 == 0:
            out(f"  · procesados {i}/{len(universe)} · {stats}")

    out("")
    out(f"══════════ RESUMEN ══════════")
    for k, v in stats.items():
        out(f"  {k:<16}: {v}")
    if not args.live and stats["would-tag"] > 0:
        out(f"\n⚠ DRY-RUN. Para aplicar los {stats['would-tag']} tags: agrega --live")

if __name__ == "__main__":
    main()
