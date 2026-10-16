import { Link } from 'react-router-dom';
import { BadgeNivel } from '../BadgeNivel';
import { GraficoTrayectoria } from '../GraficoTrayectoria';
import type { FichaNino } from '../../domain/consultas';
import { causasAtencion, diagnostico, manifestacionesRecientes, type DominioInfo } from '../../domain/experiencia';
import { estadoManifestaciones, focosPedagogicos } from '../../domain/estimulacion';
import type { Nivel } from '../../domain/tipos';
import { GraficoBarras } from './GraficoBarras';

interface Props {
  ficha: FichaNino;
  dominios: DominioInfo[];
  niveles: Nivel[];
}

export function FichaAcompanamiento({ ficha, dominios, niveles }: Props) {
  const lectura = diagnostico(ficha);
  const causas = causasAtencion(ficha);
  const evidencia = estadoManifestaciones(ficha, dominios);
  const focos = focosPedagogicos(ficha, dominios);
  const trayectoria = ficha.observaciones.map((obs) => ({ fecha: obs.fechaObservacion, nivel: obs.nivelEstimado }));
  const minNivel = niveles.length > 0 ? Math.min(...niveles.map((nivel) => nivel.nivel)) : 1;
  const maxNivel = niveles.length > 0 ? Math.max(...niveles.map((nivel) => nivel.nivel)) : 9;
  const resumenManifestaciones = manifestacionesRecientes(ficha);

  return (
    <article className="experiencia__ficha" aria-labelledby="experiencia-ficha-titulo">
      <header className="experiencia__ficha-cabecera">
        <div>
          <p className="experiencia__sobrelinea">Acompañamiento individual</p>
          <h3 id="experiencia-ficha-titulo">{ficha.nino.nombreVisible || ficha.nino.idNino}</h3>
          {ficha.nino.nombreVisible && <p>{ficha.nino.idNino}</p>}
        </div>
        <Link className="boton boton--secundario" to={`/nino/${encodeURIComponent(ficha.nino.idNino)}`}>
          Abrir ficha completa
        </Link>
      </header>

      <section className={`experiencia__lectura experiencia__lectura--${lectura.estado}`} aria-live="polite">
        <h4>{lectura.titulo}</h4>
        <p>{lectura.detalle}</p>
      </section>

      <dl className="experiencia__metricas-ficha">
        <div><dt>Edad</dt><dd>{ficha.edadMeses} meses</dd></div>
        <div><dt>Nivel vigente</dt><dd><BadgeNivel nivel={ficha.nivelVigente} /></dd></div>
        <div><dt>Nivel esperado</dt><dd><BadgeNivel nivel={ficha.nivelEsperado} /></dd></div>
        <div><dt>Brecha</dt><dd>{ficha.brecha === null ? '—' : ficha.brecha > 0 ? `+${ficha.brecha}` : ficha.brecha}</dd></div>
      </dl>

      <section aria-labelledby="experiencia-senales-titulo">
        <h4 id="experiencia-senales-titulo">Señales para revisar en contexto</h4>
        {causas.length === 0 ? (
          <p className="experiencia__texto-tenue">No hay señales de atención activas con los datos disponibles.</p>
        ) : (
          <ul className="experiencia__causas">
            {causas.map((causa) => (
              <li key={causa.tipo} className={`experiencia__causa experiencia__causa--${causa.tipo}`}>
                <strong>{causa.titulo}</strong><span>{causa.detalle}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="experiencia__aclaracion">Estas señales apoyan la observación pedagógica y no constituyen un diagnóstico clínico.</p>
      </section>

      <div className="experiencia__dos-columnas">
        <section aria-labelledby="experiencia-evidencia-titulo">
          <h4 id="experiencia-evidencia-titulo">Evidencia observable</h4>
          {dominios.length === 0 ? (
            <p className="experiencia__texto-tenue">El catálogo no informa dominios.</p>
          ) : (
            <GraficoBarras
              titulo="Manifestaciones en las últimas tres observaciones por dominio"
              etiquetaValor="Manifestaciones"
              datos={evidencia.porDominio.map((dominio) => ({ id: dominio.dominio, nombre: dominio.nombre, valor: dominio.observadas }))}
            />
          )}
          {resumenManifestaciones.total > 0 && (
            <>
              <p className="experiencia__texto-tenue">
                Mostrando {resumenManifestaciones.visibles.length} de {resumenManifestaciones.total} manifestaciones únicas, priorizando las más recientes.
              </p>
              <ul className="experiencia__manifestaciones">
                {resumenManifestaciones.visibles.map((manifestacion) => <li key={manifestacion.idManifestacion}>{manifestacion.textoObservable}</li>)}
              </ul>
              {resumenManifestaciones.restantes.length > 0 && (
                <details className="experiencia__mas-evidencia">
                  <summary>Ver {resumenManifestaciones.restantes.length} manifestaciones adicionales</summary>
                  <ul className="experiencia__manifestaciones">
                    {resumenManifestaciones.restantes.map((manifestacion) => <li key={manifestacion.idManifestacion}>{manifestacion.textoObservable}</li>)}
                  </ul>
                </details>
              )}
            </>
          )}
        </section>

        <section aria-labelledby="experiencia-focos-titulo">
          <h4 id="experiencia-focos-titulo">Focos para próximas observaciones</h4>
          {focos.length === 0 ? (
            <p className="experiencia__texto-tenue">No hay focos disponibles con el catálogo actual.</p>
          ) : (
            <ul className="experiencia__focos">
              {focos.map((foco) => (
                <li key={foco.dominio}>
                  <strong>{foco.nombre}</strong>
                  <p>{foco.motivo === 'sin-evidencia'
                    ? 'Falta evidencia reciente; observa este ámbito antes de sacar conclusiones.'
                    : 'La evidencia disponible sugiere mantener este ámbito en observación.'}</p>
                  {foco.acciones.length > 0 && (
                    <ul>{foco.acciones.map((accion) => <li key={accion.titulo}><strong>{accion.titulo}:</strong> {accion.detalle}</li>)}</ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="experiencia-trayectoria-titulo">
        <h4 id="experiencia-trayectoria-titulo">Trayectoria de observaciones</h4>
        {trayectoria.length === 0 ? (
          <p className="experiencia__texto-tenue">Todavía no hay observaciones para construir una trayectoria.</p>
        ) : (
          <>
            <GraficoTrayectoria datos={trayectoria} minNivel={minNivel} maxNivel={maxNivel} />
            <ol className="experiencia__trayectoria-texto">
              {trayectoria.map((punto, indice) => <li key={`${punto.fecha}-${indice}`}>{punto.fecha}: nivel {punto.nivel}</li>)}
            </ol>
          </>
        )}
      </section>
    </article>
  );
}
