import type { Datos } from '../data/cargar';
import { asignarProfesorasDemo, telefonosCoinciden } from '../domain/acceso';
import { generarPendientesDemo } from '../domain/revisionDemo';
import type { Pendiente, Profesora } from '../domain/tipos';

export type AccionRevision = 'aprobado' | 'editado' | 'rechazado';

export interface ServicioRevision {
  ingresar(telefono: string, datos: Datos): Promise<Profesora | null>;
  profesorasDemo(datos: Datos): Profesora[];
  pendientes(profesora: Profesora, datos: Datos): Promise<Pendiente[]>;
  /** Aprueba / edita (con nivel) / rechaza un caso. En modo API escribe la evaluación canónica. */
  resolver(pendiente: Pendiente, accion: AccionRevision, nivel?: number): Promise<void>;
}

export type ModoRevision = 'demo' | 'api';

type Json = Record<string, unknown>;

function esObjeto(valor: unknown): valor is Json {
  return typeof valor === 'object' && valor !== null && !Array.isArray(valor);
}

async function jsonValido(respuesta: Response, endpoint: string): Promise<unknown> {
  try {
    return await respuesta.json();
  } catch {
    throw new Error(`El backend devolvió JSON inválido en ${endpoint}`);
  }
}

function profesoraDesdeApi(valor: unknown): Profesora {
  if (!esObjeto(valor) ||
      typeof valor.id_educadora !== 'string' ||
      typeof valor.telefono !== 'string' ||
      !Array.isArray(valor.cursos)) {
    throw new Error('Respuesta inválida de /api/profesora');
  }
  const cursos = valor.cursos.map((curso) => {
    if (!esObjeto(curso) ||
        typeof curso.id_jardin !== 'string' ||
        typeof curso.sala_grupo !== 'string') {
      throw new Error('Respuesta inválida de /api/profesora');
    }
    return { idJardin: curso.id_jardin, salaGrupo: curso.sala_grupo };
  });
  return {
    idEducadora: valor.id_educadora,
    telefono: valor.telefono,
    cursos,
  };
}

function texto(valor: unknown): string {
  return valor === null || valor === undefined ? '' : String(valor);
}

function numeroNullable(valor: unknown): number | null {
  if (valor === null || valor === undefined || valor === '') {
    return null;
  }
  const numero = Number(valor);
  if (!Number.isFinite(numero)) {
    throw new Error('Respuesta inválida de /pendientes');
  }
  return numero;
}

function pendienteDesdeApi(valor: unknown, profesora: Profesora, datos: Datos): Pendiente {
  if (!esObjeto(valor) ||
      typeof valor.id_pendiente !== 'string' ||
      typeof valor.id_nino_propuesto !== 'string' ||
      typeof valor.creado_en !== 'string') {
    throw new Error('Respuesta inválida de /pendientes');
  }
  const nino = datos.ninos.find((item) => item.idNino === valor.id_nino_propuesto);
  return {
    idPendiente: valor.id_pendiente,
    idNinoPropuesto: valor.id_nino_propuesto,
    // "Nombre I." del niño/a: de los datos vivos o, si no está, del propio pendiente
    nombreVisible: nino?.nombreVisible || texto(valor.nombre_visible) || undefined,
    idEducadora: profesora.idEducadora,
    nivelPropuesto: numeroNullable(valor.nivel_propuesto),
    dominio: valor.dominio ? String(valor.dominio) : null,
    margen: numeroNullable(valor.margen),
    motivo: texto(valor.motivo),
    evidencia: texto(valor.evidencia),
    estado: texto(valor.estado),
    creadoEn: valor.creado_en,
    idJardin: nino?.idJardin ?? null,
    salaGrupo: nino?.salaGrupo ?? null,
  };
}

export const servicioRevisionDemo: ServicioRevision = {
  async ingresar(telefono, datos) {
    return asignarProfesorasDemo(datos.educadoras, datos.ninos).find((profesora) =>
      telefonosCoinciden(telefono, profesora.telefono)) ?? null;
  },

  profesorasDemo(datos) {
    return asignarProfesorasDemo(datos.educadoras, datos.ninos);
  },

  async pendientes(profesora, datos) {
    return generarPendientesDemo(datos, profesora);
  },

  async resolver(pendiente, accion, nivel) {
    // En demo no hay backend: se refleja localmente en el contexto.
    void pendiente; void accion; void nivel;
  },
};

export const servicioRevisionApi: ServicioRevision = {
  async ingresar(telefono) {
    const endpoint = `/api/profesora?telefono=${encodeURIComponent(telefono)}`;
    const respuesta = await fetch(endpoint);
    if (respuesta.status === 404) {
      return null;
    }
    if (!respuesta.ok) {
      throw new Error(`El backend respondió ${respuesta.status} en /api/profesora`);
    }
    return profesoraDesdeApi(await jsonValido(respuesta, '/api/profesora'));
  },

  profesorasDemo() {
    return [];
  },

  async pendientes(profesora, datos) {
    const endpoint = `/api/pendientes?from=${encodeURIComponent(profesora.telefono)}`;
    const respuesta = await fetch(endpoint);
    if (!respuesta.ok) {
      throw new Error(`El backend respondió ${respuesta.status} en /pendientes`);
    }
    const valor = await jsonValido(respuesta, '/pendientes');
    if (!esObjeto(valor) || !Array.isArray(valor.pendientes)) {
      throw new Error('Respuesta inválida de /pendientes');
    }
    return valor.pendientes.map((pendiente) => pendienteDesdeApi(pendiente, profesora, datos));
  },

  async resolver(pendiente, accion, nivel) {
    const respuesta = await fetch('/api/pendiente/resolver', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id_pendiente: pendiente.idPendiente,
        accion,
        nivel: accion === 'editado' ? nivel : undefined,
        resuelto_por: pendiente.idEducadora ?? undefined,
      }),
    });
    if (!respuesta.ok) {
      throw new Error(`El backend respondió ${respuesta.status} al resolver el caso`);
    }
    const valor = await jsonValido(respuesta, '/api/pendiente/resolver');
    if (esObjeto(valor) && valor.ok === false) {
      throw new Error(String(valor.error ?? 'no se pudo resolver el caso'));
    }
  },
};

export const modoRevision: ModoRevision =
  import.meta.env.VITE_REVISION === 'api' ? 'api' : 'demo';

export const servicioRevision: ServicioRevision =
  modoRevision === 'api' ? servicioRevisionApi : servicioRevisionDemo;
