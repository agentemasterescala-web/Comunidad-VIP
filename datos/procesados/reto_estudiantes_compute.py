#!/usr/bin/env python3
"""reto_estudiantes_compute.py — Seguimiento del "Reto Máster Escala" (ESTUDIANTES).

NO es el concurso VIP (eso es concurso_compute.py → concurso_ranking.json). Este
reto, impulsado por Iván, es para los ESTUDIANTES de Master Escala: mide la
EVOLUCIÓN de ventas en 3 momentos —septiembre (línea base, pre-reto), octubre y
noviembre (los 60 días del reto)— y la cruza con su participación en Skool.

Fuentes (las mismas del pipeline, reusadas; aquí no se recalcula Dropi):
  · ventas_periodos.json          ventas por email×país×periodo (consolidar_excel)
  · ghl_contacts_raw.json         contactos GHL → quién es estudiante/participante
  · reto_estudiantes_config.json  nombre, periodos, tags, textos (editable)
  · reto_participacion.csv        OPCIONAL: frecuencia en Skool por email
                                  (email,frecuencia[,posts_semana]) — tally manual

Dos poblaciones (decisión del dueño: "ambos, comparando"):
  · PARTICIPANTES  → contactos con el tag `reto master escala` (lo aplica el form
                     de inscripción en GHL). Hoy puede estar vacío hasta que
                     corran los fills; el script degrada bien.
  · UNIVERSO       → estudiantes de Master Escala (tag `escala`), como referencia
                     de "participó vs no participó".

El puente participante↔ventas es el EMAIL. Un vendedor puede tener varios
contactos GHL que comparten correo de ventas: se agrupan (union-find) para no
contar dos veces la misma venta de Dropi (mismo criterio que el concurso).

Escribe reto_estudiantes_ranking.json. El backend del Dashboard_GC lo sirve:
público → uuid opaco + alias + métricas; equipo logueado → además contact_id.
Idempotente: reconstruye todo en cada corrida.
"""
import os, csv, json, unicodedata
from datetime import datetime, timezone

import generar_dashboard as G          # extract_tiendas, TAG_MASTER
import concurso_compute as CC          # alias_de, opaco, _elegir_nombre, _nombre_de_email

HERE = os.path.dirname(os.path.abspath(__file__))
PERIODOS = os.path.join(HERE, "ventas_periodos.json")
RAW = os.path.join(HERE, "ghl_contacts_raw.json")
CONFIG = os.path.join(HERE, "reto_estudiantes_config.json")
PARTICIPACION = os.path.join(HERE, "reto_participacion.csv")
OUT = os.path.join(HERE, "reto_estudiantes_ranking.json")

# Frecuencias válidas en la hoja de participación (normalizadas).
_FREC_VALIDAS = {"diario", "semanal", "inactivo"}


# ─────────────────────────── Config (seed si falta) ──────────────────────────

def _config_por_defecto():
    return {
        "nombre": "Reto Máster Escala",
        "subtitulo": "60 días · octubre y noviembre",
        "base": "2026-09",                       # línea base (pre-reto)
        "reto_periodos": ["2026-10", "2026-11"],  # los 60 días del reto
        "tag_participante": "reto master escala",  # lo aplica el form en GHL
        "tag_programa": G.TAG_MASTER,             # "escala" = Master Escala
        "politicas": {
            "que_es": "Reto de Iván Caicedo para los estudiantes de Master Escala: "
                      "pasar a la acción, testear productos y aumentar tus ventas en "
                      "octubre y noviembre.",
            "inscripcion": "Para entrar al ranking oficial registra tu ficha del Reto "
                           "(incluye el correo con el que vendes en Dropi). Participas "
                           "publicando tus avances en Skool con la etiqueta "
                           "«Reto Máster Escala».",
            "medicion": "Se compara tu número de órdenes ENTREGADAS en septiembre "
                        "(línea base), octubre y noviembre, según los reportes "
                        "oficiales de Dropi. En caso de empate, sube quien tenga el "
                        "menor % de devolución (devueltas ÷ movilizadas del reporte). "
                        "Se muestra tu evolución mes a mes.",
            "participacion": "Además de las ventas, se mide tu constancia en la "
                             "comunidad: quién reporta a diario, semanal o dejó de "
                             "participar.",
            "fuente": "Fuente de ventas: reportes oficiales de Dropi. Participación: "
                      "publicaciones en la comunidad (Skool).",
        },
        "encuesta": {
            "titulo": "Cuéntanos cómo te va en el Reto (2 min)",
            "preguntas": [
                "¿El reto te está ayudando a pasar a la acción y vender? (1 a 5)",
                "¿Cuál es hoy tu principal dificultad para testear productos y vender?",
                "¿Qué tema te gustaría reforzar en la mentoría del próximo mes?",
            ],
            "url": "",   # link del form (GHL / Google Form) — se edita desde el dash
        },
    }


def cargar_config():
    if os.path.isfile(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in _config_por_defecto().items():
                cfg.setdefault(k, v)
            return cfg
        except (OSError, json.JSONDecodeError):
            pass
    cfg = _config_por_defecto()
    CC._escribir_json(CONFIG, cfg)
    return cfg


# ──────────────────────────────── Utilidades ─────────────────────────────────

def _norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s or ""))
                if not unicodedata.combining(c))
    return s.lower().strip()


def cargar_participacion():
    """Lee reto_participacion.csv → {email: {'frecuencia','posts_semana'}}.
    Columnas: email, frecuencia (diario/semanal/inactivo), posts_semana (opcional).
    Si no existe el archivo, devuelve {} (la frecuencia sale vacía)."""
    if not os.path.isfile(PARTICIPACION):
        return {}
    out = {}
    try:
        with open(PARTICIPACION, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cols = { _norm(k): (v or "").strip() for k, v in row.items() }
                em = _norm(cols.get("email", ""))
                if not em or "@" not in em:
                    continue
                frec = _norm(cols.get("frecuencia", ""))
                if frec not in _FREC_VALIDAS:
                    frec = ""
                ps = cols.get("posts_semana", "")
                try:
                    ps = int(ps) if ps else None
                except ValueError:
                    ps = None
                out[em] = {"frecuencia": frec, "posts_semana": ps}
    except OSError:
        return {}
    return out


# ──────────────────────────────── Cómputo ────────────────────────────────────

def main():
    cfg = cargar_config()
    base = cfg["base"]
    reto_periodos = list(cfg.get("reto_periodos") or [])
    tag_part = _norm(cfg.get("tag_participante"))
    tag_prog = _norm(cfg.get("tag_programa"))

    with open(PERIODOS, encoding="utf-8") as f:
        pdata = json.load(f)
    periodos = {p["id"]: p for p in pdata.get("periodos", [])}
    # Scope = base + periodos del reto, SOLO los que ya existen en los datos
    # (noviembre aún puede no estar cargado: degradamos sin romper).
    scope_ids = [pid for pid in ([base] + reto_periodos) if pid in periodos]
    scope_set = set(scope_ids)
    reto_presentes = [pid for pid in reto_periodos if pid in periodos]

    # ventas por email → {periodo: (entregados, devoluciones)}
    por_email, nombre_email = {}, {}
    for v in pdata.get("ventas_por_periodo", []):
        if v["periodo"] not in scope_set:
            continue
        por_email.setdefault(v["email"], {})[v["periodo"]] = (
            v.get("entregados", 0), v.get("devoluciones", 0), v.get("movilizadas", 0))
        if v.get("nombre") and v["email"] not in nombre_email:
            nombre_email[v["email"]] = v["nombre"]

    participacion = cargar_participacion()

    with open(RAW, encoding="utf-8") as f:
        dump = json.load(f)

    # Contactos que nos interesan: participantes del reto (tag del form) y/o
    # estudiantes de Master Escala (tag `escala`). Recogemos TODOS sus correos
    # (no solo los que tienen ventas): un participante sin ventas también cuenta.
    contactos = []
    for c in dump:
        tags = { _norm(t) for t in (c.get("tags") or []) if isinstance(t, str) }
        es_part = tag_part in tags
        es_prog = tag_prog in tags
        if not (es_part or es_prog):
            continue
        emails = {t["email"] for t in G.extract_tiendas(c)}
        emp = _norm(c.get("email"))
        if emp and "@" in emp:
            emails.add(emp)
        contactos.append({
            "cid": c["id"],
            "nombre": (c.get("contactName") or "").strip(),
            "emails": emails,
            "es_part": es_part,
            "es_prog": es_prog,
        })

    # Union-find: contactos que comparten algún correo = una sola persona.
    parent = {}
    def _find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
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
        g = grupos.setdefault(_find(ct["cid"]), {
            "cids": [], "nombres": [], "emails": set(),
            "es_part": False, "es_prog": False})
        g["cids"].append(ct["cid"])
        if ct["nombre"]:
            g["nombres"].append(ct["nombre"])
        g["emails"] |= ct["emails"]
        g["es_part"] = g["es_part"] or ct["es_part"]
        g["es_prog"] = g["es_prog"] or ct["es_prog"]

    filas = []
    for g in grupos.values():
        # Agregar ventas por periodo (cada correo del grupo cuenta UNA vez).
        ep = {pid: 0 for pid in scope_ids}   # entregadas por periodo
        dp = {pid: 0 for pid in scope_ids}   # devoluciones por periodo
        mp = {pid: 0 for pid in scope_ids}   # movilizadas por periodo (denom. del %)
        frec, posts = "", None
        for em in g["emails"]:
            pe = por_email.get(em) or {}
            for pid in scope_ids:
                if pid in pe:
                    e, d, m = pe[pid]
                    ep[pid] += e
                    dp[pid] += d
                    mp[pid] += m
            if em in participacion:          # frecuencia/engagement por correo
                info = participacion[em]
                if info.get("frecuencia"):
                    frec = info["frecuencia"]
                if info.get("posts_semana") is not None:
                    posts = info["posts_semana"]

        ent_reto = sum(ep[p] for p in reto_presentes)
        dev_reto = sum(dp[p] for p in reto_presentes)
        mov_reto = sum(mp[p] for p in reto_presentes)
        ent_base = ep.get(base, 0)
        tiene_ventas = any(ep[p] or dp[p] for p in scope_ids)

        # Quién entra: todo PARTICIPANTE (aunque venda 0, queremos su evolución)
        # y los estudiantes de Master Escala CON ventas (universo de referencia).
        if not g["es_part"] and not tiene_ventas:
            continue

        cand = list(g["nombres"]) + [nombre_email[e] for e in g["emails"]
                                     if e in nombre_email]
        nombre = CC._elegir_nombre(cand, g["emails"])
        cid = sorted(g["cids"])[0]
        filas.append({
            "cid": cid, "nombre": nombre,
            "es_participante": g["es_part"],
            "es_master": g["es_prog"],
            "frecuencia": frec,
            "posts_semana": posts,
            "ep": ep, "dp": dp, "mp": mp,
            "entregadas_base": ent_base,
            "entregadas_reto": ent_reto, "devoluciones_reto": dev_reto,
            "movilizadas_reto": mov_reto,
            # Desempate coherente con el concurso: MENOR % de devolución del
            # reporte de Dropi (devueltas ÷ movilizadas), no una efectividad aparte.
            "pct_dev_reto": (dev_reto / mov_reto) if mov_reto else 1.0,
            "delta_reto": ent_reto - ent_base,   # crecimiento vs base (informativo)
        })

    # Orden: órdenes ENTREGADAS en la ventana del reto (oct+nov) desc; desempate
    # por MENOR % de devolución asc; luego nombre. (Mismo criterio que el concurso.)
    filas.sort(key=lambda r: (-r["entregadas_reto"], r["pct_dev_reto"],
                              r["nombre"].lower()))

    ranking = []
    for i, r in enumerate(filas, 1):
        ranking.append({
            "uuid": CC.opaco(r["cid"]), "alias": CC.alias_de(r["nombre"]),
            "pos": i,
            "es_participante": r["es_participante"], "es_master": r["es_master"],
            "frecuencia": r["frecuencia"], "posts_semana": r["posts_semana"],
            "ep": r["ep"], "dp": r["dp"], "mp": r["mp"],
            "entregadas_base": r["entregadas_base"],
            "entregadas_reto": r["entregadas_reto"],
            "devoluciones_reto": r["devoluciones_reto"],
            "movilizadas_reto": r["movilizadas_reto"],
            "pct_dev_reto": round(r["pct_dev_reto"], 4),
            "delta_reto": r["delta_reto"],
            # Solo equipo logueado (el endpoint público los quita):
            "_cid": r["cid"], "_nombre": r["nombre"],
        })

    participantes = [r for r in ranking if r["es_participante"]]
    corte = pdata.get("corte")
    ultimo = periodos.get(reto_presentes[-1]) if reto_presentes else periodos.get(base)

    out = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "nombre": cfg["nombre"], "subtitulo": cfg["subtitulo"],
        "base": base, "reto_periodos": reto_periodos,
        "periodos_scope": [periodos[p] for p in scope_ids],
        "reto_presentes": reto_presentes,
        "ultimo_periodo": ultimo, "corte": corte,
        "politicas": cfg["politicas"], "encuesta": cfg["encuesta"],
        "total_universo": len(ranking),
        "total_participantes": len(participantes),
        "ranking": ranking,
    }
    CC._escribir_json(OUT, out)

    print(f"✅ reto_estudiantes_ranking.json · scope={scope_ids} · "
          f"universo={len(ranking)} · participantes(tag)={len(participantes)}")
    for r in ranking[:5]:
        ev = " → ".join(f"{p[-2:]}:{r['ep'].get(p,0)}" for p in scope_ids)
        print(f"   {r['pos']}º {r['alias']:20} reto={r['entregadas_reto']:>6}  "
              f"[{ev}]  {'PART' if r['es_participante'] else ''}")


if __name__ == "__main__":
    main()
