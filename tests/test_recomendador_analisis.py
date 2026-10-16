from src.recomendador.analisis import (aplicar_implicaciones, comparar_curso, edad_meses_decimal,
    estado_hito, nivel_esperado, analizar_nivel)


def test_edad_decimal_y_ausencia_no_es_negacion():
    assert round(edad_meses_decimal("2025-01-01", "2025-10-01"), 2) == 8.97
    assert estado_hito([], "sentarse_sin_apoyo")["estado"] == "sin_registro"
    assert estado_hito([{"hito_id":"sentarse_sin_apoyo","estado":"no_logrado","fecha":"2025-01-01"}], "sentarse_sin_apoyo")["estado"] == "sin_registro"


def test_reciente_con_cita_y_contradiccion():
    evidencias = [
      {"hito_id":"sentarse_sin_apoyo","estado":"logrado","fecha":"2025-01-01","cita":"se sienta","id_observacion":"O1"},
      {"hito_id":"sentarse_sin_apoyo","estado":"no_logrado","fecha":"2025-02-01","cita":"no se sienta","id_observacion":"O2"}]
    r = estado_hito(evidencias, "sentarse_sin_apoyo")
    assert r["estado"] == "no_logrado" and r["contradiccion"]


def test_implica_sin_inferir_gateo_y_curso_k5():
    r = aplicar_implicaciones({"caminar_solo":{"estado":"logrado"}, "sentarse_sin_apoyo":{"estado":"sin_registro"}, "gatear_manos_rodillas":{"estado":"sin_registro"}})
    assert r["sentarse_sin_apoyo"]["estado"] == "logrado_inferido"
    assert r["gatear_manos_rodillas"]["estado"] == "sin_registro"
    estados = {"A":"no_logrado", "B":"logrado", "C":"logrado", "D":"logrado", "E":"logrado"}
    assert comparar_curso(estados, "A")["unico_sin_logro"]
    assert not comparar_curso(dict(list(estados.items())[:4]), "A")["base_suficiente"]


def test_paridad_nivel_frontend():
    niveles=[{"nivel":4,"edad_min_meses":6,"edad_max_meses":9},{"nivel":5,"edad_min_meses":9,"edad_max_meses":12}]
    assert nivel_esperado(9, niveles) == 5
    r=analizar_nivel("NINO-00001","2025-01-15","2025-10-14",niveles,[{"id_nino":"NINO-00001","fecha_observacion":"2025-10-01","nivel_estimado":2}],niveles_sala=[4,4,4,4,2])
    assert r["nivel_esperado"] == 4 and r["brecha"] == -2 and r["alerta_absoluta"]
