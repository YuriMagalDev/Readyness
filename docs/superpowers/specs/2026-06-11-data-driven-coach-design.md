# Garmin Coach Data-Driven (v2) — Design Spec

**Data:** 2026-06-11
**Objetivo:** Tornar o app orientado a dados — extrair o máximo do Garmin (FR55),
persistir histórico permanente, e usar Haiku para gerar sugestões baseadas em
tendências e no dia. Prioridades do usuário: tendências de longo prazo (B) >
prontidão diária rica (C) > profundidade por treino (A) > cockpit (D).

---

## Contexto e Restrições

Fase 1 (MVP Streamlit) e Fase 2 (React + FastAPI) prontas. Esta é a Fase 3:
profundidade de dados + IA analítica.

**Restrições do Forerunner 55 (sondado na conta real):**

Disponível: stress, respiração, SpO2, intensity minutes, floors, resumo diário
(calorias/BMR), **race predictions** (5k/10k/21k/42k — proxy de fitness), sono,
FC repouso, Body Battery, steps, atividades com splits por volta.

NÃO disponível (vem vazio): VO2max, Training Readiness, Training Status, HRV
contínuo, Endurance Score. Sem esses → usar **race predictions** como proxy de
evolução de fitness e Body Battery como proxy de recuperação.

**Rate limit:** sondagem disparou HTTP 429. Backfill e sync devem throttlar
(pausa entre chamadas, backoff em 429).

**Escala:** single-user, local. SQLite (sem Postgres). `cache.db` continua
volátil (TTL 6h); novo `history.db` é o armazém permanente.

---

## Arquitetura

```
Garmin API → GarminClient (cache 6h) → Ingestor → history.db (SQLite permanente)
                                                        ↓
                          FastAPI services → AnalyticsEngine (queries de tendência)
                                                        ↓
                              Haiku (InsightEngine) → React (Tendências/Treinos/Hoje)
```

**Princípio:** ingestão separada da leitura.
- **Ingestor** escreve snapshots em `history.db` (backfill 3 meses no 1º run,
  depois `sync_today()` incremental).
- **API/Analytics** só leem de `history.db` — rápido, sem bater Garmin a cada
  request.
- **InsightEngine** consome saída do Analytics, nunca toca o DB direto.

---

## Modelo de Dados — `history.db` (SQLite)

### Tabela `daily_snapshot` (1 linha/dia, saúde e tendências)

| Campo | Tipo | Fonte |
|-------|------|-------|
| `date` | TEXT PK (ISO) | — |
| `resting_hr` | REAL | get_heart_rates |
| `sleep_hours` | REAL | get_sleep_data |
| `sleep_score` | REAL | get_sleep_data |
| `body_battery_high` | REAL | get_body_battery |
| `body_battery_low` | REAL | get_body_battery |
| `stress_avg` | REAL | get_stress_data |
| `stress_max` | REAL | get_stress_data |
| `respiration_avg` | REAL | get_respiration_data |
| `spo2_avg` | REAL | get_spo2_data |
| `intensity_minutes` | INTEGER | get_intensity_minutes_data |
| `steps` | INTEGER | get_user_summary |
| `floors` | INTEGER | get_floors |
| `calories_total` | REAL | get_stats_and_body |
| `calories_active` | REAL | get_stats_and_body |
| `race_pred_5k` | INTEGER (seg) | get_race_predictions |
| `race_pred_10k` | INTEGER (seg) | get_race_predictions |
| `race_pred_21k` | INTEGER (seg) | get_race_predictions |
| `race_pred_42k` | INTEGER (seg) | get_race_predictions |
| `runs` | INTEGER | activities classificadas |
| `strength` | INTEGER | activities classificadas |
| `train_minutes` | REAL | activities classificadas |

Campos ausentes num dia → `null`. Upsert por `date` (idempotente).

### Tabela `activity` (1 linha/treino)

| Campo | Tipo | |
|-------|------|--|
| `activity_id` | INTEGER PK | |
| `date` | TEXT | |
| `name` | TEXT | |
| `type` | TEXT | |
| `is_strength` | INTEGER (0/1) | |
| `distance_m` | REAL | |
| `duration_min` | REAL | |
| `pace_min_km` | REAL | derivado de averageSpeed |
| `avg_hr` | REAL | |
| `max_hr` | REAL | |
| `calories` | REAL | |
| `cadence` | REAL | averageRunningCadenceInStepsPerMinute |
| `stride_length` | REAL | |
| `splits_json` | TEXT | splits por volta (pace/FC/cadência por km) como JSON |

Upsert por `activity_id` (idempotente).

---

## Módulos Novos

| Módulo | Responsabilidade |
|--------|-----------------|
| `src/history_db.py` | Schema + conexão `history.db`. `upsert_snapshot(dict)`, `upsert_activity(dict)`, `get_snapshots(start, end)`, `get_activities(start, end)`, `get_activity(id)`. Cria schema no 1º acesso. Idempotente. |
| `src/ingestor.py` | `backfill(months=3)` com throttle (pausa entre dias, backoff em 429, retoma de onde parou). `sync_today()` incremental. Usa GarminClient → grava via history_db. Mascara credenciais nos logs. |
| `src/analytics.py` | Puro sobre `history.db`. Séries temporais, médias móveis, deltas semanais, tendência linear (slope: subindo/descendo/estável). Sem IA. Determinístico. |
| `src/insight_engine.py` | Haiku. `trend_insights(analytics_output, profile)` → 2-3 observações texto. `daily_insight(context, recent_trend)` → 1 recomendação consolidada. Fallback em falha de API/JSON. |

**Mudanças em módulos existentes:**
- `src/garmin_client.py` — métodos novos com cache: `get_stress`, `get_respiration`,
  `get_spo2`, `get_intensity_minutes`, `get_race_predictions`, `get_daily_summary`,
  `get_activity_splits(id)`.
- `src/data_processor.py` — continua montando context da Hoje (sem mudança de papel).

**Boundaries:** ingestão (escreve) e analytics (lê) nunca se cruzam. InsightEngine
só consome analytics.

---

## API (FastAPI)

| Rota | Método | Retorna |
|------|--------|---------|
| `/api/trends?period=30` | GET | séries (FC, sono, stress, battery, intensity, race_pred) + deltas/tendência (analytics) + insights Haiku (auto, prioridade B) |
| `/api/activities?period=30` | GET | lista de treinos da tabela `activity` (pace/FC/duração) |
| `/api/activity/{id}` | GET | 1 treino + splits por km + comentário Haiku (prioridade A) |
| `/api/sync` | POST | dispara `sync_today()` manual; retorna status |
| `/api/today` | GET | (existente) + `daily_insight` consolidado (prioridade C) + stress/respiração/SpO2 do dia |

`period` aceita 7/30/90 (dias). Erros viram JSON `{"erro": ...}` com 503 (Garmin/DB)
ou 502 (Haiku) — Haiku sempre tem fallback, então 502 raro.

---

## Frontend (React)

- **Tendências** (nova, B) — seletor de período (7/30/90d). Multi-gráfico: cada
  métrica com linha de tendência. Caixa de insights Haiku no topo (auto ao abrir).
- **Treinos** (nova, A) — lista de corridas/musculação. Clica → detalhe com splits
  por km (tabela/gráfico de pace) + leitura IA.
- **Hoje** (enriquecer, C) — + card "Insight do dia" (Haiku consolidado) +
  stress/respiração/SpO2 do dia.
- **Dados** (existente) — funde em Tendências (remover página separada).
- **Plano/Perfil** — sem mudança.
- Sidebar: Hoje · Tendências · Treinos · Plano Semanal · Perfil.

**Backfill UX:** 1º run sem histórico → página mostra banner "Montando seu
histórico (3 meses)…" enquanto ingestor roda. Idempotente.

---

## Estratégia de Modelos

- **Haiku** — todos os insights (trends + daily + comentário de treino). São
  análises curtas de leitura de dados. Mantém a regra do CLAUDE.md (Haiku p/ 90%).
- **Sonnet** — continua só no `training_planner` (geração de plano). Insights
  analíticos NÃO usam Sonnet.

---

## Tratamento de Erros

- **429 rate limit** — ingestor com backoff: pausa entre dias no backfill, retry
  com espera crescente. Persiste → para e salva progresso; idempotente retoma.
- **Endpoint vazio** (dia sem dado) — grava snapshot com campos `null`. Analytics
  ignora `null` nas médias/tendências.
- **Haiku falha/JSON inválido** — InsightEngine devolve fallback textual sem
  derrubar a página.
- **history.db ausente** — cria schema no 1º acesso.

---

## Testes

- `history_db` — upsert idempotente, queries de range (SQLite temp, sem API).
- `analytics` — séries/deltas/tendência (slope) com dados fixos. Determinístico.
- `ingestor` — mock GarminClient: valida throttle, gravação correta, retoma
  backfill interrompido.
- `insight_engine` — mock Haiku: valida fallback em JSON ruim, depth="quick".
- `api` — TestClient: rotas novas com analytics/insight mockados.
- Frontend — build TS + verificação manual no browser.

---

## Fora de Escopo (YAGNI)

- Sync automático agendado/background (usuário clica ou abre o app).
- Export de dados.
- Comparação com outros atletas / social.
- Modalidades além de corrida e musculação.
- VO2max/readiness/training status (FR55 não fornece).
- Deploy remoto (ver spec da Fase 2 para notas futuras).
