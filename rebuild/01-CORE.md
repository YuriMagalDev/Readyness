# CORE — GarminAI Coach

## Conceito

App local (desktop, 1 usuário) de coaching de saúde e treino. Integra dados do **Garmin
Connect (Forerunner 55)** com uma **LLM local** para gerar uma análise diária confiável:
"posso treinar hoje? em que intensidade?" + insights rastreáveis até os números.

Atleta-alvo: objetivo corrida (pace) + hipertrofia. O perfil do atleta (idade, peso, altura,
objetivo, dias disponíveis) fica num `athlete_profile.json` local, incluído como contexto
em todo prompt. Nunca enviar perfil à API do Garmin. Campos nulos: perguntar, não inventar.

## A dor que o app resolve

1. **Pouco dado** — centralizar tudo que dá pra puxar do Garmin.
2. **Confiança no dado** — saber se cada número é fresco, completo, "de quando é".
3. **Confiança na análise** — entender de onde a IA tirou cada conclusão.

## Arquitetura em 3 camadas (construir de baixo pra cima)

### Camada 1 — Dados + Confiança
- **Catálogo curado** (~20 métricas) definido estático em código: cada métrica tem
  `key, label, unidade, domínio, cadência`. Domínios: prontidão, recuperação, atividade,
  corpo, check-in. NÃO varrer todos os endpoints — catálogo priorizado pro objetivo.
- **Tabela longa `metric_value(date, metric_key, value, measured_at, source)`** (PK
  date+metric_key). Métrica nova = nova linha, zero migração. Predições de prova guardadas
  em segundos (formatar na UI). Check-ins manuais entram aqui com `source="manual"`.
- **Coletores por domínio**: funções puras `normalize(raw, day) -> [rows]`. Só emitem linha
  quando há valor (campo ausente → sem linha; a API marca como ausente via catálogo).
- **Frescor calculado na leitura** (não é coluna). Status por métrica:
  - `estimado` se `source=estimado` (ex: predições de prova) — tem precedência.
  - `ausente` se não há valor na janela.
  - `fresco` se medido dentro da janela da cadência; senão `velho`.
  - Janelas: diária = hoje (0d); corpo = 7d; fitness (VO2/endurance/predições) = 14d;
    evento = sempre fresco se existe. Carry-forward: corpo/fitness buscam o último valor
    ≤ data e aplicam a janela.
- **Cache obrigatório** antes de qualquer chamada Garmin (TTL ~6h). Tratar rate-limit com
  retry + backoff. Mascarar credenciais em logs.
- **Check-ins manuais 1-5** (decisão de produto): hidratação, energia, dor muscular
  (soreness), qualidade da alimentação. Entram no `metric_value` e alimentam a análise.

Métricas do catálogo (referência): training_readiness, vo2max, endurance_score,
race_pred_5k/10k/21k/42k (estimado), sleep_hours/deep/light/rem, resting_hr, hrv_overnight,
body_battery_high/low, stress_avg/max, respiration_avg, spo2_avg, steps, floors,
intensity_minutes, calories_total, weight_kg, body_fat_pct, lean_mass_kg + os 4 check-ins.

### Camada 2 — Análise diária rastreável
- **Veredito determinístico por REGRA** (não LLM): semáforo verde/amarelo/vermelho +
  recomendação. Regras (ajustáveis): FC repouso ≥5 bpm acima da média 7d → vermelho;
  Body Battery matinal < 25 → amarelo; dívida de sono semanal ≥ 2h → amarelo; senão verde.
  O contexto dessas regras é montado a partir do `metric_value` (FC hoje, média 7d, bateria,
  dívida de sono, nº de corridas na semana).
- **Insights rastreáveis (LLM)**: alimenta a LLM com a lista de métricas disponíveis
  (`[{key,label,valor,status}]`); ela devolve 2-5 observações curtas, cada uma citando as
  `keys` que usou. **Validação**: descarta keys que não foram alimentadas; se um insight
  fica sem nenhuma fonte válida, **descarta o insight inteiro** (sem fonte = não confiável).
  Resolve key → `{label, valor, unidade, status}` pra exibir como "chips" de fonte.
- **Cache da análise por dia** (recompute só sob botão "regenerar"). Não cachear fallback.

### Camada 3 — UI ("Hoje") — ver 02-DESIGN.md

## API (FastAPI)

- `GET /api/metrics?date=` → catálogo × valores agrupados por domínio, cada métrica com
  `{key,label,value,unidade,measured_at,status,source}`.
- `POST /api/checkin` → grava check-ins manuais (valida inteiro 1-5; sobrescreve o do dia).
- `GET /api/analysis?date=` / `POST` (force) → `{date, veredito{status,motivo,recomendacao},
  insights:[{texto, metricas_usadas:[{key,label,valor,unidade,status}]}]}`.
- `POST /api/sync` → ingestão do dia (puxa Garmin → grava metric_value).
- Padrão de erro: wrapper que devolve `{erro}` com 503/502; UI mostra banner.

## Regras de ouro

1. Cache primeiro (nunca rechamar Garmin/LLM se já tem dado fresco).
2. Frescor por métrica, visível — é o que constrói confiança.
3. Insight sem fonte real é descartado.
4. Veredito é regra, não LLM.
5. LLM local (ver 03) — sem provedor pago, sem dado sensível saindo da máquina.
6. TDD por camada, commits pequenos, dual-write se precisar migrar sem quebrar telas antigas.

## Estrutura sugerida

```
src/
  metric_catalog.py     # MetricSpec + CATALOG + janelas de cadência
  metric_status.py      # compute_status(cadencia, source, measured_at, today)
  metric_reader.py      # read_metrics (catálogo×valores+status) + context_from_metrics
  collectors/           # normalizadores puros por domínio
  garmin_client.py      # wrappers cacheados + retry de rate-limit
  history_db.py         # metric_value + atividades + acessores (sqlite)
  ingestor.py           # roda coletores → grava metric_value
  daily_analysis.py     # veredito (regra) + insights (LLM local + validação)
  llm.py                # cliente da LLM local (ver 03)
api/
  services.py · main.py
web/                    # React/Vite
```
