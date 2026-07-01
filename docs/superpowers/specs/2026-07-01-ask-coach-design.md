# Spec — `/ask`: coach conversacional no bot Telegram

**Data:** 2026-07-01
**Projeto:** GarminAI Coach (readiness) — nova frente do bot
**Status:** aprovado (design), pronto p/ plano de implementação

## Objetivo

Comando `/ask` no bot Telegram que deixa o Yuri conversar com o coach (Claude) sobre
uma corrida específica ou um assunto geral, com **contexto real** (dados Garmin da
corrida, readiness do dia, nutrição). Caso de uso motivador: esclarecer decisões de
treino, ex. "na última corrida perdi ritmo no fim, mas era desaquecendo/correndo mais
devagar pra terminar seguro — é certo fazer isso durante ou depois da corrida?".

## Princípios (herdados do CLAUDE.md)

- **Bot resiliente**: sem `ANTHROPIC_API_KEY` o `/ask` degrada com aviso, bot segue no ar.
  Sem Garmin (429) a corrida usa dados do DB/insight cacheado, sem splits.
- **Sem dado sensível**: `athlete_profile.json` vai no system do Claude (já feito por
  `ask_coach`); NÃO contém credenciais Garmin (verificado: só nome/medidas/nutrição).
- **Reuso**: aproveita `ask_coach`, `filter_runs`, `build_run_detail`, estado por
  `user_data` no padrão do `/comi`.

## Arquitetura

Reusa o núcleo existente `src/ai_coach.py::ask_coach(prompt, context, depth)`:
- profile carregado e cacheado no `system` (cache_control ephemeral) + bloco de contexto.
- `depth="deep"` → Sonnet.

### Mudanças no núcleo

1. **`ask_coach` aceita histórico.** Hoje recebe `prompt: str` e monta
   `messages=[{"role":"user","content":prompt}]`. Estender para aceitar **ou** uma string
   (compat atual) **ou** uma lista de mensagens `[{"role","content"}, ...]` (thread).
   Assinatura nova: `ask_coach(messages, context, depth="quick")` onde `messages` pode ser
   `str | list[dict]`. String → embrulha em `[{"role":"user","content": s}]`. Mantém
   retrocompatibilidade com chamadas atuais (`insight_engine`, se houver).
2. **Modelo Sonnet atualizado.** `SONNET = "claude-sonnet-4-6"` → `"claude-sonnet-5"`
   (mais capaz; custo desprezível p/ 1 usuário). Verificar se `insight_engine`/outros
   consumidores de `depth="deep"` continuam ok (mesma API, só troca id do modelo).

## Fluxo (stateful, padrão `/comi`)

```
/ask
 └─ inline: [🏃 Corrida]  [💬 Outro assunto]
     ├─ ask:run  → lista últimas 8 corridas (filter_runs + labels do /atividades)
     │             callback ask:pick:<activityId>
     │             → "Manda tua pergunta 👇" ; estado thread aberta (mode=run, run_id)
     │             → contexto = build_run_detail(activityId): activity + splits + insight
     └─ ask:geral → "Manda tua pergunta 👇" ; estado thread aberta (mode=geral)
                    → contexto = readiness de hoje (daily_analysis/veredito) + painel nutrição
 → primeira pergunta (texto) → ask_coach(history, context, depth="deep")
 → resposta + botão [✋ finalizar] (callback ask:fim)
 → próximas mensagens de texto continuam na MESMA thread (history acumulado)
    até ✋ finalizar (limpa estado) ou /cancelar ou novo /ask
```

## Componentes

### `bot/ask.py` (novo)
Lógica pura + gestão de estado da thread (testável sem Telegram).
- `build_run_context(db, client, activity_id) -> dict`: `{activity, splits, insight}` via
  `build_run_detail`; se splits indisponível (Garmin 429), retorna sem splits (não quebra).
- `build_general_context(db, db_path, profile, date) -> dict`: `{readiness, nutricao}` —
  veredito do dia (`daily_analysis`) + `today_panel(...)["today"]` (macros/EA).
- Estado da thread em `user_data["ask_thread"]`: `{mode, run_id, context, history: list}`.
  - `open_thread(user_data, mode, run_id, context)`
  - `append_user(user_data, text)` / `append_assistant(user_data, text)`
  - `is_active(user_data) -> bool`
  - `close_thread(user_data)`
- `history` = lista de `{"role","content"}` acumulada; enviada inteira a cada turno.

### `bot/handlers.py`
- `cmd_ask`: se `bot_data["anthropic"]` é None → responde "🤖 coach indisponível
  (sem ANTHROPIC_API_KEY)" e retorna. Senão manda inline `[🏃 Corrida][💬 Outro assunto]`.
- `on_ask_button` (callback `^ask:`):
  - `ask:run` → busca `filter_runs(client.get_activities(...))[:8]`, monta teclado
    `ask:pick:<id>` (reusa `_run_button_label`). Sem corridas → aviso.
  - `ask:pick:<id>` → `build_run_context`, `open_thread(mode=run)`, pede pergunta.
  - `ask:geral` → `build_general_context`, `open_thread(mode=geral)`, pede pergunta.
  - `ask:fim` → `close_thread`, "conversa encerrada ✋".
- Captura de texto: em `on_text_macros`, checar `ask.is_active(user_data)` **ANTES** do
  fluxo de macros. Se ativa → `_handle_ask_turn`: append user, chama `ask_coach(history,
  context, depth="deep")`, append assistant, responde com botão `[✋ finalizar]`.

### `bot/main.py`
- `CommandHandler("ask", handlers.cmd_ask)`.
- `CallbackQueryHandler(handlers.on_ask_button, pattern=r"^ask:")` (registrar ANTES do
  handler genérico se houver colisão de prefixo — não há: `ask:` é único).
- `/ask` no texto de ajuda do `/start`.

## Data flow

```
pergunta texto
  → append_user(history)
  → ask_coach(history, context, depth="deep")   # Sonnet, profile no system cacheado
  → append_assistant(history)
  → reply_text(resposta, botão ✋ finalizar)
```

Contexto (`context` dict) muda por modo:
- **run**: `{"activity": {...}, "splits": [...], "insight": "..."}`
- **geral**: `{"readiness": {veredito...}, "nutricao": {totals, target, ea, training}}`

## Erros / resiliência

| Situação | Comportamento |
|---|---|
| Sem `ANTHROPIC_API_KEY` | `/ask` avisa "coach indisponível", NÃO abre thread |
| Garmin 429 / sem splits | usa activity do DB + insight cacheado, contexto sem splits |
| Chamada Sonnet falha (timeout/rede) | "não consegui responder agora, tenta de novo"; thread SEGUE aberta |
| Texto solto sem thread ativa | segue fluxo de macros atual (sem regressão) |
| `/cancelar` ou novo `/ask` com thread ativa | reseta estado da thread |
| Thread perdida em restart do bot | aceitável — conversa efêmera, user_data em memória |

## Testes (TDD, puros primeiro)

1. `ask_coach` aceita `str` (compat) e `list[dict]` (histórico) — mock do client Anthropic,
   sem chamada real; verifica que `messages` enviado bate com o histórico.
2. `bot/ask.py`:
   - `build_run_context` monta `{activity, splits, insight}`; degrada sem splits.
   - `build_general_context` monta `{readiness, nutricao}`.
   - estado: `open_thread` / `append_*` / `is_active` / `close_thread` (roundtrip).
3. Handlers (com fakes de update/context dos testes de bot existentes):
   - `cmd_ask` sem API key → aviso, sem thread.
   - `cmd_ask` com API key → manda botões.
   - `on_ask_button`: `ask:run`→lista, `ask:geral`→prompt+thread, `ask:pick`→thread run,
     `ask:fim`→fecha.
   - `on_text_macros`: thread ativa → turno do coach (mock ask_coach); thread inativa →
     fluxo de macros (sem regressão).

## Fora de escopo (YAGNI)

Persistir thread em DB, histórico entre restarts, budget de tokens, streaming da resposta,
entrada por voz, seleção de corrida por período/busca.

## Deploy

Mesmo processo das frentes anteriores (ver `garmin_nutricao` memory): tar dos arquivos
(conteúdo LF) → extrair no servidor Oracle `ubuntu@136.248.77.150:/home/ubuntu/readiness`
→ verificar imports + testes no `.venv` → `systemctl restart readiness-bot` → commit local
no server. Arquivos novos/alterados: `src/ai_coach.py`, `bot/ask.py` (novo), `bot/handlers.py`,
`bot/main.py` + testes. Sem dependência nova.
