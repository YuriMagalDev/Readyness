# UI Nova "Hoje" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reescrever a tela "Hoje" em layout 2 colunas (desktop) — veredito + insights rastreáveis à esquerda, métricas por domínio com frescor à direita, e check-in manual — consumindo `/api/metrics` e `/api/analysis`.

**Architecture:** React/TypeScript (Vite). Componentes de apresentação pequenos e focados (`FreshnessBadge`, `MetricChip`, `DomainGrid`, `InsightList`, `CheckinBlock`) compostos pela página `Hoje.tsx`. Dados via `api.ts` (fetch dos dois endpoints em paralelo). **Sem framework de teste de frontend** — verificação por `npm run build` (TypeScript compila e pega erros de tipo) a cada task.

**Tech Stack:** React 18, TypeScript, Vite. Tema escuro com CSS vars existentes (`--green`, `--amber`, `--red`, `--text-faint`, `--text-dim`, `--border`, `--surface`, classes `card`/`btn-gen`).

**Nota sobre verificação:** o projeto não tem Vitest/Jest. Cada task termina com `cd web; npm run build` que deve passar sem erro TS. A verificação visual final (screenshots) é feita ao fim, no preview.

---

### Task 1: Tipos da Camada 4 em `types.ts`

**Files:**
- Modify: `web/src/types.ts`

- [ ] **Step 1: Add types**

Append to `web/src/types.ts`:

```typescript
export type MetricStatus = "fresco" | "velho" | "ausente" | "estimado";

export interface MetricCell {
  key: string;
  label: string;
  value: number | null;
  unidade: string;
  measured_at: string | null;
  status: MetricStatus;
  source: string;
}

export interface MetricsPayload {
  date: string;
  dominios: Record<string, MetricCell[]>;
}

export interface InsightSource {
  key: string;
  label: string;
  valor: number | null;
  unidade: string;
  status: MetricStatus;
}

export interface Insight {
  texto: string;
  metricas_usadas: InsightSource[];
}

export interface Analysis {
  date: string;
  veredito: { semaforo: "verde" | "amarelo" | "vermelho"; motivo: string; recomendacao: string };
  insights: Insight[];
}
```

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success, no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/types.ts
git commit -m "feat(ui): types for metrics + analysis payloads"
```

---

### Task 2: Funções de API em `api.ts`

**Files:**
- Modify: `web/src/api.ts`

- [ ] **Step 1: Add API helpers**

Append to `web/src/api.ts` (the file already has a generic `get<T>(url)` helper and the error pattern `body.erro || \`Erro ${resp.status}\``):

```typescript
import type { MetricsPayload, Analysis } from "./types";

export const fetchMetrics = (date?: string) =>
  get<MetricsPayload>(`/api/metrics${date ? `?date=${date}` : ""}`);

export const fetchAnalysis = (date?: string) =>
  get<Analysis>(`/api/analysis${date ? `?date=${date}` : ""}`);

export async function regenerateAnalysis(date?: string): Promise<Analysis> {
  const resp = await fetch("/api/analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export async function postCheckin(payload: Record<string, number>): Promise<{ ok: boolean }> {
  const resp = await fetch("/api/checkin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}
```

If `types.ts` import lines already exist at the top of `api.ts`, merge the `MetricsPayload, Analysis` names into the existing import instead of adding a duplicate import line.

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add web/src/api.ts
git commit -m "feat(ui): api helpers fetchMetrics/fetchAnalysis/regenerateAnalysis/postCheckin"
```

---

### Task 3: `FreshnessBadge` + helper de formatação

**Files:**
- Create: `web/src/components/FreshnessBadge.tsx`
- Create: `web/src/lib/fmt.ts`

- [ ] **Step 1: Create the format helper**

Create `web/src/lib/fmt.ts`:

```typescript
// Formata valor de métrica. unidade === "time" → segundos em [h:]mm:ss.
export function fmtMetric(value: number | null, unidade: string): string {
  if (value === null || value === undefined) return "—";
  if (unidade === "time") {
    const secs = Math.round(value);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    if (m >= 60) {
      const h = Math.floor(m / 60);
      return `${h}:${String(m % 60).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${m}:${String(s).padStart(2, "0")}`;
  }
  const num = Number.isInteger(value) ? value : Math.round(value * 10) / 10;
  return `${num}${unidade}`;
}
```

- [ ] **Step 2: Create FreshnessBadge**

Create `web/src/components/FreshnessBadge.tsx`:

```tsx
import type { MetricStatus } from "../types";

const CFG: Record<MetricStatus, { emoji: string; titulo: string }> = {
  fresco: { emoji: "🟢", titulo: "Fresco" },
  velho: { emoji: "🟡", titulo: "Desatualizado" },
  ausente: { emoji: "⚪", titulo: "Ausente" },
  estimado: { emoji: "〰️", titulo: "Estimado" },
};

export default function FreshnessBadge({ status, measuredAt }: { status: MetricStatus; measuredAt?: string | null }) {
  const c = CFG[status];
  const tip = measuredAt ? `${c.titulo} · medido em ${measuredAt.replace("T", " ")}` : c.titulo;
  return <span title={tip} style={{ fontSize: 11 }}>{c.emoji}</span>;
}
```

- [ ] **Step 3: Verify build**

Run: `cd web; npm run build`
Expected: success.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/FreshnessBadge.tsx web/src/lib/fmt.ts
git commit -m "feat(ui): FreshnessBadge + fmtMetric helper"
```

---

### Task 4: `MetricChip` (fonte de insight)

**Files:**
- Create: `web/src/components/MetricChip.tsx`

- [ ] **Step 1: Create MetricChip**

Create `web/src/components/MetricChip.tsx`:

```tsx
import type { InsightSource } from "../types";
import { fmtMetric } from "../lib/fmt";
import FreshnessBadge from "./FreshnessBadge";

export default function MetricChip({ src }: { src: InsightSource }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4,
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: "2px 8px", fontSize: 11, color: "var(--text-dim)",
      margin: "2px 4px 0 0" }}>
      {src.label} {fmtMetric(src.valor, src.unidade)}
      <FreshnessBadge status={src.status} />
    </span>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MetricChip.tsx
git commit -m "feat(ui): MetricChip — insight source chip"
```

---

### Task 5: `InsightList`

**Files:**
- Create: `web/src/components/InsightList.tsx`

- [ ] **Step 1: Create InsightList**

Create `web/src/components/InsightList.tsx`:

```tsx
import type { Insight } from "../types";
import MetricChip from "./MetricChip";

export default function InsightList({ insights }: { insights: Insight[] }) {
  if (!insights.length) {
    return <div style={{ fontSize: 12, color: "var(--text-faint)" }}>Sem insights hoje.</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {insights.map((ins, i) => (
        <div key={i} className="card" style={{ padding: "10px 12px" }}>
          <div style={{ fontSize: 13, color: "var(--text)" }}>{ins.texto}</div>
          <div style={{ marginTop: 6 }}>
            {ins.metricas_usadas.map((s) => <MetricChip key={s.key} src={s} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/InsightList.tsx
git commit -m "feat(ui): InsightList — traceable insights with source chips"
```

---

### Task 6: `CheckinBlock` (inputs 1-5)

**Files:**
- Create: `web/src/components/CheckinBlock.tsx`

- [ ] **Step 1: Create CheckinBlock**

Create `web/src/components/CheckinBlock.tsx`:

```tsx
import { useState } from "react";
import type { MetricCell } from "../types";

// Pré-seleciona valores já salvos hoje (vindos do domínio "checkin" de /api/metrics).
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
```

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/CheckinBlock.tsx
git commit -m "feat(ui): CheckinBlock — 1-5 manual check-in inputs"
```

---

### Task 7: `DomainGrid`

**Files:**
- Create: `web/src/components/DomainGrid.tsx`

Renderiza cada domínio (exceto `checkin`, tratado pelo `CheckinBlock` na página) como seção com grid de cards. Cada card: label + valor formatado + badge de frescor.

- [ ] **Step 1: Create DomainGrid**

Create `web/src/components/DomainGrid.tsx`:

```tsx
import type { MetricsPayload } from "../types";
import { fmtMetric } from "../lib/fmt";
import FreshnessBadge from "./FreshnessBadge";

const TITULOS: Record<string, string> = {
  prontidao: "Prontidão", recuperacao: "Recuperação",
  atividade: "Atividade", corpo: "Corpo",
};
const ORDEM = ["prontidao", "recuperacao", "atividade", "corpo"];

export default function DomainGrid({ metrics }: { metrics: MetricsPayload }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {ORDEM.map((dom) => {
        const cells = metrics.dominios[dom] || [];
        if (!cells.length) return null;
        return (
          <div key={dom}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
              letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>
              {TITULOS[dom]}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
              {cells.map((c) => (
                <div key={c.key} className="card" style={{ padding: "8px 10px" }}>
                  <div style={{ fontSize: 11, color: "var(--text-faint)", display: "flex",
                    justifyContent: "space-between", alignItems: "center" }}>
                    <span>{c.label}</span>
                    <FreshnessBadge status={c.status} measuredAt={c.measured_at} />
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 500, color: "#fff", marginTop: 2 }}>
                    {fmtMetric(c.value, c.unidade)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/DomainGrid.tsx
git commit -m "feat(ui): DomainGrid — metrics by domain with freshness"
```

---

### Task 8: Reescrever `Hoje.tsx` (layout 2 colunas)

**Files:**
- Modify: `web/src/pages/Hoje.tsx` (rewrite)

- [ ] **Step 1: Rewrite the page**

Replace the entire contents of `web/src/pages/Hoje.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { fetchMetrics, fetchAnalysis, regenerateAnalysis, postCheckin, postSync } from "../api";
import type { MetricsPayload, Analysis } from "../types";
import Semaforo from "../components/Semaforo";
import InsightList from "../components/InsightList";
import DomainGrid from "../components/DomainGrid";
import CheckinBlock from "../components/CheckinBlock";

export default function Hoje() {
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [erro, setErro] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [regen, setRegen] = useState(false);

  function carregar() {
    setErro("");
    fetchMetrics().then(setMetrics).catch((e) => setErro(e.message));
    fetchAnalysis().then(setAnalysis).catch(() => { /* análise é degradação graciosa */ });
  }

  useEffect(() => { carregar(); }, []);

  async function sincronizar() {
    setSyncing(true);
    try { await postSync(); carregar(); }
    catch (e) { setErro((e as Error).message); }
    finally { setSyncing(false); }
  }

  async function regenerar() {
    setRegen(true);
    try { const a = await regenerateAnalysis(); setAnalysis(a); }
    catch (e) { setErro((e as Error).message); }
    finally { setRegen(false); }
  }

  async function salvarCheckin(payload: Record<string, number>) {
    await postCheckin(payload);
    carregar();
  }

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!metrics) return <div className="page-sub">Carregando…</div>;

  const checkinCells = metrics.dominios["checkin"] || [];

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div className="page-title">Status do Dia</div>
          <div className="page-sub">Prontidão para treino hoje</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-gen" disabled={syncing} onClick={sincronizar}>
            {syncing ? "Sincronizando…" : "🔄 Sincronizar"}
          </button>
          <button className="btn-gen" disabled={regen} onClick={regenerar}>
            {regen ? "Gerando…" : "💡 Regenerar análise"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 360px) 1fr", gap: 20, alignItems: "start" }}>
        {/* Coluna esquerda: veredito + insights */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {analysis && (
            <Semaforo status={analysis.veredito.semaforo}
              motivo={analysis.veredito.motivo}
              recomendacao={analysis.veredito.recomendacao} />
          )}
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
            letterSpacing: ".05em", color: "var(--text-faint)" }}>Insights</div>
          <InsightList insights={analysis?.insights ?? []} />
        </div>

        {/* Coluna direita: métricas por domínio + check-in */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <DomainGrid metrics={metrics} />
          {checkinCells.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
                letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>Check-in</div>
              <div className="card" style={{ padding: "12px 14px" }}>
                <CheckinBlock cells={checkinCells} onSave={salvarCheckin} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd web; npm run build`
Expected: success, no TS errors. (The old `Today`/`MetricCard`/`postSync`-only imports are gone; `postSync` ainda existe em api.ts.)

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/Hoje.tsx
git commit -m "feat(ui): rewrite Hoje — 2-column verdict+insights | metrics+checkin"
```

---

## Verificação final

- [ ] `cd web; npm run build` — sem erros TS.
- [ ] `python -m pytest -q` (backend) — segue verde (não tocamos backend nesta camada).
- [ ] Preview manual: subir `iniciar.bat`, abrir Hoje, conferir: (a) 2 colunas, (b) veredito + insights com chips, (c) grid de domínios com badges de frescor, (d) check-in seleciona 1-5 e salva (recarrega). Screenshots no preview.
