/** Pontes entre o contrato do backend (pt-BR) e os status do design system.
 *  Mapas SEMPRE com fallback (status desconhecido → neutro), regra de robustez
 *  do 02-DESIGN.md: nunca deixar um status inesperado quebrar a tela. */
import type { FreshStatus, VerdictStatus } from "../ds";
import type { MetricStatus } from "../types";

/** veredito do backend → tom do <Verdict>. Desconhecido → "go" (neutro otimista). */
export function verdictTone(status: string | undefined): VerdictStatus {
  switch (status) {
    case "verde":
      return "go";
    case "amarelo":
      return "easy";
    case "vermelho":
      return "rest";
    default:
      return "go";
  }
}

/** status de métrica do backend → status de frescor do design. Desconhecido → "absent". */
export function freshOf(status: MetricStatus | string | undefined): FreshStatus {
  switch (status) {
    case "fresco":
      return "fresh";
    case "velho":
      return "stale";
    case "estimado":
      return "estimated";
    case "ausente":
      return "absent";
    default:
      return "absent";
  }
}

/** "de quando é": deriva um carimbo curto a partir do measured_at (ISO) e do status. */
export function whenLabel(measuredAt: string | null, status: MetricStatus | string): string {
  if (!measuredAt) return status === "estimado" ? "predição" : "sem registro";
  // ISO "2026-06-15T06:12" → mostra hora se for hoje, senão a data curta.
  const iso = measuredAt;
  const today = new Date().toISOString().slice(0, 10);
  if (iso.slice(0, 10) === today) {
    const t = iso.slice(11, 16);
    return t || "hoje";
  }
  return iso.slice(0, 10);
}
