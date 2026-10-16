import { describe, expect, it } from 'vitest';
import { brecha, edadMeses, nivelEsperado } from './metrics';

const niveles = [{ nivel: 4, nombreNivel: '', edadMinMeses: 6, edadMaxMeses: 9, descripcion: '' }, { nivel: 5, nombreNivel: '', edadMinMeses: 9, edadMaxMeses: 12, descripcion: '' }];
describe('paridad del recomendador', () => {
  it('usa meses completos y bordes semiabiertos', () => {
    expect(edadMeses('2025-01-15', new Date('2025-10-15T12:00:00'))).toBe(9);
    expect(nivelEsperado(9, niveles)).toBe(5);
    expect(brecha(2, 4)).toBe(-2);
  });
});
