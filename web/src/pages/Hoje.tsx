import { useEffect, useState } from "react";
import { fetchToday, fetchAnalysis, fetchMetrics, regenerateAnalysis, postSync } from "../api";
import type { Today, Analysis, MetricsPayload, MetricCell } from "../types";
import { Verdict, MetricCard, Insight, Button } from "../ds";
import { verdictTone, freshOf, whenLabel } from "../lib/ds";
import { useLucide } from "../lib/useLucide";
import type { VerdictStatus } from "../ds";

const DATE_FMT = new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "short" });

interface Props {
  onVerdict?: (v: VerdictStatus) => void;
}

export default function Hoje({ onVerdict }: Props) {
  const [today, setToday] = useState<Today | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [aiOffline, setAiOffline] = useState(false);
  const [metricIndex, setMetricIndex] = useState<Map<string, MetricCell>>(new Map());
  const [erro, setErro] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [regen, setRegen] = useState(false);

  useLucide([today, analysis, aiOffline]);

  function carregar() {
    setErro("");
    fetchToday()
      .then((t) => {
        setToday(t);
        onVerdict?.(verdictTone(t.status));
      })
      .catch((e) => setErro(e.message));
    fetchAnalysis()
      .then((a) => {
        setAnalysis(a);
        setAiOffline(false);
        onVerdict?.(verdictTone(a.veredito.status));
      })
      .catch(() => {
        setAnalysis(null);
        setAiOffline(true); // análise degrada graciosamente; veredito continua via /api/today
      });
    fetchMetrics()
      .then((m: MetricsPayload) => {
        const idx = new Map<string, MetricCell>();
        Object.values(m.dominios).forEach((cells) => cells.forEach((c) => idx.set(c.key, c)));
        setMetricIndex(idx);
      })
      .catch(() => setMetricIndex(new Map()));
  }

  useEffect(carregar, []);

  async function sincronizar() {
    setSyncing(true);
    try {
      await postSync();
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  async function regenerar() {
    setRegen(true);
    try {
      const a = await regenerateAnalysis();
      setAnalysis(a);
      setAiOffline(false);
      onVerdict?.(verdictTone(a.veredito.status));
    } catch {
      setAiOffline(true);
    } finally {
      setRegen(false);
    }
  }

  // frescor por métrica vindo de /api/metrics (fonte da verdade do "de quando é")
  function fresh(key: string): { status: ReturnType<typeof freshOf>; when: string } {
    const cell = metricIndex.get(key);
    if (!cell) return { status: "fresh", when: "hoje" };
    return { status: freshOf(cell.status), when: whenLabel(cell.measured_at, cell.status) };
  }

  if (erro && !today) return <div className="rk-screen"><div className="rk-banner rk-banner--erro"><i data-lucide="triangle-alert"></i><span>{erro}</span></div></div>;
  if (!today) return <div className="rk-screen"><div className="rk-loading">Carregando…</div></div>;

  const m = today.metrics;
  const hrDelta = m.resting_hr_today - m.resting_hr_avg_7d;
  // veredito determinístico: da análise se houver, senão do /api/today (regra)
  const vered = analysis?.veredito ?? { status: today.status, motivo: today.motivo, recomendacao: today.recomendacao };

  const fcF = fresh("resting_hr");
  const bbF = fresh("body_battery_high");
  const slF = fresh("sleep_hours");

  return (
    <div className="rk-screen">
      <header className="rk-head">
        <div>
          <div className="rk-greeting">Bom dia.</div>
          <div className="rk-head__sub">
            <span className="rk-date">{DATE_FMT.format(new Date())}</span>
          </div>
        </div>
        <div className="rk-actions">
          <Button variant="secondary" size="sm" disabled={syncing} onClick={sincronizar}>
            <i data-lucide="refresh-cw"></i> {syncing ? "Sincronizando…" : "Sincronizar"}
          </Button>
          <Button variant="ghost" size="sm" disabled={regen} onClick={regenerar}>
            <i data-lucide="sparkles"></i> {regen ? "Gerando…" : "Regenerar análise"}
          </Button>
        </div>
      </header>

      {erro && (
        <div className="rk-banner rk-banner--erro">
          <i data-lucide="triangle-alert"></i>
          <span>{erro}</span>
        </div>
      )}

      <Verdict
        status={verdictTone(vered.status)}
        date={DATE_FMT.format(new Date())}
        reason={vered.motivo}
        recommendation={vered.recomendacao}
      />

      <section>
        <div className="rk-seclabel">
          <span className="eyebrow">Métricas-chave</span>
          <span className="rk-from-ai">
            <i data-lucide="layout-grid"></i> ver todas as métricas
          </span>
        </div>
        <div className="rk-metrics">
          <MetricCard
            icon={<i data-lucide="heart-pulse"></i>}
            label="FC repouso vs 7d"
            value={m.resting_hr_today}
            unit="bpm"
            delta={hrDelta === 0 ? "= média" : `${Math.abs(hrDelta).toFixed(1)} bpm`}
            deltaTone={hrDelta >= 5 ? "up" : hrDelta <= -1 ? "down" : "flat"}
            status={fcF.status}
            when={fcF.when}
          />
          <MetricCard
            icon={<i data-lucide="battery-low"></i>}
            label="Body Battery matinal"
            value={m.morning_battery_avg}
            unit="/100"
            delta={m.morning_battery_avg < 25 ? "baixa" : "ok"}
            deltaTone={m.morning_battery_avg < 25 ? "up" : "flat"}
            status={bbF.status}
            when={bbF.when}
          />
          <MetricCard
            icon={<i data-lucide="moon"></i>}
            label="Dívida de sono semanal"
            value={m.sleep_debt_hours}
            unit="h"
            delta={m.sleep_debt_hours >= 2 ? "acima do limite" : "sob controle"}
            deltaTone={m.sleep_debt_hours >= 2 ? "up" : "flat"}
            status={slF.status}
            when={slF.when}
          />
          <MetricCard
            icon={<i data-lucide="footprints"></i>}
            label="Corridas esta semana"
            value={m.run_sessions_7d}
            unit="sessões"
            delta={m.run_sessions_7d >= 3 ? "mínimo atingido" : "abaixo de 3"}
            deltaTone="flat"
            status="fresh"
            when="7 dias"
          />
        </div>
      </section>

      <section>
        <div className="rk-seclabel">
          <span className="eyebrow">Insights de hoje</span>
          <span className="rk-from-ai">
            <i data-lucide="sparkles"></i> IA local
          </span>
        </div>
        <div className="rk-insights">
          {aiOffline ? (
            <Insight variant="unavailable" />
          ) : analysis && analysis.insights.length > 0 ? (
            analysis.insights.map((ins, i) => (
              <Insight
                key={i}
                text={ins.texto}
                sources={ins.metricas_usadas.map((s) => ({
                  label: s.label,
                  value: s.valor != null ? `${s.valor}${s.unidade ? " " + s.unidade : ""}` : "—",
                  status: freshOf(s.status),
                }))}
              />
            ))
          ) : (
            <span className="rk-insights--empty">Sem insights hoje.</span>
          )}
        </div>
      </section>
    </div>
  );
}
