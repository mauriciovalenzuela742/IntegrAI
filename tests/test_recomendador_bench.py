from bench.recomendador.evaluar import evaluar


def test_veinte_controles_offline():
    resultados=evaluar()
    assert len(resultados)==20
    assert all(r['ok'] for r in resultados)
