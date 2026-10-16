# IntegrAI · Frontend del dashboard

Interfaz React para coordinación y profesoras. Permite consultar los niveles de desarrollo (1–9), revisar trayectorias y mostrar advertencias cuando una clasificación queda bajo el umbral. No edita clasificaciones.

**Demo en vivo:** https://integrai-coder.github.io/IntegrAI/ (GitHub Pages) · https://d2eg8hbkfurj9b.cloudfront.net (CloudFront)

## Requisitos y ejecución

- Node.js 18+ y npm.

```bash
cd frontend
npm i
npm run dev     # servidor de desarrollo (Vite)
npm test        # tests Vitest en modo single-run
npm run build   # chequeo de tipos + build de producción
```

Abre la URL que imprime Vite (por defecto `http://localhost:5173`). La aplicación usa `HashRouter`.

## Fuentes de datos y revisión

Los CSV generales viven en `../data`. `vite.config.ts` usa `publicDir: '../data'`, por lo que Vite los sirve en desarrollo y los incluye en `dist/`. Las rutas se construyen con `import.meta.env.BASE_URL` para funcionar tanto en `/` como en el subpath `/IntegrAI/`. La copia de `educadoras.csv` usada por el demo vive en `src/data/` y Vite la integra en el bundle, por lo que no requiere publicar un CSV adicional.

`DatosProvider` (`src/data/DatosContext.tsx`) carga los datos una vez y los comparte entre las vistas. Si se configura `VITE_API_BASE`, intenta `GET /api/datos`, conserva el fallback CSV y refresca mediante SSE (`/api/eventos`) más polling. Las educadoras demo empaquetadas no agregan una solicitud de red ni bloquean `/api/datos` cuando el despliegue usa `VITE_REVISION=api`.

La fuente de revisión se elige de forma independiente:

```dotenv
# Predeterminado cuando no se define: demo
VITE_REVISION=demo

# Opcional e independiente: datos vivos del dashboard
# VITE_API_BASE=
```

- `VITE_REVISION=demo`: deriva profesoras de `educadoras.csv`. Ordena educadoras y salas, reparte una sala de su jardín a cada educadora de forma cíclica y genera teléfonos ficticios (`EDU-0007` → `56900000007`). Sobre las 12 observaciones más recientes de sus cursos calcula un margen determinista con FNV-1a de 32 bits: `hash / 2^32 × 0,6`. Solo los márgenes menores a `0,15` generan advertencias. La pantalla muestra **Modo demostración** y permite ingresar con un clic.
- `VITE_REVISION=api`: usa rutas del mismo origen, sin enviar API keys ni secretos:
  - `GET /api/profesora?telefono=<teléfono>` → `{id_educadora, telefono, cursos:[{id_jardin, sala_grupo}]}`.
  - `GET /api/pendientes?from=<teléfono>` → cola de observaciones por verificar.

`VITE_API_BASE` controla únicamente la fuente general CSV/API y `VITE_REVISION` controla únicamente el ingreso y las advertencias de profesoras; se pueden combinar de forma independiente.

## Vistas

### Coordinación (sin sesión de profesora)

1. `/` — cursos con buscador.
2. `/curso/:idJardin/:sala` — resumen, distribución y alumnos del curso.
3. `/nino/:idNino` — ficha, trayectoria y observaciones.
4. `/jardines` — panorama por jardín.
5. `/experiencia` — acompañamiento para coordinación con cursos, evidencia, trayectorias y focos pedagógicos.
6. `/pendientes` — cola general disponible con backend.

La cabecera conserva Cursos, Jardines y Por verificar, agrega **Acompañamiento** y mantiene **Soy profesora**.

### Profesora

1. `/profesora` — ingreso con el mismo número de WhatsApp usado para enviar observaciones.
2. `/profesora/inicio` — conteo de cursos y casos, todas las advertencias y tabla de cursos propios.
3. `/profesora/experiencia` — acompañamiento calculado únicamente después de filtrar los cursos de la sesión.
4. La campana cuenta todas las advertencias y despliega las 6 más recientes. No existe estado leído ni acción para marcar una advertencia: desaparece solo cuando el servicio deja de devolver el pendiente.

Los teléfonos se normalizan conservando solo dígitos. Coinciden si son iguales o, cuando ambos tienen al menos 9 dígitos, si tienen los mismos últimos 9. La sesión se guarda en `sessionStorage`, por lo que sobrevive a recargar la pestaña y termina al pulsar **Salir** o cerrar la pestaña.

> **Importante — no es seguridad:** el filtro por cursos solo ordena y restringe la interfaz. Los datos ya cargados siguen en el navegador; la autorización y el filtrado reales deben implementarse en el backend.

No se implementa encuesta de clasificación. La única notificación es la advertencia por clasificación bajo el umbral.

## Lógica de dominio

Las funciones puras de `src/domain/` tienen tests Vitest. Entre otras cosas calculan edad, nivel esperado, brecha, nivel vigente, resúmenes, comparación de teléfonos, asignación demo, acceso a cursos, advertencias y la experiencia de acompañamiento. **Curso** es la combinación `id_jardin + sala_grupo`.

La experiencia mantiene separadas tres señales que antes podían aparecer agregadas:

- **Señal de rúbrica:** texto de la evaluación consolidada del backend.
- **Brecha de edad:** comparación entre nivel vigente y rango etario mediante las reglas existentes.
- **Comparación de sala:** diferencia relativa respecto del promedio del grupo-curso.

Los dominios se derivan del catálogo de manifestaciones cargado. La ausencia de evidencia se presenta como información pendiente de observar, no como déficit. Las actividades sugeridas son ideas generales de apoyo pedagógico, no instrucciones clínicas.

Solo se muestran códigos o etiquetas abreviadas de niños/as, nunca RUT ni nombres completos. El pie recuerda que la herramienta no constituye diagnóstico clínico.

## Despliegue

GitHub Pages publica bajo `/IntegrAI/`; por eso Vite usa esa base por defecto y las rutas quedan después de `#`. CloudFront publica la aplicación en `/` con:

```bash
python tools/desplegar_frontend.py subir
```

El build integra `src/data/educadoras.csv` en los assets de Vite, que el despliegue de CloudFront ya publica; no se requiere agregar ese CSV a la lista de archivos estáticos.

## Pendientes del backend (fuera de alcance)

Estos puntos solo se documentan; no están resueltos por los filtros del frontend:

1. `/api/profesora` identifica por número, pero todavía necesita una sesión que demuestre posesión del teléfono y aplique autorización servidor a servidor.
2. `/api/datos`, `/api/pendientes`, `/api/pendiente/resolver` y `/api/evaluacion` deben limitar cada respuesta o mutación al rol, jardín y cursos autorizados. El navegador no debe recibir el dataset general cuando una profesora inicia sesión.
3. El backend debe exponer metadatos no sensibles del marco activo si la interfaz necesita explicar reglas o dominios específicos; la rúbrica privada no debe publicarse.

Hasta resolverlos, el modo API no proporciona seguridad completa. La restricción por profesora aplicada en React solo ordena la experiencia y no sustituye autorización del backend.
