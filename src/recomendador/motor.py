"""Orquestación pública del recomendador referenciado."""
from __future__ import annotations

from typing import Any

from . import normas
from .analisis import edad_meses_decimal
from .contrato import AVISO, Hallazgo, HitoAnalizado, Procedencia, Recomendacion, Validacion
from .privacidad import prefiltro
from .rag import Indice
from .redactor import plantilla
from .validadores import validar_recomendacion


def recomendar(caso: dict[str, Any], indice: Indice | None = None, numero: int = 1) -> Recomendacion | None:
    filtro = prefiltro(caso.get("nota", ""), caso.get("nombres", []))
    base = {"id_recomendacion": f"REC-{numero:05d}", "id_nino": caso["id_nino"],
            "id_jardin": caso["id_jardin"], "sala_grupo": caso["sala_grupo"],
            "estado_revision": "por_verificar", "generado_por": Procedencia(tipo="plantilla_deterministica"),
            "validacion": Validacion(citas_literales=True, numeros_verificados=True, sin_pii=True, requiere_revision_humana=True),
            "aviso": AVISO}
    if filtro.posible_manipulacion:
        return Recomendacion(**base, hito=None,
            hallazgos_deterministicos=[Hallazgo(id="H-1", tipo="posible_manipulacion", regla="PREFILTRO_INYECCION_V1", resultado="La nota contiene instrucciones ajenas a una observación.", observacion_ids=[caso["id_observacion"]])],
            resumen="La nota se separó para revisión manual porque contiene instrucciones que podrían manipular el procesamiento.", sugerencias=[], derivacion_salud=False)
    item = normas.hito(caso["hito_id"])
    edad = edad_meses_decimal(caso["fecha_nacimiento"], caso["fecha_referencia"])
    zona = normas.zona(item, edad)
    estado = caso.get("estado", "sin_registro")
    tipo = "hito_sin_registro" if estado == "sin_registro" else "hito_no_logrado"
    if estado not in {"no_logrado", "sin_registro"}:
        return None
    if estado == "sin_registro" and zona not in {"atencion", "fuera_de_ventana"}:
        return None
    consulta_es, consulta_en = normas.consultas_hito(item.id)
    pasajes = indice.buscar(consulta_es, consulta_en, k=2, max_por_fuente=1) if indice else []
    resumen, sugerencias = plantilla(item.nombre, estado, zona, pasajes, consulta_es + " " + consulta_en)
    hito = HitoAnalizado(id=item.id, estado=estado, zona=zona, edad_meses=round(edad, 2),
                         id_observacion=caso.get("id_observacion") if estado == "no_logrado" else None,
                         cita_observacion=caso.get("cita") if estado == "no_logrado" else None,
                         fecha_observacion=caso.get("fecha_observacion") if estado == "no_logrado" else None)
    hallazgos = [Hallazgo(id="H-1", tipo=tipo, regla="DISPARO_HITO_V1",
                           resultado=f"{item.id}: {estado}; zona {zona}; umbrales por validar.",
                           observacion_ids=[caso["id_observacion"]] if caso.get("id_observacion") else [])]
    nivel = caso.get("nivel")
    if nivel and (nivel.get("alerta_absoluta") or nivel.get("rezago_relativo")):
        hallazgos.append(Hallazgo(id=f"H-{len(hallazgos) + 1}", tipo="nivel", regla="PARIDAD_E1_V1",
                                  resultado=(f"Escala E-1: nivel vigente {nivel['vigente']}, esperado {nivel['esperado']}; "
                                             f"brecha {nivel['vigente'] - nivel['esperado']}; fecha {nivel['fecha']}."),
                                  observacion_ids=nivel.get("observacion_ids", [])))
    curso = caso.get("curso")
    if curso and curso.get("unico_sin_logro"):
        hallazgos.append(Hallazgo(id=f"H-{len(hallazgos) + 1}", tipo="curso", regla="K_MIN_CURSO_5",
                                  resultado=f"Comparación anónima con {curso['k_registrados']} registros: único sin logro registrado.",
                                  observacion_ids=[]))
    rec = Recomendacion(**base, hito=hito, hallazgos_deterministicos=hallazgos,
        resumen=resumen, sugerencias=sugerencias, derivacion_salud=zona == "fuera_de_ventana")
    errores = validar_recomendacion(rec)
    if errores:
        raise ValueError("; ".join(errores))
    return rec
