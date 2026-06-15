import type { HTMLAttributes, ReactNode } from "react";
import { useStyle } from "./useStyle";
import { Freshness, type FreshStatus } from "./Freshness";

const CSS = `
.rd-metric {
  display: flex; flex-direction: column; gap: var(--space-3);
  background: var(--surface-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-5);
  min-height: 132px;
  transition: border-color var(--dur-base) var(--ease-out);
}
.rd-metric--absent {
  background: var(--surface-well);
  border-style: dashed;
  box-shadow: var(--shadow-inset);
}
.rd-metric__head { display: flex; align-items: center; gap: var(--space-2); }
.rd-metric__icon { color: var(--text-muted); display: inline-flex; }
.rd-metric__icon :where(svg) { width: 16px; height: 16px; stroke-width: 1.75; }
.rd-metric--absent .rd-metric__icon { color: var(--text-disabled); }
.rd-metric__label {
  font-family: var(--font-ui); font-size: var(--text-2xs); font-weight: var(--weight-semibold);
  letter-spacing: var(--tracking-eyebrow); text-transform: uppercase; color: var(--text-faint);
}
.rd-metric__body { display: flex; align-items: baseline; gap: 6px; margin-top: auto; }
.rd-metric__value {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums lining-nums;
  font-feature-settings: var(--num-features);
  font-size: var(--text-metric-xl); line-height: 0.95; letter-spacing: -0.02em;
  color: var(--text-strong);
}
.rd-metric--absent .rd-metric__value { color: var(--text-disabled); font-weight: 300; }
.rd-metric__unit { font-family: var(--font-ui); font-size: var(--text-sm); color: var(--text-muted); font-weight: var(--weight-medium); }
.rd-metric__delta { font-family: var(--font-mono); font-size: var(--text-xs); font-variant-numeric: tabular-nums; }
.rd-metric__delta--up { color: var(--rest); }
.rd-metric__delta--down { color: var(--go); }
.rd-metric__delta--flat { color: var(--text-faint); }
.rd-metric__foot { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
`;

const ARROW: Record<string, string> = { up: "▲", down: "▼", flat: "·" };

export interface MetricCardProps extends HTMLAttributes<HTMLDivElement> {
  label: string;
  value?: ReactNode;
  unit?: string;
  delta?: string;
  deltaTone?: "up" | "down" | "flat";
  icon?: ReactNode;
  status?: FreshStatus;
  when?: string | null;
}

/** MetricCard — uma métrica-chave com valor, unidade, delta e o carimbo de frescor.
 *  `status="absent"` vira poço tracejado com em-dash (vazio que parece intencional). */
export function MetricCard({
  label,
  value,
  unit,
  delta,
  deltaTone = "flat",
  icon,
  status = "fresh",
  when,
  className = "",
  ...rest
}: MetricCardProps) {
  useStyle("rd-metric-css", CSS);
  const absent = status === "absent";
  return (
    <div className={`rd-metric ${absent ? "rd-metric--absent" : ""} ${className}`.trim()} {...rest}>
      <div className="rd-metric__head">
        {icon && <span className="rd-metric__icon">{icon}</span>}
        <span className="rd-metric__label">{label}</span>
      </div>
      <div className="rd-metric__body">
        <span className="rd-metric__value">{absent ? "—" : value}</span>
        {!absent && unit && <span className="rd-metric__unit">{unit}</span>}
        {!absent && delta && (
          <span className={`rd-metric__delta rd-metric__delta--${deltaTone}`}>
            {ARROW[deltaTone]} {delta}
          </span>
        )}
      </div>
      <div className="rd-metric__foot">
        <Freshness status={status} when={when} />
      </div>
    </div>
  );
}
