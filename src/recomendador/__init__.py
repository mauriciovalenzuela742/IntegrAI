"""Recomendador referenciado con análisis determinístico y revisión humana obligatoria.

Importar este paquete no carga pypdf ni deepeval: esas dependencias solo pertenecen a ingesta y bench.
"""
from __future__ import annotations

from typing import Any


def recomendar(caso: dict[str, Any], indice=None, numero: int = 1):
    """Genera una propuesta validada o ``None`` si las reglas no disparan recomendación."""
    from .motor import recomendar as _recomendar
    return _recomendar(caso, indice=indice, numero=numero)


__all__ = ["recomendar"]
