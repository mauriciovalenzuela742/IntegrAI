"""Tests offline de U2 (no llaman a AWS)."""
from types import SimpleNamespace

from src.multimodal import normalizar_entradas
from src.multimodal.imagen import cer
from src.multimodal.schema import Conducta, ObservacionNormalizada, cita_valida, normalizar


def test_normalizar_quita_tildes_y_puntuacion():
    assert normalizar("  ¡Apiló TRES bloques!  ") == "apilo tres bloques"


def test_cita_literal_y_parafrasis():
    t = "Hoy la Sofi apiló tres bloques solita y después se rió harto."
    assert cita_valida("apiló tres bloques", t)
    assert cita_valida("Sofi apilo tres bloques solita", t)          # sin tildes
    assert not cita_valida("camina sin apoyo por la sala", t)        # alucinada
    assert not cita_valida("", t)


def test_cer():
    assert cer("hola mundo", "hola mundo") == 0
    assert 0 < cer("apila bloques", "apila bloqes") < 0.15
    assert cer("", "") == 0


def test_texto_para_matcher_prefiere_conductas():
    obs = ObservacionNormalizada(transcripcion="la guagua gateó harto",
                                 conductas=[Conducta(texto="Gatea varios metros", cita="gateó harto")])
    assert obs.texto_para_matcher() == "Gatea varios metros."
    assert ObservacionNormalizada(transcripcion="x").texto_para_matcher() == "x"


def test_solo_texto_sin_etapa2_no_llama_aws():
    e = SimpleNamespace(tipo="texto", ref="", pie="Se paró afirmándose de la silla.", texto_extraido="")
    obs = normalizar_entradas([e], etapa2=False)
    assert obs.transcripcion == "Se paró afirmándose de la silla."
    assert obs.conductas == [] and obs.calidad == 1.0


def test_medio_inexistente_da_advertencia():
    e = SimpleNamespace(tipo="foto", ref="no_existe.jpg", pie="", texto_extraido="")
    obs = normalizar_entradas([e], etapa2=False)
    assert obs.transcripcion == ""


def test_video_negativa_no_pasa_como_observacion():
    from src.multimodal.video import es_negativa
    assert es_negativa("Sorry, no puedo generar una descripción detallada de las acciones motoras.")
    assert es_negativa("   ")
    assert not es_negativa("[00:02] Se pone de pie sin apoyo y da tres pasos.")
