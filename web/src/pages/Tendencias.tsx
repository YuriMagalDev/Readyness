import { useEffect, useState } from "react";
import { fetchTrends, regenerateInsights } from "../api";
import type { Trends } from "../types";
import Sparkline from "../components/Sparkline";

const LABELS: Record<string, string> = {
  resting_hr: "FC repouso",
  sleep_hours: "Sono (h)",
  stress_avg: "Stress médio",
  body_battery_high: "Body Battery (pico)",
  intensity_minutes: "Minutos de intensidade",
  race_pred_5k: "Previsão 5k (s)",
};

const DIR_COR: Record<string, string> = {
  subindo: "var(--amber)", descendo: "var(--green)", estável: "var(--text-dim)",
};

export default function Tendencias() {
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<Trends | null>(null);
  const [erro, setErro] = useState("");
  const [regen, setRegen] = useState(false);

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
      const fresh = await fetchTrends(period);
      setData(fresh);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setRegen(false);
    }
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <div>
          <div className="page-title">Tendências</div>
          <div className="page-sub">Padrões de saúde e treino + leitura da IA</div>
        </div>
        <button className="btn-gen" disabled={regen} onClick={regenerar}>
          {regen ? "Gerando…" : "💡 Regenerar análise"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {[7, 30, 90].map((p) => (
          <button key={p} className="nav-item" style={{ width: "auto", borderRadius: 8,
            background: p === period ? "#222" : "var(--surface)", color: p === period ? "#fff" : "var(--text-dim)" }}
            onClick={() => setPeriod(p)}>{p}d</button>
        ))}
      </div>

      {erro && <div className="banner-erro">{erro}</div>}
      {!data && !erro && <div className="page-sub">Carregando…</div>}

      {data && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
              letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>Insights da IA</div>
            {data.insights.map((ins, i) => (
              <div key={i} style={{ fontSize: 13, color: "var(--text)", marginBottom: 6 }}>• {ins}</div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {Object.entries(data.metrics).map(([key, m]) => (
              <div key={key} className="card">
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{LABELS[key] || key}</span>
                  <span style={{ fontSize: 10, color: DIR_COR[m.trend.direction] }}>{m.trend.direction}</span>
                </div>
                <Sparkline data={m.series} cor={DIR_COR[m.trend.direction]} />
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
