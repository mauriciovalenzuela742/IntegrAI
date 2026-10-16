import type { NotificacionAdvertencia, Pendiente } from './tipos';

// El backend decide qué entra a la cola; la UI ya NO re-filtra por margen (antes ocultaba casos).
export const UMBRAL_ADVERTENCIA = 0.15;

export function notificacionesDesdePendientes(
  pendientes: Pendiente[],
): NotificacionAdvertencia[] {
  return pendientes
    .map((pendiente, indice) => ({ pendiente, indice }))
    .sort(
      (a, b) =>
        b.pendiente.creadoEn.localeCompare(a.pendiente.creadoEn) ||
        a.indice - b.indice,
    )
    .map(({ pendiente }) => ({
      idNotificacion: pendiente.idPendiente,
      tipo: 'advertencia',
      titulo: `Confirma a ${pendiente.nombreVisible || pendiente.idNinoPropuesto}`,
      detalle: `El sistema propuso el nivel ${pendiente.nivelPropuesto ?? '—'} y quedó por confirmar.`,
      fecha: pendiente.creadoEn,
      href: `/nino/${encodeURIComponent(pendiente.idNinoPropuesto)}`,
      pendiente,
    }));
}
