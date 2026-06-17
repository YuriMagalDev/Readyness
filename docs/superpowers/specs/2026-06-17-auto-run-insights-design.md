# Spec — Insight automático de corrida + `/atividades`

Data: 2026-06-17 · Projeto: Readiness (bot Telegram pessoal, 1 usuário)

## Objetivo

Quando o Yuri termina uma corrida e ela sincroniza no Garmin Connect, o bot manda
sozinho um insight daquela corrida (cabeçalho com números + leitura da IA). Também
expõe `/atividades` pra listar as últimas corridas e pedir o insight de uma à mão.

**Vale só pra corrida**: `running`, `treadmill_running`, `trail_running`. **Exclui**
`indoor_cardio` (usado pela musculação) e qualquer outro tipo.

## Decisões (do brainstorming)

- **Cadência de detecção**: polling a cada **15 min** (job recorrente).
- **`/atividades`**: lista só corridas (últimas **8**).
- **Mensagem**: cabeçalho (nome · distância · tempo · pace · FC média) **+** insight da IA.
- **Janela de detecção**: últimas **48h** de atividades por ciclo.

## Por que polling

Garmin Connect não oferece webhook/push pessoal viável. Detecção = puxar atividades
recentes periodicamente. 15 min equilibra rapidez do insight e risco de rate-limit no
IP do datacenter (Oracle). Uma chamada leve por ciclo (`get_activities`, cacheada).

## Componentes

### `bot/runs.py` (novo)
- `RUN_TYPES = {"running", "treadmill_running", "trail_running"}`
- `is_run(activity) -> bool` — `typeKey`/`type` ∈ `RUN_TYPES`.
- `filter_runs(activities) -> list` — só corridas, ordenadas da mais recente.
- Sem dependência de Telegram nem Garmin → testável puro.

### `src/history_db.py`
- Tabela nova `notified_activity(activity_id INTEGER PRIMARY KEY, sent_at TEXT)`
  (criada no `_init_db`; migração tolerante já existente cobre bancos antigos).
- `is_notified(activity_id) -> bool`
- `mark_notified(activity_id)` — grava com `sent_at` = agora ISO.
- Seed flag reusa `get_state/set_state` (`bot_state`): chave `runs_seeded`.

### `src/services_core.py`
- `build_run_detail(db, client, activity_id) -> dict` — adapta o `build_activity_detail`
  existente em `api/services.py`: usa splits do cache (`splits_json`) ou busca no Garmin
  (`get_activity_splits` → `splits_from_garmin`), persiste, e gera
  `InsightEngine.activity_insight(act, splits)`. Retorna `{activity, splits, insight}`.
- `api/services.build_activity_detail` passa a delegar pra cá (fonte única, sem duplicar).

### `bot/messages.py`
- `format_activity(activity, insight) -> str` (HTML):
  - Cabeçalho: `🏃 <b>{nome}</b>` + linha `distância · tempo · pace · FC média`.
  - Formatação tolerante a `None` (em-dash quando faltar), reusa helpers de fmt.
  - Insight da IA abaixo, separado pela régua já usada no saldo.
  - Distância: metros→km (1 casa). Pace: seg/km → `mm:ss /km`. Tempo: seg → `h`/`mm:ss`.

### `bot/jobs.py` → `job_runs(context)`
1. Puxa atividades recentes (~48h) via `client.get_activities`.
2. `runs = filter_runs(...)`.
3. Se `bot_state.runs_seeded` ausente: **seed** — `mark_notified` em todas as corridas
   atuais **sem enviar**, set `runs_seeded=1`, return. (Evita spammar histórico no 1º start.)
4. Senão, pra cada corrida com `not is_notified(id)`: ingere no DB (`Ingestor`/upsert),
   `build_run_detail`, manda `format_activity`, `mark_notified(id)`.
5. Garmin 429/erro → loga e sai quieto (próximo ciclo tenta). Não derruba o bot.

### `bot/handlers.py`
- `cmd_atividades(update, context)`:
  - Guard `_authorized`.
  - Puxa recentes, `filter_runs`, pega 8.
  - Vazio → "Nenhuma corrida recente." Senão InlineKeyboard, um botão por corrida
    (texto `{data} · {nome} · {km}`, callback `act:{activity_id}`).
- `on_activity_button(update, context)` (`CallbackQueryHandler` pattern `^act:`):
  - Guard. Parseia id. `build_run_detail` → edita/responde com `format_activity`.
  - Não-corrida (defensivo) → "Insight é só pra corrida."
  - Falha Garmin → "Não consegui analisar essa corrida agora."

### `bot/main.py`
- Registra `CommandHandler("atividades", handlers.cmd_atividades)`.
- Registra `CallbackQueryHandler(handlers.on_activity_button, pattern=r"^act:")`.
- `jq.run_repeating(jobs.job_runs, interval=15*60, first=30)`.

## Fluxo de dados

```
[corrida termina] -> sincroniza no Garmin Connect
   ↓ (≤15 min)
job_runs: get_activities(48h) -> filter_runs -> novas? 
   ↓ sim
build_run_detail (splits cache/Garmin + InsightEngine) -> format_activity -> Telegram
   ↓
mark_notified(id)
```

`/atividades` usa o mesmo `build_run_detail` sob demanda (sem depender do job).

## Tratamento de erro / robustez

- Toda chamada Garmin no job em try/except → loga, segue (princípio: não martelar, degradar).
- Insight da IA falha → `InsightEngine` já tem fallback; mensagem ainda sai com o cabeçalho.
- Seed garante zero spam de histórico no primeiro deploy.
- `chat_id` guard em todos os handlers (single-user).
- Campos `None` (FC/pace/distância ausentes) → em-dash, nunca crash.

## Testes (TDD por unidade)

- `bot/runs.py`: `is_run`/`filter_runs` — inclui os 3 tipos, exclui `indoor_cardio`/outros, ordena.
- `history_db`: `is_notified`/`mark_notified` persistem; PK evita duplicata.
- `messages.format_activity`: monta cabeçalho com números; tolera `None`; inclui insight.
- `jobs.job_runs`:
  - 1º ciclo seeda sem enviar (set `runs_seeded`), nada vai pro Telegram.
  - corrida nova após seed → 1 envio + `mark_notified`.
  - não reenvia corrida já notificada.
  - musculação/cardio nunca dispara.
  - Garmin lança → não envia, não quebra.
- `handlers`: `cmd_atividades` monta teclado só com corridas; vazio → aviso;
  `on_activity_button` chama `build_run_detail` e responde; guard de chat alheio.
- `services_core.build_run_detail`: usa splits do cache quando há; busca quando falta.

## Fora de escopo (YAGNI)

- Insight pra musculação/cardio.
- Comparação entre corridas / histórico agregado de pace (já tem `/semana` e `/mes`).
- Push/webhook Garmin (inviável).
- Configurar tipos via env (constante em código basta pra 1 usuário).
