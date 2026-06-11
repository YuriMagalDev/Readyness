import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import type { SeriePoint } from "../types";

interface Props {
  data: SeriePoint[];
  cor: string;
}

export default function Sparkline({ data, cor }: Props) {
  const pontos = data.filter((p) => p.valor !== null);
  return (
    <ResponsiveContainer width="100%" height={48}>
      <LineChart data={pontos}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line type="monotone" dataKey="valor" stroke={cor} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
