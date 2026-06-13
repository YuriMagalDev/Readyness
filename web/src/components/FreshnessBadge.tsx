import type { MetricStatus } from "../types";

const CFG: Record<MetricStatus, { emoji: string; titulo: string }> = {
  fresco: { emoji: "🟢", titulo: "Fresco" },
  velho: { emoji: "🟡", titulo: "Desatualizado" },
  ausente: { emoji: "⚪", titulo: "Ausente" },
  estimado: { emoji: "〰️", titulo: "Estimado" },
};

export default function FreshnessBadge({ status, measuredAt }: { status: MetricStatus; measuredAt?: string | null }) {
  const c = CFG[status];
  const tip = measuredAt ? `${c.titulo} · medido em ${measuredAt.replace("T", " ")}` : c.titulo;
  return <span title={tip} style={{ fontSize: 11 }}>{c.emoji}</span>;
}
