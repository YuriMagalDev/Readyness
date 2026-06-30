# Nutrição: tracking de refeições + macros + energia (Telegram bot)

**Data:** 2026-06-30
**Status:** design aprovado
**Escopo:** primeira frente de evolução do GarminAI Coach. Registro de refeições em
linguagem natural → kcal/macros via tabela TACO (determinístico), com alvo diário
ciclado por treino e aviso de energia disponível. Foco: hipertrofia.

---

## Contexto

Usuário único (Yuri). Stats no `athlete_profile.json`: 25 anos, 108 kg, 181 cm, ~30% BF
→ massa magra (LBM) ≈ **75.6 kg**. Meta: hipertrofia / recomposição (leve déficit).

Mudança de premissa do projeto: **LLM local sai**. Chave da API Anthropic continua
disponível. Para nutrição o parsing é **100% determinístico** (tabela TACO); a API entra
só como *fallback* de parse e texto-coach, em frente futura. Isso reverte a regra antiga
do CLAUDE.md "nada de API paga" — atualizar o CLAUDE.md em tarefa separada.

Princípio mantido do projeto: **número sai de fonte real (tabela TACO), nunca inventado**.
Match abaixo do limiar = pergunta ao usuário, jamais chuta valor.

---

## Arquitetura

Módulo novo `src/nutrition/`, isolado, testável por unidade:

- **`food_db.py`** — carrega a TACO (CSV embarcado, ~600 itens, valores por 100 g:
  kcal, proteína, carbo, gordura) **+ os itens de `custom_foods`** (cadastrados pelo
  usuário). Expõe:
  - lookup exato por nome normalizado (custom_foods tem prioridade sobre TACO);
  - match fuzzy (`rapidfuzz`) com limiar; abaixo do limiar → "não reconhecido";
  - tabela de **aliases** (ex.: `frango` → `peito de frango grelhado`);
  - tabela de **porções unitárias** (ex.: `1 ovo` = 50 g, `1 banana` = 100 g,
    `1 fatia de pão` = 25 g).
  - Não achou em lugar nenhum → dispara o **cadastro manual** (uma vez).
- **`meal_parser.py`** — função pura. Texto da refeição → lista de itens
  `{food, grams, kcal, p, c, g}`. Patterns: `100g arroz`, `200 g peito de frango`,
  `2 ovos`, `1 fatia pão`. Itens sem match viram `{raw, recognized: false}`.
- **`targets.py`** — funções puras de alvo do dia e energia:
  - TDEE base (sem exercício) via Katch-McArdle sobre LBM;
  - alvo ciclado (descanso vs treino), proteína fixa, gordura fixa, carbo = resto;
  - energia disponível (EA) e classificação em faixas.
- **`charts` (em `bot/charts.py`)** — `nutrition_chart_png(...)` segue o padrão
  existente (matplotlib `Agg` → `io.BytesIO`, dpi 120).

### Dados (SQLite — tabelas novas no `history.db`)

```
meal_log(date TEXT, meal TEXT, food TEXT, grams REAL,
         kcal REAL, p REAL, c REAL, g REAL, logged_at TEXT)

day_plan(date TEXT PRIMARY KEY, vai_treinar INT, vai_correr INT, set_at TEXT)

-- itens cadastrados manualmente quando não estão na TACO.
-- base_unit: "100g" (valores por 100 g) ou "porcao" (valores por 1 unidade/scoop).
-- porcao_g: gramas por porção quando base_unit="porcao" (opcional, informativo).
custom_foods(name TEXT PRIMARY KEY, base_unit TEXT, porcao_g REAL,
             kcal REAL, p REAL, c REAL, g REAL, created_at TEXT)
```

`meal_log` e `day_plan` ficam legíveis por camadas futuras (prontidão), mas **não**
são acoplados a elas agora (YAGNI).

---

## Cálculo de alvos (números do usuário)

- **LBM** = 108 × (1 − 0.30) = 75.6 kg
- **BMR** (Katch-McArdle) = 370 + 21.6 × 75.6 ≈ **2000 kcal**
- **TDEE base** (sem exercício, fator NEAT ~1.3) ≈ **2600 kcal**
- **Dia descanso:** alvo ≈ 2100 kcal (déficit −500, recomposição)
- **Dia treino/corrida:** 2100 **+ kcal do exercício** (vindo do Garmin) →
  preserva energia disponível
- **Proteína:** fixa **165 g/dia** (≈ 2.2 g/kg LBM), todo dia
- **Gordura:** ≈ 60 g/dia (≈ 0.8 g/kg LBM)
- **Carbo:** preenche o restante das calorias (sobe em dia de treino)

Todos os parâmetros (déficit, fatores, alvos) ficam configuráveis no
`athlete_profile.json`; os números acima são os defaults.

### Energia disponível (EA)

```
EA = (kcal ingerida − kcal exercício do dia) / LBM
```

- EA < 25 → 🔴 "comendo pouco demais pra treinar/recuperar — risco de perda muscular"
- 25 ≤ EA < 30 → 🟡 "ok pra cut curto, fica de olho"
- EA ≥ 30 → 🟢

Limiares configuráveis.

---

## Fluxo do bot

### Pergunta da manhã (job proativo)

Job diário manda:

```
Bom dia. Hoje você vai:
[🏋 treinar] [🏃 correr] [💪🏃 os 2] [😴 descanso]
```

Callback grava `day_plan` e fixa o alvo de kcal/macro do dia.

### `/comi <texto>` — registrar refeição

```
/comi almoço: 100g arroz, 200g peito de frango, 1 ovo
```

Bot **ecoa antes de salvar** (passo de confirmação — substitui a segurança que o LLM daria):

```
🍽 Almoço
• arroz cozido 100g → 128 kcal · P 2.5 · C 28 · G 0.2
• peito de frango grelhado 200g → 318 kcal · P 62 · C 0 · G 7
• ovo 1un (50g) → 72 kcal · P 6 · C 0.6 · G 5
─ total: 518 kcal · P 70 · C 29 · G 12
[✅ salvar] [✏️ corrigir]
```

- Item não reconhecido → **cadastro manual (uma vez)**:
  ```
  ❓ não conheço "whey Soldier". Cadastra pra eu lembrar sempre:
  é por 100g ou por porção/scoop?  [100g] [porção]
  → manda: kcal proteína carbo gordura  (ex.: 120 24 3 1.5)
  → porção: também quantos g tem 1 scoop (opcional)
  ```
  Grava em `custom_foods`; daí em diante o item é reconhecido local, instantâneo.
  O fluxo do `/comi` retoma com o item já calculado.
- `✏️ corrigir` → usuário reedita a linha; reprocessa.
- `✅ salvar` → grava em `meal_log`.
- `/comi` sem texto → ajuda + exemplo.

### `/dieta` — painel do dia (PNG matplotlib)

`nutrition_chart_png` renderiza, layout **anéis de progresso** (tema escuro):

- 1 anel grande central: **kcal** ingerida / alvo do dia (cor muda perto do alvo);
- 3 anéis menores: **proteína / carbo / gordura** (% do alvo);
- faixa lateral: **energia disponível** 🟢🟡🔴 com o valor;
- rodapé: nº de refeições + horário da última.

Mensagem acompanha o PNG com botão `[🗑 apagar última]` (desfaz último registro).

---

## Testes (TDD por camada, commits pequenos)

- **`food_db`**: match exato, fuzzy acima/abaixo do limiar, alias, porção unitária,
  alimento inexistente; `custom_foods` tem prioridade sobre TACO; cálculo por
  `base_unit` 100g vs porção/scoop.
- **`meal_parser`**: uma linha, múltiplos itens, unidade `g` vs unitária, texto-lixo,
  item não reconhecido marcado corretamente.
- **`targets`**: TDEE, ciclo descanso vs treino, EA nas três faixas, parâmetros do perfil.
- **handlers**: confirma → salva, corrige → reprocessa, `/dieta` agrega o dia certo,
  apagar última remove só o último, callback da manhã grava `day_plan`.

---

## Fora de escopo (YAGNI — frentes futuras)

- Histórico / gráfico de macros ao longo de dias.
- Foto de comida, código de barras.
- Busca online de alimentos (web/OpenFoodFacts) — substituído por cadastro manual.
- Integrar nutrição na pontuação de prontidão.
- Fallback de parse e texto-coach via API Anthropic.
- Remoção do LLM local do resto do projeto (frente separada).
- Reestruturar a saída diária em camadas (veredito → motivo → plano) (frente separada).
