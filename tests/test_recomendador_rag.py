import json
from pathlib import Path
import pytest
from src.recomendador.rag import Indice, extracto, cargar_manifiesto, fuentes_por_id
from tools.rag_ingestar import ErrorIngesta, construir_indice, decodificar, fragmentar, verificar_hashes


def test_decodificacion_familias_y_fragmentacion():
    assert decodificar(chr(ord('S')-29), "Arial") == "S"
    assert decodificar(chr(ord('S')-32), "Minion") == "S"
    assert decodificar(chr(ord('S')-32), "Syntax") == "S"
    trozos = fragmentar("Una oración útil. " * 100, tam=100, traslape=20)
    assert len(trozos) > 2 and all(t.strip() for t in trozos)


def test_hash_invalido_no_construye(tmp_path):
    (tmp_path / "x.pdf").write_bytes(b"x")
    man={"fuentes":[{"id":"F","archivo":"x.pdf","sha256":"0"*64}]}
    assert verificar_hashes(man, tmp_path)
    with pytest.raises(ErrorIngesta): construir_indice(man, tmp_path)


def test_busqueda_lexica_bilingue_pagina_y_diversidad():
    fuentes={"A":{"titulo":"A","organizacion":"OMS","url":"https://www.who.int","idioma":"en","tipo":["norma"]},"B":{"titulo":"B","organizacion":"CDC","url":"https://www.cdc.gov","idioma":"en","tipo":["norma"]}}
    idx=Indice([{"id":"A#1","fuente_id":"A","pagina":2,"texto":"sits without support safely"},{"id":"A#2","fuente_id":"A","pagina":3,"texto":"sitting alone"},{"id":"B#1","fuente_id":"B","pagina":1,"texto":"sits without support"}],fuentes)
    r=idx.buscar("sentarse sin apoyo","sits without support",k=3,max_por_fuente=1)
    assert len(r)==2 and {p.fuente_id for p in r}=={"A","B"} and all(p.pagina>=1 for p in r)
    assert extracto(r[0].texto,"sits") in r[0].texto


def test_manifiesto_19_fuentes():
    man=cargar_manifiesto()
    assert len(fuentes_por_id(man)) == 19
