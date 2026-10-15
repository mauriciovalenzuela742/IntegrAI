"""IntegrAI — servicio de decisión (EC2). Expone /procesar y /clasificar.

/procesar  : texto + remitente -> RESOLVER (determinista) -> CLASIFICAR (ensemble) -> registrar
             Si NO identifica al niño -> NO registra y pide rectificar el nombre.
/clasificar: texto -> nivel + margen (sin registrar)

El enrutamiento nombre->id es DETERMINISTA: ante duda, NO adivina (pide corrección).
La verificación humana en la plataforma queda SOLO para el nivel de la rúbrica.
"""
from __future__ import annotations

import base64
import os
import tempfile
from datetime import date

import hmac
import os as _os
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.plataforma import Plataforma
from src.resolver import Resolver, DIMINUTIVOS, normalizar
from src.marco import STOPWORDS
from src import config
from src.clasificador import Clasificador
from src import marco

JARDIN_DEMO = os.getenv("INTEGRA_JARDIN", "JAR-0001")
EDUCADORA_DEMO = os.getenv("INTEGRA_EDUCADORA", "EDU-DEMO")
BACKEND = os.getenv("BACKEND_DECISION", "ensemble")

API_TOKEN = os.getenv("INTEGRA_API_TOKEN", "")
# U2: la nota pasa a conductas observables antes del ensemble (docs/EVAL_ENSEMBLE.md §5: 47 % -> 72 %)
U2_CONDUCTAS = os.getenv("U2_CONDUCTAS", "1") == "1"
MAX_MEDIA = int(os.getenv("MAX_MEDIA_BYTES", str(16 * 1024 * 1024)))
_docs = os.getenv("INTEGRA_DOCS", "0") == "1"   # Swagger solo en desarrollo

app = FastAPI(title="IntegrAI · decisión (EC2)", docs_url="/docs" if _docs else None,
              redoc_url=None, openapi_url="/openapi.json" if _docs else None)
if not API_TOKEN:
    print("[seguridad] INTEGRA_API_TOKEN no definido: la API queda ABIERTA (solo para desarrollo)", flush=True)


def requiere_token(x_api_key: str = Header(default="")) -> None:
    """Token compartido con el webhook. Ley 21.459: la barrera de acceso debe existir."""
    if API_TOKEN and not hmac.compare_digest(x_api_key, API_TOKEN):
        raise HTTPException(status_code=401, detail="no autorizado")


def _a_conductas(texto: str) -> str:
    """Texto para el clasificador: conductas U2 (sin nombres) o el texto original si U2 falla."""
    if not U2_CONDUCTAS or config.usar_mock():
        return texto
    try:
        from types import SimpleNamespace
        from src.multimodal import normalizar_entradas
        obs = normalizar_entradas([SimpleNamespace(tipo="texto", ref="", pie=texto, texto_extraido="")])
        return obs.texto_para_matcher() or texto
    except Exception as e:  # noqa: BLE001
        print(f"[u2] fallo, uso texto original: {type(e).__name__}", flush=True)
        return texto
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


def extraer_mencion(texto: str, filas: list[dict]) -> str:
    """Heurística determinista: busca un nombre de pila del roster (o diminutivo)
    y toma el nombre + el siguiente token SOLO si es plausible apellido (no stopword)."""
    toks = normalizar(texto).split()
    pila = {normalizar(f["nombre_pila"]) for f in filas if f.get("nombre_pila")}
    aliases = set(DIMINUTIVOS.keys())
    for i, t in enumerate(toks):
        if t in pila or t in aliases:
            nombre = [t]
            if i + 1 < len(toks) and toks[i + 1] not in STOPWORDS and len(toks[i + 1]) > 1:
                nombre.append(toks[i + 1])   # apellido plausible
            return " ".join(nombre)
    return toks[0] if toks else ""


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


def _procesar(from_: str, texto: str, fecha: str | None = None) -> dict:
    fecha = fecha or date.today().isoformat()
    filas = _filas(JARDIN_DEMO)
    res = Resolver(filas).resolver(extraer_mencion(texto, filas))

    if res.estado != "resuelto":
        return {"ok": False, "estado": res.estado, "metodo": res.metodo,
                "candidatos": res.candidatos,
                "ack": _ack_no_identificado(extraer_mencion(texto, filas), res)}

    nin = plat.nino(res.id_nino) or {}
    edad = marco.edad_meses(nin["fecha_nacimiento"], fecha) if nin.get("fecha_nacimiento") else None
    # el clasificador recibe conductas sin nombres; se guarda eso, no la nota cruda con el nombre
    texto_clas = _a_conductas(texto)
    cl = clas.clasificar(texto_clas, edad)
    estado = "por_verificar" if cl.requiere_revision else "auto"

    oid = plat.registrar_observacion(
        id_nino=res.id_nino, id_educadora=EDUCADORA_DEMO, fecha=fecha, formato="texto",
        nivel=cl.nivel, nota=texto_clas, dominios=cl.dominios,
        manifestaciones=[m.manifestacion["id"] for m in cl.matches],
        confianza=cl.confianza, origen="whatsapp", metodo_resolucion=res.metodo,
        margen=cl.margen, estado=estado)

    if estado == "auto":
        ack = f"registrado ✓ — {nin.get('nombre_pila','')} · nivel {cl.nivel}"
    else:
        ack = f"registrado ✓ — {nin.get('nombre_pila','')} · nivel {cl.nivel} (quedó por confirmar en la plataforma)"
    return {"ok": True, "id_nino": res.id_nino, "nivel": cl.nivel, "margen": cl.margen,
            "metodo": res.metodo, "estado_resolucion": estado, "observacion_id": oid,
            "ack": ack}


@app.get("/health")
def health() -> dict:
    # sin jardín ni tamaño del roster (no exponer datos operativos sin autenticación)
    return {"ok": True}


@app.post("/procesar", dependencies=[Depends(requiere_token)])
def procesar(m: Msg) -> dict:
    return _procesar(m.from_, m.texto, m.fecha)

# GET /procesar eliminado: ponía la nota (datos de menores) en la URL y en los logs de acceso.


@app.post("/clasificar", dependencies=[Depends(requiere_token)])
def clasificar(texto: str, edad_meses: int | None = None) -> dict:
    cl = clas.clasificar(texto, edad_meses)
    return cl.to_dict()


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
        return _procesar(m.from_, texto)
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
    return _procesar(m.from_, texto)


# --- estático (index.html del demo) como fallback en "/" ---
if _os.path.isdir("/opt/integra/www"):
    app.mount("/", StaticFiles(directory="/opt/integra/www", html=True), name="www")
