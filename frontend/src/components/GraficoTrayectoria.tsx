import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Punto {
  fecha: string;
  nivel: number;
}

interface Props {
  datos: Punto[];
  minNivel?: number;
  maxNivel?: number;
}

export function GraficoTrayectoria({ datos, minNivel = 1, maxNivel = 9 }: Props) {
  return (
    <div
      className="grafico"
      role="img"
      aria-label="Trayectoria del nivel estimado en el tiempo"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={datos} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
          <XAxis dataKey="fecha" tickLine={false} />
          <YAxis domain={[minNivel, maxNivel]} allowDecimals={false} tickLine={false} width={32} />
          <Tooltip
            formatter={(valor: number) => [`${valor}`, 'Nivel']}
            labelFormatter={(fecha) => `Fecha ${fecha}`}
          />
          <Line
            type="monotone"
            dataKey="nivel"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
