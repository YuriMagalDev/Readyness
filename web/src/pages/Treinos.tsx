import { useEffect, useState } from "react";
import { fetchActivities, fetchActivity } from "../api";
import type { ActivitySummary, ActivityDetail } from "../types";

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

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!list) return <div className="page-sub">Carregando…</div>;

  return (
    <>
      <div className="page-title">Treinos</div>
      <div className="page-sub">Últimos 30 dias · clique para detalhes e leitura da IA</div>

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          {list.map((a) => (
            <div key={a.activity_id} className="card" style={{ cursor: "pointer",
              borderLeft: `3px solid ${a.is_strength ? "var(--blue)" : "var(--green)"}` }}
              onClick={() => abrir(a.activity_id)}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, color: "#fff" }}>{a.is_strength ? "💪" : "🏃"} {a.name}</span>
                <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{a.date}</span>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>
                {a.duration_min ? `${a.duration_min} min` : ""}
                {a.pace_min_km ? ` · ${paceLabel(a.pace_min_km)}` : ""}
                {a.avg_hr ? ` · ${a.avg_hr} bpm` : ""}
              </div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }}>
          {loadingDetail && <div className="page-sub">Analisando…</div>}
          {detail && (
            <div className="card">
              <div style={{ fontSize: 14, color: "#fff", marginBottom: 4 }}>{detail.activity.name}</div>
              <div style={{ fontSize: 12, color: "var(--green)", marginBottom: 12 }}>{detail.insight}</div>
              {detail.splits.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 6 }}>Splits por volta</div>
                  {detail.splits.map((s, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between",
                      fontSize: 12, padding: "5px 0", borderBottom: "1px solid #1f1f1f" }}>
                      <span style={{ color: "var(--text-dim)" }}>Km {i + 1}</span>
                      <span style={{ color: "#ccc" }}>{paceLabel(s.pace_min_km)}</span>
                      <span style={{ color: "var(--text-faint)" }}>{s.avg_hr ?? "—"} bpm</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
