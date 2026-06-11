interface Props {
  icon: string;
  label: string;
  value: string;
  delta?: string;
  deltaWarn?: boolean;
}

export default function MetricCard({ icon, label, value, delta, deltaWarn }: Props) {
  return (
    <div className="card" style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, display: "flex",
        alignItems: "center", justifyContent: "center", fontSize: 18,
        background: "var(--surface)", border: "1px solid var(--border)" }}>{icon}</div>
      <div>
        <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{label}</div>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#fff" }}>
          {value}
          {delta && (
            <span style={{ fontSize: 11, marginLeft: 6,
              color: deltaWarn ? "var(--amber)" : "var(--green)" }}>{delta}</span>
          )}
        </div>
      </div>
    </div>
  );
}
