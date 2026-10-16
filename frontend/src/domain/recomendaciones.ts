import type { LoteRecomendaciones, Recomendacion, DecisionRecomendacion } from './tipos';

export const CLAVE_DECISIONES = 'integrai.recomendaciones.v1';

export function aplicarDecisiones(
  items: Recomendacion[],
  decisiones: Record<string, DecisionRecomendacion>,
): Array<Recomendacion & { decision?: DecisionRecomendacion }> {
  return items
    .filter((item) => decisiones[item.idRecomendacion]?.estado !== 'descartada')
    .map((item) => ({ ...item, decision: decisiones[item.idRecomendacion] }));
}

export function recomendacionesPendientes(
  items: Recomendacion[],
  decisiones: Record<string, DecisionRecomendacion>,
): Recomendacion[] {
  return items.filter((item) => !decisiones[item.idRecomendacion]);
}

export function recomendacionesAprobadas(
  items: Recomendacion[],
  decisiones: Record<string, DecisionRecomendacion>,
  idNino: string,
): Array<Recomendacion & { textoVisible: string }> {
  return items.flatMap((item) => {
    const decision = decisiones[item.idRecomendacion];
    if (item.idNino !== idNino || !decision || !['aprobada', 'editada'].includes(decision.estado)) return [];
    return [{ ...item, textoVisible: decision.textoEditado?.trim() || item.resumen }];
  });
}

export function esLoteRecomendaciones(valor: unknown): valor is LoteRecomendaciones {
  if (!valor || typeof valor !== 'object') return false;
  const lote = valor as Partial<LoteRecomendaciones>;
  return lote.version === 1 && lote.umbralesPorValidar === true && typeof lote.aviso === 'string' && Array.isArray(lote.items)
    && lote.items.every((item) => item && typeof item.idRecomendacion === 'string'
      && item.estadoRevision === 'por_verificar' && /^NINO-\d{5}$/.test(item.idNino)
      && Array.isArray(item.hallazgosDeterministicos) && Array.isArray(item.sugerencias));
}
