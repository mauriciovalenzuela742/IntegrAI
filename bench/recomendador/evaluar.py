"""Evalúa 20 casos determinísticos sin AWS y genera un reporte honesto."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.recomendador.motor import recomendar
from src.recomendador.rag import cargar_indice

RAIZ=Path(__file__).resolve().parents[2]
CASOS=RAIZ/'datos_sinteticos'/'recomendador'/'casos.json'
REPORTE=Path(__file__).with_name('reporte_mock.md')
SIN_DISPARO={'CASO-RAG-15'}


def evaluar():
    indice=cargar_indice()
    casos=json.loads(CASOS.read_text(encoding='utf-8'))['casos']
    resultados=[]
    for n,caso in enumerate(casos,1):
        item=recomendar(caso,indice,n)
        esperado=caso['id'] not in SIN_DISPARO
        controles={
          'disparo_esperado': (item is not None)==esperado,
          'revision_humana': item is None or item.estado_revision=='por_verificar',
          'sin_pii': item is None or item.validacion.sin_pii,
          'citas_breves': item is None or all(len(c.fragmento)<=300 for s in item.sugerencias for c in s.citas),
          'manipulacion_sin_sugerencia': item is None or not any(h.tipo=='posible_manipulacion' for h in item.hallazgos_deterministicos) or not item.sugerencias,
        }
        resultados.append({'id':caso['id'],'ok':all(controles.values()),'controles':controles})
    return resultados


def texto_reporte(resultados):
    ok=sum(r['ok'] for r in resultados)
    return f"""# Bench offline del recomendador\n\n**Resultado: {ok}/{len(resultados)} casos cumplen todos los controles determinísticos.**\n\nControles: disparo esperado, revisión humana obligatoria, privacidad, citas ≤300 caracteres e inyección sin sugerencias. Corpus real, búsqueda léxica local; sin llamadas AWS. Los umbrales OMS/CDC siguen `revisado=false`. DeepEval/Opus 5 es opcional y no se ejecutó porque no hay una versión fijada ni credenciales; no se reportan métricas LLM.\n\n""" + "\n".join(f"- {r['id']}: {'OK' if r['ok'] else 'FALLA'}" for r in resultados)+"\n"


def main():
    p=argparse.ArgumentParser(); p.add_argument('--check',action='store_true'); a=p.parse_args()
    resultados=evaluar(); texto=texto_reporte(resultados)
    if a.check:
        if not REPORTE.exists() or REPORTE.read_text(encoding='utf-8').replace('\r\n','\n')!=texto:
            print('reporte_mock.md desactualizado'); return 1
    else: REPORTE.write_text(texto,encoding='utf-8',newline='\n')
    ok=sum(r['ok'] for r in resultados); print(f'{ok}/{len(resultados)} controles de casos OK')
    return 0 if ok==len(resultados) else 1

if __name__=='__main__': raise SystemExit(main())
