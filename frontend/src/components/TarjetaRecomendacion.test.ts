import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it } from 'vitest';
import { TarjetaRecomendacion } from './TarjetaRecomendacion';
import type { Recomendacion } from '../domain/tipos';

it('renderiza respaldo y aviso textual', () => {
  const item = { idRecomendacion:'REC-00001', idNino:'NINO-00001', idJardin:'JAR-0013', salaGrupo:'SG-C',
    estadoRevision:'por_verificar', hito:null, resumen:'Propuesta', derivacionSalud:false,
    hallazgosDeterministicos:[{id:'H-1',tipo:'nivel',regla:'R',resultado:'Resultado',observacionIds:[]}],
    sugerencias:[{texto:'Actividad',citas:[{fuenteId:'F',organizacion:'OMS',titulo:'Fuente',paginaPdf:1,fragmento:'Cita',url:'https://www.who.int'}]}],
    aviso:'Propuesta para el criterio de la educadora. No es un diagnóstico.' } as Recomendacion;
  const html = renderToStaticMarkup(createElement(TarjetaRecomendacion, { item }));
  expect(html).toContain('Respaldo profesional');
  expect(html).toContain('No es un diagnóstico');
});
