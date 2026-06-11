# Frontend React + FastAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o dashboard Streamlit por um frontend React (Vite + TS) servido por uma camada FastAPI fina que serializa o backend `src/` existente, com UI dark atlética e duas grades de treino (corrida + musculação) que podem coincidir no mesmo dia.

**Architecture:** FastAPI expõe `src/` (GarminClient, DataProcessor, HealthMonitor, TrainingPlanner) como JSON. React consome via fetch. Dev: Vite 5173 + uvicorn 8000 com proxy. Prod: `vite build` → FastAPI serve estáticos + API na 8000. Cache 6h continua no GarminClient. Streamlit fica como legado.

**Tech Stack:** FastAPI, uvicorn, React 18, Vite, TypeScript, Recharts.

**Spec:** `docs/superpowers/specs/2026-06-11-frontend-react-fastapi-design.md`

---

## File Map

| Arquivo | Responsabilidade |
|---------|-----------------|
| `src/data_processor.py` | + `weekly_trend()` (delta tendência) |
| `src/training_planner.py` | output 2 grades `{corrida, musculacao}`, mesmo-dia OK |
| `tests/test_data_processor.py` | + testes `weekly_trend` |
| `tests/test_training_planner.py` | testes novo formato |
| `api/__init__.py` | pacote |
| `api/services.py` | monta context + chama src, devolve dicts JSON-ready |
| `api/main.py` | FastAPI: rotas + CORS + serve estáticos |
| `tests/test_api.py` | smoke tests via TestClient (src mockado) |
| `web/package.json` | deps frontend |
| `web/vite.config.ts` | proxy /api → 8000 |
| `web/index.html` | root |
| `web/src/main.tsx` | bootstrap React |
| `web/src/types.ts` | interfaces dos contratos |
| `web/src/api.ts` | fetch wrappers tipados |
| `web/src/styles/theme.css` | vars dark atlético |
| `web/src/App.tsx` | shell + sidebar + roteamento de página |
| `web/src/components/Sidebar.tsx` | nav |
| `web/src/components/Semaforo.tsx` | semáforo vertical |
| `web/src/components/MetricCard.tsx` | card métrica |
| `web/src/components/PlanGrid.tsx` | grade reusável (corrida ou musculação) |
| `web/src/components/Sparkline.tsx` | wrapper Recharts |
| `web/src/pages/Hoje.tsx` | semáforo + cards |
| `web/src/pages/Plano.tsx` | 2 grades + botão gerar |
| `web/src/pages/Dados.tsx` | sparklines + deltas + lista |
| `requirements.txt` | + fastapi, uvicorn |
| `iniciar.bat` / `iniciar.vbs` | sobem uvicorn + abrem browser |
| `web/README.md` | comandos dev |

---

## Task 1: `weekly_trend` no DataProcessor

**Files:**
- Modify: `src/data_processor.py`
- Test: `tests/test_data_processor.py`

- [ ] **Step 1: Escrever testes falhos**

Adicionar ao fim de `tests/test_data_processor.py`:
```python
def test_weekly_trend_queda():
    dp = DataProcessor()
    # 7d recentes média 52, 7d anteriores média 54 → delta -2
    series = [54, 54, 54, 54, 54, 54, 54, 52, 52, 52, 52, 52, 52, 52]
    result = dp.weekly_trend(series, unidade="bpm")
    assert result["delta"] == -2.0
    assert "bpm" in result["label"]
    assert "▼" in result["label"]

def test_weekly_trend_alta():
    dp = DataProcessor()
    series = [50] * 7 + [55] * 7
    result = dp.weekly_trend(series, unidade="bpm")
    assert result["delta"] == 5.0
    assert "▲" in result["label"]

def test_weekly_trend_estavel():
    dp = DataProcessor()
    series = [52] * 14
    result = dp.weekly_trend(series, unidade="bpm")
    assert result["delta"] == 0.0
    assert "estável" in result["label"].lower()

def test_weekly_trend_dados_insuficientes():
    dp = DataProcessor()
    result = dp.weekly_trend([52, 53], unidade="bpm")
    assert result["delta"] == 0.0
    assert result["label"] == ""
```

- [ ] **Step 2: Rodar pra confirmar falha**

Run: `pytest tests/test_data_processor.py -k weekly_trend -v`
Expected: FAIL — `AttributeError: 'DataProcessor' object has no attribute 'weekly_trend'`

- [ ] **Step 3: Implementar**

Adicionar método à classe `DataProcessor` em `src/data_processor.py` (após `morning_body_battery`):
```python
    def weekly_trend(self, series: list, unidade: str = "") -> dict:
        """Compara média dos 7 valores mais recentes vs os 7 anteriores.
        `series` ordenada do mais antigo ao mais recente. < 14 pontos → vazio."""
        valores = [v for v in series if v is not None]
        if len(valores) < 14:
            return {"delta": 0.0, "label": ""}
        recentes = valores[-7:]
        anteriores = valores[-14:-7]
        media_rec = sum(recentes) / 7
        media_ant = sum(anteriores) / 7
        delta = round(media_rec - media_ant, 1)
        if delta == 0.0:
            return {"delta": 0.0, "label": f"estável vs semana passada"}
        seta = "▲" if delta > 0 else "▼"
        sufixo = f" {unidade}" if unidade else ""
        return {
            "delta": delta,
            "label": f"{seta} {abs(delta)}{sufixo} vs semana passada",
        }
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_data_processor.py -k weekly_trend -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/data_processor.py tests/test_data_processor.py
git commit -m "feat: add weekly_trend to DataProcessor"
```

---

## Task 2: TrainingPlanner em 2 grades

**Files:**
- Modify: `src/training_planner.py`
- Test: `tests/test_training_planner.py`

- [ ] **Step 1: Reescrever testes pro novo formato**

Substituir TODO o conteúdo de `tests/test_training_planner.py`:
```python
import json
from unittest.mock import patch
from src.training_planner import TrainingPlanner

BASE_CONTEXT = {
    "resting_hr_avg_7d": 52.0,
    "morning_battery_avg": 65.0,
    "sleep_debt_hours": 0.0,
    "recent_activities": [],
    "strength_sessions_7d": 1,
    "run_sessions_7d": 2,
}

MOCK_PLAN = json.dumps({
    "corrida": [
        {"dia": "Segunda", "descricao": "Corrida leve 5km", "duracao": 40, "intensidade": "leve"},
        {"dia": "Quarta", "descricao": "Corrida moderada 7km", "duracao": 50, "intensidade": "moderada"},
        {"dia": "Sexta", "descricao": "Corrida intervalada", "duracao": 45, "intensidade": "alta"},
    ],
    "musculacao": [
        {"dia": "Segunda", "descricao": "Peito e tríceps", "duracao": 60, "intensidade": "moderada"},
        {"dia": "Quinta", "descricao": "Costas e bíceps", "duracao": 60, "intensidade": "moderada"},
    ],
})

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_returns_two_grids(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    assert "corrida" in plan
    assert "musculacao" in plan

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_minimum_3_run_days(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    assert len(plan["corrida"]) >= 3

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_calls_sonnet(mock_ask):
    TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    call = mock_ask.call_args
    depth = call[1].get("depth") or call[0][2]
    assert depth == "deep"

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_items_have_required_fields(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    for item in plan["corrida"] + plan["musculacao"]:
        assert "dia" in item
        assert "descricao" in item
        assert "duracao" in item
        assert "intensidade" in item

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_same_day_run_and_strength_allowed(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    run_days = {d["dia"] for d in plan["corrida"]}
    gym_days = {d["dia"] for d in plan["musculacao"]}
    # Segunda aparece nos dois — permitido, sem erro
    assert "Segunda" in run_days
    assert "Segunda" in gym_days

@patch("src.training_planner.ask_coach", return_value=json.dumps({
    "corrida": [{"dia": "Segunda", "descricao": "x", "duracao": 30, "intensidade": "leve"}],
    "musculacao": [],
}))
def test_plan_raises_when_under_3_runs(mock_ask):
    import pytest
    with pytest.raises(ValueError):
        TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
```

- [ ] **Step 2: Rodar pra confirmar falha**

Run: `pytest tests/test_training_planner.py -v`
Expected: FAIL — formato atual retorna lista, não dict com `corrida`/`musculacao`.

- [ ] **Step 3: Reescrever `generate_weekly_plan`**

Substituir TODO o corpo de `src/training_planner.py`:
```python
import json
from src.ai_coach import ask_coach


class TrainingPlanner:
    def generate_weekly_plan(self, context: dict) -> dict:
        """
        Gera plano semanal via Sonnet (depth='deep') em DUAS grades.

        CONSTRAINTS:
        - Mínimo 3 dias de corrida por semana (HARD CONSTRAINT)
        - Máximo 5 dias com treino (corrida e/ou musculação)
        - Corrida e musculação PODEM cair no mesmo dia
        - Se sono ruim (debt > 1h) ou Body Battery < 40: reduza intensidade
        - Considere atividades recentes para evitar sobrecarga

        Returns:
            dict {"corrida": [...], "musculacao": [...]}
            cada item: {dia, descricao, duracao, intensidade}

        Raises:
            ValueError: se plano gerado tiver menos de 3 dias de corrida após 3 tentativas
        """
        prompt = """Gere um plano semanal de treino dividido em DUAS grades separadas:
uma para CORRIDA e uma para MUSCULAÇÃO.

REGRAS OBRIGATÓRIAS:
- Mínimo 3 dias de corrida por semana (HARD CONSTRAINT)
- Máximo 5 dias com algum treino na semana (deixe 2 dias livres)
- Corrida e musculação PODEM ocorrer no mesmo dia
- Musculação preferencialmente em dias de corrida leve ou sem corrida
- Se sono ruim (debt > 1h) ou Body Battery < 40: reduza intensidade do dia
- Considere atividades recentes para evitar sobrecarga

Retorne EXATAMENTE este JSON (sem markdown, sem texto extra):
{
  "corrida": [
    {"dia": "Segunda", "descricao": "...", "duracao": <minutos>, "intensidade": "leve|moderada|alta"}
  ],
  "musculacao": [
    {"dia": "Segunda", "descricao": "...", "duracao": <minutos>, "intensidade": "leve|moderada|alta"}
  ]
}"""

        for _ in range(3):
            raw = ask_coach(prompt, context, depth="deep")
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]

            plan = json.loads(cleaned)
            corrida = plan.get("corrida", [])
            if len(corrida) >= 3:
                return {"corrida": corrida, "musculacao": plan.get("musculacao", [])}

        raise ValueError("Plan failed to include ≥3 run days after 3 attempts.")
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_training_planner.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/training_planner.py tests/test_training_planner.py
git commit -m "feat: TrainingPlanner returns two grids, allow same-day run+strength"
```

---

## Task 3: Dependências FastAPI

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Adicionar deps**

Adicionar ao `requirements.txt`:
```
fastapi>=0.115.0
uvicorn>=0.32.0
```

- [ ] **Step 2: Instalar**

Run: `pip install fastapi uvicorn`
Expected: instala sem erro.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add fastapi + uvicorn deps"
```

---

## Task 4: Camada de serviços da API

**Files:**
- Create: `api/__init__.py`
- Create: `api/services.py`
- Test: `tests/test_api.py` (parcial — serviços)

> `services.py` isola a montagem de context e a serialização. `main.py` só roteia.
> Testes mockam `GarminClient` pra não bater na API real.

- [ ] **Step 1: Criar `api/__init__.py` vazio**

Run: `python -c "open('api/__init__.py','w').close()"`

- [ ] **Step 2: Escrever testes dos serviços**

Criar `tests/test_api.py`:
```python
from unittest.mock import MagicMock, patch
from api import services


def _fake_client():
    client = MagicMock()
    client.get_activities.return_value = [{
        "activityType": {"typeKey": "running"},
        "duration": 2520, "averageHR": 150,
        "startTimeLocal": "2026-06-10 07:00:00", "activityName": "Corrida",
    }]
    client.get_heart_rate_stats.return_value = [{"restingHeartRate": 52}] * 14
    client.get_sleep.return_value = [{"dailySleepDTO": {"sleepTimeSeconds": 25200}}] * 14
    client.get_body_battery.return_value = [[{"charged": 65, "drained": 0}]] * 7
    return client


def test_build_today_payload():
    client = _fake_client()
    with patch("api.services.HealthMonitor") as MockMon:
        MockMon.return_value.check.return_value = {
            "status": "verde", "motivo": "ok", "recomendacao": "treine"
        }
        payload = services.build_today(client)
    assert payload["status"] == "verde"
    assert "metrics" in payload
    assert payload["metrics"]["resting_hr_avg_7d"] == 52.0


def test_build_data_payload_has_trends():
    client = _fake_client()
    payload = services.build_data(client)
    assert "fc_series" in payload
    assert "fc_trend" in payload
    assert "atividades" in payload
    assert isinstance(payload["atividades"], list)


def test_build_plan_payload():
    client = _fake_client()
    with patch("api.services.TrainingPlanner") as MockPlanner:
        MockPlanner.return_value.generate_weekly_plan.return_value = {
            "corrida": [{"dia": "Seg", "descricao": "x", "duracao": 40, "intensidade": "leve"}],
            "musculacao": [],
        }
        payload = services.build_plan(client)
    assert "corrida" in payload
    assert "musculacao" in payload
```

- [ ] **Step 3: Rodar pra confirmar falha**

Run: `pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.services'`

- [ ] **Step 4: Implementar `api/services.py`**

```python
"""Monta payloads JSON-ready a partir do backend src/. Sem lógica de negócio nova."""
from datetime import date, timedelta

from src.data_processor import DataProcessor
from src.health_monitor import HealthMonitor
from src.training_planner import TrainingPlanner


def _load_context(client):
    dp = DataProcessor()
    activities = client.get_activities(28)
    hr_data = client.get_heart_rate_stats(7)
    sleep_data = client.get_sleep(14)
    battery_data = client.get_body_battery(7)
    context = dp.build_context_summary(activities, hr_data, sleep_data, battery_data)
    return dp, context, activities, hr_data, sleep_data, battery_data


def build_today(client) -> dict:
    _, context, *_ = _load_context(client)
    status = HealthMonitor().check(context)
    return {
        "status": status["status"],
        "motivo": status["motivo"],
        "recomendacao": status["recomendacao"],
        "metrics": {
            "resting_hr_today": context["resting_hr_today"],
            "resting_hr_avg_7d": context["resting_hr_avg_7d"],
            "morning_battery_avg": context["morning_battery_avg"],
            "sleep_debt_hours": context["sleep_debt_hours"],
            "run_sessions_7d": context["run_sessions_7d"],
        },
    }


def build_plan(client) -> dict:
    _, context, *_ = _load_context(client)
    return TrainingPlanner().generate_weekly_plan(context)


def _datas(n: int) -> list:
    hoje = date.today()
    return [(hoje - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def build_data(client) -> dict:
    dp, _, activities, hr_data, sleep_data, battery_data = _load_context(client)

    # séries do mais antigo ao mais recente (hr_data[0] = hoje → inverter)
    fc = [d.get("restingHeartRate") for d in reversed(hr_data)]
    bat = [
        day[0]["charged"] if day and isinstance(day, list) and day[0].get("charged") is not None else None
        for day in reversed(battery_data)
    ]
    sono = [
        round(d.get("dailySleepDTO", {}).get("sleepTimeSeconds", 0) / 3600, 1)
        for d in reversed(sleep_data)
    ]

    def serie(vals, datas):
        return [{"data": dt, "valor": v} for dt, v in zip(datas, vals)]

    atividades = [
        {
            "data": a["date"], "nome": a["name"], "tipo": a["type"],
            "is_strength": a["is_strength"], "duracao": a["duration_minutes"],
        }
        for a in dp.classify_activities(activities)[:15]
    ]

    return {
        "fc_series": serie(fc, _datas(len(fc))),
        "battery_series": serie(bat, _datas(len(bat))),
        "sleep_series": serie(sono, _datas(len(sono))),
        "fc_trend": dp.weekly_trend(fc, unidade="bpm"),
        "battery_trend": dp.weekly_trend(bat, unidade="%"),
        "atividades": atividades,
    }
```

- [ ] **Step 5: Rodar testes**

Run: `pytest tests/test_api.py -v`
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add api/__init__.py api/services.py tests/test_api.py
git commit -m "feat: add API services layer over src backend"
```

---

## Task 5: App FastAPI

**Files:**
- Create: `api/main.py`
- Modify: `tests/test_api.py` (+ testes de rota)

- [ ] **Step 1: Adicionar testes de rota a `tests/test_api.py`**

Adicionar ao fim de `tests/test_api.py`:
```python
from fastapi.testclient import TestClient


def test_today_route():
    with patch("api.main.GarminClient") as MockClient, \
         patch("api.main.services.build_today", return_value={"status": "verde", "metrics": {}}):
        from api.main import app
        resp = TestClient(app).get("/api/today")
    assert resp.status_code == 200
    assert resp.json()["status"] == "verde"


def test_plan_route():
    with patch("api.main.GarminClient"), \
         patch("api.main.services.build_plan", return_value={"corrida": [], "musculacao": []}):
        from api.main import app
        resp = TestClient(app).post("/api/plan")
    assert resp.status_code == 200
    assert "corrida" in resp.json()


def test_today_route_garmin_error_returns_503():
    with patch("api.main.GarminClient"), \
         patch("api.main.services.build_today", side_effect=RuntimeError("auth failed")):
        from api.main import app
        resp = TestClient(app).get("/api/today")
    assert resp.status_code == 503
    assert "erro" in resp.json()
```

- [ ] **Step 2: Rodar pra confirmar falha**

Run: `pytest tests/test_api.py -k route -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Implementar `api/main.py`**

```python
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.garmin_client import GarminClient
from api import services

app = FastAPI(title="Garmin AI Coach")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = None


def get_client() -> GarminClient:
    global _client
    if _client is None:
        _client = GarminClient()
    return _client


def _safe(fn, *, code: int):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — devolve erro estruturado ao frontend
        return JSONResponse(status_code=code, content={"erro": str(e)})


@app.get("/api/today")
def today():
    return _safe(lambda: services.build_today(get_client()), code=503)


@app.post("/api/plan")
def plan():
    return _safe(lambda: services.build_plan(get_client()), code=502)


@app.get("/api/data")
def data():
    return _safe(lambda: services.build_data(get_client()), code=503)


@app.get("/api/profile")
def profile():
    path = Path("athlete_profile.json")
    if not path.exists():
        return JSONResponse(status_code=404, content={"erro": "athlete_profile.json não encontrado"})
    return json.loads(path.read_text(encoding="utf-8"))


# Serve build React em prod, se existir (montado por último pra não capturar /api).
_dist = Path("web/dist")
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_api.py -v`
Expected: 6 PASSED (3 serviços + 3 rotas)

- [ ] **Step 5: Smoke manual (opcional, bate API real)**

Run: `uvicorn api.main:app --port 8000`
Abrir `http://localhost:8000/api/today` no browser → JSON do status.
Parar com Ctrl+C.

- [ ] **Step 6: Commit**

```bash
git add api/main.py tests/test_api.py
git commit -m "feat: add FastAPI app with today/plan/data/profile routes"
```

---

## Task 6: Scaffold do frontend (Vite)

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/vite-env.d.ts`

- [ ] **Step 1: Criar `web/package.json`**

```json
{
  "name": "garmin-coach-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.13.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Criar `web/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: { outDir: "dist" },
});
```

- [ ] **Step 3: Criar `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Criar `web/index.html`**

```html
<!DOCTYPE html>
<html lang="pt">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Garmin AI Coach</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Criar `web/src/vite-env.d.ts`**

```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 6: Criar `web/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 7: Instalar deps**

Run: `cd web && npm install`
Expected: cria `node_modules`, sem erro.

- [ ] **Step 8: Commit**

```bash
git add web/package.json web/vite.config.ts web/tsconfig.json web/index.html web/src/main.tsx web/src/vite-env.d.ts web/package-lock.json
git commit -m "chore: scaffold Vite + React + TS frontend"
```

> Nota: `App.tsx` e `theme.css` ainda não existem — `npm run dev` só funciona após Task 7-8.
> Adicionar `web/node_modules/` ao `.gitignore` (Step incluído na Task 11).

---

## Task 7: Tema, tipos e cliente API

**Files:**
- Create: `web/src/styles/theme.css`
- Create: `web/src/types.ts`
- Create: `web/src/api.ts`

- [ ] **Step 1: Criar `web/src/styles/theme.css`**

```css
:root {
  --bg: #0f0f0f;
  --surface: #1a1a1a;
  --border: #2a2a2a;
  --text: #e0e0e0;
  --text-dim: #888;
  --text-faint: #666;
  --green: #4ade80;
  --green-bg: #14532d;
  --blue: #60a5fa;
  --blue-bg: #1e3a5f;
  --amber: #fbbf24;
  --amber-bg: #451a03;
  --red: #ef4444;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}

.app-shell { display: flex; min-height: 100vh; }

.sidebar {
  width: 200px; background: #141414; border-right: 1px solid var(--border);
  padding: 16px 0; flex-shrink: 0;
}
.brand { padding: 8px 16px 16px; font-size: 14px; font-weight: 600; color: #fff;
  border-bottom: 1px solid var(--border); margin-bottom: 10px; }
.nav-item { padding: 10px 16px; font-size: 13px; color: var(--text-faint);
  display: flex; gap: 8px; cursor: pointer; transition: all .15s; border: none;
  background: none; width: 100%; text-align: left; }
.nav-item:hover { color: #aaa; background: var(--surface); }
.nav-item.active { color: #fff; background: #222; border-right: 2px solid var(--green); }

.main { flex: 1; padding: 28px 32px; }
.page-title { font-size: 16px; font-weight: 500; color: #fff; margin-bottom: 4px; }
.page-sub { font-size: 13px; color: var(--text-dim); margin-bottom: 24px; }

.card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px; }

.btn-gen { display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px;
  background: var(--green-bg); border: none; border-radius: 8px; color: var(--green);
  font-size: 13px; font-weight: 500; cursor: pointer; }
.btn-gen:disabled { opacity: .5; cursor: default; }

.banner-erro { background: #3a1212; border: 1px solid #7f1d1d; color: #fca5a5;
  padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
```

- [ ] **Step 2: Criar `web/src/types.ts`**

```typescript
export interface TodayMetrics {
  resting_hr_today: number;
  resting_hr_avg_7d: number;
  morning_battery_avg: number;
  sleep_debt_hours: number;
  run_sessions_7d: number;
}

export interface Today {
  status: "verde" | "amarelo" | "vermelho";
  motivo: string;
  recomendacao: string;
  metrics: TodayMetrics;
}

export interface PlanItem {
  dia: string;
  descricao: string;
  duracao: number;
  intensidade: string;
}

export interface Plan {
  corrida: PlanItem[];
  musculacao: PlanItem[];
}

export interface SeriePoint {
  data: string;
  valor: number | null;
}

export interface Trend {
  delta: number;
  label: string;
}

export interface Atividade {
  data: string;
  nome: string;
  tipo: string;
  is_strength: boolean;
  duracao: number;
}

export interface Dados {
  fc_series: SeriePoint[];
  battery_series: SeriePoint[];
  sleep_series: SeriePoint[];
  fc_trend: Trend;
  battery_trend: Trend;
  atividades: Atividade[];
}
```

- [ ] **Step 3: Criar `web/src/api.ts`**

```typescript
import type { Today, Plan, Dados } from "./types";

async function get<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export const fetchToday = () => get<Today>("/api/today");
export const fetchDados = () => get<Dados>("/api/data");

export async function generatePlan(): Promise<Plan> {
  const resp = await fetch("/api/plan", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/styles/theme.css web/src/types.ts web/src/api.ts
git commit -m "feat: add frontend theme, types, and API client"
```

---

## Task 8: Componentes + App shell

**Files:**
- Create: `web/src/components/Sidebar.tsx`
- Create: `web/src/components/Semaforo.tsx`
- Create: `web/src/components/MetricCard.tsx`
- Create: `web/src/components/PlanGrid.tsx`
- Create: `web/src/components/Sparkline.tsx`
- Create: `web/src/App.tsx`

- [ ] **Step 1: Criar `web/src/components/Sidebar.tsx`**

```tsx
interface Props {
  page: string;
  onNavigate: (page: string) => void;
}

const ITEMS = [
  { id: "hoje", label: "☀ Hoje" },
  { id: "plano", label: "📅 Plano Semanal" },
  { id: "dados", label: "📊 Dados" },
];

export default function Sidebar({ page, onNavigate }: Props) {
  return (
    <nav className="sidebar">
      <div className="brand">⚡ Garmin Coach</div>
      {ITEMS.map((it) => (
        <button
          key={it.id}
          className={"nav-item" + (page === it.id ? " active" : "")}
          onClick={() => onNavigate(it.id)}
        >
          {it.label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Criar `web/src/components/Semaforo.tsx`**

```tsx
interface Props {
  status: "verde" | "amarelo" | "vermelho";
  motivo: string;
  recomendacao: string;
}

const CFG = {
  verde: { emoji: "🟢", label: "Verde", color: "var(--green)" },
  amarelo: { emoji: "🟡", label: "Amarelo", color: "var(--amber)" },
  vermelho: { emoji: "🔴", label: "Vermelho", color: "var(--red)" },
};

export default function Semaforo({ status, motivo, recomendacao }: Props) {
  const c = CFG[status];
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column",
      alignItems: "center", gap: 10, textAlign: "center" }}>
      <div style={{ fontSize: 40 }}>{c.emoji}</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: c.color }}>{c.label}</div>
      <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{motivo}</div>
      <div style={{ fontSize: 12, color: "var(--text-faint)", borderTop: "1px solid var(--border)",
        paddingTop: 10, marginTop: 4 }}>{recomendacao}</div>
    </div>
  );
}
```

- [ ] **Step 3: Criar `web/src/components/MetricCard.tsx`**

```tsx
interface Props {
  icon: string;
  label: string;
  value: string;
  delta?: string;
  deltaWarn?: boolean;
}

export default function MetricCard({ icon, label, value, delta, deltaWarn }: Props) {
  return (
    <div className="card" style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, display: "flex",
        alignItems: "center", justifyContent: "center", fontSize: 18,
        background: "var(--surface)", border: "1px solid var(--border)" }}>{icon}</div>
      <div>
        <div style={{ fontSize: 11, color: "var(--text-faint)" }}>{label}</div>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#fff" }}>
          {value}
          {delta && (
            <span style={{ fontSize: 11, marginLeft: 6,
              color: deltaWarn ? "var(--amber)" : "var(--green)" }}>{delta}</span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Criar `web/src/components/PlanGrid.tsx`**

```tsx
import type { PlanItem } from "../types";

interface Props {
  titulo: string;
  cor: string;
  itens: PlanItem[];
}

export default function PlanGrid({ titulo, cor, itens }: Props) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase",
        letterSpacing: ".05em", color: cor, marginBottom: 10 }}>{titulo}</div>
      {itens.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--text-faint)" }}>Nenhuma sessão.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {itens.map((it, i) => (
            <div key={i} className="card" style={{ borderLeft: `3px solid ${cor}` }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#fff" }}>{it.dia}</span>
                <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{it.duracao} min</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>{it.descricao}</div>
              <div style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 2 }}>{it.intensidade}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Criar `web/src/components/Sparkline.tsx`**

```tsx
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import type { SeriePoint } from "../types";

interface Props {
  data: SeriePoint[];
  cor: string;
}

export default function Sparkline({ data, cor }: Props) {
  const pontos = data.filter((p) => p.valor !== null);
  return (
    <ResponsiveContainer width="100%" height={48}>
      <LineChart data={pontos}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line type="monotone" dataKey="valor" stroke={cor} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 6: Criar `web/src/App.tsx`**

```tsx
import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Hoje from "./pages/Hoje";
import Plano from "./pages/Plano";
import Dados from "./pages/Dados";

export default function App() {
  const [page, setPage] = useState("hoje");
  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="main">
        {page === "hoje" && <Hoje />}
        {page === "plano" && <Plano />}
        {page === "dados" && <Dados />}
      </main>
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add web/src/components web/src/App.tsx
git commit -m "feat: add frontend components and app shell"
```

> Nota: páginas ainda não existem — build falha até Task 9. Sem `npm run dev` aqui.

---

## Task 9: Páginas

**Files:**
- Create: `web/src/pages/Hoje.tsx`
- Create: `web/src/pages/Plano.tsx`
- Create: `web/src/pages/Dados.tsx`

- [ ] **Step 1: Criar `web/src/pages/Hoje.tsx`**

```tsx
import { useEffect, useState } from "react";
import { fetchToday } from "../api";
import type { Today } from "../types";
import Semaforo from "../components/Semaforo";
import MetricCard from "../components/MetricCard";

export default function Hoje() {
  const [data, setData] = useState<Today | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    fetchToday().then(setData).catch((e) => setErro(e.message));
  }, []);

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!data) return <div className="page-sub">Carregando…</div>;

  const m = data.metrics;
  const hrDelta = m.resting_hr_today - m.resting_hr_avg_7d;
  return (
    <>
      <div className="page-title">Status do Dia</div>
      <div className="page-sub">Prontidão para treino hoje</div>
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 16, alignItems: "start" }}>
        <Semaforo status={data.status} motivo={data.motivo} recomendacao={data.recomendacao} />
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <MetricCard icon="❤" label="FC repouso hoje vs média 7d"
            value={`${m.resting_hr_today} bpm`}
            delta={hrDelta === 0 ? "= média" : `${hrDelta > 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm`}
            deltaWarn={hrDelta >= 5} />
          <MetricCard icon="⚡" label="Body Battery matinal"
            value={`${m.morning_battery_avg}`}
            delta={m.morning_battery_avg < 25 ? "abaixo do limite" : "ok"}
            deltaWarn={m.morning_battery_avg < 25} />
          <MetricCard icon="🌙" label="Dívida de sono semanal"
            value={`${m.sleep_debt_hours}h`}
            delta={m.sleep_debt_hours >= 2 ? "acima do limite" : "abaixo do limite (2h)"}
            deltaWarn={m.sleep_debt_hours >= 2} />
          <MetricCard icon="🏃" label="Corridas esta semana"
            value={`${m.run_sessions_7d} sessões`}
            delta={m.run_sessions_7d >= 3 ? "mínimo atingido" : "abaixo de 3"}
            deltaWarn={m.run_sessions_7d < 3} />
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Criar `web/src/pages/Plano.tsx`**

```tsx
import { useState } from "react";
import { generatePlan } from "../api";
import type { Plan } from "../types";
import PlanGrid from "../components/PlanGrid";

export default function Plano() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  async function gerar() {
    setLoading(true);
    setErro("");
    try {
      setPlan(await generatePlan());
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="page-title">Plano Semanal</div>
      <div className="page-sub">Duas grades — corrida e musculação podem cair no mesmo dia</div>
      <button className="btn-gen" onClick={gerar} disabled={loading}>
        {loading ? "Gerando com Sonnet…" : "⚡ Gerar novo plano"}
      </button>
      {erro && <div className="banner-erro" style={{ marginTop: 16 }}>{erro}</div>}
      {plan && (
        <div style={{ display: "flex", gap: 24, marginTop: 20 }}>
          <PlanGrid titulo="🏃 Corrida" cor="var(--green)" itens={plan.corrida} />
          <PlanGrid titulo="💪 Musculação" cor="var(--blue)" itens={plan.musculacao} />
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 3: Criar `web/src/pages/Dados.tsx`**

```tsx
import { useEffect, useState } from "react";
import { fetchDados } from "../api";
import type { Dados as DadosType } from "../types";
import Sparkline from "../components/Sparkline";

export default function Dados() {
  const [data, setData] = useState<DadosType | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    fetchDados().then(setData).catch((e) => setErro(e.message));
  }, []);

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!data) return <div className="page-sub">Carregando…</div>;

  const ultimo = (s: { valor: number | null }[]) => {
    const v = [...s].reverse().find((p) => p.valor !== null);
    return v?.valor ?? "—";
  };

  return (
    <>
      <div className="page-title">Dados do Garmin</div>
      <div className="page-sub">Tendências de 7 dias e atividades recentes</div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div className="card">
          <div style={{ fontSize: 11, color: "var(--text-faint)" }}>FC repouso — 7d</div>
          <div style={{ fontSize: 18, fontWeight: 500, color: "#fff" }}>{ultimo(data.fc_series)} bpm</div>
          <div style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>{data.fc_trend.label}</div>
          <Sparkline data={data.fc_series} cor="var(--green)" />
        </div>
        <div className="card">
          <div style={{ fontSize: 11, color: "var(--text-faint)" }}>Body Battery — 7d</div>
          <div style={{ fontSize: 18, fontWeight: 500, color: "#fff" }}>{ultimo(data.battery_series)} %</div>
          <div style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>{data.battery_trend.label}</div>
          <Sparkline data={data.battery_series} cor="var(--blue)" />
        </div>
      </div>

      <div className="card">
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
          letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>Atividades recentes</div>
        {data.atividades.map((a, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8,
            padding: "7px 0", borderBottom: i < data.atividades.length - 1 ? "1px solid #1f1f1f" : "none",
            fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%",
              background: a.is_strength ? "var(--blue)" : "var(--green)" }} />
            <span style={{ flex: 1, color: "#ccc" }}>{a.nome}</span>
            <span style={{ color: "var(--text-faint)" }}>{a.data} · {a.duracao} min</span>
          </div>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Build pra validar TypeScript**

Run: `cd web && npm run build`
Expected: build OK, gera `web/dist/`. Sem erros TS.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages
git commit -m "feat: add Hoje, Plano, Dados pages"
```

---

## Task 10: Verificação end-to-end

**Files:** nenhum (validação)

- [ ] **Step 1: Subir API**

Run (terminal 1): `uvicorn api.main:app --port 8000`

- [ ] **Step 2: Subir frontend dev**

Run (terminal 2): `cd web && npm run dev`
Abrir `http://localhost:5173`.

- [ ] **Step 3: Validar páginas**

- Hoje → semáforo + 4 cards com dados reais
- Plano → "Gerar novo plano" → 2 grades, corrida ≥ 3 sessões
- Dados → sparklines FC/Battery com label de tendência + lista de atividades

- [ ] **Step 4: Validar build de produção**

Parar Vite. Com `web/dist/` gerado (Task 9 Step 4), abrir `http://localhost:8000`.
Expected: FastAPI serve o React buildado. Mesmas 3 páginas funcionam.

- [ ] **Step 5: Rodar suíte completa**

Run: `pytest tests/ -v`
Expected: todos passam (cache, data_processor, health_monitor, training_planner, api).

---

## Task 11: Launchers + .gitignore + README

**Files:**
- Modify: `iniciar.bat`
- Modify: `iniciar.vbs`
- Modify: `.gitignore`
- Create: `web/README.md`

- [ ] **Step 1: Atualizar `.gitignore`**

Adicionar:
```
web/node_modules/
web/dist/
```

- [ ] **Step 2: Sobrescrever `iniciar.bat`**

```bat
@echo off
cd /d "%USERPROFILE%\Documents\Antigravity\Garmin"
if not exist "web\dist" (
  echo Building frontend...
  cd web && call npm install && call npm run build && cd ..
)
start "" http://localhost:8000
uvicorn api.main:app --port 8000
pause
```

- [ ] **Step 3: Sobrescrever `iniciar.vbs`**

```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d ""%USERPROFILE%\Documents\Antigravity\Garmin"" && (if not exist web\dist (cd web && npm install && npm run build && cd ..)) && start """" http://localhost:8000 && uvicorn api.main:app --port 8000", 0, False
```

- [ ] **Step 4: Criar `web/README.md`**

```markdown
# Frontend — Garmin AI Coach

## Dev (hot reload)
Dois terminais:
```
uvicorn api.main:app --port 8000 --reload   # backend
cd web && npm run dev                        # frontend (5173, proxy /api)
```
Abrir http://localhost:5173

## Produção local
```
cd web && npm run build      # gera web/dist/
uvicorn api.main:app --port 8000
```
Abrir http://localhost:8000 (FastAPI serve API + React).

Ou usar `iniciar.bat` / `iniciar.vbs` na raiz.
```

- [ ] **Step 5: Commit**

```bash
git add iniciar.bat iniciar.vbs .gitignore web/README.md
git commit -m "chore: update launchers for FastAPI+React, add web README"
```

---

## Verificação Final

- [ ] `pytest tests/ -v` → todos passam
- [ ] `uvicorn api.main:app --port 8000` + `cd web && npm run dev` → 3 páginas funcionam em :5173
- [ ] Plano gera 2 grades, corrida ≥ 3 sessões, mesmo dia pode ter corrida + musculação
- [ ] Dados mostra sparklines com label de tendência
- [ ] `cd web && npm run build` + `uvicorn api.main:app --port 8000` → :8000 serve build
- [ ] `iniciar.bat` duplo-clique → abre browser em :8000 funcionando
- [ ] Streamlit antigo (`dashboard/app.py`) intacto, não quebrado
