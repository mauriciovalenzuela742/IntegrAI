import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { CampanaNotificaciones } from './components/CampanaNotificaciones';
import { useRevision } from './data/RevisionContext';
import { Curso } from './pages/Curso';
import { Cursos } from './pages/Cursos';
import { Experiencia } from './pages/Experiencia';
import { Jardines } from './pages/Jardines';
import { Nino } from './pages/Nino';
import { Pendientes } from './pages/Pendientes';
import { ProfesoraIngreso } from './pages/ProfesoraIngreso';
import { ProfesoraInicio } from './pages/ProfesoraInicio';

export function App() {
  const navegar = useNavigate();
  const { profesora, notificaciones, salir } = useRevision();
  const inicio = profesora ? '/profesora/inicio' : '/';

  function cerrarSesion() {
    salir();
    navegar('/profesora', { replace: true });
  }

  return (
    <div className="app">
      <header className="cabecera">
        <div className="contenedor cabecera__contenido">
          <div className="cabecera__marca">
            <h1>
              <Link to={inicio}>IntegrAI</Link>
            </h1>
            <p>Dashboard de apoyo pedagógico</p>
          </div>

          {profesora ? (
            <div className="cabecera__sesion">
              <span className="cabecera__profesora">{profesora.idEducadora}</span>
              <CampanaNotificaciones notificaciones={notificaciones} />
              <button type="button" className="boton boton--secundario" onClick={cerrarSesion}>
                Salir
              </button>
            </div>
          ) : (
            <div className="cabecera__coordinacion">
              <nav className="navegacion" aria-label="Navegación principal">
                <NavLink to="/" end>Cursos</NavLink>
                <NavLink to="/jardines">Jardines</NavLink>
                <NavLink to="/experiencia">Acompañamiento</NavLink>
                <NavLink to="/pendientes">Por verificar</NavLink>
              </nav>
              <Link className="boton boton--secundario" to="/profesora">
                Soy profesora
              </Link>
            </div>
          )}
        </div>
      </header>

      <main className="principal">
        <div className="contenedor">
          <Routes>
            <Route path="/" element={profesora ? <Navigate to="/profesora/inicio" replace /> : <Cursos />} />
            <Route path="/curso/:idJardin/:sala" element={<Curso />} />
            <Route path="/nino/:idNino" element={<Nino />} />
            <Route path="/jardines" element={profesora ? <Navigate to="/profesora/inicio" replace /> : <Jardines />} />
            <Route path="/experiencia" element={profesora ? <Navigate to="/profesora/experiencia" replace /> : <Experiencia modo="coordinacion" />} />
            <Route path="/pendientes" element={profesora ? <Navigate to="/profesora/inicio" replace /> : <Pendientes />} />
            <Route path="/profesora" element={profesora ? <Navigate to="/profesora/inicio" replace /> : <ProfesoraIngreso />} />
            <Route path="/profesora/inicio" element={profesora ? <ProfesoraInicio /> : <Navigate to="/profesora" replace />} />
            <Route path="/profesora/experiencia" element={profesora ? <Experiencia modo="profesora" /> : <Navigate to="/profesora" replace />} />
            <Route path="*" element={<Navigate to={inicio} replace />} />
          </Routes>
        </div>
      </main>

      <footer className="pie">
        <div className="contenedor">
          <p>Herramienta de apoyo pedagógico, no constituye diagnóstico clínico.</p>
        </div>
      </footer>
    </div>
  );
}
