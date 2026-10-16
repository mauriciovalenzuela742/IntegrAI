import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { cargarRecomendaciones } from './cargar';
import { CLAVE_DECISIONES, recomendacionesAprobadas, recomendacionesPendientes } from '../domain/recomendaciones';
import type { DecisionRecomendacion, LoteRecomendaciones } from '../domain/tipos';

type Estado = { estado: 'cargando' } | { estado: 'error'; mensaje: string } | { estado: 'listo'; lote: LoteRecomendaciones };

interface Valor {
  carga: Estado;
  decisiones: Record<string, DecisionRecomendacion>;
  pendientes: LoteRecomendaciones['items'];
  decidir: (id: string, decision: DecisionRecomendacion) => void;
  aprobadasDe: (idNino: string) => ReturnType<typeof recomendacionesAprobadas>;
}

const Contexto = createContext<Valor | null>(null);

function leerDecisiones(): Record<string, DecisionRecomendacion> {
  try {
    const valor = localStorage.getItem(CLAVE_DECISIONES);
    return valor ? JSON.parse(valor) as Record<string, DecisionRecomendacion> : {};
  } catch {
    return {};
  }
}

export function RecomendacionesProvider({ children }: { children: ReactNode }) {
  const [carga, setCarga] = useState<Estado>({ estado: 'cargando' });
  const [decisiones, setDecisiones] = useState<Record<string, DecisionRecomendacion>>(leerDecisiones);
  useEffect(() => {
    cargarRecomendaciones().then((lote) => setCarga({ estado: 'listo', lote }))
      .catch((error: unknown) => setCarga({ estado: 'error', mensaje: error instanceof Error ? error.message : 'Error desconocido' }));
  }, []);
  function decidir(id: string, decision: DecisionRecomendacion) {
    setDecisiones((actuales) => {
      const nuevas = { ...actuales, [id]: decision };
      try { localStorage.setItem(CLAVE_DECISIONES, JSON.stringify(nuevas)); } catch { /* demo usable sin almacenamiento */ }
      return nuevas;
    });
  }
  const items = carga.estado === 'listo' ? carga.lote.items : [];
  const valor = useMemo<Valor>(() => ({
    carga, decisiones, pendientes: recomendacionesPendientes(items, decisiones), decidir,
    aprobadasDe: (idNino) => recomendacionesAprobadas(items, decisiones, idNino),
  }), [carga, decisiones, items]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useRecomendaciones(): Valor {
  const valor = useContext(Contexto);
  if (!valor) throw new Error('useRecomendaciones debe usarse dentro de RecomendacionesProvider');
  return valor;
}
