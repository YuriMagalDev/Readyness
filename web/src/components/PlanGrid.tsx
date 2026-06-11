import type { PlanItem } from "../types";

interface Props {
  titulo: string;
  cor: string;
  itens: PlanItem[];
}

export default function PlanGrid({ titulo, cor, itens }: Props) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase",
        letterSpacing: ".05em", color: cor, marginBottom: 10 }}>{titulo}</div>
      {itens.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--text-faint)" }}>Nenhuma sessão.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {itens.map((it, i) => (
            <div key={i} className="card" style={{ borderLeft: `3px solid ${cor}` }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#fff" }}>{it.dia}</span>
                <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{it.duracao} min</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>{it.descricao}</div>
              <div style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 2 }}>{it.intensidade}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
