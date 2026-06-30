# CLAUDE.md — Readiness (coach pessoal Garmin)

## O que é
Painel **pessoal** (1 usuário: Yuri) de coaching de corrida + hipertrofia, rodando no
**desktop**. Puxa dados do Garmin Connect (Forerunner 55), centraliza num catálogo de
métricas com frescor, e gera uma análise diária. Integra nutrição (TACO + tabela manual)
com ciclo de calorias por dia de treino. Responde todo dia: "posso treinar hoje e em
que intensidade?" e "qual é meu alvo de macros?".

Sem login, sem cadastro, sem multiusuário, sem marketing. Abre direto no painel do dia.

> **Contexto completo da reformulação está em `rebuild/`** — leia antes de mudanças grandes:
> `01-CORE.md` (núcleo), `02-DESIGN.md` (UI validada), `04-CLAUDE-DESIGN-BRIEF.md` (brief criativo de UI).

## Princípio que guia tudo: CONFIANÇA
1. **Números de fonte real** — todo número vem de TACO (tabela oficial de composição), cadastro
   manual (100g ou porção), ou Garmin. Nenhum número é inventado pela LLM.
2. **Frescor e transparência** — que comida tem macro conforme, quantas horas atrás.
3. **Veredito determinístico** — calorias e macros saem de cálculo puro (perfil + treino do dia),
   nunca opinião. O bot responde mesmo sem API (foto fica indisponível, mas /comi manual funciona).

## Stack
- Python 3.11+, FastAPI + uvicorn (1 usuário, IO-bound → performance da linguagem não é
  gargalo; o gargalo é rede Garmin).
- SQLite local (cache + histórico + refeições + alimentos custom).
- `garminconnect` (SSO) pra dados de corrida/sono/FC.
- Telegram Bot (python-telegram-bot) para registro de refeições e plano do dia.
- **Anthropic API** (`claude-haiku` via vision) **apenas** em `src/nutrition/label_vision.py`
  (extrai macros de foto da tabela nutricional); bot sobe mesmo sem `ANTHROPIC_API_KEY`
  (cadastro por foto fica indisponível, /comi manual funciona).
- Frontend React/TypeScript (Vite), servido pelo FastAPI em produção.

## Arquitetura em 3 camadas
1. **Dados** — Garmin (corrida/sono/FC), TACO completa (591 alimentos oficiais, NEPA/UNICAMP;
   gerada por `scripts/build_taco.py`) + `aliases.csv` (sinônimo comum → nome TACO exato, ex.
   frango→peito grelhado, carregado em prod por `load_food_db`), custom_foods (cadastro manual
   100g ou porção). Tabela `meal_log(date, meal, food, grams, kcal, p, c, g, logged_at)`.
   Frescor calculado na leitura; check-ins manuais 1-5 (hidratação/energia/soreness).
2. **Lógica** — veredito de readiness (FC, sono, bateria do relógio → treinar/correr/descansar).
   Ciclo de calorias: perfil (108kg/30%bodyfat) + dia de treino (binário: treina/não treina) → alvo
   kcal e macros. Sem LLM, sem opinião — cálculo puro.
3. **Painel + Bot** — FastAPI: resumo do dia (readiness + macros). Telegram: `/comi` (registra
   refeição com confirmação), `/dieta` (gráfico anéis: kcal + macros + EA), pergunta matinal
   "/plano?" (cicla calorias pro dia). Foto → Anthropic vision → extrai macros (ou digita manual).

## Visão de Rótulo (label_vision.py)
- **Única** função paga: `src/nutrition/label_vision.py` chama Claude vision (Haiku) pra
  ler foto da tabela nutricional brasileira (ANVISA).
- Sem foto: cadastro manual (kcal + macros digitados). Bot sobe sem `ANTHROPIC_API_KEY`,
  a feature de foto fica indisponível, /comi manual funciona sempre.
- Parsing rigoroso: extrai nome/base_unit/porcao_g/kcal/p/c/g do JSON. Resposta sem JSON
  válido = fallback para digitação manual.

## Perfil do Atleta (`athlete_profile.json`)
Arquivo local obrigatório: peso, % de gordura, meta de proteína diária, faixa de kcal por
tipo de dia. Campos nulos: **perguntar ao usuário, nunca inventar**. Nunca enviar à API
do Garmin. Usado em `src/nutrition/targets.py` pra calcular alvo do dia.

## Regras pro Claude Code
1. **Cache primeiro** — nunca rechamar Garmin (TTL ~6h).
2. **Frescor sempre visível** por métrica e por comida (horário/fonte).
3. **Números de fonte real só** — Garmin, TACO, ou cadastro manual. Nenhuma estimativa
   da LLM em números; se Anthropic vision falha, fallback para digitação.
4. **Campos nulos do perfil** → perguntar antes de gerar alvo de calorias.
5. **Sem dado sensível em log** (mascarar email/senha/API keys).
6. **Forerunner 55**: sem HRV contínuo confiável, sem SpO2 contínuo, sem training status
   estável — essas métricas costumam vir ausentes; o app tem que ficar bom com metade vazia.
7. **TDD por camada, commits pequenos.** Migração sem quebrar tela antiga = dual-write.
8. **Frontend robusto**: mapas de config sempre com fallback (status desconhecido → neutro,
   nunca tela preta). Tipos TS derivados do JSON real da API (contrato front↔back tem que bater).
9. **Bot resiliente**: sem ANTHROPIC_API_KEY a feature de foto fica indisponível, /comi manual
   funciona sempre. Sem Garmin (429): readiness sai do DB, painel monta mesmo assim.

## Variáveis de ambiente (.env)
```
# Garmin
GARMIN_EMAIL=...
GARMIN_PASSWORD=...
GARMINTOKENS=~/.garminconnect  # onde guardar token Garmin (loga 1x)

# Telegram bot
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...

# Anthropic (opcional: sem ela, cadastro por foto fica indisponível)
ANTHROPIC_API_KEY=...
VISION_MODEL=claude-haiku-4-5-20251001  # default pra leitura de rótulos

# Config
TZ=America/Sao_Paulo
DB_PATH=history.db
MORNING_SLOTS=09:30,12:00,14:00  # horários de tentativa do saldo matinal
CHECKIN_HOUR=21
```

## Estrutura
```
src/
  metric_catalog.py · metric_status.py · metric_reader.py
  collectors/         # normalizadores puros por domínio
  garmin_client.py    # wrappers cacheados + retry rate-limit
  history_db.py · ingestor.py
  daily_analysis.py   # veredito determinístico (FC, sono, bateria)
  readiness_score.py  # ACWR, RC, score final
  
  nutrition/
    config.py         # nutrition_config(profile) → ranges kcal/macros
    targets.py        # day_target() + energy_availability()
    food_db.py        # FoodDB: TACO lookup + custom_foods
    meal_parser.py    # parse_meal(text, fdb) → items (recognized, unrecognized)
    label_vision.py   # extract_label(image, client, model) → {name, base_unit, kcal, p, c, g}
    store.py          # salvar/ler refeições, custom foods, plano do dia
    data/taco.csv     # TACO completa (591 alimentos oficiais) — gerada por scripts/build_taco.py
    data/aliases.csv  # termo comum -> nome TACO exato (curado)

api/  services.py · main.py · (ReadinessDB, nutrition endpoints TBD)
web/  React/Vite (tela Hoje + aba Métricas)

bot/
  main.py             # build_app(): handlers + jobs
  config.py           # Config.from_env()
  handlers.py         # cmd_*, on_* callbacks (start, saldo, checkin, comi, dieta, plano, etc)
  nutrition.py        # load_food_db(), today_panel()
  nutrition_format.py # format_meal_confirm()
  jobs.py             # job_morning, job_checkin, job_day_plan, job_briefing, etc
  messages.py         # formatação de texto/markup
  charts.py           # recovery_chart_png(), nutrition_chart_png()
  checkin.py          # CHECKINS config, keyboard
  runs.py             # filtro de atividades
  core.py             # load_context(), collect_metrics(), daily_analysis()
  state.py · wake_detector.py

rebuild/  prompts-fonte da reformulação (01..04)
```

## Deploy
### Desktop (Windows)
`iniciar.bat` na raiz: entra na pasta, builda o front se faltar, sobe o bot (token Telegram
obrigatório) e o painel FastAPI em paralelo. Abre o navegador no painel.
- Parar: Ctrl+C (mata ambos).
- Sem Garmin (429, relogin): painel monta mesmo assim (readiness do cache).
- Sem Anthropic: bot sobe, /comi manual funciona, foto fica indisponível.
- Trocou build front → hard-refresh no navegador (Ctrl+Shift+R).
