"""Etapa 1 · video → texto: ANÁLISIS VISUAL (Pegasus 1.2, fallback Nova 2 Lite) + audio como complemento.

Lo que importa de un video es lo que se ve: si el niño/a se para solo o con apoyo, si levanta y
sostiene la cabeza, cómo gatea o toma objetos. La mitad del catálogo es motora y no se escucha.
La pista de audio (Whisper) solo complementa: lo que la tía comenta al grabar, o el nombre.
Los videos de WhatsApp pesan ≤ 16 MB, así que se envían inline (base64) sin necesidad de bucket.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from .. import config
from ._bedrock import cliente, converse
from .audio import transcribir
from .schema import Segmento

PROMPT_VIDEO = ("Eres una educadora de párvulos observando un video de un niño o niña de 0 a 3 años. "
                "Describe SOLO lo que se VE, en frases cortas en presente y tercera persona, cada una precedida "
                "por el segundo aproximado entre corchetes. Sé preciso en lo motor, porque eso define el nivel: "
                "- Control de cabeza y tronco: si levanta o sostiene la cabeza (boca abajo, sentado, en brazos) y cuánto tiempo. "
                "- Postura: acostado, sentado con o sin apoyo, gateando, de pie. "
                "- Apoyo: distingue SIEMPRE 'sin apoyo' de 'con apoyo' y di en qué se apoya (mueble, adulto, pared). "
                "- Desplazamiento: rueda, se arrastra, gatea, da pasos (cuántos), camina, corre, sube. "
                "- Manos: alcanza, toma con toda la mano o con pinza, transfiere, apila, suelta. "
                "- Mirada, gestos, vocalizaciones e interacción con otros. "
                "Ejemplos: '[2s] Boca abajo, levanta la cabeza y la sostiene unos 5 segundos.' "
                "'[8s] Se pone de pie sin apoyo y da tres pasos solo.' "
                "Si algo no se ve con claridad, dilo ('no se distingue si se apoya'). "
                "No nombres a nadie, no describas rasgos físicos ni ropa, no estimes edad ni nivel.")

MAX_INLINE = 25 * 1024 * 1024


def _pegasus(path: str) -> str:
    body = {"inputPrompt": PROMPT_VIDEO, "temperature": 0,
            "mediaSource": {"base64String": base64.b64encode(Path(path).read_bytes()).decode()}}
    r = cliente().invoke_model(modelId=config.MODELO_VIDEO, body=json.dumps(body))
    return json.loads(r["body"].read())["message"]


def _nova(path: str) -> str:
    fmt = Path(path).suffix.lstrip(".").lower() or "mp4"
    contenido = [{"video": {"format": fmt if fmt in ("mp4", "mov", "webm", "mkv") else "mp4",
                            "source": {"bytes": Path(path).read_bytes()}}},
                 {"text": PROMPT_VIDEO}]
    return converse(config.MODELO_VIDEO_FALLBACK, contenido, max_tokens=700)["texto"]


_NEGATIVAS = ("no puedo", "lo siento", "sorry", "i can't", "i cannot", "no es posible", "no me es posible")


def es_negativa(texto: str) -> bool:
    """Respuesta que no describe el video (negativa o descargo). Probado: Nova 2 Lite se niega a veces."""
    t = texto.lower()
    return not t.strip() or ("[" not in t and any(n in t[:200] for n in _NEGATIVAS))


def describir_video(path: str) -> Segmento:
    adv: list[str] = []
    for nombre, fn, modelo in (("pegasus", _pegasus, config.MODELO_VIDEO),
                               ("nova", _nova, config.MODELO_VIDEO_FALLBACK)):
        try:
            texto = fn(path).strip()
            if es_negativa(texto):
                logging.getLogger(__name__).warning("%s no describió el video (negativa)", nombre)
                adv.append("descripción visual no disponible")
                continue
            if texto:
                return Segmento(fuente="video_visual", texto=texto, calidad=0.8, modelo=modelo,
                                advertencias=adv + ["descripción visual generada por modelo: revisar"])
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("descripción de video con %s falló", nombre)
            adv.append("descripción visual no disponible")
    return Segmento(fuente="video_visual", texto="", calidad=0.0, advertencias=adv or ["sin descripción visual"])


def procesar_video(path: str) -> list[Segmento]:
    if not path or not Path(path).exists():
        return [Segmento(fuente="video_visual", texto="", calidad=0.0, advertencias=["video no encontrado"])]
    if Path(path).stat().st_size > MAX_INLINE:
        return [transcribir(path, fuente="video_audio"),
                Segmento(fuente="video_visual", texto="", calidad=0.0,
                         advertencias=["video > 25 MB: solo se procesó el audio"])]
    return [transcribir(path, fuente="video_audio"), describir_video(path)]
