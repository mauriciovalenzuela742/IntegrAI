import { describe, expect, it } from 'vitest';
import {
  asignarProfesorasDemo,
  datosDeProfesora,
  filtrarCursosDeProfesora,
  normalizarTelefono,
  telefonoDemo,
  telefonosCoinciden,
  tieneAccesoCurso,
  tieneAccesoNino,
} from './acceso';
import type { Educadora, Nino, Profesora } from './tipos';

const nino = (idNino: string, idJardin: string, salaGrupo: string): Nino => ({
  idNino,
  idJardin,
  salaGrupo,
  fechaNacimiento: '2023-01-01',
  fechaIngreso: '2024-01-01',
});

describe('teléfonos de profesoras', () => {
  it('normaliza dejando solo dígitos', () => {
    expect(normalizarTelefono(' +56 (9) 1234-5678 ')).toBe('56912345678');
    expect(normalizarTelefono('sin número')).toBe('');
  });

  it('compara igualdad o los últimos nueve dígitos de números suficientemente largos', () => {
    expect(telefonosCoinciden('+56 9 1234 5678', '9-1234-5678')).toBe(true);
    expect(telefonosCoinciden('123', '(123)')).toBe(true);
    expect(telefonosCoinciden('00123456789', '99123456789')).toBe(true);
  });

  it('no hace coincidir vacíos ni números cortos solo por sufijo', () => {
    expect(telefonosCoinciden('', '---')).toBe(false);
    expect(telefonosCoinciden('00123', '123')).toBe(false);
    expect(telefonosCoinciden('56912345678', '812345678')).toBe(false);
  });

  it('genera el teléfono ficticio solicitado', () => {
    expect(telefonoDemo('EDU-0007')).toBe('56900000007');
  });
});

describe('asignación demo', () => {
  it('ordena educadoras y salas y las reparte cíclicamente', () => {
    const educadoras: Educadora[] = [
      { idEducadora: 'EDU-0003', idJardin: 'JAR-1', rol: 'educadora', aniosExperiencia: 3 },
      { idEducadora: 'EDU-0001', idJardin: 'JAR-1', rol: 'educadora', aniosExperiencia: 1 },
      { idEducadora: 'EDU-0002', idJardin: 'JAR-1', rol: 'tecnico', aniosExperiencia: 2 },
      { idEducadora: 'EDU-0004', idJardin: 'JAR-2', rol: 'educadora', aniosExperiencia: 4 },
    ];
    const ninos = [
      nino('N-2', 'JAR-1', 'Sala B'),
      nino('N-1', 'JAR-1', 'Sala A'),
      nino('N-3', 'JAR-1', 'Sala A'),
      nino('N-4', 'JAR-2', 'Sala C'),
    ];

    const profesoras = asignarProfesorasDemo(educadoras, ninos);
    expect(profesoras.map((p) => p.idEducadora)).toEqual([
      'EDU-0001',
      'EDU-0002',
      'EDU-0003',
      'EDU-0004',
    ]);
    expect(profesoras.map((p) => p.cursos[0]?.salaGrupo)).toEqual([
      'Sala A',
      'Sala B',
      'Sala A',
      'Sala C',
    ]);
    expect(profesoras.every((p) => p.cursos.length === 1)).toBe(true);
  });
});

describe('acceso por curso', () => {
  const profesora: Profesora = {
    idEducadora: 'EDU-0001',
    telefono: '56900000001',
    cursos: [{ idJardin: 'JAR-1', salaGrupo: 'Sala A' }],
  };

  it('filtra cursos por la clave compuesta de jardín y sala', () => {
    const cursos = [
      { idJardin: 'JAR-1', salaGrupo: 'Sala A', total: 2 },
      { idJardin: 'JAR-1', salaGrupo: 'Sala B', total: 3 },
      { idJardin: 'JAR-2', salaGrupo: 'Sala A', total: 4 },
    ];
    expect(filtrarCursosDeProfesora(cursos, profesora)).toEqual([cursos[0]]);
  });

  it('autoriza cursos y niños propios y rechaza los ajenos', () => {
    expect(tieneAccesoCurso(profesora, 'JAR-1', 'Sala A')).toBe(true);
    expect(tieneAccesoCurso(profesora, 'JAR-1', 'Sala B')).toBe(false);
    expect(tieneAccesoNino(profesora, nino('N-1', 'JAR-1', 'Sala A'))).toBe(true);
    expect(tieneAccesoNino(profesora, nino('N-2', 'JAR-2', 'Sala A'))).toBe(false);
  });
});


it('proyecta todos los datos relacionados antes de calcular métricas de profesora', () => {
  const profesora: Profesora = {
    idEducadora: 'EDU-1',
    telefono: '56900000001',
    cursos: [{ idJardin: 'J1', salaGrupo: 'A' }],
  };
  const datos = {
    educadoras: [
      { idEducadora: 'EDU-1', idJardin: 'J1', rol: 'educadora', aniosExperiencia: 1 },
      { idEducadora: 'EDU-2', idJardin: 'J2', rol: 'educadora', aniosExperiencia: 1 },
    ],
    niveles: [],
    jardines: [
      { idJardin: 'J1', nombreFantasia: 'Uno', comuna: '', region: '' },
      { idJardin: 'J2', nombreFantasia: 'Dos', comuna: '', region: '' },
    ],
    ninos: [nino('N1', 'J1', 'A'), nino('N2', 'J1', 'B'), nino('N3', 'J2', 'A')],
    observaciones: [
      { idObservacion: 'O1', idNino: 'N1', fechaObservacion: '', formatoCaptura: 'texto', nivelEstimado: 2 },
      { idObservacion: 'O2', idNino: 'N2', fechaObservacion: '', formatoCaptura: 'texto', nivelEstimado: 3 },
    ],
    manifestaciones: [],
    observacionManifestaciones: [
      { idObservacion: 'O1', idManifestacion: 'M1' },
      { idObservacion: 'O2', idManifestacion: 'M2' },
    ],
    evaluaciones: [
      { idNino: 'N1', dominio: 'global', nivel: 2, margen: 1, periodo: '', tendencia: '', alerta: null },
      { idNino: 'N2', dominio: 'global', nivel: 3, margen: 1, periodo: '', tendencia: '', alerta: null },
    ],
  };

  const resultado = datosDeProfesora(datos, profesora);
  expect(resultado.ninos.map((actual) => actual.idNino)).toEqual(['N1']);
  expect(resultado.observaciones.map((actual) => actual.idObservacion)).toEqual(['O1']);
  expect(resultado.observacionManifestaciones).toEqual([{ idObservacion: 'O1', idManifestacion: 'M1' }]);
  expect(resultado.evaluaciones?.map((actual) => actual.idNino)).toEqual(['N1']);
  expect(resultado.jardines.map((actual) => actual.idJardin)).toEqual(['J1']);
});