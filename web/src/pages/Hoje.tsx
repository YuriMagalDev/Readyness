import { useEffect, useState } from "react";
import { fetchToday, fetchAnalysis, regenerateAnalysis, postSync } from "../api";
import type { Today, Analysis } from "../types";
import Semaforo from "../components/Semaforo";
import MetricCard from "../components/MetricCard";
import InsightList from "../components/InsightList";

export default function Hoje() {
  const [today, setToday] = useState<Today | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [erro, setErro] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [regen, setRegen] = useState(false);

  function carregar() {
    setErro("");
    fetchToday().then(setToday).catch((e) => setErro(e.message));
    fetchAnalysis().then(setAnalysis).catch(() => { /* análise degrada graciosamente */ });
  }

  useEffect(() => { carregar(); }, []);

  async function sincronizar() {
    setSyncing(true);
    try { await postSync(); carregar(); }
    catch (e) { setErro((e as Error).message); }
    finally { setSyncing(false); }
  }

  async function regenerar() {
    setRegen(true);
    try { const a = await regenerateAnalysis(); setAnalysis(a); }
    catch (e) { setErro((e as Error).message); }
    finally { setRegen(false); }
  }

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!today) return <div className="page-sub">Carregando…</div>;

  const m = today.metrics;
  const hrDelta = m.resting_hr_today - m.resting_hr_avg_7d;
  // veredito determinístico da análise; cai pro status do /api/today se a análise falhar
  const vered = analysis?.veredito ?? { status: today.status, motivo: today.motivo, recomendacao: today.recomendacao };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div className="page-title">Status do Dia</div>
          <div className="page-sub">Prontidão para treino hoje</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-gen" disabled={syncing} onClick={sincronizar}>
            {syncing ? "Sincronizando…" : "🔄 Sincronizar"}
          </button>
          <button className="btn-gen" disabled={regen} onClick={regenerar}>
            {regen ? "Gerando…" : "💡 Regenerar análise"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 16, alignItems: "start" }}>
        <Semaforo status={vered.status} motivo={vered.motivo} recomendacao={vered.recomendacao} />
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

      <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
        letterSpacing: ".05em", color: "var(--text-faint)", margin: "24px 0 10px" }}>
        💡 Insights — só com o dado disponível
      </div>
      <InsightList insights={analysis?.insights ?? []} />
    </>
  );
}
