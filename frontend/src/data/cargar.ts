import Papa from 'papaparse';
import educadorasCsv from './educadoras.csv?raw';
import type {
  Educadora,
  Evaluacion,
  Jardin,
  Manifestacion,
  Nino,
  Nivel,
  Observacion,
  ObservacionManifestacion,
  Pendiente,
  LoteRecomendaciones,
  Recomendacion,
} from '../domain/tipos';

export interface Datos {
  educadoras: Educadora[];
  niveles: Nivel[];
  jardines: Jardin[];
  ninos: Nino[];
  observaciones: Observacion[];
  manifestaciones: Manifestacion[];
  observacionManifestaciones: ObservacionManifestacion[];
  /** Nivel consolidado + alerta (que produce el cron en el backend). Opcional:
   *  en el modo CSV estático no existe y el dashboard usa la observación más reciente. */
  evaluaciones?: Evaluacion[];
}

type Fila = Record<string, string>;

function filasDesdeCsv(texto: string): Fila[] {
  const resultado = Papa.parse<Fila>(texto, { header: true, skipEmptyLines: true });
  return resultado.data;
}

/**
 * Fuente de datos. Si `VITE_API_BASE` está definido, el dashboard lee los datos
 * VIVOS del backend (`GET /api/datos`: incluye JAR-EQUIPO y las observaciones que
 * llegan por WhatsApp). Si no está definido —o si la API falla— cae de vuelta a
 * los CSV estáticos (dataset sintético E-1) que ya vivían en `data/`.
 *
 *   VITE_API_BASE sin definir  -> CSV estáticos (GitHub Pages)
 *   VITE_API_BASE="" (vacío)   -> mismo origen (CloudFront enruta /api/* al backend)
 *   VITE_API_BASE="http://..." -> backend absoluto (requiere CORS)
 */
const RAW_API_BASE = import.meta.env.VITE_API_BASE;
const USAR_API = RAW_API_BASE !== undefined;
const API_BASE = (RAW_API_BASE ?? '').replace(/\/+$/, '');

/** ¿El dashboard está leyendo datos VIVOS del backend? (habilita vistas que lo requieren). */
export function usaApi(): boolean {
  return USAR_API;
}

/** URL del stream SSE de eventos (o null si el dashboard está en modo CSV). */
export function urlEventos(): string | null {
  return USAR_API ? `${API_BASE}/api/eventos` : null;
}

interface DatosCrudos {
  ruta_niveles?: Fila[];
  jardines?: Fila[];
  ninos?: Fila[];
  observaciones?: Fila[];
  manifestaciones?: Fila[];
  observacion_manifestaciones?: Fila[];
  evaluaciones?: Fila[];
}

function educadorasDesde(filas: Fila[]): Educadora[] {
  return filas.map((f) => ({
    idEducadora: f.id_educadora ?? '',
    idJardin: f.id_jardin ?? '',
    rol: f.rol ?? '',
    aniosExperiencia: Number(f.anios_experiencia),
  }));
}

const EDUCADORAS_DEMO = educadorasDesde(filasDesdeCsv(educadorasCsv));

function nivelesDesde(filas: Fila[]): Nivel[] {
  return filas.map((f) => ({
    nivel: Number(f.nivel),
    nombreNivel: f.nombre_nivel ?? '',
    edadMinMeses: Number(f.edad_min_meses),
    edadMaxMeses: Number(f.edad_max_meses),
    descripcion: f.descripcion ?? '',
  }));
}

function jardinesDesde(filas: Fila[]): Jardin[] {
  return filas.map((f) => ({
    idJardin: f.id_jardin ?? '',
    nombreFantasia: f.nombre_fantasia ?? '',
    comuna: f.comuna ?? '',
    region: f.region ?? '',
  }));
}

function ninosDesde(filas: Fila[]): Nino[] {
  return filas.map((f) => ({
    idNino: f.id_nino ?? '',
    nombreVisible: f.nombre_visible ?? '',
    fechaNacimiento: f.fecha_nacimiento ?? '',
    idJardin: f.id_jardin ?? '',
    salaGrupo: f.sala_grupo ?? '',
    fechaIngreso: f.fecha_ingreso ?? '',
  }));
}

function observacionesDesde(filas: Fila[]): Observacion[] {
  return filas.map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idNino: f.id_nino ?? '',
    fechaObservacion: f.fecha_observacion ?? '',
    formatoCaptura: f.formato_captura ?? '',
    nivelEstimado: Number(f.nivel_estimado),
  }));
}

function manifestacionesDesde(filas: Fila[]): Manifestacion[] {
  return filas.map((f) => ({
    idManifestacion: f.id_manifestacion ?? '',
    nivel: Number(f.nivel),
    dominio: f.dominio ?? '',
    textoObservable: f.texto_observable ?? '',
  }));
}

function omDesde(filas: Fila[]): ObservacionManifestacion[] {
  return filas.map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idManifestacion: f.id_manifestacion ?? '',
  }));
}

function evaluacionesDesde(filas: Fila[]): Evaluacion[] {
  return filas.map((f) => ({
    idNino: f.id_nino ?? '',
    dominio: f.dominio ?? '',
    nivel: Number(f.nivel),
    margen: Number(f.margen),
    periodo: f.periodo ?? '',
    tendencia: f.tendencia ?? '',
    alerta: f.alerta && f.alerta !== '' ? f.alerta : null,
    origen: f.origen ?? 'auto',
  }));
}

function armarDatos(r: DatosCrudos, educadoras: Educadora[]): Datos {
  return {
    educadoras,
    niveles: nivelesDesde(r.ruta_niveles ?? []),
    jardines: jardinesDesde(r.jardines ?? []),
    ninos: ninosDesde(r.ninos ?? []),
    observaciones: observacionesDesde(r.observaciones ?? []),
    manifestaciones: manifestacionesDesde(r.manifestaciones ?? []),
    observacionManifestaciones: omDesde(r.observacion_manifestaciones ?? []),
    evaluaciones: evaluacionesDesde(r.evaluaciones ?? []),
  };
}

async function desdeApi(educadoras: Educadora[]): Promise<Datos> {
  const respuesta = await fetch(`${API_BASE}/api/datos`);
  if (!respuesta.ok) {
    throw new Error(`El backend respondió ${respuesta.status} en /api/datos`);
  }
  return armarDatos((await respuesta.json()) as DatosCrudos, educadoras);
}

function rutaCsv(nombre: string): string {
  return `${import.meta.env.BASE_URL}${nombre}`;
}

async function leerCsv(nombre: string): Promise<Fila[]> {
  const ruta = rutaCsv(nombre);
  const respuesta = await fetch(ruta);
  if (!respuesta.ok) {
    throw new Error(`No se pudo cargar ${ruta} (${respuesta.status})`);
  }
  const texto = await respuesta.text();
  return filasDesdeCsv(texto);
}

async function desdeCsv(educadoras: Educadora[]): Promise<Datos> {
  const [
    ruta_niveles,
    jardines,
    ninos,
    observaciones,
    manifestaciones,
    observacion_manifestaciones,
  ] = await Promise.all([
    leerCsv('ruta_niveles.csv'),
    leerCsv('jardines.csv'),
    leerCsv('ninos.csv'),
    leerCsv('observaciones.csv'),
    leerCsv('manifestaciones.csv'),
    leerCsv('observacion_manifestaciones.csv'),
  ]);
  return armarDatos({
    ruta_niveles,
    jardines,
    ninos,
    observaciones,
    manifestaciones,
    observacion_manifestaciones,
  }, educadoras);
}

function pendienteDesde(f: Record<string, unknown>): Pendiente {
  const num = (v: unknown): number | null => (v === null || v === undefined || v === '' ? null : Number(v));
  const txt = (v: unknown): string => (v === null || v === undefined ? '' : String(v));
  return {
    idPendiente: txt(f.id_pendiente),
    idNinoPropuesto: txt(f.id_nino_propuesto),
    nombreVisible: txt(f.nombre_visible),
    idEducadora: f.id_educadora ? String(f.id_educadora) : null,
    nivelPropuesto: num(f.nivel_propuesto),
    dominio: f.dominio ? String(f.dominio) : null,
    margen: num(f.margen),
    motivo: txt(f.motivo),
    evidencia: txt(f.evidencia),
    estado: txt(f.estado),
    creadoEn: txt(f.creado_en),
    idJardin: f.id_jardin ? String(f.id_jardin) : null,
    salaGrupo: f.sala_grupo ? String(f.sala_grupo) : null,
  };
}

/** Cola POR VERIFICAR (requiere backend; en modo CSV devuelve []). */
export async function cargarPendientes(): Promise<Pendiente[]> {
  if (!USAR_API) {
    return [];
  }
  const respuesta = await fetch(`${API_BASE}/api/pendientes`);
  if (!respuesta.ok) {
    throw new Error(`El backend respondió ${respuesta.status} en /api/pendientes`);
  }
  const datos = (await respuesta.json()) as { pendientes?: Record<string, unknown>[] };
  return (datos.pendientes ?? []).map(pendienteDesde);
}

/** Aprueba / edita (con nivel) / rechaza un pendiente (requiere backend). */
export async function resolverPendiente(
  idPendiente: string,
  accion: 'aprobado' | 'editado' | 'rechazado',
  nivel?: number,
): Promise<void> {
  if (!USAR_API) {
    throw new Error('Requiere datos vivos del backend');
  }
  const respuesta = await fetch(`${API_BASE}/api/pendiente/resolver`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_pendiente: idPendiente, accion, nivel }),
  });
  if (!respuesta.ok) {
    throw new Error(`El backend respondió ${respuesta.status} al resolver`);
  }
  const datos = (await respuesta.json()) as { ok?: boolean; error?: string };
  if (datos && datos.ok === false) {
    throw new Error(datos.error ?? 'no se pudo resolver');
  }
}

/** Ajuste MANUAL del nivel de un niño/a (la profesora corrige, incluso los auto). */
export async function ajustarNivel(idNino: string, nivel: number, resueltoPor?: string): Promise<void> {
  if (!USAR_API) {
    throw new Error('Requiere datos vivos del backend');
  }
  const respuesta = await fetch(`${API_BASE}/api/evaluacion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_nino: idNino, nivel, resuelto_por: resueltoPor }),
  });
  if (!respuesta.ok) {
    throw new Error(`El backend respondió ${respuesta.status} al ajustar el nivel`);
  }
  const datos = (await respuesta.json()) as { ok?: boolean; error?: string };
  if (datos && datos.ok === false) {
    throw new Error(datos.error ?? 'no se pudo ajustar el nivel');
  }
}

function recomendacionDesde(f: Record<string, unknown>): Recomendacion {
  const hito = f.hito as Record<string, unknown> | null;
  return {
    idRecomendacion: String(f.id_recomendacion), idNino: String(f.id_nino),
    idJardin: String(f.id_jardin), salaGrupo: String(f.sala_grupo), estadoRevision: 'por_verificar',
    hito: hito ? { id: String(hito.id), estado: String(hito.estado), zona: String(hito.zona), edadMeses: Number(hito.edad_meses) } : null,
    hallazgosDeterministicos: ((f.hallazgos_deterministicos ?? []) as Record<string, unknown>[]).map((h) => ({
      id: String(h.id), tipo: String(h.tipo), regla: String(h.regla), resultado: String(h.resultado),
      observacionIds: (h.observacion_ids ?? []) as string[],
    })),
    resumen: String(f.resumen),
    sugerencias: ((f.sugerencias ?? []) as Record<string, unknown>[]).map((s) => ({
      texto: String(s.texto), citas: ((s.citas ?? []) as Record<string, unknown>[]).map((c) => ({
        fuenteId: String(c.fuente_id), organizacion: String(c.organizacion), titulo: String(c.titulo),
        paginaPdf: Number(c.pagina_pdf), fragmento: String(c.fragmento), url: String(c.url),
      })),
    })),
    derivacionSalud: Boolean(f.derivacion_salud), aviso: String(f.aviso),
  };
}

/** Recomendaciones estáticas disponibles tanto con CSV como con API; 404 significa que no hay demo. */
export async function cargarRecomendaciones(): Promise<LoteRecomendaciones> {
  const ruta = `${import.meta.env.BASE_URL}recomendaciones.json`;
  const respuesta = await fetch(ruta);
  if (respuesta.status === 404) {
    return { version: 1, generadoEn: '', umbralesPorValidar: true,
      aviso: 'Propuesta para el criterio de la educadora. No es un diagnóstico.', items: [] };
  }
  if (!respuesta.ok) throw new Error(`No se pudo cargar ${ruta} (${respuesta.status})`);
  const crudo = await respuesta.json() as Record<string, unknown>;
  if (crudo.version !== 1 || crudo.umbrales_por_validar !== true || !Array.isArray(crudo.items)) {
    throw new Error('recomendaciones.json no cumple el contrato público');
  }
  return { version: 1, generadoEn: String(crudo.generado_en), umbralesPorValidar: true,
    aviso: String(crudo.aviso), items: (crudo.items as Record<string, unknown>[]).map(recomendacionDesde) };
}

export async function cargarDatos(): Promise<Datos> {
  if (USAR_API) {
    try {
      return await desdeApi(EDUCADORAS_DEMO);
    } catch (error) {
      console.warn('No se pudo leer /api/datos; uso los CSV estáticos.', error);
    }
  }
  return desdeCsv(EDUCADORAS_DEMO);
}
