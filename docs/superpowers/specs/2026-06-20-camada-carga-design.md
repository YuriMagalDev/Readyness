# Spec — Sub-projeto 1: Camada de Carga/Tendência (fundação)

**Data:** 2026-06-20 · **Roadmap pai:** `2026-06-20-camada-temporal-roadmap.md`

## Objetivo

Transformar atividades cruas (já no DB) numa série temporal de **carga de treino** e expor 3 métricas
derivadas com frescor: `acwr`, `training_monotony`, `resting_hr_baseline`. Pura, determinística, sem IA,
sem rede. **Não mexe no veredito** (dual-track) — só adiciona métricas que `/metrics` e `/semana` mostram.
Vira a base que o sub-projeto 2 (veredito inteligente) vai consumir.

## Princípios herdados (CLAUDE.md)

- Frescor por métrica sempre visível. Carga estimada (sem FC) marcada como `estimado`, não `fresco`.
- Determinístico. Nenhuma chamada de LLM neste sub-projeto.
- Forerunner 55: metade dos dados pode faltar. Funções degradam (fallback), nunca quebram.

## Componentes

### 1. `src/training_load.py` (módulo novo, puro)

Funções sobre rows de `activity` (dict com `type`, `is_strength`, `duration_min`, `avg_hr`, `max_hr`)
e a série de `resting_hr`. Nada de IO próprio — recebe dados, devolve números.

**`session_trimp(activity, hr_rest, hr_max) -> (float, bool)`**
Banister TRIMP (homem). Retorna `(carga, estimado)`.
```
HRr   = clamp((avg_hr − hr_rest) / (hr_max − hr_rest), 0, 1)
trimp = duration_min × HRr × 0.64 × e^(1.92 × HRr)
```
- Sem `avg_hr` (ou `hr_max ≤ hr_rest`): fallback `carga = duration_min`, `estimado=True`.
- Sem `duration_min`: carga `0.0`, `estimado=True`.
- `is_strength=1` ou `type` fora de `RUN_TYPES` → não é chamado (filtrado antes).

**`estimate_hr_max(activities, idade) -> int`**
Maior `max_hr` observado nas atividades (corrida, ≥90d) **se** ≥ a fórmula; senão **Tanaka**
`round(208 − 0.7 × idade)`. Garante que ruído baixo não derruba a FCmáx. (idade vem de
`athlete_profile.json`.)

**`daily_load_series(activities, hr_rest_by_date, hr_max) -> dict[date_iso, float]`**
Soma TRIMP das corridas por dia. Dias sem corrida = `0.0` (importante: ACWR precisa dos zeros).

**`ewma(series_by_date, end_date, tau_days, span_days) -> float`**
Média exponencial da carga diária terminando em `end_date`, peso `α = 2/(tau+1)`, sobre os últimos
`span_days` (preenche dias faltantes com 0). Determinística.

**`acwr(series, end_date) -> (float|None, str)`**
`agudo = ewma(τ=7, span=7)`, `cronico = ewma(τ=28, span=28)`. Razão `agudo/cronico`.
- `cronico == 0` (sem histórico) → `(None, "ausente")`.
- Zona: `<0.8 "baixo"` · `0.8..1.5 "otimo"` · `>1.5 "risco"`. Mapa com fallback `"otimo"` p/ valor inesperado.

**`monotony(series, end_date) -> float|None`** (Foster)
`média(carga diária 7d) / desvio-padrão(7d)`. Desvio 0 (carga constante) → `None`.

**`resting_hr_baseline(hr_series, end_date) -> (float|None, float|None)`**
Média de `resting_hr` dos últimos 30d → `(baseline, desvio_do_dia)`. Sem dados → `(None, None)`.

### 2. Catálogo — 3 métricas novas (`src/metric_catalog.py`)

```python
MetricSpec("acwr", "Carga aguda:crônica", "", "prontidao", "diaria", "computed"),
MetricSpec("training_monotony", "Monotonia", "", "prontidao", "diaria", "computed"),
MetricSpec("resting_hr_baseline", "FC repouso (base 30d)", " bpm", "recuperacao", "diaria", "computed"),
```
Novo `source_default="computed"`. `compute_status` (verificado em `src/metric_status.py`) já trata isso
sem mudança: `computed` ≠ `estimado` e tem `measured_at` → frescor pela cadência `diaria` (window 0) →
`fresco` no dia em que foi computada. Nenhuma alteração em `metric_status.py`.

### 3. Ingestor — dual-write (`src/ingestor.py`)

Após ingerir atividades+sono do dia, computar e gravar as 3 métricas em `metric_value` (mesmo caminho de
escrita das outras métricas), `measured_at = agora`, `source = "computed"`. Assim:
- `read_metrics` pega elas naturalmente (sem special-case).
- histórico acumula → `/semana` e `/mes` ganham série.
- carga estimada (algum dia sem FC na janela) reflete no frescor.

Se faltar dado (ACWR sem crônico, etc.): **não grava** a métrica daquele dia (fica `ausente` honesto),
em vez de gravar `None`. Mesmo espírito do `store_if` do sono.

## Fora de escopo (vai pros próximos sub-projetos)

- Mudar `HealthMonitor.verdict` / `context_from_metrics` — sub-projeto 2.
- Score 0-100, overreaching, alertas, briefing, plano.

## Testes (TDD por função)

1. `session_trimp`: FC conhecida → valor esperado (caso de referência calculado à mão); HRr clampado;
   fallback sem `avg_hr` retorna `(duration_min, True)`; sem duração `(0.0, True)`.
2. `estimate_hr_max`: observada > fórmula usa observada; observada < fórmula usa Tanaka(25)=190; sem
   atividades usa fórmula.
3. `daily_load_series`: agrupa por dia, zera dias sem corrida, ignora `is_strength`.
4. `ewma`: série sintética → valor determinístico conhecido; preenche faltantes com 0.
5. `acwr`: série crescente → razão >1; sem crônico → `(None,"ausente")`; zonas nos limiares 0.8 e 1.5.
6. `monotony`: série conhecida; carga constante → `None`.
7. `resting_hr_baseline`: média 30d + desvio do dia; sem dados → `(None,None)`.
8. Ingestor: grava as 3 com `source="computed"`; não grava quando dado insuficiente; `read_metrics` as
   devolve com frescor; veredito **inalterado** (regressão — `context_from_metrics` igual).

## Verificação end-to-end

- Suite verde (incl. testes acima).
- `/metrics` mostra as 3 métricas novas com frescor correto.
- `/semana` reflete série de ACWR sem quebrar gráfico.
- Veredito de `/saldo` **idêntico** ao de antes (dual-track confirmado).
