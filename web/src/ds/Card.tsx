import type { HTMLAttributes, ReactNode } from "react";
import { useStyle } from "./useStyle";

const CSS = `
.rd-card {
  background: var(--surface-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.rd-card--raised { background: var(--surface-raised); box-shadow: var(--shadow-md); }
.rd-card--flat { box-shadow: none; }
.rd-card--well {
  background: var(--surface-well);
  box-shadow: var(--shadow-inset);
  border-color: var(--border-card);
  border-style: dashed;
}
.rd-card--p4 { padding: var(--space-4); }
.rd-card--p5 { padding: var(--space-5); }
.rd-card--p6 { padding: var(--space-6); }
.rd-card--p0 { padding: 0; }
`;

export interface CardProps extends HTMLAttributes<HTMLElement> {
  variant?: "default" | "raised" | "flat" | "well";
  padding?: "p0" | "p4" | "p5" | "p6";
  as?: keyof JSX.IntrinsicElements;
  children?: ReactNode;
}

/** Card — superfície de papel. `well` (tracejado/inset) é o lar de dado ausente. */
export function Card({
  variant = "default",
  padding = "p5",
  as: Tag = "div",
  className = "",
  children,
  ...rest
}: CardProps) {
  useStyle("rd-card-css", CSS);
  const cls = `rd-card rd-card--${variant} rd-card--${padding} ${className}`.trim();
  const Comp = Tag as keyof JSX.IntrinsicElements;
  return (
    <Comp className={cls} {...rest}>
      {children}
    </Comp>
  );
}
