"""Validaciones semánticas posteriores al contrato Pydantic."""
from __future__ import annotations

import re
from typing import Iterable

from .contrato import AVISO, Recomendacion

PROHIBIDO = re.compile(r"\b(?:diagn[oó]stic[oa]|trastorno|enfermedad|paciente)\b", re.IGNORECASE)
SECRETO = re.compile(r"(?:AKIA[0-9A-Z]{16}|aws_secret|bearer\s+[\w.-]+|-----BEGIN)", re.IGNORECASE)
PII = re.compile(r"(?:\b\d{7,9}-[0-9kK]\b|\b(?:\+?56\s*)?9\s*\d{4}\s*\d{4}\b|[\w.+-]+@[\w.-]+\.\w+)")


def cita_valida(fragmento: str, pasaje: str) -> bool:
    return bool(fragmento) and len(fragmento) <= 300 and fragmento in pasaje


def validar_recomendacion(recomendacion: Recomendacion, pasajes: dict[str, str] | None = None) -> list[str]:
    errores: list[str] = []
    textos = [recomendacion.resumen, recomendacion.aviso]
    textos.extend(s.texto for s in recomendacion.sugerencias)
    textos.extend(c.fragmento for s in recomendacion.sugerencias for c in s.citas)
    unido = " ".join(textos)
    if recomendacion.aviso != AVISO:
        errores.append("aviso inválido")
    if PROHIBIDO.search(" ".join([recomendacion.resumen, *(s.texto for s in recomendacion.sugerencias)])):
        errores.append("lenguaje diagnóstico")
    if PII.search(unido) or SECRETO.search(unido):
        errores.append("PII o secreto")
    if pasajes is not None:
        for sugerencia in recomendacion.sugerencias:
            for cita in sugerencia.citas:
                original = pasajes.get(cita.fuente_id, "")
                if not cita_valida(cita.fragmento, original):
                    errores.append(f"cita no literal: {cita.fuente_id}")
    return errores


def validar_numeros(texto: str, permitidos: Iterable[float | int]) -> bool:
    valores = {str(v) for v in permitidos}
    return all(numero in valores for numero in re.findall(r"\b\d+(?:[.,]\d+)?\b", texto))
