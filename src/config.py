"""Configuración del agente IntegraAI.

Todo es *ambiente-primero*: sin credenciales AWS, el sistema corre 100% en MOCK
(plantillas deterministas), de modo que la demo funciona sin nube y el salto a
producción es sólo enchufar credenciales.
"""
from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"

# --- AWS / Bedrock ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MODELO_SIMPLE = os.getenv("MODELO_SIMPLE", "amazon.nova-lite-v1:0")
MODELO_RAZONAMIENTO = os.getenv("MODELO_RAZONAMIENTO", "amazon.nova-pro-v1:0")
MODELO_VISION = os.getenv("MODELO_VISION", "amazon.nova-pro-v1:0")

# --- U2 · Ingesta multimodal (src/multimodal) ---
# "legacy" = Procesador original | "v2" = puente de texto en 2 etapas (transcripción + conductas)
U2_PIPELINE = os.getenv("U2_PIPELINE", "legacy")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3-turbo")
MODELO_OCR = os.getenv("MODELO_OCR", "us.anthropic.claude-sonnet-5")
MODELO_OCR_VERIF = os.getenv("MODELO_OCR_VERIF", "us.amazon.nova-2-lite-v1:0")
MODELO_VIDEO = os.getenv("MODELO_VIDEO", "us.twelvelabs.pegasus-1-2-v1:0")
MODELO_VIDEO_FALLBACK = os.getenv("MODELO_VIDEO_FALLBACK", "us.amazon.nova-pro-v1:0")  # Nova 2 Lite se negó en pruebas
MODELO_CONDUCTAS = os.getenv("MODELO_CONDUCTAS", "us.anthropic.claude-sonnet-5")

# auto = Bedrock si hay credenciales, si no MOCK | "1" = fuerza MOCK
MODO_MOCK = os.getenv("MODO_MOCK", "auto")

# --- Decision model (Jev / Laya / CLM) ---
# "heuristico" = mock | "jev" | "laya" | "clm"
BACKEND_DECISION = os.getenv("BACKEND_DECISION", "heuristico")
LAYA_MODEL_PATH = os.getenv("LAYA_MODEL_PATH", "")
# Gate: si el margen (top1-top2) del ensemble < este valor -> escala a revision humana
GATE_MARGEN = float(os.getenv("GATE_MARGEN", "0.15"))
JEV_API_KEY = os.getenv("JEV_API_KEY")
JEV_ENDPOINT = os.getenv("JEV_ENDPOINT")

# --- Plataforma de datos ---
DB_PATH = os.getenv("DB_PATH", str(RAIZ / "plataforma.db"))

# --- WhatsApp ---
# canal: "consola" (mock) | "cloud" (Meta Cloud API) | "twilio"
WHATSAPP_CANAL = os.getenv("WHATSAPP_CANAL", "consola")


def usar_mock() -> bool:
    """Decide si correr en modo MOCK (sin nube)."""
    if MODO_MOCK in ("1", "true", "True", "yes"):
        return True
    if MODO_MOCK in ("0", "false", "False", "no"):
        return False
    # auto: usar Bedrock si hay credenciales en el entorno o en ~/.aws
    if any(os.getenv(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_ROLE_ARN", "AWS_SESSION_TOKEN")):
        return False
    if (Path.home() / ".aws" / "credentials").exists():
        return False
    # En EC2 las credenciales vienen del instance profile (IMDS), no de env/~/.aws
    try:
        import boto3
        if boto3.Session().get_credentials() is not None:
            return False
    except Exception:
        pass
    return True


def datos_dir():
    """Ubica los CSV del dataset (sirve tanto en local como en el repo del equipo)."""
    for cand in (RAIZ / "data", RAIZ / "dataset_e1" / "datos_publicos"):
        if (cand / "observaciones.csv").exists():
            return cand
    return RAIZ / "dataset_e1" / "datos_publicos"
