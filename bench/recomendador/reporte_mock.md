# Bench offline del recomendador

**Resultado: 20/20 casos cumplen todos los controles determinísticos.**

Controles: disparo esperado, revisión humana obligatoria, privacidad, citas ≤300 caracteres e inyección sin sugerencias. Corpus real, búsqueda léxica local; sin llamadas AWS. Los umbrales OMS/CDC siguen `revisado=false`. DeepEval/Opus 5 es opcional y no se ejecutó porque no hay una versión fijada ni credenciales; no se reportan métricas LLM.

- CASO-RAG-01: OK
- CASO-RAG-02: OK
- CASO-RAG-03: OK
- CASO-RAG-04: OK
- CASO-RAG-05: OK
- CASO-RAG-06: OK
- CASO-RAG-07: OK
- CASO-RAG-08: OK
- CASO-RAG-09: OK
- CASO-RAG-10: OK
- CASO-RAG-11: OK
- CASO-RAG-12: OK
- CASO-RAG-13: OK
- CASO-RAG-14: OK
- CASO-RAG-15: OK
- CASO-RAG-16: OK
- CASO-RAG-17: OK
- CASO-RAG-18: OK
- CASO-RAG-19: OK
- CASO-RAG-20: OK
