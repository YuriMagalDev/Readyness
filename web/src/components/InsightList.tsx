import type { Insight } from "../types";
import MetricChip from "./MetricChip";

export default function InsightList({ insights }: { insights: Insight[] }) {
  if (!insights.length) {
    return <div style={{ fontSize: 12, color: "var(--text-faint)" }}>Sem insights hoje.</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {insights.map((ins, i) => (
        <div key={i} className="card" style={{ padding: "10px 12px" }}>
          <div style={{ fontSize: 13, color: "var(--text)" }}>{ins.texto}</div>
          <div style={{ marginTop: 6 }}>
            {ins.metricas_usadas.map((s) => <MetricChip key={s.key} src={s} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
