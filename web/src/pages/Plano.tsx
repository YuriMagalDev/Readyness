import { useEffect, useState } from "react";
import { generatePlan, fetchPlanStatus } from "../api";
import type { PlanStatus, PlanSessionStatus } from "../types";

const BADGE: Record<string, { txt: string; cor: string; bg: string }> = {
  feito: { txt: "✓ feito", cor: "var(--green)", bg: "var(--green-bg)" },
  pendente: { txt: "⏳ pendente", cor: "var(--text-dim)", bg: "var(--surface)" },
  furou: { txt: "✗ furou", cor: "#fca5a5", bg: "#3a1212" },
};

function StatusGrid({ titulo, cor, itens }: { titulo: string; cor: string; itens: PlanSessionStatus[] }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase",
        letterSpacing: ".05em", color: cor, marginBottom: 10 }}>{titulo}</div>
      {itens.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--text-faint)" }}>Nenhuma sessão.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {itens.map((it, i) => {
            const b = BADGE[it.status] || BADGE.pendente;
            return (
              <div key={i} className="card" style={{ borderLeft: `3px solid ${cor}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: "#fff" }}>{it.dia}</span>
                  <span style={{ fontSize: 10, color: b.cor, background: b.bg,
                    padding: "2px 8px", borderRadius: 6 }}>{b.txt}</span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>{it.descricao}</div>
                <div style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 2 }}>
                  {it.duracao} min · {it.intensidade}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Plano() {
  const [status, setStatus] = useState<PlanStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  function carregar() {
    fetchPlanStatus().then(setStatus).catch((e) => setErro(e.message));
  }

  useEffect(() => { carregar(); }, []);

  async function gerar() {
    setLoading(true);
    setErro("");
    try {
      await generatePlan();
      carregar();  // recarrega plano salvo + cruzamento
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const match = status?.match;
  const plan = status?.plan;
  const corrida: PlanSessionStatus[] = match
    ? match.corrida
    : (plan?.corrida.map((s) => ({ ...s, date: "", status: "pendente" as const })) ?? []);
  const musculacao: PlanSessionStatus[] = match
    ? match.musculacao
    : (plan?.musculacao.map((s) => ({ ...s, date: "", status: "pendente" as const })) ?? []);

  return (
    <>
      <div className="page-title">Plano Semanal</div>
      <div className="page-sub">
        Salvo e cruzado com seus treinos reais · corrida e musculação podem cair no mesmo dia
      </div>
      <button className="btn-gen" onClick={gerar} disabled={loading}>
        {loading ? "Gerando com Sonnet…" : plan ? "⚡ Regerar plano" : "⚡ Gerar plano"}
      </button>
      {erro && <div className="banner-erro" style={{ marginTop: 16 }}>{erro}</div>}

      {!plan && !erro && (
        <div className="page-sub" style={{ marginTop: 16 }}>
          Nenhum plano salvo para esta semana. Clique em gerar.
        </div>
      )}

      {plan && (
        <div style={{ display: "flex", gap: 24, marginTop: 20 }}>
          <StatusGrid titulo="🏃 Corrida" cor="var(--green)" itens={corrida} />
          <StatusGrid titulo="💪 Musculação" cor="var(--blue)" itens={musculacao} />
        </div>
      )}
    </>
  );
}
