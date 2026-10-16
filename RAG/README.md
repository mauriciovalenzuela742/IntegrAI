# Corpus público del recomendador RAG

Esta carpeta contiene 19 publicaciones accesibles de organizaciones públicas: 6 documentos de la Organización Mundial de la Salud (OMS), 12 listas de hitos de los CDC y las Bases Curriculares de Educación Parvularia de MINEDUC Chile. Los archivos se usan como corpus profesional de la demo estática del recomendador; el índice con texto extraído se genera en `privado/rag/indice.json` y no se versiona.

`MANIFEST.csv` registra tamaño, SHA-256, procedencia y URL oficial. Los hashes permiten verificar que los PDF son idénticos a los insumos recibidos. **Que una publicación sea accesible públicamente no equivale a que tenga una licencia abierta de redistribución.** Cuando el documento no declara una licencia redistributiva, el campo se mantiene como `por confirmar`; no se infiere ninguna autorización adicional.

El corpus no constituye validación clínica. Los seis umbrales OMS están marcados `revisado=false`; toda propuesta es apoyo pedagógico, muestra citas breves y requiere decisión de la educadora.

Verificación:

```powershell
.\.venv\Scripts\python.exe tools\rag_ingestar.py verificar
.\.venv\Scripts\python.exe tools\rag_ingestar.py indexar --sin-embeddings
```
