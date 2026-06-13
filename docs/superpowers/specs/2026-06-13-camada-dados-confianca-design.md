# Spec — Camada de Dados + Confiança (Reformulação, parte 1/3)

**Data:** 2026-06-13
**Objetivo:** Centralizar um catálogo curado de ~20 métricas do Garmin (+ 4 check-ins manuais), guardando cada valor com seu frescor e fonte, e expor uma API que entrega valor + contexto de confiança por métrica.

## Contexto da reformulação

O app atual mostra pouco dado e não dá pra saber se o número é fresco, completo ou de quando é. A reformulação foi decomposta em camadas, construídas de baixo pra cima:

1. **Camada 1+2 — Dados + Confiança** (ESTE spec): ingestão do catálogo + tabela longa de métricas com frescor + API de leitura.
2. **Camada 3 — Análise rastreável** (spec futuro): análises diárias que mostram quais números geraram cada conclusão.
3. **Camada 4 — UI** (spec futuro): tela redesenhada que exibe muito dado sem poluir, com frescor visível e drill-down até a fonte. Aposenta `daily_snapshot`.

Este spec entrega software funcional e testável por conta própria (backend + API), sem depender das camadas seguintes.

## Decisões tomadas no brainstorming

- **Estratégia de ingestão:** catálogo curado (não "varre tudo"). ~20 métricas priorizadas pro objetivo (corrida + hipertrofia + composição corporal).
- **Frescor por métrica** (não por grupo nem global).
- **Modelo de dados:** tabela longa `metric_value` (1 linha por data+métrica), não snapshot largo.
- **Check-ins manuais:** hidratação, energia, soreness, alimentação — escala 1-5.
- **Transição:** dual-write (`metric_value` + `daily_snapshot`) pra não quebrar Hoje/Tendências atuais. `daily_snapshot` só aposenta na Camada 4.

## Catálogo de métricas

Registro **estático em código** (`src/metric_catalog.py`): lista de specs `MetricSpec(key, label, unidade, dominio, cadencia, source_default)`.

`cadencia` ∈ {`diaria`, `corpo`, `fitness`, `evento`} — define a janela de frescor (ver "Regras de status").

### Prontidão / treino (`dominio="prontidao"`)
| key | label | unidade | cadência | endpoint Garmin |
|---|---|---|---|---|
| `training_readiness` | Training readiness | "" | diaria | `get_morning_training_readiness` |
| `vo2max` | VO2max | "" | fitness | `get_max_metrics` |
| `endurance_score` | Endurance score | "" | fitness | `get_endurance_score` |
| `race_pred_5k` | Prova 5k | "time" | fitness | `get_race_predictions` |
| `race_pred_10k` | Prova 10k | "time" | fitness | `get_race_predictions` |
| `race_pred_21k` | Prova 21k | "time" | fitness | `get_race_predictions` |
| `race_pred_42k` | Prova 42k | "time" | fitness | `get_race_predictions` |
| `training_status` | Training status | "" | diaria | `get_progress_summary_between_dates` (se disponível; ausente se vazio) |

### Recuperação / sono (`dominio="recuperacao"`)
| key | label | unidade | cadência | endpoint |
|---|---|---|---|---|
| `sleep_hours` | Sono | " h" | diaria | `get_sleep_data` |
| `sleep_deep_h` | Sono profundo | " h" | diaria | `get_sleep_data` |
| `sleep_light_h` | Sono leve | " h" | diaria | `get_sleep_data` |
| `sleep_rem_h` | Sono REM | " h" | diaria | `get_sleep_data` |
| `resting_hr` | FC repouso | " bpm" | diaria | `get_rhr_day` / `get_stats_and_body` |
| `hrv_overnight` | HRV noturno | " ms" | diaria | `get_hrv_data` (ausente se FR55 não gravar) |
| `body_battery_high` | Body Battery alta | "" | diaria | `get_body_battery` |
| `body_battery_low` | Body Battery baixa | "" | diaria | `get_body_battery` |
| `stress_avg` | Stress médio | "" | diaria | `get_stress_data` |
| `stress_max` | Stress máx | "" | diaria | `get_stress_data` |
| `respiration_avg` | Respiração | " rpm" | diaria | `get_respiration_data` |
| `spo2_avg` | SpO2 | "%" | diaria | `get_spo2_data` |

### Atividade diária (`dominio="atividade"`)
| key | label | unidade | cadência | endpoint |
|---|---|---|---|---|
| `steps` | Passos | "" | diaria | `get_stats_and_body` |
| `floors` | Andares | "" | diaria | `get_stats_and_body` |
| `intensity_minutes` | Min. intensidade | " min" | diaria | `get_stats_and_body` |
| `calories_total` | Calorias | " kcal" | diaria | `get_stats_and_body` |

### Corpo (`dominio="corpo"`)
| key | label | unidade | cadência | endpoint |
|---|---|---|---|---|
| `weight_kg` | Peso | " kg" | corpo | `get_body_composition` / `get_daily_weigh_ins` |
| `body_fat_pct` | % gordura | "%" | corpo | `get_body_composition` |
| `lean_mass_kg` | Massa magra | " kg" | corpo | `get_body_composition` |

### Check-ins manuais (`dominio="checkin"`, `source_default="manual"`, escala 1-5)
| key | label | rótulos |
|---|---|---|
| `hidratacao` | Hidratação | 1 Muito pouca · 2 Pouca · 3 Ok · 4 Boa · 5 Ótima |
| `energia` | Energia/disposição | 1-5 |
| `soreness` | Dor muscular | 1-5 |
| `alimentacao` | Qualidade alimentação | 1-5 |

Métricas marcadas como "ausente se vazio" (HRV, training_status) entram no catálogo mas, quando o endpoint não retorna, não geram linha e a API as reporta como ⚪ ausente.

## Modelo de dados

Nova tabela em `history.db`:

```sql
CREATE TABLE IF NOT EXISTS metric_value (
  date TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  value REAL,
  measured_at TEXT,        -- ISO datetime de quando o dado foi medido
  source TEXT NOT NULL,    -- 'garmin' | 'manual' | 'estimado'
  PRIMARY KEY (date, metric_key)
);
```

- `value` REAL: predições de prova guardadas em **segundos** (formatação mm:ss é responsabilidade da UI, Camada 4). Check-ins 1-5.
- `measured_at`: da resposta Garmin quando houver (ex: hora da pesagem, hora do sono); senão hora do fetch.
- `status` **não** é coluna — é calculado na leitura (ver abaixo).

`activity` e `weekly_plan` permanecem como hoje (treinos ganham séries/reps — ver "Atividades"). `daily_snapshot` permanece e segue recebendo dual-write até a Camada 4.

### Acessores em `HistoryDB`
```python
def upsert_metric(self, date, metric_key, value, measured_at, source) -> None
def get_metrics(self, date) -> list[dict]   # linhas brutas do dia
def get_metric_series(self, metric_key, start, end) -> list[dict]  # pra tendências futuras
```

## Regras de status (calculadas na leitura)

Dado `hoje` e a `cadencia` da métrica:

| status | condição |
|---|---|
| 〰️ `estimado` | `source == "estimado"` (ex: predições de prova) |
| ⚪ `ausente` | sem linha `metric_value` pra métrica na janela |
| 🟢 `fresco` | tem valor e `measured_at` dentro da janela |
| 🟡 `velho` | tem valor mas `measured_at` fora da janela |

Janelas por cadência:
- `diaria`: fresco = medido **hoje**; senão velho.
- `corpo`: fresco = `measured_at` ≤ **7 dias**; senão velho.
- `fitness`: fresco = `measured_at` ≤ **14 dias**; senão velho.
- `evento`: sem frescor diário — exibe a data do evento (status sempre `fresco` se existe).

Carry-forward: a leitura de uma métrica `corpo`/`fitness` busca o valor mais recente ≤ a data pedida e aplica a janela. Ex: peso medido há 3 dias → 🟢 dentro de 7d, com `measured_at` real.

`race_pred_*` têm `source="estimado"` → status `estimado` sempre (Garmin estima, não mede), mas mantêm `measured_at` da geração.

## Ingestão

Estende o `Ingestor` atual. Um **coletor por domínio** (`src/collectors/`), cada um com:
- `endpoints`: quais métodos do `GarminClient` chamar.
- `normalize(raw, day) -> list[MetricRow]`: converte resposta crua em linhas `(metric_key, value, measured_at, source)`.

Fluxo de `sync_today` (e `backfill`):
1. Para cada coletor, puxa endpoint(s) via `GarminClient` (cache + retry de rate-limit já existentes; `sleeper` entre chamadas).
2. Normaliza → linhas.
3. `db.upsert_metric(...)` pra cada linha. Endpoint vazio → nenhuma linha.
4. **Dual-write:** monta também o `snapshot` atual (via lógica existente) e `db.upsert_snapshot(...)`, pra Hoje/Tendências atuais não quebrarem.

`GarminClient` ganha os métodos novos que faltam (wrappers cacheados sobre `get_morning_training_readiness`, `get_max_metrics`, `get_endurance_score`, `get_hrv_data`, `get_respiration_data`, `get_spo2_data`, `get_stress_data`, `get_body_composition`, `get_floors` se necessário), seguindo o padrão `_cached(key, fetch_fn)`.

### Atividades — séries/reps
`activity_from_garmin` ganha um passo opcional: pra atividades de força, chamar `get_activity_exercise_sets(activity_id)` e guardar as séries/reps em `activity.sets_json` (nova coluna TEXT). Normalização tolerante a ausência.

## Check-ins manuais

`POST /api/checkin` — body `{hidratacao?, energia?, soreness?, alimentacao?}` (cada 1-5, todos opcionais).
- Para cada campo presente: `db.upsert_metric(hoje, key, valor, measured_at=now, source="manual")`.
- Reenviar no mesmo dia sobrescreve (PK date+metric_key).
- Validação: valor inteiro 1-5; fora disso → 422.

## API de leitura

`GET /api/metrics?date=YYYY-MM-DD` (default hoje) → 
```json
{
  "date": "2026-06-13",
  "dominios": {
    "prontidao": [ {"key","label","value","unidade","measured_at","status","source"}, ... ],
    "recuperacao": [...], "atividade": [...], "corpo": [...], "checkin": [...]
  }
}
```
Monta cruzando o **catálogo** (todas as métricas esperadas) com `metric_value` (o que existe), aplicando as regras de status. Métrica do catálogo sem dado → entra com `value=null`, `status="ausente"`.

Rotas existentes (`/api/today`, `/api/trends`, etc.) seguem funcionando via dual-write — intocadas neste spec.

## Estrutura de arquivos

```
src/
  metric_catalog.py        # MetricSpec + CATALOG (lista estática) + janelas de cadência
  metric_status.py         # compute_status(spec, measured_at, today) → str
  collectors/
    __init__.py            # registry de coletores
    base.py                # interface Collector (endpoints, normalize)
    prontidao.py
    recuperacao.py
    atividade.py
    corpo.py
  ingestor.py              # estendido: roda coletores + dual-write
  garmin_client.py         # + wrappers cacheados novos
  history_db.py            # + metric_value + acessores
api/
  services.py              # + build_metrics(db, date)
  main.py                  # + GET /api/metrics, POST /api/checkin
```

## Testes

- `metric_value`: upsert/PK/sobrescrita; `get_metrics`, `get_metric_series`.
- `metric_status.compute_status`: cada combinação status × cadência, com `today` fixo (fresco/velho por janela diaria/corpo/fitness; estimado; ausente quando `measured_at=None`).
- Catálogo: integridade (keys únicas, cadência válida).
- Cada normalizador de coletor: amostra crua representativa do Garmin → linhas esperadas com `value`, `measured_at`, `source` corretos; resposta vazia → lista vazia.
- `Ingestor`: dual-write grava `metric_value` **e** `daily_snapshot` (mock client); coletor com endpoint vazio não gera linha.
- `build_metrics`: agrupa por domínio; métrica ausente do catálogo aparece com `status="ausente"`; carry-forward de peso retorna `measured_at` real.
- `POST /api/checkin`: grava linhas manuais; valor fora de 1-5 → 422; reenvio sobrescreve.
- `GET /api/metrics`: estrutura de domínios, status correto (TestClient).

## Não-objetivos (YAGNI)

- Sem varredura de todos os ~80 endpoints — só o catálogo curado.
- Sem UI nova (Camada 4); este spec entrega backend + API.
- Sem análise/insight novo (Camada 3).
- Sem aposentar `daily_snapshot` agora (só na Camada 4).
- Sem coletar domínios irrelevantes ao FR55 (potência, FTP cycling, golf, gestação, etc.).
