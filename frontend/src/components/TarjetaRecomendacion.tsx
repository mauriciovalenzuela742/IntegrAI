import { useEffect, useRef, useState } from 'react';
import type { DecisionRecomendacion, Recomendacion } from '../domain/tipos';

export function TarjetaRecomendacion({ item, nombre, onDecidir }: {
  item: Recomendacion;
  /** "Nombre I." del niño/a, si se conoce (datos vivos). */
  nombre?: string;
  onDecidir?: (decision: DecisionRecomendacion) => void;
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(item.resumen);
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (editando) area.current?.focus(); }, [editando]);
  return (
    <article className="recomendacion" aria-labelledby={`titulo-${item.idRecomendacion}`}>
      <header className="recomendacion__cabecera">
        <h4 id={`titulo-${item.idRecomendacion}`}>{nombre || item.idNino} · {item.hito?.id.replace(/_/g, ' ') ?? (item.hallazgosDeterministicos.some((h) => h.tipo === 'nivel') ? 'identidad y autonomía' : 'revisión de nota')}</h4>
        <span className="badge-alerta">Por verificar</span>
      </header>
      <p>{item.resumen}</p>
      <h5>Análisis determinístico</h5>
      <ul>{item.hallazgosDeterministicos.map((h) => <li key={h.id}>{h.resultado}</li>)}</ul>
      {item.sugerencias.map((sugerencia, indice) => (
        <section key={indice} aria-label={`Sugerencia ${indice + 1}`}>
          <p><strong>Propuesta:</strong> {sugerencia.texto}</p>
          <details><summary>Respaldo profesional</summary>
            {sugerencia.citas.map((cita) => <blockquote key={`${cita.fuenteId}-${cita.paginaPdf}`}>
              “{cita.fragmento}” — <a href={cita.url} target="_blank" rel="noreferrer">{cita.organizacion}, {cita.titulo}</a>, p. PDF {cita.paginaPdf}.
            </blockquote>)}
          </details>
        </section>
      ))}
      <p className="recomendacion__limite"><strong>Umbrales por validar.</strong> {item.aviso}</p>
      {onDecidir && (editando ? (
        <div className="recomendacion__edicion">
          <label htmlFor={`edicion-${item.idRecomendacion}`}>Texto corregido por la educadora</label>
          <textarea ref={area} id={`edicion-${item.idRecomendacion}`} value={texto} onChange={(e) => setTexto(e.target.value)} />
          <button type="button" onClick={() => onDecidir({ estado: 'editada', textoEditado: texto })}>Guardar y aprobar edición</button>
          <button type="button" onClick={() => setEditando(false)}>Cancelar</button>
        </div>
      ) : (
        <div className="advertencia__acciones">
          <button type="button" onClick={() => onDecidir({ estado: 'aprobada' })}>Aprobar</button>
          <button type="button" onClick={() => setEditando(true)}>Editar</button>
          <button type="button" onClick={() => onDecidir({ estado: 'descartada' })}>Descartar</button>
        </div>
      ))}
    </article>
  );
}
