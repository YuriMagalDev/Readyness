# Roadmap — Camada Temporal (carga, tendência, veredito proativo)

**Data:** 2026-06-20
**Status:** roadmap aprovado. Sub-projeto 1 tem spec próprio; 2/3/4 esboçados aqui, ganham spec quando chegar a vez.

## Problema

O app hoje **só olha HOJE**. O veredito ("treinar hoje?") lê só FC repouso vs média 7d, dívida de
sono, bateria e contagem crua de corridas. Consequências:

- **Check-in não fecha o loop** — soreness/energia/hidratação/alimentação são gravados, aparecem em
  `/metrics`, entram no prompt de insight da IA, mas **a regra do veredito os ignora**
  (`context_from_metrics` em `src/metric_reader.py:40` não os lê). Soreness=5 pode dar semáforo verde.
- **Carga é contagem crua** — `run_sessions_7d` só conta sessões; não distingue 5km easy de 15km tiro.
- **Sem memória de tendência** — não detecta FC repouso subindo, não estima risco de lesão, não planeja.

Quase toda melhoria boa vem de olhar a **série temporal**. A reforma é uma camada temporal que vira
fundação pra um veredito proativo.

## Decisões travadas (valem pros 4 sub-projetos)

- **Unidade de carga: TRIMP por FC** (Banister, homem). `duração × intensidade(FC)`. Fallback duração
  quando falta `avg_hr`. Padrão científico sem potência; encaixa no Forerunner 55 (tem FC por atividade).
- **FCmáx: observada + fallback fórmula.** Maior `max_hr` do histórico (≥90d); fallback Tanaka
  `208 − 0.7×idade`. Auto-corrige; grava no perfil quando estabilizar.
- **ACWR: EWMA** (média exponencial, τ=7d agudo / τ=28d crônico) — mais sensível que média simples.
- **Musculação fora** — só corrida/esteira/trail entra na carga (igual `job_runs`).
- **Veredito segue determinístico.** A camada nova alimenta a regra; LLM nunca decide treinar/não.
- **Dual-track** — a fundação adiciona métricas novas sem mexer no veredito atual; o veredito só muda
  no sub-projeto 2. Não quebra tela/comando existente.

## Decomposição

### Sub-projeto 1 — Camada de Carga/Tendência (FUNDAÇÃO) — *spec próprio*
`src/training_load.py` puro. TRIMP por sessão, ACWR (EWMA), monotonia (Foster), baseline rolante de FC
(30d). Saída: 3 métricas novas no catálogo (`acwr`, `training_monotony`, `resting_hr_baseline`) com
frescor. Aparecem em `/metrics` e `/semana`. **Não mexem no veredito ainda.**
→ Ver `2026-06-20-camada-carga-design.md`.

### Sub-projeto 2 — Veredito inteligente
`HealthMonitor.verdict` passa a ler a fundação + check-ins:
- soreness/energia entram na regra (fecha buraco #1): dor alta → rebaixa easy/rest mesmo com FC/bateria ok.
- ACWR zona risco (>1.5) → força easy/rest.
- **score 0-100 contínuo** (soma ponderada: FC vs baseline + dívida sono + ACWR + check-ins); semáforo
  derivado do score.
- **overreaching** multi-sinal: FC repouso ↑ vs baseline + ACWR alto + soreness alto = flag.
Determinístico. IA só comenta.

### Sub-projeto 3 — Proatividade
Job novo, bot cutuca sem ser pedido:
- alerta FC repouso subindo N dias vs baseline.
- **briefing semanal** (domingo): km, ACWR, sono médio, FCmáx, o que a semana pede.
- alerta ao cruzar zona ACWR de risco.

### Sub-projeto 4 — Plano adaptativo
`LLM_MODEL_DEEP`. Propõe a semana (long/tempo/easy/descanso) respeitando `dias_disponiveis_treino` +
meta (pace + hipertrofia); ajusta conforme ACWR/cumprimento. Sai do reativo.

## Ordem e dependências

```
1 Fundação  ──►  2 Veredito  ──►  3 Proatividade
       └──────────────────────►  4 Plano
```

Cada um entrega valor sozinho. 2/3/4 dependem de 1. Constrói 1 primeiro.
