import { useEffect, useState } from "react";
import { fetchMetrics, fetchAnalysis, regenerateAnalysis, postCheckin, postSync } from "../api";
import type { MetricsPayload, Analysis } from "../types";
import Semaforo from "../components/Semaforo";
import InsightList from "../components/InsightList";
import DomainGrid from "../components/DomainGrid";
import CheckinBlock from "../components/CheckinBlock";

export default function Hoje() {
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [erro, setErro] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [regen, setRegen] = useState(false);

  function carregar() {
    setErro("");
    fetchMetrics().then(setMetrics).catch((e) => setErro(e.message));
    fetchAnalysis().then(setAnalysis).catch(() => { /* análise é degradação graciosa */ });
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

  async function salvarCheckin(payload: Record<string, number>) {
    await postCheckin(payload);
    carregar();
  }

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!metrics) return <div className="page-sub">Carregando…</div>;

  const checkinCells = metrics.dominios["checkin"] || [];

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

      <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 360px) 1fr", gap: 20, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {analysis && (
            <Semaforo status={analysis.veredito.status}
              motivo={analysis.veredito.motivo}
              recomendacao={analysis.veredito.recomendacao} />
          )}
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
            letterSpacing: ".05em", color: "var(--text-faint)" }}>Insights</div>
          <InsightList insights={analysis?.insights ?? []} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <DomainGrid metrics={metrics} />
          {checkinCells.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
                letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>Check-in</div>
              <div className="card" style={{ padding: "12px 14px" }}>
                <CheckinBlock cells={checkinCells} onSave={salvarCheckin} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
