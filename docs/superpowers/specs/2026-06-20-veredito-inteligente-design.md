# Spec — Sub-projeto 2: Veredito Inteligente

**Data:** 2026-06-20 · **Roadmap pai:** `2026-06-20-camada-temporal-roadmap.md` · **Depende de:** sub-projeto 1 (camada de carga, já merged)

## Objetivo

Trocar o veredito atual (cascata first-match sobre 4 sinais) por um **score de prontidão 0-100**
determinístico que soma os sinais novos da camada de carga + os check-ins, deriva o semáforo de faixas,
e **cita os fatores** que o geraram. Fecha o buraco #1 (check-in soreness/energia hoje não entra no
veredito). Continua determinístico — LLM nunca decide.

## Princípios herdados (CLAUDE.md)

- **Veredito por regra**, nunca LLM. O treino do dia não depende da IA estar de pé.
- **Rastreável**: o veredito cita as métricas que o geraram (chips de fator).
- **Bom com metade vazia** (FR55): sinal ausente desconta 0 — só penaliza com evidência de problema.

## Decisões travadas (brainstorming)

- Score 0-100 é o motor; semáforo derivado de faixas.
- **ACWR pesa mais**; demais sinais peso médio.
- Faixas: **≥70 verde · 40-69 amarelo · <40 vermelho**.
- **Overreaching** (3 sinais ruins juntos) é o **único override**: crava vermelho ignorando o score.

## Modelo de score

`score = clamp(100 − Σ descontos, 0, 100)`. Cada sinal desconta por faixa de severidade. Sinal **ausente
desconta 0**.

| Sinal | chave(s) no context | Desconto |
|---|---|---|
| **ACWR** | `acwr` (float, zona derivada) | zona ótimo (0.8–1.5): 0 · zona baixo (<0.8): 0 · zona risco (>1.5): **−35** · ausente: 0 |
| FC repouso vs baseline | `resting_hr_today`, `resting_hr_baseline` → `desvio = today − baseline` | desvio ≤+2: 0 · +3..+5: **−12** · >+5: **−25** · baseline ausente: 0 |
| Soreness | `soreness` (1-5) | 1-2: 0 · 3: **−10** · 4: **−18** · 5: **−25** · ausente: 0 |
| Dívida de sono | `sleep_debt_hours` | <2: 0 · 2..4: **−10** · >4: **−20** |
| Energia | `energia` (1-5) | 4-5: 0 · 3: **−6** · 2: **−12** · 1: **−15** · ausente: 0 |
| Body battery | `morning_battery_avg` | ≥50: 0 · 25..49: **−8** · <25: **−15** |

Faixas de desvio de FC, soreness, energia usam limiares inclusivos como escritos (ex.: soreness `==3`
desconta 10; `>=4` cai nas faixas 18/25). Zona ACWR vem de `acwr_zone(acwr)` da camada de carga.

## Overreaching (override)

Se **todas** verdadeiras: `desvio_fc > +5` **E** `acwr_zone(acwr) == "risco"` **E** `soreness >= 4` →
veredito = vermelho, `motivo = "possível overreaching: FC acima da base, carga em risco e dor alta"`,
`recomendacao = "Descanso. 3 sinais de sobrecarga juntos."`, `overreaching = True`. Ignora o score (mas
o score ainda é calculado e devolvido pra exibição).

## Saída do veredito

`compute_readiness(context) -> dict`:
```python
{
  "status": "verde|amarelo|vermelho",
  "score": int,                      # 0-100
  "motivo": str,                     # top fatores que descontaram, ou "Métricas normais"
  "recomendacao": str,
  "overreaching": bool,
  "fatores": [                       # ordenado por desconto desc, só os que descontaram >0
    {"chave": "soreness", "label": "Dor muscular", "valor": 4, "desconto": 18},
    ...
  ],
}
```
- `motivo` quando score perfeito / nenhum fator: `"Métricas normais"`.
- `motivo` caso geral: junta os 2-3 maiores fatores em pt-BR, ex.: `"dor muscular 4; dívida de sono 3.0h"`.
- `recomendacao` por status: verde `"Pode treinar conforme planejado."` · amarelo `"Treino leve ou
  moderado; evite intensidade alta."` · vermelho `"Priorize recuperação. Evite treino intenso."`
  (overreaching tem recomendação própria, acima).

## Arquitetura

### `src/readiness_score.py` (módulo novo, puro)
- `_deduction_acwr(acwr)`, `_deduction_hr(today, baseline)`, `_deduction_soreness(v)`,
  `_deduction_sleep(debt)`, `_deduction_energia(v)`, `_deduction_battery(b)` — cada um retorna
  `(desconto:int, fator_dict|None)`. Funções pequenas, testáveis isoladas.
- `compute_readiness(context)` — soma descontos, monta fatores ordenados, calcula score+clamp, deriva
  status por faixa, aplica override de overreaching, monta motivo/recomendação.
- Constantes de limiar e desconto no topo do módulo (nomeadas), não mágicas espalhadas.

### `src/metric_reader.py` — estender `context_from_metrics`
Hoje retorna 5 chaves. Passa a incluir também (lendo o dia via `db.get_metrics(date)` + séries já usadas):
`acwr` (float|None), `soreness` (int|None), `energia` (int|None), `resting_hr_baseline` (float|None).
`resting_hr_today` já existe. As 5 chaves antigas permanecem (não remover — outros consumidores).

**Cross-track deliberado:** o teste `test_context_ignora_metricas_de_carga` (sub-projeto 1, Task 10) trava
o context nas 5 chaves antigas. Ele é **atualizado** aqui para refletir as chaves novas — era um lock do
dual-track durante a fundação, agora cruzamos de propósito.

### `src/health_monitor.py` — `HealthMonitor.verdict`
Delega para `compute_readiness(context)`. Remove a cascata `_evaluate_rules` do caminho do veredito
(mantê-la só se algum outro chamador usar — verificar; `check()`/`ask_coach` usa `_evaluate_rules` como
preliminar, então manter `_evaluate_rules` mas `verdict` passa a usar `compute_readiness`). O `daily_analysis`
chama `HealthMonitor().verdict(context)` — ganha score+fatores automaticamente.

### `bot/messages.py` — `format_saldo`
Mostra o score e os chips de fator junto do semáforo. Ex.: `🟡 Amarelo · prontidão 58/100` + linha de
fatores `dor 4 · sono −3h`. Degrada se `fatores` vazio (mostra só o semáforo, como hoje).

## Fora de escopo (próximos sub-projetos)

- Proatividade / alertas / briefing semanal (sub-projeto 3).
- Plano adaptativo (sub-projeto 4).
- Ajuste fino dos pesos por aprendizado de histórico (futuro).

## Testes (TDD)

1. Cada `_deduction_*`: cada faixa retorna o desconto certo + fator; valor ausente (None) → `(0, None)`.
2. `compute_readiness`: dia tudo bom (sem descontos) → score 100, verde, motivo "Métricas normais",
   fatores [].
3. Faixas de status: score 70 → verde; 69 → amarelo; 40 → amarelo; 39 → vermelho.
4. Clamp: descontos somando >100 → score 0 (não negativo).
5. Fatores ordenados por desconto desc; só os >0; motivo cita os top 2-3.
6. Overreaching: os 3 gatilhos juntos → vermelho + `overreaching=True` mesmo com outros sinais ótimos
   (score calculado mas ignorado pra cor).
7. Ausência não penaliza: context só com `resting_hr_today` ruim e resto None → desconta só FC.
8. `context_from_metrics` estendido: devolve as chaves novas com valores do DB; chaves ausentes → None.
9. Regressão atualizada: `verdict` agora devolve `score`+`fatores`; status coerente com o score.
10. `format_saldo` renderiza score+fatores e degrada sem fatores.

## Verificação end-to-end

- Suite verde.
- `/saldo` mostra score + fatores; veredito coerente (ex.: soreness 5 derruba pra amarelo/vermelho —
  buraco #1 fechado).
- IA fora do ar → veredito (regra) continua saindo normal.
