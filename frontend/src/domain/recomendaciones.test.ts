import { describe, expect, it } from 'vitest';
import { aplicarDecisiones, recomendacionesAprobadas, recomendacionesPendientes } from './recomendaciones';
import type { Recomendacion } from './tipos';

const item = { idRecomendacion: 'REC-00001', idNino: 'NINO-00001', resumen: 'Original' } as Recomendacion;

describe('decisiones de recomendaciones', () => {
  it('mantiene nuevas recomendaciones pendientes', () => expect(recomendacionesPendientes([item], {})).toHaveLength(1));
  it('descarta sin mutar el item', () => expect(aplicarDecisiones([item], { 'REC-00001': { estado: 'descartada' } })).toEqual([]));
  it('expone solo aprobadas y usa edición', () => {
    expect(recomendacionesAprobadas([item], { 'REC-00001': { estado: 'editada', textoEditado: 'Corregido' } }, 'NINO-00001')[0]?.textoVisible).toBe('Corregido');
  });
});
