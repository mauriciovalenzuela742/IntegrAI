import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import { App } from './App';
import { DatosProvider } from './data/DatosContext';
import { RevisionProvider } from './data/RevisionContext';
import { RecomendacionesProvider } from './data/RecomendacionesContext';
import './estilos.css';

const contenedor = document.getElementById('root');
if (!contenedor) {
  throw new Error('No se encontró el elemento raíz');
}

createRoot(contenedor).render(
  <StrictMode>
    <HashRouter>
      <DatosProvider>
        <RevisionProvider>
          <RecomendacionesProvider>
            <App />
          </RecomendacionesProvider>
        </RevisionProvider>
      </DatosProvider>
    </HashRouter>
  </StrictMode>,
);
