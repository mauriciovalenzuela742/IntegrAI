# Bench del recomendador

Ejecuta 20 casos sintéticos sin AWS:

```powershell
$env:MODO_MOCK='1'
.\.venv\Scripts\python.exe -m bench.recomendador.evaluar --check
```

Comprueba reglas de disparo, revisión humana, privacidad, límites de citas e inyección. `reporte_mock.md` contiene el resultado versionado. DeepEval con Opus 5 queda como evaluación opcional: no se instala ni se atribuyen resultados hasta fijar una versión compatible y disponer de AWS.
