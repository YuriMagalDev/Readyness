import { useEffect, useState } from "react";
import { generatePlan, fetchPlanStatus } from "../api";
import type { PlanStatus, PlanSessionStatus } from "../types";
import { Card, Badge, Button } from "../ds";
import type { BadgeTone } from "../ds/Badge";
import { useLucide } from "../lib/useLucide";

const BADGE: Record<string, { txt: string; tone: BadgeTone }> = {
  feito: { txt: "feito", tone: "go" },
  pendente: { txt: "pendente", tone: "neutral" },
  furou: { txt: "furou", tone: "rest" },
};

function StatusGrid({ titulo, itens }: { titulo: string; itens: PlanSessionStatus[] }) {
  return (
    <div style={{ flex: 1 }}>
      <div className="eyebrow" style={{ marginBottom: 10 }}>{titulo}</div>
      {itens.length === 0 ? (
        <div className="rk-faint">Nenhuma sessão.</div>
      ) : (
        <div className="rk-stack">
          {itens.map((it, i) => {
            const b = BADGE[it.status] || BADGE.pendente;
            return (
              <Card key={i} padding="p4">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: "var(--weight-semibold)", color: "var(--text-strong)" }}>{it.dia}</span>
                  <Badge tone={b.tone} dot>{b.txt}</Badge>
                </div>
                <div className="rk-muted" style={{ marginTop: 4, color: "var(--text-body)" }}>{it.descricao}</div>
                <div className="rk-faint" style={{ marginTop: 2 }}>
                  {it.duracao} min · {it.intensidade}
                </div>
              </Card>
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

  useLucide([status, loading]);

  function carregar() {
    fetchPlanStatus().then(setStatus).catch((e) => setErro(e.message));
  }

  useEffect(carregar, []);

  async function gerar() {
    setLoading(true);
    setErro("");
    try {
      await generatePlan();
      carregar();
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
    : plan?.corrida.map((s) => ({ ...s, date: "", status: "pendente" as const })) ?? [];
  const musculacao: PlanSessionStatus[] = match
    ? match.musculacao
    : plan?.musculacao.map((s) => ({ ...s, date: "", status: "pendente" as const })) ?? [];

  return (
    <div className="rk-screen">
      <header className="rk-head">
        <div>
          <h1 className="rk-title">Plano semanal</h1>
          <div className="rk-head__sub">
            <span className="rk-date">Salvo e cruzado com seus treinos reais</span>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={gerar} disabled={loading}>
          <i data-lucide="zap"></i> {loading ? "Gerando…" : plan ? "Regerar plano" : "Gerar plano"}
        </Button>
      </header>

      {erro && (
        <div className="rk-banner rk-banner--erro">
          <i data-lucide="triangle-alert"></i>
          <span>{erro}</span>
        </div>
      )}

      {!plan && !erro && (
        <div className="rk-faint">Nenhum plano salvo para esta semana. Clique em gerar.</div>
      )}

      {plan && (
        <div className="rk-row-2">
          <StatusGrid titulo="Corrida" itens={corrida} />
          <StatusGrid titulo="Musculação" itens={musculacao} />
        </div>
      )}
    </div>
  );
}
