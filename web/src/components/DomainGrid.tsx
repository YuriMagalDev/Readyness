import type { MetricsPayload } from "../types";
import { fmtMetric } from "../lib/fmt";
import FreshnessBadge from "./FreshnessBadge";

const TITULOS: Record<string, string> = {
  prontidao: "Prontidão", recuperacao: "Recuperação",
  atividade: "Atividade", corpo: "Corpo",
};
const ORDEM = ["prontidao", "recuperacao", "atividade", "corpo"];

export default function DomainGrid({ metrics }: { metrics: MetricsPayload }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {ORDEM.map((dom) => {
        const cells = metrics.dominios[dom] || [];
        if (!cells.length) return null;
        return (
          <div key={dom}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
              letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>
              {TITULOS[dom]}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
              {cells.map((c) => (
                <div key={c.key} className="card" style={{ padding: "8px 10px" }}>
                  <div style={{ fontSize: 11, color: "var(--text-faint)", display: "flex",
                    justifyContent: "space-between", alignItems: "center" }}>
                    <span>{c.label}</span>
                    <FreshnessBadge status={c.status} measuredAt={c.measured_at} />
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 500, color: "#fff", marginTop: 2 }}>
                    {fmtMetric(c.value, c.unidade)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
