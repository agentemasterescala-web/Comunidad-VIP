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

def http_get(url, retries=4):
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
                time.sleep(2 ** attempt); continue
            raise
        except Exception as e:
            last = e; time.sleep(2 ** attempt)
    raise last

def main():
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
        time.sleep(0.15)
    out = os.path.join(_HERE, "ghl_contacts_raw.json")
    with open(out, "w") as fp:
        json.dump(contacts, fp, ensure_ascii=False)
    print(f"✓ {len(contacts)} contactos guardados en {out}")

if __name__ == "__main__":
    main()
