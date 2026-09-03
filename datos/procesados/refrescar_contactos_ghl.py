#!/usr/bin/env python3
"""Refresca ghl_contacts_raw.json paginando todos los contactos de GHL."""
import os, sys, json, time, urllib.request, urllib.error

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(_HERE, ".env")
if os.path.isfile(_ENV):
    for line in open(_ENV):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

TOK = os.environ.get("GHL_TOKEN")
LOC = os.environ.get("GHL_LOCATION")
if not TOK or not LOC:
    sys.exit("Faltan GHL_TOKEN y/o GHL_LOCATION (env o .env)")

def http_get(url, retries=7):
    """GET con retry exponencial. Para 429 respeta Retry-After si viene.
    Backoff hasta 2^6=64s → total worst-case ~2 min por request."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {TOK}",
                "Version": "2021-07-28",
                "Accept": "application/json",
                "User-Agent": "ProyectoClaude/1.0",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 502, 503, 504):
                # Respeta Retry-After si viene; si no, backoff exponencial
                ra = e.headers.get("Retry-After") if e.headers else None
                try:
                    wait = float(ra) if ra else min(2 ** attempt, 64)
                except (TypeError, ValueError):
                    wait = min(2 ** attempt, 64)
                print(f"  {e.code} · reintento {attempt+1}/{retries} en {wait:.0f}s", file=sys.stderr)
                time.sleep(wait); continue
            raise
        except Exception as e:
            last = e; time.sleep(min(2 ** attempt, 64))
    raise last

def main():
    out = os.path.join(_HERE, "ghl_contacts_raw.json")
    marker = os.path.join(_HERE, ".refrescar_last_attempt")
    # Guard de frescura: NO re-bajar los ~116k contactos (~1.165 llamadas) si se
    # INTENTÓ hace < CONTACTS_MAX_AGE_SEC (30 min por defecto). Se cuenta desde el
    # INTENTO (marcador), no desde el éxito: así, si GHL 429-ea a media descarga y
    # refrescar falla, NO se re-baja todo cada 90s (ese ciclo vicioso —re-bajar
    # desde cero sin completar nunca— drenaba la cuota diaria de GHL, 200k).
    # `--force` (o CONTACTS_MAX_AGE_SEC=0) lo ignora para un refresh manual.
    max_age = int(os.environ.get("CONTACTS_MAX_AGE_SEC", "1800"))
    ref = marker if os.path.exists(marker) else (out if os.path.exists(out) else None)
    if ("--force" not in sys.argv and max_age > 0 and ref
            and (time.time() - os.path.getmtime(ref)) < max_age):
        edad = int((time.time() - os.path.getmtime(ref)) / 60)
        print(f"↷ refresco reciente ({edad} min < {max_age // 60} min); no se re-baja "
              f"(usa --force para forzar).")
        return
    # Marca el intento AHORA (antes de descargar): el guard cuenta desde aquí,
    # aunque la descarga falle. Rompe el ciclo de reintentos cada 90s.
    try:
        open(marker, "w").close()
    except OSError:
        pass
    contacts = []
    url = f"https://services.leadconnectorhq.com/contacts/?locationId={LOC}&limit=100"
    page = 1
    while url:
        d = http_get(url)
        batch = d.get("contacts", [])
        contacts.extend(batch)
        meta = d.get("meta", {})
        total = meta.get("total")
        print(f"page {page} ... got {len(batch)} (acc {len(contacts)}/{total})")
        url = meta.get("nextPageUrl")
        page += 1
        # 0.4s entre páginas → 2.5 req/s bien dentro del límite (10 req/s de GHL)
        # y deja margen para las otras rutinas escalonadas.
        time.sleep(0.4)
    out = os.path.join(_HERE, "ghl_contacts_raw.json")
    with open(out, "w") as fp:
        json.dump(contacts, fp, ensure_ascii=False)
    print(f"✓ {len(contacts)} contactos guardados en {out}")

if __name__ == "__main__":
    main()
