import { useEffect, useState } from "react";
import { fetchToday, postSync } from "../api";
import type { Today } from "../types";
import Semaforo from "../components/Semaforo";
import MetricCard from "../components/MetricCard";

export default function Hoje() {
  const [data, setData] = useState<Today | null>(null);
  const [erro, setErro] = useState("");
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchToday().then(setData).catch((e) => setErro(e.message));
  }, []);

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!data) return <div className="page-sub">Carregando…</div>;

  const m = data.metrics;
  const hrDelta = m.resting_hr_today - m.resting_hr_avg_7d;
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="page-title">Status do Dia</div>
          <div className="page-sub">Prontidão para treino hoje</div>
        </div>
        <button className="btn-gen" disabled={syncing}
          onClick={async () => { setSyncing(true); try { await postSync(); } finally { setSyncing(false); } }}>
          {syncing ? "Sincronizando…" : "🔄 Sincronizar"}
        </button>
      </div>
      {data.daily_insight && (
        <div className="card" style={{ marginBottom: 16, borderLeft: "3px solid var(--green)" }}>
          <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 4 }}>💡 Insight do dia</div>
          <div style={{ fontSize: 13, color: "var(--text)" }}>{data.daily_insight}</div>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 16, alignItems: "start" }}>
        <Semaforo status={data.status} motivo={data.motivo} recomendacao={data.recomendacao} />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <MetricCard icon="❤" label="FC repouso hoje vs média 7d"
            value={`${m.resting_hr_today} bpm`}
            delta={hrDelta === 0 ? "= média" : `${hrDelta > 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm`}
            deltaWarn={hrDelta >= 5} />
          <MetricCard icon="⚡" label="Body Battery matinal"
            value={`${m.morning_battery_avg}`}
            delta={m.morning_battery_avg < 25 ? "abaixo do limite" : "ok"}
            deltaWarn={m.morning_battery_avg < 25} />
          <MetricCard icon="🌙" label="Dívida de sono semanal"
            value={`${m.sleep_debt_hours}h`}
            delta={m.sleep_debt_hours >= 2 ? "acima do limite" : "abaixo do limite (2h)"}
            deltaWarn={m.sleep_debt_hours >= 2} />
          <MetricCard icon="🏃" label="Corridas esta semana"
            value={`${m.run_sessions_7d} sessões`}
            delta={m.run_sessions_7d >= 3 ? "mínimo atingido" : "abaixo de 3"}
            deltaWarn={m.run_sessions_7d < 3} />
        </div>
      </div>
    </>
  );
}
