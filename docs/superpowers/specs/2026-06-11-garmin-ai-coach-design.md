# Garmin AI Coach — Design Spec
**Date:** 2026-06-11  
**Scope:** MVP pessoal, uso local, Windows 11

---

## Context

Yuri usa um Garmin Forerunner 55 e quer um app local que cruze dados reais do Garmin Connect com a Claude API para:
1. Dar um status diário de prontidão para treino (semáforo)
2. Gerar plano semanal personalizado (corrida ≥ 3x/semana + musculação)

O Forerunner 55 não registra treino de força nativamente — Yuri usa a função Cardio e depois renomeia a atividade para "Treino de Força" no Garmin Connect. O app detecta isso automaticamente via `activity_type`.

---

## Arquitetura

```
Garmin Connect API
       ↓
garmin_client.py  ←→  cache.py (SQLite, TTL 6h)
       ↓
data_processor.py   (normaliza + classifica atividades)
       ↓
   ┌──────────────────────────────┐
   │         ai_coach.py          │
   │  depth=quick → Haiku         │
   │  depth=deep  → Sonnet        │
   └──────┬───────────────┬───────┘
          ↓               ↓
  health_monitor.py  training_planner.py
          ↓               ↓
       dashboard/app.py (Streamlit, porta 8501)
```

**Ordem de build (auth-first):**
1. `scripts/test_auth.py` — valida SSO Garmin antes de qualquer coisa
2. `src/cache.py` + `src/garmin_client.py`
3. `src/data_processor.py`
4. `src/ai_coach.py`
5. `src/health_monitor.py` + `src/training_planner.py`
6. `dashboard/app.py`
7. `iniciar.bat` / `iniciar.vbs`

---

## Módulos

### `scripts/test_auth.py`
Script standalone. Autentica no Garmin Connect e imprime nome do usuário + última atividade. Roda antes de qualquer desenvolvimento da camada de dados.

### `src/cache.py`
- SQLite local (`cache.db`)
- TTL configurável via `CACHE_TTL_HOURS` (default: 6)
- Chave: `(endpoint, date_str)`
- `get(key)` → dados ou None se expirado
- `set(key, data)`

### `src/garmin_client.py`
- Auth via `garminconnect.Garmin(email, password)`
- Cache obrigatório antes de qualquer chamada
- Métodos:
  - `get_activities(days=28)`
  - `get_sleep(days=14)`
  - `get_heart_rate_stats(days=7)`
  - `get_body_battery(days=7)`
  - `get_steps(days=7)`
- Trata `GarminConnectAuthenticationError` e `GarminConnectTooManyRequestsError`

### `src/data_processor.py`
- Normaliza estrutura das atividades
- Classifica como musculação se `activity_type` in `['strength_training', 'indoor_cardio']`
- Calcula: FC repouso média 7d, dívida de sono semanal, Body Battery matinal médio
- Monta `context_summary` para os prompts

### `src/ai_coach.py`
```python
def ask_coach(prompt: str, context: dict, depth: str = "quick") -> str:
    model = "claude-haiku-4-5-20251001" if depth == "quick" else "claude-sonnet-4-6"
    # system prompt sempre inclui athlete_profile.json + context_summary
```
- `depth="quick"` → Haiku (análises do dia a dia, < 300 tokens esperados)
- `depth="deep"` → Sonnet (planos, análises multi-etapa)

### `src/health_monitor.py` (→ Haiku)
Regras de alerta:
| Condição | Status |
|----------|--------|
| FC repouso ≥ média 7d + 5 bpm | 🔴 vermelho |
| Body Battery matinal < 25 | 🟡 amarelo |
| Dívida de sono ≥ 2h na semana | 🟡 amarelo |
| Tudo normal | 🟢 verde |

Retorno: `{ "status": "verde|amarelo|vermelho", "motivo": str, "recomendacao": str }`

### `src/training_planner.py` (→ Sonnet)
- **Corrida: mínimo 3 dias por semana** (restrição hard)
- Musculação nos dias de menor carga aeróbica
- Total: ≤ 5 dias de treino (conforme `dias_disponiveis_treino` no perfil)
- Ajuste automático: sono ruim ou Body Battery < 40 → reduz intensidade do dia
- Considera atividades dos últimos 7 dias para evitar sobrecarga
- Output: `[{ "dia": str, "tipo": str, "descricao": str, "duracao": int, "intensidade": str }]`

---

## Dashboard Streamlit (`dashboard/app.py`)

3 páginas via sidebar:

**Hoje**
- Semáforo colorido (verde/amarelo/vermelho)
- Motivo e recomendação do health monitor
- FC repouso hoje vs média 7d
- Body Battery atual

**Plano Semanal**
- Botão "Gerar plano" → chama Sonnet → exibe tabela
- Plano gerado persiste na sessão (não regera sozinho)

**Dados**
- Gráfico Body Battery 7 dias
- Gráfico FC repouso 7 dias
- Lista de atividades 28 dias com tipo e duração

Read-only. Nenhuma escrita via dashboard.

---

## Configuração

**`.env`** (nunca commitado):
```
GARMIN_EMAIL=seu@email.com
GARMIN_PASSWORD=suasenha
ANTHROPIC_API_KEY=sk-ant-...
CACHE_TTL_HOURS=6
```

**`athlete_profile.json`** (nunca commitado):
```json
{
  "nome": "Yuri",
  "idade": null,
  "sexo": "masculino",
  "peso_kg": null,
  "altura_cm": null,
  "objetivo_principal": "melhorar pace corrida + hipertrofia",
  "nivel_corrida": "intermediário",
  "nivel_musculacao": "intermediário",
  "restricoes_medicas": [],
  "meta_peso_kg": null,
  "dias_disponiveis_treino": 5
}
```
Campos `null` devem ser preenchidos antes de gerar planos. App avisa se estiverem vazios.

---

## Modelos Claude (regra obrigatória)

| Modelo | Quando usar |
|--------|-------------|
| `claude-haiku-4-5-20251001` | `daily_readiness_check`, alertas de saúde, qualquer resposta < 300 tokens |
| `claude-sonnet-4-6` | `generate_weekly_plan`, análise de carga, insights corporais |

---

## Launchers Windows

**`iniciar.bat`** — mostra terminal (uso em desenvolvimento)  
**`iniciar.vbs`** — abre direto no browser sem janela (uso diário)  
Ambos apontam para `C:\Users\%USERNAME%\Documents\Antigravity\Garmin`.

---

## Verificação

1. Rodar `python scripts/test_auth.py` → deve imprimir nome do usuário Garmin
2. Rodar `python -c "from src.garmin_client import GarminClient; c = GarminClient(); print(c.get_activities(7))"` → lista de atividades
3. Rodar `streamlit run dashboard/app.py` → abrir localhost:8501, ver semáforo do dia
4. Clicar "Gerar plano" → plano com ≥ 3 dias de corrida na semana
5. Verificar no log que Haiku foi usado para health monitor e Sonnet para o plano
