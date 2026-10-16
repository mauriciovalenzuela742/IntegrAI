import json
from pathlib import Path
from src.recomendador.lote import generar


def test_reproducible_salvo_fecha_y_cubre_hallazgos():
    a=generar(generado_en="A").model_dump(mode="json")
    b=generar(generado_en="B").model_dump(mode="json")
    a.pop("generado_en"); b.pop("generado_en")
    assert a == b
    tipos={h["tipo"] for i in a["items"] for h in i["hallazgos_deterministicos"]}
    assert {"hito_no_logrado","hito_sin_registro","nivel","posible_manipulacion"} <= tipos


def test_solo_ids_existentes_y_contrato_publico():
    ninos={line.split(',')[0] for line in Path('data/ninos.csv').read_text(encoding='utf-8').splitlines()[1:]}
    lote=generar(generado_en="A")
    assert all(i.id_nino in ninos for i in lote.items)
    assert all(len(c.fragmento)<=300 for i in lote.items for s in i.sugerencias for c in s.citas)
