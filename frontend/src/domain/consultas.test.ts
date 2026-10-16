import { describe, it, expect } from 'vitest';
import type { Datos } from '../data/cargar';
import {
  alumnosDeCurso,
  alumnoDesde,
  resumenCursos,
  distribucionNiveles,
  fichaNino,
  claveCurso,
  resumenJardines,
} from './consultas';
import type { AlumnoCurso } from './consultas';

const HOY = new Date('2026-01-01');

const datos: Datos = {
  educadoras: [],
  niveles: [
    { nivel: 1, nombreNivel: 'N1', edadMinMeses: 0, edadMaxMeses: 12, descripcion: 'd1' },
    { nivel: 2, nombreNivel: 'N2', edadMinMeses: 12, edadMaxMeses: 24, descripcion: 'd2' },
    { nivel: 3, nombreNivel: 'N3', edadMinMeses: 24, edadMaxMeses: 36, descripcion: 'd3' },
    { nivel: 5, nombreNivel: 'N5', edadMinMeses: 36, edadMaxMeses: 48, descripcion: 'd5' },
  ],
  jardines: [
    { idJardin: 'JAR-1', nombreFantasia: 'Jardín Uno', comuna: 'Comuna', region: 'Región' },
  ],
  ninos: [
    { idNino: 'NINO-1', fechaNacimiento: '2024-01-01', idJardin: 'JAR-1', salaGrupo: 'SG-A', fechaIngreso: '2024-06-01' },
    { idNino: 'NINO-2', fechaNacimiento: '2023-01-01', idJardin: 'JAR-1', salaGrupo: 'SG-A', fechaIngreso: '2024-06-01' },
  ],
  observaciones: [
    { idObservacion: 'OBS-1', idNino: 'NINO-1', fechaObservacion: '2025-06-01', formatoCaptura: 'texto', nivelEstimado: 2 },
    { idObservacion: 'OBS-2', idNino: 'NINO-1', fechaObservacion: '2025-12-01', formatoCaptura: 'video', nivelEstimado: 2 },
    { idObservacion: 'OBS-3', idNino: 'NINO-2', fechaObservacion: '2025-11-01', formatoCaptura: 'audio', nivelEstimado: 1 },
  ],
  manifestaciones: [
    { idManifestacion: 'MAN-1', nivel: 2, dominio: 'cognitivo', textoObservable: 'Conducta A' },
    { idManifestacion: 'MAN-2', nivel: 2, dominio: 'lenguaje', textoObservable: 'Conducta B' },
  ],
  observacionManifestaciones: [
    { idObservacion: 'OBS-2', idManifestacion: 'MAN-1' },
    { idObservacion: 'OBS-2', idManifestacion: 'MAN-2' },
  ],
};

describe('claveCurso', () => {
  it('combina jardín y sala', () => {
    expect(claveCurso('JAR-1', 'SG-A')).toBe('JAR-1__SG-A');
  });
});

describe('alumnosDeCurso', () => {
  it('calcula nivel vigente, esperado, brecha y alerta', () => {
    const alumnos = alumnosDeCurso(datos, 'JAR-1', 'SG-A', HOY);
    expect(alumnos).toHaveLength(2);

    const n1 = alumnos.find((a) => a.idNino === 'NINO-1');
    expect(n1?.edadMeses).toBe(24);
    expect(n1?.nivelVigente).toBe(2);
    expect(n1?.nivelEsperado).toBe(3);
    expect(n1?.brecha).toBe(-1);
    expect(n1?.alerta).toBe(false);

    const n2 = alumnos.find((a) => a.idNino === 'NINO-2');
    expect(n2?.nivelVigente).toBe(1);
    expect(n2?.nivelEsperado).toBe(5);
    expect(n2?.brecha).toBe(-4);
    expect(n2?.alerta).toBe(true);
  });
});

describe('resumenCursos', () => {
  it('agrega por curso con promedio y alertas', () => {
    const resumen = resumenCursos(datos, HOY);
    expect(resumen).toHaveLength(1);
    expect(resumen[0]?.totalNinos).toBe(2);
    expect(resumen[0]?.nivelPromedio).toBe(1.5);
    expect(resumen[0]?.totalAlertas).toBe(1);
    expect(resumen[0]?.nombreJardin).toBe('Jardín Uno');
  });
});

describe('distribucionNiveles', () => {
  it('cuenta por nivel del 1 al 9', () => {
    const alumnos: AlumnoCurso[] = alumnosDeCurso(datos, 'JAR-1', 'SG-A', HOY);
    const dist = distribucionNiveles(alumnos);
    expect(dist).toHaveLength(9);
    expect(dist.find((d) => d.nivel === 1)?.total).toBe(1);
    expect(dist.find((d) => d.nivel === 2)?.total).toBe(1);
    expect(dist.find((d) => d.nivel === 9)?.total).toBe(0);
  });
});

describe('fichaNino', () => {
  it('arma la ficha con observaciones ordenadas y manifestaciones', () => {
    const ficha = fichaNino(datos, 'NINO-1', HOY);
    expect(ficha).not.toBeNull();
    expect(ficha?.observaciones).toHaveLength(2);
    expect(ficha?.observaciones[0]?.idObservacion).toBe('OBS-1');
    expect(ficha?.observaciones[1]?.manifestaciones).toHaveLength(2);
    expect(ficha?.nivelVigente).toBe(2);
  });

  it('devuelve null si el niño no existe', () => {
    expect(fichaNino(datos, 'NINO-999', HOY)).toBeNull();
  });
});

describe('evaluación consolidada del backend', () => {
  it('usa el nivel y la alerta del backend cuando existen', () => {
    const conEval: Datos = {
      ...datos,
      evaluaciones: [
        { idNino: 'NINO-1', dominio: 'global', nivel: 3, margen: 0.5, periodo: '2026-01-01', tendencia: 'estable', alerta: null },
        { idNino: 'NINO-2', dominio: 'global', nivel: 4, margen: 0.5, periodo: '2026-01-01', tendencia: 'retroceso', alerta: 'Nivel 4 en el tramo bajo (posible rezago).' },
      ],
    };
    const alumnos = alumnosDeCurso(conEval, 'JAR-1', 'SG-A', HOY);

    const n1 = alumnos.find((a) => a.idNino === 'NINO-1');
    expect(n1?.nivelVigente).toBe(3);
    expect(n1?.alerta).toBe(false);

    const n2 = alumnos.find((a) => a.idNino === 'NINO-2');
    expect(n2?.nivelVigente).toBe(4);
    expect(n2?.alerta).toBe(true);
  });
});

describe('rezago relativo + panorama de jardín', () => {
  const datosRr: Datos = {
    ...datos,
    ninos: [
      { idNino: 'N1', fechaNacimiento: '2024-01-01', idJardin: 'JAR-1', salaGrupo: 'SG-A', fechaIngreso: '' },
      { idNino: 'N2', fechaNacimiento: '2024-01-01', idJardin: 'JAR-1', salaGrupo: 'SG-A', fechaIngreso: '' },
      { idNino: 'N3', fechaNacimiento: '2024-01-01', idJardin: 'JAR-1', salaGrupo: 'SG-A', fechaIngreso: '' },
      { idNino: 'N4', fechaNacimiento: '2024-01-01', idJardin: 'JAR-2', salaGrupo: 'SG-B', fechaIngreso: '' },
    ],
    jardines: [
      ...datos.jardines,
      { idJardin: 'JAR-2', nombreFantasia: 'Jardín Dos', comuna: 'C2', region: 'R2' },
    ],
    observaciones: [
      { idObservacion: 'o1', idNino: 'N1', fechaObservacion: '2025-06-01', formatoCaptura: 'texto', nivelEstimado: 6 },
      { idObservacion: 'o2', idNino: 'N2', fechaObservacion: '2025-06-01', formatoCaptura: 'texto', nivelEstimado: 6 },
      { idObservacion: 'o3', idNino: 'N3', fechaObservacion: '2025-06-01', formatoCaptura: 'texto', nivelEstimado: 1 },
      { idObservacion: 'o4', idNino: 'N4', fechaObservacion: '2025-06-01', formatoCaptura: 'texto', nivelEstimado: 4 },
    ],
    evaluaciones: [],
  };

  it('marca rezagado al que está por debajo del promedio de su sala', () => {
    const alumnos = alumnosDeCurso(datosRr, 'JAR-1', 'SG-A', HOY);
    const by = (id: string) => alumnos.find((a) => a.idNino === id);
    // media sala = (6+6+1)/3 = 4.33 -> N3 (1) está >1 por debajo
    expect(by('N3')?.rezagoRelativo).toBe(true);
    expect(by('N3')?.alerta).toBe(true);
    expect(by('N1')?.rezagoRelativo).toBe(false);
  });

  it('resume jardines con conteos', () => {
    const js = resumenJardines(datosRr, HOY);
    const j1 = js.find((j) => j.idJardin === 'JAR-1');
    expect(j1?.totalSalas).toBe(1);
    expect(j1?.totalNinos).toBe(3);
    expect(j1?.nombreJardin).toBe('Jardín Uno');
  });
});


describe('causas de atención separadas', () => {
  const ninoBase = datos.ninos[0]!;
  const observaciones = datos.observaciones.filter((o) => o.idNino === ninoBase.idNino);

  it('calcula alerta etaria aun cuando existe evaluación consolidada', () => {
    const alumno = alumnoDesde(ninoBase, observaciones, datos.niveles, HOY, {
      idNino: ninoBase.idNino,
      dominio: 'global',
      nivel: 1,
      margen: 0.7,
      periodo: '2026-01-01',
      tendencia: 'estable',
      alerta: null,
      origen: 'auto',
    });

    expect(alumno.brecha).toBe(-2);
    expect(alumno.alertaEdad).toBe(true);
    expect(alumno.alertaRubrica).toBeNull();
    expect(alumno.alerta).toBe(true);
  });

  it('conserva una señal de rúbrica independiente de la brecha etaria', () => {
    const alumno = alumnoDesde(ninoBase, observaciones, datos.niveles, HOY, {
      idNino: ninoBase.idNino,
      dominio: 'global',
      nivel: 3,
      margen: 0.7,
      periodo: '2026-01-01',
      tendencia: 'estable',
      alerta: 'Señal del marco vigente',
      origen: 'manual:EDU-1',
    });

    expect(alumno.alertaEdad).toBe(false);
    expect(alumno.alertaRubrica).toBe('Señal del marco vigente');
    expect(alumno.alerta).toBe(true);
    expect(alumno.ajustadoManual).toBe(true);
  });

  it('marca solo rezago relativo cuando la brecha etaria no alcanza el umbral', () => {
    const datosRelativos: Datos = {
      ...datos,
      ninos: ['A', 'B', 'C'].map((id) => ({
        idNino: id,
        fechaNacimiento: '2023-01-01',
        idJardin: 'JAR-1',
        salaGrupo: 'SG-A',
        fechaIngreso: '',
      })),
      observaciones: [
        { idObservacion: 'OA', idNino: 'A', fechaObservacion: '2025-12-01', formatoCaptura: 'texto', nivelEstimado: 6 },
        { idObservacion: 'OB', idNino: 'B', fechaObservacion: '2025-12-01', formatoCaptura: 'texto', nivelEstimado: 6 },
        { idObservacion: 'OC', idNino: 'C', fechaObservacion: '2025-12-01', formatoCaptura: 'texto', nivelEstimado: 4 },
      ],
      evaluaciones: [],
    };

    const alumno = alumnosDeCurso(datosRelativos, 'JAR-1', 'SG-A', HOY)
      .find((actual) => actual.idNino === 'C');
    expect(alumno?.brecha).toBe(-1);
    expect(alumno?.alertaEdad).toBe(false);
    expect(alumno?.alertaRubrica).toBeNull();
    expect(alumno?.rezagoRelativo).toBe(true);
    expect(alumno?.alerta).toBe(true);
  });

  it('propaga las causas separadas a la ficha', () => {
    const conEval: Datos = {
      ...datos,
      evaluaciones: [{
        idNino: 'NINO-1',
        dominio: 'global',
        nivel: 1,
        margen: 0.4,
        periodo: '2026-01-01',
        tendencia: 'estable',
        alerta: 'Señal de rúbrica',
      }],
    };
    const ficha = fichaNino(conEval, 'NINO-1', HOY);
    expect(ficha?.alertaRubrica).toBe('Señal de rúbrica');
    expect(ficha?.alertaEdad).toBe(true);
    expect(ficha?.alerta).toBe(true);
  });
});