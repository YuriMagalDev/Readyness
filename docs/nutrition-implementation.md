# Nutrição — estado da implementação (handoff)

> Resumo da sessão de 2026-06-30/07-01. Objetivo: retomar em sessão nova sem re-derivar contexto.
> A frente de nutrição está **implementada e em produção**.

## O que é
Tracking de refeições no bot Telegram do GarminAI Coach (`readiness`). Registra o que o
usuário come → kcal/macros, alvo diário ciclado por treino, energia disponível (EA), e um
painel `/dieta`. Foco: hipertrofia/recomposição.

## Pipeline de resolução de alimento (a peça central)
Por alimento, em ordem — **sem fuzzy** (era a fonte de bugs):
1. `custom_foods` (cache do que já foi resolvido) — exato normalizado
2. **TACO exato** + **aliases curados** (`data/aliases.csv`, ~79 termos comuns → nome TACO real)
3. **IA resolve** (`food_resolver.resolve_food`, Claude Haiku texto) → macros/100g →
   salva em `custom_foods` (source=`ia`) → usa. 1 chamada por alimento novo, depois é cache.
4. **Foto do rótulo** (`label_vision`, Claude vision) → pro específico/marca.

`FoodDB.match(name, fuzzy=False)` = custom + TACO exato + alias curado. `fuzzy=True` (default,
usado só em teste) liga o match aproximado + ambiguidade. Prod sempre `fuzzy=False`.
Aliases globais (`ALIASES` em food_db.py) apontam pros nomes do FIXTURE (não existem na TACO
real) — **NÃO entram em prod**; `load_food_db` usa só `aliases.csv`.

## Fluxo `/comi` (guiado, stateful via user_data)
- `/comi` sem args → pergunta refeição (botões `nut:meal:<café da manhã|almoço|lanche|janta>`)
- Escolhe → "manda os alimentos, vou somando" + botões `[✅ finalizar][↩ desfazer último][📷 foto da tabela]`
- Cada mensagem de texto → `_comi_add_foods`: parse exato → IA resolve desconhecidos → acumula
  em `user_data["comi"]["items"]`, mostra total parcial (fonte marcada: TACO / `~IA`)
- `↩ desfazer` (`nut:comi_undo`) → tira último item da sessão (antes de salvar)
- `📷 foto` (`nut:comi_foto`) → manda foto → lê rótulo → **pergunta o NOME** (`awaiting_food_name`)
  → usuário digita nome → cadastra em custom_foods (source=`foto`) → pede a quantidade
- `✅ finalizar` (`nut:comi_fim`) → `save_meal_items` do dia, limpa sessão
- `/comi <texto>` (com args) → one-shot antigo (parse+IA+confirma com `nut:save/edit/photo/manual`)
- `/cancelar` → limpa todo estado de sessão

## Outros comandos
- `/dieta` → PNG (matplotlib) painel de 2 partes:
  - HOJE: anéis PROTEÍNA (dominante) + KCAL·EA + CARBO + GORDURA. Número à ESQUERDA do anel,
    legenda à direita. Alvo ciclado por treino.
  - ONTEM (dia fechado): comido vs gasto Garmin, saldo, EA — o número confiável.
- `/ref` → lista refeições de hoje, um botão `🗑` por item (`nut:rmitem:<id>`) pra apagar erro já salvo
- `/saldo` → veredito de prontidão + linha de **contexto de nutrição** (`format_nutri_context`,
  energia+proteína de ONTEM). **Não muda o veredito** — decisão de treino é do usuário;
  `compute_readiness` fica 100% determinístico por regra.

## Alvos / cálculo (perfil `athlete_profile.json`)
- Prod: **108 kg / 30% BF** → LBM 75.6 kg. Bloco `nutricao`: neat_factor 1.3, deficit_kcal 500,
  protein_g 165, fat_g 60, ea_low 25, ea_ok 30.
- `targets.py`: TDEE (Katch-McArdle) = (370+21.6·LBM)·neat; alvo = TDEE−déficit (+exercício se treino).
- **Ciclo híbrido** (`resolve_exercise_kcal`): usa Garmin active calories (do `daily_snapshot`)
  se >0, senão estimativa fixa (treino 300 / corrida 400).
- **EA** = (kcal ingerida − exercício)/LBM. 🟢≥30 · 🟡25–30 · 🔴<25 (aviso, não muda veredito).

## Arquivos
```
src/nutrition/
  config.py        # nutrition_config(profile) -> ranges (LBM, defaults, override via perfil)
  targets.py       # tdee_base, day_target, energy_availability, resolve_exercise_kcal, day_balance
  food_db.py       # FoodDB (custom+TACO exato+alias, fuzzy opcional), normalize, load_aliases, ALIASES/PORTIONS
  meal_parser.py   # parse_meal(text, db, fuzzy=False), _extract_meal (tipo refeição c/ ou s/ ":")
  food_resolver.py # resolve_food(name, client, model) -> macros via IA (texto)
  label_vision.py  # extract_label(img) + parse_label_response (foto do rótulo)
  store.py         # meal_log/day_plan/custom_foods CRUD; list_meal_items, delete_meal_item, day_totals...
  data/taco.csv    # TACO completa (591 alimentos) — gerada por scripts/build_taco.py
  data/aliases.csv # termo comum -> nome TACO exato (~79, com plurais)
bot/
  nutrition.py     # load_food_db (só aliases.csv em prod), today_panel {today,yesterday}, resolve_unknowns
  nutrition_format.py # format_meal_confirm (tag ~IA/rótulo), format_nutri_context
  charts.py        # nutrition_panel_png (/dieta), nutrition_chart_png (legacy), _ring
  handlers.py      # cmd_comi (guiado+one-shot), on_nutrition_button (nut:*), cmd_ref, cmd_dieta,
                   # on_photo, on_text_macros (roteia sessão), cmd_cancelar
scripts/build_taco.py # transform da TACO oficial (repo machine-learning-mocha/taco)
```
`custom_foods` tem coluna `source` (taco/ia/manual/foto). Tabelas criadas em `src/history_db.py::_init_db`.

## Deploy / Prod
- Servidor Oracle Cloud: `ubuntu@136.248.77.150` (hostname `bot`), `/home/ubuntu/readiness`,
  systemd `readiness-bot.service`, `.venv`. Chave SSH: `Garmin/ssh-key-2026-06-17.key`.
- **Repo de deploy**: github.com/YuriMagalDev/**Readyness** (é o origin do servidor; projeto no root).
- **Cuidado com a topologia**: o repo LOCAL é a pasta home (`C:/Users/yurig/.git`), origin=**AgendaPsi
  (errado)**, projeto sob `Documents/Antigravity/Garmin/`, história NÃO-relacionada ao Readyness.
  O servidor tinha working tree divergente (editavam direto em prod sem commitar) — foi reconciliada
  em commits locais no server (backup tar + snapshot). Readyness GitHub segue stale (push pendente).
- **Como fiz deploy nesta sessão** (repetir): `tar czf - <arquivos> | ssh ... 'tar xzf -'` no
  `/home/ubuntu/readiness`; `pip install` se dep nova; edição cirúrgica do `main.py` do server pra
  registrar CommandHandler novo (NÃO sobrescrever o main.py — é divergente); `sudo systemctl restart
  readiness-bot`; commit local no git do server. Sempre `shred` a cópia da chave depois.
- `ANTHROPIC_API_KEY` setada no `.env` do server; `VISION_MODEL=claude-haiku-4-5-20251001`; `rapidfuzz` instalado.

## Estado dos testes
~359 testes passando local; suíte da nutrição roda no servidor também. TDD nas camadas puras;
handlers de IO cobertos por smoke de import + testes das funções puras (`format_*`, `parse_*`, `_comi_running`, `_ref_view` via store).

## Pendências / próximas frentes
- **Peso/BF**: confirmar 108/30 (prod) vs valores reais.
- Push do Readyness GitHub (precisa credencial no server) — hoje só o git local do server reflete prod.
- Arrumar origin errado do repo home (AgendaPsi) — dívida de infra.
- Minor abertos: `n_meals` ignora refeição sem rótulo; frescor/fonte por comida na UI ainda não aparece.
- Frentes maiores mapeadas: reestruturar saída diária em camadas veredito→motivo→plano;
  remover LLM local do resto do projeto; integrar nutrição mais fundo (segue como CONTEXTO, não veredito).

## Princípios a respeitar
- **Veredito de treino é determinístico por regra** (`compute_readiness`). Nutrição é CONTEXTO,
  nunca vira desconto/score. Decisão de treino é do usuário.
- Números de fonte real (TACO/custom/Garmin) onde dá; IA marcada `~IA` e confirmável (o usuário
  escolheu usar IA pra alimentos comuns — rastreável e cacheado).
- Bot sobe sem `ANTHROPIC_API_KEY` (foto/IA ficam off, resto funciona).
