import pytest
from src.recomendador import normas


def test_seis_ids_y_fallback_cdc_p75():
    items = normas.hitos()
    assert len(items) == 6
    assert len({h.id for h in items}) == 6
    assert normas.hito("sentarse_sin_apoyo").a == 9.0
    assert normas.hito("gatear_manos_rodillas").a == 9.3
    assert all(not normas.cargar()["revisado"] for _ in [0])


@pytest.mark.parametrize("h", normas.hitos(), ids=lambda h: h.id)
def test_bordes_zonas(h):
    assert normas.zona(h, h.p50 - .001) == "esperable"
    assert normas.zona(h, h.p50) == "estimular"
    assert normas.zona(h, h.a - .001) == ("estimular" if h.a <= h.p99 else "fuera_de_ventana")
    assert normas.zona(h, h.a) == ("atencion" if h.a <= h.p99 else "fuera_de_ventana")
    assert normas.zona(h, h.p99) == ("atencion" if h.a <= h.p99 else "estimular")
    assert normas.zona(h, h.p99 + .001) == "fuera_de_ventana"


def test_sentarse_nueve_meses_y_consultas_bilingues():
    assert normas.zona("sentarse_sin_apoyo", 9.0) == "atencion"
    es, en = normas.consultas_hito("sentarse_sin_apoyo")
    assert "sentarse" in es and "sits without support" in en
