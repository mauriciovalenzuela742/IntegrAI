import type { Datos } from '../data/cargar';
import type { Evaluacion, Manifestacion, Nino, Nivel, Observacion } from './tipos';
import {
  brecha,
  edadMeses,
  nivelEsperado,
  nivelVigente,
  promedio,
  tieneAlerta,
} from './metrics';

/** Un niño/a se considera REZAGADO en su grupo-curso si su nivel está más de
 *  `UMBRAL_REZAGO_RELATIVO` niveles por debajo del promedio de su sala (comparación
 *  RELATIVA con los pares — el criterio que pidió Fundación Integra, FAQ E1 #5/#8). */
export const UMBRAL_REZAGO_RELATIVO = 1.0;

export interface AlumnoCurso {
  idNino: string;
  /** Etiqueta legible del backend ("Emilia Co."); si falta, la UI cae al código. */
  nombreVisible?: string;
  edadMeses: number;
  nivelVigente: number | null;
  nivelEsperado: number | null;
  brecha: number | null;
  /** Texto rubric-aware entregado por la evaluación consolidada del backend. */
  alertaRubrica: string | null;
  /** Señal etaria calculada con la brecha y el umbral existentes. */
  alertaEdad: boolean;
  /** Agregado compatible: rúbrica, edad o rezago relativo. */
  alerta: boolean;
  /** Rezagado RELATIVO a su sala (no a un estándar absoluto). */
  rezagoRelativo: boolean;
  /** El nivel vigente fue AJUSTADO manualmente por la profesora. */
  ajustadoManual: boolean;
}

export interface ResumenCurso {
  idJardin: string;
  salaGrupo: string;
  nombreJardin: string;
  comuna: string;
  totalNinos: number;
  nivelPromedio: number | null;
  totalAlertas: number;
}

export function claveCurso(idJardin: string, salaGrupo: string): string {
  return `${idJardin}__${salaGrupo}`;
}

/** Nivel CONSOLIDADO por niño/a (la evaluación `global` más reciente que produce el
 *  cron en el backend). Si no hay, el dashboard cae a la observación más reciente. */
function evaluacionesGlobales(datos: Datos): Map<string, Evaluacion> {
  const mapa = new Map<string, Evaluacion>();
  for (const e of datos.evaluaciones ?? []) {
    if (e.dominio !== 'global') continue;
    const previo = mapa.get(e.idNino);
    if (!previo || e.periodo >= previo.periodo) {
      mapa.set(e.idNino, e);
    }
  }
  return mapa;
}

function observacionesDe(datos: Datos): Map<string, Observacion[]> {
  const mapa = new Map<string, Observacion[]>();
  for (const obs of datos.observaciones) {
    const lista = mapa.get(obs.idNino) ?? [];
    lista.push(obs);
    mapa.set(obs.idNino, lista);
  }
  return mapa;
}

export function alumnoDesde(
  nino: Nino,
  observaciones: Observacion[],
  niveles: Nivel[],
  hoy: Date,
  evaluacion?: Evaluacion,
): AlumnoCurso {
  const meses = edadMeses(nino.fechaNacimiento, hoy);
  const vigente = evaluacion ? evaluacion.nivel : nivelVigente(observaciones);
  const esperado = nivelEsperado(meses, niveles);
  const valorBrecha = brecha(vigente, esperado);
  const textoRubrica = evaluacion?.alerta?.trim() ?? '';
  const alertaRubrica = textoRubrica || null;
  const alertaEdad = tieneAlerta(valorBrecha);
  return {
    idNino: nino.idNino,
    nombreVisible: nino.nombreVisible ?? '',
    edadMeses: meses,
    nivelVigente: vigente,
    nivelEsperado: esperado,
    brecha: valorBrecha,
    alertaRubrica,
    alertaEdad,
    alerta: alertaRubrica !== null || alertaEdad,
    rezagoRelativo: false,
    ajustadoManual: evaluacion ? (evaluacion.origen ?? '').startsWith('manual') : false,
  };
}

/** Marca el rezago RELATIVO de un grupo-curso: compara cada niño/a con el promedio
 *  de SU sala y suma ese rezago al flag agregado de atención. */
function conRezagoRelativo(alumnos: AlumnoCurso[]): AlumnoCurso[] {
  const niveles = alumnos
    .map((a) => a.nivelVigente)
    .filter((v): v is number => v !== null);
  const media = promedio(niveles);
  return alumnos.map((a) => {
    const rezagoRelativo =
      media !== null && a.nivelVigente !== null && a.nivelVigente < media - UMBRAL_REZAGO_RELATIVO;
    return { ...a, rezagoRelativo, alerta: a.alerta || rezagoRelativo };
  });
}

export function alumnosDeCurso(
  datos: Datos,
  idJardin: string,
  salaGrupo: string,
  hoy: Date,
): AlumnoCurso[] {
  const obsPorNino = observacionesDe(datos);
  const evs = evaluacionesGlobales(datos);
  const alumnos = datos.ninos
    .filter((n) => n.idJardin === idJardin && n.salaGrupo === salaGrupo)
    .map((n) => alumnoDesde(n, obsPorNino.get(n.idNino) ?? [], datos.niveles, hoy, evs.get(n.idNino)));
  return conRezagoRelativo(alumnos);
}

export function resumenCursos(datos: Datos, hoy: Date): ResumenCurso[] {
  const obsPorNino = observacionesDe(datos);
  const evs = evaluacionesGlobales(datos);
  const jardinPorId = new Map(datos.jardines.map((j) => [j.idJardin, j]));
  const porCurso = new Map<string, { idJardin: string; sala: string; ninos: Nino[] }>();

  for (const nino of datos.ninos) {
    const clave = claveCurso(nino.idJardin, nino.salaGrupo);
    const grupo =
      porCurso.get(clave) ??
      { idJardin: nino.idJardin, sala: nino.salaGrupo, ninos: [] };
    grupo.ninos.push(nino);
    porCurso.set(clave, grupo);
  }

  const resumenes: ResumenCurso[] = [];
  for (const { idJardin, sala, ninos } of porCurso.values()) {
    const alumnos = conRezagoRelativo(
      ninos.map((n) =>
        alumnoDesde(n, obsPorNino.get(n.idNino) ?? [], datos.niveles, hoy, evs.get(n.idNino)),
      ),
    );
    const nivelesVigentes = alumnos
      .map((a) => a.nivelVigente)
      .filter((v): v is number => v !== null);
    const jardin = jardinPorId.get(idJardin);
    resumenes.push({
      idJardin,
      salaGrupo: sala,
      nombreJardin: jardin?.nombreFantasia ?? idJardin,
      comuna: jardin?.comuna ?? '',
      totalNinos: ninos.length,
      nivelPromedio: promedio(nivelesVigentes),
      totalAlertas: alumnos.filter((a) => a.alerta).length,
    });
  }

  return resumenes.sort(
    (a, b) =>
      a.nombreJardin.localeCompare(b.nombreJardin) ||
      a.salaGrupo.localeCompare(b.salaGrupo),
  );
}

export function distribucionNiveles(alumnos: AlumnoCurso[]): { nivel: number; total: number }[] {
  const conteo = new Map<number, number>();
  for (let nivel = 1; nivel <= 9; nivel += 1) {
    conteo.set(nivel, 0);
  }
  for (const alumno of alumnos) {
    if (alumno.nivelVigente !== null) {
      conteo.set(alumno.nivelVigente, (conteo.get(alumno.nivelVigente) ?? 0) + 1);
    }
  }
  return [...conteo.entries()].map(([nivel, total]) => ({ nivel, total }));
}

export interface ObservacionDetallada {
  idObservacion: string;
  fechaObservacion: string;
  formatoCaptura: string;
  nivelEstimado: number;
  manifestaciones: Manifestacion[];
}

export interface FichaNino {
  nino: Nino;
  edadMeses: number;
  nivelVigente: number | null;
  nivelEsperado: number | null;
  brecha: number | null;
  alertaRubrica: string | null;
  alertaEdad: boolean;
  alerta: boolean;
  rezagoRelativo: boolean;
  ajustadoManual: boolean;
  observaciones: ObservacionDetallada[];
}

export function fichaNino(
  datos: Datos,
  idNino: string,
  hoy: Date,
): FichaNino | null {
  const nino = datos.ninos.find((n) => n.idNino === idNino);
  if (!nino) {
    return null;
  }

  const manifestacionPorId = new Map(
    datos.manifestaciones.map((m) => [m.idManifestacion, m]),
  );
  const manifestacionesPorObs = new Map<string, Manifestacion[]>();
  for (const om of datos.observacionManifestaciones) {
    const man = manifestacionPorId.get(om.idManifestacion);
    if (!man) {
      continue;
    }
    const lista = manifestacionesPorObs.get(om.idObservacion) ?? [];
    lista.push(man);
    manifestacionesPorObs.set(om.idObservacion, lista);
  }

  const observaciones = datos.observaciones
    .filter((o) => o.idNino === idNino)
    .sort((a, b) => a.fechaObservacion.localeCompare(b.fechaObservacion));

  // Usamos el alumno del grupo-curso para heredar el rezago RELATIVO a su sala.
  const alumnoCurso = alumnosDeCurso(datos, nino.idJardin, nino.salaGrupo, hoy).find(
    (a) => a.idNino === idNino,
  );
  const alumno =
    alumnoCurso ??
    alumnoDesde(nino, observaciones, datos.niveles, hoy, evaluacionesGlobales(datos).get(idNino));

  const detalladas: ObservacionDetallada[] = observaciones.map((o) => ({
    idObservacion: o.idObservacion,
    fechaObservacion: o.fechaObservacion,
    formatoCaptura: o.formatoCaptura,
    nivelEstimado: o.nivelEstimado,
    manifestaciones: manifestacionesPorObs.get(o.idObservacion) ?? [],
  }));

  return {
    nino,
    edadMeses: alumno.edadMeses,
    nivelVigente: alumno.nivelVigente,
    nivelEsperado: alumno.nivelEsperado,
    brecha: alumno.brecha,
    alertaRubrica: alumno.alertaRubrica,
    alertaEdad: alumno.alertaEdad,
    alerta: alumno.alerta,
    rezagoRelativo: alumno.rezagoRelativo,
    ajustadoManual: alumno.ajustadoManual,
    observaciones: detalladas,
  };
}

export function nivelPorNumero(niveles: Nivel[]): Map<number, Nivel> {
  return new Map(niveles.map((n) => [n.nivel, n]));
}

export interface ResumenJardin {
  idJardin: string;
  nombreJardin: string;
  comuna: string;
  totalSalas: number;
  totalNinos: number;
  nivelPromedio: number | null;
  totalAlertas: number;
  /** Sala más rezagada del jardín (por debajo del promedio del jardín) → alerta a la directora. */
  salaMasRezagada: { salaGrupo: string; nivelPromedio: number } | null;
}

/** Vista de la DIRECTORA: panorama por jardín, comparando sus salas y destacando la
 *  más rezagada (FAQ E1 #1: "detectar un grupo-curso más rezagado y alertar"). */
export function resumenJardines(datos: Datos, hoy: Date): ResumenJardin[] {
  const porJardin = new Map<string, ResumenCurso[]>();
  for (const curso of resumenCursos(datos, hoy)) {
    const lista = porJardin.get(curso.idJardin) ?? [];
    lista.push(curso);
    porJardin.set(curso.idJardin, lista);
  }

  const jardines: ResumenJardin[] = [];
  for (const [idJardin, salas] of porJardin) {
    const nivelPromedio = promedio(
      salas.map((s) => s.nivelPromedio).filter((v): v is number => v !== null),
    );
    const conPromedio = salas.filter((s) => s.nivelPromedio !== null);
    let salaMasRezagada: ResumenJardin['salaMasRezagada'] = null;
    if (conPromedio.length > 0 && nivelPromedio !== null) {
      const peor = conPromedio.reduce((a, b) =>
        (a.nivelPromedio as number) <= (b.nivelPromedio as number) ? a : b,
      );
      if ((peor.nivelPromedio as number) < nivelPromedio - UMBRAL_REZAGO_RELATIVO) {
        salaMasRezagada = { salaGrupo: peor.salaGrupo, nivelPromedio: peor.nivelPromedio as number };
      }
    }
    const primera = salas[0];
    jardines.push({
      idJardin,
      nombreJardin: primera?.nombreJardin ?? idJardin,
      comuna: primera?.comuna ?? '',
      totalSalas: salas.length,
      totalNinos: salas.reduce((s, c) => s + c.totalNinos, 0),
      nivelPromedio,
      totalAlertas: salas.reduce((s, c) => s + c.totalAlertas, 0),
      salaMasRezagada,
    });
  }
  return jardines.sort((a, b) => a.nombreJardin.localeCompare(b.nombreJardin));
}
