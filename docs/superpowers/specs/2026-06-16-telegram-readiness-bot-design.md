# Spec — Readiness Telegram Bot (pivot)

_Data: 2026-06-16_

## Contexto

O produto era um painel web (React/Vite + FastAPI) de prontidão de treino sobre dados do
Garmin. A camada de dados/análise (`src/`) funciona, mas o front-end não entregou valor no uso
real. **Pivot:** abandonar o front e transformar o produto num **bot de Telegram pessoal (1
usuário)** que, **quando detecta a hora que acordei pelo Garmin**, manda o "saldo do dia"
(veredito de prontidão + métricas-chave). Inclui comandos sob demanda, check-in noturno
interativo e resumos de semana/mês com gráfico.

O cérebro (`src/`: garmin_client, daily_analysis, ingestor, history_db, llm, metric_reader,
analytics, insight_engine) é **reusado quase intacto**. A LLM segue na **Anthropic** por ora
(decisão do usuário sobrepõe o CLAUDE.md; trocar pra Ollama depois é só `src/llm.py`/env).

## Objetivos

- Bot Telegram que manda o saldo diário ao detectar o despertar via Garmin.
- Comandos: `/saldo`, `/insights`, `/checkin`, `/semana`, `/mes`, `/start`.
- Check-in dos 4 itens manuais (1–5) por botões inline, automático às 21h e sob demanda.
- Hospedagem **gratuita e sempre-ligada** (Oracle Cloud Always Free), mantendo o SQLite.

## Fora de escopo (YAGNI)

- Front-end web (`web/`) e o mount de SPA estático no `api/main.py`.
- Geração de planos de treino (`TrainingPlanner`, `build_plan`, comando de plano).
- Multiusuário, login, webhook público.

## Arquitetura

Processo único **python-telegram-bot** (long-polling — sem URL pública/porta) com `JobQueue`.

```
src/                      # CÉREBRO reusado (intacto)
  garmin_client.py · daily_analysis.py · ingestor.py · history_db.py
  llm.py · metric_reader.py · analytics.py · insight_engine.py · ...
bot/
  __init__.py
  config.py        # lê .env: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, horários, janela matinal
  main.py          # cria Application, registra handlers + jobs, run_polling()
  messages.py      # formata saldo / insights (texto Telegram, sem poluição)
  charts.py        # render PNG (matplotlib) do trio de recuperação p/ semana/mês
  handlers.py      # CommandHandlers + CallbackQueryHandler (botões 1–5)
  jobs.py          # job_wake (poll matinal) + job_checkin (21h)
  wake_detector.py # "o sono de hoje já tem hora de acordar?"
  state.py         # dedup via tabela bot_state no history.db
iniciar_bot.bat    # sobe o bot local (dev)
deploy/readiness-bot.service  # unit systemd (Oracle VM)
```

Reuso direto (caminhos):
- Veredito + insights do dia: `src/daily_analysis.py::DailyAnalysis.build(date, force)`.
- Sync do dia: `src/ingestor.py::Ingestor.sync_today()`.
- Hora de acordar: `src/garmin_client.py::GarminClient.get_sleep_day(day)` (DTO com fim do sono).
- Check-in: `api/services.py::save_checkin` (mover/expor a lógica p/ `src/` ou chamar via helper).
- Tendências semana/mês: `api/services.py::build_trends(db, period)` → migrar p/ `src/` ou
  replicar o acesso (`Analytics().summary(snaps)` + `InsightEngine.trend_insights`).

> Nota: parte da lógica de payload vive hoje em `api/services.py`. Mover o que o bot precisa
> (`save_checkin`, `build_trends`) para `src/` (ex.: `src/services_core.py`) pra não depender da
> camada FastAPI, que sai de escopo.

## Funcionalidades

### 1. Saldo matinal (trigger por despertar)
`job_wake` roda a cada 15 min na janela `WAKE_WINDOW` (default 05:00–11:00, hora local TZ).
Cada tick: `wake_detector` chama `get_sleep_day(hoje)`; se há hora de fim de sono (sono fechado
e sincronizado), dispara: `Ingestor.sync_today()` → `DailyAnalysis.build(hoje)` →
`messages.saldo(...)` → envia ao `TELEGRAM_CHAT_ID` → grava `bot_state['saldo_date']=hoje`
(não repete no dia). Fallback: ao fim da janela (11:00), se ainda não enviou, manda com o que
tiver + nota "sono ainda não sincronizou".

Formato (enxuto, sem emoji-poluição; um emoji de status + ícones-âncora):
```
☀️ Bom dia — acordou 06:12
🟡 Pegue leve
Dívida de sono 2.4h · durma cedo.

FC repouso  55  (-5.9 vs 7d)   · fresco
Body Battery 38                · fresco
Sono 6:18 · dívida 2.4h        · esta noite
Corridas 3/semana
```
Veredito por regra (🟢 verde / 🟡 amarelo / 🔴 vermelho). Frescor por métrica em texto.

### 2. Comandos sob demanda
- `/saldo` — reenvia o saldo do dia (usa cache; não re-sincroniza à toa).
- `/insights` — manda os insights rastreáveis da IA do dia (texto + as métricas-fonte). Se a
  IA falhar: "IA indisponível — veredito acima segue válido".
- `/checkin` — dispara o fluxo de check-in a qualquer hora.
- `/semana` / `/mes` — ver seção 4.
- `/start` — ajuda curta com a lista de comandos.

### 3. Check-in interativo (21h + `/checkin`)
`job_checkin` às `CHECKIN_HOUR` (default 21:00) e o comando `/checkin` mandam 4 perguntas
(hidratação, energia, dor muscular, alimentação), cada uma com teclado inline **1–5** + rótulos
das pontas (ex.: "desidratado … bem hidratado"). Ao tocar: grava via `save_checkin` (inteiro
1–5, `source="manual"`, sobrescreve o do dia) e **edita a mensagem** mostrando o valor escolhido
("Hidratação: 4 ✓"). Idempotente. Marca `bot_state['checkin_date']` pra não repetir o automático.

### 4. Resumos `/semana` (7d) e `/mes` (30d)
`build_trends(db, period)` → **gráfico PNG (matplotlib)** do **trio de recuperação** (FC repouso,
Sono em h, Body Battery) ao longo do período (3 painéis/linhas, estilo limpo), enviado como foto,
com legenda = insights da IA do período + direção de cada métrica (↑/↓/→). Sem dados suficientes
→ mensagem discreta "histórico insuficiente para o período".

## Estado, dedup e erros

- **`bot_state(key TEXT PRIMARY KEY, value TEXT)`** no `history.db`: `saldo_date`, `checkin_date`.
  Migração via o mesmo padrão de `_add_missing_columns` / `CREATE TABLE IF NOT EXISTS`.
- **Garmin falha:** saldo sai com o último dado em cache + aviso; loga sem vazar credenciais.
- **Anthropic falha:** saldo sai mesmo assim (veredito é regra); `/insights` responde indisponível.
- **Token Garmin expira:** tenta relogar (garth); se persistir, avisa no chat ("preciso relogar
  no Garmin").
- **Segurança:** todo handler checa `update.effective_chat.id == TELEGRAM_CHAT_ID`; ignora o
  resto. Secrets só em env/`.env`; nunca no git. Mascarar email/senha em log.

## Configuração (.env / env vars)
```
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
GARMIN_EMAIL=...
GARMIN_PASSWORD=...
ANTHROPIC_API_KEY=...
TZ=America/Sao_Paulo
WAKE_WINDOW_START=05:00
WAKE_WINDOW_END=11:00
WAKE_POLL_MINUTES=15
CHECKIN_HOUR=21
DB_PATH=/home/ubuntu/readiness/history.db
```

## Deploy — Oracle Cloud Always Free

- VM Ubuntu (ARM Ampere, always-free, sempre ligada, disco persistente).
- `git clone` + `python -m venv` + `pip install -r requirements.txt` (add `python-telegram-bot`,
  `matplotlib`).
- `.env` com os secrets; `TZ` no sistema/serviço.
- Serviço **systemd** `readiness-bot.service`: `Restart=always`, `WantedBy=multi-user.target`
  (sobe no boot, reinicia se cair).
- `history.db` + token Garmin (garth) no disco da VM (persistente entre reinícios).
- Update: `git pull && systemctl restart readiness-bot`.
- IP estável da VM reduz fricção do login Garmin (vs IP de datacenter rotativo).

## Arquivamento do front

Antes de remover, salvar o estado atual numa branch: **`legacy/frontend`** (push). No `master`,
remover `web/` e o mount de SPA estático do `api/main.py`. O `api/` pode ficar como utilitário
ou ser aposentado depois (o bot não depende dele se `save_checkin`/`build_trends` migrarem p/
`src/`).

## Testes

- `wake_detector`: dado um DTO de sono com/sem fim de sono → detecta certo.
- `messages.saldo` / formatação: snapshot de texto com dados mock (inclui estado "ausente").
- `state`: dedup grava/lê data; não reenvia no mesmo dia.
- Handlers: simular `update`/`context` (mock) p/ `/saldo`, `/checkin` (callback grava 1–5).
- `charts`: gera PNG sem erro a partir de séries mock (não compara pixels).
- Telegram e Garmin **mockados** nos testes — não bater em rede real.

## Risco aberto

Login Garmin a partir da nuvem pode pedir MFA/relogin esporádico. Mitigação: persistir token
garth no disco da VM e relogar sob demanda; IP estável ajuda. É o ponto mais frágil — monitorar
nas primeiras semanas.
