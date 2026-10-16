import pytest
from pydantic import ValidationError
from src.recomendador.contrato import Cita, HitoAnalizado, LoteRecomendaciones
from src.recomendador.lote import generar
from src.recomendador.validadores import cita_valida


def test_lote_publico_valida_y_no_importa_pypdf():
    lote = generar(max_items=3, generado_en="2026-01-01T00:00:00+00:00")
    assert LoteRecomendaciones.model_validate(lote.model_dump()).items
    assert all(i.estado_revision == "por_verificar" for i in lote.items)


def test_no_logrado_exige_cita_y_fuera_ventana_derivacion():
    with pytest.raises(ValidationError):
        HitoAnalizado(id="x",estado="no_logrado",zona="atencion",edad_meses=9)


def test_citas_breves_y_literales():
    with pytest.raises(ValidationError):
        Cita(fuente_id="F",organizacion="OMS",titulo="T",pagina_pdf=1,fragmento="x"*301,url="https://www.who.int")
    assert cita_valida("literal", "un texto literal aquí")
