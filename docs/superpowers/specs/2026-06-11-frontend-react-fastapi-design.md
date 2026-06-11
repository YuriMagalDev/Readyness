# Frontend React + FastAPI — Design Spec

**Data:** 2026-06-11
**Objetivo:** Substituir o dashboard Streamlit por um frontend React (Vite + TypeScript)
servido por uma camada FastAPI fina, com UI/UX dark atlética minimalista e navegação
por sidebar. Reusa todo o backend existente em `src/` sem reescrever lógica de negócio.

---

## Visão Geral

O MVP em Streamlit (`dashboard/app.py`) validou o fluxo: dados reais do Garmin →
análise Haiku/Sonnet → exibição. Limitação: UX travada no teto do Streamlit.

Esta fase troca a camada de apresentação por React, mantendo `src/` intacto. FastAPI
serializa os módulos existentes como JSON e serve o build estático do React em produção.

**Princípio:** zero lógica de negócio nova. FastAPI só serializa
`GarminClient`, `DataProcessor`, `HealthMonitor`, `TrainingPlanner`.

---

## Arquitetura

```
Browser (React + Vite)  ──fetch──>  FastAPI (api/main.py)  ──>  src/ (existente)
       UI dark                         serialização JSON         Garmin + Claude
```

- **Dev:** Vite na 5173 (HMR), FastAPI na 8000. Proxy Vite `/api` → 8000.
- **Prod:** `vite build` → `web/dist/`. FastAPI serve estáticos + API na mesma porta (8000).
- **Cache:** TTL 6h já vive no `GarminClient`. FastAPI NÃO recacheia.
- **Streamlit:** mantido como legado. Não apagar `dashboard/`.

---

## Stack

| Camada | Tech |
|--------|------|
| API | FastAPI + uvicorn |
| Frontend | React 18 + Vite + TypeScript |
| Gráficos | Recharts (sparklines, séries) |
| Estilo | CSS custom (dark atlético). Sem framework pesado — escala baixa. |

---

## API — `api/main.py`

| Rota | Método | Retorna | Fonte | Modelo |
|------|--------|---------|-------|--------|
| `/api/today` | GET | `{status, motivo, recomendacao, metrics}` | HealthMonitor + context | Haiku |
| `/api/plan` | POST | `{corrida: [...], musculacao: [...]}` | TrainingPlanner | Sonnet |
| `/api/data` | GET | `{fc_series, battery_series, sleep_series, atividades}` | DataProcessor | — |
| `/api/profile` | GET | conteúdo de `athlete_profile.json` | arquivo | — |

### Contratos

`GET /api/today`
```json
{
  "status": "verde|amarelo|vermelho",
  "motivo": "...",
  "recomendacao": "...",
  "metrics": {
    "resting_hr_today": 52,
    "resting_hr_avg_7d": 52.0,
    "morning_battery_avg": 68.0,
    "sleep_debt_hours": 0.5,
    "run_sessions_7d": 3
  }
}
```

`POST /api/plan` → gera plano (chama Sonnet; pode demorar)
```json
{
  "corrida": [
    {"dia": "Segunda", "descricao": "Corrida leve 5km", "duracao": 40, "intensidade": "leve"}
  ],
  "musculacao": [
    {"dia": "Segunda", "descricao": "Peito e tríceps", "duracao": 60, "intensidade": "moderada"}
  ]
}
```

`GET /api/data`
```json
{
  "fc_series": [{"data": "2026-06-05", "valor": 53}, ...],
  "battery_series": [{"data": "2026-06-05", "valor": 65}, ...],
  "sleep_series": [{"data": "2026-06-05", "valor": 6.5}, ...],
  "atividades": [
    {"data": "2026-06-10", "nome": "Corrida em esteira", "tipo": "running",
     "is_strength": false, "duracao": 42}
  ]
}
```

### Deltas de tendência (página Dados)

Cada série carrega delta calculado server-side: média últimos 7d vs 7d anteriores.
Frontend exibe label tipo `▼ 2 bpm vs semana passada` / `leve queda desde seg`.
Adicionar a `/api/data`:
```json
"fc_trend": {"delta": -2, "label": "▼ 2 bpm vs semana passada"}
```
Helper novo em `DataProcessor` (`weekly_trend(series)`) — única adição ao backend,
e é cálculo puro determinístico (testável sem API).

### Erros

- Falha Garmin/auth → `503 {"erro": "..."}`. Frontend mostra banner, não quebra.
- Falha geração plano (3 retries esgotados) → `502 {"erro": "..."}`.
- CORS liberado só pra `localhost` (dev).

---

## Frontend — `web/`

```
web/
├── index.html
├── vite.config.ts          # proxy /api -> :8000
├── package.json
├── src/
│   ├── main.tsx
│   ├── App.tsx             # shell + sidebar nav (Hoje/Plano/Dados/Perfil)
│   ├── api.ts              # fetch wrappers tipados
│   ├── types.ts            # interfaces dos contratos
│   ├── pages/
│   │   ├── Hoje.tsx        # semáforo + cards métrica (layout B+C aprovado)
│   │   ├── Plano.tsx       # 2 grades: corrida + musculação
│   │   └── Dados.tsx       # sparklines + lista atividades + deltas
│   ├── components/
│   │   ├── Sidebar.tsx
│   │   ├── Semaforo.tsx
│   │   ├── MetricCard.tsx
│   │   ├── PlanGrid.tsx    # reusável: recebe título + sessões
│   │   └── Sparkline.tsx   # Recharts wrapper
│   └── styles/
│       └── theme.css       # vars dark atlético
```

### Página Hoje (layout aprovado — `docs/mockups/layout-hoje.html`)
- Semáforo vertical (vermelho/amarelo/verde) à esquerda + motivo + recomendação.
- Stack de cards à direita: FC repouso hoje vs média, Body Battery, dívida sono, corridas semana.

### Página Plano (`docs/mockups/layout-plano.html` — Grade A, modificada)
- **Duas grades separadas:** uma corrida, uma musculação.
- **Corrida e musculação PODEM cair no mesmo dia** (relaxa regra antiga do MVP).
- Botão "Gerar novo plano" → `POST /api/plan` → preenche as 2 grades.
- Estado loading enquanto Sonnet gera.

### Página Dados (`docs/mockups/layout-dados.html` — Layout A + deltas do B)
- Sparklines FC e Body Battery no topo, cada um com label de delta de tendência.
- Lista de atividades recentes abaixo (dot verde=corrida, azul=musculação).

---

## Mudança no Backend

### `training_planner.py`
- **Remover** regra "Corrida e musculação NÃO no mesmo dia" do prompt.
- **Adicionar** instrução: separar saída em dois conjuntos — corridas e musculações —
  podendo coincidir no mesmo dia.
- Output novo: `{"corrida": [...], "musculacao": [...]}` (em vez de lista única de 7).
- Manter hard constraint **≥ 3 dias de corrida**.
- Atualizar testes (`tests/test_training_planner.py`) pro novo formato.

### `data_processor.py`
- Adicionar `weekly_trend(series) -> {delta, label}` — cálculo puro, testável.
- Adicionar testes em `tests/test_data_processor.py`.

Nenhum outro módulo de `src/` muda.

---

## Launcher (Windows)

- Atualizar `iniciar.bat` / `iniciar.vbs`:
  1. (se `web/dist` ausente ou desatualizado) `npm run build` em `web/`
  2. `uvicorn api.main:app --port 8000`
  3. abrir `http://localhost:8000`
- Dev separado: `npm run dev` (web) + `uvicorn ... --reload` (api). Documentar no README.

---

## Testes

- `weekly_trend` — testes unitários determinísticos (deltas positivos/negativos/zero).
- `training_planner` novo formato — mock `ask_coach`, validar 2 chaves + ≥3 corridas.
- API — smoke test cada rota com cliente FastAPI (TestClient), mockando `src/`.
- Frontend — verificação manual no browser (escala baixa, sem suíte E2E).

---

## Fora de Escopo (YAGNI)

- Autenticação/login no frontend (app local, single-user).
- Persistência de planos gerados (regerar é barato o bastante).
- Mobile/responsivo além do básico.
- Edição de perfil pela UI (continua editando `athlete_profile.json` à mão).
- Deploy remoto. Roda só em localhost.
