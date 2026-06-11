interface Props {
  status: "verde" | "amarelo" | "vermelho";
  motivo: string;
  recomendacao: string;
}

const CFG = {
  verde: { emoji: "🟢", label: "Verde", color: "var(--green)" },
  amarelo: { emoji: "🟡", label: "Amarelo", color: "var(--amber)" },
  vermelho: { emoji: "🔴", label: "Vermelho", color: "var(--red)" },
};

export default function Semaforo({ status, motivo, recomendacao }: Props) {
  const c = CFG[status];
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column",
      alignItems: "center", gap: 10, textAlign: "center" }}>
      <div style={{ fontSize: 40 }}>{c.emoji}</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: c.color }}>{c.label}</div>
      <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{motivo}</div>
      <div style={{ fontSize: 12, color: "var(--text-faint)", borderTop: "1px solid var(--border)",
        paddingTop: 10, marginTop: 4 }}>{recomendacao}</div>
    </div>
  );
}
