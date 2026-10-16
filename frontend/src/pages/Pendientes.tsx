import { useEffect, useMemo, useState } from 'react';
import { useEstadoDatos, useVersionDatos } from '../data/DatosContext';
import { cargarPendientes, resolverPendiente, usaApi } from '../data/cargar';
import type { Pendiente } from '../domain/tipos';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { TarjetaRecomendacion } from '../components/TarjetaRecomendacion';
import { useRecomendaciones } from '../data/RecomendacionesContext';
import { Tabla, type Columna } from '../components/Tabla';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

function seguridad(margen: number | null): string {
  if (margen === null) return '—';
  if (margen >= 0.6) return 'alta';
  if (margen >= 0.4) return 'media';
  return 'baja';
}

type EstadoCarga =
  | { estado: 'cargando' }
  | { estado: 'error'; mensaje: string }
  | { estado: 'listo'; pendientes: Pendiente[] };

export function Pendientes() {
  // Aseguramos que el contexto de datos esté montado (misma app).
  const estadoDatos = useEstadoDatos();
  const nombreDe = (idNino: string) => estadoDatos.estado === 'listo'
    ? estadoDatos.datos.ninos.find((n) => n.idNino === idNino)?.nombreVisible : undefined;
  const version = useVersionDatos();
  const hayApi = usaApi();
  const [carga, setCarga] = useState<EstadoCarga>({ estado: 'cargando' });
  const [accionError, setAccionError] = useState<string | null>(null);
  const [resolviendo, setResolviendo] = useState<string | null>(null);
  const recomendaciones = useRecomendaciones();
  const [mensajeRecomendacion, setMensajeRecomendacion] = useState('');

  useEffect(() => {
    if (!hayApi) {
      setCarga({ estado: 'listo', pendientes: [] });
      return;
    }
    let activo = true;
    cargarPendientes()
      .then((pendientes) => {
        if (activo) setCarga({ estado: 'listo', pendientes });
      })
      .catch((error: unknown) => {
        if (activo) {
          setCarga({ estado: 'error', mensaje: error instanceof Error ? error.message : 'Error desconocido' });
        }
      });
    return () => {
      activo = false;
    };
  }, [hayApi, version]);

  const columnas: Columna<Pendiente>[] = useMemo(
    () => [
      {
        clave: 'nino',
        encabezado: 'Niño/a',
        ordenable: true,
        valor: (p) => p.nombreVisible || p.idNinoPropuesto,
        render: (p) => <span title={p.idNinoPropuesto}>{p.nombreVisible || p.idNinoPropuesto}</span>,
      },
      {
        clave: 'curso',
        encabezado: 'Curso',
        ordenable: true,
        valor: (p) => `${p.idJardin ?? ''} ${p.salaGrupo ?? ''}`,
        render: (p) => (
          <>
            {p.idJardin ?? '—'} · {p.salaGrupo ?? '—'}
          </>
        ),
      },
      { clave: 'tia', encabezado: 'Profesora', ordenable: true, valor: (p) => p.idEducadora ?? '—' },
      { clave: 'nivel', encabezado: 'Nivel sugerido', numerica: true, ordenable: true, valor: (p) => p.nivelPropuesto ?? -1 },
      { clave: 'margen', encabezado: 'Seguridad', ordenable: true, valor: (p) => p.margen ?? 0,
        render: (p) => <>{seguridad(p.margen)}</> },
      { clave: 'motivo', encabezado: 'Por qué', ordenable: true, valor: (p) => p.motivo },
      { clave: 'creado', encabezado: 'Cuándo', ordenable: true, valor: (p) => p.creadoEn },
      {
        clave: 'acciones',
        encabezado: 'Verificar',
        valor: () => '',
        render: (p) => (
          <div className="advertencia__acciones">
            <button type="button" disabled={resolviendo === p.idPendiente}
                    onClick={() => accion(p, 'aprobado')}>
              ✓ Está bien
            </button>
            <button type="button" disabled={resolviendo === p.idPendiente}
                    onClick={() => accion(p, 'editado', p.nivelPropuesto ?? undefined)}>
              ✏️ Cambiar nivel
            </button>
            <button type="button" disabled={resolviendo === p.idPendiente}
                    onClick={() => accion(p, 'rechazado')}>
              🚫 No es este niño/a
            </button>
          </div>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resolviendo],
  );

  async function accion(p: Pendiente, accionTipo: 'aprobado' | 'editado' | 'rechazado', nivel?: number) {
    setResolviendo(p.idPendiente);
    setAccionError(null);
    try {
      await resolverPendiente(p.idPendiente, accionTipo, nivel);
      const nuevos = await cargarPendientes();
      setCarga({ estado: 'listo', pendientes: nuevos });
    } catch (error: unknown) {
      setAccionError(error instanceof Error ? error.message : 'No se pudo resolver');
    } finally {
      setResolviendo(null);
    }
  }

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Por confirmar' }]} />
      <h2>Confirma lo que observaste</h2>
      <p className="ficha-descripcion">
        Estas son las observaciones que el sistema <strong>no pudo dar por seguras</strong>. Mira el
        nivel propuesto y <strong>confírmalo</strong> o <strong>corrígelo</strong>: lo que decidas
        queda como el nivel oficial del niño/a.
      </p>

      <section className="seccion-profesora" aria-labelledby="titulo-recomendaciones">
        <h3 id="titulo-recomendaciones">Recomendaciones RAG por verificar</h3>
        <p className="aviso-demo"><strong>Demo estática:</strong> estas decisiones se guardan solo en este navegador y no escriben en producción.</p>
        <p className="sr-only" aria-live="polite">{mensajeRecomendacion}</p>
        {recomendaciones.carga.estado === 'cargando' && <Cargando mensaje="Cargando recomendaciones…" />}
        {recomendaciones.carga.estado === 'error' && <ErrorEstado mensaje={recomendaciones.carga.mensaje} />}
        {recomendaciones.carga.estado === 'listo' && (recomendaciones.pendientes.length === 0
          ? <Vacio mensaje="No hay recomendaciones RAG pendientes en este navegador." />
          : <div className="lista-recomendaciones">{recomendaciones.pendientes.map((item) => (
              <TarjetaRecomendacion key={item.idRecomendacion} item={item} nombre={nombreDe(item.idNino)} onDecidir={(decision) => {
                recomendaciones.decidir(item.idRecomendacion, decision);
                setMensajeRecomendacion(`${item.idRecomendacion}: decisión guardada.`);
              }} />
            ))}</div>)}
      </section>

      {!hayApi && <p className="ficha-descripcion">La cola de clasificaciones del backend no está disponible en modo CSV.</p>}
      {hayApi && carga.estado === 'cargando' && <Cargando mensaje="Cargando cola…" />}
      {carga.estado === 'error' && <ErrorEstado mensaje={`No se pudo cargar la cola: ${carga.mensaje}`} />}
      {accionError && <ErrorEstado mensaje={accionError} />}
      {hayApi && carga.estado === 'listo' && (
        carga.pendientes.length === 0 ? (
          <Vacio mensaje="¡Todo al día! No tienes observaciones por confirmar." />
        ) : (
          <>
            <p className="estado">Tienes {carga.pendientes.length} observaciones para confirmar.</p>
            <Tabla
              columnas={columnas}
              filas={carga.pendientes}
              claveFila={(p) => p.idPendiente}
              descripcion="Cola de observaciones por verificar"
            />
          </>
        )
      )}
    </>
  );
}
