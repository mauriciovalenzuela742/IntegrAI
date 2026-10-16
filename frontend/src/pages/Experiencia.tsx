import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { FichaAcompanamiento } from '../components/experiencia/FichaAcompanamiento';
import { GraficoBarras, type DatoBarra } from '../components/experiencia/GraficoBarras';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';
import { Tarjeta } from '../components/Tarjeta';
import { useEstadoDatos } from '../data/DatosContext';
import { useRevision } from '../data/RevisionContext';
import { datosDeProfesora } from '../domain/acceso';
import { alumnosDeCurso, claveCurso, fichaNino, resumenCursos } from '../domain/consultas';
import { dominiosDisponibles, resumenTrayectorias, valorPendientes } from '../domain/experiencia';
import { formatearPromedio } from '../domain/formato';
import './Experiencia.css';

export type ModoExperiencia = 'coordinacion' | 'profesora';

export function Experiencia({ modo }: { modo: ModoExperiencia }) {
  const estadoDatos = useEstadoDatos();
  const { profesora, modo: modoRevision, notificaciones, estadoPendientes } = useRevision();
  const [claveSeleccionada, setClaveSeleccionada] = useState('');
  const [idNinoSeleccionado, setIdNinoSeleccionado] = useState('');
  const esProfesora = modo === 'profesora';

  const datos = useMemo(() => {
    if (estadoDatos.estado !== 'listo') return null;
    if (!esProfesora) return estadoDatos.datos;
    return profesora ? datosDeProfesora(estadoDatos.datos, profesora) : null;
  }, [esProfesora, estadoDatos, profesora]);

  const hoy = useMemo(() => new Date(), [datos]);
  const cursos = useMemo(() => datos ? resumenCursos(datos, hoy) : [], [datos, hoy]);
  const curso = useMemo(
    () => cursos.find((actual) => claveCurso(actual.idJardin, actual.salaGrupo) === claveSeleccionada) ?? cursos[0],
    [claveSeleccionada, cursos],
  );
  const alumnos = useMemo(
    () => datos && curso ? alumnosDeCurso(datos, curso.idJardin, curso.salaGrupo, hoy) : [],
    [curso, datos, hoy],
  );
  const alumno = useMemo(
    () => alumnos.find((actual) => actual.idNino === idNinoSeleccionado) ?? alumnos[0],
    [alumnos, idNinoSeleccionado],
  );
  const ficha = useMemo(
    () => datos && alumno ? fichaNino(datos, alumno.idNino, hoy) : null,
    [alumno, datos, hoy],
  );
  const dominios = useMemo(() => datos ? dominiosDisponibles(datos.manifestaciones) : [], [datos]);
  const trayectorias = useMemo(() => datos ? resumenTrayectorias(datos) : null, [datos]);
  const totalAlertas = useMemo(
    () => cursos.reduce((total, actual) => total + actual.totalAlertas, 0),
    [cursos],
  );
  const distribucion = useMemo<DatoBarra[]>(() => {
    if (!datos) return [];
    const niveles = [...new Set([
      ...datos.niveles.map((nivel) => nivel.nivel),
      ...alumnos.map((actual) => actual.nivelVigente).filter((nivel): nivel is number => nivel !== null),
    ])].sort((a, b) => a - b);
    return niveles.map((nivel) => ({
      id: String(nivel),
      nombre: `Nivel ${nivel}`,
      valor: alumnos.filter((actual) => actual.nivelVigente === nivel).length,
    }));
  }, [alumnos, datos]);

  const migas = esProfesora
    ? [{ etiqueta: 'Inicio', ruta: '/profesora/inicio' }, { etiqueta: 'Acompañamiento' }]
    : [{ etiqueta: 'Cursos', ruta: '/' }, { etiqueta: 'Acompañamiento' }];

  return (
    <div className="experiencia">
      <Breadcrumbs migas={migas} />
      <header className="experiencia__encabezado">
        <div>
          <p className="experiencia__sobrelinea">{esProfesora ? 'Experiencia de profesora' : 'Experiencia de coordinación'}</p>
          <h2>Acompañamiento pedagógico</h2>
          <p className="experiencia__introduccion">
            Explora niveles, trayectorias y evidencia observable para orientar próximas observaciones.
          </p>
        </div>
        <Link className="boton boton--secundario" to={esProfesora ? '/profesora/inicio' : '/'}>Volver al inicio</Link>
      </header>

      {esProfesora && modoRevision === 'demo' && (
        <p className="aviso-demo" role="status"><strong>Modo demostración</strong>: cursos y advertencias simulados.</p>
      )}

      {estadoDatos.estado === 'cargando' && <Cargando mensaje="Cargando experiencia…" />}
      {estadoDatos.estado === 'error' && <ErrorEstado mensaje={`No se pudo cargar la experiencia: ${estadoDatos.mensaje}`} />}

      {estadoDatos.estado === 'listo' && datos && cursos.length === 0 && (
        <Vacio mensaje={esProfesora ? 'No tienes cursos disponibles para esta experiencia.' : 'No hay cursos disponibles.'} />
      )}

      {estadoDatos.estado === 'listo' && datos && cursos.length > 0 && (
        <>
          <section className="tarjetas" aria-label="Resumen del alcance visible">
            <Tarjeta etiqueta={esProfesora ? 'Mis cursos' : 'Cursos'} valor={String(cursos.length)} />
            <Tarjeta etiqueta="Niños/as" valor={String(datos.ninos.length)} />
            <Tarjeta etiqueta="Con señales" valor={String(totalAlertas)} alerta={totalAlertas > 0} />
            <Tarjeta etiqueta="Con seguimiento" valor={String(trayectorias?.conSeguimiento ?? 0)} />
            {esProfesora && (
              <Tarjeta
                etiqueta="Por confirmar"
                valor={valorPendientes(estadoPendientes.estado, notificaciones.length)}
                alerta={estadoPendientes.estado === 'listo' && notificaciones.length > 0}
              />
            )}
          </section>

          {esProfesora && estadoPendientes.estado === 'error' && (
            <ErrorEstado mensaje={`No se pudo consultar la cola por confirmar: ${estadoPendientes.mensaje}`} />
          )}

          <section className="panel experiencia__filtros" aria-label="Seleccionar curso y niño o niña">
            <div className="experiencia__campo">
              <label htmlFor="experiencia-curso">Curso</label>
              <select
                id="experiencia-curso"
                value={curso ? claveCurso(curso.idJardin, curso.salaGrupo) : ''}
                onChange={(evento) => { setClaveSeleccionada(evento.target.value); setIdNinoSeleccionado(''); }}
              >
                {cursos.map((actual) => (
                  <option key={claveCurso(actual.idJardin, actual.salaGrupo)} value={claveCurso(actual.idJardin, actual.salaGrupo)}>
                    {actual.nombreJardin} · {actual.salaGrupo}
                  </option>
                ))}
              </select>
            </div>
            <div className="experiencia__campo">
              <label htmlFor="experiencia-nino">Niño/a</label>
              <select
                id="experiencia-nino"
                value={alumno?.idNino ?? ''}
                onChange={(evento) => setIdNinoSeleccionado(evento.target.value)}
                disabled={alumnos.length === 0}
              >
                {alumnos.map((actual) => (
                  <option key={actual.idNino} value={actual.idNino}>
                    {actual.nombreVisible || actual.idNino}{actual.nombreVisible ? ` · ${actual.idNino}` : ''}
                  </option>
                ))}
              </select>
            </div>
          </section>

          {curso && (
            <section className="panel" aria-labelledby="experiencia-curso-titulo">
              <h3 id="experiencia-curso-titulo">{curso.nombreJardin} · {curso.salaGrupo}</h3>
              <p>Nivel promedio: <strong>{formatearPromedio(curso.nivelPromedio)}</strong> · {curso.totalNinos} niños/as.</p>
              <GraficoBarras datos={distribucion} titulo="Distribución del nivel vigente" etiquetaValor="Niños/as" />
            </section>
          )}

          {ficha ? (
            <FichaAcompanamiento ficha={ficha} dominios={dominios} niveles={datos.niveles} />
          ) : (
            <Vacio mensaje="Este curso no tiene niños/as disponibles." />
          )}
        </>
      )}
    </div>
  );
}
