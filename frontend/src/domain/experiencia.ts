import type { Datos } from '../data/cargar';
import type { FichaNino } from './consultas';
import type { Manifestacion, Nino, Observacion } from './tipos';

export interface DominioInfo {
  id: string;
  nombre: string;
}

const ETIQUETAS_DOMINIO: Record<string, string> = {
  motor_grueso: 'Motor grueso',
  motor_fino: 'Motor fino',
  lenguaje_comunicacion: 'Lenguaje y comunicación',
  socioemocional: 'Socioemocional',
  cognitivo: 'Cognitivo',
};

const ORDEN_DOMINIOS = Object.keys(ETIQUETAS_DOMINIO);

export function canonicalizarDominio(id: string): string {
  return id.trim().toLowerCase();
}

export function nombreDominio(id: string): string {
  const canonico = canonicalizarDominio(id);
  return ETIQUETAS_DOMINIO[canonico] ?? canonico.split('_').join(' ');
}

/** Los dominios vienen del catálogo cargado; las etiquetas conocidas son solo presentación. */
export function dominiosDisponibles(manifestaciones: Manifestacion[]): DominioInfo[] {
  const ids = [...new Set(manifestaciones.map((m) => canonicalizarDominio(m.dominio)).filter(Boolean))];
  return ids
    .sort((a, b) => {
      const ia = ORDEN_DOMINIOS.indexOf(a);
      const ib = ORDEN_DOMINIOS.indexOf(b);
      if (ia >= 0 && ib >= 0) return ia - ib;
      if (ia >= 0) return -1;
      if (ib >= 0) return 1;
      return a.localeCompare(b);
    })
    .map((id) => ({ id, nombre: nombreDominio(id) }));
}

export function dominiosCubiertos(ficha: FichaNino, dominios: DominioInfo[]): string[] {
  const observados = new Set(
    ficha.observaciones.flatMap((obs) => obs.manifestaciones.map((m) => canonicalizarDominio(m.dominio))),
  );
  return dominios.map((d) => d.id).filter((id) => observados.has(id));
}

export function dominiosFaltantes(ficha: FichaNino, dominios: DominioInfo[]): string[] {
  const cubiertos = new Set(dominiosCubiertos(ficha, dominios));
  return dominios.map((d) => d.id).filter((id) => !cubiertos.has(id));
}

export type TipoCausaAtencion = 'rubrica' | 'edad' | 'sala';

export interface CausaAtencion {
  tipo: TipoCausaAtencion;
  titulo: string;
  detalle: string;
}

/** Explica por separado cada señal. Ninguna de estas señales constituye un diagnóstico. */
export function causasAtencion(ficha: FichaNino): CausaAtencion[] {
  const causas: CausaAtencion[] = [];
  if (ficha.alertaRubrica) {
    causas.push({
      tipo: 'rubrica',
      titulo: 'Señal del marco de evaluación',
      detalle: ficha.alertaRubrica,
    });
  }
  if (ficha.alertaEdad) {
    causas.push({
      tipo: 'edad',
      titulo: 'Brecha respecto del rango de edad habitual',
      detalle: ficha.brecha === null
        ? 'No fue posible calcular la brecha con los datos disponibles.'
        : `El nivel vigente está ${Math.abs(ficha.brecha)} niveles por debajo del esperado según la edad registrada.`,
    });
  }
  if (ficha.rezagoRelativo) {
    causas.push({
      tipo: 'sala',
      titulo: 'Comparación con su grupo-curso',
      detalle: 'El nivel vigente está más de un nivel por debajo del promedio de su sala.',
    });
  }
  return causas;
}

export type EstadoAcompanamiento = 'sin-datos' | 'atencion' | 'observar' | 'al-dia';

export interface Diagnostico {
  estado: EstadoAcompanamiento;
  titulo: string;
  detalle: string;
}

export function diagnostico(ficha: FichaNino): Diagnostico {
  if (ficha.observaciones.length === 0 && ficha.nivelVigente === null) {
    return {
      estado: 'sin-datos',
      titulo: 'Sin información suficiente',
      detalle: 'Todavía no hay registros que permitan describir una trayectoria.',
    };
  }
  const causas = causasAtencion(ficha);
  if (causas.length > 0) {
    return {
      estado: 'atencion',
      titulo: 'Requiere atención pedagógica',
      detalle: `Se ${causas.length === 1 ? 'identificó una señal' : `identificaron ${causas.length} señales`} para revisar en contexto.`,
    };
  }
  if ((ficha.brecha ?? 0) < 0) {
    return {
      estado: 'observar',
      titulo: 'Conviene seguir observando',
      detalle: 'Existe una diferencia leve respecto del rango habitual; continúa registrando evidencia.',
    };
  }
  return {
    estado: 'al-dia',
    titulo: 'Sin señales de atención actuales',
    detalle: 'Mantén observaciones periódicas para comprender la trayectoria en el tiempo.',
  };
}

export interface ResumenTrayectorias {
  avanzan: number;
  estables: number;
  retroceden: number;
  sinSeguimiento: number;
  conSeguimiento: number;
}

export function resumenTrayectorias(
  datos: Datos,
  ninos: Nino[] = datos.ninos,
): ResumenTrayectorias {
  const ids = new Set(ninos.map((n) => n.idNino));
  const porNino = new Map<string, Observacion[]>();
  for (const obs of datos.observaciones) {
    if (!ids.has(obs.idNino)) continue;
    const lista = porNino.get(obs.idNino) ?? [];
    lista.push(obs);
    porNino.set(obs.idNino, lista);
  }

  let avanzan = 0;
  let estables = 0;
  let retroceden = 0;
  let sinSeguimiento = 0;
  for (const nino of ninos) {
    const observaciones = [...(porNino.get(nino.idNino) ?? [])]
      .sort((a, b) => a.fechaObservacion.localeCompare(b.fechaObservacion));
    const primera = observaciones[0];
    const ultima = observaciones[observaciones.length - 1];
    if (!primera || !ultima || observaciones.length < 2) {
      sinSeguimiento += 1;
    } else if (ultima.nivelEstimado > primera.nivelEstimado) {
      avanzan += 1;
    } else if (ultima.nivelEstimado < primera.nivelEstimado) {
      retroceden += 1;
    } else {
      estables += 1;
    }
  }
  return {
    avanzan,
    estables,
    retroceden,
    sinSeguimiento,
    conSeguimiento: avanzan + estables + retroceden,
  };
}


export type EstadoConsultaPendientes = 'inactivo' | 'cargando' | 'listo' | 'error';

export function valorPendientes(estado: EstadoConsultaPendientes, total: number): string {
  if (estado === 'listo') return String(total);
  if (estado === 'cargando') return 'Cargando…';
  return 'No disponible';
}

export interface ResumenManifestacionesRecientes {
  total: number;
  visibles: Manifestacion[];
  restantes: Manifestacion[];
}

/** Prioriza evidencia nueva y deduplica por identificador estable. */
export function manifestacionesRecientes(
  ficha: FichaNino,
  limite = 8,
): ResumenManifestacionesRecientes {
  const unicas = new Map<string, Manifestacion>();
  const observaciones = [...ficha.observaciones]
    .sort((a, b) => b.fechaObservacion.localeCompare(a.fechaObservacion));
  for (const observacion of observaciones) {
    for (const manifestacion of observacion.manifestaciones) {
      if (!unicas.has(manifestacion.idManifestacion)) {
        unicas.set(manifestacion.idManifestacion, manifestacion);
      }
    }
  }
  const todas = [...unicas.values()];
  const corte = Math.max(0, limite);
  return { total: todas.length, visibles: todas.slice(0, corte), restantes: todas.slice(corte) };
}
