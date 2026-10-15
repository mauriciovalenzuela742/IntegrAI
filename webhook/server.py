"""IntegrAI — Receptor webhook WhatsApp Cloud API (oficial de Meta).

Recibe los mensajes de Meta (texto/imagen/audio/video), los envía al servicio de
decisión (EC2: resolver + OCR/Whisper + ensemble) y responde el ACK por WhatsApp.

Incluye FAN-OUT opcional a Chatwoot y deduplicación por message-id (idempotencia).

Rutas:
  GET  /webhooks/whatsapp/{phone}   -> verificación de Meta (hub.challenge)
  POST /webhooks/whatsapp/{phone}   -> mensajes entrantes
  GET  /health                      -> liveness
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.request
from datetime import datetime

import httpx
from fastapi import BackgroundTasks, FastAPI, Request, Response

VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "")
WA_TOKEN     = os.getenv("WA_TOKEN", "")
PHONE_ID     = os.getenv("WA_PHONE_NUMBER_ID", "")
APP_SECRET   = os.getenv("WA_APP_SECRET", "")       # OBLIGATORIO: sin él se rechaza todo POST
ALLOW_UNSIGNED = os.getenv("WA_ALLOW_UNSIGNED", "0") == "1"   # solo desarrollo local
FANOUT_URL   = os.getenv("CHATWOOT_FANOUT", "")     # ej: http://chatwoot-web:3000 (tercero: requiere DPA)
BACKEND_URL  = os.getenv("INTEGRA_BACKEND", "")     # ej: https://<backend> (nunca HTTP por internet)
API_TOKEN    = os.getenv("INTEGRA_API_TOKEN", "")   # token compartido con el servicio de decisión
# Teléfonos autorizados (educadoras), separados por coma. Vacío = nadie (fail-closed).
WHITELIST    = {"".join(ch for ch in t if ch.isdigit()) for t in os.getenv("WA_WHITELIST", "").split(",") if t.strip()}
MAX_MEDIA    = int(os.getenv("MAX_MEDIA_BYTES", str(16 * 1024 * 1024)))
DRY_RUN      = os.getenv("DRY_RUN", "0") == "1"     # no envía mensajes reales
GRAPH = "https://graph.facebook.com/v21.0"

app = FastAPI(title="IntegrAI WhatsApp Webhook")
_vistos: set[str] = set()   # dedupe por message-id (idempotencia)


# --------------------------------------------------------------------------- #
def firma_valida(raw: bytes, header: str | None) -> bool:
    """Fail-closed: sin APP_SECRET no se acepta nada (salvo WA_ALLOW_UNSIGNED=1 en desarrollo)."""
    if not APP_SECRET:
        return ALLOW_UNSIGNED
    if not header or not header.startswith("sha256="):
        return False
    esperado = hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.split("=", 1)[1].strip().lower(), esperado)


def autorizado(tel: str) -> bool:
    return "".join(ch for ch in tel if ch.isdigit()) in WHITELIST


def mask(tel: str) -> str:
    d = "".join(ch for ch in tel if ch.isdigit())
    return d[:3] + "*" * max(len(d) - 6, 0) + d[-3:] if len(d) > 6 else "***"


def _headers_backend() -> dict:
    return {"X-Api-Key": API_TOKEN} if API_TOKEN else {}


async def descargar_media(media_id: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            meta = await c.get(f"{GRAPH}/{media_id}", headers={"Authorization": f"Bearer {WA_TOKEN}"})
            url = meta.json().get("url")
            if not url:
                return None
            if int(meta.json().get("file_size") or 0) > MAX_MEDIA:
                print("[media] archivo demasiado grande -> rechazado", flush=True)
                return None
            blob = await c.get(url, headers={"Authorization": f"Bearer {WA_TOKEN}"})
            return blob.content if len(blob.content) <= MAX_MEDIA else None
    except Exception as e:  # noqa: BLE001
        print(f"[media] error: {type(e).__name__}", flush=True)
        return None


async def enviar_texto(destino: str, texto: str) -> None:
    if DRY_RUN:
        print(f"[ack][DRY_RUN] -> {destino}: {texto!r}", flush=True)
        return
    if not (WA_TOKEN and PHONE_ID):
        print("[ack] sin token/phone_id -> skip", flush=True)
        return
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{GRAPH}/{PHONE_ID}/messages",
                             headers={"Authorization": f"Bearer {WA_TOKEN}"},
                             json={"messaging_product": "whatsapp", "to": destino,
                                   "type": "text", "text": {"body": texto}})
            print(f"[ack] -> {r.status_code}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[ack] error: {e!r}", flush=True)


def fanout(raw: bytes, path: str) -> None:
    if not FANOUT_URL:
        return
    try:
        req = urllib.request.Request(f"{FANOUT_URL}{path}", data=raw,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
            print(f"[fanout] chatwoot -> {r.status}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[fanout] error: {e!r}", flush=True)


def procesar_texto(de: str, texto: str) -> str:
    if not BACKEND_URL:
        return "registrado ✓ (sin backend)"
    try:
        with httpx.Client(timeout=120) as c:
            r = c.post(f"{BACKEND_URL}/procesar", json={"from": de, "texto": texto}, headers=_headers_backend())
            return r.json().get("ack") or "registrado ✓"
    except Exception as e:  # noqa: BLE001
        print(f"[backend] error: {e!r}", flush=True)
        return "⚠️ Recibí tu mensaje, pero no pude procesarlo ahora."


def procesar_media(de: str, tipo: str, blob: bytes, caption: str) -> str:
    if not BACKEND_URL:
        return "registrado ✓ (sin backend)"
    # el video va como video: el backend lo analiza visualmente (Pegasus) + audio
    # (antes iba al OCR como si fuera una imagen y fallaba)
    tipo_be = {"audio": "audio", "video": "video", "image": "image"}.get(tipo)
    if not tipo_be:
        return "⚠️ Ese tipo de archivo no se procesa. Envía texto, foto, audio o video."
    try:
        with httpx.Client(timeout=180) as c:
            r = c.post(f"{BACKEND_URL}/procesar_media",
                       json={"from": de, "tipo": tipo_be,
                             "media_b64": base64.b64encode(blob).decode(),
                             "caption": caption or ""}, headers=_headers_backend())
            return r.json().get("ack") or "registrado ✓"
    except Exception as e:  # noqa: BLE001
        print(f"[backend-media] error: {e!r}", flush=True)
        return "⚠️ Recibí el archivo, pero no pude procesarlo ahora."


# --------------------------------------------------------------------------- #
@app.get("/health")
async def health() -> dict:
    return {"ok": True, "ts": datetime.now().isoformat(timespec="seconds"),
            "fanout": bool(FANOUT_URL), "backend": bool(BACKEND_URL), "dry_run": DRY_RUN}


@app.get("/webhooks/whatsapp/{phone}")
async def verificar(phone: str, request: Request) -> Response:
    q = request.query_params
    if VERIFY_TOKEN and q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), VERIFY_TOKEN):
        return Response(content=q.get("hub.challenge", ""), media_type="text/plain")
    return Response(content="forbidden", status_code=403)


@app.post("/webhooks/whatsapp/{phone}")
async def recibir(phone: str, request: Request, bg: BackgroundTasks) -> Response:
    raw = await request.body()
    if not firma_valida(raw, request.headers.get("X-Hub-Signature-256")):
        print("[post] firma inválida", flush=True)
        return Response(content="invalid signature", status_code=403)
    bg.add_task(procesar, raw, phone, request.url.query)
    return Response(content="EVENT_RECEIVED", status_code=200)


async def procesar(raw: bytes, phone: str, query: str) -> None:
    if FANOUT_URL:
        fanout(raw, f"/webhooks/whatsapp/{phone}" + (f"?{query}" if query else ""))
    try:
        data = json.loads(raw)
    except Exception:
        return

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                wamid = msg.get("id")
                if wamid:
                    if wamid in _vistos:
                        print(f"[dup] {wamid} ya procesado -> skip", flush=True)
                        continue
                    _vistos.add(wamid)
                    if len(_vistos) > 5000:
                        _vistos.clear()

                de = msg.get("from", "")
                if not autorizado(de):
                    # número desconocido: se descarta en silencio, sin descargar medios ni responder
                    print(f"[msg] remitente no autorizado {mask(de)} -> descartado", flush=True)
                    continue
                tipo = msg.get("type", "")
                texto, media_id, caption = "", None, ""
                if tipo == "text":
                    texto = msg.get("text", {}).get("body", "")
                elif tipo in ("image", "audio", "video", "document"):
                    media_id = msg.get(tipo, {}).get("id")
                    caption = msg.get(tipo, {}).get("caption", "") or ""
                # sin PII en logs: teléfono enmascarado y solo el largo del texto
                print(f"[msg] de={mask(de)} tipo={tipo} chars={len(texto)} media={bool(media_id)}", flush=True)

                if media_id:
                    blob = await descargar_media(media_id)
                    if not blob:
                        await enviar_texto(de, "⚠️ Recibí el archivo pero no pude descargarlo. Reenvíalo.")
                        continue
                    print(f"[media] {tipo} -> {len(blob)} bytes", flush=True)
                    ack = procesar_media(de, tipo, blob, caption)
                else:
                    ack = procesar_texto(de, texto) if texto else "registrado ✓"

                print(f"[ack] enviado a {mask(de)}", flush=True)
                await enviar_texto(de, ack)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8123")))
