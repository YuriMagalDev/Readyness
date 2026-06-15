import type { HTMLAttributes } from "react";
import { useStyle } from "./useStyle";

const CSS = `
.rd-fresh {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  line-height: 1;
  white-space: nowrap;
}
.rd-fresh__mark { flex: none; display: inline-flex; }
.rd-fresh--fresh { color: var(--go-ink); }
.rd-fresh--fresh .rd-fresh__dot {
  width: 7px; height: 7px; border-radius: 999px; background: var(--fresh-dot);
  box-shadow: 0 0 0 0 color-mix(in oklch, var(--fresh-dot) 60%, transparent);
  animation: rd-breathe var(--dur-breathe) var(--ease-in-out) infinite;
}
@keyframes rd-breathe {
  0%, 100% { box-shadow: 0 0 0 0 color-mix(in oklch, var(--fresh-dot) 55%, transparent); }
  50% { box-shadow: 0 0 0 4px color-mix(in oklch, var(--fresh-dot) 0%, transparent); }
}
.rd-fresh--stale { color: var(--stale); }
.rd-fresh--stale .rd-fresh__ring {
  width: 7px; height: 7px; border-radius: 999px;
  border: 1.5px solid currentColor; opacity: 0.75;
}
.rd-fresh--estimated { color: var(--estimated); }
.rd-fresh--estimated .rd-fresh__tilde { font-size: 12px; font-weight: 600; line-height: 1; }
.rd-fresh--absent { color: var(--text-disabled); }
.rd-fresh--absent .rd-fresh__dash {
  width: 9px; height: 1.5px; border-radius: 2px; background: currentColor;
}
.rd-fresh__label { font-weight: 500; }
.rd-fresh__when { color: var(--text-faint); }
.rd-fresh--fresh .rd-fresh__when { color: color-mix(in oklch, var(--go-ink) 60%, var(--text-faint)); }
`;

export type FreshStatus = "fresh" | "stale" | "estimated" | "absent";

const LABEL: Record<FreshStatus, string> = {
  fresh: "Fresco",
  stale: "Desatualizado",
  estimated: "Estimado",
  absent: "Ausente",
};

export interface FreshnessProps extends HTMLAttributes<HTMLSpanElement> {
  status?: FreshStatus;
  when?: string | null;
  label?: string;
  showLabel?: boolean;
}

/** Freshness — o indicador-assinatura: o quanto dá pra confiar na idade do número.
 *  Fallback defensivo: status desconhecido → tratado como "absent" (nunca quebra). */
export function Freshness({
  status = "fresh",
  when,
  label,
  showLabel = true,
  className = "",
  ...rest
}: FreshnessProps) {
  useStyle("rd-fresh-css", CSS);
  const safe: FreshStatus = (["fresh", "stale", "estimated", "absent"] as const).includes(
    status as FreshStatus,
  )
    ? status
    : "absent";
  const text = label ?? LABEL[safe] ?? safe;
  return (
    <span className={`rd-fresh rd-fresh--${safe} ${className}`.trim()} {...rest}>
      <span className="rd-fresh__mark" aria-hidden="true">
        {safe === "fresh" && <span className="rd-fresh__dot" />}
        {safe === "stale" && <span className="rd-fresh__ring" />}
        {safe === "estimated" && <span className="rd-fresh__tilde">~</span>}
        {safe === "absent" && <span className="rd-fresh__dash" />}
      </span>
      {showLabel && <span className="rd-fresh__label">{text}</span>}
      {when && <span className="rd-fresh__when">· {when}</span>}
    </span>
  );
}
