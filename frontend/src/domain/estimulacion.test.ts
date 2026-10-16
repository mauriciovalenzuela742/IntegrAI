import { describe, expect, it } from 'vitest';
import type { FichaNino, ObservacionDetallada } from './consultas';
import type { DominioInfo } from './experiencia';
import { estadoManifestaciones, focosPedagogicos } from './estimulacion';
import type { Manifestacion } from './tipos';

const dominios: DominioInfo[] = [
  { id: 'motor_fino', nombre: 'Motor fino' },
  { id: 'cognitivo', nombre: 'Cognitivo' },
  { id: 'nuevo', nombre: 'Nuevo' },
];

function manifestacion(dominio: string, nivel: number): Manifestacion {
  return { idManifestacion: `${dominio}-${nivel}`, dominio, nivel, textoObservable: 'Evidencia' };
}

function observacion(manifestaciones: Manifestacion[]): ObservacionDetallada {
  return { idObservacion: 'O1', fechaObservacion: '2026-01-01', formatoCaptura: 'texto', nivelEstimado: 3, manifestaciones };
}

function ficha(observaciones: ObservacionDetallada[]): FichaNino {
  return {
    nino: { idNino: 'N1', fechaNacimiento: '', idJardin: 'J1', salaGrupo: 'A', fechaIngreso: '' },
    edadMeses: 24,
    nivelVigente: 3,
    nivelEsperado: 3,
    brecha: 0,
    alertaRubrica: null,
    alertaEdad: false,
    alerta: false,
    rezagoRelativo: false,
    ajustadoManual: false,
    observaciones,
  };
}

describe('estadoManifestaciones', () => {
  it('cuenta evidencia por dominio y conserva dominios desconocidos', () => {
    const estado = estadoManifestaciones(ficha([
      observacion([manifestacion('cognitivo', 5), manifestacion('cognitivo', 3), manifestacion('nuevo', 4)]),
    ]), dominios);
    expect(estado.total).toBe(3);
    expect(estado.porDominio.find((d) => d.dominio === 'cognitivo')?.nivelPromedio).toBe(4);
    expect(estado.sinEvidencia).toEqual(['motor_fino']);
  });

  it('un catálogo vacío produce un estado vacío', () => {
    expect(estadoManifestaciones(ficha([]), [])).toEqual({ total: 0, porDominio: [], sinEvidencia: [] });
  });
});

describe('focosPedagogicos', () => {
  it('prioriza observación donde falta evidencia, sin llamarla déficit', () => {
    const focos = focosPedagogicos(ficha([observacion([manifestacion('cognitivo', 4)])]), dominios, 2);
    expect(focos.map((foco) => foco.motivo)).toEqual(['sin-evidencia', 'sin-evidencia']);
    expect(focos[0]?.dominio).toBe('motor_fino');
  });

  it('ordena evidencia existente por nivel promedio y respeta el máximo', () => {
    const actual = ficha([observacion([
      manifestacion('motor_fino', 5), manifestacion('cognitivo', 2), manifestacion('nuevo', 4),
    ])]);
    const focos = focosPedagogicos(actual, dominios, 2);
    expect(focos.map((foco) => foco.dominio)).toEqual(['cognitivo', 'nuevo']);
  });

  it('no inventa acciones para un dominio desconocido', () => {
    const focos = focosPedagogicos(ficha([]), [{ id: 'nuevo', nombre: 'Nuevo' }]);
    expect(focos[0]?.acciones).toEqual([]);
    expect(focosPedagogicos(ficha([]), dominios, 0)).toEqual([]);
  });
});


it('usa solo las tres observaciones más recientes y canonicaliza dominios', () => {
  const observaciones = [
    { ...observacion([manifestacion('motor_fino', 1)]), idObservacion: 'antigua', fechaObservacion: '2025-01-01' },
    { ...observacion([manifestacion(' cognitivo ', 4)]), idObservacion: 'r1', fechaObservacion: '2026-01-01' },
    { ...observacion([manifestacion('cognitivo', 4)]), idObservacion: 'r2', fechaObservacion: '2026-02-01' },
    { ...observacion([manifestacion('nuevo', 3)]), idObservacion: 'r3', fechaObservacion: '2026-03-01' },
  ];
  const estado = estadoManifestaciones(ficha(observaciones), dominios);
  expect(estado.porDominio.find((d) => d.dominio === 'motor_fino')?.observadas).toBe(0);
  expect(estado.porDominio.find((d) => d.dominio === 'cognitivo')?.observadas).toBe(2);
});

it('las orientaciones conocidas son neutrales y remiten a una experiencia adecuada a la edad', () => {
  const foco = focosPedagogicos(ficha([]), [{ id: 'motor_grueso', nombre: 'Motor grueso' }])[0];
  expect(foco?.acciones[0]?.detalle).toContain('adecuada a su edad');
  expect(foco?.acciones[0]?.detalle).toContain('observa');
});