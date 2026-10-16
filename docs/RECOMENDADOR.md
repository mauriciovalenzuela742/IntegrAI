# Recomendador RAG — demo estática referenciada

## Qué demuestra

Después del clasificador, IntegrAI puede producir una propuesta pedagógica con dos respaldos: (1) análisis determinístico de edad, estado del hito, curso y nivel E-1; y (2) pasajes breves de publicaciones de OMS, CDC y MINEDUC. Todo item nace `por_verificar`. La educadora puede aprobar, editar o descartar; solo una recomendación aprobada o editada aparece en la ficha.

> Propuesta para el criterio de la educadora. No es un diagnóstico.

Esta rama **no integra ni despliega el recomendador en EC2/WhatsApp/CloudFront**. Genera `data/recomendaciones.json` con datos sintéticos y GitHub Pages lo carga. Las decisiones de la preview viven en `localStorage` bajo `integrai.recomendaciones.v1`.

## Flujo

```text
19 PDF públicos (RAG/) → verificación SHA-256 → extracción por página
→ privado/rag/indice.json (no versionado) → análisis determinístico
→ plantilla referenciada → data/recomendaciones.json
→ Por verificar → aprobar/editar/descartar → ficha
```

La búsqueda es bilingüe, léxica offline y opcionalmente híbrida con Titan v2. La extracción/redacción Sonnet 5 es opcional; el modo mock usa reglas y plantillas determinísticas. Importar `src.recomendador` no importa `pypdf` ni DeepEval.

## Ejecutar

PowerShell 5.1, desde el repositorio:

```powershell
$env:MODO_MOCK='1'
.\.venv\Scripts\python.exe tools\rag_ingestar.py verificar
.\.venv\Scripts\python.exe tools\rag_ingestar.py indexar --sin-embeddings
.\.venv\Scripts\python.exe -m src.recomendador.rag sentarse_sin_apoyo 3
.\.venv\Scripts\python.exe tools\recomendar_lote.py
.\.venv\Scripts\python.exe -m bench.recomendador.evaluar --check
Push-Location frontend; npm test; npm run build; Pop-Location
```

Opciones del lote: `--max`, `--cursos JAR-0013:SG-C` y `--fecha-ref AAAA-MM-DD`. Antes de escribir, Pydantic valida el contrato completo. Dos generaciones son iguales salvo `generado_en`.

## Demo en la web

1. Abrir `#/pendientes` y buscar `NINO-00001` / `REC-00001`.
2. Revisar análisis, cita, página y enlace oficial; elegir **Aprobar** o **Editar**. La edición mueve el foco al campo etiquetado.
3. Abrir `#/nino/NINO-00001`: la recomendación aprobada aparece tras el panel de nivel vigente. Las pendientes solo enlazan a la cola.
4. **Descartar** elimina la propuesta de la cola y de la ficha. Recargar conserva decisiones en ese navegador.

Las notas demo son adicionales: no existe “Emilio” en `data/ninos.csv`, por lo que no se alteró el dataset para simularlo. Se usan IDs sintéticos ya existentes y se documentan en `datos_sinteticos/recomendador/`.

## Reglas y seguridad

- Edad de hitos: días / 30,4375. Zonas: antes de p50, p50–A, A–p99 y posterior a p99; `A` usa CDC cuando existe o p75 OMS como fallback.
- Los seis hitos y equivalencias permanecen `revisado=false`; 9,0 meses en sentarse sin apoyo cae en atención.
- `sin_registro` nunca se convierte en `no_logrado`. La negación exige observación y cita literal.
- Comparación de curso solo con al menos cinco registros y sin identificar pares.
- Nivel y brecha reproducen `frontend/src/domain/consultas.ts` y `metrics.ts`.
- Inyección produce `posible_manipulacion`, sin llamada LLM ni sugerencia.
- Citas profesionales literales, con fuente/página/URL y máximo 300 caracteres.
- IDs sintéticos, sin nombres, teléfonos, RUT, correos, secretos o direcciones de infraestructura.
- Fuera de ventana obliga sugerir conversación con salud sin diagnosticar.

## Corpus y licencias

`RAG/MANIFEST.csv` contiene 6 PDF OMS, 12 CDC y 1 MINEDUC, con tamaño y SHA-256 reales. `publicación accesible` no implica licencia abierta; se usa `por confirmar` cuando el PDF no declara una licencia redistributiva. El índice y el texto completo extraído no se publican.

## Limitaciones y pendiente productivo

Los umbrales requieren revisión humana por Integra y un profesional de salud. DeepEval/Opus 5 no se ejecuta hasta fijar una versión y disponer de AWS; el bench publicado es determinístico. La persistencia, RBAC, auditoría, integración con el clasificador y despliegue productivo quedan futuros.

Bug conocido del área de Sebastián: `_procesar` no encola observaciones `por_verificar` y el cron las excluye. Esta rama lo documenta y no cambia `webhook_ec2.py` ni la cola.
