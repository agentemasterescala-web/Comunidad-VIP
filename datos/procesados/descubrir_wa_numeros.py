#!/usr/bin/env python3
"""Descubre todos los números WhatsApp del negocio recorriendo conversations
de contactos con actividad reciente. Loguea a stdout el progreso y al final
imprime la lista deduplicada con conteo + una muestra de mensaje por cada uno.
"""
import os, json, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
for line in open(os.path.join(_HERE, ".env")):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))
TOK = os.environ["GHL_TOKEN"]; LOC = os.environ["GHL_LOCATION"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128.0.0.0"
HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 24*90

def api(url, retries=3):
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {TOK}", "Version": "2021-04-15",
            "Accept": "application/json", "User-Agent": UA,
        })
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {"_error": str(e)[:150]}
    return {}

dump = json.load(open(os.path.join(_HERE, "ghl_contacts_raw.json")))
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=HOURS)
def parse(s):
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except: return None
universe = [c for c in dump if c.get("phone") and parse(c.get("dateUpdated") or "") and parse(c["dateUpdated"]) >= cutoff]
print(f"Contactos con phone activos en {HOURS}h: {len(universe)}")

biz_counter = Counter()
biz_sample = {}  # número → mensaje ejemplo (para que el usuario lo reconozca)
for i, c in enumerate(universe, 1):
    r = api(f"https://services.leadconnectorhq.com/conversations/search?locationId={LOC}&contactId={c['id']}")
    convs = r.get("conversations", []) if isinstance(r, dict) else []
    for conv in convs:
        if conv.get("lastMessageType") != "TYPE_WHATSAPP": continue
        m = api(f"https://services.leadconnectorhq.com/conversations/{conv['id']}/messages?limit=20")
        msgs = m.get("messages", {}).get("messages", []) if isinstance(m, dict) else []
        for msg in msgs:
            if msg.get("messageType") != "TYPE_WHATSAPP": continue
            biz = (msg.get("from") if msg.get("direction") == "outbound" else msg.get("to")) or ""
            biz = biz.replace(" ", "")
            if not biz.startswith("+"): continue
            biz_counter[biz] += 1
            if biz not in biz_sample:
                body = (msg.get("body") or "")[:120]
                biz_sample[biz] = {"dir": msg.get("direction"), "body": body, "date": msg.get("dateAdded","")[:16]}
    if i % 100 == 0:
        print(f"  {i}/{len(universe)} contactos · {len(biz_counter)} números negocio hallados")
        sys.stdout.flush()

print(f"\n═══════════ RESULTADOS ═══════════")
print(f"Contactos escaneados: {len(universe)}")
print(f"Números del negocio detectados: {len(biz_counter)}\n")
for num, cnt in biz_counter.most_common():
    tail4 = num[-4:]
    s = biz_sample.get(num, {})
    print(f"  {num:<18} · tag propuesto: wa-{tail4} · {cnt:>5} mensajes")
    print(f"     ejemplo ({s.get('dir')} {s.get('date')}): {s.get('body','')[:100]!r}")
    print()
