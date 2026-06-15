import type { HTMLAttributes, ReactNode } from "react";
import { useStyle } from "./useStyle";

const CSS = `
.rd-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-ui);
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  letter-spacing: 0.02em;
  padding: 3px 9px;
  border-radius: var(--radius-pill);
  border: 1px solid transparent;
  line-height: 1.3;
  white-space: nowrap;
}
.rd-badge--neutral { background: var(--surface-well); color: var(--text-muted); border-color: var(--border-card); }
.rd-badge--go { background: var(--go-wash); color: var(--go-ink); border-color: var(--go-line); }
.rd-badge--easy { background: var(--easy-wash); color: var(--easy-ink); border-color: var(--easy-line); }
.rd-badge--rest { background: var(--rest-wash); color: var(--rest-ink); border-color: var(--rest-line); }
.rd-badge--estimated { background: var(--estimated-wash); color: var(--estimated); border-color: color-mix(in oklch, var(--estimated) 28%, transparent); }
.rd-badge__dot { width: 6px; height: 6px; border-radius: 999px; background: currentColor; }
`;

export type BadgeTone = "neutral" | "go" | "easy" | "rest" | "estimated";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
  children?: ReactNode;
}

/** Badge — pílula pequena. Tons mapeiam a semântica do veredito + neutral/estimated. */
export function Badge({ tone = "neutral", dot = false, className = "", children, ...rest }: BadgeProps) {
  useStyle("rd-badge-css", CSS);
  const cls = `rd-badge rd-badge--${tone} ${className}`.trim();
  return (
    <span className={cls} {...rest}>
      {dot && <span className="rd-badge__dot" />}
      {children}
    </span>
  );
}
