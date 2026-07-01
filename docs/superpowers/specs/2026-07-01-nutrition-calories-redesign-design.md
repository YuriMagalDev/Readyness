# Nutrição — Redesign do cálculo de calorias (perfil vivo)

> Spec de 2026-07-01. Reformula como o alvo de kcal/macros é **calculado, sugerido e mostrado**.
> Substitui o cálculo estático atual (carbo = sobra, deficit fixo 500, BF chutado, sem loop).

## Problema (estado atual)
`targets.day_target` hoje:
- Deficit fixo 500 em todo dia; dia treino só soma o gasto de exercício de volta.
- Proteína (165g) e gordura (60g) fixas; **carbo = sobra** → infla (dia treino passa de 300g).
- BF 30% é estimativa estática → LBM/TDEE nunca se corrige ao corpo real.
- Sem feedback de progresso: peso, ritmo, aderência não fecham o loop.

Dores relatadas: número parece errado, sugestão fraca, muito carbo, sem feedback de progresso.

## Objetivo
**Recomp equilibrada** rumo a 108→95kg. Carbo ciclado e **capado**, deficit **auto-corrigido**
por peso semanal + aderência, BF **estimado** que deriva do progresso. Bot **propõe**, usuário confirma
(alvo nunca muda sozinho — respeita o princípio determinístico).

Perfil de referência: 108 kg, 30% BF → LBM 75,6 kg. TDEE base (Katch-McArdle, NEAT 1,3):
`(370 + 21,6·75,6)·1,3 ≈ 2604 kcal` (já inclui vida leve, **não** inclui treino).

---

## Bloco 1 — Modelo de macro (carbo ciclado e capado)

Troca "carbo = sobra" por **alvos diretos**. Proteína e gordura viram **piso**; carbo é alvo por tipo de dia.

| Alvo | Valor | Racional |
|---|---|---|
| Proteína | **180g** piso | ~2,4 g/kg LBM — segura músculo no deficit |
| Gordura | **60g** piso | piso hormonal |
| Carbo dia descanso | **130g** | baixo, dia parado |
| Carbo dia treino/corrida | **200g** | suficiente pra treinar + correr com deficit |

**Binário que decide o carbo:** "treinou/vai treinar hoje?" (sim → 200g, não → 130g).
Não olha o número exato do Garmin → menos dependente do FR55.

### Piso de comida (deficit floor -900)
O gasto do dia (`TDEE_base + gasto ativo`) pode jogar o deficit fundo demais nos dias pesados.
Regra: **se `gasto_total − intake(carbo 200g) < -900`, sobe o carbo até o deficit voltar pra -900.**
Só morde em dia de gasto alto.

- `gasto_total = 2604 + gasto_ativo`
- `gasto_ativo` = Garmin active kcal (real); se ausente (FR55) → fallback tier fixo (treino 300 / corrida 400).
- `intake = 180·4 + 60·9 + carbo_g·4 = 1260 + carbo_g·4`

### Alvos resultantes (perfil de referência)

| Dia | Gasto ativo | Gasto total | Carbo | Intake | Deficit |
|---|---|---|---|---|---|
| Descanso | 0 | 2604 | 130g | 1780 | -824 |
| Só treino | 300 | 2904 | 200g | 2060 | -844 |
| Treino+corrida | 700 | 3304 | ~285g* | 2404 | **-900** (piso) |

\* piso libera carbo: `(2404 − 1260)/4 ≈ 285g`.

**Nota:** Garmin active kcal deixa de mudar o alvo de carbo base — serve pro **piso** e pra mostrar EA/saldo.

---

## Bloco 2 — Perfil vivo (peso semanal → auto-corrige)

Loop fechado que corrige o alvo ao corpo real.

### Captura de peso
- Tabela nova `weights(date, kg, source)`.
- **Job semanal** (domingo manhã, horário config) → bot pergunta *"peso da semana?"*.
- Comando `/peso 107.4` grava a qualquer momento (`source=manual`).
- Cadência semanal proposital: pesar todo dia é ruído.

### Tendência
- Média móvel de **2–3 semanas** (peso oscila com água/glicogênio; 1 ponto não decide).
- Ritmo = %/semana da tendência.

### Auto-correção (proposta, usuário confirma)
- Meta de ritmo recomp: perder **~0,3–0,4%/sem** (~-0,35 kg).
- Estagnou ≥2 sem **e** aderência boa → propõe **-100 kcal** (tira do carbo).
- Caindo rápido demais (>0,7%/sem, risco músculo) → propõe **+100 kcal** (no carbo).
- No ritmo → mantém.
- Proposta vem com botões `[✅ aplicar] [✋ manter]`. Aplicar grava o novo alvo no perfil.

### BF estimado (derivado)
- Assume composição da perda: **~85% gordura / 15% massa** (deficit moderado + proteína alta + treino).
- Cada peso novo → recalcula LBM → atualiza TDEE base → atualiza alvos.
- Marcado **"estimado"** na UI. Medida real (fita/DEXA) sobrescreve via comando.
- **Tensão com CONFIANÇA:** BF estimado é *inferido*, não medido. Mantido transparente (marcado + corrigível),
  aceito conscientemente pelo usuário. Nenhum outro número passa a ser inventado.

---

## Bloco 3 — Feedback de progresso + gate de aderência

### Mini-relatório (`/progresso` + resposta ao peso semanal)
- Peso: tendência (média móvel) e ritmo (%/sem) vs meta.
- BF estimado atual + LBM.
- Aderência da semana.
- Proposta de ajuste, se houver → `[✅ aplicar] [✋ manter]`.

### Gate de aderência
Antes de propor cortar kcal, olha se o usuário **seguiu o plano** (via `meal_log`, que já existe).
- **Aderência de um dia = bateu proteína (≥90% de 180g = 162g) E kcal dentro da banda (≤ alvo +150).**
- Semana boa = **≥5 de 7 dias** aderentes.
- Peso travado **+ aderência ruim** → bot diz *"segue o plano primeiro"*, **não** corta kcal.
- Peso travado **+ aderência boa** → propõe corte.
- (O gate vale só pro corte por estagnação. Ritmo rápido demais sempre pode propor +kcal.)

---

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `src/nutrition/config.py` | novos params: `protein_g=180`, `carb_rest_g=130`, `carb_train_g=200`, `deficit_floor=900`, `target_rate_pct`, `bf_fat_frac=0.85` |
| `src/nutrition/targets.py` | reescreve `day_target` (carbo ciclado + piso -900); mantém `energy_availability` |
| `src/nutrition/adaptive.py` | **novo** — tendência de peso, ritmo, proposta de ajuste, derivação de BF, gate de aderência |
| `src/nutrition/store.py` | CRUD `weights`; query de aderência sobre `meal_log` |
| `src/history_db.py` | tabela `weights` no `_init_db` |
| `bot/handlers.py` | `/peso`, `/progresso`, job peso semanal, botões aplicar/manter |
| `bot/jobs.py` | `job_weekly_weight` |
| `bot/charts.py` | linha de tendência de peso (opcional no relatório) |
| `athlete_profile.json` | bloco `nutricao` com params novos |

## Testes (TDD por camada pura)
- `targets`: carbo ciclado (descanso/treino), piso -900 libera carbo, gordura/proteína piso.
- `adaptive`: média móvel, ritmo %/sem, proposta ±100 nas faixas, derivação de BF (85/15), gate de aderência (5/7).
- `store`: weights CRUD, query de aderência.
- Handlers de IO: smoke de import + funções puras (padrão do projeto).

## Migração (sem quebrar tela antiga)
- Novos params entram com default no `config._DEFAULTS` → `day_target` antigo continua montando.
- `day_target` reescrito atrás dos mesmos campos de retorno (`kcal, protein_g, fat_g, carb_g`) → `/dieta` não quebra.
- `weights`/adaptive são aditivos; `/progresso` é comando novo.

## Riscos / notas
- **FR55 sem active kcal** → piso usa fallback tier fixo; alvo de carbo base não depende disso.
- **BF estimado** pode divergir do real com o tempo → relatório sempre mostra "estimado"; correção manual disponível.
- **Aderência** depende do usuário registrar refeições (`/comi`) — se registrar pouco, gate trava correção (comportamento correto: sem dado, não corta).

## Princípios respeitados
- Alvo determinístico por regra; ajuste só por **proposta confirmada**.
- Números de fonte real (peso digitado, Garmin, TACO); único inferido é BF, marcado.
- Bot sobe sem Anthropic; nada disso depende de LLM.
