import { useEffect, useState } from "react";
import { fetchTrends, regenerateInsights } from "../api";
import type { Trends } from "../types";
import { Card, Button } from "../ds";
import Sparkline from "../components/Sparkline";
import { useLucide } from "../lib/useLucide";

const LABELS: Record<string, string> = {
  resting_hr: "FC repouso",
  sleep_hours: "Sono (h)",
  stress_avg: "Stress médio",
  body_battery_high: "Body Battery (pico)",
  intensity_minutes: "Minutos de intensidade",
  race_pred_5k: "Previsão 5k (s)",
};

const DIR_COR: Record<string, string> = {
  subindo: "var(--easy)",
  descendo: "var(--go)",
  estável: "var(--text-faint)",
};

export default function Tendencias() {
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<Trends | null>(null);
  const [erro, setErro] = useState("");
  const [regen, setRegen] = useState(false);

  useLucide([data, regen]);

  useEffect(() => {
    setData(null);
    setErro("");
    fetchTrends(period).then(setData).catch((e) => setErro(e.message));
  }, [period]);

  async function regenerar() {
    setRegen(true);
    setErro("");
    try {
      await regenerateInsights("trends", period);
      setData(null);
      setData(await fetchTrends(period));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setRegen(false);
    }
  }

  return (
    <div className="rk-screen">
      <header className="rk-head">
        <div>
          <h1 className="rk-title">Tendências</h1>
          <div className="rk-head__sub">
            <span className="rk-date">Padrões de saúde e treino + leitura da IA</span>
          </div>
        </div>
        <Button variant="ghost" size="sm" disabled={regen} onClick={regenerar}>
          <i data-lucide="sparkles"></i> {regen ? "Gerando…" : "Regenerar análise"}
        </Button>
      </header>

      <div className="rk-switcher" role="tablist">
        {[7, 30, 90].map((p) => (
          <button
            key={p}
            role="tab"
            aria-selected={p === period}
            className={`rk-switcher__btn ${p === period ? "is-active" : ""}`}
            onClick={() => setPeriod(p)}
          >
            {p}d
          </button>
        ))}
      </div>

      {erro && (
        <div className="rk-banner rk-banner--erro">
          <i data-lucide="triangle-alert"></i>
          <span>{erro}</span>
        </div>
      )}
      {!data && !erro && <div className="rk-loading">Carregando…</div>}

      {data && (
        <>
          <Card>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Insights da IA</div>
            {data.insights.length > 0 ? (
              <div className="rk-stack">
                {data.insights.map((ins, i) => (
                  <div key={i} style={{ fontSize: "var(--text-base)", color: "var(--text-body)" }}>
                    {ins}
                  </div>
                ))}
              </div>
            ) : (
              <span className="rk-faint">Sem insights para este período.</span>
            )}
          </Card>

          <div className="rk-grid-2">
            {Object.entries(data.metrics).map(([key, mt]) => (
              <Card key={key}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span className="rk-faint">{LABELS[key] || key}</span>
                  <span style={{ fontSize: "var(--text-xs)", color: DIR_COR[mt.trend.direction] }}>
                    {mt.trend.direction}
                  </span>
                </div>
                <Sparkline data={mt.series} cor={DIR_COR[mt.trend.direction]} />
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
