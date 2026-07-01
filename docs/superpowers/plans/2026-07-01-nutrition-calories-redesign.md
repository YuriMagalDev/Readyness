# Nutrição — Redesign do Cálculo de Calorias (Perfil Vivo) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o cálculo estático de kcal/macros por carbo ciclado/capado, deficit auto-corrigido por peso semanal + gate de aderência, e BF estimado derivado — com o bot propondo ajustes que o usuário confirma.

**Architecture:** Camadas puras (`config`, `targets`, `adaptive`) fazem o cálculo determinístico e são cobertas por TDD. `store` + `history_db` persistem peso. `bot` adiciona `/peso`, `/progresso`, job semanal e botões aplicar/manter. Nenhum número novo é inventado por LLM; BF é o único inferido, marcado "estimado".

**Tech Stack:** Python 3.11, sqlite3, pytest, python-telegram-bot.

## Global Constraints

- Números de fonte real (peso digitado, Garmin, TACO). BF é o único inferido — sempre marcado "estimado".
- Alvo determinístico por regra; ajuste **só** via proposta confirmada pelo usuário. Nada muda o alvo sozinho.
- Bot sobe sem `ANTHROPIC_API_KEY`; nada aqui depende de LLM.
- Perfil de referência: 108 kg, 30% BF → LBM 75,6 kg → TDEE base ≈ 2604 kcal (Katch-McArdle, NEAT 1,3).
- Testes das camadas puras por TDD; handlers de IO cobertos por smoke de import + funções puras (padrão do projeto).
- Rodar teste único: `python -m pytest tests/CAMINHO::NOME -v`. Suíte: `python -m pytest -q`.

---

### Task 1: Novos parâmetros de config

**Files:**
- Modify: `src/nutrition/config.py`
- Test: `tests/test_nutrition_config.py`

**Interfaces:**
- Consumes: nada.
- Produces: `nutrition_config(profile)` passa a devolver as chaves `protein_g` (default 180),
  `carb_rest_g` (130), `carb_train_g` (200), `deficit_floor` (900), `target_rate_low` (-0.4),
  `target_rate_high` (-0.3), `fast_rate` (-0.7), `bf_fat_frac` (0.85), `kcal_adjust` (0).

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_nutrition_config.py  (adicionar)
from src.nutrition.config import nutrition_config


def test_novos_defaults():
    cfg = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})
    assert cfg["protein_g"] == 180
    assert cfg["carb_rest_g"] == 130
    assert cfg["carb_train_g"] == 200
    assert cfg["deficit_floor"] == 900
    assert cfg["bf_fat_frac"] == 0.85
    assert cfg["kcal_adjust"] == 0
```

- [ ] **Step 2: Rodar teste — deve falhar**

Run: `python -m pytest tests/test_nutrition_config.py::test_novos_defaults -v`
Expected: FAIL (`KeyError: 'carb_rest_g'`).

- [ ] **Step 3: Implementação mínima**

```python
# src/nutrition/config.py  — substituir _DEFAULTS
_DEFAULTS = {
    "neat_factor": 1.3,
    "protein_g": 180,
    "fat_g": 60,
    "carb_rest_g": 130,
    "carb_train_g": 200,
    "deficit_floor": 900,
    "target_rate_low": -0.4,   # %/sem — ritmo alvo (perde mais)
    "target_rate_high": -0.3,  # %/sem — ritmo alvo (perde menos); acima disso = travado
    "fast_rate": -0.7,         # %/sem — abaixo disso = rápido demais
    "bf_fat_frac": 0.85,       # fração da perda que é gordura
    "kcal_adjust": 0,          # ajuste aplicado (proposto+confirmado)
    "ea_low": 25,
    "ea_ok": 30,
    "ex_kcal_treino": 300,
    "ex_kcal_corrida": 400,
}
```

Nota: `deficit_kcal` sai dos defaults (não é mais usado; o deficit emerge do carbo+piso).

- [ ] **Step 4: Rodar teste — deve passar**

Run: `python -m pytest tests/test_nutrition_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/config.py tests/test_nutrition_config.py
git commit -m "feat(nutrition): params de carbo ciclado, piso e ritmo no config"
```

---

### Task 2: `day_target` — carbo ciclado + piso de comida

**Files:**
- Modify: `src/nutrition/targets.py:26-33`
- Test: `tests/test_nutrition_targets.py`

**Interfaces:**
- Consumes: `cfg` da Task 1; `tdee_base(cfg)`.
- Produces: `day_target(cfg, *, training: bool, exercise_kcal: float = 0.0) -> {"kcal","protein_g","fat_g","carb_g"}`.
  Carbo base = `carb_train_g` se training senão `carb_rest_g`. Se `(tdee_base+exercise_kcal) − intake > deficit_floor`,
  sobe carbo até o deficit igualar `deficit_floor`. `kcal_adjust` desloca carbo/kcal no fim.

- [ ] **Step 1: Escrever testes que falham (substituir os 2 testes antigos de day_target)**

Remover `test_dia_descanso` e `test_dia_treino_soma_exercicio` antigos. Adicionar:

```python
# tests/test_nutrition_targets.py
def test_descanso_carbo_baixo():
    t = day_target(CFG, training=False)
    assert t["protein_g"] == 180
    assert t["fat_g"] == 60
    assert round(t["carb_g"]) == 130
    # intake = 180*4 + 60*9 + 130*4 = 720 + 540 + 520 = 1780
    assert round(t["kcal"]) == 1780


def test_treino_carbo_200_sem_piso():
    # só treino: gasto 2604+300=2904 ; intake carbo200 = 2060 ; deficit 844 < 900 -> fica 200
    t = day_target(CFG, training=True, exercise_kcal=300)
    assert round(t["carb_g"]) == 200
    assert round(t["kcal"]) == 2060


def test_piso_libera_carbo_dia_pesado():
    # treino+corrida: gasto 2604+700=3304 ; carbo200 daria deficit 1244 > 900
    # piso: intake alvo = 3304-900 = 2404 ; carbo = (2404-1260)/4 = 286
    t = day_target(CFG, training=True, exercise_kcal=700)
    assert round(t["carb_g"]) == 286
    assert round(t["kcal"]) == 2404


def test_kcal_adjust_desloca_carbo():
    cfg = dict(CFG, kcal_adjust=-100)
    t = day_target(cfg, training=False)
    # 1780 - 100 = 1680 ; carbo 130 - 25 = 105
    assert round(t["kcal"]) == 1680
    assert round(t["carb_g"]) == 105
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/test_nutrition_targets.py -v`
Expected: FAIL (carbo 226 ≠ 130, etc).

- [ ] **Step 3: Implementação**

```python
# src/nutrition/targets.py  — substituir day_target
def day_target(cfg: dict, *, training: bool, exercise_kcal: float = 0.0) -> dict:
    protein_g = cfg["protein_g"]
    fat_g = cfg["fat_g"]
    carb_g = cfg["carb_train_g"] if training else cfg["carb_rest_g"]
    fixed_kcal = protein_g * 4 + fat_g * 9
    intake = fixed_kcal + carb_g * 4

    # piso de comida: não deixar o deficit passar de deficit_floor
    expenditure = tdee_base(cfg) + (exercise_kcal if training else 0.0)
    if expenditure - intake > cfg["deficit_floor"]:
        intake = expenditure - cfg["deficit_floor"]
        carb_g = max(0.0, (intake - fixed_kcal) / 4)

    # ajuste aplicado (proposto+confirmado): desloca o carbo
    adjust = cfg.get("kcal_adjust", 0)
    if adjust:
        carb_g = max(0.0, carb_g + adjust / 4)
        intake = fixed_kcal + carb_g * 4

    return {"kcal": intake, "protein_g": protein_g, "fat_g": fat_g, "carb_g": carb_g}
```

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/test_nutrition_targets.py -v`
Expected: PASS (todos, incluindo os de `resolve_exercise_kcal`/`day_balance` intactos).

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/targets.py tests/test_nutrition_targets.py
git commit -m "feat(nutrition): day_target com carbo ciclado e piso de deficit"
```

---

### Task 3: Tabela `weights` + CRUD no store

**Files:**
- Modify: `src/history_db.py` (dentro de `_init_db`, junto às outras `CREATE TABLE`)
- Modify: `src/nutrition/store.py`
- Test: `tests/test_nutrition_store.py`

**Interfaces:**
- Consumes: `HistoryDB(path)` cria tabelas.
- Produces: `store.add_weight(db_path, date, kg, source="manual")`,
  `store.get_weights(db_path) -> list[dict]` (ordenado por date asc, chaves `date`,`kg`,`source`),
  `store.latest_weight(db_path) -> float | None`.

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_nutrition_store.py  (adicionar)
def test_weights_roundtrip(tmp_path):
    p = _db(tmp_path)
    store.add_weight(p, "2026-06-22", 108.0)
    store.add_weight(p, "2026-06-29", 107.4)
    ws = store.get_weights(p)
    assert [w["kg"] for w in ws] == [108.0, 107.4]
    assert store.latest_weight(p) == 107.4


def test_weight_upsert_mesma_data(tmp_path):
    p = _db(tmp_path)
    store.add_weight(p, "2026-06-29", 107.4)
    store.add_weight(p, "2026-06-29", 107.1)   # corrige o mesmo dia
    assert store.latest_weight(p) == 107.1
    assert len(store.get_weights(p)) == 1
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/test_nutrition_store.py::test_weights_roundtrip -v`
Expected: FAIL (`no such table: weights` ou `AttributeError`).

- [ ] **Step 3: Implementação**

Em `src/history_db.py`, dentro do `with self._connect() as conn:` do `_init_db`, adicionar após o bloco `custom_foods`:

```python
            conn.execute(
                "CREATE TABLE IF NOT EXISTS weights ("
                "date TEXT PRIMARY KEY, kg REAL NOT NULL, source TEXT, set_at TEXT)"
            )
```

Em `src/nutrition/store.py` (adicionar ao fim):

```python
def add_weight(db_path, date, kg, source="manual"):
    with _session(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO weights (date, kg, source, set_at) VALUES (?,?,?,?)",
            (date, float(kg), source, dt.datetime.now().isoformat()),
        )


def get_weights(db_path) -> list:
    with _session(db_path) as conn:
        rows = conn.execute(
            "SELECT date, kg, source FROM weights ORDER BY date ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def latest_weight(db_path):
    with _session(db_path) as conn:
        row = conn.execute(
            "SELECT kg FROM weights ORDER BY date DESC LIMIT 1"
        ).fetchone()
    return row["kg"] if row else None
```

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/test_nutrition_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/history_db.py src/nutrition/store.py tests/test_nutrition_store.py
git commit -m "feat(nutrition): tabela weights + CRUD de peso"
```

---

### Task 4: `adaptive.py` — tendência e ritmo de peso

**Files:**
- Create: `src/nutrition/adaptive.py`
- Test: `tests/test_nutrition_adaptive.py`

**Interfaces:**
- Consumes: lista de pesos (floats, ordem cronológica).
- Produces: `trend_kg(kgs, window=3) -> float | None` (média dos últimos `window`),
  `weekly_rate_pct(kgs) -> float | None` (slope por semana via mínimos quadrados, % do peso médio).

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_nutrition_adaptive.py
from src.nutrition.adaptive import trend_kg, weekly_rate_pct


def test_trend_media_ultimos():
    assert trend_kg([108.0, 107.4, 107.1], window=3) == round((108.0+107.4+107.1)/3, 2)
    assert trend_kg([109, 108, 107.4, 107.1], window=3) == round((108+107.4+107.1)/3, 2)


def test_trend_poucos_pontos():
    assert trend_kg([]) is None
    assert trend_kg([107.4]) == 107.4


def test_rate_none_com_um_ponto():
    assert weekly_rate_pct([107.4]) is None


def test_rate_perda_negativa():
    # queda constante ~-0.5kg/sem sobre ~108 -> ~-0.46%/sem
    r = weekly_rate_pct([108.0, 107.5, 107.0, 106.5])
    assert r is not None and -0.6 < r < -0.4


def test_rate_estavel_zero():
    assert abs(weekly_rate_pct([107.0, 107.0, 107.0])) < 0.05
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/test_nutrition_adaptive.py -v`
Expected: FAIL (`ModuleNotFoundError: src.nutrition.adaptive`).

- [ ] **Step 3: Implementação**

```python
# src/nutrition/adaptive.py
def trend_kg(kgs, window=3):
    if not kgs:
        return None
    last = kgs[-window:]
    return round(sum(last) / len(last), 2)


def weekly_rate_pct(kgs):
    """Slope por passo (semana) via mínimos quadrados, em % do peso médio."""
    n = len(kgs)
    if n < 2:
        return None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(kgs) / n
    num = sum((xs[i] - mean_x) * (kgs[i] - mean_y) for i in range(n))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0 or mean_y == 0:
        return 0.0
    slope = num / den            # kg por semana
    return slope / mean_y * 100  # %/semana
```

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/test_nutrition_adaptive.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/adaptive.py tests/test_nutrition_adaptive.py
git commit -m "feat(nutrition): tendencia e ritmo de peso em adaptive.py"
```

---

### Task 5: `adaptive.py` — BF estimado derivado

**Files:**
- Modify: `src/nutrition/adaptive.py`
- Test: `tests/test_nutrition_adaptive.py`

**Interfaces:**
- Consumes: `bf_fat_frac` do cfg.
- Produces: `derive_bf(prev_weight, prev_bf, new_weight, fat_frac=0.85) -> float` (novo %BF estimado).

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_nutrition_adaptive.py  (adicionar)
from src.nutrition.adaptive import derive_bf


def test_derive_bf_perda_maioria_gordura():
    # 108kg 30%BF -> perde 1kg, 85% gordura
    # fat_mass = 32.4 ; perde 0.85 -> 31.55 ; novo peso 107 ; bf = 31.55/107 = 29.49%
    bf = derive_bf(108.0, 30.0, 107.0)
    assert round(bf, 2) == 29.49


def test_derive_bf_ganho_peso():
    # ganhou 1kg, 85% vira gordura
    bf = derive_bf(108.0, 30.0, 109.0)
    assert bf > 30.0
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/test_nutrition_adaptive.py::test_derive_bf_perda_maioria_gordura -v`
Expected: FAIL (`ImportError: cannot import name 'derive_bf'`).

- [ ] **Step 3: Implementação**

```python
# src/nutrition/adaptive.py  (adicionar)
def derive_bf(prev_weight, prev_bf, new_weight, fat_frac=0.85):
    """Novo %BF estimado assumindo que fat_frac da variação de peso é gordura."""
    delta = new_weight - prev_weight
    prev_fat_mass = prev_weight * prev_bf / 100.0
    new_fat_mass = prev_fat_mass + delta * fat_frac
    if new_weight <= 0:
        return prev_bf
    return new_fat_mass / new_weight * 100.0
```

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/test_nutrition_adaptive.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/adaptive.py tests/test_nutrition_adaptive.py
git commit -m "feat(nutrition): BF estimado derivado da variacao de peso"
```

---

### Task 6: `adaptive.py` — aderência + proposta de ajuste

**Files:**
- Modify: `src/nutrition/adaptive.py`
- Test: `tests/test_nutrition_adaptive.py`

**Interfaces:**
- Consumes: `totals` (dict com `p`,`kcal` — de `store.day_totals`), `target` (de `day_target`), `rate_pct` (Task 4).
- Produces:
  - `is_adherent_day(totals, target, protein_frac=0.9, kcal_over=150) -> bool`
  - `week_adherence_ok(flags, need=5) -> bool`
  - `propose_adjustment(rate_pct, adherence_ok, cfg) -> {"action","delta_kcal","reason"}`
    onde `action` ∈ `{"hold","cut","add","follow_plan"}`.

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_nutrition_adaptive.py  (adicionar)
from src.nutrition.adaptive import (
    is_adherent_day, week_adherence_ok, propose_adjustment,
)
from src.nutrition.config import nutrition_config

CFG = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})


def test_dia_aderente():
    target = {"protein_g": 180, "kcal": 1780}
    assert is_adherent_day({"p": 170, "kcal": 1800}, target) is True   # p>=162, kcal<=1930
    assert is_adherent_day({"p": 150, "kcal": 1800}, target) is False  # proteina baixa
    assert is_adherent_day({"p": 170, "kcal": 2100}, target) is False  # estourou kcal


def test_semana_aderente_5_de_7():
    assert week_adherence_ok([True]*5 + [False]*2) is True
    assert week_adherence_ok([True]*4 + [False]*3) is False


def test_proposta_rapido_demais_soma():
    # rate -0.9 < fast_rate -0.7 -> +100 mesmo sem aderencia
    p = propose_adjustment(-0.9, adherence_ok=False, cfg=CFG)
    assert p["action"] == "add" and p["delta_kcal"] == 100


def test_proposta_travado_com_aderencia_corta():
    # rate -0.1 >= target_high -0.3 (travado) e aderente -> -100
    p = propose_adjustment(-0.1, adherence_ok=True, cfg=CFG)
    assert p["action"] == "cut" and p["delta_kcal"] == -100


def test_proposta_travado_sem_aderencia_segue_plano():
    p = propose_adjustment(-0.1, adherence_ok=False, cfg=CFG)
    assert p["action"] == "follow_plan" and p["delta_kcal"] == 0


def test_proposta_no_ritmo_mantem():
    # -0.35 entre -0.7 e -0.3 -> hold
    p = propose_adjustment(-0.35, adherence_ok=True, cfg=CFG)
    assert p["action"] == "hold" and p["delta_kcal"] == 0


def test_proposta_sem_rate_mantem():
    p = propose_adjustment(None, adherence_ok=True, cfg=CFG)
    assert p["action"] == "hold"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/test_nutrition_adaptive.py -k proposta -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementação**

```python
# src/nutrition/adaptive.py  (adicionar)
def is_adherent_day(totals, target, protein_frac=0.9, kcal_over=150):
    return (totals["p"] >= protein_frac * target["protein_g"]
            and totals["kcal"] <= target["kcal"] + kcal_over)


def week_adherence_ok(flags, need=5):
    return sum(1 for f in flags if f) >= need


def propose_adjustment(rate_pct, adherence_ok, cfg):
    if rate_pct is None:
        return {"action": "hold", "delta_kcal": 0, "reason": "sem dado de peso suficiente"}
    if rate_pct <= cfg["fast_rate"]:
        return {"action": "add", "delta_kcal": 100,
                "reason": "caindo rápido demais — risco de perder músculo"}
    if rate_pct >= cfg["target_rate_high"]:   # travado (perde pouco ou nada)
        if adherence_ok:
            return {"action": "cut", "delta_kcal": -100,
                    "reason": "peso travado com boa aderência — apertar o alvo"}
        return {"action": "follow_plan", "delta_kcal": 0,
                "reason": "peso travado, mas aderência baixa — segue o plano primeiro"}
    return {"action": "hold", "delta_kcal": 0, "reason": "no ritmo alvo"}
```

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/test_nutrition_adaptive.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/adaptive.py tests/test_nutrition_adaptive.py
git commit -m "feat(nutrition): gate de aderencia e proposta de ajuste"
```

---

### Task 7: `store` — aderência da semana + persistência do ajuste

**Files:**
- Modify: `src/nutrition/store.py`
- Test: `tests/test_nutrition_store.py`

**Interfaces:**
- Consumes: `meal_log`, `day_plan` (via funções já existentes), `bot_state` (tabela existente).
- Produces:
  - `store.get_kcal_adjust(db_path) -> int` (lê de `bot_state`, default 0)
  - `store.set_kcal_adjust(db_path, value)`
  - `store.week_totals(db_path, dates) -> list[dict]` (um `day_totals` por data da lista).

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_nutrition_store.py  (adicionar)
def test_kcal_adjust_default_zero(tmp_path):
    p = _db(tmp_path)
    assert store.get_kcal_adjust(p) == 0


def test_kcal_adjust_roundtrip(tmp_path):
    p = _db(tmp_path)
    store.set_kcal_adjust(p, -100)
    assert store.get_kcal_adjust(p) == -100


def test_week_totals(tmp_path):
    p = _db(tmp_path)
    store.save_meal_items(p, "2026-06-29", "almoço",
                          [{"recognized": True, "food": "x", "grams": 10,
                            "kcal": 500, "p": 40, "c": 10, "g": 5}])
    tots = store.week_totals(p, ["2026-06-29", "2026-06-30"])
    assert round(tots[0]["kcal"]) == 500 and tots[1]["kcal"] == 0
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/test_nutrition_store.py::test_kcal_adjust_roundtrip -v`
Expected: FAIL (`AttributeError: module ... has no attribute 'set_kcal_adjust'`).

- [ ] **Step 3: Implementação**

```python
# src/nutrition/store.py  (adicionar)
def get_kcal_adjust(db_path) -> int:
    with _session(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM bot_state WHERE key='nutri_kcal_adjust'"
        ).fetchone()
    return int(row["value"]) if row and row["value"] is not None else 0


def set_kcal_adjust(db_path, value):
    with _session(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_state (key, value) VALUES ('nutri_kcal_adjust', ?)",
            (str(int(value)),),
        )


def week_totals(db_path, dates) -> list:
    return [day_totals(db_path, d) for d in dates]
```

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/test_nutrition_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/store.py tests/test_nutrition_store.py
git commit -m "feat(nutrition): persistencia do ajuste kcal + totais da semana"
```

---

### Task 8: `bot` — comando `/peso` + carregar ajuste no cfg

**Files:**
- Modify: `bot/handlers.py`
- Modify: `bot/nutrition.py` (onde o cfg é montado pra alvos — `today_panel`/`load` do perfil)
- Test: `tests/bot/test_bot_nutrition.py`

**Interfaces:**
- Consumes: `store.add_weight`, `store.get_kcal_adjust`, `nutrition_config`, `day_target`.
- Produces:
  - `cmd_peso(update, context)` — parse `/peso 107.4`, grava via `store.add_weight`, confirma.
  - helper puro `parse_peso_arg(text) -> float | None` em `bot/nutrition.py` (testável).
  - cfg de alvos passa a incluir `kcal_adjust=store.get_kcal_adjust(db)` antes de `day_target`.

- [ ] **Step 1: Escrever teste que falha (função pura de parse)**

```python
# tests/bot/test_bot_nutrition.py  (adicionar)
from bot.nutrition import parse_peso_arg


def test_parse_peso_ok():
    assert parse_peso_arg("107.4") == 107.4
    assert parse_peso_arg("107,4") == 107.4     # vírgula PT-BR
    assert parse_peso_arg("  108 ") == 108.0


def test_parse_peso_invalido():
    assert parse_peso_arg("") is None
    assert parse_peso_arg("abc") is None
    assert parse_peso_arg("0") is None          # peso zero não faz sentido
    assert parse_peso_arg("500") is None        # fora de faixa humana plausível
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/bot/test_bot_nutrition.py::test_parse_peso_ok -v`
Expected: FAIL (`ImportError: cannot import name 'parse_peso_arg'`).

- [ ] **Step 3: Implementação**

Em `bot/nutrition.py` (adicionar):

```python
def parse_peso_arg(text):
    """'107,4' | '107.4' -> 107.4 ; inválido/fora de faixa -> None."""
    if not text:
        return None
    try:
        v = float(text.strip().replace(",", "."))
    except ValueError:
        return None
    if not (30.0 <= v <= 300.0):
        return None
    return v
```

Onde o cfg é montado pra `day_target` (na função que gera o painel `/dieta`/alvo em `bot/nutrition.py`), incluir o ajuste:

```python
    cfg = nutrition_config(profile)
    cfg["kcal_adjust"] = store.get_kcal_adjust(db_path)
```

Em `bot/handlers.py` (adicionar handler; registrar o `CommandHandler("peso", cmd_peso)` junto aos outros):

```python
async def cmd_peso(update, context):
    import datetime as dt
    from bot.nutrition import parse_peso_arg
    import src.nutrition.store as store
    arg = " ".join(context.args) if context.args else ""
    kg = parse_peso_arg(arg)
    if kg is None:
        await update.message.reply_text("Uso: /peso 107.4")
        return
    today = dt.date.today().isoformat()
    store.add_weight(context.bot_data["db_path"], today, kg, source="manual")
    await update.message.reply_text(f"Peso salvo: {kg:.1f} kg ✅")
```

(Adaptar `context.bot_data["db_path"]` ao acessor de db_path já usado nos outros handlers do arquivo.)

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/bot/test_bot_nutrition.py -v`
Expected: PASS. Também rodar smoke de import: `python -c "import bot.handlers"`.

- [ ] **Step 5: Commit**

```bash
git add bot/nutrition.py bot/handlers.py tests/bot/test_bot_nutrition.py
git commit -m "feat(bot): comando /peso e ajuste kcal aplicado no alvo"
```

---

### Task 9: `bot` — `/progresso`, job semanal e botões aplicar/manter

**Files:**
- Modify: `bot/handlers.py` (`/progresso`, callbacks `nut:adj:apply|hold`)
- Modify: `bot/jobs.py` (`job_weekly_weight`)
- Modify: `bot/nutrition.py` (builder puro do relatório)
- Modify: `bot/main.py` (registrar handlers + job)
- Test: `tests/bot/test_bot_nutrition.py`

**Interfaces:**
- Consumes: `store.get_weights`, `store.week_totals`, `store.get_day_plan`, `adaptive.*`, `day_target`, `nutrition_config`.
- Produces:
  - `build_progress_report(weights, week_days, cfg, prev_bf, prev_weight) -> {"text","proposal"}` (puro, em `bot/nutrition.py`).
  - `cmd_progresso(update, context)` — monta e envia com botões se `proposal["action"] in {"cut","add"}`.
  - callbacks `nut:adj:apply` (aplica `store.set_kcal_adjust` somando o delta) e `nut:adj:hold`.
  - `job_weekly_weight(context)` — pergunta o peso da semana no chat.

- [ ] **Step 1: Escrever teste que falha (builder puro do relatório)**

```python
# tests/bot/test_bot_nutrition.py  (adicionar)
from bot.nutrition import build_progress_report
from src.nutrition.config import nutrition_config

_CFG = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})


def test_report_travado_com_aderencia_propoe_corte():
    weights = [108.0, 107.9, 107.9]           # praticamente travado
    # 5 de 7 dias aderentes (proteína ok, kcal ok)
    week_days = [{"p": 185, "kcal": 1800, "training": False}] * 5 + \
                [{"p": 100, "kcal": 2500, "training": False}] * 2
    rep = build_progress_report(weights, week_days, _CFG, prev_bf=30.0, prev_weight=108.0)
    assert rep["proposal"]["action"] == "cut"
    assert "estimado" in rep["text"].lower()   # BF marcado


def test_report_sem_peso_nao_propoe():
    rep = build_progress_report([107.4], [], _CFG, prev_bf=30.0, prev_weight=108.0)
    assert rep["proposal"]["action"] == "hold"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `python -m pytest tests/bot/test_bot_nutrition.py::test_report_sem_peso_nao_propoe -v`
Expected: FAIL (`ImportError: cannot import name 'build_progress_report'`).

- [ ] **Step 3: Implementação**

Em `bot/nutrition.py` (adicionar):

```python
from src.nutrition.adaptive import (
    trend_kg, weekly_rate_pct, derive_bf,
    is_adherent_day, week_adherence_ok, propose_adjustment,
)
from src.nutrition.targets import day_target


def build_progress_report(weights, week_days, cfg, prev_bf, prev_weight):
    """weights: lista de kg (cronológica). week_days: list de dicts com p,kcal,training."""
    trend = trend_kg(weights)
    rate = weekly_rate_pct(weights)

    flags = []
    for d in week_days:
        target = day_target(cfg, training=d.get("training", False))
        flags.append(is_adherent_day({"p": d["p"], "kcal": d["kcal"]}, target))
    adher_ok = week_adherence_ok(flags)

    proposal = propose_adjustment(rate, adher_ok, cfg)

    bf = derive_bf(prev_weight, prev_bf, weights[-1]) if weights else prev_bf
    lbm = (weights[-1] if weights else prev_weight) * (1 - bf / 100.0)

    lines = ["📊 *Progresso*"]
    if trend is not None:
        lines.append(f"Peso (tendência): {trend:.1f} kg")
    if rate is not None:
        lines.append(f"Ritmo: {rate:+.2f}%/sem")
    lines.append(f"BF estimado: {bf:.1f}% · LBM {lbm:.1f} kg")
    lines.append(f"Aderência: {sum(flags)}/{len(flags) if flags else 0} dias")
    lines.append(f"→ {proposal['reason']}")
    return {"text": "\n".join(lines), "proposal": proposal}
```

Em `bot/handlers.py`:

```python
async def cmd_progresso(update, context):
    import datetime as dt
    import src.nutrition.store as store
    from bot.nutrition import build_progress_report, _load_profile  # _load_profile: acessor já usado
    from src.nutrition.config import nutrition_config
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    db = context.bot_data["db_path"]
    profile = _load_profile()
    cfg = nutrition_config(profile)
    cfg["kcal_adjust"] = store.get_kcal_adjust(db)

    ws = [w["kg"] for w in store.get_weights(db)]
    today = dt.date.today()
    dates = [(today - dt.timedelta(days=i)).isoformat() for i in range(1, 8)]
    tots = store.week_totals(db, dates)
    week_days = []
    for d, t in zip(dates, tots):
        plan = store.get_day_plan(db, d) or {}
        training = bool(plan.get("vai_treinar") or plan.get("vai_correr"))
        week_days.append({"p": t["p"], "kcal": t["kcal"], "training": training})

    prev_bf = float(profile.get("percentual_gordura") or 30)
    prev_weight = float(profile.get("peso_kg") or (ws[0] if ws else 108))
    rep = build_progress_report(ws, week_days, cfg, prev_bf, prev_weight)

    markup = None
    if rep["proposal"]["action"] in ("cut", "add"):
        delta = rep["proposal"]["delta_kcal"]
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ aplicar", callback_data=f"nut:adj:apply:{delta}"),
            InlineKeyboardButton("✋ manter", callback_data="nut:adj:hold"),
        ]])
    await update.message.reply_text(rep["text"], parse_mode="Markdown", reply_markup=markup)


async def on_adjust_button(update, context):
    import src.nutrition.store as store
    q = update.callback_query
    await q.answer()
    db = context.bot_data["db_path"]
    if q.data.startswith("nut:adj:apply:"):
        delta = int(q.data.split(":")[-1])
        novo = store.get_kcal_adjust(db) + delta
        store.set_kcal_adjust(db, novo)
        await q.edit_message_text(f"Alvo ajustado em {delta:+d} kcal. Novo ajuste: {novo:+d}. ✅")
    else:
        await q.edit_message_text("Alvo mantido. ✋")
```

Em `bot/jobs.py`:

```python
async def job_weekly_weight(context):
    chat_id = context.job.data["chat_id"] if context.job.data else context.bot_data.get("chat_id")
    await context.bot.send_message(
        chat_id, "🗓 Peso da semana? Manda com /peso 107.4"
    )
```

Em `bot/main.py`, registrar (junto aos outros `add_handler` / `job_queue`):

```python
    app.add_handler(CommandHandler("peso", cmd_peso))
    app.add_handler(CommandHandler("progresso", cmd_progresso))
    app.add_handler(CallbackQueryHandler(on_adjust_button, pattern=r"^nut:adj:"))
    # job semanal: domingo 09:00 TZ do bot
    app.job_queue.run_daily(
        job_weekly_weight, time=_time(9, 0), days=(6,),  # 6 = domingo (python-telegram-bot)
        data={"chat_id": config.chat_id},
    )
```

(Usar os imports/acessadores já presentes no `main.py`: `CommandHandler`, `CallbackQueryHandler`, helper de `time`, `config.chat_id`.)

- [ ] **Step 4: Rodar — deve passar**

Run: `python -m pytest tests/bot/test_bot_nutrition.py -v`
Expected: PASS. Smoke de import: `python -c "import bot.handlers, bot.jobs, bot.main"`.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers.py bot/jobs.py bot/nutrition.py bot/main.py tests/bot/test_bot_nutrition.py
git commit -m "feat(bot): /progresso, job de peso semanal e botoes aplicar/manter"
```

---

### Task 10: Atualizar `athlete_profile.json` e suíte completa

**Files:**
- Modify: `athlete_profile.json`
- Test: suíte inteira

**Interfaces:**
- Consumes: config novo.
- Produces: perfil sem `deficit_kcal` obsoleto; bloco `nutricao` alinhado aos defaults.

- [ ] **Step 1: Ajustar o perfil**

```json
  "nutricao": {
    "neat_factor": 1.3,
    "protein_g": 180,
    "fat_g": 60,
    "carb_rest_g": 130,
    "carb_train_g": 200,
    "deficit_floor": 900,
    "ea_low": 25,
    "ea_ok": 30
  }
```

(Remover `deficit_kcal` e `protein_g:165` antigos. Valores omitidos caem no default do config.)

- [ ] **Step 2: Rodar suíte inteira**

Run: `python -m pytest -q`
Expected: PASS (todos ~360+). Se algum teste antigo assumia `deficit_kcal`/carbo 226, atualizar pro modelo novo.

- [ ] **Step 3: Commit**

```bash
git add athlete_profile.json
git commit -m "chore(nutrition): perfil alinhado ao modelo de carbo ciclado"
```

---

## Self-Review

**Spec coverage:**
- Bloco 1 (carbo ciclado/capado + piso) → Tasks 1, 2. ✓
- Bloco 2 (peso semanal, tendência, auto-correção proposta, BF derivado) → Tasks 3, 4, 5, 6, 8, 9. ✓
- Bloco 3 (relatório + gate de aderência) → Tasks 6, 7, 9. ✓
- Migração sem quebrar `/dieta` (mesmas chaves de retorno) → Task 2 nota + Task 10. ✓
- Arquivos afetados do spec (config, targets, adaptive, store, history_db, handlers, jobs, charts, profile) → cobertos, exceto `charts.py` (linha de tendência era "opcional" no spec → YAGNI, fora deste plano). ✓

**Placeholder scan:** sem TBD/TODO; todo step tem código concreto. Handlers de IO trazem código real com nota pra alinhar acessores de `db_path`/`profile` aos já existentes (não são placeholders — são pontos de integração reais que o implementador confirma lendo o arquivo).

**Type consistency:** `day_target` mantém chaves `kcal/protein_g/fat_g/carb_g`. `propose_adjustment` retorna `action∈{hold,cut,add,follow_plan}` usado igual na Task 9. `derive_bf(prev_weight, prev_bf, new_weight)` chamado com essa ordem no relatório. `store.get_kcal_adjust/set_kcal_adjust` consistentes entre Tasks 7, 8, 9. ✓

## Nota de integração (bot)
As Tasks 8–9 tocam handlers grandes de IO. O implementador deve **ler `bot/handlers.py`, `bot/main.py`, `bot/jobs.py`, `bot/nutrition.py` antes** e alinhar: acessor de `db_path` (pode ser `context.bot_data`, `Config`, ou global), acessor do perfil (`_load_profile` é ilustrativo — usar o que existe), e o registro de handlers/jobs ao padrão do arquivo. A lógica pura (Tasks 1–7) é o núcleo testado; os handlers são cola.
