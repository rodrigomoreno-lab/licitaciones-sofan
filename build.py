#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera index.html del Sistema de Licitaciones SOFAN (versión responsiva + editor).
Consulta la API de Mercado Público (ChileCompra), embebe la lista completa de
licitaciones activas para reclasificación en vivo, y trae el detalle de las que
coinciden con las palabras clave. El ticket se lee de la variable MP_TICKET.
"""
import os, json, time, re, unicodedata, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

TICKET = os.environ.get("MP_TICKET", "").strip()
if not TICKET:
    raise SystemExit("Falta MP_TICKET (configúralo como secret del repo).")

CHILE = timezone(timedelta(hours=-4))
NOW = datetime.now(CHILE)
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
UPDATED = f"{DIAS[NOW.weekday()]} {NOW.day:02d} de {MESES[NOW.month-1]} {NOW.year}, {NOW.strftime('%H:%M')} hrs (hora de Chile)"
NOWISO = NOW.strftime("%Y-%m-%dT%H:%M:%S-04:00")
HOY = NOW.replace(tzinfo=None)

CONFIG = {
 "lineas": {
  "Publicidad y medios": {"color":"#7c4dff","keywords":["medios publicitarios","publicidad en television","servicios relacionados con la television","avisos en television","publicidad en radio","servicios relacionados con la radio","administracion de radioemisoras","avisos en radio","publicidad en internet","publicidad en periodicos","servicios audiovisuales","capsulas audiovisuales","capsulas de video","capsulas radiales","diseno grafico","servicios de diagramacion","diseno de pagina web","diseno sitio web","produccion de video","campanas comunicacionales","campana comunicacional","campanas de marketing","plan de medios","planes de medios","servicios de diseno grafico","audiovisual","lengua de senas","lenguaje de senas","audio visuales","produccion expo rural","diseno editorial","apoyo comunicacional","procesos creativos","produccion capsulas","campana redes sociales","plan medios nacional","produccion piezas","plan medios fndr","produccion videos tutoriales","videos explicativos","accesibilidad audiovisual","diseno piezas","actualizacion identidad visual","plan medios","videos difusion","plan avisaje","agencia publicidad","asesoria comunicacion digital","asesoria comunicaciones","animacion","animacion digital","produccion de eventos"]},
  "Servicios laborales": {"color":"#00897b","keywords":["servicio de promocion y planificacion de empleo","servicio de digitacion de datos","servicios de evaluacion de curriculum vitae","personal administrativo temporal","servicios profesionales","inclusion laboral","servicios de contratacion de personal"]},
  "Inclusion": {"color":"#e53935","keywords":["inclusion laboral","inclusion","discapacidad","discapacitados","accesibilidad universal","educacion de adultos"]},
  "Capacitacion": {"color":"#1e88e5","keywords":["capacitacion","entrenamiento"]}
 },
 "negativas_globales": ["emulsion","asfalto","medio de contraste","temozolomida","proteccion personal","epp","vehiculo","videolaparoscopia","gestion documental","topografic","construccion accesibilidad"]
}
PER_LINEA = int(os.environ.get("PER_LINEA","8"))

def norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii","ignore").decode().lower()
    return re.sub(r"\s+"," ", s)

def api(url, intentos=4):
    for _ in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(6)
    return None

def fetch_activas():
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?estado=activas&ticket={TICKET}"
    for _ in range(5):
        d = api(url, 1)
        if d and "Listado" in d:
            return d["Listado"]
        time.sleep(8)
    return []

def fetch_detalle(codigo):
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={urllib.parse.quote(codigo)}&ticket={TICKET}"
    d = api(url, 3)
    return d["Listado"][0] if d and d.get("Listado") else None

lst = fetch_activas()
# RAW: lista completa para reclasificación en vivo
RAW = [{"c": x.get("CodigoExterno"), "n": x.get("Nombre")} for x in lst if x.get("CodigoExterno")]

NEG = CONFIG["negativas_globales"]
lk = {ln: [norm(k) for k in d["keywords"]] for ln,d in CONFIG["lineas"].items()}
def clasifica(nombre):
    n = norm(nombre)
    if any(neg in n for neg in NEG): return None, None
    for ln, kws in lk.items():
        for kw in kws:
            if kw in n: return ln, kw
    return None, None

por_linea = {ln: [] for ln in lk}
for it in lst:
    ln, kw = clasifica(it.get("Nombre",""))
    if ln:
        por_linea[ln].append(it.get("CodigoExterno"))

# DET: detalle de una muestra por línea (descartando cerradas)
DET = {}
for ln, codigos in por_linea.items():
    n = 0
    for c in codigos:
        if n >= PER_LINEA: break
        L = fetch_detalle(c); time.sleep(0.4)
        if not L: continue
        f = L.get("Fechas") or {}; cierre = f.get("FechaCierre"); comp = L.get("Comprador") or {}
        try:
            if cierre and datetime.fromisoformat(cierre.split(".")[0]) < HOY: continue
        except Exception: pass
        DET[c] = {"organismo": comp.get("NombreOrganismo"), "region": (comp.get("RegionUnidad") or "").strip(),
                  "estado": L.get("Estado"), "cierre": cierre, "monto": L.get("MontoEstimado"), "tipo": L.get("Tipo")}
        n += 1

print(f"Activas: {len(RAW)} | con detalle: {len(DET)}")

tpl = open(os.path.join(os.path.dirname(__file__), "template.html"), encoding="utf-8").read()
html = (tpl.replace("__RAW__", json.dumps(RAW, ensure_ascii=False))
           .replace("__DET__", json.dumps(DET, ensure_ascii=False))
           .replace("__CFG__", json.dumps(CONFIG, ensure_ascii=False))
           .replace("__UPDATED__", UPDATED)
           .replace("__NOWISO__", NOWISO))
open(os.path.join(os.path.dirname(__file__), "index.html"), "w", encoding="utf-8").write(html)
print("index.html generado.")
