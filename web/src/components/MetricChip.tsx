import type { InsightSource } from "../types";
import { fmtMetric } from "../lib/fmt";
import FreshnessBadge from "./FreshnessBadge";

export default function MetricChip({ src }: { src: InsightSource }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4,
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: "2px 8px", fontSize: 11, color: "var(--text-dim)",
      margin: "2px 4px 0 0" }}>
      {src.label} {fmtMetric(src.valor, src.unidade)}
      <FreshnessBadge status={src.status} />
    </span>
  );
}
