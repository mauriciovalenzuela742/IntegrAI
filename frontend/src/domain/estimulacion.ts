import type { FichaNino } from './consultas';
import { canonicalizarDominio, type DominioInfo } from './experiencia';

export const VENTANA_OBSERVACIONES = 3;

export interface AccionEstimulo {
  titulo: string;
  detalle: string;
}

export interface EstadoDominio {
  dominio: string;
  nombre: string;
  observadas: number;
  nivelPromedio: number | null;
}

export interface EstadoManifestaciones {
  total: number;
  porDominio: EstadoDominio[];
  sinEvidencia: string[];
}

export interface FocoPedagogico {
  dominio: string;
  nombre: string;
  motivo: 'sin-evidencia' | 'evidencia-a-observar';
  acciones: AccionEstimulo[];
}

/** Preguntas observacionales neutrales, adaptables al tramo y sin intención clínica. */
export const ACCIONES_POR_DOMINIO: Record<string, AccionEstimulo[]> = {
  motor_grueso: [{
    titulo: 'Movimiento cotidiano',
    detalle: 'En una situación segura y adecuada a su edad, observa cómo cambia de postura, se desplaza o coordina movimientos.',
  }],
  motor_fino: [{
    titulo: 'Exploración con objetos',
    detalle: 'Con materiales seguros y adecuados a su edad, observa cómo alcanza, sostiene, manipula o combina objetos.',
  }],
  lenguaje_comunicacion: [{
    titulo: 'Interacción comunicativa',
    detalle: 'Durante una interacción habitual, observa cómo responde, expresa necesidades y participa en intercambios.',
  }],
  socioemocional: [{
    titulo: 'Participación acompañada',
    detalle: 'En una rutina conocida, observa cómo busca apoyo, expresa emociones y participa con otras personas.',
  }],
  cognitivo: [{
    titulo: 'Exploración y resolución',
    detalle: 'En una experiencia adecuada a su edad, observa cómo explora, anticipa y busca soluciones simples.',
  }],
};

/** Resume únicamente las últimas observaciones para que un registro antiguo no defina el foco actual. */
export function estadoManifestaciones(
  ficha: FichaNino,
  dominios: DominioInfo[],
): EstadoManifestaciones {
  const nivelesPorDominio = new Map<string, number[]>();
  const observacionesRecientes = [...ficha.observaciones]
    .sort((a, b) => b.fechaObservacion.localeCompare(a.fechaObservacion))
    .slice(0, VENTANA_OBSERVACIONES);
  for (const obs of observacionesRecientes) {
    for (const manifestacion of obs.manifestaciones) {
      const id = canonicalizarDominio(manifestacion.dominio);
      const niveles = nivelesPorDominio.get(id) ?? [];
      niveles.push(manifestacion.nivel);
      nivelesPorDominio.set(id, niveles);
    }
  }
  const porDominio = dominios.map((dominio) => {
    const niveles = nivelesPorDominio.get(dominio.id) ?? [];
    return {
      dominio: dominio.id,
      nombre: dominio.nombre,
      observadas: niveles.length,
      nivelPromedio: niveles.length > 0
        ? niveles.reduce((suma, nivel) => suma + nivel, 0) / niveles.length
        : null,
    };
  });
  return {
    total: porDominio.reduce((suma, dominio) => suma + dominio.observadas, 0),
    porDominio,
    sinEvidencia: porDominio.filter((dominio) => dominio.observadas === 0).map((dominio) => dominio.dominio),
  };
}

/** Prioriza información reciente faltante y luego evidencia reciente de niveles menores. */
export function focosPedagogicos(
  ficha: FichaNino,
  dominios: DominioInfo[],
  max = 3,
): FocoPedagogico[] {
  if (max <= 0) return [];
  const estado = estadoManifestaciones(ficha, dominios);
  const faltantes = estado.porDominio
    .filter((dominio) => dominio.observadas === 0)
    .map((dominio) => ({
      dominio: dominio.dominio,
      nombre: dominio.nombre,
      motivo: 'sin-evidencia' as const,
      acciones: ACCIONES_POR_DOMINIO[dominio.dominio] ?? [],
    }));
  const observados = estado.porDominio
    .filter((dominio) => dominio.observadas > 0)
    .sort((a, b) => (a.nivelPromedio ?? Number.POSITIVE_INFINITY) - (b.nivelPromedio ?? Number.POSITIVE_INFINITY))
    .map((dominio) => ({
      dominio: dominio.dominio,
      nombre: dominio.nombre,
      motivo: 'evidencia-a-observar' as const,
      acciones: ACCIONES_POR_DOMINIO[dominio.dominio] ?? [],
    }));
  return [...faltantes, ...observados].slice(0, max);
}
