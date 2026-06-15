import type { HTMLAttributes } from "react";
import { useStyle } from "./useStyle";
import { SourceChip } from "./SourceChip";
import type { FreshStatus } from "./Freshness";

const CSS = `
.rd-insight {
  display: flex; flex-direction: column; gap: var(--space-3);
  background: var(--surface-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  padding: var(--space-5);
}
.rd-insight__text {
  font-family: var(--font-display); font-size: var(--text-lg); line-height: 1.4;
  color: var(--text-strong); letter-spacing: -0.005em; text-wrap: pretty;
}
.rd-insight__sources { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
.rd-insight__from {
  font-family: var(--font-ui); font-size: var(--text-2xs); font-weight: var(--weight-semibold);
  letter-spacing: var(--tracking-eyebrow); text-transform: uppercase; color: var(--text-faint);
  margin-right: var(--space-1);
}
.rd-insight--unavailable {
  background: var(--surface-well);
  border-style: dashed;
  box-shadow: var(--shadow-inset);
  align-items: flex-start;
  gap: var(--space-2);
}
.rd-insight__muted {
  font-family: var(--font-ui); font-size: var(--text-sm); color: var(--text-faint);
  display: flex; align-items: center; gap: var(--space-2);
}
.rd-insight__muted :where(svg) { width: 16px; height: 16px; stroke-width: 1.75; }
`;

export interface InsightSourceItem {
  label: string;
  value?: string | null;
  status?: FreshStatus;
}

export interface InsightProps extends HTMLAttributes<HTMLDivElement> {
  text?: string;
  sources?: InsightSourceItem[];
  variant?: "default" | "unavailable";
  unavailableText?: string;
}

/** Insight — observação curta e rastreável, ancorada nas métricas que a geraram.
 *  `variant="unavailable"` = LLM local fora do ar; o veredito acima continua válido. */
export function Insight({
  text,
  sources = [],
  variant = "default",
  unavailableText = "Análise indisponível — a IA local está fora do ar. O veredito acima continua válido.",
  className = "",
  ...rest
}: InsightProps) {
  useStyle("rd-insight-css", CSS);

  if (variant === "unavailable") {
    return (
      <div className={`rd-insight rd-insight--unavailable ${className}`.trim()} {...rest}>
        <span className="rd-insight__muted">
          <i data-lucide="cloud-off"></i>
          {unavailableText}
        </span>
      </div>
    );
  }

  return (
    <div className={`rd-insight ${className}`.trim()} {...rest}>
      <p className="rd-insight__text">{text}</p>
      {sources.length > 0 && (
        <div className="rd-insight__sources">
          <span className="rd-insight__from">Fontes</span>
          {sources.map((s, i) => (
            <SourceChip key={i} label={s.label} value={s.value} status={s.status} />
          ))}
        </div>
      )}
    </div>
  );
}
