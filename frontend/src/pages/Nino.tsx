import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { BadgeAlerta } from '../components/BadgeAlerta';
import { BadgeNivel } from '../components/BadgeNivel';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';
import { GraficoTrayectoria } from '../components/GraficoTrayectoria';
import { Tarjeta } from '../components/Tarjeta';
import { useEstadoDatos } from '../data/DatosContext';
import { ajustarNivel, usaApi } from '../data/cargar';
import { useRevision } from '../data/RevisionContext';
import { tieneAccesoNino } from '../domain/acceso';
import { fichaNino, nivelPorNumero } from '../domain/consultas';
import { useRecomendaciones } from '../data/RecomendacionesContext';

const HOY = new Date();

function RecomendacionesFicha({ idNino }: { idNino: string }) {
  const { aprobadasDe, pendientes } = useRecomendaciones();
  const aprobadas = aprobadasDe(idNino);
  const tienePendientes = pendientes.some((item) => item.idNino === idNino);
  if (aprobadas.length === 0 && !tienePendientes) return null;
  return (
    <section aria-label="Recomendaciones pedagógicas" className="panel">
      <h3>Recomendaciones pedagógicas</h3>
      {aprobadas.map((item) => <article key={item.idRecomendacion} className="recomendacion-ficha">
        <p>{item.textoVisible}</p>
        {item.sugerencias.map((s, i) => <p key={i}>{s.texto}</p>)}
        <p className="recomendacion__limite">{item.aviso}</p>
      </article>)}
      {tienePendientes && <p><a href="#/pendientes">Hay propuestas pendientes; revísalas en Por verificar.</a></p>}
    </section>
  );
}

export function Nino() {
  const { idNino = '' } = useParams();
  const estado = useEstadoDatos();
  const { profesora } = useRevision();
  const nino = estado.estado === 'listo'
    ? estado.datos.ninos.find((item) => item.idNino === idNino)
    : undefined;
  const autorizado = !profesora || !nino || tieneAccesoNino(profesora, nino);

  const vista = useMemo(() => {
    if (estado.estado !== 'listo' || !autorizado) {
      return null;
    }
    const ficha = fichaNino(estado.datos, idNino, HOY);
    if (!ficha) {
      return null;
    }
    const niveles = nivelPorNumero(estado.datos.niveles);
    return {
      ficha,
      nivelVigenteInfo:
        ficha.nivelVigente !== null ? niveles.get(ficha.nivelVigente) : undefined,
      trayectoria: ficha.observaciones.map((o) => ({
        fecha: o.fechaObservacion,
        nivel: o.nivelEstimado,
      })),
    };
  }, [autorizado, estado, idNino]);

  const [nivelAjuste, setNivelAjuste] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [mensajeAjuste, setMensajeAjuste] = useState<string | null>(null);
  const [errorAjuste, setErrorAjuste] = useState<string | null>(null);
  const puedeAjustar = usaApi();

  async function guardarNivel() {
    const valor = Number(nivelAjuste || vista?.ficha.nivelVigente);
    if (!Number.isInteger(valor) || valor < 1 || valor > 9) {
      setErrorAjuste('Elige un nivel entre 1 y 9');
      return;
    }
    setGuardando(true);
    setErrorAjuste(null);
    setMensajeAjuste(null);
    try {
      await ajustarNivel(idNino, valor, profesora?.idEducadora);
      setMensajeAjuste(`Nivel actualizado a ${valor} ✓`);
      setNivelAjuste('');
    } catch (error: unknown) {
      setErrorAjuste(error instanceof Error ? error.message : 'No se pudo guardar el nivel');
    } finally {
      setGuardando(false);
    }
  }

  const idJardin = vista?.ficha.nino.idJardin ?? nino?.idJardin;
  const sala = vista?.ficha.nino.salaGrupo ?? nino?.salaGrupo;

  return (
    <>
      <Breadcrumbs
        migas={[
          profesora
            ? { etiqueta: 'Inicio', ruta: '/profesora/inicio' }
            : { etiqueta: 'Cursos', ruta: '/' },
          ...(autorizado && idJardin && sala
            ? [{ etiqueta: `${idJardin} · ${sala}`, ruta: `/curso/${idJardin}/${sala}` }]
            : []),
          { etiqueta: nino?.nombreVisible || idNino },
        ]}
      />

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}
      {estado.estado === 'listo' && !autorizado && <Vacio mensaje="No tienes acceso" />}
      {estado.estado === 'listo' && autorizado && !vista && (
        <Vacio mensaje={`No se encontró el niño/a ${idNino}.`} />
      )}

      {estado.estado === 'listo' && autorizado && vista && (
        <>
          <h2>{vista.ficha.nino.nombreVisible || idNino}</h2>

          <section aria-label="Resumen del niño/a" className="tarjetas">
            <Tarjeta etiqueta="Edad (meses)" valor={String(vista.ficha.edadMeses)} />
            <Tarjeta etiqueta="Nivel vigente" valor={vista.ficha.nivelVigente?.toString() ?? '—'} />
            <Tarjeta etiqueta="Nivel esperado" valor={vista.ficha.nivelEsperado?.toString() ?? '—'} />
            <Tarjeta
              etiqueta="Brecha"
              valor={
                vista.ficha.brecha === null
                  ? '—'
                  : vista.ficha.brecha > 0
                    ? `+${vista.ficha.brecha}`
                    : String(vista.ficha.brecha)
              }
              alerta={vista.ficha.alerta}
            />
          </section>

          {vista.nivelVigenteInfo && (
            <section aria-label="Nivel vigente" className="panel">
              <h3>
                Nivel {vista.nivelVigenteInfo.nivel}: {vista.nivelVigenteInfo.nombreNivel}{' '}
                {vista.ficha.alerta && <BadgeAlerta activa />}
              </h3>
              <p className="ficha-descripcion">{vista.nivelVigenteInfo.descripcion}</p>
            </section>
          )}

          <RecomendacionesFicha idNino={idNino} />

          {vista.ficha.ajustadoManual && (
            <p className="ficha-descripcion" role="status">
              ✏️ Nivel ajustado manualmente por la profesora.
            </p>
          )}

          {puedeAjustar && (
            <section aria-label="Ajustar nivel" className="panel">
              <h3 className="tarjeta__etiqueta">Ajustar nivel (profesora)</h3>
              <p className="ficha-descripcion">
                Puedes <strong>corregir el nivel vigente</strong> — incluso los que el modelo
                registró solo (por encima del umbral).
              </p>
              {errorAjuste && <ErrorEstado mensaje={errorAjuste} />}
              {mensajeAjuste && <p className="estado" role="status">{mensajeAjuste}</p>}
              <div className="advertencia__acciones">
                <label htmlFor="nivel-ajuste">Nivel (1–9)</label>
                <input
                  id="nivel-ajuste"
                  type="number"
                  min={1}
                  max={9}
                  value={nivelAjuste}
                  placeholder={String(vista.ficha.nivelVigente ?? '')}
                  onChange={(e) => setNivelAjuste(e.target.value)}
                />
                <button type="button" disabled={guardando} onClick={guardarNivel}>
                  {guardando ? 'Guardando…' : 'Guardar nivel'}
                </button>
              </div>
            </section>
          )}

          <section aria-label="Trayectoria del nivel" className="panel">
            <h3 className="tarjeta__etiqueta">Trayectoria del nivel</h3>
            {vista.trayectoria.length === 0 ? (
              <Vacio mensaje="Sin observaciones registradas." />
            ) : (
              <GraficoTrayectoria datos={vista.trayectoria} />
            )}
          </section>

          <section aria-label="Observaciones" className="panel">
            <h3 className="tarjeta__etiqueta">Observaciones</h3>
            {vista.ficha.observaciones.length === 0 ? (
              <Vacio mensaje="Sin observaciones registradas." />
            ) : (
              [...vista.ficha.observaciones]
                .slice()
                .reverse()
                .map((obs) => (
                  <article key={obs.idObservacion} className="observacion">
                    <div className="observacion__cabecera">
                      <span className="observacion__fecha">{obs.fechaObservacion}</span>
                      <span className="observacion__formato">{obs.formatoCaptura}</span>
                      <BadgeNivel nivel={obs.nivelEstimado} />
                    </div>
                    {obs.manifestaciones.length > 0 ? (
                      <ul>
                        {obs.manifestaciones.map((m) => (
                          <li key={m.idManifestacion}>{m.textoObservable}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="ficha-descripcion">Sin manifestaciones registradas.</p>
                    )}
                  </article>
                ))
            )}
          </section>
        </>
      )}
    </>
  );
}
