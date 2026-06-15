import { useEffect, useState } from "react";
import { fetchActivities, fetchActivity } from "../api";
import type { ActivitySummary, ActivityDetail } from "../types";
import { Card } from "../ds";
import { useLucide } from "../lib/useLucide";

function paceLabel(pace: number | null): string {
  if (!pace) return "—";
  const m = Math.floor(pace);
  const s = Math.round((pace - m) * 60);
  return `${m}:${String(s).padStart(2, "0")}/km`;
}

export default function Treinos() {
  const [list, setList] = useState<ActivitySummary[] | null>(null);
  const [erro, setErro] = useState("");
  const [detail, setDetail] = useState<ActivityDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useLucide([list, detail]);

  useEffect(() => {
    fetchActivities(30).then(setList).catch((e) => setErro(e.message));
  }, []);

  async function abrir(id: number) {
    setLoadingDetail(true);
    setDetail(null);
    try {
      setDetail(await fetchActivity(id));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setLoadingDetail(false);
    }
  }

  if (erro) return <div className="rk-screen"><div className="rk-banner rk-banner--erro"><i data-lucide="triangle-alert"></i><span>{erro}</span></div></div>;
  if (!list) return <div className="rk-screen"><div className="rk-loading">Carregando…</div></div>;

  return (
    <div className="rk-screen">
      <header className="rk-head">
        <div>
          <h1 className="rk-title">Treinos</h1>
          <div className="rk-head__sub">
            <span className="rk-date">Últimos 30 dias · clique para detalhes e leitura da IA</span>
          </div>
        </div>
      </header>

      <div className="rk-row-2">
        <div className="rk-stack" style={{ flex: 1 }}>
          {list.map((a) => (
            <Card
              key={a.activity_id}
              padding="p4"
              style={{ cursor: "pointer" }}
              onClick={() => abrir(a.activity_id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "var(--text-strong)" }}>
                  <i data-lucide={a.is_strength ? "dumbbell" : "footprints"} style={{ width: 16, height: 16 }}></i>
                  {a.name}
                </span>
                <span className="rk-faint">{a.date}</span>
              </div>
              <div className="rk-muted" style={{ marginTop: 4 }}>
                {a.duration_min ? `${a.duration_min} min` : ""}
                {a.pace_min_km ? ` · ${paceLabel(a.pace_min_km)}` : ""}
                {a.avg_hr ? ` · ${a.avg_hr} bpm` : ""}
              </div>
            </Card>
          ))}
        </div>

        <div style={{ flex: 1 }}>
          {loadingDetail && <div className="rk-loading">Analisando…</div>}
          {detail && (
            <Card>
              <div style={{ fontSize: "var(--text-h3)", fontFamily: "var(--font-display)", color: "var(--text-strong)", marginBottom: 4 }}>
                {detail.activity.name}
              </div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--go-ink)", marginBottom: 12, fontStyle: "italic", fontFamily: "var(--font-display)" }}>
                {detail.insight}
              </div>
              {detail.splits.length > 0 && (
                <div>
                  <div className="eyebrow" style={{ marginBottom: 6 }}>Splits por volta</div>
                  {detail.splits.map((s, i) => (
                    <div
                      key={i}
                      style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border-faint)", fontSize: "var(--text-sm)" }}
                    >
                      <span className="rk-muted">Km {i + 1}</span>
                      <span className="rk-num">{paceLabel(s.pace_min_km)}</span>
                      <span className="rk-faint">{s.avg_hr ?? "—"} bpm</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
