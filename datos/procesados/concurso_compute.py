#!/usr/bin/env python3
"""concurso_compute.py — Ranking del "Reto Más Ventas VIP".

Calcula el ranking de vendedores de la comunidad VIP por ventas NETAS
(entregadas − devoluciones) en la ventana del concurso, a partir de:
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
import os, json, uuid, unicodedata
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
        "metrica": "entregadas_menos_devoluciones",
        "demo": {
            "usar_periodos": ["2026-09"],
            "nota": "Datos de ejemplo (septiembre) — resultados preliminares.",
        },
        "politicas": {
            "inscripcion": "Solo participan miembros VIP registrados antes del "
                           "[FECHA DE CORTE DE INSCRIPCIÓN].",
            "metrica": "Se cuentan las ventas entregadas, descontando devoluciones.",
            "fechas": "El reto corre del 1 de octubre de 2026 al 31 de marzo de "
                      "2027. Cortes y publicación de resultados: [DETALLE].",
            "desempate": "En caso de empate: [CRITERIO DE DESEMPATE].",
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
            v.get("entregados", 0), v.get("devoluciones", 0))
        if v.get("nombre") and v["email"] not in nombre_email:
            nombre_email[v["email"]] = v["nombre"]

    # Participantes = contactos de la comunidad VIP (mismo criterio del dash).
    with open(RAW, encoding="utf-8") as f:
        dump = json.load(f)

    filas = []
    for c in dump:
        tags = [t.lower() for t in (c.get("tags") or []) if isinstance(t, str)]
        if not G.audiencias_de(tags):
            continue  # fuera de la comunidad VIP
        emails = {t["email"] for t in G.extract_tiendas(c)}
        emp = (c.get("email") or "").strip().lower()
        if emp:
            emails.add(emp)
        ent = dev = 0
        por_per = {}   # periodo → [entregadas, devoluciones]
        tiene = False
        for em in emails:
            pe = por_email.get(em)
            if not pe:
                continue
            for per in scope_ids:
                if per in pe:
                    e, d = pe[per]
                    ent += e
                    dev += d
                    tiene = True
                    acc = por_per.setdefault(per, [0, 0])
                    acc[0] += e
                    acc[1] += d
        if not tiene:
            continue  # VIP sin ventas en la ventana → no aparece en el ranking
        nombre = (c.get("contactName") or "").strip()
        if not nombre:
            nombre = next((nombre_email[e] for e in emails if e in nombre_email), "")
        filas.append({
            "cid": c["id"], "nombre": nombre,
            "entregadas": ent, "devoluciones": dev, "ventas": ent - dev,
            "vp": {per: e - d for per, (e, d) in por_per.items()},  # neto por periodo
        })

    # Orden: ventas netas desc, desempate por entregadas desc y nombre.
    filas.sort(key=lambda r: (-r["ventas"], -r["entregadas"], r["nombre"].lower()))

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
            "vp": r["vp"],   # neto por periodo (para el selector quincena/mes/acumulado)
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
        print(f"   {r['pos']}º {r['alias']:20} ventas={r['ventas']:>7} mov={r['movimiento']:+d}")


if __name__ == "__main__":
    main()
