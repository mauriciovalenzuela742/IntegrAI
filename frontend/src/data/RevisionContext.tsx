import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { notificacionesDesdePendientes } from '../domain/notificaciones';
import type { NotificacionAdvertencia, Pendiente, Profesora } from '../domain/tipos';
import {
  modoRevision,
  servicioRevision,
  type AccionRevision,
  type ModoRevision,
} from '../services/ServicioRevision';
import { useEstadoDatos, useVersionDatos } from './DatosContext';

const CLAVE_SESION = 'integrai-profesora';

export type EstadoPendientesRevision =
  | { estado: 'inactivo' }
  | { estado: 'cargando' }
  | { estado: 'listo' }
  | { estado: 'error'; mensaje: string };

interface RevisionContexto {
  profesora: Profesora | null;
  modo: ModoRevision;
  profesorasDemo: Profesora[];
  pendientes: Pendiente[];
  notificaciones: NotificacionAdvertencia[];
  estadoPendientes: EstadoPendientesRevision;
  ingresar: (telefono: string) => Promise<Profesora | null>;
  salir: () => void;
  /** Aprueba / edita (con nivel) / rechaza un caso y lo quita de la cola. */
  resolver: (idPendiente: string, accion: AccionRevision, nivel?: number) => Promise<void>;
}

const RevisionContext = createContext<RevisionContexto | null>(null);

function esProfesora(valor: unknown): valor is Profesora {
  if (typeof valor !== 'object' || valor === null) {
    return false;
  }
  const posible = valor as Partial<Profesora>;
  return typeof posible.idEducadora === 'string' &&
    typeof posible.telefono === 'string' &&
    Array.isArray(posible.cursos) &&
    posible.cursos.every(
      (curso) =>
        typeof curso === 'object' &&
        curso !== null &&
        typeof curso.idJardin === 'string' &&
        typeof curso.salaGrupo === 'string',
    );
}

function restaurarSesion(): Profesora | null {
  try {
    const guardada = window.sessionStorage.getItem(CLAVE_SESION);
    if (!guardada) {
      return null;
    }
    const valor: unknown = JSON.parse(guardada);
    return esProfesora(valor) ? valor : null;
  } catch {
    return null;
  }
}

export function RevisionProvider({ children }: { children: ReactNode }) {
  const estadoDatos = useEstadoDatos();
  const versionDatos = useVersionDatos();
  const [profesora, setProfesora] = useState<Profesora | null>(restaurarSesion);
  const [pendientes, setPendientes] = useState<Pendiente[]>([]);
  const [estadoPendientes, setEstadoPendientes] = useState<EstadoPendientesRevision>(
    profesora ? { estado: 'cargando' } : { estado: 'inactivo' },
  );

  useEffect(() => {
    try {
      if (profesora) {
        window.sessionStorage.setItem(CLAVE_SESION, JSON.stringify(profesora));
      } else {
        window.sessionStorage.removeItem(CLAVE_SESION);
      }
    } catch {
      // La sesión sigue disponible en memoria si sessionStorage está bloqueado.
    }
  }, [profesora]);

  useEffect(() => {
    if (!profesora) {
      setPendientes([]);
      setEstadoPendientes({ estado: 'inactivo' });
      return;
    }
    if (estadoDatos.estado !== 'listo') {
      setEstadoPendientes({ estado: 'cargando' });
      return;
    }

    let activo = true;
    // Solo la primera carga muestra "Cargando…": los refrescos (SSE/polling) actualizan en silencio,
    // para que la lista no desaparezca ni la página salte cada vez que llega un aviso del backend.
    setEstadoPendientes((previo) => (previo.estado === 'listo' ? previo : { estado: 'cargando' }));
    servicioRevision.pendientes(profesora, estadoDatos.datos)
      .then((nuevosPendientes) => {
        if (activo) {
          setPendientes(nuevosPendientes);
          setEstadoPendientes({ estado: 'listo' });
        }
      })
      .catch((error: unknown) => {
        if (activo) {
          setEstadoPendientes((previo) => previo.estado === 'listo' ? previo : {
            estado: 'error',
            mensaje: error instanceof Error ? error.message : 'Error desconocido',
          });
        }
      });
    return () => {
      activo = false;
    };
  }, [estadoDatos, profesora, versionDatos]);

  const profesorasDemo = useMemo(
    () => estadoDatos.estado === 'listo'
      ? servicioRevision.profesorasDemo(estadoDatos.datos)
      : [],
    [estadoDatos],
  );

  const notificaciones = useMemo(
    () => notificacionesDesdePendientes(pendientes),
    [pendientes],
  );

  const ingresar = useCallback(async (telefono: string) => {
    if (estadoDatos.estado !== 'listo') {
      throw new Error('Los datos todavía se están cargando');
    }
    const encontrada = await servicioRevision.ingresar(telefono, estadoDatos.datos);
    if (encontrada) {
      setPendientes([]);
      setProfesora(encontrada);
    }
    return encontrada;
  }, [estadoDatos]);

  const salir = useCallback(() => {
    setProfesora(null);
    setPendientes([]);
  }, []);

  const resolver = useCallback(async (idPendiente: string, accion: AccionRevision, nivel?: number) => {
    const caso = pendientes.find((p) => p.idPendiente === idPendiente);
    if (!caso) {
      return;
    }
    await servicioRevision.resolver(caso, accion, nivel);
    setPendientes((prev) => prev.filter((p) => p.idPendiente !== idPendiente));
  }, [pendientes]);

  const valor = useMemo<RevisionContexto>(() => ({
    profesora,
    modo: modoRevision,
    profesorasDemo,
    pendientes,
    notificaciones,
    estadoPendientes,
    ingresar,
    salir,
    resolver,
  }), [
    estadoPendientes,
    ingresar,
    notificaciones,
    pendientes,
    profesora,
    profesorasDemo,
    resolver,
    salir,
  ]);

  return <RevisionContext.Provider value={valor}>{children}</RevisionContext.Provider>;
}

export function useRevision(): RevisionContexto {
  const contexto = useContext(RevisionContext);
  if (!contexto) {
    throw new Error('useRevision debe usarse dentro de RevisionProvider');
  }
  return contexto;
}
