import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { ListaAdvertencias } from '../components/ListaAdvertencias';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';
import { Tabla, type Columna } from '../components/Tabla';
import { Tarjeta } from '../components/Tarjeta';
import { useEstadoDatos } from '../data/DatosContext';
import { useRevision } from '../data/RevisionContext';
import { useRecomendaciones } from '../data/RecomendacionesContext';
import { TarjetaRecomendacion } from '../components/TarjetaRecomendacion';
import { filtrarCursosDeProfesora, tieneAccesoCurso } from '../domain/acceso';
import { resumenCursos, type ResumenCurso } from '../domain/consultas';
import { formatearPromedio } from '../domain/formato';

const HOY = new Date();

export function ProfesoraInicio() {
  const estadoDatos = useEstadoDatos();
  const nombreDe = (idNino: string) => estadoDatos.estado === 'listo'
    ? estadoDatos.datos.ninos.find((n) => n.idNino === idNino)?.nombreVisible : undefined;
  const { profesora, modo, notificaciones, estadoPendientes, resolver } = useRevision();
  const [resolviendo, setResolviendo] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const recomendaciones = useRecomendaciones();
  const [mensajeRecomendacion, setMensajeRecomendacion] = useState('');
  // Solo las recomendaciones de niños/as de los cursos de esta profesora
  const misRecomendaciones = profesora
    ? recomendaciones.pendientes.filter((item) => tieneAccesoCurso(profesora, item.idJardin, item.salaGrupo))
    : [];

  async function manejarResolver(idPendiente: string, accion: 'aprobado' | 'editado' | 'rechazado', nivel?: number) {
    setResolviendo(idPendiente);
    setErrorAccion(null);
    try {
      await resolver(idPendiente, accion, nivel);
    } catch (error: unknown) {
      setErrorAccion(error instanceof Error ? error.message : 'No se pudo guardar la verificación');
    } finally {
      setResolviendo(null);
    }
  }

  const cursos = useMemo(() => {
    if (estadoDatos.estado !== 'listo' || !profesora) {
      return [];
    }
    return filtrarCursosDeProfesora(resumenCursos(estadoDatos.datos, HOY), profesora);
  }, [estadoDatos, profesora]);

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Inicio' }]} />
      <h2>Inicio</h2>

      {modo === 'demo' && (
        <p className="aviso-demo" role="status">
          <strong>Modo demostración</strong>: datos de prueba.
        </p>
      )}

      <section aria-label="Resumen de profesora" className="tarjetas">
        <Tarjeta etiqueta="Mis cursos" valor={String(cursos.length)} />
        <Tarjeta
          etiqueta="Por confirmar"
          valor={String(notificaciones.length)}
          alerta={notificaciones.length > 0}
        />
        <Tarjeta
          etiqueta="Recomendaciones"
          valor={String(misRecomendaciones.length)}
          alerta={misRecomendaciones.length > 0}
        />
      </section>

      <p className="profesora-ayuda">
        <Link className="boton boton--secundario" to="/profesora/experiencia">
          Ver acompañamiento pedagógico
        </Link>
      </p>

      <section id="advertencias" className="seccion-profesora" aria-labelledby="titulo-advertencias">
        <h3 id="titulo-advertencias">Por confirmar</h3>
        {estadoPendientes.estado === 'cargando' && <Cargando mensaje="Cargando advertencias…" />}
        {estadoPendientes.estado === 'error' && (
          <ErrorEstado mensaje={`No se pudieron cargar las advertencias: ${estadoPendientes.mensaje}`} />
        )}
        {estadoPendientes.estado === 'listo' && (
          notificaciones.length === 0 ? (
            <Vacio mensaje="¡Todo al día! No tienes casos por confirmar." />
          ) : (
            <>
              <p className="profesora-ayuda">
                Estas observaciones quedaron <strong>por confirmar</strong>. Mira lo que se observó y
                elige: <strong>Está bien</strong>, <strong>Cambiar nivel</strong> o
                <strong>No es este niño/a</strong>.
              </p>
              {errorAccion && <ErrorEstado mensaje={errorAccion} />}
              <ListaAdvertencias
                notificaciones={notificaciones}
                onResolver={manejarResolver}
                resolviendoId={resolviendo}
              />
            </>
          )
        )}
      </section>

      <section className="seccion-profesora" aria-labelledby="titulo-recomendaciones">
        <h3 id="titulo-recomendaciones">Recomendaciones por verificar</h3>
        <p className="aviso-demo"><strong>Demo:</strong> estas decisiones se guardan solo en este navegador y no escriben en producción.</p>
        <p className="sr-only" aria-live="polite">{mensajeRecomendacion}</p>
        {recomendaciones.carga.estado === 'cargando' && <Cargando mensaje="Cargando recomendaciones…" />}
        {recomendaciones.carga.estado === 'error' && <ErrorEstado mensaje={recomendaciones.carga.mensaje} />}
        {recomendaciones.carga.estado === 'listo' && (misRecomendaciones.length === 0
          ? <Vacio mensaje="No tienes recomendaciones por verificar." />
          : (
            <>
              <p className="profesora-ayuda">
                Propuestas de actividades según lo observado en tus niños/as. Revísalas y elige:
                <strong> Aprobar</strong>, <strong>Editar</strong> o <strong>Descartar</strong>.
              </p>
              <div className="lista-recomendaciones">{misRecomendaciones.map((item) => (
                <TarjetaRecomendacion key={item.idRecomendacion} item={item} nombre={nombreDe(item.idNino)} onDecidir={(decision) => {
                  recomendaciones.decidir(item.idRecomendacion, decision);
                  setMensajeRecomendacion(`${item.idRecomendacion}: decisión guardada.`);
                }} />
              ))}</div>
            </>
          ))}
      </section>

      <section className="seccion-profesora" aria-labelledby="titulo-mis-cursos">
        <h3 id="titulo-mis-cursos">Mis cursos</h3>
        {estadoDatos.estado === 'cargando' && <Cargando />}
        {estadoDatos.estado === 'error' && (
          <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estadoDatos.mensaje}`} />
        )}
        {estadoDatos.estado === 'listo' && (
          cursos.length === 0 ? (
            <Vacio mensaje="No tienes cursos registrados." />
          ) : (
            <div className="panel lista-cursos">
              <Tabla
                descripcion="Cursos asociados a la profesora"
                filas={cursos}
                claveFila={(curso) => `${curso.idJardin}-${curso.salaGrupo}`}
                columnas={columnas}
              />
            </div>
          )
        )}
      </section>
    </>
  );
}

const columnas: Columna<ResumenCurso>[] = [
  {
    clave: 'jardin',
    encabezado: 'Jardín',
    valor: (curso) => curso.nombreJardin,
    render: (curso) => (
      <Link to={`/curso/${encodeURIComponent(curso.idJardin)}/${encodeURIComponent(curso.salaGrupo)}`}>
        {curso.nombreJardin}
      </Link>
    ),
  },
  { clave: 'sala', encabezado: 'Sala', valor: (curso) => curso.salaGrupo },
  {
    clave: 'ninos',
    encabezado: 'Niños/as',
    numerica: true,
    valor: (curso) => curso.totalNinos,
  },
  {
    clave: 'promedio',
    encabezado: 'Nivel promedio',
    numerica: true,
    valor: (curso) => curso.nivelPromedio,
    render: (curso) => formatearPromedio(curso.nivelPromedio),
  },
];
