import type { CSSProperties, HTMLAttributes } from "react";
import { useStyle } from "./useStyle";

const CSS = `
.rd-verdict {
  position: relative;
  display: flex; align-items: center; gap: var(--space-8);
  border-radius: var(--radius-2xl);
  padding: var(--space-8) var(--space-8);
  border: 1px solid var(--vd-line);
  background:
    radial-gradient(120% 140% at 0% 0%, color-mix(in oklch, var(--vd-wash) 70%, var(--surface-raised)) 0%, var(--surface-raised) 62%);
  overflow: hidden;
}
.rd-verdict::after {
  content: ""; position: absolute; right: -90px; top: 50%; transform: translateY(-50%);
  width: 360px; height: 360px; border-radius: 999px;
  border: 1px solid var(--vd-line); opacity: 0.5; pointer-events: none;
}
.rd-verdict__light { position: relative; flex: none; width: 132px; height: 132px; display: grid; place-items: center; }
.rd-verdict__ring {
  position: absolute; inset: 0; border-radius: 999px;
  border: 2px solid var(--vd-line);
}
.rd-verdict__ring--core {
  inset: 30px; border: 0; background: var(--vd-core);
  box-shadow: 0 0 0 0 color-mix(in oklch, var(--vd-core) 50%, transparent);
  animation: rd-vd-breathe var(--dur-breathe) var(--ease-in-out) infinite;
}
@keyframes rd-vd-breathe {
  0%, 100% { box-shadow: 0 0 0 0 color-mix(in oklch, var(--vd-core) 45%, transparent); }
  50% { box-shadow: 0 0 0 14px color-mix(in oklch, var(--vd-core) 0%, transparent); }
}
.rd-verdict__body { display: flex; flex-direction: column; gap: var(--space-3); position: relative; z-index: 1; }
.rd-verdict__eyebrow {
  font-family: var(--font-ui); font-size: var(--text-2xs); font-weight: var(--weight-semibold);
  letter-spacing: var(--tracking-eyebrow); text-transform: uppercase; color: var(--text-faint);
  display: flex; align-items: center; gap: var(--space-3);
}
.rd-verdict__word {
  font-family: var(--font-display); font-size: var(--text-verdict); line-height: 0.95;
  letter-spacing: var(--tracking-tight); color: var(--vd-ink); margin: 0;
}
.rd-verdict__reason {
  font-family: var(--font-display); font-style: italic; font-weight: 300;
  font-size: var(--text-h3); color: var(--text-body); max-width: 46ch; line-height: 1.35;
}
.rd-verdict__rec {
  font-family: var(--font-ui); font-size: var(--text-base); color: var(--text-muted);
  display: flex; align-items: center; gap: var(--space-2);
}
.rd-verdict__rec :where(svg) { width: 16px; height: 16px; stroke-width: 1.9; color: var(--vd-ink); }
`;

export type VerdictStatus = "go" | "easy" | "rest";

const TONE: Record<VerdictStatus, { word: string; core: string; ink: string; line: string; wash: string }> = {
  go: { word: "Pode treinar", core: "var(--go)", ink: "var(--go-ink)", line: "var(--go-line)", wash: "var(--go-wash)" },
  easy: { word: "Pegue leve", core: "var(--easy)", ink: "var(--easy-ink)", line: "var(--easy-line)", wash: "var(--easy-wash)" },
  rest: { word: "Descanse", core: "var(--rest)", ink: "var(--rest-ink)", line: "var(--rest-line)", wash: "var(--rest-wash)" },
};

export interface VerdictProps extends HTMLAttributes<HTMLDivElement> {
  status?: VerdictStatus;
  headline?: string;
  reason?: string;
  recommendation?: string;
  date?: string;
}

/** Verdict — o herói da "Hoje". Chamado diário por regra (confiável), renderizado
 *  como luz de prontidão (anel + core que respira) + palavra serifada + a razão. */
export function Verdict({
  status = "go",
  headline,
  reason,
  recommendation,
  date,
  className = "",
  ...rest
}: VerdictProps) {
  useStyle("rd-verdict-css", CSS);
  const t = TONE[status] || TONE.go;
  const style = {
    "--vd-core": t.core,
    "--vd-ink": t.ink,
    "--vd-line": t.line,
    "--vd-wash": t.wash,
  } as CSSProperties;
  return (
    <div className={`rd-verdict ${className}`.trim()} style={style} {...rest}>
      <div className="rd-verdict__light" aria-hidden="true">
        <span className="rd-verdict__ring" />
        <span className="rd-verdict__ring rd-verdict__ring--core" />
      </div>
      <div className="rd-verdict__body">
        <div className="rd-verdict__eyebrow">
          <span>Prontidão de hoje</span>
          {date && <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}>{date}</span>}
        </div>
        <h2 className="rd-verdict__word">{headline || t.word}</h2>
        {reason && <p className="rd-verdict__reason">{reason}</p>}
        {recommendation && (
          <p className="rd-verdict__rec">
            <i data-lucide="arrow-right"></i>
            {recommendation}
          </p>
        )}
      </div>
    </div>
  );
}
