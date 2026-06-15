import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useStyle } from "./useStyle";

const CSS = `
.rd-btn {
  font-family: var(--font-ui);
  font-weight: var(--weight-semibold);
  display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2);
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out),
              border-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
  line-height: 1;
}
.rd-btn:active { transform: translateY(1px); }
.rd-btn[disabled] { cursor: not-allowed; opacity: 0.45; transform: none; }
.rd-btn :where(svg) { width: 1.05em; height: 1.05em; stroke-width: 1.9; }
.rd-btn--sm { font-size: var(--text-sm); padding: 7px 13px; }
.rd-btn--md { font-size: var(--text-base); padding: 10px 18px; }
.rd-btn--primary { background: var(--action); color: var(--action-text); }
.rd-btn--primary:hover:not([disabled]) { background: var(--action-hover); }
.rd-btn--secondary { background: var(--surface-raised); color: var(--text-strong); border-color: var(--border-divider); }
.rd-btn--secondary:hover:not([disabled]) { background: var(--surface-well); border-color: var(--ink-3); }
.rd-btn--ghost { background: transparent; color: var(--text-muted); }
.rd-btn--ghost:hover:not([disabled]) { background: var(--surface-well); color: var(--text-strong); }
`;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
  children?: ReactNode;
}

/** Button — ação primária ink, secundária hairline, ghost discreta. */
export function Button({
  variant = "primary",
  size = "md",
  type = "button",
  className = "",
  children,
  ...rest
}: ButtonProps) {
  useStyle("rd-button-css", CSS);
  const cls = `rd-btn rd-btn--${variant} rd-btn--${size} ${className}`.trim();
  return (
    <button type={type} className={cls} {...rest}>
      {children}
    </button>
  );
}
