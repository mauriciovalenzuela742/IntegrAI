import { describe, expect, it } from 'vitest';
import { notificacionesDesdePendientes } from './notificaciones';
import type { Pendiente } from './tipos';

function pendiente(
  idPendiente: string,
  idNinoPropuesto: string,
  margen: number | null,
  creadoEn: string,
  nivelPropuesto = 3,
): Pendiente {
  return {
    idPendiente,
    idNinoPropuesto,
    idEducadora: 'EDU-1',
    nivelPropuesto,
    dominio: null,
    margen,
    motivo: 'margen bajo',
    evidencia: '',
    estado: 'pendiente',
    creadoEn,
    idJardin: 'JAR-1',
    salaGrupo: 'Sala A',
  };
}

describe('notificaciones de advertencia', () => {
  it('mapea el texto, detalle, fecha y vínculo exactos', () => {
    const caso = pendiente('P-1', 'NINO-X', 0.08, '2026-02-03T10:00:00');
    const [notificacion] = notificacionesDesdePendientes([caso]);

    expect(notificacion).toEqual({
      idNotificacion: 'P-1',
      tipo: 'advertencia',
      titulo: 'Confirma a NINO-X',
      detalle: 'El sistema propuso el nivel 3 y quedó por confirmar.',
      fecha: '2026-02-03T10:00:00',
      href: '/nino/NINO-X',
      pendiente: caso,
    });
  });

  it('crea una advertencia por CADA pendiente (ya no filtra por margen)', () => {
    const notificaciones = notificacionesDesdePendientes([
      pendiente('baja', 'N-1', 0.149, '2026-01-01'),
      pendiente('igual', 'N-2', 0.15, '2026-01-02'),
      pendiente('alta', 'N-3', 0.4, '2026-01-03'),
      pendiente('sin-margen', 'N-4', null, '2026-01-04'),
    ]);
    expect(notificaciones.map((n) => n.idNotificacion)).toEqual(['sin-margen', 'alta', 'igual', 'baja']);
  });

  it('ordena de nueva a antigua y conserva el orden en empates', () => {
    const notificaciones = notificacionesDesdePendientes([
      pendiente('antigua', 'N-1', 0.1, '2026-01-01'),
      pendiente('empate-1', 'N-2', 0.1, '2026-02-01'),
      pendiente('empate-2', 'N-3', 0.1, '2026-02-01'),
    ]);
    expect(notificaciones.map((n) => n.idNotificacion)).toEqual([
      'empate-1',
      'empate-2',
      'antigua',
    ]);
  });
});
