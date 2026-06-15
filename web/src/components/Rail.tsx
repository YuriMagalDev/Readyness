import { useLucide } from "../lib/useLucide";
import type { VerdictStatus } from "../ds";

export type Route = "hoje" | "metricas" | "checkin" | "tendencias" | "treinos" | "plano";

interface Props {
  active: Route;
  onNavigate: (r: Route) => void;
  verdict?: VerdictStatus;
}

const ITEMS: { id: Route; icon: string; label: string }[] = [
  { id: "hoje", icon: "sun", label: "Hoje" },
  { id: "metricas", icon: "layout-grid", label: "Métricas" },
  { id: "checkin", icon: "clipboard-pen", label: "Check-in" },
  { id: "tendencias", icon: "trending-up", label: "Tendências" },
  { id: "treinos", icon: "footprints", label: "Treinos" },
  { id: "plano", icon: "calendar", label: "Plano" },
];

const VERDICT_COLOR: Record<VerdictStatus, string> = {
  go: "var(--go)",
  easy: "var(--easy)",
  rest: "var(--rest)",
};

/** Rail — navegação esquerda fina. App de um usuário só: sem conta, só as
 *  superfícies do dia. A marca = anel + core que pulsa na cor do veredito. */
export default function Rail({ active, onNavigate, verdict = "go" }: Props) {
  useLucide(active);
  return (
    <nav className="rk-rail">
      <div className="rk-rail__mark" title="readiness">
        <span className="rk-rail__ring" />
        <span className="rk-rail__core" style={{ background: VERDICT_COLOR[verdict] }} />
      </div>
      <div className="rk-rail__items">
        {ITEMS.map((it) => (
          <button
            key={it.id}
            className={`rk-rail__btn ${active === it.id ? "is-active" : ""}`}
            onClick={() => onNavigate(it.id)}
            title={it.label}
            aria-label={it.label}
          >
            <i data-lucide={it.icon}></i>
          </button>
        ))}
      </div>
      <button className="rk-rail__btn rk-rail__settings" title="Ajustes" aria-label="Ajustes">
        <i data-lucide="settings"></i>
      </button>
    </nav>
  );
}
