"""Prefiltro de privacidad e instrucciones incrustadas para notas del recomendador."""
from __future__ import annotations

import re
from dataclasses import dataclass

PATRONES_INYECCION = (
    r"ignore (?:all |the )?(?:previous|prior) instructions",
    r"ignora (?:todas )?(?:las )?instrucciones",
    r"system prompt|prompt del sistema|developer message",
    r"revela (?:el )?(?:secreto|token|prompt)",
    r"act[uú]a como (?:administrador|sistema)",
)
PATRONES_PII = (
    r"\b\d{7,9}-[0-9kK]\b",
    r"\b(?:\+?56\s*)?9\s*\d{4}\s*\d{4}\b",
    r"[\w.+-]+@[\w.-]+\.\w+",
)


@dataclass(frozen=True)
class Prefiltro:
    texto: str
    tiene_pii: bool
    posible_manipulacion: bool


def quitar_nombres(texto: str, nombres: list[str] | tuple[str, ...] = ()) -> str:
    salida = texto or ""
    for nombre in sorted((n.strip() for n in nombres if n.strip()), key=len, reverse=True):
        salida = re.sub(rf"\b{re.escape(nombre)}\b", "[NINO]", salida, flags=re.IGNORECASE)
    salida = re.sub(r"\b(?:niñ[oa]|beb[eé])\s+(?:llamad[oa]\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b", "niño/a [NINO]", salida)
    return salida


def contiene_pii(texto: str) -> bool:
    return any(re.search(p, texto or "", re.IGNORECASE) for p in PATRONES_PII)


def detectar_inyeccion(texto: str) -> bool:
    return any(re.search(p, texto or "", re.IGNORECASE) for p in PATRONES_INYECCION)


def prefiltro(texto: str, nombres: list[str] | tuple[str, ...] = ()) -> Prefiltro:
    limpio = quitar_nombres(texto, nombres)
    return Prefiltro(limpio, contiene_pii(limpio), detectar_inyeccion(limpio))
