#!/usr/bin/env python3
"""
Dashboard del Panel Comunidad VIP — Iván Caicedo.
Layout tipo panel ejecutivo con tabs, charts y métricas en vivo.
"""
import os, json, html
from datetime import datetime
from collections import defaultdict, Counter
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
ORIG = os.path.join(PARENT, "originales")
RAW = os.path.join(HERE, "ghl_contacts_raw.json")
MAESTRO = os.path.join(HERE, "maestro_emails.xlsx")
CLAS = os.path.join(HERE, "clasificacion_usuarios.xlsx")
OUT = os.path.join(HERE, "dashboard.html")

TIENDA_IDS = {
    "CQk3UpeEwUnbegiqR2Q3","P3jZOcralEFKIg4XpYho","p7TjCy0lVm6fP9xEbS3l",
    "CZSUn21ycO4tr4LkNrbj","Mir5XAqxPoCrfT3fkgRF","riVtpCpiQPJvASPdEkKd",
    "ThOpku1erpbHGCCBei6Z","83RmxTxcA8gkkWUsADls","2bl6kY6oQEIbPRRKpmaq",
    "75tlJ2SQeSdymOTxoScY"
}
TIENDA_PAIS_IDS = {
    "CQk3UpeEwUnbegiqR2Q3":"0HWT1wbaaadgxxBPODUH","P3jZOcralEFKIg4XpYho":"yJyX6eZUzkgnpBmAslde",
    "p7TjCy0lVm6fP9xEbS3l":"IsI0hZEBHczVZ0itmPmV","CZSUn21ycO4tr4LkNrbj":"CqZvpz0gtfu4bvCZwNqA",
    "Mir5XAqxPoCrfT3fkgRF":"yWAvExtJrOJXTdjDnQuj","riVtpCpiQPJvASPdEkKd":"u7iiKtYTqJSKiFpioMdv",
    "ThOpku1erpbHGCCBei6Z":"28jQePKJQGIZ198U0R6Z","83RmxTxcA8gkkWUsADls":"gCaIQVieS9PqEU5AI8Uh",
    "2bl6kY6oQEIbPRRKpmaq":"pEkrMm5ahV6PPow8PYQW","75tlJ2SQeSdymOTxoScY":"cnShQcBSUMbU1WAFVqQx",
}
PROG_ID = "TwrGqT8nj3jJmVMUlVFq"
TAG_MASTER = "escala"
TAG_INICIACION = "iniciacion"

TIER_ORDER = ["Diamante","Platino","Oro","Plata","Bronce","Sin clasificar"]

ES_MONTHS_SHORT_FULL = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
def mes_label(yyyy_mm):
    y, m = yyyy_mm.split("-")
    return f"{ES_MONTHS_SHORT_FULL[int(m)-1]} {y}"


# ============================================================
# Normalización de nombres pegados (típico en data Dropi)
# Ej: "nicolasmanrique" -> "Nicolas Manrique"
#     "juanavalentinalopezsanchez" -> "Juana Valentina Lopezsanchez"
# ============================================================
import unicodedata
NOMBRES_HISPANOS = {
    # Masculinos
    "abraham","abrahan","adalberto","adan","adolfo","adrian","agustin","alejandro","alberto","albino",
    "alex","alexander","alexis","alfonso","alfredo","alirio","alvaro","amilcar","anderson","andres",
    "andy","angel","anibal","antonio","arcadio","arcadio","armando","arnaldo","arnulfo","arthur","arturo",
    "augusto","aurelio","axel","baltazar","benjamin","bernardo","bismark","boris","brandon","breiner",
    "brian","bruno","byron","camilo","carlos","cesar","christian","christhian","cipriano","cristian",
    "cristhian","cristobal","cruz","daniel","danny","dario","david","deivis","deivys","deyvis","deyson",
    "diego","diomedes","domingo","duvan","eder","edgar","edinson","eduardo","edwin","efrain","efren",
    "einer","elias","eliecer","elkin","emanuel","emiliano","emilio","enrique","eric","ernesto","esteban",
    "estiven","ever","ezequiel","fabian","fabio","federico","felipe","felix","fermin","fernando",
    "francisco","franklin","franco","fredy","freddy","gabriel","geison","geovanny","geovany","gerardo",
    "german","gerson","gilberto","giovanni","giovani","gonzalo","gregorio","guillermo","gustavo",
    "hamilton","harold","hector","henry","heriberto","hernan","hernando","hilario","homero","horacio",
    "hugo","humberto","ibarra","ignacio","ildefonso","isaac","isaias","ismael","ivan","jacinto","jacobo",
    "jaime","jair","jairo","james","javier","jean","jefferson","jeremy","jeronimo","jesus","jeyder",
    "jeyfer","jhojan","jhon","jhonatan","jhonny","joaquin","joel","johan","johnatan","johnny","jonathan",
    "jordan","jorge","jose","joshua","juan","julian","julio","kenny","kevin","leandro","leider","leiver",
    "leonardo","leonel","leyder","lisandro","lorenzo","luciano","lucas","luis","manuel","marcelo","marco",
    "marcos","mariano","mario","martin","marvin","matheus","mateo","mateus","matias","mauricio","maximo",
    "michael","miguel","milton","misael","moises","nelson","nestor","nicanor","nicolas","noel","octavio",
    "olmer","omar","orlando","oscar","osvaldo","pablo","patricio","paul","pedro","pio","rafael","ramiro",
    "ramon","raul","rene","reinaldo","ricardo","richard","roberto","robinson","rodolfo","rodrigo",
    "rogelio","rolando","ronald","ronaldo","ruben","salomon","samuel","santiago","saul","sebastian",
    "sergio","silvio","simon","steven","stiven","teodoro","tobias","tomas","ubaldo","valentin","vicente",
    "victor","vinicio","vladimir","walter","wilber","wilberto","wilfredo","wilfrido","william","willmar",
    "wilmer","wilmar","wilson","wladimir","yamil","yefferson","yefri","yeison","yender","yesid","yhojan",
    "yhonatan","yoel","yonatan","yonny","yordan",
    # Femeninos
    "adelina","adriana","alba","alejandra","alexandra","alicia","alondra","amalia","amelia","amparo",
    "ana","andrea","anet","angie","angela","angelica","anita","antonia","aracely","araceli","ariana",
    "ariadna","astrid","aura","aurora","azucena","barbara","beatriz","berenice","betty","bianca","blanca",
    "brenda","camila","carla","carmen","carolina","catalina","cecilia","celeste","celia","cesarina",
    "chela","cinthia","claudia","clemencia","constanza","consuelo","cristina","dana","daniela","dayana",
    "delia","diana","dolores","dora","dorothy","edith","elba","eliana","elena","elia","elisa","eliza",
    "elizabeth","elsa","elvira","emilia","emma","enith","erika","esmeralda","esperanza","estefania",
    "estela","ester","esther","estrella","eugenia","eulalia","eva","fabiana","fabiola","fanny","felipa",
    "fernanda","flor","flora","florencia","florinda","francisca","gabriela","gala","geraldine","gladis",
    "gladys","gloria","graciela","greicell","greisy","guadalupe","henny","hilda","ingrid","inocencia",
    "irene","iris","irma","isabel","isabela","ivanna","jackeline","jacqueline","janeth","jennifer",
    "jenny","jessenia","jessica","joana","joanna","johana","johanna","josefa","josefina","juana","judith",
    "julia","juliana","julieta","karen","karina","karla","katherine","katia","kelly","kim","kimberly",
    "laura","leidy","lesly","leticia","lidia","lilia","liliana","lilibeth","lina","linda","lisbeth",
    "lizbeth","lizeth","lorena","lourdes","lucia","lucrecia","ludy","luisa","luz","macarena","magaly",
    "magdalena","maite","manuela","marcela","margarita","maria","mariana","maricela","marilin","marilyn",
    "marina","marisa","marisol","marlene","marta","martha","mary","matilde","mayerlin","mayra","melissa",
    "mercedes","milagros","milena","mildred","mireya","monica","monserrat","nancy","natalia","nayeli",
    "nelida","nelly","nereida","nidia","nieves","noemi","nora","norma","ofelia","olga","olivia","olivia",
    "ondina","pamela","paola","patricia","paula","paulina","paz","perla","piedad","pilar","pricila",
    "priscila","raquel","ramona","rebeca","regina","rita","rocio","rosa","rosalia","rosalina","rosario",
    "rosaura","roxana","rubi","ruth","sandra","sara","sarah","sayda","selena","selenia","senith","shirley",
    "silvia","sofia","soledad","sonia","stefania","stefany","stephania","stephany","susana","tania",
    "tatiana","tere","teresa","trinidad","ursula","valentina","valeria","vanesa","vanessa","vera",
    "veronica","victoria","violeta","viviana","wendy","ximena","yadira","yajaira","yamila","yamile",
    "yamileth","yaneth","yarisbel","yenifer","yenny","yesenia","yesica","yolanda","yorleny","yuli",
    "yulieth","yuliana","yuri","zaida","zaira","zenaida","zoila","zoraida",
}

def _strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# Precomputado: map de forma sin tildes → forma canónica
_NOMBRES_MAP = {_strip_accents(n): n for n in NOMBRES_HISPANOS}
_NOMBRES_SORTED = sorted(_NOMBRES_MAP.keys(), key=lambda x: -len(x))

# Valores basura que mejor mostrar vacíos
_NOMBRE_BASURA = {"#n/a","n/a","na","null","none","-","--","sin nombre","sin_nombre","x","xxx"}

def normalizar_nombre_dropi(s):
    """Si el nombre viene pegado (sin espacios), intenta separar nombre + apellido.
    Maneja tildes y filtra valores basura."""
    if not s:
        return ""
    s = str(s).strip()
    if not s or s.lower() in _NOMBRE_BASURA:
        return ""
    # Si ya tiene espacios → title-case por palabra (preserva tildes)
    if " " in s:
        return " ".join(w.capitalize() for w in s.split() if w)
    s_no_acc = _strip_accents(s.lower())
    s_low = s.lower()
    parts = []                # nombres detectados (con tildes)
    rest = s_low              # cola con tildes
    rest_no_acc = s_no_acc    # cola sin tildes para matching
    while rest_no_acc and len(parts) < 2:
        match_key = None
        for name_key in _NOMBRES_SORTED:
            if rest_no_acc.startswith(name_key):
                match_key = name_key
                break
        if match_key and len(rest_no_acc) - len(match_key) >= 3:
            # tomar la porción de la cola con tildes (misma longitud)
            parts.append(rest[:len(match_key)])
            rest = rest[len(match_key):]
            rest_no_acc = rest_no_acc[len(match_key):]
        else:
            break
    if not parts:
        return s.capitalize()
    out = [p.capitalize() for p in parts]
    if rest:
        out.append(rest.capitalize())
    return " ".join(out)


def load_maestro_window():
    wb = openpyxl.load_workbook(MAESTRO, read_only=True, data_only=True)
    ws = wb["MAESTRO"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]; idx = {n:i for i,n in enumerate(hdr)}
    db = defaultdict(list)
    months_set = set()
    has_nombre = "nombre" in idx
    has_tel = "telefono" in idx
    for r in rows[1:]:
        em = r[idx["email"]]
        if not em: continue
        mes = r[idx["mes"]]; months_set.add(mes)
        db[em].append({
            "pais": r[idx["pais"]], "mes": mes,
            "pedidos": r[idx["pedidos"]] or 0,
            "entregados": r[idx["entregados"]] or 0,
            "devoluciones": r[idx["devoluciones"]] or 0,
            "nombre": (r[idx["nombre"]] if has_nombre else "") or "",
            "telefono": (r[idx["telefono"]] if has_tel else "") or "",
        })
    months = sorted(months_set)[-5:]
    return db, months


def extract_tiendas(contact):
    cf = {f["id"]: f.get("value") for f in contact.get("customFields", [])}
    seen = {}
    for fid in TIENDA_IDS:
        em = cf.get(fid)
        if em and isinstance(em, str) and "@" in em:
            em_low = em.strip().lower()
            if em_low not in seen:
                seen[em_low] = {"email": em_low, "pais": cf.get(TIENDA_PAIS_IDS[fid]) or ""}
    return list(seen.values())


def first_seen_month(maestro, email):
    """Devuelve el mes (YYYY-MM) más antiguo en que aparece este correo en el maestro."""
    rows = maestro.get(email, [])
    if not rows: return ""
    return min(r["mes"] for r in rows if r.get("mes"))


VIP_TAG = "comunidad vip new"

def compute_all():
    all_contacts = json.load(open(RAW))
    # Filtrar SOLO los contactos que tienen el tag "comunidad vip new"
    contacts = [c for c in all_contacts if VIP_TAG in [t.lower() for t in (c.get("tags") or [])]]
    excluidos = len(all_contacts) - len(contacts)
    print(f"Contactos GHL totales: {len(all_contacts)}  ·  Filtrados por '{VIP_TAG}': {len(contacts)}  ·  Excluidos: {excluidos}")
    maestro, months = load_maestro_window()

    # Fuentes
    excels_total = 0
    excels_breakdown = []
    if os.path.isdir(ORIG):
        # Walk recursivo: la fuente puede ser un Drive sincronizado con
        # estructura <Año>/<MesAño>/, no plana. Solo carpetas hoja con .xlsx
        # cuentan, deduplicadas por nombre de carpeta para evitar contar
        # el mismo Mes-Año dos veces si aparece en varias ramas.
        seen_folders = set()
        for dirpath, dirnames, filenames in os.walk(ORIG, followlinks=True):
            dirnames.sort()
            n = len([f for f in filenames if f.endswith(".xlsx") and not f.startswith("~$")])
            if n == 0:
                continue
            sub = os.path.basename(dirpath)
            if sub in seen_folders:
                continue
            seen_folders.add(sub)
            excels_breakdown.append({"carpeta": sub, "n": n}); excels_total += n
    paises_set = set()
    correos_maestro = set()
    pedidos_comunidad_total = 0   # toda la comunidad Dropi (para Fuentes de datos)
    for em, rows in maestro.items():
        correos_maestro.add(em)
        for r in rows:
            if r["pais"]: paises_set.add(r["pais"])
            pedidos_comunidad_total += r["pedidos"]
    paises_lista = sorted(paises_set)

    # Procesar contactos
    LATEST = months[-1]
    PREVIOUS = months[-2] if len(months) > 1 else None
    ACTIVE_RECENT = months[-2:]  # 2 últimos meses

    # Programa formativo derivado de los TAGS, no del custom field.
    # "escala" → Master Escala, "iniciacion" → Iniciación Escala.
    # Posibles: solo Master, solo Iniciación, Ambos, Sin programa.
    PROGRAMA = {}
    sin_programa_ids = []
    for c in contacts:
        tags = [t.lower() for t in (c.get("tags") or [])]
        has_m = TAG_MASTER in tags
        has_i = TAG_INICIACION in tags
        if has_m and has_i: PROGRAMA[c["id"]] = "Ambos"
        elif has_m: PROGRAMA[c["id"]] = "Master Escala"
        elif has_i: PROGRAMA[c["id"]] = "Iniciación Escala"
        else:
            PROGRAMA[c["id"]] = "Sin programa"
            sin_programa_ids.append({
                "contact_id": c["id"],
                "nombre": c.get("contactName") or "",
                "email": (c.get("email") or "").lower(),
                "tags": [t for t in (c.get("tags") or []) if not t.lower().startswith("wa:")],
            })

    users_with_tienda = []
    multipais_count = 0
    activos_2m = 0
    desaparecidos = 0
    recuperados = 0
    pedidos_vip_total = 0   # SOLO pedidos de los VIPs (lo que va en el card)
    for c in contacts:
        tiendas = extract_tiendas(c)
        # Si no hay tiendas registradas, igual incluirlo como "Sin tienda" para que el equipo lo vea.
        sin_tienda = not tiendas
        ped_mes = {m: 0 for m in months}
        ent_mes = {m: 0 for m in months}
        dev_mes = {m: 0 for m in months}
        paises_lista = []   # una entrada por cada tienda (puede repetirse país si tiene varios correos en el mismo país)
        paises_set = set()  # para flag "multi-país" (países únicos)
        for t in tiendas:
            if t["pais"]:
                paises_lista.append(t["pais"])
                paises_set.add(t["pais"])
            for mr in maestro.get(t["email"], []):
                if mr["mes"] in ped_mes:
                    ped_mes[mr["mes"]] += mr["pedidos"]
                    ent_mes[mr["mes"]] += mr["entregados"]
                    dev_mes[mr["mes"]] += mr["devoluciones"]
        pedidos_vip_total += sum(ped_mes.values())
        active = sum(1 for v in ped_mes.values() if v > 0)
        sv = sorted(ped_mes.values(), reverse=True)
        top1 = sv[0]; top2 = sv[1] if len(sv) > 1 else 0; top3 = sv[2] if len(sv) > 2 else 0
        suma_top2 = top1 + top2
        suma_top3 = top1 + top2 + top3
        if active < 2 or suma_top2 < 60:
            nivel = "Sin clasificar"
        elif active < 3:
            nivel = "Bronce"
        elif suma_top3 >= 15000: nivel = "Diamante"
        elif suma_top3 >= 3000:  nivel = "Platino"
        elif suma_top3 >= 900:   nivel = "Oro"
        elif suma_top3 >= 300:   nivel = "Plata"
        else: nivel = "Bronce"

        # alertas
        en_riesgo = (
            len(months) >= 3
            and all(ped_mes[m] == 0 for m in months[-3:])
            and any(ped_mes[m] > 0 for m in months[:-3])
        )
        recientes_count = sum(1 for m in ACTIVE_RECENT if ped_mes[m] > 0)
        if recientes_count > 0:
            activos_2m += 1
        # desaparecido: tenía pedidos en algún mes previo PERO 0 en ACTIVE_RECENT
        if (any(ped_mes[m] > 0 for m in months[:-2]) if len(months) > 2 else False) \
           and all(ped_mes[m] == 0 for m in ACTIVE_RECENT):
            desaparecidos += 1
        # recuperado: 0 en penúltimo mes pero >0 en último
        if PREVIOUS and ped_mes.get(PREVIOUS, 0) == 0 and ped_mes.get(LATEST, 0) > 0:
            recuperados += 1
        if len(paises_set) > 1:
            multipais_count += 1

        total_ped = sum(ped_mes.values())
        total_dev = sum(dev_mes.values())
        pct_dev = (total_dev / total_ped * 100) if total_ped > 0 else 0
        # Alerta tipo (excluyentes en orden de severidad):
        #   "Eliminado"     → últimos 3+ meses en 0 (con actividad previa)
        #   "Riesgo"        → últimos 2 meses en 0 (con actividad previa)
        #   "Desaparecido"  → último mes en 0 (con actividad previa)
        # Y crítica (puede coexistir):
        #   "Crítica"       → % devolución > 50%
        alerta_tipo = None
        # 1. Huérfana: tiene tienda pero NUNCA vendió en toda la ventana
        if not sin_tienda and total_ped == 0:
            alerta_tipo = "Huérfana"
        # 2-4. Eliminado / Riesgo / Desaparecido (requieren actividad previa)
        if alerta_tipo is None and len(months) >= 3:
            last3 = months[-3:]
            if all(ped_mes[m] == 0 for m in last3) and any(ped_mes[m] > 0 for m in months[:-3]):
                alerta_tipo = "Eliminado"
        if alerta_tipo is None and len(months) >= 2:
            last2 = months[-2:]
            if all(ped_mes[m] == 0 for m in last2) and any(ped_mes[m] > 0 for m in months[:-2]):
                alerta_tipo = "Riesgo"
        if alerta_tipo is None and len(months) >= 1:
            if ped_mes[months[-1]] == 0 and any(ped_mes[m] > 0 for m in months[:-1]):
                alerta_tipo = "Desaparecido"
        # 5. Crítica (puede sumarse a las otras, pero solo es etiqueta primaria si no hay otra)
        es_critica = pct_dev > 50 and total_ped > 0
        if alerta_tipo is None and es_critica:
            alerta_tipo = "Crítica"

        # Semáforo: verde=ok, amarillo=desap/crit, naranja=riesgo, rojo=eliminado/sin nivel/sin tienda
        if sin_tienda: semaforo = "rojo"
        elif alerta_tipo == "Eliminado": semaforo = "rojo"
        elif alerta_tipo == "Riesgo": semaforo = "naranja"
        elif alerta_tipo in ("Desaparecido","Crítica"): semaforo = "amarillo"
        elif nivel == "Sin clasificar": semaforo = "gris"
        else: semaforo = "verde"
        users_with_tienda.append({
            "cid": c["id"],
            "nombre": c.get("contactName") or "",
            "email": (c.get("email") or "").lower(),
            "telefono": c.get("phone") or "",
            "n_tiendas": len(tiendas),
            "paises": paises_lista,
            "paises_unicos": sorted(paises_set),
            "tiendas_detalle": [
                {"email": t["email"], "pais": t["pais"], "primera_vez": first_seen_month(maestro, t["email"])}
                for t in tiendas
            ],
            "ped_mes": ped_mes,
            "ent_mes": ent_mes,
            "dev_mes": dev_mes,
            "total_pedidos": total_ped,
            "pct_dev": round(pct_dev, 1),
            "active": active,
            "top1": top1, "top2": top2, "top3": top3,
            "suma_top2": suma_top2,
            "suma_top3": suma_top3,
            "nivel": nivel,
            "programa": PROGRAMA.get(c["id"], "Sin programa"),
            "en_riesgo": en_riesgo,
            "semaforo": semaforo,
            "sin_tienda": sin_tienda,
            "alerta_tipo": alerta_tipo,
            "es_critica": es_critica,
        })

    # Programa formativo (derivado de tags)
    prog_counts = Counter(PROGRAMA.values())
    solo_master = prog_counts.get("Master Escala", 0)
    solo_iniciacion = prog_counts.get("Iniciación Escala", 0)
    ambos = prog_counts.get("Ambos", 0)
    sin_programa = prog_counts.get("Sin programa", 0)

    # Distribución por nivel
    dist = Counter(u["nivel"] for u in users_with_tienda)
    clasificados = sum(dist[t] for t in TIER_ORDER if t != "Sin clasificar")
    nivel_pedidos = defaultdict(int)
    for u in users_with_tienda:
        nivel_pedidos[u["nivel"]] += sum(u["ped_mes"].values())

    # Semáforo (4 categorías, alineadas con los nuevos tipos de alerta)
    verde     = sum(1 for u in users_with_tienda if u["semaforo"] == "verde")
    amarillo  = sum(1 for u in users_with_tienda if u["semaforo"] in ("amarillo","naranja"))
    rojo      = sum(1 for u in users_with_tienda if u["semaforo"] == "rojo")
    sin_activ = sum(1 for u in users_with_tienda if u["semaforo"] == "gris")

    sin_alertas = verde

    # Series para charts mensuales
    pedidos_por_mes = {m: 0 for m in months}
    activos_por_mes = {m: 0 for m in months}
    for u in users_with_tienda:
        for m in months:
            v = u["ped_mes"].get(m, 0)
            pedidos_por_mes[m] += v
            if v > 0:
                activos_por_mes[m] += 1

    # Diagnóstico (del Excel)
    diagnostico = {"huerfanas":[],"duplicados":[],"riesgo":[],"capeados":[]}
    if os.path.isfile(CLAS):
        wb = openpyxl.load_workbook(CLAS, read_only=True, data_only=True)
        if "TIENDAS_NO_ENCONTRADAS" in wb.sheetnames:
            for r in list(wb["TIENDAS_NO_ENCONTRADAS"].iter_rows(values_only=True))[1:]:
                if not r[0]: continue
                diagnostico["huerfanas"].append({"contact_id":r[0],"contact_email":r[1] or "","nombre":r[2] or "",
                                  "label":r[3] or "","tienda_email":r[4] or "","pais":r[5] or ""})
        if "CORREOS_DUPLICADOS_GHL" in wb.sheetnames:
            for r in list(wb["CORREOS_DUPLICADOS_GHL"].iter_rows(values_only=True))[1:]:
                if not r[0]: continue
                diagnostico["duplicados"].append({"contact_id":r[0],"correo":r[3] or "","pais":r[4] or "",
                                                   "nombre":r[2] or ""})
        if "RIESGO_ELIMINACION" in wb.sheetnames:
            for r in list(wb["RIESGO_ELIMINACION"].iter_rows(values_only=True))[1:]:
                if not r[0]: continue
                diagnostico["riesgo"].append({"contact_id":r[0],"nombre":r[1] or "","nivel":r[3] or ""})
        if "CAPEADOS_2_MESES" in wb.sheetnames:
            for r in list(wb["CAPEADOS_2_MESES"].iter_rows(values_only=True))[1:]:
                if not r[0]: continue
                diagnostico["capeados"].append({"contact_id":r[0],"nombre":r[1] or "",
                                                "meses":r[3] or 0,"top3":r[4] or 0,"hubiera_sido":r[5] or ""})

    # Por país
    por_pais = Counter()
    for u in users_with_tienda:
        for p in u["paises"]:
            por_pais[p] += 1

    # ============================================================
    # MÉTRICAS · datasets independientes del VIP
    # No tocan la lógica de niveles ni los stats de VIP.
    # ============================================================

    # Universo total de emails GHL: principal + emails de las 10 tiendas
    ghl_emails_set = set()
    for c in all_contacts:
        em_p = (c.get("email") or "").strip().lower()
        if em_p: ghl_emails_set.add(em_p)
        cf_all = {f["id"]: f.get("value") for f in c.get("customFields", [])}
        for fid in TIENDA_IDS:
            v = cf_all.get(fid)
            if v and isinstance(v, str) and "@" in v:
                ghl_emails_set.add(v.strip().lower())

    # Vista 1: contactos con tag escala/iniciacion que NO tienen "comunidad vip new"
    # Vista 2: clasificación de TODOS los contactos GHL por programa
    met_sin_vip = []
    met_programas = []
    cnt_master = 0
    cnt_iniciacion = 0
    cnt_ambos = 0
    cnt_sin_prog = 0
    for c in all_contacts:
        tags_l = [t.lower() for t in (c.get("tags") or [])]
        has_m = TAG_MASTER in tags_l
        has_i = TAG_INICIACION in tags_l
        has_vip = VIP_TAG in tags_l
        if has_m and has_i:
            prog = "Ambos"; cnt_ambos += 1
        elif has_m:
            prog = "Master Escala"; cnt_master += 1
        elif has_i:
            prog = "Iniciación Escala"; cnt_iniciacion += 1
        else:
            prog = "Sin programa"; cnt_sin_prog += 1
        item = {
            "cid": c["id"],
            "nombre": c.get("contactName") or "",
            "email": (c.get("email") or "").lower(),
            "telefono": c.get("phone") or "",
            "programa": prog,
            "tiene_vip_new": has_vip,
        }
        # Vista 2 incluye TODOS (incluyendo Sin programa para tener conteo completo)
        met_programas.append(item)
        # Vista 1 solo los que tienen programa pero NO tienen VIP new
        if (has_m or has_i) and not has_vip:
            met_sin_vip.append(item)

    # Vista 3: emails Dropi que NO están en GHL
    met_dropi_sin_ghl = []
    for em, rows in maestro.items():
        if not em or em.strip().lower() in ghl_emails_set:
            continue
        em_low = em.strip().lower()
        total_ped = sum(r["pedidos"] for r in rows)
        total_ent = sum(r["entregados"] for r in rows)
        total_dev = sum(r["devoluciones"] for r in rows)
        paises_em = sorted({r["pais"] for r in rows if r.get("pais")})
        meses_activos_em = sorted({r["mes"] for r in rows if r.get("pedidos", 0) > 0})
        nombre_raw = next((r.get("nombre") for r in rows if r.get("nombre")), "") or ""
        nombre_em = normalizar_nombre_dropi(nombre_raw)
        tel_em = next((r.get("telefono") for r in rows if r.get("telefono")), "") or ""
        ped_mes_em = {m: 0 for m in months}
        for r in rows:
            if r["mes"] in ped_mes_em:
                ped_mes_em[r["mes"]] += r["pedidos"]
        met_dropi_sin_ghl.append({
            "email": em_low,
            "nombre": nombre_em,
            "telefono": tel_em,
            "paises": paises_em,
            "total_pedidos": total_ped,
            "total_entregados": total_ent,
            "total_devoluciones": total_dev,
            "n_meses_activos": len(meses_activos_em),
            "tiene_ventas": total_ped > 0,
            "ped_mes": ped_mes_em,
        })
    met_dropi_sin_ghl.sort(key=lambda x: -x["total_pedidos"])

    # Vista 4: duplicados potenciales
    # Detecta tiendas cuyo correo coincide con el email principal de OTRO contacto.
    # Ej: Contacto A tiene email 'diego@gmail.com'.
    #     Contacto B (Diego Adolfo) tiene email principal 'diegoaforero@gmail.com'
    #     y como Tienda 3 'diego@gmail.com'.
    #     -> A y B son posibles duplicados o cuentas compartidas.
    email_to_contact = {}
    for c in all_contacts:
        em_p = (c.get("email") or "").strip().lower()
        if em_p:
            # Si hay varios contactos con el mismo email principal (raro), nos quedamos con el primero
            if em_p not in email_to_contact:
                email_to_contact[em_p] = {
                    "cid": c["id"],
                    "nombre": c.get("contactName") or "",
                    "telefono": c.get("phone") or "",
                }
    met_duplicados = []
    SLOT_LABEL = {fid: f"Tienda {i+1}" for i, fid in enumerate(sorted(TIENDA_IDS))}
    # Mantener orden estable
    TIENDA_IDS_ORDER = list(TIENDA_IDS)
    for c in all_contacts:
        cid = c["id"]
        em_principal = (c.get("email") or "").strip().lower()
        nombre = c.get("contactName") or ""
        telefono = c.get("phone") or ""
        cf_all = {f["id"]: f.get("value") for f in c.get("customFields", [])}
        for i, fid in enumerate(TIENDA_IDS_ORDER):
            v = cf_all.get(fid)
            if not v or not isinstance(v, str) or "@" not in v:
                continue
            t_em = v.strip().lower()
            other = email_to_contact.get(t_em)
            if other and other["cid"] != cid:
                pais = cf_all.get(TIENDA_PAIS_IDS.get(fid, "")) or ""
                met_duplicados.append({
                    "cid": cid,
                    "nombre": nombre,
                    "email_principal": em_principal,
                    "telefono": telefono,
                    "tienda_slot": f"Tienda {i+1}",
                    "tienda_email": t_em,
                    "tienda_pais": pais,
                    "otro_cid": other["cid"],
                    "otro_nombre": other["nombre"],
                    "otro_telefono": other["telefono"],
                })
    # Ordenar por nombre del contacto B (el que tiene la tienda)
    met_duplicados.sort(key=lambda x: (x["nombre"] or "").lower())

    return {
        "meta": {
            "ultimo_mes": LATEST,
            "ultimo_mes_label": mes_label(LATEST),
            "generated": datetime.now().strftime("%d de %B de %Y, %H:%M"),
            "generated_iso": datetime.now().isoformat(),
            "ventana": months,
            "ventana_labels": [mes_label(m) for m in months],
        },
        "fuentes": {
            "excels_total": excels_total,
            "excels_breakdown": excels_breakdown,
            "meses": months,
            "paises": paises_lista,
            "correos_maestro": len(correos_maestro),
            "pedidos_total": pedidos_comunidad_total,
            "contactos_ghl": len(contacts),
            "contactos_con_tienda": sum(1 for u in users_with_tienda if not u["sin_tienda"]),
        },
        "stats": {
            "usuarios_totales": len(contacts),
            "clasificados_vip": clasificados,
            "total_pedidos": pedidos_comunidad_total,
            "total_pedidos_vip": pedidos_vip_total,
            "multi_pais": multipais_count,
            "sin_alertas": sin_alertas,
            "activos_2_meses": activos_2m,
            "desaparecidos": desaparecidos,
            "recuperados": recuperados,
        },
        "programa": {
            "master": solo_master,
            "iniciacion": solo_iniciacion,
            "ambos": ambos,
            "sin_programa": sin_programa,
            "sin_programa_ids": sin_programa_ids,
        },
        "distribucion": {t: {"n": dist.get(t,0), "pedidos": nivel_pedidos.get(t,0)} for t in TIER_ORDER},
        "semaforo": {"verde": verde, "amarillo": amarillo, "rojo": rojo, "sin_actividad": sin_activ},
        "pedidos_por_mes": pedidos_por_mes,
        "activos_por_mes": activos_por_mes,
        "por_pais": dict(sorted(por_pais.items(), key=lambda x:-x[1])),
        "usuarios": users_with_tienda,
        "diagnostico": diagnostico,
        "metricas": {
            "ghl_total": len(all_contacts),
            "ghl_emails_universo": len(ghl_emails_set),
            "dropi_emails_total": len(maestro),
            "master_total": cnt_master,
            "iniciacion_total": cnt_iniciacion,
            "ambos_total": cnt_ambos,
            "sin_programa_total": cnt_sin_prog,
            "sin_vip_total": len(met_sin_vip),
            "dropi_sin_ghl_total": len(met_dropi_sin_ghl),
            "dropi_sin_ghl_con_ventas": sum(1 for x in met_dropi_sin_ghl if x["tiene_ventas"]),
            "dropi_sin_ghl_sin_ventas": sum(1 for x in met_dropi_sin_ghl if not x["tiene_ventas"]),
            "sin_comunidad_vip": met_sin_vip,
            "programas": met_programas,
            "dropi_sin_ghl": met_dropi_sin_ghl,
            "duplicados": met_duplicados,
            "duplicados_total": len(met_duplicados),
            "duplicados_contactos_unicos": len({d["cid"] for d in met_duplicados}),
        },
    }


def render_html(data):
    j = json.dumps(data, ensure_ascii=False, default=str)
    return """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Panel Comunidad VIP — Iván Caicedo</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { background: #06091a; }
  .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
          border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; backdrop-filter: blur(8px); }
  .card:hover { border-color: rgba(255,255,255,0.10); }
  .tab { padding: 8px 14px; font-size: 13px; font-weight: 500; color: #94a3b8; border-bottom: 2px solid transparent; transition: all .15s; }
  .tab:hover { color: #e2e8f0; }
  .tab.active { color: #38bdf8; border-bottom-color: #38bdf8; }
  .cat-btn { padding: 7px 18px; font-size: 13px; font-weight: 600; color: #94a3b8; border-radius: 8px; transition: all .15s;
             background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); }
  .cat-btn:hover { color: #e2e8f0; background: rgba(255,255,255,0.06); }
  .cat-btn.active { color: #ffffff; background: linear-gradient(135deg, rgba(34,211,238,0.25) 0%, rgba(59,130,246,0.25) 100%); border-color: rgba(34,211,238,0.55); box-shadow: 0 0 14px rgba(34,211,238,0.15); }
  @keyframes pulse-warn {
    0%, 100% { box-shadow: 0 0 0 0 rgba(248,113,113,0); }
    50%      { box-shadow: 0 0 0 6px rgba(248,113,113,0.25); }
  }
  .pill { padding: 2px 10px; border-radius: 9999px; font-size: 11px; font-weight: 600; border: 1px solid; display: inline-block; }
  .neon-cyan { color: #22d3ee; }
  .neon-yellow { color: #facc15; }
  .neon-green { color: #4ade80; }
  .neon-pink { color: #f472b6; }
  .neon-red { color: #f87171; }
  .neon-violet { color: #a78bfa; }
  .neon-orange { color: #fb923c; }
  .neon-blue { color: #60a5fa; }
  table { border-collapse: collapse; }
  tr.hover-row:hover { background: rgba(255,255,255,0.02); }
  .scrollable { max-height: 600px; overflow-y: auto; }
  .scrollable::-webkit-scrollbar { width: 8px; }
  .scrollable::-webkit-scrollbar-track { background: transparent; }
  .scrollable::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
</style>
</head>
<body class="text-slate-200 min-h-screen font-sans">

<!-- HEADER -->
<header class="border-b border-white/5 px-6 py-4 flex items-center gap-4">
  <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-cyan-500/30 to-blue-700/30 border border-cyan-500/30 flex items-center justify-center text-xs font-bold">VIP</div>
  <div class="flex-1">
    <h1 class="text-xl font-bold">Panel <span class="neon-cyan">Comunidad VIP</span> — Iván Caicedo</h1>
    <div class="text-xs text-slate-500" id="header-meta"></div>
  </div>
  <button id="btn-refresh" onclick="location.reload()"
          class="cat-btn flex items-center gap-2"
          title="Recargar la página para obtener los datos más recientes">
    🔄 <span>Actualizar</span>
  </button>
</header>

<!-- CATEGORIES -->
<nav class="border-b border-white/5 px-6 py-3 flex flex-wrap gap-2" id="categories"></nav>

<!-- TABS -->
<nav class="border-b border-white/5 px-6 flex flex-wrap gap-1" id="tabs"></nav>

<!-- CONTENT -->
<main class="p-6 max-w-[1600px] mx-auto" id="main-content"></main>

<footer class="text-center text-xs text-slate-700 py-8">
  Generado por <code>generar_dashboard.py</code> · datos en vivo de GHL
</footer>

<!-- MODAL FICHA -->
<div id="ficha-modal" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm overflow-y-auto" onclick="if(event.target===this)cerrarFicha()">
  <div class="max-w-3xl mx-auto my-6 p-4">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-semibold neon-cyan uppercase tracking-wider">Ficha del miembro</h2>
      <button onclick="cerrarFicha()" class="text-slate-400 hover:text-white text-2xl leading-none">×</button>
    </div>
    <div id="ficha-content"></div>
  </div>
</div>

<!-- MODAL ENVÍO DE CORREO -->
<div id="envio-modal" class="hidden fixed inset-0 z-50 bg-black/70 backdrop-blur-sm overflow-y-auto" onclick="if(event.target===this)cerrarModalEnvio()">
  <div class="max-w-3xl mx-auto my-6 p-4">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-semibold neon-cyan uppercase tracking-wider">Envío de correo</h2>
      <button onclick="cerrarModalEnvio()" class="text-slate-400 hover:text-white text-2xl leading-none">×</button>
    </div>
    <div id="envio-content"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
const tierColor = {
  "Diamante":"bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
  "Platino":"bg-violet-500/20 text-violet-300 border-violet-500/40",
  "Oro":"bg-amber-500/20 text-amber-300 border-amber-500/40",
  "Plata":"bg-slate-400/20 text-slate-200 border-slate-400/40",
  "Bronce":"bg-orange-500/20 text-orange-300 border-orange-500/40",
  "Sin clasificar":"bg-slate-700/40 text-slate-500 border-slate-600/40",
};
const TIER_COLORS_HEX = {
  "Diamante":"#22d3ee","Platino":"#a78bfa","Oro":"#facc15","Plata":"#cbd5e1","Bronce":"#fb923c","Sin clasificar":"#475569",
};
const TIER_ORDER = ["Diamante","Platino","Oro","Plata","Bronce","Sin clasificar"];
const fmt = n => (n||0).toLocaleString("es-CO");
function tc(s) {
  if (!s) return s;
  return s.toLowerCase().split(/(\s+)/).map(w => {
    if (!w || !w.trim()) return w;
    return w.charAt(0).toUpperCase() + w.slice(1);
  }).join('');
}

function actualizarFrescura() {
  const gen = new Date(DATA.meta.generated_iso);
  const seg = Math.floor((Date.now() - gen.getTime())/1000);
  let txt;
  if (seg < 60) txt = `hace ${seg}s`;
  else if (seg < 3600) txt = `hace ${Math.floor(seg/60)} min`;
  else txt = `hace ${Math.floor(seg/3600)} h`;
  const color = seg<120?'text-green-400':seg<300?'text-yellow-400':'text-red-400';
  document.getElementById("header-meta").innerHTML =
    `Último mes cargado: <span class="text-cyan-400">${DATA.meta.ultimo_mes_label}</span>  ·  ` +
    `Datos generados <span class="${color}">${txt}</span>` +
    (seg >= 300 ? ` <span class="text-red-400 font-semibold">· conviene actualizar</span>` : '');
  // Resaltar el botón cuando los datos están viejos
  const btn = document.getElementById('btn-refresh');
  if (btn) {
    if (seg >= 300) {
      btn.classList.add('active');
      btn.style.animation = 'pulse-warn 2s ease-in-out infinite';
    } else {
      btn.classList.remove('active');
      btn.style.animation = '';
    }
  }
}
actualizarFrescura();
setInterval(actualizarFrescura, 10000);

const CATEGORIES = [
  {id:"vip",      label:"🏆 VIP"},
  {id:"metricas", label:"📈 Métricas"},
];
const TABS_BY_CAT = {
  "vip": [
    {id:"resumen", label:"📊 Resumen"},
    {id:"clasif",  label:"🏆 Clasificación VIP"},
    {id:"top100",  label:"🔥 Top 100"},
    {id:"alertas", label:"⚠ Alertas"},
    {id:"paises",  label:"🌎 Reportes País"},
    {id:"reglas",  label:"📋 Reglas VIP"},
    {id:"consulta",label:"🔎 Consulta"},
  ],
  "metricas": [
    {id:"met_sin_vip",     label:"👥 No están en Comunidad VIP"},
    {id:"met_programas",   label:"📊 Master vs Iniciación"},
    {id:"met_dropi_ghl",   label:"👻 En Dropi sin GHL"},
    {id:"met_duplicados",  label:"🔁 Posibles duplicados"},
  ],
};
// --- Persistencia de estado (sobrevive al auto-refresh cada 60s) ---
const STATE_KEY = "dashboard_vip_state_v1";
function loadState() {
  try {
    const s = JSON.parse(localStorage.getItem(STATE_KEY) || "{}");
    return s || {};
  } catch(e) { return {}; }
}
function saveState() {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({
      cat: currentCategory,
      tab: currentTab,
      scroll: window.scrollY,
    }));
  } catch(e) {}
}
const _st = loadState();
let currentCategory = (_st.cat && TABS_BY_CAT[_st.cat]) ? _st.cat : "vip";
let _wantedTab = _st.tab || "resumen";
let currentTab = (TABS_BY_CAT[currentCategory].some(t => t.id === _wantedTab))
  ? _wantedTab
  : TABS_BY_CAT[currentCategory][0].id;

function renderCategories() {
  document.getElementById("categories").innerHTML = CATEGORIES.map(c =>
    `<button class="cat-btn ${currentCategory===c.id?'active':''}" data-cat="${c.id}">${c.label}</button>`
  ).join('');
  document.querySelectorAll('[data-cat]').forEach(b => b.onclick = () => {
    currentCategory = b.dataset.cat;
    currentTab = TABS_BY_CAT[currentCategory][0].id;
    saveState();
    renderCategories();
    renderTabs();
    render();
  });
}
function renderTabs() {
  const tabs = TABS_BY_CAT[currentCategory] || [];
  document.getElementById("tabs").innerHTML = tabs.map(t =>
    `<button class="tab ${currentTab===t.id?'active':''}" data-tab="${t.id}">${t.label}</button>`
  ).join('');
  document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
    currentTab = b.dataset.tab;
    saveState();
    renderTabs();
    render();
  });
}
// Guardar el scroll antes de cada refresh (el meta refresh dispara beforeunload)
window.addEventListener('beforeunload', saveState);
// Y restaurarlo después del render inicial
window.addEventListener('load', () => {
  if (_st.scroll) {
    setTimeout(() => window.scrollTo(0, _st.scroll), 50);
  }
});
renderCategories();
renderTabs();
detectarServidor().then(() => {
  // Re-render si estamos en una vista que depende del estado del servidor
  if (currentTab === 'met_sin_vip') render();
});

function statCard(label, n, sub, accentClass) {
  return `<div class="card p-4">
    <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">${label}</div>
    <div class="text-3xl font-bold mt-1 ${accentClass||'text-slate-100'}">${fmt(n)}</div>
    <div class="text-[11px] text-slate-500 mt-1 leading-tight">${sub}</div>
  </div>`;
}

function renderResumen() {
  const s = DATA.stats;
  const p = DATA.programa;
  const ventanaTxt = DATA.meta.ventana_labels.length > 1
    ? `${DATA.meta.ventana_labels[0]} → ${DATA.meta.ventana_labels[DATA.meta.ventana_labels.length-1]}`
    : DATA.meta.ventana_labels[0];
  return `
    <!-- ROW 1 -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      ${statCard("Usuarios totales", s.usuarios_totales, `${fmt(DATA.fuentes.contactos_con_tienda)} con tienda registrada`, "neon-cyan")}
      ${statCard("Clasificados VIP", s.clasificados_vip, "Bronce · Plata · Oro · Platino · Diamante", "neon-yellow")}
      ${statCard("Total pedidos", s.total_pedidos, `Acumulado comunidad completa · ${ventanaTxt}`, "neon-green")}
      ${statCard("Multi-país", s.multi_pais, "Con tiendas en +1 país", "neon-pink")}
      ${statCard("Sin alertas", s.sin_alertas, "Clasificados y no en riesgo", "neon-green")}
      ${statCard("Activos últimos 2 meses", s.activos_2_meses, "Con pedidos recientes", "neon-blue")}
    </div>

    <!-- ROW 2 -->
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
      ${statCard("Desaparecidos", s.desaparecidos, "Activos antes, 0 los últimos 2 meses", "neon-red")}
      ${statCard("Recuperados", s.recuperados, "Estaban inactivos, vendieron en " + DATA.meta.ultimo_mes_label, "neon-violet")}
      ${statCard("En riesgo de salir", DATA.semaforo.amarillo, "3 meses consecutivos sin vender", "neon-orange")}
    </div>

    <!-- PROGRAMA FORMATIVO -->
    <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mt-8 mb-3">Distribución por programa formativo (según tags GHL)</h2>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      ${statCard("Master Escala", p.master, "Solo tag 'escala' (sin 'iniciacion')", "neon-violet")}
      ${statCard("Iniciación Escala", p.iniciacion, "Solo tag 'iniciacion' (sin 'escala')", "neon-pink")}
      ${statCard("Ambos programas", p.ambos, "Tienen ambos tags (escala + iniciacion)", "neon-yellow")}
      ${statCard("Sin programa", p.sin_programa, "VIPs sin tag de Master ni de Iniciación", "neon-red")}
    </div>

    <!-- CHARTS · grid 2x2 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-8">
      <div class="card p-5">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Distribución VIP</h3>
        <canvas id="chart-donut" height="220"></canvas>
      </div>
      <div class="card p-5">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Semáforo general</h3>
        <canvas id="chart-semaforo" height="220"></canvas>
      </div>
      <div class="card p-5">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Evolución pedidos por mes</h3>
        <canvas id="chart-evolucion" height="220"></canvas>
      </div>
      <div class="card p-5">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Actividad en ventana de evaluación</h3>
        <canvas id="chart-actividad" height="220"></canvas>
      </div>
    </div>

    <!-- TABLA DISTRIBUCION -->
    <div class="card p-5 mt-4">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Detalle por nivel</h3>
      <table class="w-full text-sm">
        <thead class="text-[10px] text-slate-500 uppercase tracking-wider">
          <tr><th class="text-left py-2">Nivel</th><th class="text-right">Usuarios</th><th class="text-right">%</th><th class="text-left pl-6">Reparto</th><th class="text-right">Pedidos acumulados</th></tr>
        </thead>
        <tbody>${renderDistRows()}</tbody>
      </table>
    </div>
  `;
}

function renderDistRows() {
  const d = DATA.distribucion;
  const total = Object.values(d).reduce((s,x)=>s+x.n,0);
  const maxN = Math.max(...Object.values(d).map(x=>x.n)) || 1;
  return TIER_ORDER.map(t => {
    const x = d[t];
    const pct = total ? (x.n*100/total).toFixed(1) : 0;
    const bw = (x.n/maxN*100).toFixed(1);
    const c = TIER_COLORS_HEX[t];
    return `<tr class="border-b border-white/5">
      <td class="py-2"><span class="pill ${tierColor[t]}">${t}</span></td>
      <td class="text-right font-mono text-slate-200">${x.n}</td>
      <td class="text-right text-slate-500">${pct}%</td>
      <td class="pl-6 pr-2 w-2/5"><div class="bg-white/5 h-2 rounded-full overflow-hidden"><div class="h-full rounded-full" style="width:${bw}%;background:${c}"></div></div></td>
      <td class="text-right font-mono text-slate-400">${fmt(x.pedidos)}</td>
    </tr>`;
  }).join('');
}

let currentFilter = "Todos", currentSearch = "", currentProg = "Todos", currentCountry = "Todos", currentMultipais = false;

const COUNTRY_FLAG = {
  "Colombia":"🇨🇴","Chile":"🇨🇱","Ecuador":"🇪🇨","México":"🇲🇽","Mexico":"🇲🇽",
  "Argentina":"🇦🇷","Perú":"🇵🇪","Peru":"🇵🇪","Guatemala":"🇬🇹","Panamá":"🇵🇦","Panama":"🇵🇦",
  "Paraguay":"🇵🇾","Costa Rica":"🇨🇷","CostaRica":"🇨🇷","España":"🇪🇸","Espana":"🇪🇸",
  "COLOMBIA":"🇨🇴","CHILE":"🇨🇱","ECUADOR":"🇪🇨","MEXICO":"🇲🇽","ARGENTINA":"🇦🇷",
  "PERU":"🇵🇪","GUATEMALA":"🇬🇹","PANAMA":"🇵🇦","PARAGUAY":"🇵🇾","COSTARICA":"🇨🇷",
};
const flag = p => COUNTRY_FLAG[p] || "🏳";
const semColor = {"verde":"bg-green-400","amarillo":"bg-yellow-400","naranja":"bg-orange-400","rojo":"bg-red-400","gris":"bg-slate-500"};
const semLabel = {"verde":"VERDE","amarillo":"AMARILLO","naranja":"NARANJA","rojo":"ROJO","gris":"SIN ACT."};
const semText  = {"verde":"text-green-400","amarillo":"text-yellow-400","naranja":"text-orange-400","rojo":"text-red-400","gris":"text-slate-500"};
const PROG_ORDER = ["Master Escala","Iniciación Escala","Ambos","Sin programa"];
const PROG_SHORT = {"Master Escala":"Master","Iniciación Escala":"Iniciación","Ambos":"Ambos","Sin programa":"Sin definir"};
const MES_ABBR = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
function mesShort(yyyymm) { const [y,m]=yyyymm.split('-'); return MES_ABBR[+m-1]+' '+y; }

function renderClasificacion(limit) {
  const users = DATA.usuarios;

  // SCOPE = todos los filtros aplicados EXCEPTO el tier (para que los stats por tier sean reactivos)
  let scope = users;
  if (currentProg !== "Todos") scope = scope.filter(u => u.programa === currentProg);
  if (currentCountry !== "Todos") scope = scope.filter(u => (u.paises_unicos||[]).includes(currentCountry));
  if (currentMultipais) scope = scope.filter(u => (u.paises_unicos||[]).length > 1);
  if (currentSearch) {
    const s = currentSearch.toLowerCase();
    scope = scope.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
  }

  const tierCounts = { "Todos": scope.length };
  TIER_ORDER.forEach(t => tierCounts[t] = scope.filter(u=>u.nivel===t).length);

  // counts por programa con todos los filtros excepto programa
  let scopeNoProg = users;
  if (currentCountry !== "Todos") scopeNoProg = scopeNoProg.filter(u => (u.paises_unicos||[]).includes(currentCountry));
  if (currentMultipais) scopeNoProg = scopeNoProg.filter(u => (u.paises_unicos||[]).length > 1);
  if (currentSearch) {
    const s = currentSearch.toLowerCase();
    scopeNoProg = scopeNoProg.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
  }
  const progCounts = { "Todos": scopeNoProg.length };
  PROG_ORDER.forEach(p => progCounts[p] = scopeNoProg.filter(u => u.programa===p).length);

  let filtered = scope;
  if (currentFilter !== "Todos") filtered = filtered.filter(u => u.nivel === currentFilter);
  filtered.sort((a,b)=>b.suma_top3 - a.suma_top3);

  const allCountries = [...new Set(users.flatMap(u => u.paises_unicos||u.paises||[]))].sort();
  const monthCols = DATA.meta.ventana.map(m => `<th class="text-right text-[10px] uppercase tracking-wider">${mesShort(m)}</th>`).join('');

  return `
    <!-- BARRA DE FILTROS -->
    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <input id="search-input" type="text" placeholder="Buscar por nombre o email..."
               class="flex-1 min-w-[260px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
               value="${currentSearch.replace(/"/g,'&quot;')}">
        <select id="country-select" class="bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500">
          <option value="Todos">Todos los países</option>
          ${allCountries.map(p => `<option value="${p}" ${currentCountry===p?'selected':''}>${flag(p)} ${p}</option>`).join('')}
        </select>
        <div class="ml-auto"><span class="pill bg-violet-500/20 text-violet-200 border-violet-500/40">${fmt(scope.length)} usuarios</span></div>
      </div>

      <div class="flex flex-wrap items-center gap-2 mb-2">
        <div class="text-[10px] uppercase tracking-wider text-slate-500 w-20">Nivel:</div>
        ${["Todos",...TIER_ORDER].map(t =>
          `<button data-tier="${t}" class="text-[11px] px-3 py-1.5 rounded-lg font-medium ${currentFilter===t?'bg-cyan-600/30 text-cyan-200 border border-cyan-500/40':'bg-white/5 text-slate-400 border border-white/5 hover:text-slate-200'}">${t==='Sin clasificar'?'Sin nivel':t} <span class="ml-1 text-slate-500">${tierCounts[t]||0}</span></button>`
        ).join('')}
      </div>

      <div class="flex flex-wrap items-center gap-2 mb-2">
        <div class="text-[10px] uppercase tracking-wider text-slate-500 w-20">Programa:</div>
        ${["Todos",...PROG_ORDER].map(p =>
          `<button data-prog="${p}" class="text-[11px] px-3 py-1.5 rounded-lg font-medium ${currentProg===p?'bg-cyan-600/30 text-cyan-200 border border-cyan-500/40':'bg-white/5 text-slate-400 border border-white/5 hover:text-slate-200'}">${p==='Todos'?'Todos':PROG_SHORT[p]} <span class="ml-1 text-slate-500">${progCounts[p]||0}</span></button>`
        ).join('')}
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="text-[10px] uppercase tracking-wider text-slate-500 w-20">Otros:</div>
        <button data-multipais="1" class="text-[11px] px-3 py-1.5 rounded-lg font-medium ${currentMultipais?'bg-cyan-600/30 text-cyan-200 border border-cyan-500/40':'bg-white/5 text-slate-400 border border-white/5 hover:text-slate-200'}">🌎 Multi-País <span class="ml-1 text-slate-500">${users.filter(u=>(u.paises_unicos||[]).length>1).length}</span></button>
      </div>
    </div>

    <!-- 4 STAT CARDS por tier -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
      ${["Diamante","Platino","Oro","Plata","Bronce"].map(t => `
        <div class="card p-4">
          <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">${t}</div>
          <div class="text-3xl font-bold mt-1" style="color:${TIER_COLORS_HEX[t]}">${fmt(tierCounts[t]||0)}</div>
        </div>`).join('')}
    </div>

    <!-- TABLA -->
    <div class="card p-4">
      <div class="text-xs text-slate-500 mb-2">Mostrando ${filtered.length} de ${users.length} VIPs</div>
      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2">Nombre</th>
              <th class="text-left">Teléfono</th>
              <th class="text-center">Nivel</th>
              <th class="text-center">Programa</th>
              <th class="text-left">Países</th>
              ${monthCols}
              <th class="text-right">Total</th>
              <th class="text-right">% Dev.</th>
              <th class="text-center">Semáforo</th>
            </tr>
          </thead>
          <tbody>
            ${filtered.slice(0,500).map(u => `
              <tr class="hover-row border-b border-white/5 cursor-pointer" data-cid="${u.cid}">
                <td class="py-2"><span class="text-cyan-300 font-medium hover:underline">${tc(u.nombre)||'—'}</span></td>
                <td class="text-slate-400 font-mono">${u.telefono||'—'}</td>
                <td class="text-center"><span class="pill ${tierColor[u.nivel]}">${u.nivel==='Sin clasificar'?'Sin nivel':u.nivel}</span></td>
                <td class="text-center"><span class="pill bg-white/5 border-white/10 text-slate-300">${PROG_SHORT[u.programa]||'Sin definir'}</span></td>
                <td class="text-[14px]">${u.sin_tienda?'<span class="pill bg-red-500/20 text-red-300 border-red-500/40 text-[10px]">⚠ Sin tienda</span>':((u.paises_unicos||u.paises||[]).map(p => `<span title="${p}">${flag(p)}</span>`).join(' ')||'—')}</td>
                ${DATA.meta.ventana.map(m => `<td class="text-right font-mono text-slate-400">${fmt(u.ped_mes[m])}</td>`).join('')}
                <td class="text-right font-mono font-semibold text-slate-100">${fmt(u.total_pedidos)}</td>
                <td class="text-right font-mono ${u.pct_dev>15?'text-orange-400':u.pct_dev>10?'text-yellow-400':'text-slate-400'}">${u.pct_dev}%</td>
                <td class="text-center"><span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-full ${semColor[u.semaforo]||'bg-slate-600'}"></span><span class="text-[10px] ${semText[u.semaforo]||'text-slate-500'} font-semibold">${semLabel[u.semaforo]||'—'}</span></span></td>
              </tr>
            `).join('')}
            ${filtered.length>500?`<tr><td colspan="20" class="text-center text-slate-500 py-3">... y ${filtered.length-500} más</td></tr>`:''}
            ${filtered.length===0?`<tr><td colspan="20" class="text-center text-slate-500 py-6">— sin resultados —</td></tr>`:''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

let top100_desde = null, top100_hasta = null, top100_prog = "Todos", top100_tend = "Todas";

function tendencia(values) {
  // values: array de pedidos por mes (en orden cronológico) dentro del rango
  if (values.length < 2) return { sym:'—', col:'text-slate-500', key:'estable' };
  const first = values[0];
  const last = values[values.length-1];
  if (first === 0 && last === 0) return { sym:'—', col:'text-slate-500', key:'estable' };
  if (first === 0) return { sym:'▲', col:'text-green-400', key:'subiendo' };
  const delta = ((last - first) / first) * 100;
  if (delta > 10)  return { sym:'▲', col:'text-green-400', key:'subiendo' };
  if (delta < -10) return { sym:'▼', col:'text-red-400', key:'bajando' };
  return { sym:'—', col:'text-slate-500', key:'estable' };
}

function renderTop100() {
  const months = DATA.meta.ventana;
  if (!top100_desde) top100_desde = months[0];
  if (!top100_hasta) top100_hasta = months[months.length-1];
  if (months.indexOf(top100_desde) > months.indexOf(top100_hasta)) {
    [top100_desde, top100_hasta] = [top100_hasta, top100_desde];
  }
  const rangeMonths = months.slice(months.indexOf(top100_desde), months.indexOf(top100_hasta)+1);

  // Calcular sumas dentro del rango por usuario
  const list = DATA.usuarios.map(u => {
    const ped = rangeMonths.reduce((s,m) => s + (u.ped_mes[m]||0), 0);
    const ent = rangeMonths.reduce((s,m) => s + (u.ent_mes[m]||0), 0);
    const dev = rangeMonths.reduce((s,m) => s + (u.dev_mes[m]||0), 0);
    const pct = ped > 0 ? +(dev/ped*100).toFixed(1) : 0;
    const tend = tendencia(rangeMonths.map(m => u.ped_mes[m]||0));
    return { ...u, range_ped: ped, range_ent: ent, range_dev: dev, range_pct: pct, range_tend: tend };
  });

  // Filtros
  let filtered = list.filter(u => u.range_ped > 0);
  if (top100_prog !== "Todos") filtered = filtered.filter(u => u.programa === top100_prog);
  if (top100_tend !== "Todas") filtered = filtered.filter(u => u.range_tend.key === top100_tend);
  filtered.sort((a,b) => b.range_ped - a.range_ped);
  const top = filtered.slice(0, 100);

  // Totales
  const tot_ped = top.reduce((s,u) => s + u.range_ped, 0);
  const tot_ent = top.reduce((s,u) => s + u.range_ent, 0);
  const tot_dev = top.reduce((s,u) => s + u.range_dev, 0);
  const tot_pct = tot_ped > 0 ? (tot_dev/tot_ped*100).toFixed(1) : 0;

  const monthOpts = months.map(m => `<option value="${m}">${mesShort(m)}</option>`).join('');

  return `
    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <h3 class="text-base font-bold neon-cyan">Leaderboard — Top 100</h3>
        <label class="text-xs text-slate-500">Desde</label>
        <select id="t100-desde" class="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs">${months.map(m => `<option value="${m}" ${top100_desde===m?'selected':''}>${mesShort(m)}</option>`).join('')}</select>
        <label class="text-xs text-slate-500">Hasta</label>
        <select id="t100-hasta" class="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs">${months.map(m => `<option value="${m}" ${top100_hasta===m?'selected':''}>${mesShort(m)}</option>`).join('')}</select>
        <select id="t100-prog" class="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs">
          <option value="Todos" ${top100_prog==='Todos'?'selected':''}>Todos los programas</option>
          ${PROG_ORDER.map(p => `<option value="${p}" ${top100_prog===p?'selected':''}>${PROG_SHORT[p]}</option>`).join('')}
        </select>
        <select id="t100-tend" class="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs">
          <option value="Todas" ${top100_tend==='Todas'?'selected':''}>Todas las tendencias</option>
          <option value="subiendo" ${top100_tend==='subiendo'?'selected':''}>▲ Subiendo</option>
          <option value="bajando"  ${top100_tend==='bajando'?'selected':''}>▼ Bajando</option>
          <option value="estable"  ${top100_tend==='estable'?'selected':''}>— Estable</option>
        </select>
      </div>

      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2">#</th>
              <th class="text-left">Nombre</th>
              <th class="text-left">Email</th>
              <th class="text-left">Teléfono</th>
              <th class="text-center">Programa</th>
              <th class="text-left">País</th>
              <th class="text-center">Nivel</th>
              <th class="text-center">Tend.</th>
              <th class="text-right">Pedidos VIP</th>
              <th class="text-right">Entregados</th>
              <th class="text-right">Devueltos</th>
              <th class="text-right">% Dev.</th>
              <th class="text-center">Sem.</th>
            </tr>
          </thead>
          <tbody>
            ${top.map((u,i) => `
              <tr class="hover-row border-b border-white/5 cursor-pointer" data-cid="${u.cid}">
                <td class="py-2 text-slate-500">${i+1}</td>
                <td><span class="text-cyan-300 font-medium hover:underline">${tc(u.nombre)||'—'}</span></td>
                <td class="text-slate-400">${u.email||'—'}</td>
                <td class="text-slate-400 font-mono">${u.telefono||'—'}</td>
                <td class="text-center"><span class="pill bg-white/5 border-white/10 text-slate-300">${PROG_SHORT[u.programa]||'Sin definir'}</span></td>
                <td class="text-slate-300">${(u.paises_unicos||[]).map(p => flag(p)+' '+p).join(', ')||'—'}</td>
                <td class="text-center"><span class="pill ${tierColor[u.nivel]}">${u.nivel==='Sin clasificar'?'Sin nivel':u.nivel}</span></td>
                <td class="text-center font-mono ${u.range_tend.col}">${u.range_tend.sym}</td>
                <td class="text-right font-mono font-semibold text-slate-100">${fmt(u.range_ped)}</td>
                <td class="text-right font-mono text-slate-300">${fmt(u.range_ent)}</td>
                <td class="text-right font-mono text-slate-300">${fmt(u.range_dev)}</td>
                <td class="text-right font-mono ${u.range_pct>15?'text-orange-400':u.range_pct>10?'text-yellow-400':'text-green-400'}">${u.range_pct}%</td>
                <td class="text-center"><span class="w-2 h-2 rounded-full ${semColor[u.semaforo]} inline-block"></span></td>
              </tr>
            `).join('')}
            ${top.length===0?`<tr><td colspan="13" class="text-center text-slate-500 py-6">— sin resultados —</td></tr>`:''}
          </tbody>
          <tfoot class="border-t-2 border-cyan-500/30 bg-cyan-500/5 sticky bottom-0">
            <tr class="font-semibold">
              <td colspan="2" class="py-2 text-cyan-300">TOTAL (${top.length})</td>
              <td colspan="6"></td>
              <td class="text-right font-mono text-slate-100">${fmt(tot_ped)}</td>
              <td class="text-right font-mono text-slate-200">${fmt(tot_ent)}</td>
              <td class="text-right font-mono text-slate-200">${fmt(tot_dev)}</td>
              <td class="text-right font-mono ${tot_pct>15?'text-orange-400':tot_pct>10?'text-yellow-400':'text-green-400'}">${tot_pct}%</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;
}

function wireTop100() {
  const sd = document.getElementById('t100-desde');
  const sh = document.getElementById('t100-hasta');
  const sp = document.getElementById('t100-prog');
  const st = document.getElementById('t100-tend');
  if (sd) sd.onchange = e => { top100_desde = e.target.value; render(); };
  if (sh) sh.onchange = e => { top100_hasta = e.target.value; render(); };
  if (sp) sp.onchange = e => { top100_prog = e.target.value; render(); };
  if (st) st.onchange = e => { top100_tend = e.target.value; render(); };
  document.querySelectorAll('[data-cid]').forEach(row => row.onclick = () => abrirFicha(row.dataset.cid));
}

let alertaFiltroTipo = "Todas", alertaFiltroProg = "Todos", alertaSearch = "";

function renderAlertas() {
  const users = DATA.usuarios;
  const months = DATA.meta.ventana;

  // Counts globales
  const cnt = { "Eliminado":0, "Riesgo":0, "Desaparecido":0, "Crítica":0, "Huérfana":0 };
  users.forEach(u => {
    if (u.alerta_tipo) cnt[u.alerta_tipo] = (cnt[u.alerta_tipo]||0) + 1;
  });
  const totalAlertas = users.filter(u => u.alerta_tipo).length;

  // Filtros
  let filtered = users.filter(u => u.alerta_tipo); // solo con alguna alerta
  if (alertaFiltroTipo !== "Todas") filtered = filtered.filter(u => u.alerta_tipo === alertaFiltroTipo);
  if (alertaFiltroProg !== "Todos") filtered = filtered.filter(u => u.programa === alertaFiltroProg);
  if (alertaSearch) {
    const s = alertaSearch.toLowerCase();
    filtered = filtered.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
  }

  const alertColor = {
    "Crítica":     "bg-red-500/20 text-red-300 border-red-500/40",
    "Eliminado":   "bg-red-600/30 text-red-200 border-red-500/40",
    "Riesgo":      "bg-orange-500/20 text-orange-300 border-orange-500/40",
    "Desaparecido":"bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
    "Huérfana":    "bg-violet-500/20 text-violet-300 border-violet-500/40",
  };
  const semColor2 = {"verde":"bg-green-400","amarillo":"bg-yellow-400","naranja":"bg-orange-400","rojo":"bg-red-400","gris":"bg-slate-500"};
  const semLabel2 = {"verde":"VERDE","amarillo":"AMARILLO","naranja":"NARANJA","rojo":"ROJO","gris":"GRIS"};

  const monthCols = months.map(m => `<th class="text-right text-[10px] uppercase tracking-wider">${mesShort(m)}</th>`).join('');

  return `
    <!-- BARRA DE FILTROS -->
    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3">
        <select id="al-tipo" class="bg-black/40 border border-cyan-500/40 rounded-lg px-3 py-2 text-sm">
          <option value="Todas" ${alertaFiltroTipo==='Todas'?'selected':''}>Todas las alertas</option>
          <option value="Crítica" ${alertaFiltroTipo==='Crítica'?'selected':''}>🚨 Críticas</option>
          <option value="Desaparecido" ${alertaFiltroTipo==='Desaparecido'?'selected':''}>⚠️ Desaparecidos</option>
          <option value="Riesgo" ${alertaFiltroTipo==='Riesgo'?'selected':''}>🟠 Riesgo de eliminación</option>
          <option value="Eliminado" ${alertaFiltroTipo==='Eliminado'?'selected':''}>🔴 Eliminados</option>
          <option value="Huérfana" ${alertaFiltroTipo==='Huérfana'?'selected':''}>👻 Huérfanas (nunca vendieron)</option>
        </select>
        <select id="al-prog" class="bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm">
          <option value="Todos" ${alertaFiltroProg==='Todos'?'selected':''}>Todos los programas</option>
          ${PROG_ORDER.map(p => `<option value="${p}" ${alertaFiltroProg===p?'selected':''}>${PROG_SHORT[p]}</option>`).join('')}
        </select>
        <input id="al-search" type="text" placeholder="Buscar..." class="flex-1 min-w-[200px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500" value="${alertaSearch.replace(/"/g,'&quot;')}">
      </div>
    </div>

    <!-- STAT CARDS + TOTAL -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
      <div class="card p-4">
        <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">🚨 Críticas</div>
        <div class="text-3xl font-bold mt-1 text-red-400">${fmt(cnt['Crítica'])}</div>
        <div class="text-[10px] text-slate-500 mt-1">% devolución > 50%</div>
      </div>
      <div class="card p-4">
        <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">⚠️ Desaparecidos</div>
        <div class="text-3xl font-bold mt-1 text-yellow-400">${fmt(cnt['Desaparecido'])}</div>
        <div class="text-[10px] text-slate-500 mt-1">0 pedidos en ${mesShort(months[months.length-1])}</div>
      </div>
      <div class="card p-4">
        <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">🟠 Riesgo</div>
        <div class="text-3xl font-bold mt-1 text-orange-400">${fmt(cnt['Riesgo'])}</div>
        <div class="text-[10px] text-slate-500 mt-1">Últimos 2 meses en 0</div>
      </div>
      <div class="card p-4">
        <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">🔴 Eliminados</div>
        <div class="text-3xl font-bold mt-1 text-red-500">${fmt(cnt['Eliminado'])}</div>
        <div class="text-[10px] text-slate-500 mt-1">3+ meses en 0</div>
      </div>
      <div class="card p-4">
        <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">👻 Huérfanas</div>
        <div class="text-3xl font-bold mt-1 text-violet-400">${fmt(cnt['Huérfana'])}</div>
        <div class="text-[10px] text-slate-500 mt-1">Nunca han tenido ventas</div>
      </div>
      <div class="card p-4">
        <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Total alertas</div>
        <div class="text-3xl font-bold mt-1 neon-cyan">${fmt(totalAlertas)}</div>
        <div class="text-[10px] text-slate-500 mt-1">usuarios con alerta</div>
      </div>
    </div>

    <!-- TABLA -->
    <div class="card p-4">
      <div class="text-xs text-slate-500 mb-2">Mostrando ${filtered.length} de ${totalAlertas} con alerta</div>
      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2">Nombre</th>
              <th class="text-left">Email</th>
              <th class="text-left">Teléfono</th>
              <th class="text-center">Programa</th>
              <th class="text-left">País</th>
              <th class="text-center">Nivel</th>
              ${monthCols}
              <th class="text-center">Semáforo</th>
              <th class="text-center">Alerta</th>
            </tr>
          </thead>
          <tbody>
            ${filtered.map(u => `
              <tr class="hover-row border-b border-white/5 cursor-pointer" data-cid="${u.cid}">
                <td class="py-2"><span class="text-cyan-300 font-medium hover:underline">${tc(u.nombre)||'—'}</span></td>
                <td class="text-slate-400">${u.email||'—'}</td>
                <td class="text-slate-400 font-mono">${u.telefono||'—'}</td>
                <td class="text-center"><span class="pill bg-white/5 border-white/10 text-slate-300">${PROG_SHORT[u.programa]||'Sin definir'}</span></td>
                <td class="text-[14px]">${(u.paises_unicos||u.paises||[]).map(p => flag(p)).join(' ')||'—'}</td>
                <td class="text-center"><span class="pill ${tierColor[u.nivel]}">${u.nivel==='Sin clasificar'?'Sin nivel':u.nivel}</span></td>
                ${months.map(m => `<td class="text-right font-mono ${(u.ped_mes[m]||0)===0?'text-slate-700':'text-slate-400'}">${fmt(u.ped_mes[m])}</td>`).join('')}
                <td class="text-center"><span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-full ${semColor2[u.semaforo]||'bg-slate-500'}"></span><span class="text-[10px] font-semibold">${semLabel2[u.semaforo]||'—'}</span></span></td>
                <td class="text-center"><span class="pill ${alertColor[u.alerta_tipo]||'bg-white/5'}">${u.alerta_tipo||'—'}</span></td>
              </tr>
            `).join('')}
            ${filtered.length===0?`<tr><td colspan="20" class="text-center text-slate-500 py-6">— sin alertas en este filtro —</td></tr>`:''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function wireAlertas() {
  const t = document.getElementById('al-tipo');
  const p = document.getElementById('al-prog');
  const s = document.getElementById('al-search');
  if (t) t.onchange = e => { alertaFiltroTipo = e.target.value; render(); };
  if (p) p.onchange = e => { alertaFiltroProg = e.target.value; render(); };
  if (s) {
    s.oninput = e => { alertaSearch = e.target.value; render(); };
    s.focus(); s.setSelectionRange(alertaSearch.length, alertaSearch.length);
  }
  document.querySelectorAll('[data-cid]').forEach(row => row.onclick = () => abrirFicha(row.dataset.cid));
}

function renderPaises() {
  const pp = DATA.por_pais;
  const total = Object.values(pp).reduce((s,n)=>s+n,0);
  return `<div class="card p-5">
    <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Contactos con tienda · por país</h3>
    <table class="w-full text-sm">
      <thead class="text-[10px] text-slate-500 uppercase tracking-wider">
        <tr><th class="text-left py-2">País</th><th class="text-right">Contactos</th><th class="text-right">%</th><th class="text-left pl-6">Reparto</th></tr>
      </thead>
      <tbody>
        ${Object.entries(pp).map(([p,n]) => {
          const pct = total ? (n*100/total).toFixed(1) : 0;
          const max = Math.max(...Object.values(pp)) || 1;
          const bw = (n/max*100).toFixed(1);
          return `<tr class="border-b border-white/5">
            <td class="py-2 text-slate-200">${p}</td>
            <td class="text-right font-mono text-slate-300">${n}</td>
            <td class="text-right text-slate-500">${pct}%</td>
            <td class="pl-6 pr-2 w-2/5"><div class="bg-white/5 h-2 rounded-full overflow-hidden"><div class="h-full rounded-full bg-cyan-500" style="width:${bw}%"></div></div></td>
          </tr>`;
        }).join('')}
      </tbody></table>
  </div>`;
}

function renderReglas() {
  return `<div class="space-y-4">
    <div class="card p-5">
      <h3 class="text-sm font-semibold mb-3 neon-cyan">Reglas de Ingreso y Permanencia</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
        <div><h4 class="font-semibold text-slate-200 mb-2">① Ingreso</h4>
          <ul class="text-slate-400 space-y-1 text-xs">
            <li>• Mínimo 2 meses con ventas dentro de la ventana de 5 meses</li>
            <li>• Suma de tus 2 mejores meses (top-2) ≥ <span class="neon-yellow font-semibold">60 pedidos</span></li>
            <li>• Si cumples → ingresas como <span class="pill ${tierColor.Bronce}">Bronce</span></li>
          </ul></div>
        <div><h4 class="font-semibold text-slate-200 mb-2">② Escalafón</h4>
          <ul class="text-slate-400 space-y-1 text-xs">
            <li>• Para subir de Bronce: necesitas <span class="neon-yellow font-semibold">3 meses con ventas</span></li>
            <li>• Tu nivel se calcula con suma top-3</li>
            <li>• Mantienes beneficios de niveles anteriores</li>
          </ul></div>
        <div><h4 class="font-semibold text-slate-200 mb-2">③ Eliminación</h4>
          <ul class="text-slate-400 space-y-1 text-xs">
            <li>• 3 meses CONSECUTIVOS sin pedidos → eliminado</li>
            <li>• Si vendes en cualquiera de los 3, te mantienes</li>
            <li>• Aplica a todos los niveles</li>
          </ul></div>
      </div>
    </div>
    <div class="card p-5">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">Reglas de escalafones</h3>
      <table class="w-full text-sm">
        <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10">
          <tr>
            <th class="text-left py-3">Nivel</th>
            <th class="text-left">Pedidos/mes mínimo</th>
            <th class="text-left">Meses requeridos</th>
            <th class="text-left">Sumatoria mínima</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b border-white/5">
            <td class="py-3"><span class="pill ${tierColor.Diamante}">Diamante</span></td>
            <td class="font-mono text-slate-200">5.000+</td>
            <td class="text-slate-300">3 activos</td>
            <td class="font-mono text-slate-100">15.000</td>
          </tr>
          <tr class="border-b border-white/5">
            <td class="py-3"><span class="pill ${tierColor.Platino}">Platino</span></td>
            <td class="font-mono text-slate-200">1.000+</td>
            <td class="text-slate-300">3 activos</td>
            <td class="font-mono text-slate-100">3.000</td>
          </tr>
          <tr class="border-b border-white/5">
            <td class="py-3"><span class="pill ${tierColor.Oro}">Oro</span></td>
            <td class="font-mono text-slate-200">300+</td>
            <td class="text-slate-300">3 activos</td>
            <td class="font-mono text-slate-100">900</td>
          </tr>
          <tr class="border-b border-white/5">
            <td class="py-3"><span class="pill ${tierColor.Plata}">Plata</span></td>
            <td class="font-mono text-slate-200">100+</td>
            <td class="text-slate-300">3 activos</td>
            <td class="font-mono text-slate-100">300</td>
          </tr>
          <tr class="border-b border-white/5">
            <td class="py-3"><span class="pill ${tierColor.Bronce}">Bronce</span></td>
            <td class="font-mono text-slate-200">30+</td>
            <td class="text-slate-300">2 activos</td>
            <td class="font-mono text-slate-100">60</td>
          </tr>
          <tr class="border-b border-white/5">
            <td class="py-3"><span class="pill ${tierColor['Sin clasificar']}">Sin nivel</span></td>
            <td class="text-slate-400">&lt;30 o 1 mes</td>
            <td class="text-slate-500">—</td>
            <td class="text-slate-500">—</td>
          </tr>
        </tbody></table>
      <div class="text-[11px] text-slate-500 mt-4 leading-relaxed">
        <strong class="text-slate-400">Cómo se lee:</strong> Diamante se obtiene con 3 meses activos donde el promedio sea 5.000+ pedidos por mes
        (sumatoria de los 3 mejores meses ≥ 15.000). Bronce es el único nivel que requiere solo 2 meses activos (top-2 ≥ 60).
        Los demás requieren al menos 3 meses con ventas dentro de la ventana de 5 meses.
      </div>
    </div>
  </div>`;
}

function renderConsulta() {
  return `<div class="card p-5">
    <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Consulta individual</h3>
    <input id="consulta-input" type="text" placeholder="Pega un correo, contact_id o nombre..."
           class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:border-cyan-500">
    <div id="consulta-result" class="text-sm text-slate-500">Buscando...</div>
  </div>`;
}

function render() {
  const main = document.getElementById("main-content");
  switch (currentTab) {
    case "resumen": main.innerHTML = renderResumen(); drawCharts(); break;
    case "clasif":  main.innerHTML = renderClasificacion(0); wireClasificacion(); break;
    case "top100":  main.innerHTML = renderTop100(); wireTop100(); break;
    case "alertas": main.innerHTML = renderAlertas(); wireAlertas(); break;
    case "paises":  main.innerHTML = renderPaises(); break;
    case "reglas":  main.innerHTML = renderReglas(); break;
    case "consulta":main.innerHTML = renderConsulta(); wireConsulta(); break;
    case "met_sin_vip":    main.innerHTML = renderMetSinVIP();     wireMetSinVIP();     break;
    case "met_programas":  main.innerHTML = renderMetProgramas();   wireMetProgramas();   break;
    case "met_dropi_ghl":  main.innerHTML = renderMetDropiGHL();    wireMetDropiGHL();    break;
    case "met_duplicados": main.innerHTML = renderMetDuplicados();  wireMetDuplicados();  break;
  }
}

// ============================================================
// MÉTRICAS · 3 vistas independientes del VIP
// ============================================================
let metSinVipProg   = "Todos";
let metSinVipSearch = "";
let metProgFilter   = "Todos";
let metProgSearch   = "";
let metDropiVentas  = "Todos";   // "Todos" | "Con ventas" | "Sin ventas"
let metDropiSearch  = "";
let metDropiCountry = "Todos";

function downloadCSV(filename, rows) {
  const NL = String.fromCharCode(10);
  const csv = rows.map(r => r.map(c => {
    const s = (c == null ? '' : String(c));
    return (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf(NL) >= 0)
      ? '"' + s.replace(/"/g,'""') + '"' : s;
  }).join(',')).join(NL);
  const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

// ---------- VISTA 1: No están en Comunidad VIP ----------
// Selección múltiple para envío de correos
let metSinVipSelected = new Set();
let serverReady = null;   // se detecta al primer render
let serverConfig = null;

function detectarServidor() {
  if (location.protocol !== 'http:' && location.protocol !== 'https:') {
    serverReady = false;
    return Promise.resolve();
  }
  return fetch('/api/config').then(r => r.json()).then(cfg => {
    serverConfig = cfg;
    serverReady = !!cfg.ready;
  }).catch(() => { serverReady = false; });
}

function renderMetSinVIP() {
  const all = DATA.metricas.sin_comunidad_vip || [];
  let list = all.slice();
  if (metSinVipProg !== "Todos") list = list.filter(u => u.programa === metSinVipProg);
  if (metSinVipSearch) {
    const s = metSinVipSearch.toLowerCase();
    list = list.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
  }
  const cnt = {
    Todos: all.length,
    "Master Escala": all.filter(u => u.programa==="Master Escala").length,
    "Iniciación Escala": all.filter(u => u.programa==="Iniciación Escala").length,
    "Ambos": all.filter(u => u.programa==="Ambos").length,
  };
  // ¿Cuántos visibles tienen email válido?
  const listConEmail = list.filter(u => u.email && u.email.includes('@'));
  // ¿Cuántos seleccionados están en la lista filtrada actual?
  const selVisible = listConEmail.filter(u => metSinVipSelected.has(u.cid)).length;
  const allChecked = listConEmail.length > 0 && selVisible === listConEmail.length;

  const isLocal = (location.protocol === 'http:' || location.protocol === 'https:');
  const banner = !isLocal
    ? `<div class="card p-3 mb-3 border-amber-500/30 bg-amber-500/5">
         <div class="text-xs text-amber-300 font-semibold mb-1">⚠ Servidor local no detectado</div>
         <div class="text-[11px] text-amber-200/70 leading-relaxed">
           Para enviar correos arranca el servidor:<br>
           <code class="text-amber-100">cd "$(pwd)" && python3 servidor_local.py</code><br>
           Luego abre <code class="text-amber-100">http://localhost:8888</code> en lugar de <code>file://</code>.
         </div>
       </div>`
    : (serverReady === false
      ? `<div class="card p-3 mb-3 border-red-500/30 bg-red-500/5">
           <div class="text-xs text-red-300 font-semibold mb-1">⚠ Servidor local detectado, pero falta configurar Gmail</div>
           <div class="text-[11px] text-red-200/70">Edita <code>.env</code> y agrega <code>GMAIL_FROM</code> y <code>GMAIL_APP_PASSWORD</code>. Reinicia el servidor.</div>
         </div>`
      : '');

  return `
    <div class="card p-4 mb-4">
      <h2 class="text-base font-bold neon-cyan mb-1">👥 No están en Comunidad VIP</h2>
      <div class="text-xs text-slate-500">Contactos con tag <code>escala</code> o <code>iniciacion</code> en GHL que NO tienen el tag <code>comunidad vip new</code>.</div>
    </div>

    ${banner}

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      ${statCard("Total sin VIP new", cnt["Todos"], "Master o Iniciación sin la etiqueta", "neon-cyan")}
      ${statCard("Solo Master Escala", cnt["Master Escala"], "Tag 'escala' sin 'iniciacion'", "neon-violet")}
      ${statCard("Solo Iniciación", cnt["Iniciación Escala"], "Tag 'iniciacion' sin 'escala'", "neon-pink")}
      ${statCard("Ambos programas", cnt["Ambos"], "Tienen los dos tags formativos", "neon-yellow")}
    </div>

    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <input id="met1-search" type="text" placeholder="Buscar por nombre o email..."
               class="flex-1 min-w-[260px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
               value="${metSinVipSearch.replace(/"/g,'&quot;')}">
        <button id="met1-csv" class="text-[11px] px-3 py-2 rounded-lg bg-cyan-600/30 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-600/40">⬇ Descargar CSV</button>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div class="text-[10px] uppercase tracking-wider text-slate-500 w-20">Programa:</div>
        ${["Todos","Master Escala","Iniciación Escala","Ambos"].map(p =>
          `<button data-met1prog="${p}" class="text-[11px] px-3 py-1.5 rounded-lg font-medium ${metSinVipProg===p?'bg-cyan-600/30 text-cyan-200 border border-cyan-500/40':'bg-white/5 text-slate-400 border border-white/5 hover:text-slate-200'}">${p==='Todos'?'Todos':PROG_SHORT[p]} <span class="ml-1 text-slate-500">${cnt[p]||0}</span></button>`
        ).join('')}
      </div>
    </div>

    <div class="card p-4">
      <div class="flex justify-between items-center mb-2">
        <div class="text-xs text-slate-500">Mostrando ${list.length} de ${all.length} · ${listConEmail.length} con email</div>
        <div class="flex items-center gap-2">
          ${metSinVipSelected.size > 0
            ? `<span class="text-xs text-cyan-300 font-semibold">${metSinVipSelected.size} seleccionado${metSinVipSelected.size!==1?'s':''}</span>
               <button id="met1-clear" class="text-[10px] px-2 py-1 rounded text-slate-400 hover:text-slate-200">Limpiar</button>
               <button id="met1-send" class="text-[11px] px-3 py-1.5 rounded-lg bg-green-600/30 text-green-200 border border-green-500/40 hover:bg-green-600/40 font-semibold">✉ Enviar a ${metSinVipSelected.size}</button>`
            : `<span class="text-[11px] text-slate-600">Selecciona contactos para enviar correos</span>`
          }
        </div>
      </div>
      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2 w-8"><input type="checkbox" id="met1-checkall" ${allChecked?'checked':''} title="Seleccionar visibles con email"></th>
              <th class="text-left">Nombre</th>
              <th class="text-left">Email</th>
              <th class="text-left">Teléfono</th>
              <th class="text-center">Programa</th>
              <th class="text-left">Contact ID</th>
            </tr>
          </thead>
          <tbody>
            ${list.map(u => {
              const hasEmail = u.email && u.email.includes('@');
              const checked = metSinVipSelected.has(u.cid);
              return `
              <tr class="hover-row border-b border-white/5 ${checked?'bg-cyan-500/5':''}">
                <td class="py-2">${hasEmail
                  ? `<input type="checkbox" data-met1cid="${u.cid}" ${checked?'checked':''}>`
                  : `<span title="Sin email — no se puede enviar" class="text-slate-700">—</span>`}</td>
                <td class="text-slate-200">${tc(u.nombre)||'—'}</td>
                <td class="text-slate-300">${u.email||'<span class="text-slate-600">sin email</span>'}</td>
                <td class="text-slate-400 font-mono">${u.telefono||'—'}</td>
                <td class="text-center"><span class="pill bg-white/5 border-white/10 text-slate-300">${PROG_SHORT[u.programa]||u.programa}</span></td>
                <td class="text-slate-500 font-mono text-[10px]">${u.cid}</td>
              </tr>`;
            }).join('')}
            ${list.length===0?`<tr><td colspan="6" class="text-center text-slate-500 py-6">— sin resultados —</td></tr>`:''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
function wireMetSinVIP() {
  document.querySelectorAll('[data-met1prog]').forEach(b => b.onclick = () => { metSinVipProg = b.dataset.met1prog; render(); });
  const inp = document.getElementById('met1-search');
  if (inp) {
    inp.oninput = e => { metSinVipSearch = e.target.value; render(); };
    inp.focus(); inp.setSelectionRange(metSinVipSearch.length, metSinVipSearch.length);
  }
  const btn = document.getElementById('met1-csv');
  if (btn) btn.onclick = () => {
    const all = DATA.metricas.sin_comunidad_vip || [];
    let list = all.slice();
    if (metSinVipProg !== "Todos") list = list.filter(u => u.programa === metSinVipProg);
    if (metSinVipSearch) {
      const s = metSinVipSearch.toLowerCase();
      list = list.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
    }
    const rows = [["Nombre","Email","Teléfono","Programa","Contact ID"]];
    list.forEach(u => rows.push([u.nombre,u.email,u.telefono,u.programa,u.cid]));
    downloadCSV("no_estan_en_comunidad_vip.csv", rows);
  };
  // Checkboxes individuales
  document.querySelectorAll('[data-met1cid]').forEach(cb => cb.onclick = e => {
    const cid = e.target.dataset.met1cid;
    if (e.target.checked) metSinVipSelected.add(cid); else metSinVipSelected.delete(cid);
    render();
  });
  // Check all (solo visibles con email)
  const ca = document.getElementById('met1-checkall');
  if (ca) ca.onclick = e => {
    const all = DATA.metricas.sin_comunidad_vip || [];
    let list = all.slice();
    if (metSinVipProg !== "Todos") list = list.filter(u => u.programa === metSinVipProg);
    if (metSinVipSearch) {
      const s = metSinVipSearch.toLowerCase();
      list = list.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
    }
    const visConEmail = list.filter(u => u.email && u.email.includes('@'));
    if (e.target.checked) visConEmail.forEach(u => metSinVipSelected.add(u.cid));
    else visConEmail.forEach(u => metSinVipSelected.delete(u.cid));
    render();
  };
  const clearBtn = document.getElementById('met1-clear');
  if (clearBtn) clearBtn.onclick = () => { metSinVipSelected.clear(); render(); };
  const sendBtn = document.getElementById('met1-send');
  if (sendBtn) sendBtn.onclick = () => abrirModalEnvio();
}

// ============================================================
// MODAL DE ENVÍO DE CORREO
// ============================================================
function abrirModalEnvio() {
  const isLocal = (location.protocol === 'http:' || location.protocol === 'https:');
  if (!isLocal) {
    alert("Para enviar correos arranca el servidor local:" + String.fromCharCode(10,10) +
          "python3 servidor_local.py" + String.fromCharCode(10,10) +
          "Luego abre http://localhost:8888");
    return;
  }
  if (serverReady === false) {
    alert("El servidor está corriendo pero faltan credenciales de Gmail en .env (GMAIL_FROM y GMAIL_APP_PASSWORD). Edita el .env y reinicia el servidor.");
    return;
  }
  const all = DATA.metricas.sin_comunidad_vip || [];
  const selectedContacts = all.filter(u => metSinVipSelected.has(u.cid) && u.email && u.email.includes('@'));
  if (!selectedContacts.length) { alert("No hay contactos válidos seleccionados."); return; }

  const draft = (function(){
    try { return JSON.parse(localStorage.getItem('email_draft_v1')||'{}'); } catch(e) { return {}; }
  })();
  const defSubject = draft.subject || "Te invitamos a la Comunidad VIP";
  const _NL = String.fromCharCode(10);
  const defBody = draft.body || [
    "Hola {nombre},",
    "",
    "Notamos que ya formas parte de {programa} pero aún no te hemos sumado a la Comunidad VIP.",
    "",
    "Si quieres conocer los beneficios y unirte, respóndenos a este correo.",
    "",
    "Saludos,",
    "Iván Caicedo"
  ].join(_NL);

  const modal = document.getElementById('envio-modal');
  modal.classList.remove('hidden');
  document.getElementById('envio-content').innerHTML = `
    <div class="card p-5 mb-3">
      <h3 class="text-lg font-bold neon-cyan mb-1">✉ Enviar correo</h3>
      <div class="text-xs text-slate-400">A <span class="text-cyan-300 font-semibold">${selectedContacts.length}</span> destinatario${selectedContacts.length!==1?'s':''} · From: <span class="text-slate-300">${serverConfig?.from_email||'(servidor)'}</span></div>
    </div>

    <div class="card p-5 mb-3">
      <label class="text-[10px] uppercase tracking-wider text-slate-500 block mb-1">Asunto</label>
      <input id="env-subject" type="text" value="${defSubject.replace(/"/g,'&quot;')}"
             class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500 mb-4">

      <div class="flex justify-between items-baseline mb-1">
        <label class="text-[10px] uppercase tracking-wider text-slate-500">Cuerpo del mensaje</label>
        <div class="text-[10px] text-slate-500">Variables: <code class="text-cyan-400">{nombre}</code> <code class="text-cyan-400">{email}</code> <code class="text-cyan-400">{programa}</code> <code class="text-cyan-400">{telefono}</code></div>
      </div>
      <textarea id="env-body" rows="10"
                class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500 font-mono text-xs">${defBody}</textarea>
      <div class="text-[10px] text-slate-500 mt-1">Tip: puedes usar HTML básico (&lt;br&gt;, &lt;b&gt;, &lt;a href&gt;...). Los saltos de línea se respetan automáticamente.</div>
    </div>

    <div class="card p-4 mb-3">
      <div class="text-[10px] uppercase tracking-wider text-slate-500 mb-2">👁 Vista previa con el primer destinatario</div>
      <div class="bg-black/30 border border-white/5 rounded-lg p-3 text-xs" id="env-preview"></div>
    </div>

    <div id="env-progress" class="hidden card p-4 mb-3">
      <div class="text-[11px] uppercase tracking-wider text-slate-500 mb-2">Enviando...</div>
      <div class="w-full bg-black/40 rounded-full h-3 overflow-hidden mb-2">
        <div id="env-bar" class="h-full bg-gradient-to-r from-cyan-500 to-green-500 transition-all" style="width:0%"></div>
      </div>
      <div id="env-log" class="text-[11px] font-mono text-slate-400 max-h-48 overflow-y-auto"></div>
    </div>

    <div class="flex justify-end gap-2">
      <button id="env-cancel" class="cat-btn">Cancelar</button>
      <button id="env-send" class="cat-btn active">✉ Enviar a ${selectedContacts.length}</button>
    </div>
  `;

  // Helpers
  const aplicarVars = (txt, u) => txt
    .replace(/\{nombre\}/g, tc(u.nombre)||'')
    .replace(/\{email\}/g, u.email||'')
    .replace(/\{programa\}/g, PROG_SHORT[u.programa]||u.programa||'')
    .replace(/\{telefono\}/g, u.telefono||'');

  const txtToHtml = (txt) => {
    // si NO contiene tags, convertir saltos de línea a <br>
    if (/<[a-z][^>]*>/i.test(txt)) return txt;
    return txt.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').split(String.fromCharCode(10)).join('<br>');
  };

  const actualizarPreview = () => {
    const subj = document.getElementById('env-subject').value;
    const body = document.getElementById('env-body').value;
    const u = selectedContacts[0];
    document.getElementById('env-preview').innerHTML = `
      <div class="text-slate-500 text-[10px] mb-1">A: <span class="text-slate-300">${u.email}</span></div>
      <div class="text-slate-500 text-[10px] mb-2">Asunto: <span class="text-slate-200 font-semibold">${aplicarVars(subj,u).replace(/</g,'&lt;')}</span></div>
      <div class="border-t border-white/5 pt-2 text-slate-300">${txtToHtml(aplicarVars(body, u))}</div>
    `;
  };
  actualizarPreview();
  document.getElementById('env-subject').oninput = actualizarPreview;
  document.getElementById('env-body').oninput = actualizarPreview;

  document.getElementById('env-cancel').onclick = cerrarModalEnvio;

  document.getElementById('env-send').onclick = async () => {
    const subj = document.getElementById('env-subject').value.trim();
    const body = document.getElementById('env-body').value.trim();
    if (!subj || !body) { alert("Asunto y cuerpo son obligatorios."); return; }
    // Guardar borrador
    try { localStorage.setItem('email_draft_v1', JSON.stringify({subject:subj, body:body})); } catch(e){}

    // Confirmar
    if (!confirm(`¿Enviar este correo a ${selectedContacts.length} destinatario${selectedContacts.length!==1?'s':''}?`)) return;

    document.getElementById('env-send').disabled = true;
    document.getElementById('env-cancel').disabled = true;
    document.getElementById('env-progress').classList.remove('hidden');
    const bar = document.getElementById('env-bar');
    const logEl = document.getElementById('env-log');
    let ok = 0, fail = 0;
    for (let i = 0; i < selectedContacts.length; i++) {
      const u = selectedContacts[i];
      const subjFinal = aplicarVars(subj, u);
      const bodyFinal = txtToHtml(aplicarVars(body, u));
      try {
        const resp = await fetch('/api/send-email', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({to: u.email, subject: subjFinal, body_html: bodyFinal})
        });
        const j = await resp.json();
        if (resp.ok) {
          ok++;
          logEl.innerHTML += `<div class="text-green-400">✓ ${u.email}</div>`;
        } else {
          fail++;
          logEl.innerHTML += `<div class="text-red-400">✗ ${u.email} — ${j.error||'error'}</div>`;
        }
      } catch(e) {
        fail++;
        logEl.innerHTML += `<div class="text-red-400">✗ ${u.email} — ${e.message}</div>`;
      }
      bar.style.width = (((i+1)/selectedContacts.length)*100).toFixed(1)+'%';
      logEl.scrollTop = logEl.scrollHeight;
      // pequeña pausa para no saturar
      await new Promise(r => setTimeout(r, 300));
    }
    logEl.innerHTML += `<div class="mt-2 pt-2 border-t border-white/10 text-cyan-300 font-semibold">Listo · ${ok} enviados, ${fail} fallidos</div>`;
    document.getElementById('env-send').innerHTML = 'Cerrar';
    document.getElementById('env-send').disabled = false;
    document.getElementById('env-send').onclick = () => {
      cerrarModalEnvio();
      if (ok > 0 && fail === 0) {
        // Si todos OK, deseleccionamos
        metSinVipSelected.clear();
        render();
      }
    };
  };
}
function cerrarModalEnvio() {
  document.getElementById('envio-modal').classList.add('hidden');
}

// ---------- VISTA 2: Master vs Iniciación ----------
function renderMetProgramas() {
  const all = DATA.metricas.programas || [];
  const m = DATA.metricas;
  let list = all.slice();
  if (metProgFilter !== "Todos") list = list.filter(u => u.programa === metProgFilter);
  if (metProgSearch) {
    const s = metProgSearch.toLowerCase();
    list = list.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
  }
  const cnt = {
    "Todos": all.length,
    "Master Escala": m.master_total,
    "Iniciación Escala": m.iniciacion_total,
    "Ambos": m.ambos_total,
    "Sin programa": m.sin_programa_total,
  };
  return `
    <div class="card p-4 mb-4">
      <h2 class="text-base font-bold neon-cyan mb-1">📊 Master vs Iniciación</h2>
      <div class="text-xs text-slate-500">Distribución de TODOS los contactos GHL (${fmt(m.ghl_total)}) según su tag de programa formativo.</div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      ${statCard("🎓 Master Escala", m.master_total, "Solo tag 'escala'", "neon-violet")}
      ${statCard("🌱 Iniciación", m.iniciacion_total, "Solo tag 'iniciacion'", "neon-pink")}
      ${statCard("⚡ Ambos", m.ambos_total, "Tienen ambos tags", "neon-yellow")}
      ${statCard("⚪ Sin programa", m.sin_programa_total, "Ni Master ni Iniciación", "neon-red")}
    </div>

    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <input id="met2-search" type="text" placeholder="Buscar por nombre o email..."
               class="flex-1 min-w-[260px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
               value="${metProgSearch.replace(/"/g,'&quot;')}">
        <button id="met2-csv" class="text-[11px] px-3 py-2 rounded-lg bg-cyan-600/30 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-600/40">⬇ Descargar CSV</button>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div class="text-[10px] uppercase tracking-wider text-slate-500 w-20">Programa:</div>
        ${["Todos","Master Escala","Iniciación Escala","Ambos","Sin programa"].map(p =>
          `<button data-met2prog="${p}" class="text-[11px] px-3 py-1.5 rounded-lg font-medium ${metProgFilter===p?'bg-cyan-600/30 text-cyan-200 border border-cyan-500/40':'bg-white/5 text-slate-400 border border-white/5 hover:text-slate-200'}">${p==='Todos'?'Todos':(PROG_SHORT[p]||p)} <span class="ml-1 text-slate-500">${cnt[p]||0}</span></button>`
        ).join('')}
      </div>
    </div>

    <div class="card p-4">
      <div class="text-xs text-slate-500 mb-2">Mostrando ${list.length} de ${all.length}</div>
      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2">Nombre</th>
              <th class="text-left">Email</th>
              <th class="text-left">Teléfono</th>
              <th class="text-center">Programa</th>
              <th class="text-center">VIP new</th>
              <th class="text-left">Contact ID</th>
            </tr>
          </thead>
          <tbody>
            ${list.slice(0,1000).map(u => `
              <tr class="hover-row border-b border-white/5">
                <td class="py-2 text-slate-200">${tc(u.nombre)||'—'}</td>
                <td class="text-slate-300">${u.email||'—'}</td>
                <td class="text-slate-400 font-mono">${u.telefono||'—'}</td>
                <td class="text-center"><span class="pill bg-white/5 border-white/10 text-slate-300">${PROG_SHORT[u.programa]||u.programa}</span></td>
                <td class="text-center">${u.tiene_vip_new?'<span class="pill bg-green-500/20 text-green-300 border-green-500/40">✓ Sí</span>':'<span class="pill bg-slate-700/40 text-slate-500 border-slate-600/40">— No</span>'}</td>
                <td class="text-slate-500 font-mono text-[10px]">${u.cid}</td>
              </tr>
            `).join('')}
            ${list.length>1000?`<tr><td colspan="6" class="text-center text-slate-500 py-3">... y ${list.length-1000} más (usa CSV para ver todos)</td></tr>`:''}
            ${list.length===0?`<tr><td colspan="6" class="text-center text-slate-500 py-6">— sin resultados —</td></tr>`:''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
function wireMetProgramas() {
  document.querySelectorAll('[data-met2prog]').forEach(b => b.onclick = () => { metProgFilter = b.dataset.met2prog; render(); });
  const inp = document.getElementById('met2-search');
  if (inp) {
    inp.oninput = e => { metProgSearch = e.target.value; render(); };
    inp.focus(); inp.setSelectionRange(metProgSearch.length, metProgSearch.length);
  }
  const btn = document.getElementById('met2-csv');
  if (btn) btn.onclick = () => {
    const all = DATA.metricas.programas || [];
    let list = all.slice();
    if (metProgFilter !== "Todos") list = list.filter(u => u.programa === metProgFilter);
    if (metProgSearch) {
      const s = metProgSearch.toLowerCase();
      list = list.filter(u => (u.nombre||'').toLowerCase().includes(s) || (u.email||'').toLowerCase().includes(s));
    }
    const rows = [["Nombre","Email","Teléfono","Programa","Tiene VIP new","Contact ID"]];
    list.forEach(u => rows.push([u.nombre,u.email,u.telefono,u.programa,u.tiene_vip_new?"Sí":"No",u.cid]));
    downloadCSV("master_vs_iniciacion.csv", rows);
  };
}

// ---------- VISTA 3: En Dropi sin GHL ----------
function renderMetDropiGHL() {
  const all = DATA.metricas.dropi_sin_ghl || [];
  const m = DATA.metricas;
  const months = DATA.meta.ventana;
  let list = all.slice();
  if (metDropiVentas === "Con ventas") list = list.filter(u => u.tiene_ventas);
  else if (metDropiVentas === "Sin ventas") list = list.filter(u => !u.tiene_ventas);
  if (metDropiCountry !== "Todos") list = list.filter(u => (u.paises||[]).includes(metDropiCountry));
  if (metDropiSearch) {
    const s = metDropiSearch.toLowerCase();
    list = list.filter(u => (u.email||'').toLowerCase().includes(s) || (u.nombre||'').toLowerCase().includes(s) || (u.telefono||'').includes(s));
  }
  const allCountries = [...new Set(all.flatMap(u => u.paises||[]))].sort();
  const monthCols = months.map(m2 => `<th class="text-right text-[10px] uppercase tracking-wider">${mesShort(m2)}</th>`).join('');
  const cnt = {
    "Todos":      all.length,
    "Con ventas": m.dropi_sin_ghl_con_ventas,
    "Sin ventas": m.dropi_sin_ghl_sin_ventas,
  };
  return `
    <div class="card p-4 mb-4">
      <h2 class="text-base font-bold neon-cyan mb-1">👻 En Dropi pero NO están en GHL</h2>
      <div class="text-xs text-slate-500">Correos que aparecen en los Excels de Dropi pero no existen como contacto principal ni como tienda en ningún contacto de GHL.</div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      ${statCard("Total Dropi sin GHL", all.length, `de ${fmt(m.dropi_emails_total)} correos en Dropi`, "neon-cyan")}
      ${statCard("Con ventas", m.dropi_sin_ghl_con_ventas, "Tienen ≥1 pedido en la ventana", "neon-green")}
      ${statCard("Sin ventas", m.dropi_sin_ghl_sin_ventas, "0 pedidos en toda la ventana", "neon-red")}
      ${statCard("Universo GHL", m.ghl_emails_universo, "Emails únicos en GHL (principal + tiendas)", "neon-violet")}
    </div>

    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <input id="met3-search" type="text" placeholder="Buscar por email, nombre o teléfono..."
               class="flex-1 min-w-[260px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
               value="${metDropiSearch.replace(/"/g,'&quot;')}">
        <select id="met3-country" class="bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500">
          <option value="Todos">Todos los países</option>
          ${allCountries.map(p => `<option value="${p}" ${metDropiCountry===p?'selected':''}>${flag(p)} ${p}</option>`).join('')}
        </select>
        <button id="met3-csv" class="text-[11px] px-3 py-2 rounded-lg bg-cyan-600/30 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-600/40">⬇ Descargar CSV</button>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div class="text-[10px] uppercase tracking-wider text-slate-500 w-20">Ventas:</div>
        ${["Todos","Con ventas","Sin ventas"].map(f =>
          `<button data-met3ventas="${f}" class="text-[11px] px-3 py-1.5 rounded-lg font-medium ${metDropiVentas===f?'bg-cyan-600/30 text-cyan-200 border border-cyan-500/40':'bg-white/5 text-slate-400 border border-white/5 hover:text-slate-200'}">${f} <span class="ml-1 text-slate-500">${cnt[f]||0}</span></button>`
        ).join('')}
      </div>
    </div>

    <div class="card p-4">
      <div class="text-xs text-slate-500 mb-2">Mostrando ${list.length} de ${all.length}</div>
      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2">Email</th>
              <th class="text-left">Nombre</th>
              <th class="text-left">Teléfono</th>
              <th class="text-left">Países</th>
              ${monthCols}
              <th class="text-right">Total ped.</th>
              <th class="text-center">Meses act.</th>
            </tr>
          </thead>
          <tbody>
            ${list.slice(0,1500).map(u => `
              <tr class="hover-row border-b border-white/5">
                <td class="py-2 text-slate-200">${u.email}</td>
                <td class="text-slate-300">${tc(u.nombre)||'—'}</td>
                <td class="text-slate-400 font-mono">${u.telefono||'—'}</td>
                <td class="text-[14px]">${(u.paises||[]).map(p => `<span title="${p}">${flag(p)}</span>`).join(' ')||'—'}</td>
                ${months.map(m2 => `<td class="text-right font-mono ${(u.ped_mes[m2]||0)===0?'text-slate-700':'text-slate-400'}">${fmt(u.ped_mes[m2])}</td>`).join('')}
                <td class="text-right font-mono font-semibold ${u.total_pedidos>0?'text-slate-100':'text-slate-600'}">${fmt(u.total_pedidos)}</td>
                <td class="text-center font-mono text-slate-400">${u.n_meses_activos}/${months.length}</td>
              </tr>
            `).join('')}
            ${list.length>1500?`<tr><td colspan="${5+months.length+2}" class="text-center text-slate-500 py-3">... y ${list.length-1500} más (usa CSV para ver todos)</td></tr>`:''}
            ${list.length===0?`<tr><td colspan="${5+months.length+2}" class="text-center text-slate-500 py-6">— sin resultados —</td></tr>`:''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
// ---------- VISTA 4: Posibles duplicados ----------
let metDupSearch = "";
function renderMetDuplicados() {
  const all = DATA.metricas.duplicados || [];
  const m = DATA.metricas;
  let list = all.slice();
  if (metDupSearch) {
    const s = metDupSearch.toLowerCase();
    list = list.filter(d =>
      (d.nombre||'').toLowerCase().includes(s) ||
      (d.email_principal||'').toLowerCase().includes(s) ||
      (d.tienda_email||'').toLowerCase().includes(s) ||
      (d.otro_nombre||'').toLowerCase().includes(s)
    );
  }
  return `
    <div class="card p-4 mb-4">
      <h2 class="text-base font-bold neon-cyan mb-1">🔁 Posibles duplicados</h2>
      <div class="text-xs text-slate-500 leading-relaxed">
        Contactos cuyo correo de tienda coincide con el <strong>email principal de otro contacto distinto</strong>.<br>
        Ejemplo: <span class="text-slate-300">"Diego Adolfo"</span> tiene como Tienda 3 el correo <code>diego@gmail.com</code>,
        que es el email principal de <span class="text-slate-300">"Diego Forero"</span> → posible duplicado o cuenta compartida.
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
      ${statCard("Coincidencias totales", m.duplicados_total, "Pares contacto ↔ tienda detectados", "neon-cyan")}
      ${statCard("Contactos involucrados", m.duplicados_contactos_unicos, "Contactos únicos con al menos un cruce", "neon-violet")}
      ${statCard("Universo GHL", m.ghl_total, "Sobre los que se hace el cruce", "neon-yellow")}
    </div>

    <div class="card p-4 mb-4">
      <div class="flex flex-wrap items-center gap-3">
        <input id="met4-search" type="text" placeholder="Buscar por nombre o correo..."
               class="flex-1 min-w-[260px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
               value="${metDupSearch.replace(/"/g,'&quot;')}">
        <button id="met4-csv" class="text-[11px] px-3 py-2 rounded-lg bg-cyan-600/30 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-600/40">⬇ Descargar CSV</button>
      </div>
    </div>

    <div class="card p-4">
      <div class="text-xs text-slate-500 mb-2">Mostrando ${list.length} de ${all.length}</div>
      <div class="overflow-x-auto scrollable">
        <table class="w-full text-xs">
          <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10 sticky top-0 bg-[#06091a] z-10">
            <tr>
              <th class="text-left py-2" colspan="4">Contacto con la tienda</th>
              <th class="text-left border-l border-white/10 pl-3" colspan="3">↔ Coincide con email principal de</th>
            </tr>
            <tr>
              <th class="text-left">Nombre</th>
              <th class="text-left">Email principal</th>
              <th class="text-left">Slot</th>
              <th class="text-left">Email tienda</th>
              <th class="text-left border-l border-white/10 pl-3">Nombre</th>
              <th class="text-left">Email</th>
              <th class="text-left">Teléfono</th>
            </tr>
          </thead>
          <tbody>
            ${list.map(d => `
              <tr class="hover-row border-b border-white/5">
                <td class="py-2 text-slate-200">${tc(d.nombre)||'—'}</td>
                <td class="text-slate-300">${d.email_principal||'<span class="text-slate-600">—</span>'}</td>
                <td class="text-center"><span class="pill bg-violet-500/20 text-violet-300 border-violet-500/40">${d.tienda_slot}${d.tienda_pais?' · '+flag(d.tienda_pais)+' '+d.tienda_pais:''}</span></td>
                <td class="text-amber-300 font-mono">${d.tienda_email}</td>
                <td class="text-slate-200 border-l border-white/10 pl-3">${tc(d.otro_nombre)||'—'}</td>
                <td class="text-amber-300 font-mono">${d.tienda_email}</td>
                <td class="text-slate-400 font-mono">${d.otro_telefono||'—'}</td>
              </tr>
            `).join('')}
            ${list.length===0?`<tr><td colspan="7" class="text-center text-slate-500 py-6">— no hay coincidencias —</td></tr>`:''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
function wireMetDuplicados() {
  const inp = document.getElementById('met4-search');
  if (inp) {
    inp.oninput = e => { metDupSearch = e.target.value; render(); };
    inp.focus(); inp.setSelectionRange(metDupSearch.length, metDupSearch.length);
  }
  const btn = document.getElementById('met4-csv');
  if (btn) btn.onclick = () => {
    const all = DATA.metricas.duplicados || [];
    let list = all.slice();
    if (metDupSearch) {
      const s = metDupSearch.toLowerCase();
      list = list.filter(d =>
        (d.nombre||'').toLowerCase().includes(s) ||
        (d.email_principal||'').toLowerCase().includes(s) ||
        (d.tienda_email||'').toLowerCase().includes(s) ||
        (d.otro_nombre||'').toLowerCase().includes(s)
      );
    }
    const rows = [["Contacto B (tiene la tienda)","Email principal B","Teléfono B","Slot tienda","País tienda","Email tienda","Contacto A (email coincide)","Email principal A","Teléfono A","CID B","CID A"]];
    list.forEach(d => rows.push([
      d.nombre, d.email_principal, d.telefono, d.tienda_slot, d.tienda_pais,
      d.tienda_email, d.otro_nombre, d.tienda_email, d.otro_telefono, d.cid, d.otro_cid
    ]));
    downloadCSV("posibles_duplicados.csv", rows);
  };
}

function wireMetDropiGHL() {
  document.querySelectorAll('[data-met3ventas]').forEach(b => b.onclick = () => { metDropiVentas = b.dataset.met3ventas; render(); });
  const cs = document.getElementById('met3-country');
  if (cs) cs.onchange = e => { metDropiCountry = e.target.value; render(); };
  const inp = document.getElementById('met3-search');
  if (inp) {
    inp.oninput = e => { metDropiSearch = e.target.value; render(); };
    inp.focus(); inp.setSelectionRange(metDropiSearch.length, metDropiSearch.length);
  }
  const btn = document.getElementById('met3-csv');
  if (btn) btn.onclick = () => {
    const all = DATA.metricas.dropi_sin_ghl || [];
    const months = DATA.meta.ventana;
    let list = all.slice();
    if (metDropiVentas === "Con ventas") list = list.filter(u => u.tiene_ventas);
    else if (metDropiVentas === "Sin ventas") list = list.filter(u => !u.tiene_ventas);
    if (metDropiCountry !== "Todos") list = list.filter(u => (u.paises||[]).includes(metDropiCountry));
    if (metDropiSearch) {
      const s = metDropiSearch.toLowerCase();
      list = list.filter(u => (u.email||'').toLowerCase().includes(s) || (u.nombre||'').toLowerCase().includes(s) || (u.telefono||'').includes(s));
    }
    const header = ["Email","Nombre","Teléfono","Países", ...months, "Total pedidos","Meses activos"];
    const rows = [header];
    list.forEach(u => rows.push([u.email,u.nombre,u.telefono,(u.paises||[]).join('|'), ...months.map(m=>u.ped_mes[m]||0), u.total_pedidos, u.n_meses_activos]));
    downloadCSV("dropi_sin_ghl.csv", rows);
  };
}

function wireClasificacion() {
  document.querySelectorAll('[data-tier]').forEach(b => b.onclick = () => { currentFilter = b.dataset.tier; render(); });
  document.querySelectorAll('[data-prog]').forEach(b => b.onclick = () => { currentProg = b.dataset.prog; render(); });
  document.querySelectorAll('[data-multipais]').forEach(b => b.onclick = () => { currentMultipais = !currentMultipais; render(); });
  document.querySelectorAll('[data-cid]').forEach(row => row.onclick = () => abrirFicha(row.dataset.cid));
  const cs = document.getElementById('country-select');
  if (cs) cs.onchange = e => { currentCountry = e.target.value; render(); };
  const inp = document.getElementById('search-input');
  if (inp) {
    inp.oninput = e => { currentSearch = e.target.value; render(); };
    inp.focus();
    inp.setSelectionRange(currentSearch.length, currentSearch.length);
  }
}

function initials(name) {
  const parts = (name||'').trim().split(/\s+/).slice(0,2);
  return parts.map(p => p.charAt(0).toUpperCase()).join('') || '??';
}

function cerrarFicha() {
  document.getElementById('ficha-modal').classList.add('hidden');
}

let fichaChart = null;
function abrirFicha(cid) {
  const u = DATA.usuarios.find(x => x.cid === cid);
  if (!u) return;
  const months = DATA.meta.ventana;
  const months_labels = months.map(mesShort);
  const totalEntregados = months.reduce((s,m) => s + (u.ent_mes[m]||0), 0);
  const totalDevoluciones = months.reduce((s,m) => s + (u.dev_mes[m]||0), 0);
  const totalPedidos = u.total_pedidos;
  const pctDevTotal = totalEntregados > 0 ? ((totalDevoluciones/(totalEntregados+totalDevoluciones))*100).toFixed(1) : 0;
  // Últimos 3 meses (cronológicos)
  const last3 = months.slice(-3);
  const last3_ent = last3.reduce((s,m) => s + (u.ent_mes[m]||0), 0);
  const last3_dev = last3.reduce((s,m) => s + (u.dev_mes[m]||0), 0);
  const last3_ped = last3.reduce((s,m) => s + (u.ped_mes[m]||0), 0);
  const last3_pct = last3_ent > 0 ? ((last3_dev/(last3_ent+last3_dev))*100).toFixed(1) : 0;

  const rows = months.map((m, i) => {
    const ent = u.ent_mes[m]||0, dev = u.dev_mes[m]||0, ped = u.ped_mes[m]||0;
    const pct = ped > 0 ? ((dev/ped)*100).toFixed(1) : 0;
    let tend = '—', tendCol = 'text-slate-500';
    if (i > 0) {
      const prevPed = u.ped_mes[months[i-1]]||0;
      if (prevPed > 0) {
        const delta = ((ped - prevPed) / prevPed * 100);
        if (Math.abs(delta) >= 10) {
          tend = (delta > 0 ? '▲' : '▼') + Math.abs(delta).toFixed(0) + '%';
          tendCol = delta > 0 ? 'text-green-400' : 'text-red-400';
        }
      }
    }
    return `<tr class="border-b border-white/5">
      <td class="py-1.5 text-slate-200">${mesShort(m)}</td>
      <td class="text-right font-mono">${fmt(ent)}</td>
      <td class="text-right font-mono">${fmt(dev)}</td>
      <td class="text-right font-mono font-semibold">${fmt(ped)}</td>
      <td class="text-right font-mono ${pct>15?'text-orange-400':pct>10?'text-yellow-400':'text-slate-400'}">${pct}%</td>
      <td class="text-center"><span class="pill ${tierColor[u.nivel]}">${u.nivel==='Sin clasificar'?'Sin nivel':u.nivel}</span></td>
      <td class="text-center font-mono text-xs ${tendCol}">${tend}</td>
    </tr>`;
  }).join('');

  document.getElementById('ficha-content').innerHTML = `
    <div class="card p-4 mb-3">
      <div class="flex items-start gap-3">
        <div class="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500/40 to-blue-700/40 border border-cyan-500/30 flex items-center justify-center text-sm font-bold flex-shrink-0">${initials(u.nombre)}</div>
        <div class="flex-1">
          <h3 class="text-lg font-bold">${tc(u.nombre)||'—'}</h3>
          <div class="text-xs text-slate-400">${u.email||'—'}</div>
          <div class="mt-1.5"><span class="pill ${tierColor[u.nivel]}">${u.nivel==='Sin clasificar'?'Sin nivel':u.nivel}</span></div>
        </div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
        <div><div class="text-xl font-bold neon-cyan">${fmt(last3_ped)}</div><div class="text-[9px] uppercase tracking-wider text-slate-500">Total ventana</div></div>
        <div><div class="text-xl font-bold">${fmt(u.ped_mes[months[months.length-1]]||0)}</div><div class="text-[9px] uppercase tracking-wider text-slate-500">${mesShort(months[months.length-1])}</div></div>
        <div><div class="text-xl font-bold ${last3_pct>15?'text-orange-400':last3_pct>10?'text-yellow-400':'neon-green'}">${last3_pct}%</div><div class="text-[9px] uppercase tracking-wider text-slate-500">% Dev.</div></div>
        <div><div class="text-xl font-bold">${u.n_tiendas}</div><div class="text-[9px] uppercase tracking-wider text-slate-500">Tiendas</div></div>
        <div><div class="text-sm font-bold leading-tight">${(u.paises_unicos||[]).map(p=>flag(p)+' '+p).join('<br>')||'—'}</div><div class="text-[9px] uppercase tracking-wider text-slate-500 mt-0.5">Países</div></div>
      </div>
    </div>

    <div class="card p-4 mb-3">
      <h4 class="text-sm font-semibold mb-1">Historial por mes</h4>
      <div class="text-[11px] text-slate-500 mb-2">Pedidos VIP = Entregados + Devoluciones</div>
      <table class="w-full text-xs">
        <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10">
          <tr><th class="text-left py-2">Mes</th><th class="text-right">Entregados</th><th class="text-right">Devoluciones</th><th class="text-right">Pedidos VIP</th><th class="text-right">% Dev.</th><th class="text-center">Nivel mes</th><th class="text-center">Tend.</th></tr>
        </thead>
        <tbody>
          ${rows}
          <tr class="border-b border-white/10 bg-white/[0.02]">
            <td class="py-2 font-semibold neon-cyan">Total general</td>
            <td class="text-right font-mono font-semibold">${fmt(totalEntregados)}</td>
            <td class="text-right font-mono font-semibold">${fmt(totalDevoluciones)}</td>
            <td class="text-right font-mono font-semibold">${fmt(totalPedidos)}</td>
            <td class="text-right font-mono font-semibold">${pctDevTotal}%</td>
            <td></td><td></td>
          </tr>
          <tr class="bg-amber-500/10">
            <td class="py-2 font-semibold neon-yellow">Últimos 3 meses activos</td>
            <td class="text-right font-mono font-semibold neon-yellow">${fmt(last3_ent)}</td>
            <td class="text-right font-mono font-semibold neon-yellow">${fmt(last3_dev)}</td>
            <td class="text-right font-mono font-semibold neon-yellow">${fmt(last3_ped)}</td>
            <td class="text-right font-mono font-semibold neon-yellow">${last3_pct}%</td>
            <td></td><td></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card p-4 mb-3">
      <h4 class="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Evolución pedidos VIP</h4>
      <canvas id="ficha-chart" height="140"></canvas>
    </div>

    <div class="card p-4">
      <h4 class="text-sm font-semibold mb-2">Tiendas vinculadas (${(u.tiendas_detalle||[]).length})</h4>
      ${u.sin_tienda ? '<div class="text-sm text-red-400">⚠ Este contacto no tiene ninguna Tienda 1..10 cargada en GHL.</div>' : `
      <table class="w-full text-xs">
        <thead class="text-[10px] text-slate-500 uppercase tracking-wider border-b border-white/10">
          <tr><th class="text-left py-2">Email</th><th class="text-left">País</th><th class="text-left">Primera vez (en datos)</th></tr>
        </thead>
        <tbody>
          ${(u.tiendas_detalle||[]).map(t => `<tr class="border-b border-white/5">
            <td class="py-2 text-slate-200">${t.email}</td>
            <td class="text-slate-300">${flag(t.pais||'')} ${t.pais||'—'}</td>
            <td class="text-slate-400 font-mono text-xs">${t.primera_vez||'—'}</td>
          </tr>`).join('')}
        </tbody>
      </table>`}
    </div>
  `;
  document.getElementById('ficha-modal').classList.remove('hidden');

  if (!u.sin_tienda) {
    if (fichaChart) fichaChart.destroy();
    fichaChart = new Chart(document.getElementById('ficha-chart'), {
      type: 'line',
      data: {
        labels: months_labels,
        datasets: [{
          label: 'Pedidos VIP',
          data: months.map(m => u.ped_mes[m]||0),
          borderColor: '#a78bfa', backgroundColor: 'rgba(167,139,250,0.15)',
          borderWidth: 2, tension: 0.3, fill: true, pointRadius: 5, pointBackgroundColor: '#a78bfa',
        }]
      },
      options: {
        plugins: { legend: { labels: { color:'#cbd5e1' } } },
        scales: {
          y: { ticks: {color:'#94a3b8'}, grid:{color:'rgba(255,255,255,0.05)'} },
          x: { ticks: {color:'#94a3b8'}, grid:{display:false} }
        }
      }
    });
  }
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrarFicha(); });

function wireConsulta() {
  const inp = document.getElementById("consulta-input");
  const out = document.getElementById("consulta-result");
  out.innerText = "Escribe algo para buscar.";
  inp.oninput = e => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) { out.innerText = "Escribe algo para buscar."; return; }
    const hits = DATA.usuarios.filter(u =>
      (u.nombre||'').toLowerCase().includes(q) ||
      (u.email||'').toLowerCase().includes(q) ||
      (u.cid||'').toLowerCase().includes(q)
    ).slice(0,5);
    if (!hits.length) { out.innerText = "Sin coincidencias."; return; }
    out.innerHTML = hits.map(u => `
      <div class="card p-4 mb-3">
        <div class="flex justify-between items-baseline mb-2">
          <div><div class="font-semibold text-slate-200">${tc(u.nombre)||'—'}</div>
               <div class="text-xs text-slate-500">${u.email||''} · <code class="text-[10px]">${u.cid}</code></div></div>
          <span class="pill ${tierColor[u.nivel]}">${u.nivel}</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
          ${DATA.meta.ventana.map(m => `<div><div class="text-slate-500">${m}</div><div class="font-mono text-slate-200">${fmt(u.ped_mes[m])}</div></div>`).join('')}
        </div>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs mt-3">
          <div><div class="text-slate-500">Top-2</div><div class="font-mono text-slate-200">${fmt(u.suma_top2)}</div></div>
          <div><div class="text-slate-500">Top-3</div><div class="font-mono text-slate-200">${fmt(u.suma_top3)}</div></div>
          <div><div class="text-slate-500">Meses con ventas</div><div class="font-mono text-slate-200">${u.active}/${DATA.meta.ventana.length}</div></div>
          <div><div class="text-slate-500">N° tiendas</div><div class="font-mono text-slate-200">${u.n_tiendas}</div></div>
          <div><div class="text-slate-500">Programa</div><div class="font-mono text-slate-200 text-[10px]">${u.programa}</div></div>
        </div>
      </div>`).join('');
  };
  inp.focus();
}

function drawCharts() {
  const d = DATA.distribucion;
  // 1. Distribución VIP (donut)
  new Chart(document.getElementById("chart-donut"), {
    type: 'doughnut',
    data: {
      labels: TIER_ORDER.filter(t=>d[t].n>0).map(t => t==='Sin clasificar'?'Sin nivel':t),
      datasets: [{
        data: TIER_ORDER.filter(t=>d[t].n>0).map(t=>d[t].n),
        backgroundColor: TIER_ORDER.filter(t=>d[t].n>0).map(t=>TIER_COLORS_HEX[t]),
        borderWidth: 0,
      }]
    },
    options: { plugins: { legend: { position:'right', labels:{ color:'#cbd5e1', font:{size:11} } } } }
  });

  // 2. Semáforo general (bar con 4 barras)
  new Chart(document.getElementById("chart-semaforo"), {
    type: 'bar',
    data: {
      labels: ['Verde', 'Amarillo', 'Rojo', 'Sin actividad'],
      datasets: [{
        data: [DATA.semaforo.verde, DATA.semaforo.amarillo, DATA.semaforo.rojo, DATA.semaforo.sin_actividad],
        backgroundColor: ['#4ade80', '#facc15', '#f87171', '#64748b'],
        borderRadius: 4,
      }]
    },
    options: {
      plugins:{ legend:{display:false} },
      scales: {
        y: { ticks: {color:'#94a3b8'}, grid:{color:'rgba(255,255,255,0.05)'} },
        x: { ticks: {color:'#94a3b8'}, grid:{display:false} }
      }
    }
  });

  // 3. Evolución pedidos por mes (line + área)
  const months = DATA.meta.ventana;
  new Chart(document.getElementById("chart-evolucion"), {
    type: 'line',
    data: {
      labels: months.map(mesShort),
      datasets: [{
        label: 'Pedidos VIP',
        data: months.map(m => DATA.pedidos_por_mes[m] || 0),
        borderColor: '#818cf8',
        backgroundColor: 'rgba(129,140,248,0.15)',
        borderWidth: 2,
        tension: 0.35,
        fill: true,
        pointRadius: 4,
        pointBackgroundColor: '#818cf8',
      }]
    },
    options: {
      plugins: { legend: { labels: { color:'#cbd5e1' } } },
      scales: {
        y: { ticks: {color:'#94a3b8'}, grid:{color:'rgba(255,255,255,0.05)'} },
        x: { ticks: {color:'#94a3b8'}, grid:{display:false} }
      }
    }
  });

  // 4. Actividad en ventana (bar — usuarios con ventas por mes)
  new Chart(document.getElementById("chart-actividad"), {
    type: 'bar',
    data: {
      labels: months.map(mesShort),
      datasets: [{
        data: months.map(m => DATA.activos_por_mes[m] || 0),
        backgroundColor: '#a5b4fc',
        borderRadius: 4,
      }]
    },
    options: {
      plugins:{ legend:{display:false} },
      scales: {
        y: { ticks: {color:'#94a3b8'}, grid:{color:'rgba(255,255,255,0.05)'} },
        x: { ticks: {color:'#94a3b8'}, grid:{display:false} }
      }
    }
  });
}

render();
</script>

<!-- Twemoji: renderiza emojis (banderas) como imágenes para que se vean
     idéntico en Mac/Windows/Linux/móvil. Sin esto, Windows muestra los
     emojis de banderas como letras "Regional Indicator" (ej. "🇨🇴" → "CO"). -->
<script src="https://cdn.jsdelivr.net/npm/@twemoji/api@15.1.0/dist/twemoji.min.js" crossorigin="anonymous"></script>
<style>img.twemoji{height:1em;width:auto;vertical-align:-0.125em;display:inline-block;margin:0 1px}</style>
<script>
(function(){
  if (!window.twemoji) return;
  const opts = {className: 'twemoji', folder: 'svg', ext: '.svg'};
  const parse = node => { try { twemoji.parse(node, opts); } catch(e){} };
  parse(document.body);
  // Re-parsear contenido dinámico (cambios de tab, filtros, búsqueda)
  new MutationObserver(muts => {
    for (const m of muts) for (const n of m.addedNodes)
      if (n.nodeType === 1) parse(n);
  }).observe(document.body, {childList: true, subtree: true});
})();
</script>
</body>
</html>
"""


def main():
    print("Generando dashboard.html...")
    data = compute_all()
    html_str = render_html(data).replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False, default=str))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"✓ {OUT}")
    print(f"  Usuarios totales: {data['stats']['usuarios_totales']}")
    print(f"  Clasificados:     {data['stats']['clasificados_vip']}")
    print(f"  Multi-país:       {data['stats']['multi_pais']}")
    print(f"  Activos 2 meses:  {data['stats']['activos_2_meses']}")
    print(f"  Desaparecidos:    {data['stats']['desaparecidos']}")
    print(f"  Recuperados:      {data['stats']['recuperados']}")


if __name__ == "__main__":
    main()
