import csv
import unicodedata

from rapidfuzz import process, fuzz


def normalize(name: str) -> str:
    """Normalize food name: lowercase, no accents, single spaces."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


ALIASES = {
    "frango": "peito de frango grelhado",
    "peito de frango": "peito de frango grelhado",
    "ovo": "ovo de galinha cozido",
    "ovos": "ovo de galinha cozido",
    "feijao": "feijao carioca cozido",
    "banana": "banana prata",
    "arroz": "arroz cozido",
}

# margem mínima de score entre o 1º e o 2º candidato fuzzy. Abaixo dela o match é
# considerado ambíguo (vários alimentos colados) e vira "não reconhecido" → cadastro.
_AMBIGUITY_MARGIN = 5

PORTIONS = {
    "ovo": 50.0,
    "ovos": 50.0,
    "banana": 100.0,
    "fatia de pao": 25.0,
    "pao": 25.0,
}


def load_aliases(csv_path: str) -> dict:
    """Carrega aliases termo->nome de um CSV (colunas: termo,nome). Falta de arquivo = {}."""
    out = {}
    try:
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                termo = (row.get("termo") or "").strip()
                nome = (row.get("nome") or "").strip()
                if termo and nome:
                    out[termo] = nome
    except FileNotFoundError:
        pass
    return out


class FoodDB:
    """Load and lookup foods from TACO CSV by normalized name."""

    def __init__(self, csv_path: str, custom=None, aliases=None, portions=None):
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
        self._custom = {}
        for key, c in (custom or {}).items():
            self._custom[normalize(key)] = c
        # aliases/portions: por instância, com fallback pros globais (compatível com fixture).
        src_aliases = ALIASES if aliases is None else aliases
        self._aliases = {normalize(k): v for k, v in src_aliases.items()}
        src_portions = PORTIONS if portions is None else portions
        self._portions = {normalize(k): v for k, v in src_portions.items()}

    def lookup(self, name: str):
        """Lookup food by name (normalized); returns dict or None."""
        return self._by_name.get(normalize(name))

    def match(self, name: str, threshold: int = 85):
        """Match food by exact, alias, or fuzzy; returns dict with score or None."""
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
            item = self._by_name[key]
            return {**item, "score": 100}
        alias = self._aliases.get(key)
        if alias and normalize(alias) in self._by_name:
            item = self._by_name[normalize(alias)]
            return {**item, "score": 100}
        choices = list(self._by_name.keys())
        results = process.extract(key, choices, scorer=fuzz.WRatio, limit=2)
        if results and results[0][1] >= threshold:
            best = results[0]
            # ambíguo: 2+ alimentos com score colado → não chuta, deixa o usuário cadastrar.
            if len(results) > 1 and (best[1] - results[1][1]) < _AMBIGUITY_MARGIN:
                return None
            item = self._by_name[best[0]]
            return {**item, "score": int(best[1])}
        return None

    def portion_grams(self, name: str):
        """Get standard portion size in grams for a food, or None."""
        key = normalize(name)
        c = self._custom.get(key)
        if c and c.get("porcao_g"):
            return c["porcao_g"]
        return self._portions.get(key)
