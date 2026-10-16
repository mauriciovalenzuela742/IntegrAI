import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { NotificacionAdvertencia } from '../domain/tipos';
import type { AccionRevision } from '../services/ServicioRevision';

interface Props {
  notificaciones: NotificacionAdvertencia[];
  onResolver?: (idPendiente: string, accion: AccionRevision, nivel?: number) => void;
  resolviendoId?: string | null;
}

export function ListaAdvertencias({ notificaciones, onResolver, resolviendoId }: Props) {
  const [editando, setEditando] = useState<string | null>(null);
  const [niveles, setNiveles] = useState<Record<string, string>>({});

  return (
    <ol className="lista-advertencias">
      {notificaciones.map((notificacion) => {
        const pendiente = notificacion.pendiente;
        const ocupado = resolviendoId === notificacion.idNotificacion;
        const nivelTexto =
          niveles[notificacion.idNotificacion] ??
          (pendiente.nivelPropuesto !== null ? String(pendiente.nivelPropuesto) : '');
        return (
          <li key={notificacion.idNotificacion} className="advertencia">
            <span className="advertencia__icono" aria-hidden="true">!</span>
            <span className="sr-only">Caso por confirmar</span>
            <div className="advertencia__contenido">
              <p className="advertencia__titulo">{notificacion.titulo}</p>
              <p className="advertencia__detalle">{notificacion.detalle}</p>
              <div className="advertencia__pie">
                <time dateTime={notificacion.fecha}>{notificacion.fecha}</time>
                <Link to={notificacion.href}>Ver ficha</Link>
              </div>

              {onResolver && (
                <div className="advertencia__acciones" role="group" aria-label="Verificar caso">
                  <button type="button" disabled={ocupado}
                          onClick={() => onResolver(notificacion.idNotificacion, 'aprobado')}>
                    ✓ Está bien (nivel {pendiente.nivelPropuesto ?? '—'})
                  </button>
                  {editando === notificacion.idNotificacion ? (
                    <>
                      <label className="sr-only" htmlFor={`nivel-${notificacion.idNotificacion}`}>Nivel</label>
                      <input
                        id={`nivel-${notificacion.idNotificacion}`}
                        type="number" min={1} max={9} value={nivelTexto}
                        onChange={(e) =>
                          setNiveles((prev) => ({ ...prev, [notificacion.idNotificacion]: e.target.value }))}
                      />
                      <button type="button" disabled={ocupado}
                              onClick={() => {
                                const valor = Number(nivelTexto);
                                if (Number.isInteger(valor) && valor >= 1 && valor <= 9) {
                                  onResolver(notificacion.idNotificacion, 'editado', valor);
                                  setEditando(null);
                                }
                              }}>
                        Guardar
                      </button>
                      <button type="button" onClick={() => setEditando(null)}>Cancelar</button>
                    </>
                  ) : (
                    <button type="button" disabled={ocupado}
                            onClick={() => setEditando(notificacion.idNotificacion)}>
                      ✏️ Cambiar nivel
                    </button>
                  )}
                  <button type="button" disabled={ocupado}
                          onClick={() => onResolver(notificacion.idNotificacion, 'rechazado')}>
                    🚫 No es este niño/a
                  </button>
                  {ocupado && <span className="advertencia__ocupado" role="status">guardando…</span>}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
