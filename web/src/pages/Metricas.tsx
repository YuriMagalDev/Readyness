import { useEffect, useState } from "react";
import { fetchMetrics } from "../api";
import type { MetricsPayload, MetricCell } from "../types";
import { Freshness } from "../ds";
import { freshOf, whenLabel } from "../lib/ds";
import { fmtMetric } from "../lib/fmt";
import { useLucide } from "../lib/useLucide";

function MetricRow({ cell }: { cell: MetricCell }) {
  const absent = cell.status === "ausente";
  const isTime = cell.unidade === "time";
  const valor = absent ? "—" : isTime ? fmtMetric(cell.value, "time") : (cell.value ?? "—");
  return (
    <div className={`rk-mrow ${absent ? "is-absent" : ""}`}>
      <span className="rk-mrow__label">{cell.label}</span>
      <span className="rk-mrow__val">
        {valor}
        {!absent && !isTime && cell.unidade && <span className="rk-mrow__unit"> {cell.unidade}</span>}
      </span>
      <Freshness
        status={freshOf(cell.status)}
        when={whenLabel(cell.measured_at, cell.status)}
        showLabel={false}
      />
    </div>
  );
}

/** Métricas — o catálogo completo, agrupado por domínio. Onde tudo que não é
 *  métrica-chave mora, pra "Hoje" ficar calma. Frescor por célula, sempre. */
export default function Metricas() {
  const [data, setData] = useState<MetricsPayload | null>(null);
  const [erro, setErro] = useState("");
  const [hideAbsent, setHideAbsent] = useState(false);

  useLucide([data, hideAbsent]);

  useEffect(() => {
    fetchMetrics()
      .then(setData)
      .catch((e) => setErro(e.message));
  }, []);

  if (erro) return <div className="rk-screen"><div className="rk-banner rk-banner--erro"><i data-lucide="triangle-alert"></i><span>{erro}</span></div></div>;
  if (!data) return <div className="rk-screen"><div className="rk-loading">Carregando…</div></div>;

  const dominios = Object.entries(data.dominios);
  const total = dominios.reduce((n, [, cells]) => n + cells.length, 0);

  return (
    <div className="rk-screen">
      <header className="rk-head">
        <div>
          <h1 className="rk-title">Todas as métricas</h1>
          <div className="rk-head__sub">
            <span className="rk-date">{total} métricas · catálogo curado</span>
          </div>
        </div>
        <button className="rk-link" onClick={() => setHideAbsent((v) => !v)}>
          <i data-lucide={hideAbsent ? "eye" : "eye-off"}></i>
          {hideAbsent ? "Mostrar ausentes" : "Esconder ausentes"}
        </button>
      </header>

      <div className="rk-mgroups">
        {dominios.map(([dominio, cells]) => {
          const rows = hideAbsent ? cells.filter((c) => c.status !== "ausente") : cells;
          if (rows.length === 0) return null;
          return (
            <section key={dominio}>
              <div className="eyebrow rk-mgroup__title">{dominio}</div>
              <div className="rk-mgroup__list">
                {rows.map((c) => (
                  <MetricRow key={c.key} cell={c} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
