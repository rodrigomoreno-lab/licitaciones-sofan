#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera index.html del Sistema de Licitaciones SOFAN.
Consulta la API de Mercado Publico (ChileCompra), clasifica por linea de negocio
y construye el panel. El ticket se lee de la variable de entorno MP_TICKET.
Ejecutado automaticamente por GitHub Actions.
"""
import os, json, time, re, unicodedata, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

TICKET = os.environ.get("MP_TICKET", "").strip()
if not TICKET:
    raise SystemExit("Falta MP_TICKET (configuralo como secret del repo).")

CHILE = timezone(timedelta(hours=-4))
NOW = datetime.now(CHILE)
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
DIAS = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
UPDATED = f"{DIAS[NOW.weekday()]} {NOW.day:02d} de {MESES[NOW.month-1]} {NOW.year}, {NOW.strftime('%H:%M')} hrs (hora de Chile)"
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
PER_LINEA = int(os.environ.get("PER_LINEA","8"))  # detalle por linea

def norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii","ignore").decode().lower()
    return re.sub(r"\s+"," ", s)

def api(url, intentos=4):
    for i in range(intentos):
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
    if d and d.get("Listado"):
        return d["Listado"][0]
    return None

# 1. Traer y clasificar
lst = fetch_activas()
NEG = CONFIG["negativas_globales"]
lineas_kw = {ln: [norm(k) for k in d["keywords"]] for ln,d in CONFIG["lineas"].items()}
def clasifica(nombre):
    n = norm(nombre)
    if any(neg in n for neg in NEG): return None, None
    for ln, kws in lineas_kw.items():
        for kw in kws:
            if kw in n: return ln, kw
    return None, None

clasificadas = {ln: [] for ln in lineas_kw}
for it in lst:
    ln, kw = clasifica(it.get("Nombre",""))
    if ln:
        clasificadas[ln].append({"codigo": it.get("CodigoExterno"), "nombre": it.get("Nombre"), "match": kw})

# 2. Detalle (cap por linea) y descartar cerradas
res = []
for ln, items in clasificadas.items():
    n = 0
    for it in items:
        if n >= PER_LINEA: break
        L = fetch_detalle(it["codigo"]); time.sleep(0.4)
        if not L: continue
        f = L.get("Fechas") or {}; cierre = f.get("FechaCierre"); comp = L.get("Comprador") or {}
        try:
            if cierre and datetime.fromisoformat(cierre.split(".")[0]) < HOY: continue
        except Exception: pass
        res.append({"linea":ln,"codigo":it["codigo"],"match":it["match"],"nombre":L.get("Nombre"),
            "organismo":comp.get("NombreOrganismo"),"region":(comp.get("RegionUnidad") or "").strip(),
            "estado":L.get("Estado"),"cierre":cierre,"monto":L.get("MontoEstimado"),"tipo":L.get("Tipo")})
        n += 1
res.sort(key=lambda r: (r.get("cierre") or "z"))

DATA = json.dumps(res, ensure_ascii=False)
CFG = json.dumps(CONFIG, ensure_ascii=False)
print(f"Clasificadas: {sum(len(v) for v in clasificadas.values())} | con detalle vigente: {len(res)}")

# 3. Construir HTML (plantilla en archivo aparte template.html)
tpl = open(os.path.join(os.path.dirname(__file__), "template.html"), encoding="utf-8").read()
html = (tpl.replace("__DATA__", DATA).replace("__CFG__", CFG)
           .replace("__UPDATED__", UPDATED)
           .replace("__NOWISO__", NOW.strftime("%Y-%m-%dT%H:%M:%S-04:00")))
open(os.path.join(os.path.dirname(__file__), "index.html"), "w", encoding="utf-8").write(html)
print("index.html generado.")
