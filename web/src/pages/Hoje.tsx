import { useEffect, useState } from "react";
import { fetchToday, postSync, regenerateInsights } from "../api";
import type { Today } from "../types";
import Semaforo from "../components/Semaforo";
import MetricCard from "../components/MetricCard";

export default function Hoje() {
  const [data, setData] = useState<Today | null>(null);
  const [erro, setErro] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [regen, setRegen] = useState(false);

  function carregar() {
    return fetchToday().then(setData).catch((e) => setErro(e.message));
  }

  useEffect(() => { carregar(); }, []);

  async function regenerar() {
    setRegen(true);
    setErro("");
    try {
      await regenerateInsights("hoje");
      await carregar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setRegen(false);
    }
  }

  async function sincronizar() {
    setSyncing(true);
    setErro("");
    try {
      await postSync();    // grava o dia no histórico
      await carregar();    // recarrega métricas + parâmetros atualizados
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

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
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-gen" disabled={syncing} onClick={sincronizar}>
            {syncing ? "Sincronizando…" : "🔄 Sincronizar"}
          </button>
          <button className="btn-gen" disabled={regen} onClick={regenerar}>
            {regen ? "Gerando…" : "💡 Regenerar análise"}
          </button>
        </div>
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

      {data.parametros && data.parametros.length > 0 && (
        <>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
            letterSpacing: ".05em", color: "var(--text-faint)", margin: "24px 0 10px" }}>
            Parâmetros · variação vs dia anterior
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            {data.parametros.map((p) => {
              const seta = p.direcao === "subiu" ? "▲" : p.direcao === "desceu" ? "▼" : "—";
              // cor: verde se "bom" true, vermelho se "bom" false, neutro se null
              const cor = p.bom === true ? "var(--green)" : p.bom === false ? "#fca5a5" : "var(--text-dim)";
              return (
                <div key={p.label} className="card">
                  <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{p.icon} {p.label}</div>
                  <div style={{ fontSize: 22, fontWeight: 500, color: "#fff", marginTop: 2 }}>
                    {p.valor}{p.unidade}
                  </div>
                  <div style={{ fontSize: 11, color: cor, marginTop: 4 }}>
                    {p.delta === null
                      ? "sem dia anterior"
                      : `${seta} ${p.delta > 0 ? "+" : ""}${p.delta}${p.unidade} (${p.direcao})`}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
