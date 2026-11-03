#!/usr/bin/env python3
"""concurso_compute.py — Ranking del "Reto Más Ventas VIP".

Calcula el ranking de vendedores de la comunidad VIP por ÓRDENES ENTREGADAS
(desempate: menor % de devolución = devueltas ÷ movilizadas, del reporte de
Dropi) en la ventana del concurso, a partir de:
  · ventas_periodos.json   (ventas por email×país×periodo, de consolidar_excel)
  · ghl_contacts_raw.json  (contactos GHL → criterio VIP, nombre, tiendas)
  · concurso_config.json   (nombre, premios, fechas, modo, políticas; editable
                            desde el Dashboard_GC)

Escribe concurso_ranking.json, que el backend del Dashboard_GC sirve:
  · al público, SOLO: uuid opaco, alias, posición, ventas, movimiento.
  · al equipo logueado, además el contact_id para enlazar al perfil VIP.

Modo:
  · "demo"  → usa config.demo.usar_periodos (ej. ["2026-09"]) como ejemplo
              visual mientras llegan los reportes quincenales reales. La vista
              lo marca como preliminar/ejemplo y el snapshot va aparte.
  · "real"  → usa los periodos cuyo [inicio,fin] caen dentro de [inicio,fin]
              del concurso.
Reconstruye todo cada corrida → idempotente.
"""
import os, json, uuid, re, unicodedata
from datetime import datetime, timezone

import generar_dashboard as G  # extract_tiendas, audiencias_de, pais_canonico

HERE = os.path.dirname(os.path.abspath(__file__))
PERIODOS = os.path.join(HERE, "ventas_periodos.json")
RAW = os.path.join(HERE, "ghl_contacts_raw.json")
CONFIG = os.path.join(HERE, "concurso_config.json")
OUT = os.path.join(HERE, "concurso_ranking.json")
# Snapshot por modo (para el movimiento ↑/↓ vs el corte anterior). El demo va
# aparte para no contaminar el histórico real.
SNAP = os.path.join(HERE, "concurso_snapshot_{modo}.json")

# Namespace fijo para UUIDs opacos (uuid5(ns, contact_id)): estable y no revela
# el id real de GHL.
_UUID_NS = uuid.UUID("a3f1c2d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d")


# ─────────────────────────── Config (seed si falta) ──────────────────────────

def _config_por_defecto():
    return {
        "nombre": "Reto Más Ventas VIP",
        "subtitulo": "Iván Caicedo premia tus ventas",
        "modo": "demo",                       # "demo" | "real"
        "inicio": "2026-10-01",               # ventana real del concurso
        "fin": "2027-03-31",
        "cierre_iso": "2027-03-31T23:59:59-05:00",
        "premios": [100000000, 20000000, 10000000],
        "metrica": "entregadas",
        "demo": {
            "usar_periodos": ["2026-09"],
            "nota": "Datos de ejemplo (septiembre) — resultados preliminares.",
        },
        "politicas": {
            "inscripcion": "Solo participan miembros VIP registrados antes del "
                           "[FECHA DE CORTE DE INSCRIPCIÓN].",
            "metrica": "La clasificación se mide por el número de ÓRDENES ENTREGADAS, "
                       "según los reportes oficiales de Dropi.",
            "fechas": "El reto corre del 1 de octubre de 2026 al 31 de marzo de "
                      "2027. Cortes y publicación de resultados: [DETALLE].",
            "desempate": "En caso de empate en órdenes entregadas, sube quien tenga "
                         "el MENOR % de devolución (devueltas ÷ movilizadas del "
                         "reporte de Dropi).",
            "pago_premios": "Forma y plazo de pago de premios: [DETALLE].",
            "descalificacion": "Causas de descalificación: [DETALLE].",
            "fuente": "Fuente de datos: reportes oficiales de Dropi.",
            "validacion": "Las posiciones y premios están sujetos a validación y "
                          "verificación de la información antes de su entrega.",
        },
    }


def cargar_config():
    if os.path.isfile(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
            # Completar claves faltantes con los defaults (no pisa lo editado).
            base = _config_por_defecto()
            for k, v in base.items():
                cfg.setdefault(k, v)
            return cfg
        except (OSError, json.JSONDecodeError):
            pass
    cfg = _config_por_defecto()
    _escribir_json(CONFIG, cfg)
    return cfg


# ──────────────────────────────── Utilidades ─────────────────────────────────

def _escribir_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def alias_de(nombre):
    """Nombre corto que protege la privacidad: primer nombre + inicial del
    apellido (ej. 'daniel giovanni calderon' → 'Daniel C.'). Sin apellido
    completo. Si no hay apellido, solo el primer nombre."""
    toks = [t for t in (nombre or "").strip().split() if any(c.isalpha() for c in t)]
    if not toks:
        return "Participante"
    primero = toks[0].capitalize()
    if len(toks) == 1:
        return primero
    inicial = next((c for c in toks[-1] if c.isalpha()), "")
    return f"{primero} {inicial.upper()}." if inicial else primero


def opaco(cid):
    return str(uuid.uuid5(_UUID_NS, cid or ""))


def _tcase(s):
    """Title-case respetando acentos ('JOSÉ maría' → 'José María')."""
    return " ".join(w[:1].upper() + w[1:].lower() if w else w
                    for w in (s or "").split())


def _nombre_de_email(email):
    """Deriva un nombre legible del correo cuando no hay nombre real
    ('riano.dylanwork@outlook.com' → 'Riano Dylanwork')."""
    local = (email or "").split("@")[0]
    local = re.sub(r"[._\-]+", " ", local)
    local = re.sub(r"\d+", "", local).strip()
    return _tcase(local)


def _elegir_nombre(nombres, emails):
    """Mejor nombre legible del grupo: prefiere un nombre real (con apellido),
    descarta correos; si no hay, lo deriva del correo."""
    cands = []
    for n in nombres:
        n = " ".join((n or "").split())
        if n and "@" not in n:
            cands.append(n)
    # Prioriza: con apellido (≥2 tokens) → más tokens → más largo.
    cands.sort(key=lambda n: (0 if len(n.split()) >= 2 else 1,
                              -len(n.split()), -len(n)))
    if cands:
        return _tcase(cands[0])
    for em in sorted(emails):
        d = _nombre_de_email(em)
        if d:
            return d
    return ""


# ──────────────────────────────── Cómputo ────────────────────────────────────

def periodos_en_scope(cfg, periodos):
    """Lista de ids de periodo que entran en el ranking según el modo."""
    if cfg.get("modo") == "demo":
        ids = set(cfg.get("demo", {}).get("usar_periodos", []))
        return [p for p in periodos if p["id"] in ids]
    # real: periodos cuyo rango cae dentro de la ventana del concurso.
    ini, fin = cfg["inicio"], cfg["fin"]
    return [p for p in periodos if p["inicio"] >= ini and p["fin"] <= fin]


def main():
    cfg = cargar_config()

    with open(PERIODOS, encoding="utf-8") as f:
        pdata = json.load(f)
    periodos = pdata.get("periodos", [])
    scope = periodos_en_scope(cfg, periodos)
    scope_ids = {p["id"] for p in scope}

    # ventas por email → {periodo: (entregados, devoluciones)}
    por_email, nombre_email = {}, {}
    for v in pdata.get("ventas_por_periodo", []):
        if v["periodo"] not in scope_ids:
            continue
        por_email.setdefault(v["email"], {})[v["periodo"]] = (
            v.get("entregados", 0), v.get("devoluciones", 0), v.get("movilizadas", 0))
        if v.get("nombre") and v["email"] not in nombre_email:
            nombre_email[v["email"]] = v["nombre"]

    # Participantes = contactos de la comunidad VIP (mismo criterio del dash).
    with open(RAW, encoding="utf-8") as f:
        dump = json.load(f)

    # ── Participantes = contactos VIP AGRUPADOS por persona ──
    # Un mismo vendedor suele tener varios contactos en GHL que comparten el
    # mismo correo de ventas. Si se emite una fila por contacto, la misma venta
    # de Dropi se cuenta dos veces (filas duplicadas). Aquí: (1) reunimos por
    # contacto sus correos con ventas; (2) unimos contactos que comparten algún
    # correo (union-find); (3) por grupo, contamos cada correo UNA sola vez y
    # elegimos el mejor nombre legible.
    contactos = []
    for c in dump:
        tags = [t.lower() for t in (c.get("tags") or []) if isinstance(t, str)]
        if not G.audiencias_de(tags):
            continue  # fuera de la comunidad VIP
        emails = {t["email"] for t in G.extract_tiendas(c)}
        emp = (c.get("email") or "").strip().lower()
        if emp:
            emails.add(emp)
        con_ventas = {em for em in emails
                      if por_email.get(em) and any(p in por_email[em] for p in scope_ids)}
        if not con_ventas:
            continue  # VIP sin ventas en la ventana → no aparece en el ranking
        contactos.append({
            "cid": c["id"],
            "nombre": (c.get("contactName") or "").strip(),
            "emails": con_ventas,
        })

    parent = {}
    def _find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:           # path compression
            parent[x], x = root, parent[x]
        return root
    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    email_owner = {}
    for ct in contactos:
        _find(ct["cid"])
        for em in ct["emails"]:
            if em in email_owner:
                _union(ct["cid"], email_owner[em])
            else:
                email_owner[em] = ct["cid"]

    grupos = {}
    for ct in contactos:
        g = grupos.setdefault(_find(ct["cid"]),
                              {"cids": [], "nombres": [], "emails": set()})
        g["cids"].append(ct["cid"])
        if ct["nombre"]:
            g["nombres"].append(ct["nombre"])
        g["emails"] |= ct["emails"]

    filas = []
    for g in grupos.values():
        ent = dev = mov = 0
        por_per = {}   # periodo → [entregadas, devoluciones, movilizadas]
        for em in g["emails"]:             # cada correo del grupo cuenta UNA vez
            pe = por_email.get(em) or {}
            for per in scope_ids:
                if per in pe:
                    e, d, m = pe[per]
                    ent += e
                    dev += d
                    mov += m
                    acc = por_per.setdefault(per, [0, 0, 0])
                    acc[0] += e
                    acc[1] += d
                    acc[2] += m
        if ent == 0 and dev == 0:
            continue
        cand = list(g["nombres"]) + [nombre_email[e] for e in g["emails"]
                                     if e in nombre_email]
        nombre = _elegir_nombre(cand, g["emails"])
        cid = sorted(g["cids"])[0]         # representativo estable (para el UUID)
        filas.append({
            "cid": cid, "nombre": nombre,
            # "ventas netas" = ÓRDENES ENTREGADAS (aclaración del dueño: la métrica
            # del ranking es entregadas, NO entregadas − devoluciones).
            "entregadas": ent, "devoluciones": dev, "movilizadas": mov, "ventas": ent,
            "ep": {per: v[0] for per, v in por_per.items()},   # entregadas por periodo
            "dp": {per: v[1] for per, v in por_per.items()},   # devoluciones por periodo
            "mp": {per: v[2] for per, v in por_per.items()},   # movilizadas por periodo
        })

    # Orden: número de ÓRDENES ENTREGADAS desc; el que más entrega va arriba.
    # Desempate: MENOR % de devolución del reporte de Dropi = devueltas ÷
    # movilizadas (asc); luego nombre. No se recalcula nada: el % sale directo
    # de las columnas del Excel.
    def _pct_dev(r):
        return (r["devoluciones"] / r["movilizadas"]) if r["movilizadas"] else 1.0
    filas.sort(key=lambda r: (-r["entregadas"], _pct_dev(r), r["nombre"].lower()))

    ultimo = scope[-1] if scope else None
    cur_periodo = (ultimo or {}).get("id")

    # Snapshot de 2 slots por modo: 'actual' (corte vigente) y 'anterior' (corte
    # previo). El movimiento ↑/↓ se calcula contra 'anterior' (el corte anterior),
    # no contra la última corrida, así persiste hasta que entre un nuevo reporte.
    snap_path = SNAP.format(modo=cfg.get("modo", "demo"))
    snap = {}
    if os.path.isfile(snap_path):
        try:
            with open(snap_path, encoding="utf-8") as f:
                snap = json.load(f)
        except (OSError, json.JSONDecodeError):
            snap = {}
    snap_actual = snap.get("actual") or {}
    snap_anterior = snap.get("anterior") or {}
    prev_pos = snap_anterior.get("pos", {})

    ranking, nuevo_snap = [], {}
    for i, r in enumerate(filas, 1):
        u = opaco(r["cid"])
        nuevo_snap[u] = i
        antes = prev_pos.get(u)
        mov = (antes - i) if antes else 0   # + = subió, - = bajó, 0 = nuevo/igual
        ranking.append({
            "uuid": u, "alias": alias_de(r["nombre"]), "pos": i,
            "ventas": r["ventas"], "movimiento": mov, "es_nuevo": antes is None,
            "entregadas": r["entregadas"], "devoluciones": r["devoluciones"],  # publicos: desglose
            "movilizadas": r["movilizadas"],                 # denominador del % devolución
            "pct_devolucion": round(_pct_dev(r), 4),         # devueltas ÷ movilizadas (Dropi)
            "ep": r["ep"], "dp": r["dp"], "mp": r["mp"],     # por periodo (selector)
            # Solo para el equipo logueado (el endpoint público los quita):
            "_cid": r["cid"], "_nombre": r["nombre"],
            "_entregadas": r["entregadas"], "_devoluciones": r["devoluciones"],
        })

    out = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "modo": cfg.get("modo", "demo"),
        "es_demo": cfg.get("modo") == "demo",
        "nombre": cfg["nombre"],
        "subtitulo": cfg["subtitulo"],
        "premios": cfg["premios"],
        "bolsa_total": sum(cfg["premios"]),
        "cierre_iso": cfg["cierre_iso"],
        "ventana": {"inicio": cfg["inicio"], "fin": cfg["fin"]},
        "ultimo_periodo": ultimo,
        "periodos_scope": scope,
        "politicas": cfg["politicas"],
        "demo_nota": cfg.get("demo", {}).get("nota", "") if cfg.get("modo") == "demo" else "",
        "total_participantes": len(ranking),
        "ranking": ranking,
    }
    _escribir_json(OUT, out)
    # Avanzar snapshots: si cambió el corte (nuevo reporte), el 'actual' vigente
    # pasa a 'anterior' (contra él se medirá el movimiento del próximo corte).
    if snap_actual.get("periodo") and snap_actual.get("periodo") != cur_periodo:
        nueva_anterior = {"periodo": snap_actual["periodo"], "pos": snap_actual.get("pos", {})}
    else:
        nueva_anterior = snap_anterior
    _escribir_json(snap_path, {
        "actual": {"periodo": cur_periodo, "pos": nuevo_snap, "generado": out["generado"]},
        "anterior": nueva_anterior,
    })

    top = ranking[:3]
    print(f"✅ concurso_ranking.json · modo={out['modo']} · "
          f"{len(ranking)} participantes · periodos={sorted(scope_ids)}")
    for r in top:
        print(f"   {r['pos']}º {r['alias']:20} entregadas={r['entregadas']:>7} dev={r['devoluciones']:>5} mov={r['movimiento']:+d}")


if __name__ == "__main__":
    main()
