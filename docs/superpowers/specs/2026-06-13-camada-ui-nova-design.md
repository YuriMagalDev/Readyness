# Spec — UI Nova "Hoje" (Reformulação, parte 3/3)

**Data:** 2026-06-13
**Objetivo:** Redesenhar a tela "Hoje" para mostrar muito dado sem poluir — veredito + insights rastreáveis à esquerda, métricas por domínio com frescor à direita, e check-in manual — consumindo `/api/metrics` e `/api/analysis`.

## Contexto

Parte 3 de 3. Depende da Camada 1+2 (`/api/metrics`, `/api/checkin` — entregue) e da Camada 2 de análise (`/api/analysis` — spec parte 2, implementar antes desta). **Uso é desktop/PC (tela larga)** — layout multi-coluna, não mobile-first.

## Decisões do brainstorming

- **Layout:** duas colunas (escolhido vendo mockups). Esquerda fixa = veredito + insights; direita rola = métricas por domínio.
- **Escopo:** só a "Hoje" nova. Tendências/Treinos/Plano ficam como estão. `daily_snapshot` NÃO aposenta agora (dual-write segue; aposentar vira spec curto futuro).
- **Check-in manual** incluído (inputs 1-5).
- **Sem framework de teste de frontend** — verificação via `npm run build` + screenshots no preview.

## Layout (desktop, 2 colunas)

```
┌───────────────────────────────────────────────────────────┐
│ Status do Dia            [🔄 Sincronizar] [💡 Regenerar]    │
├──────────────────────────┬────────────────────────────────┤
│ ESQUERDA (fixa)          │ DIREITA (rola)                  │
│                          │                                 │
│ ┌──────────────────────┐ │ PRONTIDÃO                       │
│ │ 🟡 AMARELO           │ │ [VO2 48🟡][Readiness 62🟢]...   │
│ │ pegue leve hoje      │ │ RECUPERAÇÃO                     │
│ └──────────────────────┘ │ [FC 58🟢][Sono 6.1h🟢]...       │
│                          │ ATIVIDADE                       │
│ INSIGHTS                 │ [Passos 8k🟢][Cal 2200🟢]...    │
│ • FC repouso ↑ + bateria │ CORPO                           │
│   baixa: recuperação...  │ [Peso 80kg🟢][%gord 18🟢]       │
│   [FC 58🟢][Bat 30🟢]    │ CHECK-IN (inputs 1-5)           │
│ • Sono REM baixo...      │ Hidratação [1][2][3][4][5]      │
│   [REM 0.8h🟢]           │ Energia    [1][2][3][4][5]      │
│                          │ ... [Salvar check-in]           │
└──────────────────────────┴────────────────────────────────┘
```

## Componentes (web/src/)

Novos:
- `components/FreshnessBadge.tsx` — recebe `status` ("fresco"|"velho"|"ausente"|"estimado") → emoji + cor (🟢 verde / 🟡 amarelo / ⚪ cinza / 〰️ azul) + tooltip "medido em <measured_at>".
- `components/MetricChip.tsx` — chip compacto `{label valor🟢}` usado nos insights (fonte da conclusão).
- `components/MetricCard.tsx` — **reusar/estender** o existente: valor formatado + `FreshnessBadge` + label. (Hoje já existe `MetricCard`; estender pra aceitar `status`/`measured_at`.)
- `components/DomainGrid.tsx` — recebe `dominios` de `/api/metrics`, renderiza seção por domínio (ordem: prontidao, recuperacao, atividade, corpo) com grid de `MetricCard`. O domínio `checkin` é renderizado por `CheckinBlock` (não como cards read-only).
- `components/InsightList.tsx` — lista de insights; cada um = texto + linha de `MetricChip` (de `metricas_usadas`). Lista vazia → "Sem insights hoje" discreto.
- `components/CheckinBlock.tsx` — 4 linhas (hidratacao/energia/soreness/alimentacao), cada uma 5 botões (1-5), pré-seleciona valor atual; botão "Salvar check-in".

Página:
- `pages/Hoje.tsx` — **reescrita** para o layout 2 colunas consumindo `/api/metrics` + `/api/analysis`. Mantém os botões Sincronizar (postSync existente) e adiciona "Regenerar análise" (POST /api/analysis force).

## Formatação de valor

Métricas `time` (predições de prova, em segundos) → `mm:ss` no front (já existe lógica equivalente em `services._fmt_valor`; replicar pequena helper TS `fmtMetric(value, unidade)` que trata `unidade === "time"`). Demais: `value + unidade`. `value === null` → "—".

## Tipos (web/src/types.ts)

```typescript
export type MetricStatus = "fresco" | "velho" | "ausente" | "estimado";

export interface MetricCell {
  key: string; label: string; value: number | null;
  unidade: string; measured_at: string | null;
  status: MetricStatus; source: string;
}
export interface MetricsPayload {
  date: string;
  dominios: Record<string, MetricCell[]>;  // prontidao|recuperacao|atividade|corpo|checkin
}
export interface InsightSource {
  key: string; label: string; valor: number | null; unidade: string; status: MetricStatus;
}
export interface Insight { texto: string; metricas_usadas: InsightSource[]; }
export interface Analysis {
  date: string;
  veredito: { semaforo: "verde" | "amarelo" | "vermelho"; motivo: string; recomendacao: string };
  insights: Insight[];
}
```

## API client (web/src/api.ts)

```typescript
export const fetchMetrics = (date?: string) =>
  get<MetricsPayload>(`/api/metrics${date ? `?date=${date}` : ""}`);
export const fetchAnalysis = (date?: string) =>
  get<Analysis>(`/api/analysis${date ? `?date=${date}` : ""}`);
export async function regenerateAnalysis(date?: string): Promise<Analysis> { /* POST /api/analysis {date}, padrão de erro existente */ }
export async function postCheckin(payload: Record<string, number>): Promise<{ok: boolean}> { /* POST /api/checkin */ }
```

## Fluxo

- Mount: `Promise.all([fetchMetrics(), fetchAnalysis()])`. Erro em qualquer um → banner de erro (padrão existente), mas se só a análise falhar, ainda mostra métricas (degradação graciosa).
- "Sincronizar" → `postSync()` → recarrega ambos.
- "Regenerar análise" → `regenerateAnalysis()` → atualiza só a coluna esquerda.
- Check-in "Salvar" → `postCheckin({...})` → recarrega ambos (check-in alimenta análise).

## Verificação

- `cd web; npm run build` — sem erros TypeScript.
- Preview: screenshots confirmando (a) layout 2 colunas, (b) badges de frescor por métrica, (c) chips de fonte nos insights, (d) check-in seleciona e salva. Sem framework de teste de FE no projeto.

## Não-objetivos (YAGNI)

- Sem redesenhar Tendências/Treinos/Plano.
- Sem aposentar `daily_snapshot` (spec futuro).
- Sem testes unitários de frontend (projeto não tem runner; verificação por build + preview).
- Sem responsividade mobile dedicada (uso é desktop).
- Sem edição de métricas do Garmin pela tela (só check-in manual é editável).
