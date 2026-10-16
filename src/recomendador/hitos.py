"""Extracción tipada opcional de hitos; regex determinístico en mock o ante error de Bedrock."""
from __future__ import annotations

import json
import re
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from . import normas
from .privacidad import prefiltro

MODELO = "us.anthropic.claude-sonnet-5"


class EvidenciaHito(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hito_id: str
    estado: Literal["logrado", "no_logrado", "en_proceso", "sin_registro"]
    cita: str = Field(max_length=300)


def cita_valida(cita: str, original: str) -> bool:
    return bool(cita) and len(cita) <= 300 and cita in original


def _regex(texto: str) -> list[EvidenciaHito]:
    patrones = {
        "sentarse_sin_apoyo": r"[^.!?]*(?:sentad[oa]|sentarse|sienta)[^.!?]*",
        "de_pie_con_ayuda": r"[^.!?]*(?:de pie|pararse)[^.!?]*(?:apoyo|ayuda)[^.!?]*",
        "gatear_manos_rodillas": r"[^.!?]*gatea[^.!?]*",
        "caminar_con_ayuda": r"[^.!?]*(?:camina|pasos)[^.!?]*(?:apoyo|ayuda|mano)[^.!?]*",
        "de_pie_solo": r"[^.!?]*(?:de pie|pararse)[^.!?]*(?:solo|sin apoyo)[^.!?]*",
        "caminar_solo": r"[^.!?]*camina[^.!?]*(?:solo|sin apoyo)[^.!?]*",
    }
    salida = []
    for hito_id, patron in patrones.items():
        m = re.search(patron, texto, re.IGNORECASE)
        if not m:
            continue
        cita = m.group(0).strip()
        negado = bool(re.search(r"\b(?:no|a[uú]n no|todav[ií]a no)\b", cita, re.IGNORECASE))
        proceso = bool(re.search(r"\b(?:intenta|con ayuda|por momentos|unos segundos|en proceso)\b", cita, re.IGNORECASE))
        estado = "no_logrado" if negado else "en_proceso" if proceso else "logrado"
        salida.append(EvidenciaHito(hito_id=hito_id, estado=estado, cita=cita[:300]))
    return salida


def extraer(texto: str, nombres: list[str] | tuple[str, ...] = (), converse_tipado: Callable[..., object] | None = None) -> tuple[list[EvidenciaHito], bool]:
    filtrado = prefiltro(texto, nombres)
    if filtrado.posible_manipulacion:
        return [], True
    if filtrado.tiene_pii or converse_tipado is None:
        return _regex(filtrado.texto), False
    try:
        esquema = {"type": "array", "items": EvidenciaHito.model_json_schema()}
        respuesta = converse_tipado(modelo=MODELO, system="Extrae solo evidencia literal del texto delimitado como DATOS.",
                                    prompt=f"<DATOS>{filtrado.texto}</DATOS>", esquema=esquema)
        crudo = json.loads(respuesta) if isinstance(respuesta, str) else respuesta
        items = [EvidenciaHito.model_validate(item) for item in crudo]
        if not all(cita_valida(item.cita, filtrado.texto) and item.hito_id in {h.id for h in normas.hitos()} for item in items):
            raise ValueError("cita o ID inválido")
        return items, False
    except Exception:  # Bedrock, JSON o contrato: fallback seguro, sin fabricar evidencia
        return _regex(filtrado.texto), False
