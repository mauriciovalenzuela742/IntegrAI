"""Redacción acotada y fallback determinístico del recomendador."""
from __future__ import annotations

from .contrato import Cita, Sugerencia
from .rag import Pasaje, extracto


def cita_desde_pasaje(pasaje: Pasaje, consulta: str) -> Cita:
    return Cita(fuente_id=pasaje.fuente_id, organizacion=pasaje.organizacion, titulo=pasaje.titulo,
                pagina_pdf=pasaje.pagina, fragmento=extracto(pasaje.texto, consulta), url=pasaje.url)


def plantilla(hito_nombre: str, estado: str, zona: str, pasajes: list[Pasaje], consulta: str) -> tuple[str, list[Sugerencia]]:
    if estado == "sin_registro":
        resumen = f"No hay registro suficiente para valorar {hito_nombre.lower()}; se propone observarlo en actividades cotidianas."
    else:
        resumen = f"La evidencia registra {hito_nombre.lower()} como no logrado en una zona que aconseja apoyo y seguimiento."
    if not pasajes:
        return resumen, []
    citas = [cita_desde_pasaje(p, consulta) for p in pasajes[:2]]
    texto = (f"Ofrecer oportunidades de juego seguras y supervisadas relacionadas con {hito_nombre.lower()}, "
             "respetando el ritmo individual y registrando los cambios observables.")
    if zona == "fuera_de_ventana":
        texto += " Sugerir a la familia conversar con un profesional de salud para una evaluación oportuna."
    return resumen, [Sugerencia(texto=texto, citas=citas)]
