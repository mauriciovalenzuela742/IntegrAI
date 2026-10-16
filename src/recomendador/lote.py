"""Generación reproducible del lote público desde casos sintéticos explícitos."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .contrato import AVISO, Corpus, LoteRecomendaciones, Modelos
from .motor import recomendar
from .rag import cargar_indice, cargar_manifiesto, sha256_manifiesto

RAIZ = Path(__file__).resolve().parents[2]
CASOS = RAIZ / "datos_sinteticos" / "recomendador" / "casos.json"
SALIDA = RAIZ / "data" / "recomendaciones.json"


def generar(casos: list[dict] | None = None, fecha_ref: str | None = None, max_items: int | None = None,
            cursos: set[str] | None = None, generado_en: str | None = None) -> LoteRecomendaciones:
    manifiesto = cargar_manifiesto()
    indice = cargar_indice(manifiesto=manifiesto)
    casos = casos if casos is not None else json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    if cursos:
        casos = [c for c in casos if f"{c['id_jardin']}:{c['sala_grupo']}" in cursos]
    if max_items is not None:
        casos = casos[:max_items]
    items = []
    for caso in casos:
        caso = dict(caso)
        if fecha_ref:
            caso["fecha_referencia"] = fecha_ref
        item = recomendar(caso, indice, len(items) + 1)
        if item:
            items.append(item)
    return LoteRecomendaciones(version=1,
        generado_en=generado_en or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        modelos=Modelos(extraccion="us.anthropic.claude-sonnet-5", redaccion="us.anthropic.claude-sonnet-5", embeddings="amazon.titan-embed-text-v2:0"),
        corpus=Corpus(manifiesto_sha256=sha256_manifiesto(), indice_version=1),
        umbrales_por_validar=True, aviso=AVISO, items=items)


def escribir(lote: LoteRecomendaciones, ruta: Path = SALIDA) -> None:
    ruta.write_text(json.dumps(lote.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
