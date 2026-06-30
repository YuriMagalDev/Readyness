# Nutrição: tracking de refeições + macros + energia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar refeições em linguagem natural no bot Telegram → kcal/macros via tabela TACO (determinístico), com alvo diário ciclado por treino, aviso de energia disponível, painel `/dieta` em PNG, e cadastro de alimentos novos por foto da tabela nutricional (Claude vision) ou digitação manual.

**Architecture:** Módulo isolado `src/nutrition/` com unidades puras (`food_db`, `meal_parser`, `targets`) + acesso a dados (`store`) + leitura de rótulo por visão (`label_vision`). Tabelas novas no `history.db` (mesmo padrão de `src/history_db.py`). Bot ganha comandos `/comi` e `/dieta`, fluxo de cadastro de alimento desconhecido, e um job matinal que pergunta o plano do dia. Gráfico via `bot/charts.py` (matplotlib Agg → PNG), reaproveitando o padrão existente.

**Tech Stack:** Python 3.11, sqlite3, `rapidfuzz` (match fuzzy), `matplotlib` (PNG), `anthropic` (Claude vision, só no cadastro por foto), `python-telegram-bot[job-queue]`, `pytest`.

## Global Constraints

- **Número sai de fonte real (TACO ou `custom_foods`), nunca inventado.** Match fuzzy abaixo do limiar = item "não reconhecido"; jamais chuta valor.
- **Determinístico no caminho quente.** A API Anthropic é tocada SÓ em `label_vision` (cadastro de alimento novo por foto), uma vez por produto; resultado cacheado em `custom_foods`.
- **Confirmação antes de salvar** toda refeição e todo cadastro (substitui a segurança que o LLM daria).
- **TDD por camada, commits pequenos.** Tabelas novas via `CREATE TABLE IF NOT EXISTS` no padrão de `src/history_db.py` (não quebrar tabelas existentes).
- **Sem dado sensível em log.** Não logar conteúdo de refeição com identificação; mascarar credenciais.
- Testes não batem na rede: `label_vision` recebe um cliente injetável e é mockado nos testes.
- Perfil do atleta (`athlete_profile.json`): valores atuais a usar — idade 25, peso 108 kg, altura 181 cm, %gordura 30. Parâmetros de nutrição têm defaults no código mas são sobrescritos pelo perfil.

---

### Task 1: Campos de nutrição no perfil + leitor de config

**Files:**
- Modify: `athlete_profile.json`
- Create: `src/nutrition/__init__.py`
- Create: `src/nutrition/config.py`
- Test: `tests/test_nutrition_config.py`

**Interfaces:**
- Produces: `nutrition_config(profile: dict) -> dict` retornando chaves `peso_kg, percentual_gordura, lbm_kg, neat_factor, deficit_kcal, protein_g, fat_g, ea_low, ea_ok`. `lbm_kg = peso_kg * (1 - percentual_gordura/100)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nutrition_config.py
from src.nutrition.config import nutrition_config


def test_defaults_e_lbm():
    cfg = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})
    assert round(cfg["lbm_kg"], 1) == 75.6
    assert cfg["neat_factor"] == 1.3
    assert cfg["deficit_kcal"] == 500
    assert cfg["protein_g"] == 165
    assert cfg["fat_g"] == 60
    assert cfg["ea_low"] == 25 and cfg["ea_ok"] == 30


def test_perfil_sobrescreve_defaults():
    cfg = nutrition_config({"peso_kg": 100, "percentual_gordura": 20,
                            "nutricao": {"deficit_kcal": 300, "protein_g": 180}})
    assert cfg["deficit_kcal"] == 300
    assert cfg["protein_g"] == 180
    assert cfg["fat_g"] == 60  # não sobrescrito → default
    assert round(cfg["lbm_kg"], 1) == 80.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_nutrition_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.nutrition'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nutrition/__init__.py
```

```python
# src/nutrition/config.py
_DEFAULTS = {
    "neat_factor": 1.3,
    "deficit_kcal": 500,
    "protein_g": 165,
    "fat_g": 60,
    "ea_low": 25,
    "ea_ok": 30,
}


def nutrition_config(profile: dict) -> dict:
    peso = float(profile.get("peso_kg") or 0)
    bf = float(profile.get("percentual_gordura") or 0)
    over = dict(profile.get("nutricao") or {})
    cfg = {**_DEFAULTS, **over}
    cfg["peso_kg"] = peso
    cfg["percentual_gordura"] = bf
    cfg["lbm_kg"] = peso * (1 - bf / 100)
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_nutrition_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Update athlete_profile.json**

Atualizar os valores para os atuais e adicionar o bloco `nutricao` (defaults explícitos para visibilidade):

```json
{
  "nome": "Yuri",
  "idade": 25,
  "sexo": "masculino",
  "peso_kg": 108,
  "altura_cm": 181,
  "imc": 33,
  "percentual_gordura": 30,
  "circunferencia_cintura_cm": 107,
  "circunferencia_quadril_cm": 112,
  "objetivo_principal": "melhorar pace corrida + hipertrofia",
  "nivel_corrida": "intermediário",
  "nivel_musculacao": "intermediário",
  "restricoes_medicas": [],
  "meta_peso_kg": 95,
  "dias_disponiveis_treino": 5,
  "nutricao": {
    "neat_factor": 1.3,
    "deficit_kcal": 500,
    "protein_g": 165,
    "fat_g": 60,
    "ea_low": 25,
    "ea_ok": 30
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add src/nutrition/__init__.py src/nutrition/config.py tests/test_nutrition_config.py athlete_profile.json
git commit -m "feat(nutrition): config de nutricao + campos no perfil"
```

---

### Task 2: Alvos do dia + energia disponível (`targets.py`)

**Files:**
- Create: `src/nutrition/targets.py`
- Test: `tests/test_nutrition_targets.py`

**Interfaces:**
- Consumes: `nutrition_config(profile) -> dict` (Task 1).
- Produces:
  - `tdee_base(cfg) -> float` — `(370 + 21.6*lbm) * neat_factor`
  - `day_target(cfg, *, training: bool, exercise_kcal: float = 0.0) -> dict` →
    `{"kcal": float, "protein_g": float, "fat_g": float, "carb_g": float}`
  - `energy_availability(cfg, intake_kcal: float, exercise_kcal: float) -> dict` →
    `{"ea": float, "faixa": "verde"|"amarelo"|"vermelho"}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nutrition_targets.py
from src.nutrition.config import nutrition_config
from src.nutrition.targets import tdee_base, day_target, energy_availability

CFG = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})


def test_tdee_base():
    # bmr = 370 + 21.6*75.6 = 2002.96 ; *1.3 = 2603.8
    assert round(tdee_base(CFG)) == 2604


def test_dia_descanso():
    t = day_target(CFG, training=False)
    assert round(t["kcal"]) == 2104          # 2603.8 - 500
    assert t["protein_g"] == 165
    assert t["fat_g"] == 60
    # carb = (2104 - 165*4 - 60*9)/4 = (2104 - 660 - 540)/4 = 226
    assert round(t["carb_g"]) == 226


def test_dia_treino_soma_exercicio():
    t = day_target(CFG, training=True, exercise_kcal=400)
    assert round(t["kcal"]) == 2504          # descanso + 400
    assert round(t["carb_g"]) == 326         # +100g carbo


def test_energia_faixas():
    assert energy_availability(CFG, intake_kcal=2604, exercise_kcal=400)["faixa"] == "verde"
    # (2000-400)/75.6 = 21.2 -> vermelho
    assert energy_availability(CFG, intake_kcal=2000, exercise_kcal=400)["faixa"] == "vermelho"
    # (2300-400)/75.6 = 25.1 -> amarelo
    assert energy_availability(CFG, intake_kcal=2300, exercise_kcal=400)["faixa"] == "amarelo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_nutrition_targets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.nutrition.targets'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nutrition/targets.py


def tdee_base(cfg: dict) -> float:
    bmr = 370 + 21.6 * cfg["lbm_kg"]
    return bmr * cfg["neat_factor"]


def day_target(cfg: dict, *, training: bool, exercise_kcal: float = 0.0) -> dict:
    kcal = tdee_base(cfg) - cfg["deficit_kcal"]
    if training:
        kcal += exercise_kcal
    protein_g = cfg["protein_g"]
    fat_g = cfg["fat_g"]
    carb_g = max(0.0, (kcal - protein_g * 4 - fat_g * 9) / 4)
    return {"kcal": kcal, "protein_g": protein_g, "fat_g": fat_g, "carb_g": carb_g}


def energy_availability(cfg: dict, intake_kcal: float, exercise_kcal: float) -> dict:
    lbm = cfg["lbm_kg"]
    ea = (intake_kcal - exercise_kcal) / lbm if lbm else 0.0
    if ea >= cfg["ea_ok"]:
        faixa = "verde"
    elif ea >= cfg["ea_low"]:
        faixa = "amarelo"
    else:
        faixa = "vermelho"
    return {"ea": ea, "faixa": faixa}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_nutrition_targets.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/targets.py tests/test_nutrition_targets.py
git commit -m "feat(nutrition): alvos do dia ciclados + energia disponivel"
```

---

### Task 3: Tabela TACO + loader/lookup exato (`food_db.py` parte 1)

**Files:**
- Create: `src/nutrition/data/taco.csv` (base TACO; obter da fonte aberta — ver passo 5)
- Create: `tests/fixtures/taco_min.csv` (fixture pequena pros testes)
- Create: `src/nutrition/food_db.py`
- Test: `tests/test_food_db.py`

**Interfaces:**
- Produces:
  - `normalize(name: str) -> str` — minúsculo, sem acento, sem espaço extra.
  - `class FoodDB:` construída com `FoodDB(csv_path, custom=None)`.
    - `FoodDB.lookup(name: str) -> dict | None` → `{"name", "per100": {"kcal","p","c","g"}}` ou `None`.
  - CSV columns (header exato): `nome,kcal,proteina,carboidrato,gordura` (valores por 100 g).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_food_db.py
from src.nutrition.food_db import FoodDB, normalize

FIX = "tests/fixtures/taco_min.csv"


def test_normalize():
    assert normalize("  Peito de Frango  ") == "peito de frango"
    assert normalize("Açúcar") == "acucar"


def test_lookup_exato():
    db = FoodDB(FIX)
    item = db.lookup("arroz cozido")
    assert item["per100"]["kcal"] == 128
    assert item["per100"]["p"] == 2.5


def test_lookup_normaliza():
    db = FoodDB(FIX)
    assert db.lookup("ARROZ COZIDO")["per100"]["kcal"] == 128


def test_lookup_inexistente():
    db = FoodDB(FIX)
    assert db.lookup("dragon fruit") is None
```

- [ ] **Step 2: Create the test fixture**

```csv
# tests/fixtures/taco_min.csv
nome,kcal,proteina,carboidrato,gordura
arroz cozido,128,2.5,28,0.2
peito de frango grelhado,159,31,0,3.6
ovo de galinha cozido,143,13,1.1,9.5
feijao carioca cozido,76,4.8,13.6,0.5
banana prata,98,1.3,26,0.1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_food_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.nutrition.food_db'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/nutrition/food_db.py
import csv
import unicodedata


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


class FoodDB:
    def __init__(self, csv_path: str, custom=None):
        self._by_name = {}
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = normalize(row["nome"])
                self._by_name[key] = {
                    "name": row["nome"],
                    "per100": {
                        "kcal": float(row["kcal"]),
                        "p": float(row["proteina"]),
                        "c": float(row["carboidrato"]),
                        "g": float(row["gordura"]),
                    },
                }

    def lookup(self, name: str):
        return self._by_name.get(normalize(name))
```

- [ ] **Step 5: Obtain the real TACO CSV**

Gerar `src/nutrition/data/taco.csv` a partir da Tabela TACO (USP/NEPA, dados abertos), com o header exato `nome,kcal,proteina,carboidrato,gordura` e valores por 100 g. Manter ~600 itens de alimentos comuns. (Os testes usam só a fixture; este passo provê os dados de produção.)

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_food_db.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Commit**

```bash
git add src/nutrition/food_db.py src/nutrition/data/taco.csv tests/fixtures/taco_min.csv tests/test_food_db.py
git commit -m "feat(nutrition): FoodDB carrega TACO + lookup exato normalizado"
```

---

### Task 4: Match fuzzy + aliases + porções unitárias (`food_db.py` parte 2)

**Files:**
- Modify: `src/nutrition/food_db.py`
- Modify: `requirements.txt` (adicionar `rapidfuzz>=3.0`)
- Test: `tests/test_food_db.py` (adicionar casos)

**Interfaces:**
- Produces:
  - `FoodDB.match(name: str, threshold: int = 85) -> dict | None` — exato → alias → fuzzy; retorna `{"name","per100","score"}` ou `None` abaixo do limiar.
  - `FoodDB.portion_grams(name: str) -> float | None` — gramas de 1 unidade (ovo, banana, fatia...) ou `None`.
  - Constantes `ALIASES: dict[str,str]` e `PORTIONS: dict[str,float]` (chaves normalizadas).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_food_db.py  (adicionar)
def test_match_alias():
    db = FoodDB(FIX)
    m = db.match("frango")
    assert m["name"] == "peito de frango grelhado"


def test_match_fuzzy_acima_do_limiar():
    db = FoodDB(FIX)
    m = db.match("arroz cozido")          # exato
    assert m["score"] == 100
    m2 = db.match("arrloz cozido")        # typo
    assert m2 is not None and m2["name"] == "arroz cozido"


def test_match_abaixo_do_limiar():
    db = FoodDB(FIX)
    assert db.match("xyzqwk", threshold=85) is None


def test_porcao_unitaria():
    db = FoodDB(FIX)
    assert db.portion_grams("ovo") == 50
    assert db.portion_grams("banana") == 100
    assert db.portion_grams("arroz cozido") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_food_db.py -v`
Expected: FAIL — `AttributeError: 'FoodDB' object has no attribute 'match'`

- [ ] **Step 3: Add rapidfuzz to requirements**

Adicionar a linha `rapidfuzz>=3.0` em `requirements.txt` e instalar:

Run: `pip install "rapidfuzz>=3.0"`

- [ ] **Step 4: Write minimal implementation**

```python
# src/nutrition/food_db.py  (adicionar imports e métodos)
from rapidfuzz import process, fuzz

ALIASES = {
    "frango": "peito de frango grelhado",
    "peito de frango": "peito de frango grelhado",
    "ovo": "ovo de galinha cozido",
    "feijao": "feijao carioca cozido",
    "banana": "banana prata",
    "arroz": "arroz cozido",
}

PORTIONS = {
    "ovo": 50.0,
    "banana": 100.0,
    "fatia de pao": 25.0,
    "pao": 25.0,
}
```

Adicionar métodos na classe `FoodDB`:

```python
    def match(self, name: str, threshold: int = 85):
        key = normalize(name)
        if key in self._by_name:
            item = self._by_name[key]
            return {**item, "score": 100}
        alias = ALIASES.get(key)
        if alias and normalize(alias) in self._by_name:
            item = self._by_name[normalize(alias)]
            return {**item, "score": 100}
        choices = list(self._by_name.keys())
        best = process.extractOne(key, choices, scorer=fuzz.WRatio)
        if best and best[1] >= threshold:
            item = self._by_name[best[0]]
            return {**item, "score": int(best[1])}
        return None

    def portion_grams(self, name: str):
        return PORTIONS.get(normalize(name))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_food_db.py -v`
Expected: PASS (8 passed)

- [ ] **Step 6: Commit**

```bash
git add src/nutrition/food_db.py requirements.txt tests/test_food_db.py
git commit -m "feat(nutrition): match fuzzy + aliases + porcoes unitarias"
```

---

### Task 5: Parser de refeição (`meal_parser.py`)

**Files:**
- Create: `src/nutrition/meal_parser.py`
- Test: `tests/test_meal_parser.py`

**Interfaces:**
- Consumes: `FoodDB.match`, `FoodDB.portion_grams` (Task 4).
- Produces:
  - `parse_meal(text: str, db: FoodDB) -> dict` →
    `{"meal": str|None, "items": [item, ...]}` onde cada item reconhecido é
    `{"raw","food","grams","kcal","p","c","g","recognized": True}` e cada
    não-reconhecido é `{"raw","recognized": False}`.
  - Macros calculados de `per100` proporcional aos gramas; quantidade unitária
    (`2 ovos`) usa `portion_grams`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_meal_parser.py
from src.nutrition.food_db import FoodDB
from src.nutrition.meal_parser import parse_meal

DB = FoodDB("tests/fixtures/taco_min.csv")


def test_parse_gramas_e_rotulo():
    out = parse_meal("almoço: 100g arroz, 200g peito de frango", DB)
    assert out["meal"] == "almoço"
    arroz, frango = out["items"]
    assert arroz["grams"] == 100 and round(arroz["kcal"]) == 128
    assert frango["grams"] == 200 and round(frango["kcal"]) == 318
    assert all(i["recognized"] for i in out["items"])


def test_parse_unidade():
    out = parse_meal("2 ovos", DB)
    item = out["items"][0]
    assert item["grams"] == 100            # 2 * 50g
    assert round(item["kcal"]) == 143      # 143/100 * 100


def test_parse_item_desconhecido():
    out = parse_meal("100g patinho", DB)
    item = out["items"][0]
    assert item["recognized"] is False
    assert item["raw"] == "100g patinho"


def test_parse_sem_rotulo_e_lixo():
    out = parse_meal("blah blah", DB)
    assert out["meal"] is None
    assert out["items"][0]["recognized"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_meal_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.nutrition.meal_parser'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nutrition/meal_parser.py
import re

_GRAMS = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*g\s+(.*)$", re.I)
_UNIT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s+(.*)$")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _macros(per100: dict, grams: float) -> dict:
    f = grams / 100.0
    return {k: per100[k] * f for k in ("kcal", "p", "c", "g")}


def _parse_item(raw: str, db) -> dict:
    raw = raw.strip()
    m = _GRAMS.match(raw)
    if m:
        grams, name = _num(m.group(1)), m.group(2)
        hit = db.match(name)
        if hit:
            return {"raw": raw, "food": hit["name"], "grams": grams,
                    "recognized": True, **_macros(hit["per100"], grams)}
        return {"raw": raw, "recognized": False}
    u = _UNIT.match(raw)
    if u:
        qty, name = _num(u.group(1)), u.group(2)
        pg = db.portion_grams(name)
        hit = db.match(name)
        if pg and hit:
            grams = qty * pg
            return {"raw": raw, "food": hit["name"], "grams": grams,
                    "recognized": True, **_macros(hit["per100"], grams)}
        return {"raw": raw, "recognized": False}
    return {"raw": raw, "recognized": False}


def parse_meal(text: str, db) -> dict:
    text = (text or "").strip()
    meal = None
    if ":" in text:
        head, rest = text.split(":", 1)
        if len(head.split()) <= 2:        # "almoço", "café da manhã" curto
            meal, text = head.strip(), rest.strip()
    parts = [p for p in re.split(r"[,\n]", text) if p.strip()]
    items = [_parse_item(p, db) for p in parts] or [{"raw": text, "recognized": False}]
    return {"meal": meal, "items": items}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_meal_parser.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/meal_parser.py tests/test_meal_parser.py
git commit -m "feat(nutrition): parser de refeicao (gramas/unidade + nao-reconhecido)"
```

---

### Task 6: Tabelas SQLite + acesso a dados (`store.py`)

**Files:**
- Modify: `src/history_db.py` (criar tabelas `meal_log`, `day_plan`, `custom_foods` no `_init_db`)
- Create: `src/nutrition/store.py`
- Test: `tests/test_nutrition_store.py`

**Interfaces:**
- Produces (em `src/nutrition/store.py`, todas recebem `db_path: str`):
  - `add_custom_food(db_path, name, base_unit, porcao_g, kcal, p, c, g)`
  - `get_custom_foods(db_path) -> dict[str, dict]` — chave normalizada → `{"name","base_unit","porcao_g","per100"|"per_portion"}` (ver Task 7 pra consumo).
  - `save_meal_items(db_path, date, meal, items)` — grava só itens `recognized`.
  - `day_totals(db_path, date) -> dict` → `{"kcal","p","c","g","n_meals","last_at"}`.
  - `delete_last_meal_item(db_path, date) -> bool`.
  - `set_day_plan(db_path, date, vai_treinar, vai_correr)` / `get_day_plan(db_path, date) -> dict|None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nutrition_store.py
import src.nutrition.store as store
from src.history_db import HistoryDB


def _db(tmp_path):
    p = str(tmp_path / "h.db")
    HistoryDB(p)                       # cria tabelas
    return p


def test_custom_food_roundtrip(tmp_path):
    p = _db(tmp_path)
    store.add_custom_food(p, "whey soldier", "porcao", 30, 120, 24, 3, 1.5)
    foods = store.get_custom_foods(p)
    assert "whey soldier" in foods
    assert foods["whey soldier"]["base_unit"] == "porcao"


def test_save_e_totais(tmp_path):
    p = _db(tmp_path)
    items = [
        {"recognized": True, "food": "arroz", "grams": 100, "kcal": 128, "p": 2.5, "c": 28, "g": 0.2},
        {"recognized": False, "raw": "patinho"},
    ]
    store.save_meal_items(p, "2026-06-30", "almoço", items)
    t = store.day_totals(p, "2026-06-30")
    assert round(t["kcal"]) == 128 and t["n_meals"] == 1


def test_apaga_ultimo(tmp_path):
    p = _db(tmp_path)
    store.save_meal_items(p, "2026-06-30", "almoço",
                          [{"recognized": True, "food": "x", "grams": 10,
                            "kcal": 10, "p": 1, "c": 1, "g": 1}])
    assert store.delete_last_meal_item(p, "2026-06-30") is True
    assert store.day_totals(p, "2026-06-30")["kcal"] == 0


def test_day_plan(tmp_path):
    p = _db(tmp_path)
    store.set_day_plan(p, "2026-06-30", vai_treinar=1, vai_correr=0)
    assert store.get_day_plan(p, "2026-06-30")["vai_treinar"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_nutrition_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.nutrition.store'`

- [ ] **Step 3: Add tables to history_db**

Em `src/history_db.py`, dentro do `with self._connect() as conn:` em `_init_db`, após a tabela `notified_activity`, adicionar:

```python
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meal_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, "
                "meal TEXT, food TEXT, grams REAL, kcal REAL, p REAL, c REAL, g REAL, "
                "logged_at TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS day_plan ("
                "date TEXT PRIMARY KEY, vai_treinar INTEGER, vai_correr INTEGER, set_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS custom_foods ("
                "name TEXT PRIMARY KEY, base_unit TEXT NOT NULL, porcao_g REAL, "
                "kcal REAL, p REAL, c REAL, g REAL, created_at TEXT NOT NULL)"
            )
```

- [ ] **Step 4: Write minimal implementation**

```python
# src/nutrition/store.py
import datetime as dt
import sqlite3

from src.nutrition.food_db import normalize


def _conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def add_custom_food(db_path, name, base_unit, porcao_g, kcal, p, c, g):
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO custom_foods "
            "(name, base_unit, porcao_g, kcal, p, c, g, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (normalize(name), base_unit, porcao_g, kcal, p, c, g,
             dt.datetime.now().isoformat()),
        )


def get_custom_foods(db_path) -> dict:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM custom_foods").fetchall()
    out = {}
    for r in rows:
        out[r["name"]] = {
            "name": r["name"],
            "base_unit": r["base_unit"],
            "porcao_g": r["porcao_g"],
            "macros": {"kcal": r["kcal"], "p": r["p"], "c": r["c"], "g": r["g"]},
        }
    return out


def save_meal_items(db_path, date, meal, items):
    now = dt.datetime.now().isoformat()
    rows = [
        (date, meal, it.get("food"), it.get("grams"),
         it["kcal"], it["p"], it["c"], it["g"], now)
        for it in items if it.get("recognized")
    ]
    if not rows:
        return
    with _conn(db_path) as conn:
        conn.executemany(
            "INSERT INTO meal_log (date, meal, food, grams, kcal, p, c, g, logged_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows,
        )


def day_totals(db_path, date) -> dict:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(kcal),0) k, COALESCE(SUM(p),0) p, "
            "COALESCE(SUM(c),0) c, COALESCE(SUM(g),0) g, "
            "COUNT(DISTINCT meal) nm, MAX(logged_at) last "
            "FROM meal_log WHERE date=?", (date,),
        ).fetchone()
    return {"kcal": row["k"], "p": row["p"], "c": row["c"], "g": row["g"],
            "n_meals": row["nm"], "last_at": row["last"]}


def delete_last_meal_item(db_path, date) -> bool:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM meal_log WHERE date=? ORDER BY id DESC LIMIT 1", (date,),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM meal_log WHERE id=?", (row["id"],))
    return True


def set_day_plan(db_path, date, vai_treinar, vai_correr):
    with _conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO day_plan (date, vai_treinar, vai_correr, set_at) "
            "VALUES (?,?,?,?)",
            (date, vai_treinar, vai_correr, dt.datetime.now().isoformat()),
        )


def get_day_plan(db_path, date):
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM day_plan WHERE date=?", (date,)).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_nutrition_store.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/history_db.py src/nutrition/store.py tests/test_nutrition_store.py
git commit -m "feat(nutrition): tabelas meal_log/day_plan/custom_foods + store"
```

---

### Task 7: FoodDB integra `custom_foods`

**Files:**
- Modify: `src/nutrition/food_db.py`
- Test: `tests/test_food_db.py` (adicionar)

**Interfaces:**
- Consumes: `store.get_custom_foods` shape (Task 6): `{norm_name: {"name","base_unit","porcao_g","macros"}}`.
- Produces:
  - `FoodDB(csv_path, custom=None)` aceita `custom` (dict no shape acima). Itens custom têm prioridade no `match`.
  - `FoodDB.match` retorna, para custom com `base_unit="porcao"`, a chave extra `"per_portion": {"kcal","p","c","g"}` e `"portion_g"`; para `base_unit="100g"` retorna `per100` como TACO.
  - `FoodDB.portion_grams` também resolve `porcao_g` de itens custom.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_food_db.py  (adicionar)
def test_custom_food_prioridade_e_porcao():
    custom = {
        "whey soldier": {
            "name": "whey soldier", "base_unit": "porcao", "porcao_g": 30,
            "macros": {"kcal": 120, "p": 24, "c": 3, "g": 1.5},
        }
    }
    db = FoodDB(FIX, custom=custom)
    m = db.match("whey soldier")
    assert m["per_portion"]["p"] == 24
    assert m["portion_g"] == 30
    assert db.portion_grams("whey soldier") == 30


def test_custom_100g_vira_per100():
    custom = {
        "tapioca": {"name": "tapioca", "base_unit": "100g", "porcao_g": None,
                    "macros": {"kcal": 240, "p": 0.5, "c": 60, "g": 0.1}}
    }
    db = FoodDB(FIX, custom=custom)
    assert db.match("tapioca")["per100"]["kcal"] == 240
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_food_db.py::test_custom_food_prioridade_e_porcao -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'custom'`

- [ ] **Step 3: Write minimal implementation**

No `__init__` de `FoodDB`, após carregar o CSV, mesclar custom (sobrescreve TACO):

```python
        self._custom = {}
        for key, c in (custom or {}).items():
            self._custom[normalize(key)] = c
```

Adicionar resolução de custom no início de `match` (antes do lookup TACO):

```python
    def match(self, name: str, threshold: int = 85):
        key = normalize(name)
        if key in self._custom:
            c = self._custom[key]
            base = {"name": c["name"], "score": 100}
            if c["base_unit"] == "porcao":
                base["per_portion"] = c["macros"]
                base["portion_g"] = c["porcao_g"]
            else:
                base["per100"] = c["macros"]
            return base
        if key in self._by_name:
            ...  # (resto inalterado)
```

E em `portion_grams`, antes do `PORTIONS.get`:

```python
    def portion_grams(self, name: str):
        key = normalize(name)
        c = self._custom.get(key)
        if c and c.get("porcao_g"):
            return c["porcao_g"]
        return PORTIONS.get(key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_food_db.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/food_db.py tests/test_food_db.py
git commit -m "feat(nutrition): custom_foods com prioridade no match (100g/porcao)"
```

---

### Task 8: Parser usa porção custom; consumo de `per_portion`

**Files:**
- Modify: `src/nutrition/meal_parser.py`
- Test: `tests/test_meal_parser.py` (adicionar)

**Interfaces:**
- Consumes: `FoodDB.match` retornando `per_portion`+`portion_g` (custom porção) ou `per100` (Task 7).
- Produces: `_parse_item` lida com 3 formas: `Ng <food>` (per100), `N <unit-food>` com `portion_grams`, e `N <custom-porcao>` (ex. `1 scoop whey soldier`) usando `per_portion` direto × quantidade.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_meal_parser.py  (adicionar)
from src.nutrition.food_db import FoodDB
from src.nutrition.meal_parser import parse_meal

CUSTOM = {"whey soldier": {"name": "whey soldier", "base_unit": "porcao",
                           "porcao_g": 30, "macros": {"kcal": 120, "p": 24, "c": 3, "g": 1.5}}}


def test_parse_scoop_custom():
    db = FoodDB("tests/fixtures/taco_min.csv", custom=CUSTOM)
    out = parse_meal("2 scoops whey soldier", db)
    item = out["items"][0]
    assert item["recognized"] is True
    assert item["kcal"] == 240          # 2 * 120
    assert item["p"] == 48


def test_parse_custom_em_gramas():
    db = FoodDB("tests/fixtures/taco_min.csv", custom=CUSTOM)
    out = parse_meal("60g whey soldier", db)   # 60g = 2 porções de 30g
    item = out["items"][0]
    assert round(item["kcal"]) == 240
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_meal_parser.py::test_parse_scoop_custom -v`
Expected: FAIL — `KeyError` ou `recognized False` (match retorna `per_portion`, não tratado)

- [ ] **Step 3: Write minimal implementation**

Adicionar helper e tratar `per_portion` em `_parse_item`. Substituir o corpo de `_parse_item`:

```python
def _from_portion(hit: dict, qty: float) -> dict:
    pp = hit["per_portion"]
    return {k: pp[k] * qty for k in ("kcal", "p", "c", "g")}


def _parse_item(raw: str, db) -> dict:
    raw = raw.strip()
    m = _GRAMS.match(raw)
    if m:
        grams, name = _num(m.group(1)), m.group(2)
        hit = db.match(name)
        if hit and "per100" in hit:
            return {"raw": raw, "food": hit["name"], "grams": grams,
                    "recognized": True, **_macros(hit["per100"], grams)}
        if hit and "per_portion" in hit:
            qty = grams / hit["portion_g"]
            return {"raw": raw, "food": hit["name"], "grams": grams,
                    "recognized": True, **_from_portion(hit, qty)}
        return {"raw": raw, "recognized": False}
    u = _UNIT.match(raw)
    if u:
        qty, name = _num(u.group(1)), u.group(2)
        # "2 scoops whey soldier" -> remove unidade de medida solta antes do nome custom
        name_clean = re.sub(r"^(scoops?|colheres?|unidades?|fatias?)\s+", "", name, flags=re.I)
        hit = db.match(name_clean)
        if hit and "per_portion" in hit:
            return {"raw": raw, "food": hit["name"], "grams": qty * hit["portion_g"],
                    "recognized": True, **_from_portion(hit, qty)}
        pg = db.portion_grams(name)
        hit2 = db.match(name)
        if pg and hit2 and "per100" in hit2:
            grams = qty * pg
            return {"raw": raw, "food": hit2["name"], "grams": grams,
                    "recognized": True, **_macros(hit2["per100"], grams)}
        return {"raw": raw, "recognized": False}
    return {"raw": raw, "recognized": False}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_meal_parser.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/meal_parser.py tests/test_meal_parser.py
git commit -m "feat(nutrition): parser entende porcao/scoop de custom_foods"
```

---

### Task 9: Leitura de rótulo por visão (`label_vision.py`)

**Files:**
- Create: `src/nutrition/label_vision.py`
- Test: `tests/test_label_vision.py`

**Interfaces:**
- Produces:
  - `parse_label_response(text: str) -> dict | None` — parse tolerante do JSON retornado pelo modelo; campos faltando ou JSON inválido → `None`. Sucesso → `{"name","base_unit","porcao_g","kcal","p","c","g"}`.
  - `extract_label(image_bytes: bytes, *, client, model: str) -> dict | None` — monta a chamada Anthropic vision e delega a `parse_label_response`. `client` é injetável (mockado nos testes; nunca bate na rede no teste).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_label_vision.py
from types import SimpleNamespace
from src.nutrition.label_vision import parse_label_response, extract_label


def test_parse_json_valido():
    txt = '{"name":"whey soldier","base_unit":"porcao","porcao_g":30,"kcal":120,"p":24,"c":3,"g":1.5}'
    out = parse_label_response(txt)
    assert out["base_unit"] == "porcao" and out["p"] == 24


def test_parse_json_com_cerca_e_virgula_decimal():
    txt = '```json\n{"name":"tapioca","base_unit":"100g","porcao_g":null,"kcal":240,"p":"0,5","c":60,"g":0.1}\n```'
    out = parse_label_response(txt)
    assert out["base_unit"] == "100g" and out["p"] == 0.5


def test_parse_invalido():
    assert parse_label_response("desculpe, não consegui ler") is None
    assert parse_label_response('{"kcal":120}') is None     # faltam campos


def test_extract_usa_cliente_mock():
    fake_resp = SimpleNamespace(content=[SimpleNamespace(
        text='{"name":"x","base_unit":"100g","porcao_g":null,"kcal":50,"p":1,"c":2,"g":0.3}')])
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: fake_resp))
    out = extract_label(b"fakeimg", client=fake_client, model="claude-opus-4-8")
    assert out["kcal"] == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_label_vision.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.nutrition.label_vision'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nutrition/label_vision.py
import base64
import json
import re

_REQUIRED = ("name", "base_unit", "kcal", "p", "c", "g")

_PROMPT = (
    "Você recebe a foto de uma tabela nutricional brasileira (padrão ANVISA). "
    "Responda APENAS um JSON com as chaves: name (string curta do alimento), "
    "base_unit ('100g' se os valores são por 100g, 'porcao' se por porção), "
    "porcao_g (gramas de 1 porção, ou null), kcal, p (proteína g), c (carboidrato g), "
    "g (gordura g). Use os valores da coluna correspondente a base_unit. "
    "Números com ponto decimal. Sem texto fora do JSON."
)


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        return float(s)
    raise ValueError("not a number")


def parse_label_response(text: str):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if any(k not in raw for k in _REQUIRED):
        return None
    try:
        return {
            "name": str(raw["name"]).strip(),
            "base_unit": "porcao" if str(raw["base_unit"]).startswith("por") else "100g",
            "porcao_g": _num(raw["porcao_g"]) if raw.get("porcao_g") not in (None, "null") else None,
            "kcal": _num(raw["kcal"]),
            "p": _num(raw["p"]),
            "c": _num(raw["c"]),
            "g": _num(raw["g"]),
        }
    except (ValueError, TypeError):
        return None


def extract_label(image_bytes: bytes, *, client, model: str):
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    text = resp.content[0].text if resp.content else ""
    return parse_label_response(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_label_vision.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nutrition/label_vision.py tests/test_label_vision.py
git commit -m "feat(nutrition): leitura de rotulo por visao (parse tolerante + cliente injetavel)"
```

---

### Task 10: Gráfico de anéis `/dieta` (`nutrition_chart_png`)

**Files:**
- Modify: `bot/charts.py`
- Test: `tests/bot/test_nutrition_chart.py`

**Interfaces:**
- Consumes: totais do dia + alvo + EA (Tasks 2 e 6).
- Produces: `nutrition_chart_png(totals: dict, target: dict, ea: dict, *, titulo: str = "") -> io.BytesIO` — PNG com anel central de kcal + 3 anéis (P/C/G) + selo de EA. Retorna buffer PNG não-vazio.

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_nutrition_chart.py
from bot.charts import nutrition_chart_png


def test_gera_png_nao_vazio():
    totals = {"kcal": 1840, "p": 98, "c": 210, "g": 48}
    target = {"kcal": 2500, "protein_g": 165, "carb_g": 290, "fat_g": 60}
    ea = {"ea": 32.0, "faixa": "verde"}
    buf = nutrition_chart_png(totals, target, ea, titulo="Hoje")
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"     # assinatura PNG
    assert len(data) > 1000


def test_lida_com_alvo_zero():
    buf = nutrition_chart_png({"kcal": 0, "p": 0, "c": 0, "g": 0},
                              {"kcal": 0, "protein_g": 0, "carb_g": 0, "fat_g": 0},
                              {"ea": 0, "faixa": "vermelho"})
    assert buf.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bot/test_nutrition_chart.py -v`
Expected: FAIL — `ImportError: cannot import name 'nutrition_chart_png'`

- [ ] **Step 3: Write minimal implementation**

Adicionar em `bot/charts.py`:

```python
_FAIXA_COR = {"verde": "#2e9e5b", "amarelo": "#d99a14", "vermelho": "#c0392b"}


def _ring(ax, frac, label, value_txt, color):
    frac = max(0.0, min(1.0, frac))
    ax.pie([frac, 1 - frac], colors=[color, "#2b2b2b"], startangle=90,
           counterclock=False, radius=1.0,
           wedgeprops=dict(width=0.30, edgecolor="none"))
    ax.set_aspect("equal")
    ax.text(0, 0.15, value_txt, ha="center", va="center", fontsize=11,
            color="#f0f0f0", fontweight="bold")
    ax.text(0, -0.35, label, ha="center", va="center", fontsize=9, color="#bdbdbd")


def nutrition_chart_png(totals, target, ea, *, titulo=""):
    def frac(cur, tot):
        return (cur / tot) if tot else 0.0

    fig = plt.figure(figsize=(7, 4.2))
    fig.patch.set_facecolor("#1e1e1e")
    gs = fig.add_gridspec(2, 3)

    ax_kcal = fig.add_subplot(gs[0, :])
    kc = _FAIXA_COR.get(ea.get("faixa"), "#3b7dd8")
    _ring(ax_kcal, frac(totals["kcal"], target["kcal"]),
          f"kcal — EA {ea.get('faixa','?')}",
          f"{round(totals['kcal'])}/{round(target['kcal'])}", kc)

    specs = [("prot", totals["p"], target["protein_g"], "#3b7dd8"),
             ("carb", totals["c"], target["carb_g"], "#d99a14"),
             ("gord", totals["g"], target["fat_g"], "#9b59b6")]
    for i, (lbl, cur, tot, col) in enumerate(specs):
        ax = fig.add_subplot(gs[1, i])
        _ring(ax, frac(cur, tot), lbl, f"{round(cur)}/{round(tot)}g", col)

    if titulo:
        fig.suptitle(titulo, color="#f0f0f0", fontsize=13)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bot/test_nutrition_chart.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/charts.py tests/bot/test_nutrition_chart.py
git commit -m "feat(nutrition): grafico de aneis /dieta (kcal + macros + EA)"
```

---

### Task 11: Serviço de nutrição do bot (`bot/nutrition.py`) — montar FoodDB e contexto do dia

**Files:**
- Create: `bot/nutrition.py`
- Test: `tests/bot/test_bot_nutrition.py`

**Interfaces:**
- Consumes: `config.nutrition_config`, `targets.day_target`, `targets.energy_availability`, `store.*`, `food_db.FoodDB` (Tasks 1-7).
- Produces:
  - `load_food_db(db_path, taco_path="src/nutrition/data/taco.csv") -> FoodDB` — TACO + custom_foods.
  - `today_panel(db_path, profile, date, exercise_kcal=0.0) -> dict` → `{"totals","target","ea","training"}` lendo `day_plan` (treina/corre → `training=True`).

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_bot_nutrition.py
import src.nutrition.store as store
from src.history_db import HistoryDB
from bot.nutrition import load_food_db, today_panel

PROFILE = {"peso_kg": 108, "percentual_gordura": 30}


def _db(tmp_path):
    p = str(tmp_path / "h.db")
    HistoryDB(p)
    return p


def test_load_food_db_inclui_custom(tmp_path):
    p = _db(tmp_path)
    store.add_custom_food(p, "whey soldier", "porcao", 30, 120, 24, 3, 1.5)
    db = load_food_db(p, taco_path="tests/fixtures/taco_min.csv")
    assert db.match("whey soldier")["per_portion"]["p"] == 24
    assert db.match("arroz cozido") is not None


def test_today_panel_descanso(tmp_path):
    p = _db(tmp_path)
    store.set_day_plan(p, "2026-06-30", vai_treinar=0, vai_correr=0)
    store.save_meal_items(p, "2026-06-30", "almoço",
                          [{"recognized": True, "food": "x", "grams": 100,
                            "kcal": 500, "p": 40, "c": 50, "g": 10}])
    panel = today_panel(p, PROFILE, "2026-06-30")
    assert panel["training"] is False
    assert round(panel["target"]["kcal"]) == 2104
    assert panel["totals"]["kcal"] == 500
    assert panel["ea"]["faixa"] in ("verde", "amarelo", "vermelho")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bot/test_bot_nutrition.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.nutrition'`

- [ ] **Step 3: Write minimal implementation**

```python
# bot/nutrition.py
from src.nutrition.config import nutrition_config
from src.nutrition.targets import day_target, energy_availability
from src.nutrition.food_db import FoodDB
import src.nutrition.store as store


def load_food_db(db_path, taco_path="src/nutrition/data/taco.csv"):
    return FoodDB(taco_path, custom=store.get_custom_foods(db_path))


def today_panel(db_path, profile, date, exercise_kcal=0.0):
    cfg = nutrition_config(profile)
    plan = store.get_day_plan(db_path, date) or {}
    training = bool(plan.get("vai_treinar") or plan.get("vai_correr"))
    totals = store.day_totals(db_path, date)
    target = day_target(cfg, training=training, exercise_kcal=exercise_kcal)
    ea = energy_availability(cfg, totals["kcal"], exercise_kcal)
    return {"totals": totals, "target": target, "ea": ea, "training": training}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bot/test_bot_nutrition.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/nutrition.py tests/bot/test_bot_nutrition.py
git commit -m "feat(nutrition): servico do bot (load FoodDB + painel do dia)"
```

---

### Task 12: Handlers `/comi` (confirmação) e `/dieta` (gráfico)

**Files:**
- Modify: `bot/handlers.py`
- Create: `bot/nutrition_format.py` (texto de confirmação — função pura, testável)
- Test: `tests/bot/test_nutrition_format.py`

**Interfaces:**
- Consumes: `parse_meal` (Task 8), `today_panel`/`load_food_db` (Task 11), `nutrition_chart_png` (Task 10), `store.save_meal_items`/`delete_last_meal_item` (Task 6).
- Produces:
  - `bot/nutrition_format.py`: `format_meal_confirm(parsed: dict) -> str` — eco do que foi entendido (itens reconhecidos com macros + total + marca dos não-reconhecidos).
  - `handlers.cmd_comi(update, context)` — parseia, guarda `parsed` em `context.user_data["pending_meal"]`, manda texto + teclado `[✅ salvar][✏️ corrigir]` (callbacks `nut:save` / `nut:edit`). Sem texto → ajuda.
  - `handlers.on_nutrition_button(update, context)` — trata `nut:save` (grava via `save_meal_items`, responde total) e `nut:del` (apaga última).
  - `handlers.cmd_dieta(update, context)` — monta `today_panel`, envia `nutrition_chart_png` como foto + botão `[🗑 apagar última]` (callback `nut:del`).

- [ ] **Step 1: Write the failing test (parte pura)**

```python
# tests/bot/test_nutrition_format.py
from bot.nutrition_format import format_meal_confirm


def test_confirm_lista_itens_e_total():
    parsed = {"meal": "almoço", "items": [
        {"recognized": True, "food": "arroz cozido", "grams": 100,
         "kcal": 128, "p": 2.5, "c": 28, "g": 0.2},
        {"recognized": True, "food": "peito de frango grelhado", "grams": 200,
         "kcal": 318, "p": 62, "c": 0, "g": 7},
    ]}
    txt = format_meal_confirm(parsed)
    assert "Almoço" in txt
    assert "arroz cozido" in txt
    assert "446" in txt          # total kcal 128+318


def test_confirm_marca_nao_reconhecido():
    parsed = {"meal": None, "items": [{"recognized": False, "raw": "patinho"}]}
    txt = format_meal_confirm(parsed)
    assert "patinho" in txt
    assert "não" in txt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bot/test_nutrition_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.nutrition_format'`

- [ ] **Step 3: Write minimal implementation (format puro)**

```python
# bot/nutrition_format.py


def format_meal_confirm(parsed: dict) -> str:
    meal = (parsed.get("meal") or "Refeição").capitalize()
    lines = [f"🍽 {meal}"]
    tot = {"kcal": 0.0, "p": 0.0, "c": 0.0, "g": 0.0}
    desconhecidos = []
    for it in parsed["items"]:
        if it.get("recognized"):
            for k in tot:
                tot[k] += it[k]
            lines.append(
                f"• {it['food']} {round(it['grams'])}g → {round(it['kcal'])} kcal · "
                f"P {it['p']:.0f} · C {it['c']:.0f} · G {it['g']:.0f}"
            )
        else:
            desconhecidos.append(it["raw"])
    lines.append(
        f"─ total: {round(tot['kcal'])} kcal · P {tot['p']:.0f} · "
        f"C {tot['c']:.0f} · G {tot['g']:.0f}"
    )
    for d in desconhecidos:
        lines.append(f"❓ não reconheci \"{d}\" — cadastra ou corrige")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bot/test_nutrition_format.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Add handlers (manual wiring — sem teste unitário de IO do Telegram)**

Em `bot/handlers.py` adicionar imports:

```python
from bot.charts import nutrition_chart_png
from bot.nutrition import load_food_db, today_panel
from bot.nutrition_format import format_meal_confirm
from src.nutrition.meal_parser import parse_meal
import src.nutrition.store as store
import json
```

E os handlers:

```python
def _profile(context):
    return context.bot_data.get("profile") or {}


async def cmd_comi(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        await update.message.reply_text(
            "Use: /comi almoço: 100g arroz, 200g frango, 1 ovo")
        return
    fdb = load_food_db(db_path)
    parsed = parse_meal(text, fdb)
    context.user_data["pending_meal"] = parsed
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ salvar", callback_data="nut:save"),
        InlineKeyboardButton("✏️ corrigir", callback_data="nut:edit"),
    ]])
    await update.message.reply_text(format_meal_confirm(parsed), reply_markup=kb)


async def on_nutrition_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    db_path = context.bot_data["db_path"]
    day = dt.date.today().isoformat()
    if q.data == "nut:save":
        parsed = context.user_data.get("pending_meal")
        if not parsed:
            await q.edit_message_text("Nada pra salvar.")
            return
        store.save_meal_items(db_path, day, parsed.get("meal"), parsed["items"])
        context.user_data.pop("pending_meal", None)
        t = store.day_totals(db_path, day)
        await q.edit_message_text(f"Salvo. Hoje: {round(t['kcal'])} kcal · P {t['p']:.0f}")
    elif q.data == "nut:edit":
        await q.edit_message_text("Reenvie a refeição com /comi corrigindo o item.")
    elif q.data == "nut:del":
        ok = store.delete_last_meal_item(db_path, day)
        await q.edit_message_text("Última refeição apagada." if ok else "Nada pra apagar.")


async def cmd_dieta(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
    day = dt.date.today().isoformat()
    panel = today_panel(db_path, _profile(context), day)
    titulo = "Hoje (dia treino)" if panel["training"] else "Hoje (descanso)"
    png = nutrition_chart_png(panel["totals"], panel["target"], panel["ea"], titulo=titulo)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 apagar última", callback_data="nut:del")]])
    await update.message.reply_photo(png, reply_markup=kb)
```

- [ ] **Step 6: Run the full suite to confirm nothing broke**

Run: `pytest -q`
Expected: PASS (handlers não têm teste de IO; suíte das partes puras verde)

- [ ] **Step 7: Commit**

```bash
git add bot/handlers.py bot/nutrition_format.py tests/bot/test_nutrition_format.py
git commit -m "feat(nutrition): handlers /comi (confirma) e /dieta (grafico)"
```

---

### Task 13: Cadastro de alimento novo (foto da tabela + manual)

**Files:**
- Modify: `bot/handlers.py`
- Modify: `bot/config.py` (env do modelo de visão, se ainda não houver)
- Test: `tests/bot/test_cadastro_parse.py`

**Interfaces:**
- Consumes: `extract_label` (Task 9), `store.add_custom_food` (Task 6).
- Produces:
  - `bot/handlers.py`: `parse_manual_macros(text: str) -> dict | None` — função pura: `"120 24 3 1.5"` → `{"kcal":120,"p":24,"c":3,"g":1.5}`; entrada inválida → `None`.
  - Fluxo: refeição com item não reconhecido oferece `[📷 foto da tabela][⌨ digitar macros]` (callbacks `nut:photo`/`nut:manual`), guarda o nome pendente em `context.user_data["pending_food"]`.
  - `on_photo(update, context)` — se há `pending_food`, baixa a foto, chama `extract_label` com o cliente Anthropic de `context.bot_data["anthropic"]`, mostra leitura + `[✅ salvar][⌨ digitar]`; salva em `custom_foods` na confirmação.
  - `on_manual_macros(update, context)` — recebe texto de macros via `parse_manual_macros`, salva.

- [ ] **Step 1: Write the failing test (parte pura)**

```python
# tests/bot/test_cadastro_parse.py
from bot.handlers import parse_manual_macros


def test_parse_macros_ok():
    assert parse_manual_macros("120 24 3 1.5") == {"kcal": 120, "p": 24, "c": 3, "g": 1.5}


def test_parse_macros_virgula():
    assert parse_manual_macros("120 24 3 1,5")["g"] == 1.5


def test_parse_macros_invalido():
    assert parse_manual_macros("abc") is None
    assert parse_manual_macros("120 24") is None      # faltam campos
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bot/test_cadastro_parse.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_manual_macros'`

- [ ] **Step 3: Write minimal implementation (parte pura)**

Em `bot/handlers.py`:

```python
def parse_manual_macros(text: str):
    parts = (text or "").replace(",", ".").split()
    if len(parts) != 4:
        return None
    try:
        kcal, p, c, g = (float(x) for x in parts)
    except ValueError:
        return None
    return {"kcal": kcal, "p": p, "c": c, "g": g}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bot/test_cadastro_parse.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add the photo/manual flow handlers (manual wiring)**

Em `bot/handlers.py` adicionar:

```python
from src.nutrition.label_vision import extract_label


async def on_photo(update, context):
    if not _authorized(update, context):
        return
    name = context.user_data.get("pending_food")
    if not name:
        return                                  # foto sem contexto de cadastro: ignora
    client = context.bot_data.get("anthropic")
    model = context.bot_data["cfg"].vision_model
    photo = update.message.photo[-1]
    f = await photo.get_file()
    buf = await f.download_as_bytearray()
    data = extract_label(bytes(buf), client=client, model=model)
    if not data:
        await update.message.reply_text(
            "Não consegui ler a tabela. Manda os macros: kcal proteína carbo gordura "
            "(ex.: 120 24 3 1.5)")
        context.user_data["awaiting_manual"] = name
        return
    data["name"] = name
    context.user_data["pending_custom"] = data
    base = "porção" if data["base_unit"] == "porcao" else "100g"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ salvar", callback_data="nut:foodsave"),
        InlineKeyboardButton("⌨ digitar", callback_data="nut:manual"),
    ]])
    await update.message.reply_text(
        f"Li ({base}): {round(data['kcal'])} kcal · P {data['p']:.0f} · "
        f"C {data['c']:.0f} · G {data['g']:.0f}. Confere?", reply_markup=kb)


async def on_text_macros(update, context):
    if not _authorized(update, context):
        return
    name = context.user_data.get("awaiting_manual")
    if not name:
        return
    macros = parse_manual_macros(update.message.text)
    if not macros:
        await update.message.reply_text("Formato: kcal proteína carbo gordura (ex.: 120 24 3 1.5)")
        return
    db_path = context.bot_data["db_path"]
    store.add_custom_food(db_path, name, "100g", None,
                          macros["kcal"], macros["p"], macros["c"], macros["g"])
    context.user_data.pop("awaiting_manual", None)
    await update.message.reply_text(f"Cadastrado: {name}. Refaça o /comi.")
```

Estender `on_nutrition_button` com os novos callbacks:

```python
    elif q.data == "nut:foodsave":
        data = context.user_data.pop("pending_custom", None)
        if data:
            store.add_custom_food(db_path, data["name"], data["base_unit"],
                                  data.get("porcao_g"), data["kcal"], data["p"],
                                  data["c"], data["g"])
            await q.edit_message_text(f"Cadastrado: {data['name']}. Refaça o /comi.")
    elif q.data == "nut:manual":
        name = (context.user_data.get("pending_custom") or {}).get("name") \
            or context.user_data.get("pending_food")
        context.user_data["awaiting_manual"] = name
        await q.edit_message_text(
            "Manda: kcal proteína carbo gordura (ex.: 120 24 3 1.5)")
```

E no `format_meal_confirm` o teclado do `/comi` (Task 12) ganha, quando há item não reconhecido, os botões `[📷 foto da tabela]` (`nut:photo`) e `[⌨ digitar macros]` (`nut:manual`); `nut:photo` apenas grava `context.user_data["pending_food"] = <primeiro raw não reconhecido>` e instrui a mandar a foto. (Ajuste no `cmd_comi`: ao detectar item não reconhecido, setar `pending_food` e incluir esses botões.)

- [ ] **Step 6: Run test suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add bot/handlers.py bot/config.py tests/bot/test_cadastro_parse.py
git commit -m "feat(nutrition): cadastro de alimento novo (foto da tabela + manual)"
```

---

### Task 14: Job matinal (plano do dia) + wiring no `bot/main.py`

**Files:**
- Modify: `bot/jobs.py`
- Modify: `bot/handlers.py` (callback `dp:*` grava `day_plan`)
- Modify: `bot/main.py` (registrar handlers + job; injetar `db_path`, `profile`, `anthropic`, `vision_model` em `bot_data`)
- Modify: `bot/config.py` (campo `vision_model`)
- Test: `tests/bot/test_day_plan_callback.py`

**Interfaces:**
- Consumes: `store.set_day_plan` (Task 6).
- Produces:
  - `bot/handlers.py`: `parse_day_plan_callback(data: str) -> tuple[int,int]` — `"dp:treino"`→`(1,0)`, `"dp:corrida"`→`(0,1)`, `"dp:ambos"`→`(1,1)`, `"dp:descanso"`→`(0,0)`.
  - `handlers.on_day_plan_button(update, context)` — grava `day_plan` do dia.
  - `jobs.job_day_plan(context)` — manda a pergunta da manhã com o teclado.
  - `bot/main.py` registra: `CommandHandler("comi")`, `CommandHandler("dieta")`, `CallbackQueryHandler(on_nutrition_button, pattern=r"^nut:")`, `CallbackQueryHandler(on_day_plan_button, pattern=r"^dp:")`, `MessageHandler(filters.PHOTO, on_photo)`, `MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_macros)`, e `run_daily(jobs.job_day_plan, time=07:30)`.

- [ ] **Step 1: Write the failing test (parte pura)**

```python
# tests/bot/test_day_plan_callback.py
from bot.handlers import parse_day_plan_callback


def test_mapeia_callbacks():
    assert parse_day_plan_callback("dp:treino") == (1, 0)
    assert parse_day_plan_callback("dp:corrida") == (0, 1)
    assert parse_day_plan_callback("dp:ambos") == (1, 1)
    assert parse_day_plan_callback("dp:descanso") == (0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bot/test_day_plan_callback.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_day_plan_callback'`

- [ ] **Step 3: Write minimal implementation**

Em `bot/handlers.py`:

```python
_DP_MAP = {"dp:treino": (1, 0), "dp:corrida": (0, 1),
           "dp:ambos": (1, 1), "dp:descanso": (0, 0)}


def parse_day_plan_callback(data: str):
    return _DP_MAP.get(data, (0, 0))


async def on_day_plan_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    treina, corre = parse_day_plan_callback(q.data)
    day = dt.date.today().isoformat()
    store.set_day_plan(context.bot_data["db_path"], day, treina, corre)
    await q.edit_message_text("Anotado o plano de hoje. Use /dieta pra ver os alvos.")
```

Em `bot/jobs.py`:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def job_day_plan(context):
    cfg = context.bot_data["cfg"]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏋 treinar", callback_data="dp:treino"),
        InlineKeyboardButton("🏃 correr", callback_data="dp:corrida"),
    ], [
        InlineKeyboardButton("💪🏃 os 2", callback_data="dp:ambos"),
        InlineKeyboardButton("😴 descanso", callback_data="dp:descanso"),
    ]])
    await context.bot.send_message(chat_id=cfg.chat_id,
                                   text="Bom dia. Hoje você vai:", reply_markup=kb)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bot/test_day_plan_callback.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Wire everything in bot/main.py and config**

Em `bot/config.py`, adicionar ao objeto de config o campo `vision_model` (env `VISION_MODEL`, default `claude-opus-4-8`).

Em `bot/main.py`:

```python
from telegram.ext import MessageHandler, filters
import json
import anthropic

# ... onde bot_data é populado (db, client, cfg):
app.bot_data["db_path"] = cfg.db_path          # caminho do history.db já usado pelo HistoryDB
with open("athlete_profile.json", encoding="utf-8") as fh:
    app.bot_data["profile"] = json.load(fh)
app.bot_data["anthropic"] = anthropic.Anthropic()   # usa ANTHROPIC_API_KEY do ambiente

app.add_handler(CommandHandler("comi", handlers.cmd_comi))
app.add_handler(CommandHandler("dieta", handlers.cmd_dieta))
app.add_handler(CallbackQueryHandler(handlers.on_nutrition_button, pattern=r"^nut:"))
app.add_handler(CallbackQueryHandler(handlers.on_day_plan_button, pattern=r"^dp:"))
app.add_handler(MessageHandler(filters.PHOTO, handlers.on_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text_macros))

app.job_queue.run_daily(jobs.job_day_plan, time=dt.time(hour=7, minute=30))
```

Atualizar o texto de `cmd_start` incluindo:
```
/comi — registrar refeição
/dieta — macros e energia do dia
```

(Confirmar o nome real do campo de caminho do DB em `bot/config.py`/`bot/main.py`; se o `HistoryDB` é instanciado com um path conhecido, reusar esse mesmo valor em `bot_data["db_path"]`.)

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 7: Smoke check de import**

Run: `python -c "import bot.main, bot.handlers, bot.jobs, bot.nutrition, bot.nutrition_format"`
Expected: sem erro de import

- [ ] **Step 8: Commit**

```bash
git add bot/jobs.py bot/handlers.py bot/main.py bot/config.py tests/bot/test_day_plan_callback.py
git commit -m "feat(nutrition): job matinal do plano do dia + wiring dos handlers"
```

---

### Task 15: Atualizar CLAUDE.md (premissa LLM + nutrição)

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** nenhuma (documentação).

- [ ] **Step 1: Update CLAUDE.md**

Ajustar as seções que afirmam "sem provedor pago" / "LLM local obrigatória":
- Registrar que o **LLM local saiu**; a API Anthropic é usada de forma pontual (visão de rótulo no cadastro de alimento). Remover/expandir a regra "nada de API paga, nada de `anthropic`".
- Adicionar `src/nutrition/` à seção Estrutura (food_db, meal_parser, targets, label_vision, store).
- Adicionar comandos `/comi` e `/dieta` e o job matinal de plano do dia na descrição do bot.
- Adicionar variáveis de ambiente: `ANTHROPIC_API_KEY`, `VISION_MODEL` (default `claude-opus-4-8`).

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md reflete saida do LLM local + frente de nutricao"
```

---

## Self-Review

**Spec coverage:**
- TACO + lookup determinístico → Tasks 3, 4 ✅
- `custom_foods` (100g/porção) + prioridade → Tasks 6, 7, 8 ✅
- Parser de refeição (gramas/unidade/scoop, não-reconhecido) → Tasks 5, 8 ✅
- Alvos ciclados + EA → Task 2 ✅
- Pergunta da manhã (job + callback `day_plan`) → Task 14 ✅
- `/comi` com confirmação → Task 12 ✅
- `/dieta` PNG anéis → Tasks 10, 12 ✅
- Cadastro foto (Claude vision) + manual → Tasks 9, 13 ✅
- Apagar última → Tasks 6, 12 ✅
- Perfil (108/30, campos nutrição) → Task 1 ✅
- CLAUDE.md (reverter regra LLM) → Task 15 ✅

**Placeholder scan:** Tasks de IO do Telegram (12, 13, 14) não têm teste unitário porque exercitam a API do PTB; as partes puras (`format_meal_confirm`, `parse_manual_macros`, `parse_day_plan_callback`, parser, targets, store, vision-parse) têm teste. Smoke de import (Task 14) cobre regressão de wiring. Sem "TODO/TBD".

**Type consistency:** `match` retorna `per100` (TACO/custom-100g) ou `per_portion`+`portion_g` (custom-porção) — consumido coerentemente em Tasks 8 e a partir do shape de `get_custom_foods` (Task 6). `day_target`/`energy_availability`/`today_panel` usam as mesmas chaves (`kcal,protein_g,carb_g,fat_g`,`ea,faixa`) no gráfico (Task 10) e no painel (Task 11). `nut:*` e `dp:*` callbacks registrados em Task 14 batem com os emitidos em Tasks 12-14.

**Pontos a confirmar na execução:** nome real do campo de caminho do DB e de como `bot_data` é populado em `bot/config.py`/`bot/main.py`; formato exato de `cmd_start`. Esses são ajustes de integração marcados nos passos.
