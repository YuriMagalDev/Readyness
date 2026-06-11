import { useState } from "react";
import { generatePlan } from "../api";
import type { Plan } from "../types";
import PlanGrid from "../components/PlanGrid";

export default function Plano() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  async function gerar() {
    setLoading(true);
    setErro("");
    try {
      setPlan(await generatePlan());
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="page-title">Plano Semanal</div>
      <div className="page-sub">Duas grades — corrida e musculação podem cair no mesmo dia</div>
      <button className="btn-gen" onClick={gerar} disabled={loading}>
        {loading ? "Gerando com Sonnet…" : "⚡ Gerar novo plano"}
      </button>
      {erro && <div className="banner-erro" style={{ marginTop: 16 }}>{erro}</div>}
      {plan && (
        <div style={{ display: "flex", gap: 24, marginTop: 20 }}>
          <PlanGrid titulo="🏃 Corrida" cor="var(--green)" itens={plan.corrida} />
          <PlanGrid titulo="💪 Musculação" cor="var(--blue)" itens={plan.musculacao} />
        </div>
      )}
    </>
  );
}
