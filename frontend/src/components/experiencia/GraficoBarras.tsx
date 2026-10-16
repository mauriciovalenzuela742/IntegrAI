import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export interface DatoBarra {
  id: string;
  nombre: string;
  valor: number;
}

interface Props {
  datos: DatoBarra[];
  titulo: string;
  etiquetaValor: string;
}

export function GraficoBarras({ datos, titulo, etiquetaValor }: Props) {
  const altura = Math.max(220, datos.length * 44);
  return (
    <figure className="experiencia__figura">
      <figcaption>{titulo}</figcaption>
      <div className="experiencia__grafico" style={{ height: altura }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
            <XAxis type="number" allowDecimals={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="nombre"
              width={112}
              interval={0}
              tickLine={false}
              tick={{ fontSize: 12, fill: '#5b6676' }}
            />
            <Tooltip formatter={(valor: number) => [String(valor), etiquetaValor]} />
            <Bar dataKey="valor" name={etiquetaValor} fill="#2563eb" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="experiencia__datos-grafico">
        <summary>Ver datos: {titulo}</summary>
        <table>
          <caption className="sr-only">Datos del gráfico: {titulo}</caption>
          <thead><tr><th scope="col">Categoría</th><th scope="col">{etiquetaValor}</th></tr></thead>
          <tbody>
            {datos.map((dato) => (
              <tr key={dato.id}><th scope="row">{dato.nombre}</th><td>{dato.valor}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
