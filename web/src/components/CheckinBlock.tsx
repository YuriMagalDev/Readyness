import { useState } from "react";
import type { MetricCell } from "../types";

export default function CheckinBlock({ cells, onSave }: {
  cells: MetricCell[];
  onSave: (payload: Record<string, number>) => Promise<void>;
}) {
  const inicial: Record<string, number> = {};
  cells.forEach((c) => { if (c.value != null) inicial[c.key] = c.value; });
  const [sel, setSel] = useState<Record<string, number>>(inicial);
  const [saving, setSaving] = useState(false);

  async function salvar() {
    setSaving(true);
    try { await onSave(sel); } finally { setSaving(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {cells.map((c) => (
        <div key={c.key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{c.label}</span>
          <div style={{ display: "flex", gap: 4 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} onClick={() => setSel((s) => ({ ...s, [c.key]: n }))}
                style={{ width: 26, height: 26, borderRadius: 6, cursor: "pointer",
                  border: "1px solid var(--border)", fontSize: 12,
                  background: sel[c.key] === n ? "var(--green)" : "var(--surface)",
                  color: sel[c.key] === n ? "#06210f" : "var(--text-dim)" }}>{n}</button>
            ))}
          </div>
        </div>
      ))}
      <button className="btn-gen" disabled={saving} onClick={salvar} style={{ alignSelf: "flex-end" }}>
        {saving ? "Salvando…" : "Salvar check-in"}
      </button>
    </div>
  );
}
