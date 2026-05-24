#!/usr/bin/env python3
"""
cargar_vip_sin_form.py
═══════════════════════════════════════════════════════════════════════
Carga/actualiza contactos en GHL a partir del maestro de Dropi, con la
etiqueta "VIP SIN FORM" + etiqueta de nivel, y los campos VIP de ventas.

Reglas (definidas con el usuario):
  • CREAR  → emails de Dropi que NO existen en GHL (ni por email ni por teléfono).
  • UPDATE → contactos GHL que aparecen en Dropi (su email principal o de tienda
             está en el maestro).
  • SKIP   → contactos con tag 'comunidad vip new' (NO se tocan, quedan igual).
  • Etiquetas que se agregan: 'VIP SIN FORM' + etiqueta de nivel (vip oro, etc.)
  • Campos VIP: escalafón, pedidos (suma top-3), ventas mensuales, mes, historial.
  • Si un email de Dropi no tiene nombre → se usa el email como nombre principal.
  • Dedup: por email (exacto, principal + tiendas) y por teléfono (sufijo 10 díg.).

SEGURIDAD:
  • Por DEFECTO corre en DRY-RUN (no escribe nada). Genera un reporte + CSV.
  • Para escribir en vivo hay que pasar --live (y opcional --limit N para probar).

Uso:
  python3 cargar_vip_sin_form.py                 # DRY-RUN (default), escribe CSV
  python3 cargar_vip_sin_form.py --live --limit 20   # vivo, solo 20 (prueba)
  python3 cargar_vip_sin_form.py --live          # vivo, TODOS
"""
import os, json, sys, time, re, csv, argparse, urllib.request, urllib.error
from collections import defaultdict
import openpyxl
# Reutiliza el normalizador de nombres del generador de dashboard
# ('FABIANjimenez' -> 'Fabian Jimenez'; devuelve '' para basura como '#N/A').
from generar_dashboard import normalizar_nombre_dropi

# ── .env ────────────────────────────────────────────────────────────
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
    sys.exit("Faltan GHL_TOKEN y/o GHL_LOCATION (env o .env)")

RAW = os.path.join(_HERE, "ghl_contacts_raw.json")
MAESTRO = os.path.join(_HERE, "maestro_emails.xlsx")
VIP_TAG = "comunidad vip new"
NEW_TAG = "VIP SIN FORM"

# ── IDs de campos (idénticos a escribir_a_ghl.py) ───────────────────
TIENDA_EMAIL_IDS = {
    "Tienda 1":"CQk3UpeEwUnbegiqR2Q3","Tienda 2":"P3jZOcralEFKIg4XpYho",
    "Tienda 3":"p7TjCy0lVm6fP9xEbS3l","Tienda 4":"CZSUn21ycO4tr4LkNrbj",
    "Tienda 5":"Mir5XAqxPoCrfT3fkgRF","Tienda 6":"riVtpCpiQPJvASPdEkKd",
    "Tienda 7":"ThOpku1erpbHGCCBei6Z","Tienda 8":"83RmxTxcA8gkkWUsADls",
    "Tienda 9":"2bl6kY6oQEIbPRRKpmaq","Tienda 10":"75tlJ2SQeSdymOTxoScY",
}
TIENDA_PAIS_IDS = {
    "Tienda 1":"0HWT1wbaaadgxxBPODUH","Tienda 2":"yJyX6eZUzkgnpBmAslde",
    "Tienda 3":"IsI0hZEBHczVZ0itmPmV","Tienda 4":"CqZvpz0gtfu4bvCZwNqA",
    "Tienda 5":"yWAvExtJrOJXTdjDnQuj","Tienda 6":"u7iiKtYTqJSKiFpioMdv",
    "Tienda 7":"28jQePKJQGIZ198U0R6Z","Tienda 8":"gCaIQVieS9PqEU5AI8Uh",
    "Tienda 9":"pEkrMm5ahV6PPow8PYQW","Tienda 10":"cnShQcBSUMbU1WAFVqQx",
}
F = {
    "escalafon_vip":     "evyetA9K7plkYMDd3tCQ",
    "pedidos_vip":       "YAVJHSdLoFnTKbUxUtLK",
    "mes_escalafon":     "tXNrCxLvidhkNyK85T4T",
    "cantidad_ult_mes":  "XIoj5twBfJzJ6irOxraV",
    "ventas_ult_1":      "bgQhOLdDMJUmcxUgXv89",
    "ventas_ult_2":      "OUH451COVuZeMl6BD3lo",
    "ventas_ult_3":      "ogVSepUDzQxqzv6U3ACw",
    "historial":         "SbrJjfBouQa52aSuH64P",
}
TIER_TAG = {
    "Bronce":"vip bronce","Plata":"vip plata","Oro":"vip oro",
    "Platino":"vip platino","Diamante":"vip diamante","Sin clasificar":"vip sin clasificar",
}
TIER_FIELD_VALUE = {
    "Bronce":"Bronce","Plata":"Plata","Oro":"Oro","Platino":"Platino",
    "Diamante":"Diamante","Sin clasificar":"Sin Nivel",
}
ES_MONTH_SHORT = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

# Códigos país para construir E.164 al crear
COUNTRY_CC = {
    "COLOMBIA":"57","ECUADOR":"593","PERU":"51","MEXICO":"52","ARGENTINA":"54",
    "CHILE":"56","GUATEMALA":"502","PANAMA":"507","PARAGUAY":"595",
    "COSTARICA":"506","COSTA RICA":"506","ESPAÑA":"34","ESPANA":"34",
}

# ── HTTP ─────────────────────────────────────────────────────────────
class GHLError(RuntimeError):
    def __init__(self, code, body, msg):
        super().__init__(msg)
        self.code = code
        self.body = body          # dict parseado (o {})

def http(method, url, body=None, retries=4):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {TOK}",
                "Version": "2021-07-28",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ProyectoClaude/1.0",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read()
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            err_body = ""
            try: err_body = e.read().decode()
            except: pass
            try: parsed = json.loads(err_body)
            except: parsed = {}
            last = GHLError(e.code, parsed, f"HTTP {e.code} {method} {url}: {err_body}")
            if e.code in (429, 502, 503, 504):
                time.sleep(2 ** attempt); continue
            raise last
        except Exception as e:
            last = e; time.sleep(2 ** attempt)
    raise last

def create_contact(payload):
    return http("POST", "https://services.leadconnectorhq.com/contacts/", payload)
def update_custom_fields(cid, fields_array):
    return http("PUT", f"https://services.leadconnectorhq.com/contacts/{cid}", {"customFields": fields_array})
def add_tags(cid, tags):
    return http("POST", f"https://services.leadconnectorhq.com/contacts/{cid}/tags", {"tags": list(tags)})

# ── Helpers de datos ─────────────────────────────────────────────────
def clean_str(v):
    if v is None: return ""
    s = str(v).strip()
    if s.upper() in ("#N/A","N/A","NAN","NONE","NULL","-",""): return ""
    return s

def clean_phone_digits(raw):
    s = clean_str(raw)
    if not s: return ""
    return re.sub(r"\D", "", s)

def phone_suffix(raw):
    """Sufijo de 10 dígitos para dedup country-agnostic. '' si insuficiente."""
    d = clean_phone_digits(raw)
    return d[-10:] if len(d) >= 8 else ""

def build_e164(raw, pais):
    """Construye E.164 a partir del local + país. '' si no se puede con confianza."""
    d = clean_phone_digits(raw)
    if len(d) < 7: return ""
    cc = COUNTRY_CC.get(clean_str(pais).upper())
    if not cc:
        return "+" + d if len(d) >= 11 else ""   # país desconocido: solo si ya trae código
    local = d.lstrip("0")
    if local.startswith(cc) and len(local) > len(cc) + 6:
        return "+" + local
    return "+" + cc + local

def month_short(yyyy_mm):
    y, m = yyyy_mm.split("-"); return f"{ES_MONTH_SHORT[int(m)-1]}'{y[-2:]}"
def historial_label(nivel):
    return "Sin nivel" if nivel == "Sin clasificar" else nivel

def parse_historial(s):
    if not s: return []
    first = s.split("\n")[0].strip(); out = []
    for p in [x.strip() for x in first.split("|") if x.strip()]:
        if ":" in p:
            mes, niv = p.split(":", 1); out.append((mes.strip(), niv.strip()))
    return out

def update_historial_str(existing, yyyy_mm, nivel):
    new_mes = month_short(yyyy_mm); new_niv = historial_label(nivel)
    entries = parse_historial(existing); seen = set(); dedup = []
    for m, n in entries:
        if m not in seen: seen.add(m); dedup.append((m, n))
    dedup = [(m, n) for (m, n) in dedup if m != new_mes]
    return " | ".join(f"{m}:{n}" for m, n in ([(new_mes, new_niv)] + dedup))

def classify(active, suma_top2, suma_top3):
    if active < 2 or suma_top2 < 60: return "Sin clasificar"
    if active < 3: return "Bronce"
    if suma_top3 >= 15000: return "Diamante"
    if suma_top3 >= 3000:  return "Platino"
    if suma_top3 >= 900:   return "Oro"
    if suma_top3 >= 300:   return "Plata"
    return "Bronce"

# ── Maestro: email -> rows {pais,mes,pedidos} + nombre/tel ──────────
def load_maestro():
    wb = openpyxl.load_workbook(MAESTRO, read_only=True, data_only=True)
    ws = wb["MAESTRO"]; rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]; idx = {n:i for i,n in enumerate(hdr)}
    db = defaultdict(list); meta = {}
    months_set = set()
    for r in rows[1:]:
        em = r[idx["email"]]
        if not em: continue
        em = str(em).strip().lower()
        mes = r[idx["mes"]]; months_set.add(mes)
        db[em].append({"pais": r[idx["pais"]], "mes": mes, "pedidos": r[idx["pedidos"]] or 0})
        if em not in meta:
            meta[em] = {"nombre": clean_str(r[idx["nombre"]]), "telefono": clean_str(r[idx["telefono"]]), "pais": clean_str(r[idx["pais"]])}
        else:
            if not meta[em]["nombre"]:   meta[em]["nombre"]   = clean_str(r[idx["nombre"]])
            if not meta[em]["telefono"]: meta[em]["telefono"] = clean_str(r[idx["telefono"]])
            if not meta[em]["pais"]:     meta[em]["pais"]     = clean_str(r[idx["pais"]])
    months = sorted(months_set)[-5:]
    return db, meta, months

def extract_tiendas(contact):
    cf = {f["id"]: f.get("value") for f in contact.get("customFields", [])}
    seen = {}
    for label, fid in TIENDA_EMAIL_IDS.items():
        em = cf.get(fid)
        if em and isinstance(em, str) and "@" in em:
            el = em.strip().lower()
            if el not in seen:
                seen[el] = {"email": el, "pais": cf.get(TIENDA_PAIS_IDS[label]) or ""}
    return list(seen.values())

def ped_mes_from_emails(emails, maestro, months):
    pm = {m: 0 for m in months}
    for em in emails:
        for mr in maestro.get(em, []):
            if mr["mes"] in pm:
                pm[mr["mes"]] += mr["pedidos"]
    return pm

def calc_nivel(pm, months):
    sv = sorted(pm.values(), reverse=True)
    active = sum(1 for v in pm.values() if v > 0)
    top1 = sv[0] if sv else 0; top2 = sv[1] if len(sv) > 1 else 0; top3 = sv[2] if len(sv) > 2 else 0
    nivel = classify(active, top1 + top2, top1 + top2 + top3)
    return nivel, top1 + top2 + top3, active

def build_vip_fields(pm, nivel, months, existing_hist=""):
    def back(n): return pm[months[-1-n]] if len(months) > n else 0
    suma_top3 = sum(sorted(pm.values(), reverse=True)[:3])
    return [
        {"id": F["escalafon_vip"],    "field_value": TIER_FIELD_VALUE[nivel]},
        {"id": F["pedidos_vip"],      "field_value": suma_top3},
        {"id": F["mes_escalafon"],    "field_value": months[-1]},
        {"id": F["cantidad_ult_mes"], "field_value": back(0)},
        {"id": F["ventas_ult_1"],     "field_value": str(back(1))},
        {"id": F["ventas_ult_2"],     "field_value": str(back(2))},
        {"id": F["ventas_ult_3"],     "field_value": str(back(3))},
        {"id": F["historial"],        "field_value": update_historial_str(existing_hist, months[-1], nivel)},
    ]

# ── Main ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Escribir en GHL (sin esto = dry-run)")
    ap.add_argument("--limit", type=int, default=0, help="Procesar solo N acciones (prueba)")
    ap.add_argument("--sleep", type=float, default=0.25, help="Pausa entre requests (seg)")
    ap.add_argument("--only-dup-tel", action="store_true",
                    help="Solo procesar UPDATE_DUP_TEL (contactos pre-existentes que matchean por teléfono)")
    args = ap.parse_args()
    DRY = not args.live

    print("Cargando GHL dump + maestro...")
    contacts = json.load(open(RAW))
    maestro, meta, months = load_maestro()
    print(f"  {len(contacts)} contactos GHL · {len(maestro)} emails Dropi · ventana {months}")
    print(f"  Modo: {'DRY-RUN (no escribe)' if DRY else 'LIVE (escribe en GHL)'}")

    # Índices GHL
    email_to_contact = {}    # email_lower -> contact
    phone_to_contact = {}    # suffix -> contact
    contact_by_id = {}       # id -> contact (para resolver colisiones de duplicado)
    for c in contacts:
        contact_by_id[c["id"]] = c
        ep = (c.get("email") or "").strip().lower()
        if ep: email_to_contact.setdefault(ep, c)
        for t in extract_tiendas(c):
            email_to_contact.setdefault(t["email"], c)
        suf = phone_suffix(c.get("phone"))
        if suf: phone_to_contact.setdefault(suf, c)

    def is_vip_new(c): return VIP_TAG in [t.lower() for t in (c.get("tags") or [])]

    planes = []   # filas para CSV + ejecución
    handled_emails = set()

    # ── PASS 1: UPDATE contactos GHL que aparecen en Dropi ──────────
    for c in contacts:
        cid = c["id"]
        tiendas = extract_tiendas(c)
        own_emails = [(c.get("email") or "").strip().lower()] + [t["email"] for t in tiendas]
        own_emails = [e for e in own_emails if e]
        en_dropi = any(e in maestro for e in own_emails)
        if not en_dropi:
            continue
        for e in own_emails:
            handled_emails.add(e)
        if is_vip_new(c):
            planes.append({"accion":"SKIP_VIPNEW","cid":cid,"nombre":c.get("contactName") or "","email":c.get("email") or "",
                           "telefono":c.get("phone") or "","pais":"","nivel":"","total":"","tags":""})
            continue
        pm = ped_mes_from_emails([t["email"] for t in tiendas] or own_emails, maestro, months)
        nivel, suma3, active = calc_nivel(pm, months)
        cf_now = {f["id"]: f.get("value") for f in c.get("customFields", [])}
        vip_fields = build_vip_fields(pm, nivel, months, cf_now.get(F["historial"]) or "")
        cur_tags = [t.lower() for t in (c.get("tags") or [])]
        tags_add = [t for t in [NEW_TAG, TIER_TAG[nivel]] if t.lower() not in cur_tags]
        planes.append({"accion":"UPDATE","cid":cid,"nombre":c.get("contactName") or "","email":c.get("email") or "",
                       "telefono":c.get("phone") or "","pais":"","nivel":nivel,"total":suma3,
                       "tags":";".join(tags_add),"_vip_fields":vip_fields,"_tags_add":tags_add})

    # ── PASS 2: CREATE emails Dropi que no están en GHL ─────────────
    for em, rows in maestro.items():
        if em in handled_emails or em in email_to_contact:
            continue
        info = meta.get(em, {})
        suf = phone_suffix(info.get("telefono"))
        # Dedup por teléfono contra GHL
        if suf and suf in phone_to_contact:
            match = phone_to_contact[suf]
            if is_vip_new(match):
                planes.append({"accion":"SKIP_VIPNEW_TEL","cid":match["id"],"nombre":info.get("nombre") or "","email":em,
                               "telefono":info.get("telefono") or "","pais":info.get("pais") or "","nivel":"","total":"","tags":""})
            else:
                # El teléfono coincide con un contacto pre-existente (otro email).
                # Regla del usuario: etiquetar + actualizar campos VIP de ese contacto.
                # No destructivo: los campos VIP solo se escriben si el contacto NO
                # tiene ya un escalafón (para no pisar una clasificación existente).
                pm = ped_mes_from_emails([em], maestro, months)
                nivel, suma3, active = calc_nivel(pm, months)
                cf_now = {f["id"]: f.get("value") for f in match.get("customFields", [])}
                tiene_escalafon = bool(cf_now.get(F["escalafon_vip"]))
                cur_tags = [t.lower() for t in (match.get("tags") or [])]
                tags_add = [t for t in [NEW_TAG, TIER_TAG[nivel]] if t.lower() not in cur_tags]
                vip_fields = build_vip_fields(pm, nivel, months, cf_now.get(F["historial"]) or "")
                planes.append({"accion":"UPDATE_DUP_TEL","cid":match["id"],"nombre":info.get("nombre") or "","email":em,
                               "telefono":info.get("telefono") or "","pais":info.get("pais") or "","nivel":nivel,"total":suma3,
                               "tags":";".join(tags_add),"_vip_fields":vip_fields,"_tags_add":tags_add,
                               "_tiene_escalafon":tiene_escalafon})
            continue
        # CREATE
        pm = ped_mes_from_emails([em], maestro, months)
        nivel, suma3, active = calc_nivel(pm, months)
        # Normaliza el nombre Dropi; si queda vacío (basura/#N/A) → email como nombre
        nombre = normalizar_nombre_dropi(info.get("nombre")) or em
        e164 = build_e164(info.get("telefono"), info.get("pais"))
        payload = {
            "locationId": LOC,
            "name": nombre,
            "email": em,
            "tags": [NEW_TAG, TIER_TAG[nivel]],
            "customFields": build_vip_fields(pm, nivel, months, ""),
        }
        if e164: payload["phone"] = e164
        planes.append({"accion":"CREATE","cid":"","nombre":nombre,"email":em,
                       "telefono":e164 or (info.get("telefono") or ""),"pais":info.get("pais") or "",
                       "nivel":nivel,"total":suma3,"tags":";".join([NEW_TAG, TIER_TAG[nivel]]),"_payload":payload})

    # ── Resumen ─────────────────────────────────────────────────────
    from collections import Counter
    cnt = Counter(p["accion"] for p in planes)
    print("\n══════════ PLAN ══════════")
    for k in ("CREATE","UPDATE","UPDATE_DUP_TEL","SKIP_VIPNEW","SKIP_VIPNEW_TEL"):
        print(f"  {k:18s}: {cnt.get(k,0)}")
    creates_con_tel = sum(1 for p in planes if p["accion"]=="CREATE" and p["telefono"].startswith("+"))
    print(f"  (CREATE con teléfono E.164: {creates_con_tel})")

    # ── CSV auditable ───────────────────────────────────────────────
    csv_path = os.path.join(_HERE, "plan_vip_sin_form.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["accion","cid","nombre","email","telefono","pais","nivel","total_top3","tags_add"])
        for p in planes:
            w.writerow([p["accion"],p["cid"],p["nombre"],p["email"],p["telefono"],p["pais"],p["nivel"],p["total"],p["tags"]])
    print(f"\n📄 CSV del plan: {csv_path}")

    if DRY:
        print("\n⚠ DRY-RUN: no se escribió nada. Revisá el CSV. Para ejecutar: --live")
        return

    # ── Ejecución LIVE ──────────────────────────────────────────────
    acted = 0; errors = 0
    log_path = os.path.join(_HERE, "logs", f"cargar_vip_sin_form_{time.strftime('%Y-%m-%d_%H%M')}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logf = open(log_path, "w", encoding="utf-8")
    def log(m):
        print(m); logf.write(m + "\n"); logf.flush()
    if args.only_dup_tel:
        # Solo los contactos pre-existentes que matchean por teléfono.
        # Dedup por cid: si varios emails Dropi apuntan al mismo contacto, nos
        # quedamos con el de mayor ventas. Etiqueta SIEMPRE; campos VIP solo si
        # el contacto NO tiene escalafón (no pisar clasificaciones existentes).
        by_cid = {}
        for p in planes:
            if p["accion"] != "UPDATE_DUP_TEL": continue
            cur = by_cid.get(p["cid"])
            if cur is None or (int(p["total"]) if str(p["total"]).isdigit() else 0) > (int(cur["total"]) if str(cur["total"]).isdigit() else 0):
                by_cid[p["cid"]] = p
        todo = list(by_cid.values())
        log(f"LIVE --only-dup-tel · {len(todo)} contactos únicos (dedup por cid)" + (f" · limit {args.limit}" if args.limit else ""))
    else:
        # Intercalar CREATE/UPDATE para que --limit pruebe ambos tipos.
        # Los CREATE se ordenan por ventas desc (los con datos VIP primero, más fáciles de verificar).
        creates = sorted([p for p in planes if p["accion"]=="CREATE"],
                         key=lambda p: -(int(p["total"]) if str(p["total"]).isdigit() else 0))
        updates = [p for p in planes if p["accion"]=="UPDATE"]
        import itertools
        todo = [x for pair in itertools.zip_longest(creates, updates) for x in pair if x is not None]
        log(f"LIVE · {len(todo)} acciones (CREATE+UPDATE)" + (f" · limit {args.limit}" if args.limit else ""))
    dup_updated = 0; dup_skipped = 0; tagged_only = 0
    for i, p in enumerate(todo, 1):
        if args.limit and acted >= args.limit: break
        try:
            if p["accion"] == "CREATE":
                try:
                    create_contact(p["_payload"])
                except GHLError as ge:
                    # GHL no permite duplicados: si choca por email/teléfono, devuelve
                    # el contactId existente. Lo convertimos en UPDATE (salvo VIP New).
                    meta_dup = (ge.body or {}).get("meta", {})
                    dup_id = meta_dup.get("contactId")
                    if ge.code == 400 and dup_id:
                        matched = contact_by_id.get(dup_id)
                        if matched is not None and is_vip_new(matched):
                            dup_skipped += 1
                            log(f"  ⊝ dup→VIPNew, protegido: {p['email']} (cid {dup_id})")
                        else:
                            update_custom_fields(dup_id, p["_payload"]["customFields"])
                            add_tags(dup_id, p["_payload"]["tags"])
                            dup_updated += 1
                            log(f"  ↻ dup→UPDATE: {p['email']} → cid {dup_id} ({meta_dup.get('matchingField')})")
                        time.sleep(args.sleep)
                        continue
                    raise
            elif p["accion"] == "UPDATE_DUP_TEL":
                # Etiqueta siempre; campos VIP solo si el contacto no tenía escalafón.
                if not p.get("_tiene_escalafon"):
                    update_custom_fields(p["cid"], p["_vip_fields"])
                else:
                    tagged_only += 1
                if p["_tags_add"]:
                    add_tags(p["cid"], p["_tags_add"])
            else:
                update_custom_fields(p["cid"], p["_vip_fields"])
                if p["_tags_add"]:
                    add_tags(p["cid"], p["_tags_add"])
            acted += 1
            if acted % 50 == 0: log(f"  ... {acted} ok")
            time.sleep(args.sleep)
        except Exception as e:
            errors += 1
            log(f"  ❌ {p['accion']} {p['email']}: {e}")
    log(f"\n✅ Hecho · {acted} acciones · dup→update {dup_updated} · dup→skip {dup_skipped} · solo-etiqueta {tagged_only} · {errors} errores · log: {log_path}")
    logf.close()

if __name__ == "__main__":
    main()
