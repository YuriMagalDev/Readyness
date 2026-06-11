import { useEffect, useState } from "react";
import { fetchDados } from "../api";
import type { Dados as DadosType } from "../types";
import Sparkline from "../components/Sparkline";

export default function Dados() {
  const [data, setData] = useState<DadosType | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    fetchDados().then(setData).catch((e) => setErro(e.message));
  }, []);

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!data) return <div className="page-sub">Carregando…</div>;

  const ultimo = (s: { valor: number | null }[]) => {
    const v = [...s].reverse().find((p) => p.valor !== null);
    return v?.valor ?? "—";
  };

  return (
    <>
      <div className="page-title">Dados do Garmin</div>
      <div className="page-sub">Tendências de 7 dias e atividades recentes</div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div className="card">
          <div style={{ fontSize: 11, color: "var(--text-faint)" }}>FC repouso — 7d</div>
          <div style={{ fontSize: 18, fontWeight: 500, color: "#fff" }}>{ultimo(data.fc_series)} bpm</div>
          <div style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>{data.fc_trend.label}</div>
          <Sparkline data={data.fc_series} cor="var(--green)" />
        </div>
        <div className="card">
          <div style={{ fontSize: 11, color: "var(--text-faint)" }}>Body Battery — 7d</div>
          <div style={{ fontSize: 18, fontWeight: 500, color: "#fff" }}>{ultimo(data.battery_series)} %</div>
          <div style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>{data.battery_trend.label}</div>
          <Sparkline data={data.battery_series} cor="var(--blue)" />
        </div>
      </div>

      <div className="card">
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
          letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>Atividades recentes</div>
        {data.atividades.map((a, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8,
            padding: "7px 0", borderBottom: i < data.atividades.length - 1 ? "1px solid #1f1f1f" : "none",
            fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%",
              background: a.is_strength ? "var(--blue)" : "var(--green)" }} />
            <span style={{ flex: 1, color: "#ccc" }}>{a.nome}</span>
            <span style={{ color: "var(--text-faint)" }}>{a.data} · {a.duracao} min</span>
          </div>
        ))}
      </div>
    </>
  );
}
