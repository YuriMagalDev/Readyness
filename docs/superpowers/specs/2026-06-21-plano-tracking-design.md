# Spec — Sub-projeto 4: Registro & Tracking do Plano (Treinus)

**Data:** 2026-06-21 · **Roadmap pai:** `2026-06-20-camada-temporal-roadmap.md` · **Depende de:** sub-projetos 1-3 (merged).

## Contexto / pivô

O sub-projeto 4 original era um **gerador** de plano semanal via LLM. Descoberta no brainstorming: o
Yuri **já tem um professor** que passa as corridas pelo app **Treinus** (a musculação ele define
sozinho). Gerar plano competiria com o treinador real → **YAGNI, descartado**. O bot vira **registro +
acompanhamento** do plano: tu registra a semana, ele cruza com tuas atividades reais (feito/furou) e com
carga/prontidão. **Sem LLM** neste sub-projeto.

**Futuro (anotado, adiado):** scraping do Treinus com login/senha (login inativo agora). O registro
manual de hoje usa o **mesmo modelo de dados** (`parse_plan` → `{corrida, musculacao}`), então o scraper
só preenche depois, sem retrabalho.

## Princípios herdados (CLAUDE.md)

- **Determinístico**: parse + tracking por regra, sem LLM.
- **Frontend robusto**: status desconhecido → neutro, nunca quebra.
- **Bom com metade vazia**: sem plano registrado → mensagem instrutiva, não erro.

## Decisões travadas (brainstorming)

- Bot **registra**, não gera. Reusa `src/plan_tracker.match_plan` (já existe: feito/pendente/furou).
- Registro **manual por texto colado** (1 treino por linha), via o comando `/plano`.
- Professor passa **corridas**; **musculação** o Yuri registra também (tipo `musculacao`).
- `/plano` cruza com **carga/prontidão do dia** (score + ACWR) no cabeçalho.

## Componentes

### `src/plan_parser.py` (módulo novo, puro)
`parse_plan(text) -> dict` → `{"corrida": [...], "musculacao": [...]}`, cada item `{"dia": str, "descricao": str}`.
- Cada linha: `dia tipo descrição…`. `dia` ∈ {seg,ter,qua,qui,sex,sab,dom} (normaliza acento, 3 primeiras letras).
  `tipo`: começa com "cor" → corrida; "mus"/"forç"/"for" → musculacao. Resto da linha = `descricao`.
- Linha sem dia/tipo reconhecível → ignorada (robusto). Linhas vazias e a 1ª linha que for só o comando
  `/plano` são ignoradas.
- `dia` normalizado pra forma capitalizada esperada pelo `plan_tracker` (ele já usa as 3 primeiras letras
  lowercased, então qualquer forma serve — guardar a string original do dia).

### `src/history_db.py` — persistência do plano
- Tabela nova em `_init_db`: `weekly_plan(week_start TEXT PRIMARY KEY, plan_json TEXT NOT NULL)`.
- `save_plan(week_start: str, plan: dict)` — `INSERT OR REPLACE`, serializa JSON.
- `get_plan(week_start: str) -> dict | None` — desserializa, None se ausente.

### `src/plan_tracker.match_plan` (reusa, sem mudar)
`match_plan(plan, activities, today, week_start)` já cruza o plano com as atividades reais e marca
`feito|pendente|furou`. **Não muta** — calcula na leitura. Corrida detectada pelo `job_runs` já conta
como atividade real → vira `feito` automático.

### `bot/messages.py` — `format_plan`
`format_plan(matched: dict, score: int|None, acwr) -> str`:
- Cabeçalho: `🗓 <b>Plano da semana</b>` + linha de prontidão `prontidão N/100 · ACWR X` (cruza carga;
  campos None → em-dash).
- Duas grades (Corrida / Musculação), cada sessão: `✅ feito` / `❌ furou` / `⏳ pendente` + dia + descrição.
- Sem plano → `nil`/string vazia tratada pelo handler (ver abaixo).

### `bot/handlers.py` — `cmd_plano`
- Texto após `/plano` **vazio** → MOSTRA: `week_start = plan_tracker.week_start_of(today)`;
  `plan = db.get_plan(week_start)`. Se None → instrui como registrar. Senão:
  `acts = db.get_activities(week_start, today.isoformat())`;
  `matched = match_plan(plan, acts, today, week_start)`; score/acwr de
  `compute_readiness(context_from_metrics(db, today))`; envia `format_plan(...)`.
- Texto após `/plano` **com linhas** → REGISTRA: `plan = parse_plan(texto)`; se ambas as grades vazias →
  responde formato inválido + exemplo; senão `db.save_plan(week_start, plan)` + confirma
  ("Plano salvo: N corridas, M musculações") e já mostra o `match_plan`.

### `bot/main.py` — wiring
`app.add_handler(CommandHandler("plano", handlers.cmd_plano))`.

## Fora de escopo

- Scraper do Treinus (futuro, login inativo).
- Edição de sessão individual / múltiplas semanas históricas (só a semana corrente).
- Qualquer geração de treino por LLM.

## Testes (TDD)

1. `parse_plan`: linhas válidas → grades certas; "musc"/"força"/"cor" mapeiam; acento no dia; linha
   inválida ignorada; 1ª linha `/plano` ignorada; texto vazio → grades vazias.
2. `save_plan`/`get_plan`: round-trip; `INSERT OR REPLACE` sobrescreve; ausente → None.
3. `format_plan`: grade com os 3 status; cabeçalho com score/acwr; None → em-dash; plano vazio degrada.
4. `cmd_plano` MOSTRA: sem plano → instrução; com plano → grade + status (mock db/activities/context).
5. `cmd_plano` REGISTRA: linhas válidas → salva + confirma; formato inválido → exemplo, não salva.
6. Wiring: handler `plano` registrado.

## Verificação end-to-end

- Suite verde.
- `/plano` + colar a semana salva; `/plano` mostra grade com feito/furou + prontidão do dia.
- Corrida sincronizada (job_runs) aparece como `feito` sem ação manual.
- IA fora do ar não afeta (determinístico; score já degrada).
