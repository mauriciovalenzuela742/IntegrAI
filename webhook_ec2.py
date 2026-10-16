"""IntegrAI — servicio de decisión (EC2). Expone /procesar y /clasificar.

/procesar  : texto + remitente -> RESOLVER (determinista) -> CLASIFICAR (ensemble) -> registrar
             Si NO identifica al niño -> NO registra y pide rectificar el nombre.
/clasificar: texto -> nivel + margen (sin registrar)

El enrutamiento nombre->id es DETERMINISTA: ante duda, NO adivina (pide corrección).
La verificación humana en la plataforma queda SOLO para el nivel de la rúbrica.
"""
from __future__ import annotations

import asyncio
import base64
import csv
import json
import os
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import hmac
import os as _os
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.plataforma import Plataforma
from src.resolver import Resolver, DIMINUTIVOS, normalizar, extraer_menciones, extraer_mencion
from src.marco import STOPWORDS
from src import config
from src.clasificador import Clasificador
from src.evaluacion_periodica import consolidar_nino
from src import marco
from src import marcos

JARDIN_DEMO = os.getenv("INTEGRA_JARDIN", "JAR-0001")
EDUCADORA_DEMO = os.getenv("INTEGRA_EDUCADORA", "EDU-DEMO")
BACKEND = os.getenv("BACKEND_DECISION", "ensemble")
SALA_DEMO = os.getenv("INTEGRA_SALA", "")          # "" = todo el jardín demo
# 1 = número no registrado usa el jardín demo; 0 = rechaza
FALLBACK_DEMO = os.getenv("INTEGRA_FALLBACK_DEMO", "1") == "1"

API_TOKEN = os.getenv("INTEGRA_API_TOKEN", "")
# U2: la nota pasa a conductas observables antes del ensemble (docs/EVAL_ENSEMBLE.md §5: 47 % -> 72 %)
U2_CONDUCTAS = os.getenv("U2_CONDUCTAS", "1") == "1"
MAX_MEDIA = int(os.getenv("MAX_MEDIA_BYTES", str(16 * 1024 * 1024)))
_docs = os.getenv("INTEGRA_DOCS", "0") == "1"   # Swagger solo en desarrollo

app = FastAPI(title="IntegrAI · decisión (EC2)", docs_url="/docs" if _docs else None,
              redoc_url=None, openapi_url="/openapi.json" if _docs else None)

# CORS: el dashboard estático (GitHub Pages / CloudFront) consume /api/* desde otro origen.
# Solo lectura, sin credenciales. Configurable con INTEGRA_CORS_ORIGINS (coma-separado; "*" en demo).
CORS_ORIGINS = [o.strip() for o in os.getenv("INTEGRA_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET"], allow_headers=["*"])

# --- SSE: aviso en vivo al dashboard de que llegó una observación ---
_subs: set = set()
_loop = None
_parando = False

# Mensajes AMBIGUOS pendientes de elegir por BOTÓN (homónimos): teléfono -> datos del mensaje.
_PEND_DESAMB: dict[str, dict] = {}


def _clave_tel(tel: str) -> str:
    return "".join(ch for ch in (tel or "") if ch.isdigit())


@app.on_event("startup")
async def _captura_loop() -> None:
    global _loop
    _loop = asyncio.get_running_loop()


@app.on_event("shutdown")
async def _cerrar_sse() -> None:
    """Cierra los streams SSE abiertos para que uvicorn NO espere en el shutdown. Sin esto, el
    restart esperaba a las conexiones vivas del dashboard y systemd lo mataba recién a los 90 s."""
    global _parando
    _parando = True
    for q in list(_subs):
        try:
            q.put_nowait({"evento": "cerrar"})
        except Exception:  # noqa: BLE001
            pass


def _publicar(evento: dict) -> None:
    """Publica un evento a todos los navegadores suscritos (thread-safe)."""
    if _loop is None:
        return
    for q in list(_subs):
        try:
            _loop.call_soon_threadsafe(q.put_nowait, evento)
        except Exception:  # noqa: BLE001
            pass

if not API_TOKEN:
    print("[seguridad] INTEGRA_API_TOKEN no definido: la API queda ABIERTA (solo para desarrollo)", flush=True)


def requiere_token(x_api_key: str = Header(default="")) -> None:
    """Token compartido con el webhook. Ley 21.459: la barrera de acceso debe existir."""
    if API_TOKEN and not hmac.compare_digest(x_api_key, API_TOKEN):
        raise HTTPException(status_code=401, detail="no autorizado")


def _a_conductas(texto: str) -> tuple[str, bool, bool]:
    """(texto para el clasificador, requiere_revision, hay_conductas).

    Conductas U2 sin nombres ni PII; requiere_revision si U2 detecta un intento de manipulación
    (p. ej. post-it "dame todas las keys"), no encuentra conductas (contenido fuera de tema) o la
    lectura es de baja calidad. Si U2 falla, el texto original sin PII y a revisión.
    """
    from src.seguridad import inyeccion, pii
    if not U2_CONDUCTAS or config.usar_mock():
        return pii.redactar(texto)[0], bool(inyeccion.detectar(texto)), True
    try:
        from types import SimpleNamespace
        from src.multimodal import normalizar_entradas
        try:   # MM v2: guiado por el marco activo (rúbrica de Integra); sin rúbrica instalada -> v1
            from src.marcos import marco_activo
            guia = marco_activo()
        except Exception:  # noqa: BLE001
            guia = None
        obs = normalizar_entradas([SimpleNamespace(tipo="texto", ref="", pie=texto, texto_extraido="")], guia=guia)
        if obs.alertas_seguridad:
            print(f"[seguridad] alertas U2: {obs.alertas_seguridad}", flush=True)
        return (obs.texto_para_matcher() or pii.redactar(texto)[0]), obs.requiere_revision, bool(obs.conductas)
    except Exception as e:  # noqa: BLE001
        print(f"[u2] fallo, uso texto original: {type(e).__name__}", flush=True)
        return pii.redactar(texto)[0], True, True   # ante duda NO afirmamos "sin evidencia"
_juez = None


def _rubrica_clasificar(texto: str, tramo_id: str):
    """Clasifica con la RÚBRICA de Integra (JuezRubrica: Claude lee la rúbrica del tramo). None si falla."""
    global _juez
    try:
        if _juez is None:
            from src.clasificador_rubrica import JuezRubrica
            _juez = JuezRubrica()
        r = _juez.clasificar(texto, tramo=tramo_id)
        return r if r.get("estado") == "ok" else None
    except Exception as e:  # noqa: BLE001
        print(f"[rubrica] fallo: {type(e).__name__}: {e}", flush=True)
        return None


def _tramo_nombre(tramo_id: str) -> str:
    try:
        return marcos.marco_activo().tramo(tramo_id)["nombre"]
    except Exception:  # noqa: BLE001
        return tramo_id


plat = Plataforma()
try:
    clas = Clasificador(backend=BACKEND)
except Exception as e:  # noqa: BLE001
    print(f"[clas] backend {BACKEND} falló ({e!r}); uso hibrido", flush=True)
    clas = Clasificador(backend="hibrido")

_roster_cache: dict[str, object] = {}


def _filas(jardin: str) -> list[dict]:
    if jardin not in _roster_cache:
        _roster_cache[jardin] = plat.roster_sala(id_jardin=jardin)
    return _roster_cache[jardin]  # type: ignore[return-value]


def _ctx_remitente(from_: str) -> list[dict]:
    """Rutea el número entrante -> educadora(s) + sala(s). Sin número registrado:
    usa la sala demo (FALLBACK_DEMO=1) o rechaza (0)."""
    ctx = plat.ruta_de_whatsapp(from_ or "")
    if ctx:
        return ctx
    if FALLBACK_DEMO:
        return [{"id_educadora": EDUCADORA_DEMO, "id_jardin": JARDIN_DEMO,
                 "sala_grupo": SALA_DEMO, "_fallback": True}]
    return []


def _filas_ctx(ctx: list[dict]) -> list[dict]:
    """Roster unión de las salas del remitente (dedup por id_nino+nombre)."""
    key = tuple(sorted((c.get("id_jardin"), c.get("sala_grupo")) for c in ctx))
    if key not in _roster_cache:
        vistos: dict = {}
        for c in ctx:
            for f in plat.roster_sala(id_jardin=c.get("id_jardin"), sala_grupo=c.get("sala_grupo")):
                vistos[(f["id_nino"], f.get("nombre_pila"))] = f
        _roster_cache[key] = list(vistos.values())
    return _roster_cache[key]


def _nivel_ponderado(id_nino: str) -> tuple:
    """Nivel PONDERADO del niño/a (media de sus notas por confianza) + nº de notas."""
    obs = [o for o in plat.observaciones_de(id_nino) if o.get("nivel")]
    if not obs:
        return None, 0
    num = sum(o["nivel"] * max(float(o.get("confianza") or 0.5), 0.01) for o in obs)
    den = sum(max(float(o.get("confianza") or 0.5), 0.01) for o in obs)
    return round(num / den), len(obs)


def _ack_no_identificado(palabra: str, res) -> str:
    if res.estado == "ambiguo":
        return (f"⚠️ Hay más de un niño/a con el nombre «{palabra}». "
                f"Reenvía indicando nombre y apellido (ej. «{palabra} + apellido»).")
    extra = f" (no está en la sala)" if palabra else ""
    return (f"⚠️ No pude identificar al niño/a «{palabra}»{extra}. "
            f"Por favor reenvía la observación indicando nombre y apellido.")


class Msg(BaseModel):
    from_: str = Field(alias="from")
    texto: str
    fecha: str | None = None

    class Config:
        populate_by_name = True


def _registrar_uno(nin: dict, educadora: str, texto_clas: str, revisar_u2: bool, fecha: str, metodo: str,
                   formato: str = "texto") -> dict:
    """Clasifica (rúbrica, o ensemble de respaldo) + registra UNA observación para UN niño/a.
    Además consolida su evaluación y avisa al dashboard (best-effort)."""
    edad = marco.edad_meses(nin["fecha_nacimiento"], fecha) if nin.get("fecha_nacimiento") else None
    tramo = marcos.tramo_por_edad(nin["fecha_nacimiento"], fecha) if nin.get("fecha_nacimiento") else None
    tramo_id, tramo_nom, nombre_nivel = None, "—", None
    if tramo:
        tramo_id, _sub = tramo
        tramo_nom = _tramo_nombre(tramo_id)
    rub = _rubrica_clasificar(texto_clas, tramo_id) if tramo_id else None
    if rub:
        nivel, nombre_nivel = rub["nivel"], rub["nombre_nivel"]
        requiere, margen, conf = rub["requiere_revision"], rub.get("margen", 0.0), rub.get("confianza", 0.0)
        # Evidencia: aunque decida la rúbrica, el matcher da las conductas observables (manifestaciones).
        try:
            matches = clas.matcher.matchear(texto_clas)
            dominios = sorted({m.manifestacion["dominio"] for m in matches})
        except Exception:  # noqa: BLE001
            matches, dominios = [], []
    else:   # sin rúbrica / fallo: ensemble (Laya+matcher) como respaldo
        cl = clas.clasificar(texto_clas, edad)
        nivel, requiere, margen, conf = cl.nivel, cl.requiere_revision, cl.margen, cl.confianza
        dominios, matches = cl.dominios, cl.matches
    # manipulación, sin evidencia o lectura dudosa (U2) -> siempre a la cola de la educadora
    estado = "por_verificar" if (requiere or revisar_u2) else "auto"
    oid = plat.registrar_observacion(
        id_nino=nin["id_nino"], id_educadora=educadora, fecha=fecha, formato=formato,
        nivel=nivel, nota=texto_clas, dominios=dominios,
        manifestaciones=[m.manifestacion["id"] for m in matches],
        confianza=conf, origen="whatsapp", metodo_resolucion=metodo, margen=margen, estado=estado)
    try:
        consolidar_nino(plat, nin["id_nino"], periodo=fecha)
    except Exception as e:  # noqa: BLE001
        print(f"[live] consolidar falló: {type(e).__name__}: {e}", flush=True)
    _publicar({"evento": "observacion", "id_nino": nin["id_nino"],
               "id_jardin": nin.get("id_jardin"), "sala_grupo": nin.get("sala_grupo"),
               "nivel": nivel, "estado": estado})
    # Si quedó dudoso -> a la COLA DE VERIFICACIÓN al instante (antes esperaba al cron).
    if estado != "auto":
        try:
            _encolar_si_falta(nin, educadora, nivel, margen, dominios, fecha)
        except Exception as e:  # noqa: BLE001
            print(f"[cola] encolar falló: {type(e).__name__}: {e}", flush=True)
    pond, n_notas = _nivel_ponderado(nin["id_nino"])
    return {"id_nino": nin["id_nino"], "nombre_pila": nin.get("nombre_pila", ""),
            "tramo": tramo_id, "tramo_nombre": tramo_nom, "nivel": nivel, "nombre_nivel": nombre_nivel,
            "nivel_ponderado": pond, "n_notas": n_notas, "margen": margen, "metodo": metodo,
            "estado_resolucion": estado, "observacion_id": oid}


def _encolar_si_falta(nin: dict, educadora: str, nivel, margen, dominios: list, fecha: str) -> str | None:
    """Encola el caso en la COLA "por verificar" EN VIVO (sin esperar al cron).
    Idempotente: si el niño/a ya tiene un pendiente abierto, no lo duplica."""
    id_nino = nin["id_nino"]
    ya = plat.con.execute(
        "SELECT 1 FROM evaluaciones_pendientes WHERE id_nino_propuesto=? AND estado='pendiente' LIMIT 1",
        (id_nino,)).fetchone()
    if ya:
        return None
    tia = plat.educadora_de_sala(nin.get("id_jardin"), nin.get("sala_grupo")) or educadora
    evidencia = f"1 obs nueva ({fecha}) · dominios: {', '.join(dominios) or '—'}"
    pid = plat.encolar_pendiente(
        id_nino, [], nivel, "global", confianza=1.0, margen=float(margen or 0.0),
        motivo="margen_bajo", evidencia=evidencia,
        creado_en=datetime.now().isoformat(timespec="seconds"), id_educadora=tia)
    _publicar({"evento": "pendiente", "id_pendiente": pid, "id_nino": id_nino})
    return pid


def _ack_registros(registros: list[dict], pendientes: list) -> str:
    """ACK de WhatsApp. Con un niño/a mantiene el formato histórico; con varios los lista."""
    if len(registros) == 1:
        r = registros[0]
        etiqueta = f"{r['nivel']} {r['nombre_nivel']}" if r["nombre_nivel"] else f"nivel {r['nivel']}"
        ack = (f"registrado ✓ — {r['nombre_pila']} · {r['tramo_nombre']} · "
               f"promedio {r['nivel_ponderado']} ({r['n_notas']} notas) · este registro: {etiqueta}")
        if r["estado_resolucion"] != "auto":
            ack += " (quedó por confirmar)"
    else:
        partes = [f"{r['nombre_pila']} ({r['nombre_nivel'] or ('nivel ' + str(r['nivel']))})" for r in registros]
        ack = "registrado ✓ — " + " y ".join(partes)
        if any(r["estado_resolucion"] != "auto" for r in registros):
            ack += " (alguno quedó por confirmar)"
    if pendientes:
        nombres = ", ".join(f"«{m}»" for m, _ in pendientes)
        ack += f" · ⚠️ no pude identificar a {nombres} (reenvía con apellido)"
    return ack


def _procesar(from_: str, texto: str, fecha: str | None = None, formato: str = "texto") -> dict:
    fecha = fecha or date.today().isoformat()
    ctx = _ctx_remitente(from_)
    if not ctx:
        return {"ok": False, "estado": "remitente_desconocido",
                "ack": "⚠️ No reconozco este número. Pídele a tu coordinadora que lo registre."}
    filas = _filas_ctx(ctx)
    educadora = ctx[0]["id_educadora"]

    # U2 una sola vez por mensaje: conductas sin PII + controles + ¿trae una observación del desarrollo?
    texto_clas, revisar_u2, hay_conductas = _a_conductas(texto)

    # Un mensaje puede nombrar a VARIOS niños/as ("Sofía jugó bien con Camila").
    menciones = extraer_menciones(texto, filas) or [extraer_mencion(texto, filas)]
    resueltos, pendientes = [], []
    for men in menciones:
        r = Resolver(filas).resolver(men)
        (resueltos if r.estado == "resuelto" else pendientes).append((men, r))

    # Identificó al niño/a pero SIN observación (p. ej. mandó solo el nombre): NO se inventa un nivel
    # (antes quedaba un "nivel 1" espurio y contaminaba la trayectoria). Se pide la observación.
    if resueltos and not hay_conductas:
        nombres = ", ".join(sorted({(plat.nino(r.id_nino) or {}).get("nombre_pila", "") for _m, r in resueltos} - {""}))
        return {"ok": False, "estado": "sin_evidencia", "metodo": "-", "candidatos": [],
                "ack": (f"⚠️ Identifiqué a {nombres}, pero no encontré una observación del desarrollo. "
                        f"Reenvía contando qué hizo el niño/a (ej. «{nombres} saltó con los dos pies»).")}

    registros, vistos = [], set()
    for _men, r in resueltos:
        if r.id_nino in vistos:
            continue
        vistos.add(r.id_nino)
        registros.append(_registrar_uno(plat.nino(r.id_nino) or {}, educadora, texto_clas, revisar_u2,
                                        fecha, r.metodo, formato))

    if not registros:
        men0, r0 = pendientes[0]
        resp = {"ok": False, "estado": r0.estado, "metodo": r0.metodo,
                "candidatos": r0.candidatos, "ack": _ack_no_identificado(men0, r0)}
        # HOMÓNIMO: en vez de pedir que reescriba, ofrecer BOTONES con los candidatos. Se guarda el
        # mensaje pendiente para registrar cuando la educadora toque el botón (ver POST /elegir).
        if r0.estado == "ambiguo" and r0.candidatos:
            _PEND_DESAMB[_clave_tel(from_)] = {"texto_clas": texto_clas, "revisar_u2": revisar_u2,
                                               "formato": formato, "ts": time.time()}
            etiquetas = _etiquetas()
            resp["tipo"] = "elegir_nino"
            resp["texto"] = (f"Detecté {len(r0.candidatos)} niños/as con el nombre «{men0.split()[0]}» "
                             f"en tu sala. ¿A cuál te refieres?")
            resp["opciones"] = [{"id": idn, "titulo": etiquetas.get(idn, idn)[:20]}
                                for idn in r0.candidatos[:3]]
        return resp

    ack = _ack_registros(registros, pendientes)
    if len(registros) == 1:
        return {"ok": True, **registros[0], "registrados": registros, "ack": ack}
    return {"ok": True, "n": len(registros), "registrados": registros, "ack": ack}


@app.get("/health")
def health() -> dict:
    # sin jardín ni tamaño del roster (no exponer datos operativos sin autenticación)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# API DE LECTURA (solo consulta) para el dashboard — datos VIVOS de la BD.
# Privacidad: NUNCA expone nombres/apellidos ni la nota; solo códigos y niveles.
# --------------------------------------------------------------------------- #
API_DIR = Path(os.getenv("INTEGRA_HOME", str(Path(__file__).resolve().parent))) / "data"


def _catalogo(nombre: str) -> list[dict]:
    """Catálogo del repo (ruta_niveles / manifestaciones). Prioriza el CSV (mismas columnas
    que el frontend), pero cae al JSON si el CSV no está — la EC2 tiene los `.json`."""
    csv_fp = API_DIR / f"{nombre}.csv"
    if csv_fp.exists():
        with csv_fp.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    json_fp = API_DIR / f"{nombre}.json"
    if not json_fp.exists():
        return []
    data = json.loads(json_fp.read_text(encoding="utf-8"))
    if nombre == "manifestaciones":   # {id,nivel,dominio,texto} -> columnas del CSV
        return [{"id_manifestacion": d.get("id"), "nivel": d.get("nivel"),
                 "dominio": d.get("dominio"), "texto_observable": d.get("texto")} for d in data]
    return data   # ruta_niveles.json ya trae las claves que usa el frontend


def _etiqueta_nombre(filas: list[dict]) -> dict[str, str]:
    """id_nino -> etiqueta legible 'Nombre I.' = nombre de pila + inicial del 1er apellido.
    Si dos niños/as de la MISMA sala comparten "Nombre I", se alarga la inicial hasta distinguirlos
    ("Emilia Co." / "Emilia Ca."). NUNCA expone el nombre completo (dato personal del menor)."""
    from collections import defaultdict
    por_sala: dict[str, list[dict]] = defaultdict(list)
    for f in filas:
        por_sala[f.get("sala_grupo") or ""].append(f)
    out: dict[str, str] = {}
    for ns in por_sala.values():
        por_pila: dict[str, list[dict]] = defaultdict(list)
        for n in ns:
            por_pila[(n.get("nombre_pila") or "").strip()].append(n)
        for pila, kids in por_pila.items():
            aps = [(k.get("apellidos") or "").strip() for k in kids]
            if not pila or not any(aps):
                for k in kids:
                    out[k["id_nino"]] = pila or k["id_nino"]
                continue
            L = 1
            while L < 8 and len({a[:L].lower() for a in aps}) < len({a.lower() for a in aps}):
                L += 1
            for k, a in zip(kids, aps):
                out[k["id_nino"]] = f"{pila} {a[:L].capitalize()}." if a else pila
    return out


def _etiquetas() -> dict[str, str]:
    """id_nino -> etiqueta legible de TODA la plataforma (para no exponer nunca el nombre completo)."""
    filas = [dict(r) for r in plat.con.execute(
        "SELECT id_nino,nombre_pila,apellidos,sala_grupo FROM ninos").fetchall()]
    return _etiqueta_nombre(filas)


def _sql_filas(consulta: str) -> list[dict]:
    return [dict(r) for r in plat.con.execute(consulta).fetchall()]


@app.get("/api/datos")
def api_datos() -> dict:
    """Dataset completo para el dashboard (MISMAS columnas que los CSV que ya lee),
    pero leído de la BD viva: incluye JAR-EQUIPO y las observaciones de WhatsApp."""
    etiquetas = _etiquetas()
    ninos = _sql_filas(
        "SELECT id_nino,fecha_nacimiento,id_jardin,sala_grupo,fecha_ingreso FROM ninos ORDER BY id_nino")
    for n in ninos:   # solo la etiqueta legible; nunca el nombre/apellido completos
        n["nombre_visible"] = etiquetas.get(n["id_nino"], n["id_nino"])
    return {
        "ruta_niveles": _catalogo("ruta_niveles"),
        "manifestaciones": _catalogo("manifestaciones"),
        "jardines": _sql_filas(
            "SELECT id_jardin,nombre_fantasia,comuna,region FROM jardines ORDER BY id_jardin"),
        "ninos": ninos,
        "observaciones": _sql_filas(
            "SELECT id_observacion,id_nino,fecha_observacion,formato_captura,nivel_estimado "
            "FROM observaciones ORDER BY id_observacion"),
        "observacion_manifestaciones": _sql_filas(
            "SELECT id_observacion,id_manifestacion FROM observacion_manifestaciones"),
        # nivel CONSOLIDADO + alerta (rubric-aware) que produce el cron
        "evaluaciones": _sql_filas(
            "SELECT id_nino,dominio,nivel,margen,periodo,tendencia,alerta,origen "
            "FROM evaluaciones ORDER BY id_nino, periodo"),
    }


@app.get("/api/eventos")
async def api_eventos(request: Request) -> StreamingResponse:
    """Stream SSE: emite un evento cada vez que llega una observación (tiempo real)."""
    cola: asyncio.Queue = asyncio.Queue()
    _subs.add(cola)

    async def gen():
        try:
            yield "data: {\"evento\": \"hola\"}\n\n"
            while not _parando:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(cola.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if ev.get("evento") == "cerrar":
                    break
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            _subs.discard(cola)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/resumen")
def api_resumen() -> dict:
    """Conteos rápidos (cabecera/estado del dashboard)."""
    return {"ok": True, **plat.resumen()}


@app.get("/api/pendientes")
def api_pendientes(estado: str = "pendiente", limit: int = 300,
                   from_: str = Query("", alias="from")) -> dict:
    """Cola POR VERIFICAR, con su curso. Con `from=<número>` devuelve solo la de esa tía.
    Solo consulta; sin nombres."""
    sql = ("SELECT p.id_pendiente, p.id_nino_propuesto, p.id_educadora, p.nivel_propuesto, "
           "p.dominio, p.margen, p.motivo, substr(p.evidencia,1,140) AS evidencia, p.estado, "
           "p.creado_en, n.id_jardin, n.sala_grupo "
           "FROM evaluaciones_pendientes p LEFT JOIN ninos n ON n.id_nino = p.id_nino_propuesto "
           "WHERE p.estado = ?")
    params: list = [estado]
    if from_:
        ctx = plat.ruta_de_whatsapp(from_)
        edu = ctx[0]["id_educadora"] if ctx else None
        sql += " AND p.id_educadora = ?"
        params.append(edu)
    sql += " ORDER BY p.creado_en DESC LIMIT ?"
    params.append(int(limit))
    filas = [dict(r) for r in plat.con.execute(sql, tuple(params)).fetchall()]
    etiquetas = _etiquetas()
    for f in filas:
        f["nombre_visible"] = etiquetas.get(f["id_nino_propuesto"], f["id_nino_propuesto"])
    return {"ok": True, "n": len(filas), "pendientes": filas}


@app.get("/api/profesora")
def api_profesora(telefono: str = Query("")) -> dict:
    """Identifica a la profesora por su número de WhatsApp + sus cursos (login del dashboard)."""
    ctx = plat.ruta_de_whatsapp(telefono or "")
    if not ctx:
        raise HTTPException(status_code=404, detail="número no registrado")
    id_edu = ctx[0]["id_educadora"]
    tel = next((e["telefono_whatsapp"] for e in plat.educadoras_con_whatsapp()
                if e["id_educadora"] == id_edu), telefono)
    return {"id_educadora": id_edu, "telefono": tel,
            "cursos": [{"id_jardin": c["id_jardin"], "sala_grupo": c["sala_grupo"]} for c in ctx]}


@app.post("/procesar", dependencies=[Depends(requiere_token)])
def procesar(m: Msg) -> dict:
    return _procesar(m.from_, m.texto, m.fecha)

# GET /procesar eliminado: ponía la nota (datos de menores) en la URL y en los logs de acceso.


@app.post("/clasificar", dependencies=[Depends(requiere_token)])
def clasificar(texto: str, edad_meses: int | None = None) -> dict:
    cl = clas.clasificar(texto, edad_meses)
    return cl.to_dict()


# --------------------------------------------------------------------------- #
# COLA "POR VERIFICAR" (human-in-the-loop) — la tía consulta y resuelve SU cola
# --------------------------------------------------------------------------- #
@app.get("/pendientes", dependencies=[Depends(requiere_token)])
def pendientes(from_: str = Query("", alias="from")) -> dict:
    """La cola de verificación de la tía identificada por su número de WhatsApp."""
    ctx = _ctx_remitente(from_ or "")
    educadora = ctx[0]["id_educadora"] if ctx else None
    items = plat.pendientes_de(educadora) if educadora else []
    return {"ok": True, "educadora": educadora, "n": len(items),
            "pendientes": [{k: it.get(k) for k in
                            ("id_pendiente", "id_nino_propuesto", "nivel_propuesto", "margen",
                             "motivo", "evidencia", "estado", "creado_en")} for it in items]}


class ResolverPendiente(BaseModel):
    id_pendiente: str
    accion: str                      # aprobado | editado | rechazado
    nivel: int | None = None         # requerido si accion=editado
    resuelto_por: str | None = None


def _resolver_pendiente(m: "ResolverPendiente") -> dict:
    """Aprueba / edita / rechaza un pendiente. Aprobar o editar ESCRIBE en `evaluaciones`."""
    row = plat.con.execute("SELECT * FROM evaluaciones_pendientes WHERE id_pendiente=?",
                           (m.id_pendiente,)).fetchone()
    if not row:
        return {"ok": False, "error": "pendiente no encontrado"}
    d = dict(row)
    nivel = m.nivel if m.nivel is not None else d.get("nivel_propuesto")
    plat.resolver_pendiente(m.id_pendiente, m.accion, m.resuelto_por or d.get("id_educadora") or "tia",
                            id_nino=d.get("id_nino_propuesto"), nivel=nivel,
                            dominio=d.get("dominio"), cuando=datetime.now().isoformat(timespec="seconds"))
    _publicar({"evento": "resuelto", "id_pendiente": m.id_pendiente, "accion": m.accion})
    return {"ok": True, "id_pendiente": m.id_pendiente, "accion": m.accion,
            "id_nino": d.get("id_nino_propuesto"), "nivel": nivel}


@app.post("/pendiente/resolver", dependencies=[Depends(requiere_token)])
def pendiente_resolver(m: ResolverPendiente) -> dict:
    """Aprueba / edita / rechaza un pendiente (uso WhatsApp / tools)."""
    return _resolver_pendiente(m)


@app.post("/api/pendiente/resolver")
def api_pendiente_resolver(m: ResolverPendiente) -> dict:
    """Igual que /pendiente/resolver pero bajo /api/* (para el dashboard, mismo origen)."""
    return _resolver_pendiente(m)


class AjusteNivel(BaseModel):
    id_nino: str
    nivel: int
    resuelto_por: str | None = None


@app.post("/api/evaluacion")
def api_evaluacion(m: AjusteNivel) -> dict:
    """Ajuste MANUAL del nivel de un niño/a (la profesora puede corregir también los auto)."""
    nin = plat.nino(m.id_nino)
    if not nin:
        return {"ok": False, "error": "niño/a no encontrado"}
    if not 1 <= int(m.nivel) <= 9:
        return {"ok": False, "error": "nivel fuera de rango (1-9)"}
    ahora = datetime.now().isoformat(timespec="seconds")
    plat.guardar_evaluacion(m.id_nino, "global", int(m.nivel), 1.0, 1.0, periodo=ahora[:10],
                            tendencia="—", alerta=None, generado_en=ahora,
                            origen=f"manual:{m.resuelto_por or 'profesora'}")
    _publicar({"evento": "evaluacion", "id_nino": m.id_nino, "nivel": int(m.nivel)})
    return {"ok": True, "id_nino": m.id_nino, "nivel": int(m.nivel)}


# --------------------------------------------------------------------------- #
def extraer_texto_ocr(img_bytes: bytes, fmt: str = "jpeg") -> str:
    """OCR literal con Amazon Nova Pro (Bedrock). Devuelve el texto transcrito."""
    try:
        import boto3
        cliente = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
        prompt = ("Transcribe EXACTAMENTE y literalmente TODO el texto manuscrito o impreso de esta imagen "
                  "(suele ser un post-it con el nombre de un niño/a y una observación). "
                  "Devuelve SOLO el texto transcrito, sin comentarios, sin comillas.")
        r = cliente.converse(
            modelId="us.amazon.nova-pro-v1:0",
            messages=[{"role": "user", "content": [
                {"image": {"format": fmt, "source": {"bytes": img_bytes}}},
                {"text": prompt}]}],
            inferenceConfig={"maxTokens": 250, "temperature": 0.0})
        return r["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[ocr] error: {type(e).__name__}", flush=True)
        return ""


def _con_temporal(data: bytes, ext: str, fn):
    """Escribe el medio en un temporal dentro de DIR_MEDIOS, aplica `fn(ruta)` y SIEMPRE lo borra."""
    from src.seguridad.archivos import directorio_medios
    d = directorio_medios(); d.mkdir(parents=True, exist_ok=True)
    f = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir=d) as t:
            t.write(data)
            f = t.name
        return fn(f)
    finally:
        if f and _os.path.exists(f):
            _os.unlink(f)


def transcribir_audio_bytes(data: bytes, ext: str = ".ogg") -> str:
    try:
        from src.procesadores import transcribir_audio
        return _con_temporal(data, ext, transcribir_audio)
    except Exception as e:  # noqa: BLE001
        print(f"[whisper] error: {type(e).__name__}", flush=True)
        return ""


def analizar_video_bytes(data: bytes, ext: str = ".mp4") -> tuple[str, str]:
    """(texto_visual, texto_audio). Lo VISUAL es lo principal: Pegasus 1.2 describe postura, apoyo,
    control de cabeza, desplazamiento y manos con timestamps (fallback Nova 2 Lite).
    El audio (Whisper) complementa: comentarios de la tía o el nombre del niño/a."""
    def _ambos(ruta: str) -> tuple[str, str]:
        from src.multimodal.video import describir_video
        from src.procesadores import extraer_audio_video   # ruta ffmpeg que ya funciona en la EC2
        visual = describir_video(ruta).texto
        try:
            audio = extraer_audio_video(ruta)
        except Exception:  # noqa: BLE001
            audio = ""
        return visual, audio
    try:
        return _con_temporal(data, ext, _ambos)
    except Exception as e:  # noqa: BLE001
        print(f"[video] error: {type(e).__name__}", flush=True)
        return "", ""


class Eleccion(BaseModel):
    from_: str = Field(alias="from")
    id_nino: str

    class Config:
        populate_by_name = True


@app.post("/elegir", dependencies=[Depends(requiere_token)])
def elegir(m: Eleccion) -> dict:
    """La educadora TOCÓ un botón para elegir al niño/a de un homónimo. Registra la observación
    que quedó pendiente (guardada al detectar la ambigüedad) para el id_nino elegido."""
    ctx = _ctx_remitente(m.from_)
    if not ctx:
        return {"ok": False, "estado": "remitente_desconocido", "ack": "⚠️ No reconozco este número."}
    filas = _filas_ctx(ctx)
    if m.id_nino not in {f["id_nino"] for f in filas}:
        return {"ok": False, "estado": "no_en_sala", "ack": "⚠️ Ese niño/a no está en tu sala."}
    pend = _PEND_DESAMB.get(_clave_tel(m.from_))
    if not pend or (time.time() - pend["ts"]) > 900:   # 15 min para elegir
        return {"ok": False, "estado": "sin_pendiente",
                "ack": "⚠️ No tengo un caso pendiente para ese botón. Reenvía la observación."}
    nin = plat.nino(m.id_nino) or {}
    reg = _registrar_uno(nin, ctx[0]["id_educadora"], pend["texto_clas"], pend["revisar_u2"],
                         date.today().isoformat(), "elegido", pend.get("formato", "texto"))
    _PEND_DESAMB.pop(_clave_tel(m.from_), None)
    return {"ok": True, **reg, "ack": _ack_registros([reg], [])}


class MediaMsg(BaseModel):
    from_: str = Field(alias="from")
    tipo: str            # image | audio | video
    media_b64: str
    caption: str = ""

    class Config:
        populate_by_name = True


@app.post("/procesar_media", dependencies=[Depends(requiere_token)])
def procesar_media(m: MediaMsg) -> dict:
    from src.seguridad.archivos import tipo_real
    invalido = {"ok": False, "estado": "media_invalida",
                "ack": "\u26a0\ufe0f No pude procesar el archivo recibido (tipo o tama\u00f1o no permitido)."}
    if len(m.media_b64) > MAX_MEDIA * 4 // 3 + 16:   # tope antes de decodificar
        return invalido
    try:
        data = base64.b64decode(m.media_b64, validate=True)
    except Exception:
        return invalido
    real = tipo_real(data[:16])   # magic bytes, no la extensi\u00f3n ni lo que diga el cliente
    # rótulo que se guarda en observaciones.formato_captura (imagen | audio | video)
    formato = {"image": "imagen", "audio": "audio", "video": "video"}.get(m.tipo, "texto")
    if m.tipo == "audio" and real in ("ogg", "mp3", "wav", "mp4"):
        texto = transcribir_audio_bytes(data, ext=f".{real}")
    elif m.tipo == "video" and real in ("mp4", "webm"):
        visual, audio = analizar_video_bytes(data, ext=f".{real}")
        if not visual:
            return {"ok": False, "estado": "video_sin_analisis",
                    "ack": "⚠️ No pude analizar el video. Reenvíalo (máx. 16 MB) o describe lo que viste."}
        # el pie de foto y el audio van primero: ahí suele venir el nombre que usa el resolver;
        # la descripción visual (sin nombres) es la observación que se clasifica
        texto = " ".join(p for p in ((m.caption or ""), audio, visual) if p).strip()
        print(f"[media] video -> visual {len(visual)} chars, audio {len(audio)} chars", flush=True)
        return _procesar(m.from_, texto, formato=formato)
    elif m.tipo == "image" and real in ("jpeg", "png", "webp", "gif"):
        texto = extraer_texto_ocr(data, fmt=real)
    else:
        return invalido
    texto = (texto + " " + (m.caption or "")).strip()
    if not texto:
        return {"ok": False, "estado": "sin_texto",
                "ack": "\u26a0\ufe0f Recib\u00ed el archivo pero no pude leer un nombre en \u00e9l. "
                       "Reenv\u00eda con el nombre del ni\u00f1o/a (o escr\u00edbelo en el mensaje)."}
    print(f"[media] {m.tipo} -> {len(texto)} chars", flush=True)   # sin el texto (PII)
    return _procesar(m.from_, texto, formato=formato)


# --- estático (index.html del demo) como fallback en "/" ---
if _os.path.isdir("/opt/integra/www"):
    app.mount("/", StaticFiles(directory="/opt/integra/www", html=True), name="www")
