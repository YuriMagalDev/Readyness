# Spec — Camada de Análise Rastreável (Reformulação, parte 2/3)

**Data:** 2026-06-13
**Objetivo:** Produzir a análise diária com insights cujas conclusões são rastreáveis até as métricas que as geraram, sobre a camada de dados+confiança (parte 1).

## Contexto

Parte 2 de 3 da reformulação. Depende da Camada 1+2 (já entregue): `metric_value`, catálogo, `build_metrics` (métricas × valores + status), check-ins manuais. A Camada 4 (UI) consumirá o endpoint criado aqui.

Dor do usuário: "não sei confiar nas análises". Solução: cada conclusão exibe as métricas que a embasaram, e o veredito do dia (treinar?) é determinístico (regra), não opinião do LLM.

## Decisões do brainstorming

- **Formato:** insights estruturados, cada um com sua lista de métricas-fonte.
- **Rastreabilidade:** LLM cita `keys`; nós validamos contra o que foi alimentado (descarta inventadas).
- **Escopo:** só a análise do dia (tendências e análise por treino ficam como estão).
- **Veredito:** determinístico via `health_monitor` (regra), não LLM.
- **Sem campo de "confiança" numérico** (a lista de fontes é o sinal).

## Payload da análise

```json
{
  "date": "2026-06-13",
  "veredito": { "semaforo": "amarelo", "motivo": "...", "recomendacao": "..." },
  "insights": [
    { "texto": "FC repouso subiu e bateria baixa indicam recuperação incompleta.",
      "metricas_usadas": [
        {"key": "resting_hr", "label": "FC repouso", "valor": 58, "unidade": " bpm", "status": "fresco"},
        {"key": "body_battery_high", "label": "Body Battery alta", "valor": 30, "unidade": "", "status": "fresco"}
      ] }
  ]
}
```

`insights` pode ser lista vazia (LLM falhou ou nada relevante) — o `veredito` sempre aparece.

## Arquitetura

Novo módulo `src/daily_analysis.py`:

```python
class DailyAnalysis:
    def __init__(self, db, llm=ask_coach):
        ...
    def build(self, date: str, today=None, force=False) -> dict:
        # 1. metrics = build_metrics(db, date)  → métricas achatadas {key,label,valor,status,unidade}
        # 2. veredito = HealthMonitor().check(context_from_metrics(db, date))
        # 3. insights = self._insights(metrics, force=force)  (LLM + validação, cacheado)
        # 4. retorna {date, veredito, insights}
```

- `build_metrics` (de `api/services.py`) é a fonte das métricas. Para evitar ciclo de import, a função de achatar (catálogo×valores) que o `build_metrics` já produz é reutilizada: `DailyAnalysis` recebe o resultado de `build_metrics` (injetado pelo `services`) ou chama um helper compartilhado em `src/`. Decisão: mover a lógica de leitura de métricas para `src/metric_reader.py` (`read_metrics(db, date, today) -> dict`), e tanto `api/services.build_metrics` quanto `DailyAnalysis` chamam ele. (Refatoração alvo: extrair de `build_metrics` o que hoje está em `services`.)

### `context_from_metrics(db, date, today)` — em `src/metric_reader.py`
Monta o dict que o `HealthMonitor.check` espera, a partir do `metric_value`:
- `resting_hr_today` = valor de `resting_hr` no dia (ou mais recente ≤ dia).
- `resting_hr_avg_7d` = média de `resting_hr` nos últimos 7 dias (via `get_metric_series`).
- `morning_battery_avg` = `body_battery_high` do dia (proxy; FR55 não tem battery matinal separada).
- `sleep_debt_hours` = soma dos déficits vs 7h dos últimos 7 dias de `sleep_hours`.
- `run_sessions_7d` = contagem de atividades de corrida nos últimos 7 dias (via `db.get_activities`).

Mantém a assinatura que `HealthMonitor.check` já consome (sem alterar health_monitor).

## Contrato do LLM + validação

`DailyAnalysis._insights(metrics, force)`:

1. Achata as métricas presentes (status ≠ ausente) numa lista `[{key,label,valor,status}]`.
2. Prompt (Haiku) pede JSON:
   ```
   {"insights": [{"texto": "...", "metricas_usadas": ["resting_hr", "body_battery_high"]}]}
   ```
   Instrução: 2-5 insights, 1 frase cada, citar só keys da lista fornecida.
3. Parse tolerante (reusa `_parse_json` do `insight_engine`).
4. **Validação:** para cada insight, filtra `metricas_usadas` mantendo só keys presentes no conjunto alimentado; resolve cada key → `{key,label,valor,unidade,status}` (do catálogo + valor). Se sobrar 0 keys válidas, **descarta o insight**.
5. Cache: `ai_insights` kind `daily_v2`, key `daily_v2:<date>`, payload = lista de insights resolvidos. `force=True` recomputa (já suportado). Fallback (LLM erro/JSON inválido) → `[]`, não cacheia.

Modelo: **Haiku** (`depth="quick"`).

## API

`api/services.build_analysis(db, client, date, force=False)`:
- Chama `DailyAnalysis(db).build(date, force=force)`.
- `client` reservado p/ futura necessidade (hoje a análise sai do db; mantido por simetria com outras `build_*`). Se não usado, omitir.

`api/main.py`:
- `GET /api/analysis?date=YYYY-MM-DD` (default hoje) → payload. `_safe(..., code=503)`.
- `POST /api/analysis` body `{date?}` → `build_analysis(..., force=True)`.

## Estrutura de arquivos

```
src/
  metric_reader.py     # read_metrics(db,date,today) + context_from_metrics(db,date,today)
  daily_analysis.py    # DailyAnalysis: veredito (health_monitor) + insights rastreáveis (LLM+validação)
api/
  services.py          # build_metrics passa a delegar a metric_reader.read_metrics; + build_analysis
  main.py              # + GET/POST /api/analysis
```

## Testes

- `metric_reader.read_metrics`: idêntico ao comportamento atual de `build_metrics` (mover testes existentes; manter verdes).
- `context_from_metrics`: FC média 7d correta; FC hoje = último; sleep_debt soma déficits; run_sessions conta corridas.
- `DailyAnalysis._insights`: 
  - LLM cita key válida → insight com fonte resolvida (label/valor/status corretos).
  - LLM cita key inexistente → removida; insight sem key válida → descartado.
  - LLM falha/JSON inválido → `[]`.
  - cache hit não rechama LLM (mock contado 1×); `force` rechama.
- `DailyAnalysis.build`: payload `{date, veredito, insights}`; veredito vem do health_monitor (mockado); insights=[] não quebra.
- `build_analysis` + rota `GET /api/analysis` (TestClient): estrutura; `POST` força.

## Não-objetivos (YAGNI)

- Sem rastreabilidade em tendências/treino (ficam como estão; expandir em spec futuro).
- Sem campo de confiança numérico.
- Sem veredito por LLM.
- Sem nova UI (Camada 4 consome este endpoint).
- Sem alterar `health_monitor` (só alimentá-lo via `context_from_metrics`).
