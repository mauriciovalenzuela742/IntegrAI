"""Análisis determinístico de hitos, curso y nivel con paridad respecto del frontend."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from . import normas

K_MIN_CURSO = 5
UMBRAL_ALERTA = -2
UMBRAL_REZAGO_RELATIVO = 1.0
ESTADOS_LOGRADOS = {"logrado", "logrado_inferido"}
ESTADOS = {"logrado", "logrado_inferido", "no_logrado", "en_proceso", "sin_registro"}


def _fecha(valor: str | date) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(valor[:10])


def edad_meses_decimal(fecha_nacimiento: str | date, fecha_referencia: str | date) -> float:
    return (_fecha(fecha_referencia) - _fecha(fecha_nacimiento)).days / 30.4375


def edad_meses_completos(fecha_nacimiento: str | date, fecha_referencia: str | date) -> int:
    nacimiento, hoy = _fecha(fecha_nacimiento), _fecha(fecha_referencia)
    meses = (hoy.year - nacimiento.year) * 12 + hoy.month - nacimiento.month
    if hoy.day < nacimiento.day:
        meses -= 1
    return max(0, meses)


def estado_hito(evidencias: list[dict[str, Any]], hito_id: str) -> dict[str, Any]:
    candidatas = [e for e in evidencias if e.get("hito_id") == hito_id and e.get("estado") in ESTADOS - {"sin_registro"}]
    validas = [e for e in candidatas if e.get("estado") not in {"no_logrado", "logrado", "en_proceso"} or e.get("cita")]
    if not validas:
        return {"estado": "sin_registro", "evidencias": [], "contradiccion": False}
    validas.sort(key=lambda e: (e.get("fecha", ""), e.get("id_observacion", "")))
    reciente = validas[-1]
    signos = {"logro" if e["estado"] in ESTADOS_LOGRADOS else e["estado"] for e in validas}
    return {"estado": reciente["estado"], "id_observacion": reciente.get("id_observacion"),
            "fecha": reciente.get("fecha"), "cita": reciente.get("cita"),
            "evidencias": validas, "contradiccion": "logro" in signos and "no_logrado" in signos}


def aplicar_implicaciones(estados: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    salida = {k: dict(v) for k, v in estados.items()}
    for hito_id, estado in list(estados.items()):
        if estado.get("estado") not in ESTADOS_LOGRADOS:
            continue
        for implicado in normas.implicados_por(hito_id):
            actual = salida.get(implicado, {"estado": "sin_registro"})
            if actual.get("estado") == "sin_registro":
                salida[implicado] = {"estado": "logrado_inferido", "inferido_por": hito_id,
                                     "evidencias": [], "contradiccion": False}
    return salida


def comparar_curso(estados_por_nino: dict[str, str], id_nino: str) -> dict[str, Any]:
    registrados = {k: v for k, v in estados_por_nino.items() if v != "sin_registro"}
    suficiente = len(registrados) >= K_MIN_CURSO
    otros = [v for k, v in registrados.items() if k != id_nino]
    unico = suficiente and id_nino in registrados and registrados[id_nino] not in ESTADOS_LOGRADOS and bool(otros) and all(v in ESTADOS_LOGRADOS for v in otros)
    return {"k_registrados": len(registrados), "base_suficiente": suficiente,
            "unico_sin_logro": unico, "regla": f"K_MIN_CURSO={K_MIN_CURSO}"}


def nivel_esperado(meses: int, niveles: list[dict[str, Any]]) -> int | None:
    ordenados = sorted(niveles, key=lambda n: int(n["nivel"]))
    for nivel in ordenados:
        if int(nivel["edad_min_meses"]) <= meses < int(nivel["edad_max_meses"]):
            return int(nivel["nivel"])
    ultimo = ordenados[-1] if ordenados else None
    return int(ultimo["nivel"]) if ultimo and meses >= int(ultimo["edad_max_meses"]) else None


def analizar_nivel(id_nino: str, nacimiento: str, fecha_ref: str, niveles: list[dict[str, Any]],
                    observaciones: list[dict[str, Any]], evaluaciones: list[dict[str, Any]] | None = None,
                    niveles_sala: list[float] | None = None) -> dict[str, Any]:
    globales = [e for e in (evaluaciones or []) if e.get("id_nino") == id_nino and e.get("dominio") == "global"]
    globales.sort(key=lambda e: e.get("periodo", ""))
    propias = [o for o in observaciones if o.get("id_nino") == id_nino]
    propias.sort(key=lambda o: o.get("fecha_observacion", ""))
    fuente = globales[-1] if globales else (propias[-1] if propias else None)
    vigente = int(fuente.get("nivel", fuente.get("nivel_estimado"))) if fuente else None
    fecha = fuente.get("periodo", fuente.get("fecha_observacion")) if fuente else None
    esperado = nivel_esperado(edad_meses_completos(nacimiento, fecha_ref), niveles)
    brecha = vigente - esperado if vigente is not None and esperado is not None else None
    media = mean(niveles_sala) if niveles_sala else None
    return {"nivel_vigente": vigente, "nivel_esperado": esperado, "brecha": brecha,
            "alerta_absoluta": brecha is not None and brecha <= UMBRAL_ALERTA,
            "media_sala": media, "rezago_relativo": media is not None and vigente is not None and vigente < media - UMBRAL_REZAGO_RELATIVO,
            "escala": "E-1", "fecha": fecha}


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path, help="JSON con fecha_nacimiento, fecha_referencia y evidencias")
    args = parser.parse_args()
    datos = json.loads(args.archivo.read_text(encoding="utf-8"))
    edad = edad_meses_decimal(datos["fecha_nacimiento"], datos["fecha_referencia"])
    resultado = {item.id: {**estado_hito(datos.get("evidencias", []), item.id), "zona": normas.zona(item, edad)} for item in normas.hitos()}
    print(json.dumps({"edad_meses": round(edad, 2), "hitos": aplicar_implicaciones(resultado)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
