import type { HTMLAttributes } from "react";
import { useStyle } from "./useStyle";
import type { FreshStatus } from "./Freshness";

const CSS = `
.rd-chip {
  display: inline-flex; align-items: center; gap: 7px;
  background: var(--surface-raised);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-pill);
  padding: 4px 11px 4px 9px;
  white-space: nowrap;
  transition: border-color var(--dur-fast) var(--ease-out);
}
.rd-chip:hover { border-color: var(--ink-3); }
.rd-chip__mark { width: 6px; height: 6px; border-radius: 999px; flex: none; }
.rd-chip--fresh .rd-chip__mark { background: var(--fresh-dot); }
.rd-chip--stale .rd-chip__mark { background: transparent; border: 1.5px solid var(--stale); width: 7px; height: 7px; }
.rd-chip--estimated .rd-chip__mark { background: var(--estimated); }
.rd-chip--absent .rd-chip__mark { background: var(--text-disabled); }
.rd-chip__label { font-family: var(--font-ui); font-size: var(--text-xs); color: var(--text-muted); font-weight: var(--weight-medium); }
.rd-chip__value {
  font-family: var(--font-mono); font-size: var(--text-xs); font-variant-numeric: tabular-nums lining-nums;
  color: var(--text-strong); font-weight: var(--weight-medium);
}
.rd-chip--absent .rd-chip__value, .rd-chip--estimated .rd-chip__value { color: var(--text-muted); }
`;

export interface SourceChipProps extends HTMLAttributes<HTMLSpanElement> {
  label: string;
  value?: string | null;
  status?: FreshStatus;
}

/** SourceChip — métrica que embasa um insight (label + valor + marca de frescor). */
export function SourceChip({ label, value, status = "fresh", className = "", ...rest }: SourceChipProps) {
  useStyle("rd-chip-css", CSS);
  const safe: FreshStatus = (["fresh", "stale", "estimated", "absent"] as const).includes(
    status as FreshStatus,
  )
    ? status
    : "absent";
  return (
    <span className={`rd-chip rd-chip--${safe} ${className}`.trim()} {...rest}>
      <span className="rd-chip__mark" aria-hidden="true" />
      <span className="rd-chip__label">{label}</span>
      <span className="rd-chip__value">{value ?? "—"}</span>
    </span>
  );
}
