"""Contrato público estricto de recomendaciones sujetas a revisión humana."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

AVISO = "Propuesta para el criterio de la educadora. No es un diagnóstico."
ID_SINTETICO = re.compile(r"^NINO-\d{5}$")


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cita(Estricto):
    fuente_id: str
    organizacion: str
    titulo: str
    pagina_pdf: int = Field(ge=1)
    fragmento: str = Field(min_length=1, max_length=300)
    url: HttpUrl


class Sugerencia(Estricto):
    texto: str = Field(min_length=1, max_length=600)
    citas: list[Cita] = Field(min_length=1)


class Hallazgo(Estricto):
    id: str = Field(pattern=r"^H-\d+$")
    tipo: Literal["hito_no_logrado", "hito_sin_registro", "nivel", "curso", "posible_manipulacion"]
    regla: str
    resultado: str
    observacion_ids: list[str] = []


class HitoAnalizado(Estricto):
    id: str
    estado: Literal["logrado", "logrado_inferido", "no_logrado", "en_proceso", "sin_registro"]
    zona: Literal["esperable", "estimular", "atencion", "fuera_de_ventana"]
    edad_meses: float = Field(ge=0)
    id_observacion: str | None = None
    cita_observacion: str | None = Field(default=None, max_length=300)
    fecha_observacion: str | None = None

    @model_validator(mode="after")
    def evidencia_negacion(self):
        if self.estado == "no_logrado" and not (self.id_observacion and self.cita_observacion):
            raise ValueError("no_logrado exige observación y cita")
        return self


class Procedencia(Estricto):
    tipo: Literal["plantilla_deterministica", "llm_con_fallback"]
    modelo: str | None = None


class Validacion(Estricto):
    citas_literales: Literal[True]
    numeros_verificados: Literal[True]
    sin_pii: Literal[True]
    requiere_revision_humana: Literal[True]


class Recomendacion(Estricto):
    id_recomendacion: str = Field(pattern=r"^REC-\d{5}$")
    id_nino: str
    id_jardin: str
    sala_grupo: str
    estado_revision: Literal["por_verificar"]
    hito: HitoAnalizado | None = None
    hallazgos_deterministicos: list[Hallazgo] = Field(min_length=1)
    resumen: str = Field(min_length=1, max_length=800)
    sugerencias: list[Sugerencia]
    derivacion_salud: bool
    generado_por: Procedencia
    validacion: Validacion
    aviso: Literal[AVISO]

    @model_validator(mode="after")
    def reglas(self):
        if not ID_SINTETICO.fullmatch(self.id_nino):
            raise ValueError("id_nino debe ser sintético")
        manipulacion = any(h.tipo == "posible_manipulacion" for h in self.hallazgos_deterministicos)
        if manipulacion and self.sugerencias:
            raise ValueError("posible_manipulacion no admite sugerencias")
        if self.hito and self.hito.zona == "fuera_de_ventana" and not self.derivacion_salud:
            raise ValueError("fuera_de_ventana obliga derivación de salud")
        return self


class Modelos(Estricto):
    extraccion: str
    redaccion: str
    embeddings: str


class Corpus(Estricto):
    manifiesto_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    indice_version: int = 1


class LoteRecomendaciones(Estricto):
    version: Literal[1]
    generado_en: str
    modelos: Modelos
    corpus: Corpus
    umbrales_por_validar: Literal[True]
    aviso: Literal[AVISO]
    items: list[Recomendacion]


def exportar_schema(ruta: Path | None = None) -> dict:
    schema = LoteRecomendaciones.model_json_schema()
    if ruta:
        ruta.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return schema
