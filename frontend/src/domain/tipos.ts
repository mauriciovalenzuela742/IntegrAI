export type FormatoCaptura = 'texto' | 'foto' | 'audio' | 'video';

export interface Nivel {
  nivel: number;
  nombreNivel: string;
  edadMinMeses: number;
  edadMaxMeses: number;
  descripcion: string;
}

export interface Jardin {
  idJardin: string;
  nombreFantasia: string;
  comuna: string;
  region: string;
}

export interface Nino {
  idNino: string;
  /** Etiqueta legible "Nombre I." (nombre de pila + inicial). Nunca el nombre completo. */
  nombreVisible?: string;
  fechaNacimiento: string;
  idJardin: string;
  salaGrupo: string;
  fechaIngreso: string;
}

export interface Observacion {
  idObservacion: string;
  idNino: string;
  fechaObservacion: string;
  formatoCaptura: string;
  nivelEstimado: number;
}

export interface Manifestacion {
  idManifestacion: string;
  nivel: number;
  dominio: string;
  textoObservable: string;
}

export interface ObservacionManifestacion {
  idObservacion: string;
  idManifestacion: string;
}

export interface Evaluacion {
  idNino: string;
  dominio: string;
  nivel: number;
  margen: number;
  periodo: string;
  tendencia: string;
  alerta: string | null;
  /** `auto` (cron) | `manual*` (ajustada por la profesora). */
  origen?: string;
}

export interface Educadora {
  idEducadora: string;
  idJardin: string;
  rol: string;
  aniosExperiencia: number;
}

export interface CursoProfesora {
  idJardin: string;
  salaGrupo: string;
}

export interface Profesora {
  idEducadora: string;
  telefono: string;
  cursos: CursoProfesora[];
}

export interface Pendiente {
  idPendiente: string;
  idNinoPropuesto: string;
  /** Etiqueta legible del niño/a ("Emilia Co."); si falta, la UI cae al código. */
  nombreVisible?: string;
  idEducadora: string | null;
  nivelPropuesto: number | null;
  dominio: string | null;
  margen: number | null;
  motivo: string;
  evidencia: string;
  estado: string;
  creadoEn: string;
  idJardin: string | null;
  salaGrupo: string | null;
}

export interface NotificacionAdvertencia {
  idNotificacion: string;
  tipo: 'advertencia';
  titulo: string;
  detalle: string;
  fecha: string;
  href: string;
  /** Caso original (para poder aprobarlo/editarlo/rechazarlo desde la UI). */
  pendiente: Pendiente;
}

export interface CitaRecomendacion {
  fuenteId: string;
  organizacion: string;
  titulo: string;
  paginaPdf: number;
  fragmento: string;
  url: string;
}

export interface Recomendacion {
  idRecomendacion: string;
  idNino: string;
  idJardin: string;
  salaGrupo: string;
  estadoRevision: 'por_verificar';
  hito: { id: string; estado: string; zona: string; edadMeses: number } | null;
  hallazgosDeterministicos: Array<{ id: string; tipo: string; regla: string; resultado: string; observacionIds: string[] }>;
  resumen: string;
  sugerencias: Array<{ texto: string; citas: CitaRecomendacion[] }>;
  derivacionSalud: boolean;
  aviso: string;
}

export interface LoteRecomendaciones {
  version: 1;
  generadoEn: string;
  umbralesPorValidar: true;
  aviso: string;
  items: Recomendacion[];
}

export interface DecisionRecomendacion {
  estado: 'aprobada' | 'editada' | 'descartada';
  textoEditado?: string;
}
