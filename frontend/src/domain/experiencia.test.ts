import { describe, expect, it } from 'vitest';
import type { Datos } from '../data/cargar';
import type { FichaNino, ObservacionDetallada } from './consultas';
import { causasAtencion, diagnostico, dominiosCubiertos, dominiosDisponibles, dominiosFaltantes, resumenTrayectorias } from './experiencia';
import type { Manifestacion, Nino, Observacion } from './tipos';

function manifestacion(dominio: string, nivel = 3): Manifestacion {
  return { idManifestacion: `M-${dominio}`, nivel, dominio, textoObservable: 'Conducta observable' };
}

function observacion(manifestaciones: Manifestacion[] = [], nivel = 3): ObservacionDetallada {
  return { idObservacion: 'O1', fechaObservacion: '2026-01-01', formatoCaptura: 'texto', nivelEstimado: nivel, manifestaciones };
}

function ficha(parcial: Partial<FichaNino> = {}): FichaNino {
  return {
    nino: { idNino: 'N1', fechaNacimiento: '2024-01-01', idJardin: 'J1', salaGrupo: 'A', fechaIngreso: '' },
    edadMeses: 24,
    nivelVigente: 3,
    nivelEsperado: 3,
    brecha: 0,
    alertaRubrica: null,
    alertaEdad: false,
    alerta: false,
    rezagoRelativo: false,
    ajustadoManual: false,
    observaciones: [observacion()],
    ...parcial,
  };
}

describe('catálogo dinámico de dominios', () => {
  it('deriva dominios conocidos y desconocidos del catálogo', () => {
    const dominios = dominiosDisponibles([
      manifestacion('dominio_nuevo'),
      manifestacion('cognitivo'),
      manifestacion('cognitivo'),
    ]);
    expect(dominios).toEqual([
      { id: 'cognitivo', nombre: 'Cognitivo' },
      { id: 'dominio_nuevo', nombre: 'dominio nuevo' },
    ]);
  });

  it('distingue evidencia disponible y faltante sin inventar dominios', () => {
    const dominios = dominiosDisponibles([manifestacion('cognitivo'), manifestacion('motor_fino')]);
    const actual = ficha({ observaciones: [observacion([manifestacion('motor_fino')])] });
    expect(dominiosCubiertos(actual, dominios)).toEqual(['motor_fino']);
    expect(dominiosFaltantes(actual, dominios)).toEqual(['cognitivo']);
    expect(dominiosDisponibles([])).toEqual([]);
  });
});

describe('explicación de señales', () => {
  it('mantiene rúbrica, edad y sala como causas separadas', () => {
    const causas = causasAtencion(ficha({
      alertaRubrica: 'Señal del marco vigente',
      alertaEdad: true,
      brecha: -2,
      rezagoRelativo: true,
      alerta: true,
    }));
    expect(causas.map((causa) => causa.tipo)).toEqual(['rubrica', 'edad', 'sala']);
    expect(causas[0]?.detalle).toBe('Señal del marco vigente');
  });

  it('no describe ausencia de evidencia como déficit', () => {
    const lectura = diagnostico(ficha({ observaciones: [], nivelVigente: null }));
    expect(lectura.estado).toBe('sin-datos');
    expect(lectura.detalle).toContain('no hay registros');
  });

  it('usa una lectura prudente cuando solo existe diferencia leve', () => {
    const lectura = diagnostico(ficha({ brecha: -1 }));
    expect(lectura.estado).toBe('observar');
    expect(lectura.detalle).toContain('diferencia leve');
  });
});

function nino(id: string): Nino {
  return { idNino: id, fechaNacimiento: '', idJardin: 'J1', salaGrupo: 'A', fechaIngreso: '' };
}

function obs(idNino: string, fecha: string, nivel: number): Observacion {
  return { idObservacion: `${idNino}-${fecha}`, idNino, fechaObservacion: fecha, formatoCaptura: 'texto', nivelEstimado: nivel };
}

it('resume trayectorias y respeta el subconjunto de niños', () => {
  const ninos = [nino('A'), nino('B'), nino('C'), nino('D')];
  const datos = {
    educadoras: [], niveles: [], jardines: [], ninos,
    manifestaciones: [], observacionManifestaciones: [], evaluaciones: [],
    observaciones: [
      obs('A', '2026-01-01', 2), obs('A', '2026-02-01', 3),
      obs('B', '2026-01-01', 3), obs('B', '2026-02-01', 3),
      obs('C', '2026-01-01', 4), obs('C', '2026-02-01', 3),
      obs('D', '2026-01-01', 2),
    ],
  } satisfies Datos;
  expect(resumenTrayectorias(datos)).toEqual({
    avanzan: 1, estables: 1, retroceden: 1, sinSeguimiento: 1, conSeguimiento: 3,
  });
  expect(resumenTrayectorias(datos, [ninos[1]!]).estables).toBe(1);
});


describe('estado auxiliar de experiencia', () => {
  it('no presenta cero cuando pendientes están cargando o fallaron', async () => {
    const { valorPendientes } = await import('./experiencia');
    expect(valorPendientes('cargando', 0)).toBe('Cargando…');
    expect(valorPendientes('error', 0)).toBe('No disponible');
    expect(valorPendientes('listo', 0)).toBe('0');
  });

  it('prioriza manifestaciones recientes y conserva el total deduplicado', async () => {
    const { manifestacionesRecientes } = await import('./experiencia');
    const antigua = observacion([manifestacion('motor_fino')]);
    antigua.idObservacion = 'antigua';
    antigua.fechaObservacion = '2025-01-01';
    antigua.manifestaciones[0]!.idManifestacion = 'ANTIGUA';
    const reciente = observacion([manifestacion('cognitivo')]);
    reciente.idObservacion = 'reciente';
    reciente.fechaObservacion = '2026-02-01';
    reciente.manifestaciones[0]!.idManifestacion = 'RECIENTE';
    const resultado = manifestacionesRecientes(ficha({ observaciones: [antigua, reciente] }), 1);
    expect(resultado.total).toBe(2);
    expect(resultado.visibles[0]?.idManifestacion).toBe('RECIENTE');
    expect(resultado.restantes[0]?.idManifestacion).toBe('ANTIGUA');
  });
});