"""Gate de confianza del juez de rúbrica.

El umbral era 0.6 fijo y la autoconfianza del LLM está sub-calibrada (0.2-0.6), así que casi toda
observación real caía a "por verificar". Ahora es configurable (JUEZ_CONFIANZA_MIN, default 0.5).
"""
import importlib

import src.clasificador_rubrica as cr


def test_umbral_por_defecto_es_0_5():
    assert cr.CONFIANZA_MIN == 0.5


def test_evidencia_no_literal_siempre_escala():
    # aunque la confianza sea alta, si la evidencia no es literal va a revisión
    assert cr._requiere_revision(0.99, False) is True


def test_confianza_bajo_el_umbral_escala():
    assert cr._requiere_revision(0.4, True) is True
    assert cr._requiere_revision(0.49, True) is True


def test_confianza_en_o_sobre_el_umbral_no_escala():
    assert cr._requiere_revision(0.5, True) is False
    assert cr._requiere_revision(0.6, True) is False
    assert cr._requiere_revision(0.75, True) is False


def test_umbral_configurable_por_env(monkeypatch):
    monkeypatch.setenv("JUEZ_CONFIANZA_MIN", "0.3")
    try:
        importlib.reload(cr)
        assert cr.CONFIANZA_MIN == 0.3
        assert cr._requiere_revision(0.35, True) is False   # 0.35 >= 0.3 -> auto
        assert cr._requiere_revision(0.2, True) is True
    finally:
        monkeypatch.delenv("JUEZ_CONFIANZA_MIN", raising=False)
        importlib.reload(cr)   # restaurar 0.5 para el resto de la suite
    assert cr.CONFIANZA_MIN == 0.5
