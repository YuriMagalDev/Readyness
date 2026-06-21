# Spec — Sub-projeto 3: Proatividade

**Data:** 2026-06-20 · **Roadmap pai:** `2026-06-20-camada-temporal-roadmap.md` · **Depende de:** sub-projetos 1 (carga) e 2 (score), ambos merged.

## Objetivo

O bot passa a **cutucar sozinho** em vez de só responder. Quatro coisas proativas, todas
**determinísticas** (sem LLM → sempre saem, mesmo com a IA fora): briefing semanal de domingo +
três alertas de saúde/carga que disparam quando um sinal cruza pra ruim.

## Princípios herdados (CLAUDE.md)

- **Determinístico**: alertas e briefing são regra pura, nunca LLM.
- **Sem dado sensível em log.**
- **Bom com metade vazia (FR55)**: sinal ausente → não dispara alerta (None), nunca quebra o job.
- **Cache primeiro**: `job_alerts` faz best-effort `sync_today` (igual o saldo), mas degrada sobre o DB.

## Decisões travadas (brainstorming)

- 4 features: **briefing semanal (domingo 19:00 SP)** + alerta **FC subindo** + alerta **ACWR risco** +
  alerta **overreaching**.
- Alerta FC: **3 dias seguidos** com FC repouso **≥ baseline + 3 bpm**.
- Anti-spam **por episódio**: cada alerta dispara 1x ao cruzar pra ruim; não repete enquanto continua
  ruim; reseta quando volta ao normal.

## Componentes

### `src/alerts.py` (módulo novo, puro)
Detectores que recebem dados e retornam `dict|None` (None = sem alerta).

- `hr_rising(hr_rows, baseline, days=3, margin=3) -> dict|None`
  `hr_rows` = série de `resting_hr` (rows `{date, value}`, ordem asc) dos últimos ≥`days` dias.
  Dispara se os **últimos `days`** valores não-None existem E cada um `>= baseline + margin`.
  baseline = `resting_hr_baseline` mais recente (float). Retorna
  `{"kind": "hr_rising", "dias": days, "baseline": baseline, "valores": [...últimos days...]}`.
  Se baseline é None, ou faltam dias, ou algum dia < limiar → None.

- `acwr_risk(acwr) -> dict|None`
  Dispara se `acwr is not None` e `acwr_zone(acwr) == "risco"`. Retorna
  `{"kind": "acwr_risk", "acwr": round(acwr, 2)}`. Senão None.

- Overreaching **não** ganha detector novo: reusa `compute_readiness(context)["overreaching"]`. O job
  monta o alerta a partir do bool + do veredito.

### `src/weekly_briefing.py` (módulo novo, puro)
`build_weekly_briefing(db, today) -> dict`:
- `km_7d`: soma de `distance_m`/1000 das corridas (RUN_TYPES, não-strength) dos últimos 7 dias.
- `sessoes`: nº dessas corridas.
- `acwr`: valor de `acwr` do dia (`db.get_metrics(today)`), pode None.
- `sono_medio`: média de `sleep_hours` dos últimos 7 dias (None se sem dado).
- `fc_max`: maior `max_hr` das corridas dos últimos 90 dias (reusa `estimate_hr_max` de training_load;
  como fallback dá a estimativa Tanaka — aceitável no briefing).
- `recomendacao`: por zona ACWR — `risco` → "Semana de deload: reduza volume/intensidade." ·
  `baixo` → "Pode aumentar a carga com cuidado." · `otimo`/None → "Mantenha a carga atual."
Retorna o dict com todos os campos (None onde faltar dado).

### `bot/messages.py` — formatadores
- `format_alert(detail: dict) -> str` — despacha por `detail["kind"]`:
  - `hr_rising`: `⚠️ <b>FC repouso subindo</b>` + os N dias + "possível fadiga/infecção — considere pegar leve".
  - `acwr_risk`: `⚠️ <b>Carga em risco</b>` + ACWR + "pico de carga, risco de lesão — pisa no freio".
  - `overreaching`: `🛑 <b>Overreaching</b>` + os 3 sinais (do veredito) + "descanso recomendado".
  - kind desconhecido → string genérica (robustez, nunca crash).
- `format_briefing(data: dict) -> str` — `📊 <b>Resumo da semana</b>` + km · sessões · ACWR · sono médio ·
  FCmáx + linha de recomendação. Campos None viram em-dash. Reusa `_RULE`, `PARSE_MODE`.

### `bot/jobs.py` — dois jobs novos
- `job_alerts(context)` (diário): best-effort `Ingestor(client, db).sync_today()` (try/except, igual
  `_send_saldo`); monta context via `core.daily_analysis`/`context_from_metrics`; roda os 3 detectores;
  para cada alerta aplica **anti-spam por episódio** e envia.
  - Estado por alerta: `db.get_state(key)`/`set_state(key, "1"|"0")`, keys `alert_hr`, `alert_acwr`,
    `alert_over`. Envia só quando detecta E `state != "1"`; então `set_state(key,"1")`. Quando não
    detecta, `set_state(key,"0")` (reseta o episódio). Loga falhas (não engole silencioso — lição do
    job_runs).
- `job_briefing(context)` (domingo): guard pela data do dia (`get_state("briefing_date") == today.isoformat()`
  → não reenvia), monta `build_weekly_briefing`, envia, marca `set_state("briefing_date", today)`.

### `bot/main.py` — wiring
- `jq.run_daily(jobs.job_alerts, time=dt.time(hour=10, minute=0, tzinfo=TZ))`.
- `jq.run_daily(jobs.job_briefing, time=dt.time(hour=19, minute=0, tzinfo=TZ), days=(SUN,))`.
  **Verificar na implementação** a convenção de `days` do PTB v22 (inteiros 0-6); cobrir com teste de
  wiring que o briefing está restrito a 1 dia da semana.

## Fora de escopo

- Plano adaptativo (sub-projeto 4).
- Briefing com prosa de LLM (mantido determinístico; pode evoluir depois).

## Testes (TDD)

1. `hr_rising`: 3 dias ≥ base+3 → alerta; 1 dia abaixo → None; baseline None → None; <3 dias → None.
2. `acwr_risk`: zona risco → alerta; ótimo/baixo/None → None.
3. `build_weekly_briefing`: agrega km/sessões/sono; recomendação por zona (risco/baixo/ótimo); campos
   ausentes → None sem quebrar.
4. `format_alert`: cada kind renderiza; kind desconhecido não quebra. `format_briefing`: campos None →
   em-dash.
5. `job_alerts` anti-spam: detecta → envia 1x + `set_state "1"`; 2ª rodada ainda ruim → não envia;
   normaliza → `set_state "0"`; volta a ruim → envia de novo. (mock bot/client/db).
6. `job_briefing`: monta e envia 1x; 2ª vez no mesmo período → não reenvia.
7. Wiring: `job_alerts` e `job_briefing` registrados; briefing restrito a um dia (domingo).

## Verificação end-to-end

- Suite verde.
- Alertas disparam 1x por episódio (sem spam diário).
- Briefing chega domingo 19:00.
- IA fora do ar não afeta nada (tudo determinístico).
